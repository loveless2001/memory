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


B1_EVAL = [json.loads(x) for x in (ROOT / "plans/261009-1040-m4-sgm-p2p5-b1-occupied-fill-retention-screen/"
                                     "b1-run-v1/B1/routing_telemetry.jsonl").read_text().splitlines()
           if "eval" in json.loads(x)][-1]["eval"]                # a REAL evaluator row (B1, update 100)


def _ev(correct, absent=0.3, **kw):
    return {**B1_EVAL, "correct": correct, "total": 256, "accuracy": correct / 256,
            "query_empty_read_weight": absent, **kw}


def _rows(correct_by_step, absent=0.3):
    return [{"step": s, "eval": _ev(c, absent)} for s, c in correct_by_step.items()]


STEPS = {s: 4 for s in range(0, 1501, 100)}


@pytest.mark.parametrize("final,derange,used", [(12, 6, True), (12, 7, False), (11, 0, False), (30, 4, True)])
def test_memory_use_needs_gain_and_paired_derange_drop(final, derange, used):
    s = B.summarize(_rows(STEPS | {1500: final}), _ev(derange))
    assert s["status"] == "valid" and s["memory_used"] is used and s["band_at_end"] == "partial"
    assert "exploratory" in s["criteria"]["note"]


def _bad_rows(kind):
    rows = _rows(STEPS | {1500: 12})
    if kind == "dup_final":
        rows.append({"step": 1500, "eval": _ev(30, .1)})
    elif kind == "total_1":
        rows[-1]["eval"].update(total=1)
    elif kind == "accuracy_contradicts":
        rows[-1]["eval"].update(accuracy=0.5)
    elif kind == "episodes_1":
        rows[-1]["eval"].update(episodes=1)
    elif kind == "nan_fill_support":
        rows[5]["eval"].update(query_fill_support_cells_mean=float("nan"))
    elif kind == "nan_weight":
        rows[3]["eval"]["query_empty_read_weight"] = float("nan")
    elif kind == "bool_correct":
        rows[-1]["eval"]["correct"] = True
    elif kind == "missing_step":
        del rows[7]
    return rows


@pytest.mark.parametrize("kind,derange", [
    ("dup_final", _ev(0)), ("total_1", _ev(0)), ("nan_weight", _ev(0)), ("bool_correct", _ev(0)),
    ("missing_step", _ev(0)), ("accuracy_contradicts", _ev(0)), ("episodes_1", _ev(0)),
    ("nan_fill_support", _ev(0)), ("ok", {**_ev(0), "total": 255}), ("ok", {**_ev(0), "correct": -1}),
    ("ok", {**_ev(0), "query_empty_read_weight": float("nan")}), ("ok", {"correct": 0, "total": 256}),
    ("ok", None)])
def test_summary_invalid_on_malformed_inputs(kind, derange):
    assert B.summarize(_bad_rows(kind), derange)["status"] == "INVALID"


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
    assert [(s["start"], s["resume_step"]) for s in starts] == [(1, None), (2, 2)]
    archived = out.with_name("B2.archive") / "start-2" / "routing_telemetry.jsonl"
    assert archived.exists() and archived.read_text().strip()               # pre-resume rows kept
    assert _params_sha(out) == _params_sha(ref) and _rows_wo_time(out) == _rows_wo_time(ref)
    assert json.loads((out / "final_bank_derange_eval.json").read_text())["correct"] == \
           json.loads((ref / "final_bank_derange_eval.json").read_text())["correct"]


def test_crash_before_first_checkpoint_is_archived_not_deleted(tmp_path):
    out, pcfg = tmp_path / "B2", _tiny()
    ident = B.run_identity(pcfg, None)
    assert B.prepare_out(out, pcfg, ident) == (None, 1)
    (out / "routing_telemetry.jsonl").write_text('{"step": 0}\n')
    out.with_name("B2.starts.jsonl").write_text('{"start": 1}\n')
    assert B.prepare_out(out, pcfg, ident) == (None, 2)
    kept = out.with_name("B2.archive") / "start-2"
    assert (kept / "routing_telemetry.jsonl").read_text() == '{"step": 0}\n'
    assert sorted(x.name for x in out.iterdir()) == ["identity.json"]


def test_foreign_contents_and_checkpoints_refuse(tmp_path):
    pcfg = _tiny()
    ident = B.run_identity(pcfg, None)
    unidentified = tmp_path / "u" / "B2"
    unidentified.mkdir(parents=True)
    (unidentified / "resume.pt").write_bytes(b"x")
    with pytest.raises(SystemExit):
        B.prepare_out(unidentified, pcfg, ident)
    foreign = tmp_path / "f" / "B2"
    B.prepare_out(foreign, pcfg, {**ident, "campaign": "other"})
    with pytest.raises(SystemExit):
        B.prepare_out(foreign, pcfg, ident)
    stamped = tmp_path / "s" / "B2"
    B.prepare_out(stamped, pcfg, ident)
    B.save_atomic({"pilot_config": asdict(pcfg), "b2_identity": {**ident, "memsub_source_sha256": "0" * 64}},
                  stamped / "resume.pt")
    with pytest.raises(SystemExit):
        B.prepare_out(stamped, pcfg, ident)


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


class _Child:
    def __init__(self, finish_after=None):
        self.pid, self.rc, self.calls, self.killed = 4242, None, 0, False
        self.finish_after = finish_after

    def poll(self):
        return self.rc

    def wait(self, timeout=None):
        if self.killed:
            self.rc = -9
            return self.rc
        self.calls += 1
        if self.finish_after is not None and self.calls >= self.finish_after:
            self.rc = 0
            return 0
        raise subprocess.TimeoutExpired("trainer", timeout)


def _killpg_for(child):
    def killpg(pid, sig):
        assert pid == child.pid
        child.killed = True
    return killpg


def test_child_guard_failure_still_kills_the_trainer():
    child = _Child()

    def bad_killer(target, seconds):
        raise RuntimeError("could not arm the child guard")
    with pytest.raises(RuntimeError):
        R.supervise_child(child, 1e9, 100.0, 0.0, killer=bad_killer, commit=lambda: 0,
                          killpg=_killpg_for(child), clock=lambda: 0.0)
    assert child.killed and child.rc == -9


def test_supervise_child_commits_until_exit_and_times_out():
    child = _Child(finish_after=3)
    rc, errs = R.supervise_child(child, 1e9, 1e6, 0.0, killer=lambda t, s: None, commit=lambda: 1,
                                 killpg=_killpg_for(child), clock=lambda: 0.0)
    assert (rc, errs) == (0, 2) and not child.killed
    clock = {"t": 0.0}
    slow = _Child()

    def tick():
        clock["t"] += 40.0
        return clock["t"]
    rc, _ = R.supervise_child(slow, 1e9, 100.0, 0.0, killer=lambda t, s: None, commit=lambda: 0,
                              killpg=_killpg_for(slow), clock=tick)
    assert rc == "timeout" and slow.killed


def test_campaign_dir_binding(tmp_path):
    want = {"app": R.APP_NAME, "deadline": 123.0}
    run = tmp_path / "run"
    assert R.campaign_dir_problem(run, "start-1", want) is None
    assert R.campaign_dir_problem(run, "start-2", want) is None
    assert R.campaign_dir_problem(run, "start-2", {**want, "deadline": 124.0})
    assert R.campaign_dir_problem(run, "start-1", want)                    # populated before start-1
    assert R.campaign_dir_problem(tmp_path / "empty", "start-3", want)     # no campaign record


def test_summary_valid_on_real_evaluator_rows():
    assert B.eval_ok(B1_EVAL) and B.summarize(_rows(STEPS), _ev(3))["status"] == "valid"


def test_child_exit_race_and_failing_poll_still_reap_and_cancel_guard():
    child, cancelled = _Child(), []

    class _Guard:
        pid = 99

        def poll(self):
            return 0

        def wait(self):
            cancelled.append(True)

    def gone(pid, sig):                                  # the group exited between poll and kill
        child.killed = True
        raise ProcessLookupError(pid)

    def poll_error_wait(timeout=None):
        raise OSError("poll failed")
    child.wait_orig, child.wait = child.wait, poll_error_wait
    with pytest.raises(OSError):
        R.supervise_child(child, 1e9, 100.0, 0.0, killer=lambda t, s: _Guard(), commit=lambda: 0,
                          killpg=gone, clock=lambda: 0.0)
    assert cancelled == [True]                            # guard cancelled despite the kill race
