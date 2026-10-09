"""CPU checks for the B2 occupied-fill long-run package: probe-s0-exact config plus the variant,
pre-registered memory-use readout, crash-after-checkpoint resume parity, start claims, runner
identities/binding, ledger, launch timeouts and bounded cleanup."""

import hashlib
import importlib.util
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load("scripts/sgm-p2p5-b2-occupied-fill-long-run-train.py", "b2_train")
R = _load("modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-long-run-runner.py", "b2_runner")
R1 = _load("modal-runners/modal-m4-sgm-p2p5-b1-occupied-fill-retention-screen-runner.py", "b1_runner")
PROBE = ROOT / R.INPUT_MANIFEST
LAUNCH = ROOT / "plans/261009-1135-m4-sgm-p2p5-b2-occupied-fill-long-run/launch-b2-once.sh"


def test_config_is_probe_s0_plus_the_variant_only():
    assert hashlib.sha256(PROBE.read_bytes()).hexdigest() == B.STAGE_A.PROBE_S0_MANIFEST_SHA256
    base = json.loads(PROBE.read_text())["pilot_config"]
    b2 = asdict(B.arm_config(base, "cuda"))
    assert b2["sgm"] == B.FILL and (b2["steps"], b2["eval_every"]) == (1500, 100)
    assert {k: v for k, v in b2.items() if k not in ("sgm", "checkpoint_steps")} == \
           {k: v for k, v in base.items() if k not in ("sgm", "checkpoint_steps")}
    for bad in ({"steps": 100}, {"eval_every": 25}, {"sgm": {"address_scale": 4.0}}, {"lr": 3e-4}):
        with pytest.raises(ValueError):
            B.arm_config({**base, **bad}, "cuda")


def _rows(correct_by_step, absent=0.3):
    return [{"step": s, "eval": {"correct": c, "total": 256, "query_empty_read_weight": absent}}
            for s, c in correct_by_step.items()]


@pytest.mark.parametrize("final,derange,used", [(12, 6, True), (12, 7, False), (11, 0, False), (30, 4, True)])
def test_memory_use_needs_gain_and_paired_derange_drop(final, derange, used):
    steps = {s: 4 for s in range(0, 1501, 100)} | {1500: final}
    s = B.summarize(_rows(steps), {"correct": derange})
    assert s["status"] == "valid" and s["memory_used"] is used and s["band_at_end"] == "partial"


def test_summary_invalid_without_every_eval_or_derange():
    steps = {s: 4 for s in range(0, 1501, 100)}
    assert B.summarize(_rows(steps), None)["status"] == "INVALID"
    del steps[700]
    assert B.summarize(_rows(steps), {"correct": 3})["status"] == "INVALID"


def _tiny():
    from memsub.sgm.synthetic_pilot import PilotConfig
    return PilotConfig(arm="learned", readout="taskhead", n_bindings=4, n_queries=2, filler_len=4, batch=4,
                       eval_batches=1, seed=0, steps=4, eval_every=2, sgm=dict(B.FILL))


def _params_sha(out):
    return hashlib.sha256((out / "trained_parameters.safetensors").read_bytes()).hexdigest()


def _rows_wo_time(out):
    return [{k: v for k, v in json.loads(x).items() if k != "sec_per_step"}
            for x in (out / "routing_telemetry.jsonl").read_text().splitlines()]


def test_crash_after_checkpoint_resumes_to_the_uninterrupted_result(tmp_path, monkeypatch):
    ref = tmp_path / "ref" / "B2"
    B.run_b2(_tiny(), ref, {}, checkpoint_every=2)
    out = tmp_path / "crash" / "B2"
    real = B.save_atomic

    def save_then_crash(state, path):
        real(state, path)
        if state["step"] == 2:
            raise RuntimeError("simulated preemption right after the step-2 checkpoint")
    monkeypatch.setattr(B, "save_atomic", save_then_crash)
    with pytest.raises(RuntimeError):
        B.run_b2(_tiny(), out, {}, checkpoint_every=2)
    monkeypatch.setattr(B, "save_atomic", real)
    B.run_b2(_tiny(), out, {}, checkpoint_every=2)                       # second start resumes
    starts = [json.loads(x) for x in out.with_name("B2.starts.jsonl").read_text().splitlines()]
    assert [s["resume_step"] for s in starts] == [None, 2]
    assert _params_sha(out) == _params_sha(ref) and _rows_wo_time(out) == _rows_wo_time(ref)
    assert json.loads((out / "final_bank_derange_eval.json").read_text())["correct"] == \
           json.loads((ref / "final_bank_derange_eval.json").read_text())["correct"]


def test_out_without_checkpoint_is_wiped_but_starts_log_kept(tmp_path):
    out = tmp_path / "B2"
    out.mkdir()
    (out / "routing_telemetry.jsonl").write_text("stale\n")
    out.with_name("B2.starts.jsonl").write_text('{"t": 0, "resume_step": null}\n')
    assert B.prepare_out(out, _tiny()) is None and list(out.iterdir()) == []
    assert out.with_name("B2.starts.jsonl").read_text().count("\n") == 1


class _FakeDict:
    def __init__(self):
        self.d = {}

    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self.d:
            return False
        self.d[k] = v
        return True


def test_start_claims_are_bounded_and_deadline_is_write_once():
    d = _FakeDict()
    assert [R.claim_start(d, {}) for _ in range(R.MAX_STARTS + 1)] == ["start-1", "start-2", "start-3", None]
    t = R.set_campaign_deadline(d, 1000.0)
    assert t == 1000.0 + R.CAMPAIGN_S
    with pytest.raises(SystemExit):
        R.set_campaign_deadline(d, 2000.0)


def test_runner_identities_binding_ledger_and_launch():
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    assert len({R.APP_NAME, R1.APP_NAME}) == 2 and len({R.START_DICT, R1.START_DICT}) == 2
    assert R.VOLUME_NAME.endswith("-v1") and R.ARMS == ("B2",) and R.BASE_IMAGE_ID == R1.BASE_IMAGE_ID
    assert R.local_memsub_sha256() == source_tree_sha256(ROOT / "memsub") == R.EXPECT_MEMSUB_SHA256
    led = R.ledger()
    assert led["reservation_usd"] <= led["cap_usd"] == 17.0 and R.STOP_ALLOWANCE_S == R.CLEANUP_S
    assert led["reservation_usd"] == pytest.approx((R.CAMPAIGN_S + R.CLIENT_TAIL_S + R.CLEANUP_S) * led["rate_usd_s"])
    sh = LAUNCH.read_text()
    assert f"--kill-after=30s {R.OUTER_S - 30} " in sh and f"timeout --signal=KILL {R.CLEANUP_S + 30} " in sh
    assert R.MIN_START_S > R.END_MARGIN_S and R.FUNCTION_S == R.CAMPAIGN_S


def test_gate(tmp_path):
    assert not R.gate_ok("B2", tmp_path, {"refused": "x"})[0]
    assert not R.gate_ok("B2", tmp_path, {"returncode": "timeout"})[0]
    (tmp_path / "B2").mkdir()
    (tmp_path / "B2" / "b2_result.json").write_text(json.dumps({"status": "valid", "memory_used": False,
                                                                 "band_at_end": "partial"}))
    assert R.gate_ok("B2", tmp_path, {"returncode": 0})[0]


def test_cleanup_hanging_cli_stays_within_budget(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"app_id": "ap-test"}))
    clock = {"t": 0.0}

    def hang(cmd, timeout, **kw):
        clock["t"] += timeout
        raise subprocess.TimeoutExpired(cmd, timeout)
    rec = R.cleanup_verify(tmp_path, cp=_load(R.CONTROL_LOGIC_FILE, "cp"), run=hang,
                           sleep=lambda s: clock.__setitem__("t", clock["t"] + s), clock=lambda: clock["t"])
    assert rec["status"] == "shutdown_unresolved" and clock["t"] <= R.CLEANUP_S
