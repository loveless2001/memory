"""CPU-only independent checks of the revised paid-profile draft.
All remote calls, child work, watchdogs and volume commits are local stubs.
The logical-time fixture tests admission with one second left, without wait,
GPU/model work, or a deployment. It is not a real timing measurement.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from memsub.sgm import p2d_launch_guard as guard

RUNNER = ROOT / "modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py"
SHA = "4c0b4fd7ad9960f42314a133deb628ed736050d4226d0b81901577b656accfc4"


class Store(dict):
    def put(self, key, value, skip_if_exists=False):
        if skip_if_exists and key in self:
            return False
        self[key] = value
        return True


class FakeWatchdog:
    records = []

    def __init__(self, seconds):
        self.seconds, self.cancelled = seconds, False
        self.records.append(self)

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
    spec = importlib.util.spec_from_file_location("revised_paid_profile_audit", RUNNER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    expected = m.expected_identity()
    good = profile_fixture(m, expected["memsub"])
    assert m.profile_usable(good, 0)[0]
    accepted_bad = {}
    for name in ("wrong_source", "missing_environment", "missing_warmups", "nonfinite_mean", "nonfinite_overall_peak"):
        bad = copy.deepcopy(good)
        if name == "wrong_source":
            bad["memsub_source_sha256"] = "incorrect-source-fixture"
        elif name == "missing_environment":
            bad.pop("environment")
        elif name == "missing_warmups":
            bad["configs"][0]["warmup_s"] = []
        elif name == "nonfinite_mean":
            bad["configs"][0]["mean_measured_s_per_update"] = float("nan")
        else:
            bad["configs"][0]["peak_memory_bytes"] = float("nan")
        accepted_bad[name] = m.profile_usable(bad, 0)[0]
        assert accepted_bad[name], f"expected validation gap changed: {name}"

    with tempfile.TemporaryDirectory(prefix="codex-p2p5-cd1c0c8-") as tmp:
        temp = Path(tmp)
        start_store, attempts = Store(deadline_epoch=100.0), Store()
        calls, commits = [], []
        clock = [99.0]

        def paths(value):
            text = str(value)
            if text.startswith("/root/repo/"):
                return ROOT / text.removeprefix("/root/repo/")
            if text.startswith("/artifacts/"):
                return temp / text.removeprefix("/artifacts/")
            return Path(value)

        def fake_child(command, **kwargs):
            calls.append({"outer_timeout_s": kwargs["timeout"], "deadline_remaining_at_entry_s": 1.0})
            out = Path(command[-1])
            out.mkdir(parents=True)
            (out / "profile.json").write_text(json.dumps(good))
            clock[0] = 109.0                 # logical time only: child finished after the absolute deadline
            return SimpleNamespace(returncode=0, stdout="fixture", stderr="")

        def dict_for(name, **kwargs):
            return start_store if name.endswith("-guard") else attempts

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(m, "Path", paths))
            stack.enter_context(patch.object(m.modal.Dict, "from_name", dict_for))
            stack.enter_context(patch.object(m.time, "time", lambda: clock[0]))
            stack.enter_context(patch.object(m.subprocess, "run", fake_child))
            stack.enter_context(patch.object(m, "artifacts", SimpleNamespace(commit=lambda: commits.append(True))))
            stack.enter_context(patch.object(guard, "Watchdog", FakeWatchdog))
            result = m.run_profile.get_raw_f()(expected)
        assert result["status"] == "profiled" and clock[0] > start_store["deadline_epoch"]
        assert calls[0]["outer_timeout_s"] == 1860
        assert all(w.cancelled for w in FakeWatchdog.records)

        root = temp / "collect" / m.GROUP
        root.mkdir(parents=True)
        (root / "launch_provenance.json").write_text(json.dumps({"deployed_app_id": "fixture-app-only",
                                                                 "deadline_epoch": 100.0}))
        stopped, fetched = [], []
        collectors = {}
        with patch.object(m, "LOCAL_OUT", str(temp / "collect")), \
             patch.object(m, "_load", lambda *args: SimpleNamespace()), \
             contextlib.redirect_stdout(io.StringIO()):
            for kind in ("missing", "corrupt"):
                if kind == "corrupt":
                    (root / "call.json").write_text("{invalid JSON")
                before = len(stopped)
                report = m.collect(poller=lambda _c: (_ for _ in ()).throw(AssertionError("no call to poll")),
                                   stopper=lambda a: stopped.append(a) or {"status": "stopped_verified"},
                                   fetch=lambda r: fetched.append(str(r)) or {"returncode": 0}, now=401.0)
                assert report["poll"] == "untracked" and report["past_deadline"]
                assert len(stopped) == before + 1 and stopped[-1] == "fixture-app-only"
                collectors[kind] = {"shutdown_and_fetch_when_collect_invoked": True}
        assert len(fetched) == 2

    ledger = m.charge_bound()
    assert abs(ledger["reserved_total_usd"] - 2.5222592) < 1e-12
    assert hashlib.sha256(RUNNER.read_bytes()).hexdigest() == SHA
    print(json.dumps({"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                     "reviewed_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                     "runner_sha256": SHA, "identity": expected, "ledger": ledger,
                     "r2_local_recovery": collectors,
                     "r1_late_start_fixture": {"remaining_s": 1, "outer_timeout_s": 1860,
                                                "result_after_logical_deadline": result["status"],
                                                "watchdogs_before_child": [w.seconds for w in FakeWatchdog.records]},
                     "r3_invalid_profiles_still_accepted": accepted_bad,
                     "real_modal_calls": False, "gpu_work": False,
                     "clearance": "HOLD: R1 and remaining R3 checks"}, indent=2))


if __name__ == "__main__":
    main()
