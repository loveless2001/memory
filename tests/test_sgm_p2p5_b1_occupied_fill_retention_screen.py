"""CPU checks for the B1 occupied-fill retention screen package: A0-exact config plus the variant,
pre-fill bands with fill telemetry reported beside them, tiny end-to-end arm, runner identities,
memsub binding, gate, restart refusal and the ledger."""

import importlib.util
import json
import math
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load("scripts/sgm-p2p5-b1-occupied-fill-retention-screen-train.py", "b1_train")
R = _load("modal-runners/modal-m4-sgm-p2p5-b1-occupied-fill-retention-screen-runner.py", "b1_runner")
A = _load("modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py", "stage_a_runner")
PROBE = ROOT / R.INPUT_MANIFEST


def test_config_is_a0_plus_the_variant_only():
    import hashlib
    assert hashlib.sha256(PROBE.read_bytes()).hexdigest() == B.STAGE_A.PROBE_S0_MANIFEST_SHA256
    base = json.loads(PROBE.read_text())["pilot_config"]
    b1 = asdict(B.arm_config(base, "cpu"))
    a0 = asdict(B.STAGE_A.arm_config(base, "A0", "cpu"))
    assert {k: v for k, v in b1.items() if k != "sgm"} == {k: v for k, v in a0.items() if k != "sgm"}
    assert a0["sgm"] == {} and b1["sgm"] == B.FILL
    assert (b1["steps"], b1["eval_every"], b1["lr"], b1["seed"], b1["batch"]) == (100, 25, 0.003, 0, 16)
    with pytest.raises(ValueError):
        B.arm_config({**base, "batch": 2}, "cpu")
    with pytest.raises(ValueError):
        B.arm_config({**base, "sgm": {"address_scale": 4.0}}, "cpu")


def _rows(absent, fully):
    rows = [{"step": s, "eval": {"query_empty_read_weight": a, "accuracy": 0.02,
                                 "query_fully_absent_fraction": f, "query_without_occupied_fraction": 0.0,
                                 "query_nearest_occupied_cells_mean": 1.0, "query_fill_support_cells_mean": 2.0}}
            for s, a, f in zip(B.STAGE_A.EVAL_STEPS, absent, fully)]
    return rows + [{"step": 0, "loss": 4.1, "read_anchor": 0.3}, {"step": 90, "loss": 4.0, "read_anchor": 0.1}]


def test_band_uses_pre_fill_absence_and_reports_fill_beside_it():
    s = B.summarize(_rows((.05, .97, .99, .99, .99), (0, .9, .95, .97, .98)))
    assert (s["status"], s["band_at_100"]) == ("valid", "escaped")            # fill carrying != kept
    assert s["fill_by_step"]["100"]["query_fully_absent_fraction"] == .98
    assert s["read_anchor_by_logged_step"] == {"0": 0.3, "90": 0.1}
    k = B.summarize(_rows((.05, .1, .1, .15, .2), (0, 0, 0, 0, 0)))
    assert (k["band_at_100"], k["kept_through_100"]) == ("kept", True)
    assert B.summarize(_rows((.05, .1, .1, .15), (0,) * 4))["status"] == "INVALID"   # missing step 100


def test_tiny_b1_end_to_end(tmp_path):
    from memsub.sgm.synthetic_pilot import PilotConfig
    pcfg = PilotConfig(arm="learned", readout="taskhead", n_bindings=4, n_queries=2, filler_len=4, batch=4,
                       eval_batches=1, seed=0, steps=4, eval_every=2, sgm=dict(B.FILL))
    res = B.run_b1(pcfg, tmp_path / "B1", {"test": True})
    assert res["status"] == "INVALID"                     # tiny eval steps 0/2/4 != 0/25/50/75/100, by design
    assert all(v["query_fully_absent_fraction"] is not None for v in res["fill_by_step"].values())
    assert all(math.isfinite(v) for v in res["read_anchor_by_logged_step"].values())
    man = json.loads((tmp_path / "B1" / "run_manifest.json").read_text())
    assert man["sgm_config"]["read_fallback"] == "occupied_softmax_fill_v1" and man["b1"]["sgm_overrides"] == B.FILL
    assert (tmp_path / "B1" / "trained_parameters.safetensors").exists()


def test_runner_identities_differ_from_stage_a_and_bind_this_memsub():
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    assert (R.APP_NAME, R.START_DICT) != (A.APP_NAME, A.START_DICT) and R.START_DICT not in (A.START_DICT,)
    assert R.ARMS == ("B1",) and R.BASE_IMAGE_ID == A.BASE_IMAGE_ID and R.EXPECT_VERSIONS == A.EXPECT_VERSIONS
    assert R.local_memsub_sha256() == source_tree_sha256(ROOT / "memsub") == R.EXPECT_MEMSUB_SHA256
    assert (R.FUNCTION_S, R.CHILD_S, R.STARTUP_S, R.MIN_ARM_S, R.END_MARGIN_S) == (1560, 1500, 300, 600, 90)


def test_ledger_within_cap_and_launch_timeout_matches():
    led = R.ledger()
    assert led["reservation_usd"] <= led["cap_usd"] == 2.5
    assert led["reservation_usd"] == pytest.approx((R.CAMPAIGN_S + R.CLIENT_TAIL_S + R.STOP_ALLOWANCE_S) * led["rate_usd_s"])
    sh = (ROOT / "plans/261009-1040-m4-sgm-p2p5-b1-occupied-fill-retention-screen/launch-b1-once.sh").read_text()
    assert f"--kill-after=30s {R.OUTER_S - 30} " in sh and R.SCRIPT.split("/")[-1] not in sh


def _write(dest, **kw):
    (dest / "B1").mkdir(parents=True)
    (dest / "B1" / "b1_result.json").write_text(json.dumps({"arm": "B1", **kw}))


def test_runner_gate(tmp_path):
    assert not R.gate_ok("B1", tmp_path, {"refused": "x"})[0]
    assert not R.gate_ok("B1", tmp_path, {"returncode": 1})[0]
    assert not R.gate_ok("B1", tmp_path, {"returncode": 0})[0]                  # no result file
    _write(tmp_path / "a", status="INVALID", why="w")
    assert not R.gate_ok("B1", tmp_path / "a", {"returncode": 0})[0]
    for band in ("escaped", "partial", "kept"):                                 # any valid band is a clean finish
        _write(tmp_path / band, status="valid", band_at_100=band)
        assert R.gate_ok("B1", tmp_path / band, {"returncode": 0})[0]


class _FakeDict:
    def __init__(self):
        self.d = {}

    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self.d:
            return False
        self.d[k] = v
        return True


def test_one_campaign_deadline_per_dict():
    d = _FakeDict()
    t = R.set_campaign_deadline(d, 1000.0)
    assert t == 1000.0 + R.CAMPAIGN_S
    with pytest.raises(SystemExit):
        R.set_campaign_deadline(d, 2000.0)
