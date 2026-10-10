"""Read-only CPU audit fixtures for the paid-profile draft, with all Modal
calls, child workloads, volume commits and watchdogs substituted locally.
No deploy/build/spawn RPC, model work, GPU use or population access occurs.
"""

from __future__ import annotations

import contextlib
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
SHA = "770d4d807c99e5ff5bdb63a05066f1ea355fa6f8e6ac3fe6323f54685fd48c40"


class Store:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def put(self, key, value, skip_if_exists=False):
        if skip_if_exists and key in self.data:
            return False
        self.data[key] = value
        return True


class FakeWatchdog:
    records = []

    def __init__(self, seconds):
        self.seconds, self.cancelled = seconds, False
        self.records.append(self)

    def cancel(self):
        self.cancelled = True


def main():
    assert hashlib.sha256(RUNNER.read_bytes()).hexdigest() == SHA
    spec = importlib.util.spec_from_file_location("paid_profile_audit", RUNNER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    raw = m.run_profile.get_raw_f()
    expected = m.expected_identity()
    assert expected == {"runner": SHA,
                        "profile_script": "b5b0746a40afbd7c9feb2bcf7aa6967189903673829cf2a8d4a2afc25237a08c",
                        "memsub": "048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6"}
    ledger = m.charge_bound()
    assert abs(ledger["reserved_total_usd"] - 2.4265408) < 1e-12
    with patch.object(m, "CAP_USD", 2.0):
        assert not m.charge_bound()["admitted"]

    results = {}
    with tempfile.TemporaryDirectory(prefix="codex-p2p5-paid-runner-audit-") as tmp:
        temp = Path(tmp)

        def mapped_path(value):
            text = str(value)
            if text.startswith("/root/repo/"):
                return ROOT / text.removeprefix("/root/repo/")
            if text.startswith("/artifacts/"):
                return temp / text.removeprefix("/artifacts/")
            return Path(value)

        for mode in ("identity_mismatch", "success", "child_error", "outer_timeout", "malformed_success"):
            store, calls, commits = Store(), [], []

            def child(command, **kwargs):
                calls.append({"command": command, "timeout": kwargs["timeout"]})
                out = Path(command[-1])
                out.mkdir(parents=True, exist_ok=False)
                (out / "progress.jsonl").write_text('{"stage":"fixture"}\n')
                if mode == "outer_timeout":
                    raise subprocess.TimeoutExpired(command, 1860, output=b"fixture partial")
                if mode == "child_error":
                    return SimpleNamespace(returncode=1, stdout="", stderr="fixture error")
                profile = {"status": "complete", "configs": [] if mode == "malformed_success" else ["fixture"]}
                (out / "profile.json").write_text(json.dumps(profile))
                return SimpleNamespace(returncode=0, stdout="fixture", stderr="")

            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(m, "Path", mapped_path))
                stack.enter_context(patch.object(m, "GROUP", "fixture-" + mode.replace("_", "-")))
                stack.enter_context(patch.object(guard, "Watchdog", FakeWatchdog))
                stack.enter_context(patch.object(m.modal.Dict, "from_name", lambda *a, **k: store))
                stack.enter_context(patch.object(m, "artifacts", SimpleNamespace(commit=lambda: commits.append(True))))
                stack.enter_context(patch.object(m.subprocess, "run", child))
                result = raw({**expected, "runner": "wrong"} if mode == "identity_mismatch" else expected)
                if mode == "identity_mismatch":
                    assert result["status"] == "identity_mismatch" and not store.data and not calls
                else:
                    assert len(calls) == 1 and calls[0]["timeout"] == 1860 and len(commits) == 1
                    assert result["status"] == "done"
                    replay = raw(expected)
                    assert replay["status"] == "replay_refused" and len(calls) == 1
                    assert FakeWatchdog.records[-1].cancelled
                results[mode] = {"returned_status": result["status"], "child_exit": result.get("child_exit"),
                                 "child_invocations": len(calls), "attempt_claimed": bool(store.data),
                                 "returned_profile": result.get("profile")}

        # Exercise collector with a saved synthetic app ID and stubbed polling
        # and stop/verification helpers. These IDs never reach Modal.
        root = temp / "collector" / m.GROUP
        root.mkdir(parents=True)
        (root / "call.json").write_text(json.dumps({"call_id": "fixture-call-only"}))
        (root / "launch_provenance.json").write_text(json.dumps({"deployed_app_id": "fixture-app-only"}))
        stopped = []
        poll_result = ["pending", None]
        topup = SimpleNamespace(poll=lambda _cid: tuple(poll_result),
                                shutdown=lambda _v1, aid: stopped.append(aid) or {"status": "stopped_verified"})
        with patch.object(m, "LOCAL_OUT", str(temp / "collector")), \
             patch.object(m, "_load", lambda _p, name: topup if name == "topup" else object()), \
             contextlib.redirect_stdout(io.StringIO()):
            pending = m.collect()
            assert pending["poll"] == "pending" and not stopped
            for state, payload in (("result", {"status": "done", "child_exit": 1}), ("failed", "fixture failure"), ("expired", None)):
                poll_result[:] = state, payload
                report = m.collect()
                assert report["final_shutdown"]["status"] == "stopped_verified"
            assert stopped == ["fixture-app-only"] * 3
            (root / "call.json").unlink()
            try:
                m.collect()
            except FileNotFoundError:
                results["missing_call_id"] = {"collector_failed_before_shutdown": True,
                                              "shutdown_calls_after_failure": len(stopped)}
            else:
                raise AssertionError("missing-call behavior changed")
        results["collector_terminal_shutdown"] = {"saved_app_id_used": True, "terminal_states_checked": 3,
                                                   "pending_has_no_elapsed_stop": True}

    assert all(w.cancelled for w in FakeWatchdog.records)
    assert hashlib.sha256(RUNNER.read_bytes()).hexdigest() == SHA
    result = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "reviewed_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "identity": expected, "ledger_arithmetic": ledger, "fixtures": results,
              "real_modal_calls": False, "gpu_work": False,
              "holds": ["No total app/deploy deadline bounding crash/replay cost",
                        "Image-build reservation has no enforced resource/time basis",
                        "Collector fails on lost call-ID persistence instead of recovering bounded shutdown",
                        "Successful child profile schema/matrix is not validated before done"]}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
