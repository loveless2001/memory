"""Focused CPU checks for the Stage A read-escape blocker screen (proposal v0.2): endpoint bands and
INVALID handling, arm configs bound to the probe recipe, tiny end-to-end arms (A2 aux path included),
runner gate, restart refusal and the all-in ledger."""

import importlib.util
import json
import math
import io
import subprocess
import tarfile
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = _load("scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py", "stage_a_train")
R = _load("modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py", "stage_a_runner")
PROBE = ROOT / R.INPUT_MANIFEST


def _rows(vals):
    return [{"step": s, "eval": {"query_empty_read_weight": v}} for s, v in zip(T.EVAL_STEPS, vals)] + [{"step": 10, "loss": 4.1}]


@pytest.mark.parametrize("vals,band,through", [
    ((.05, .5, .95, .99, .99), "escaped", False),
    ((.05, .1, .1, .15, .2), "kept", True),
    ((.05, .3, .1, .1, .1), "kept", False),          # kept AT 100 but not THROUGH 100
    ((.05, .3, .5, .6, .7), "partial", False),
    ((0.0, 0.0, 0.0, 0.0, 0.2), "kept", True),         # boundaries: 0 and exactly .2 are kept
    ((.05, .5, .9, 1.0, 0.9), "escaped", False),       # exactly .9 escaped; 1.0 valid
])
def test_classify_bands(vals, band, through):
    r = T.classify(_rows(vals))
    assert r["status"] == "valid" and r["band_at_100"] == band and r["kept_through_100"] is through


@pytest.mark.parametrize("rows", [
    _rows((.05, .1, .1, .1))[:3],                                         # missing endpoints
    _rows((.05, .1, .1, .1, .1)) + [{"step": 100, "eval": {"query_empty_read_weight": .1}}],   # duplicate
    _rows((.05, .1, .1, .1, float("nan"))),                               # non-finite
    _rows((.05, .1, .1, .1, None)),                                       # missing value
    _rows((.05, .1, .1, .1, -0.1)),                                       # below 0 (codex 21987)
    _rows((.05, .1, .1, .1, 1.1)),                                        # above 1
    _rows((.05, .1, .1, .1, True)),                                       # boolean
    _rows((.05, False, .1, .1, .1)),                                      # boolean at a non-endpoint step
])
def test_classify_invalid(rows):
    assert T.classify(rows)["status"] == "INVALID"


def test_probe_manifest_binding_and_arm_configs():
    import hashlib
    assert hashlib.sha256(PROBE.read_bytes()).hexdigest() == T.PROBE_S0_MANIFEST_SHA256
    base = json.loads(PROBE.read_text())["pilot_config"]
    a0, a1, a2 = (T.arm_config(base, a, "cpu") for a in ("A0", "A1", "A2"))
    assert (a0.steps, a0.eval_every, a0.lr, a0.aux_address_lambda) == (100, 25, 0.003, 0.0)
    assert (a1.lr, a1.aux_address_lambda) == (3e-4, 0.0) and (a2.lr, a2.aux_address_lambda) == (0.003, 0.1)
    assert a0.seed == 0 and a0.batch == 16 and a0.training_filler_len(99) == 0      # phase 1 throughout
    with pytest.raises(ValueError):
        T.arm_config({**base, "batch": 2}, "A0", "cpu")                          # batch 2 = a different setting


@pytest.mark.parametrize("arm", ["A0", "A1", "A2"])
def test_tiny_arm_end_to_end(tmp_path, arm):
    from memsub.sgm.synthetic_pilot import PilotConfig
    pcfg = PilotConfig(**{**asdict(PilotConfig(arm="learned", readout="taskhead", n_bindings=4, n_queries=2,
                                               filler_len=4, batch=4, eval_batches=1, seed=0)),
                          **T.ARMS[arm], "steps": 4, "eval_every": 2})
    res = T.run_arm(pcfg, arm, tmp_path / arm, {"test": True})
    assert res["status"] == "INVALID"                     # tiny eval steps 0/2/4 != 0/25/50/75/100, by design
    man = json.loads((tmp_path / arm / "run_manifest.json").read_text())
    assert man["stage_a"]["overrides"] == T.ARMS[arm] and ("supervision" in man["stage_a"]) is (arm == "A2")
    rows = [json.loads(x) for x in (tmp_path / arm / "routing_telemetry.jsonl").read_text().splitlines()]
    assert [r["step"] for r in rows if "eval" in r] == [0, 2, 4]
    if arm == "A2":
        aux = [r["aux_address_mse"] for r in rows if "loss" in r]
        assert aux and all(v is not None and math.isfinite(v) for v in aux)
    assert (tmp_path / arm / "trained_parameters.safetensors").exists()


def _write_result(dest, arm, **kw):
    (dest / arm).mkdir(parents=True)
    (dest / arm / "stage_a_result.json").write_text(json.dumps({"arm": arm, **kw}))


def test_runner_gate(tmp_path):
    assert not R.gate_ok("A0", tmp_path, {"refused": "x"})[0]
    assert not R.gate_ok("A0", tmp_path, {"returncode": 1})[0]
    assert not R.gate_ok("A0", tmp_path, {"returncode": 0})[0]                  # no result file
    _write_result(tmp_path, "A0", status="INVALID", why="w")
    assert not R.gate_ok("A0", tmp_path, {"returncode": 0})[0]
    d2 = tmp_path / "b"
    _write_result(d2, "A0", status="valid", band_at_100="partial")
    assert not R.gate_ok("A0", d2, {"returncode": 0})[0]                        # A0 must escape
    _write_result(d2, "A1", status="valid", band_at_100="partial")
    assert R.gate_ok("A1", d2, {"returncode": 0})[0]                            # non-A0 bands continue
    d3 = tmp_path / "c"
    _write_result(d3, "A0", status="valid", band_at_100="escaped")
    assert R.gate_ok("A0", d3, {"returncode": 0})[0]


class _FakeDict:
    def __init__(self):
        self.d = {}

    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self.d:
            return False
        self.d[k] = v
        return True

    def get(self, k):
        return self.d.get(k)


@pytest.fixture
def worker(monkeypatch, tmp_path):
    """The raw remote function in ONE reused (warm) worker: fake Dict, versions OK, fake child that
    writes its own arm dir; temp dirs under tmp_path."""
    fake, calls = _FakeDict(), []
    monkeypatch.setattr(R.modal.Dict, "from_name", lambda *a, **k: fake)
    monkeypatch.setattr(R, "_versions_ok", lambda: {"ok": True, "got": R.EXPECT_VERSIONS})
    real_mkdtemp = tempfile.mkdtemp                     # R.tempfile IS this module: keep the original
    monkeypatch.setattr(R.tempfile, "mkdtemp", lambda prefix: real_mkdtemp(prefix=prefix, dir=tmp_path))

    def child(cmd, **kw):
        calls.append({"cmd": cmd, "timeout": kw["timeout"]})
        arm_out = Path(cmd[cmd.index("--out") + 1])
        arm_out.mkdir(parents=True)
        (arm_out / "stage_a_result.json").write_text(json.dumps({"arm": cmd[cmd.index("--arm") + 1]}))
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(R.subprocess, "run", child)
    return fake, calls, R.run_arm_remote.get_raw_f()


def _members(res):
    with tarfile.open(fileobj=io.BytesIO(res["tar"]), mode="r:gz") as t:
        return {m.name.split("/")[1] for m in t.getmembers() if m.name.count("/") >= 1 and m.name != "."}


def test_warm_worker_runs_a0_a1_a2_with_isolated_outputs(worker):
    fake, calls, raw = worker
    deadline = R.set_campaign_deadline(fake, time.time())
    res = [raw(arm, deadline) for arm in R.ARMS]
    assert [r["returncode"] for r in res] == [0, 0, 0] and len(calls) == 3
    assert [_members(r) & set(R.ARMS) for r in res] == [{"A0"}, {"A1"}, {"A2"}]   # each tar holds only its arm
    assert len({c["cmd"][c["cmd"].index("--out") + 1] for c in calls}) == 3


def test_second_start_refused_before_any_child(worker):
    fake, calls, raw = worker
    deadline = R.set_campaign_deadline(fake, time.time())
    assert raw("A0", deadline)["returncode"] == 0
    assert "refused" in raw("A0", deadline) and len(calls) == 1


def test_campaign_deadline_is_immutable_and_enforced(worker):
    fake, calls, raw = worker
    now = time.time()
    deadline = R.set_campaign_deadline(fake, now)
    with pytest.raises(SystemExit):
        R.set_campaign_deadline(fake, now + 5)                                 # no relaunch on a used Dict
    assert "refused" in raw("A0", deadline + 1)                               # wrong deadline
    fake.d.pop("A1", None)
    fake.d["deadline"] = time.time() + R.MIN_ARM_S - 5
    assert "refused" in raw("A1", fake.d["deadline"])                         # too little time left
    fake.d["deadline"] = time.time() + 1000
    r = raw("A2", fake.d["deadline"])
    assert r["returncode"] == 0 and calls[-1]["timeout"] <= 1000 - R.END_MARGIN_S
    assert len(calls) == 1                                                    # only A2 ran a child


def test_version_mismatch_refuses(worker, monkeypatch):
    fake, calls, raw = worker
    monkeypatch.setattr(R, "_versions_ok", lambda: {"ok": False, "got": {"torch": "x"}})
    assert "refused" in raw("A0", R.set_campaign_deadline(fake, time.time())) and not calls


def test_ledger_bound_within_user_cap():
    led = R.ledger()
    assert led["outer_s"] == R.CAMPAIGN_S + R.CLIENT_TAIL_S and led["image_build_usd"] == 0.0
    assert R.CHILD_S < R.FUNCTION_S and led["bound_usd"] <= R.CAP_USD == 4.0
    assert led["extra_unenforced_seconds_before_cap"] > 0
