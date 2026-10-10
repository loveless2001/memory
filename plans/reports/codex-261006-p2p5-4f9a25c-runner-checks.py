"""Independent CPU probes of 4f9a25c; no Modal API, image build or GPU work.

The short subprocess fixture uses the real Watchdog on an owned child process.
Other worker/reaper dependencies are substitutes; logical time is not a measured
profile. Historical reports are never overwritten by this script.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from memsub.sgm import p2d_launch_guard as guard
import modal.experimental as experimental

RUNNER = ROOT / "modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py"
SHA = "bf8d2c873b5497193d6f43ab352b84141b7d73a96dd1c28d61a1143f0454913e"


class Store(dict):
    def put(self, key, value, skip_if_exists=False):
        if skip_if_exists and key in self:
            return False
        self[key] = value
        return True


class FakeWatchdog:
    def __init__(self, seconds):
        self.seconds, self.cancelled = seconds, False

    def cancel(self):
        self.cancelled = True


def profile_fixture(m, source_hash):
    return {"status": "complete", "memsub_source_sha256": source_hash,
            "environment": {"python": "3.12.13", "torch": "2.7.1+cu126", "cuda": "12.6",
                            "gpu": "NVIDIA L40S", "gpu_total_bytes": 48 * 1024 ** 3,
                            "tf32_matmul": False},
            "contract": "full-gradient token-serial, fp32, TF32 off, batch 16, N32, seed 99",
            "wall_s": 10.0,
            "configs": [{"arm": a, "phase": p, "train_filler_len": 0 if p == 1 else 40,
                         "updates": 10, "warmup_s": [0.01] * 2, "measured_s": [0.01] * 8,
                         "mean_measured_s_per_update": 0.01, "dev_eval_batch_s": 0.01,
                         "peak_train_memory_bytes": 123, "peak_memory_bytes": 124}
                        for a, p in m.EXPECTED_CONFIGS]}


def main():
    assert hashlib.sha256(RUNNER.read_bytes()).hexdigest() == SHA
    spec = importlib.util.spec_from_file_location("paid_profile_4f9a25c_audit", RUNNER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    expected = m.expected_identity()
    good = profile_fixture(m, expected["memsub"])
    assert m.profile_usable(good, 0, expected["memsub"])[0]
    rejected, still_accepted = {}, {}
    mutations = {
        "wrong_source": lambda p: p.__setitem__("memsub_source_sha256", "incorrect-source"),
        "missing_environment": lambda p: p.pop("environment"),
        "missing_warmups": lambda p: p["configs"][0].__setitem__("warmup_s", []),
        "nonfinite_mean": lambda p: p["configs"][0].__setitem__("mean_measured_s_per_update", float("nan")),
        "inconsistent_mean": lambda p: p["configs"][0].__setitem__("mean_measured_s_per_update", 9.0),
        "nonfinite_peak": lambda p: p["configs"][0].__setitem__("peak_memory_bytes", float("nan")),
        "tf32_enabled": lambda p: p["environment"].__setitem__("tf32_matmul", True),
    }
    for label, mutate in mutations.items():
        bad = copy.deepcopy(good)
        mutate(bad)
        ok, why = m.profile_usable(bad, 0, expected["memsub"])
        assert not ok
        rejected[label] = why
    mutations = {
        "wrong_torch": lambda p: p["environment"].__setitem__("torch", "2.7.1+cpu"),
        "wrong_cuda": lambda p: p["environment"].__setitem__("cuda", "incorrect-CUDA-fixture"),
        "wrong_gpu": lambda p: p["environment"].__setitem__("gpu", "NVIDIA A10"),
        "missing_contract": lambda p: p.pop("contract"),
        "wrong_contract": lambda p: p.__setitem__("contract", "bf16 detached-source fixture"),
        "wrong_filler": lambda p: p["configs"][1].__setitem__("train_filler_len", 0),
    }
    for label, mutate in mutations.items():
        bad = copy.deepcopy(good)
        mutate(bad)
        ok, why = m.profile_usable(bad, 0, expected["memsub"])
        assert ok
        still_accepted[label] = why

    # The actual reaper blocks before stop_app if the optional cancel RPC stalls.
    store, stopped = Store(deadline_epoch=0.0, call_id="fixture-call"), []
    entered, release = threading.Event(), threading.Event()
    outcome = []

    def cancel(**kwargs):
        entered.set()
        assert release.wait(3.0), "fixture release missing"

    def reaper_thread():
        try:
            outcome.append(m.reaper.get_raw_f()())
        except BaseException as e:
            outcome.append(repr(e))

    with patch.object(m.modal.Dict, "from_name", lambda *a, **k: store), \
         patch.object(m.modal.FunctionCall, "from_id", lambda *a: SimpleNamespace(cancel=cancel)), \
         patch.object(experimental, "stop_app", lambda name: stopped.append(name)):
        thread = threading.Thread(target=reaper_thread)
        thread.start()
        try:
            assert entered.wait(2.0)
            stop_attempted_while_cancel_blocked = bool(stopped)
            assert not stop_attempted_while_cancel_blocked
        finally:
            release.set()
            thread.join(3.0)
        assert not thread.is_alive() and stopped == [m.APP_NAME]
    reaper_probe = {"stop_attempted_while_cancel_blocked": stop_attempted_while_cancel_blocked,
                    "stop_target_after_release": stopped[0], "outcome": outcome,
                    "real_rpc": False}

    # Cached admission time is not recomputed after the source/claim phase.
    with tempfile.TemporaryDirectory(prefix="codex-p2p5-4f9a25c-") as tmp:
        temp = Path(tmp)
        starts, attempts = Store(deadline_epoch=1000.0), Store()
        clock, child_calls = [100.0], []

        def paths(value):
            s = str(value)
            if s.startswith("/root/repo/"):
                return ROOT / s.removeprefix("/root/repo/")
            if s.startswith("/artifacts/"):
                return temp / s.removeprefix("/artifacts/")
            return Path(value)

        def file_sha(value):
            clock[0] = 219.0        # 119 s of logical identity/claim time, below early watchdog 120 s
            return hashlib.sha256(paths(value).read_bytes()).hexdigest()

        def fake_child(command, **kwargs):
            child_calls.append({"outer_timeout_s": kwargs["timeout"],
                                "remaining_at_child_entry_s": starts["deadline_epoch"] - clock[0],
                                "logical_timeout_epoch": clock[0] + kwargs["timeout"]})
            out = Path(command[-1])
            out.mkdir(parents=True)
            (out / "profile.json").write_text(json.dumps(good))
            return SimpleNamespace(returncode=0, stdout="fixture", stderr="")

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(m, "Path", paths))
            stack.enter_context(patch.object(m, "file_sha", file_sha))
            stack.enter_context(patch.object(m.modal.Dict, "from_name", lambda name, **k: starts if name == m.GUARD_DICT else attempts))
            stack.enter_context(patch.object(m.time, "time", lambda: clock[0]))
            stack.enter_context(patch.object(m.subprocess, "run", fake_child))
            stack.enter_context(patch.object(m, "artifacts", SimpleNamespace(commit=lambda: None)))
            stack.enter_context(patch.object(guard, "Watchdog", FakeWatchdog))
            worker_result = m.run_profile.get_raw_f()(expected)
        assert worker_result["status"] == "profiled"
        assert child_calls[0] == {"outer_timeout_s": 810.0, "remaining_at_child_entry_s": 781.0,
                                  "logical_timeout_epoch": 1029.0}

    # Check the actual Python 3.12 POSIX timeout path with an inherited pipe.
    # Unlike an unconditional communicate() after kill, subprocess.run's POSIX
    # exception cleanup waits only for the direct child and returns promptly.
    child = "from memsub.sgm.p2d_launch_guard import Watchdog; import time; w=Watchdog(0.8); print('owned_watchdog',w.proc.pid,flush=True); time.sleep(8)"
    started = time.monotonic()
    try:
        subprocess.run([sys.executable, "-u", "-c", child], cwd=ROOT, capture_output=True,
                       text=True, timeout=0.15, check=True)
        raise AssertionError("fixture child should time out")
    except subprocess.TimeoutExpired as e:
        elapsed = time.monotonic() - started
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout
        assert stdout and "owned_watchdog" in stdout
        owned_helper = int(stdout.split()[1])
        try:
            assert os.getsid(owned_helper) == owned_helper
            cmdline = Path(f"/proc/{owned_helper}/cmdline").read_bytes()
            assert b"sleep 0.800; kill -KILL" in cmdline
            os.killpg(owned_helper, signal.SIGKILL)
        except ProcessLookupError:
            pass
        assert elapsed < 0.65, elapsed
    pipe_probe = {"requested_outer_timeout_s": 0.15, "watchdog_s": 0.8,
                  "observed_return_s": elapsed, "real_owned_child_only": True,
                  "owned_helper_cleaned_up": True, "blocked_by_helper": False,
                  "explanation": "Python 3.12 POSIX subprocess.run timeout cleanup returns promptly"}

    assert hashlib.sha256(RUNNER.read_bytes()).hexdigest() == SHA
    print(json.dumps({"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                     "reviewed_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                     "runner_sha256": SHA, "identity": expected, "ledger": m.charge_bound(),
                     "corrected_metadata_probes": rejected, "invalid_metadata_still_accepted": still_accepted,
                     "reaper_control_flow_probe": reaper_probe,
                     "cached_remaining_time_probe": child_calls[0], "capture_pipe_probe": pipe_probe,
                     "real_modal_calls": False, "gpu_work": False,
                     "clearance": "HOLD R1/R3; bounded CPU self-stop proof is an appropriate next stage"}, indent=2))


if __name__ == "__main__":
    main()
