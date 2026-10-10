"""Isolated CPU-only integration probes of the profile's actual main path.

CUDA calls are replaced with inert stubs; training/evaluation are substituted
with callback fixtures or a GIL-holding C sleep. The real OS Watchdog is used
inside a disposable child. Every remaining watchdog is cleaned up by the
parent, including the early-exception case. No model/GPU/data work occurs.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "plans/reports/codex-261006-p2p5-50a7f2a-deadline-fixtures"
PROFILE = ROOT / "scripts/sgm-p2p5-local-gpu-timing-profile.py"
GUARD = ROOT / "memsub/sgm/p2d_launch_guard.py"
PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"

CHILD = r'''
import ctypes, importlib.util, json, sys, time
from pathlib import Path
root, out, mode = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location("profile_fixture", root / "scripts/sgm-p2p5-local-gpu-timing-profile.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
original_watchdog = m.Watchdog
def tracking_watchdog(seconds):
    w = original_watchdog(seconds)
    print("WATCHDOG_PID=" + str(w.proc.pid), flush=True)
    return w
m.Watchdog = tracking_watchdog
m.WALL_LIMIT_S = 0.5 if mode in ("load_hang", "eval_hang") else 3.0
m.torch.cuda.is_available = lambda: True
m.torch.cuda.get_device_name = lambda _i: "CPU fixture"
m.torch.cuda.get_device_properties = lambda _i: type("Stub", (), {"total_memory": 1})()
m.torch.cuda.reset_peak_memory_stats = lambda: None
m.torch.cuda.max_memory_allocated = lambda: 123
m.torch.cuda.synchronize = lambda: None
m.torch.cuda.empty_cache = lambda: None
def fake_train(pcfg, log, on_update):
    if mode == "load_hang":
        ctypes.PyDLL(None).usleep(8_000_000)
    if mode == "oom":
        raise m.torch.cuda.OutOfMemoryError("synthetic OOM fixture")
    if mode == "train_error":
        raise ValueError("synthetic train error fixture")
    for update in range(pcfg.steps):
        on_update(update, 0.001)
    return {"backend": None, "head": None}
def fake_evaluate(*args, **kwargs):
    if mode == "eval_hang":
        ctypes.PyDLL(None).usleep(8_000_000)
m.train, m.evaluate = fake_train, fake_evaluate
if mode == "environment_error":
    def fail_env(_i):
        raise RuntimeError("synthetic environment error after watchdog arm")
    m.torch.cuda.get_device_name = fail_env
if mode in ("initial_progress_error", "end_progress_error"):
    original_progress = m.progress
    def fail_progress(event):
        wanted = "start" if mode == "initial_progress_error" else "end"
        if event["stage"] == wanted:
            raise OSError("synthetic progress-write failure")
        original_progress(event)
    m.progress = fail_progress
if mode == "output_error":
    original_write_text = Path.write_text
    def fail_output(path, *args, **kwargs):
        if path.name == "profile.json":
            raise OSError("synthetic final report-write failure")
        return original_write_text(path, *args, **kwargs)
    Path.write_text = fail_output
sys.argv = ["profile-fixture", "--out", str(out)]
m.main()
'''


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        stat = Path(f"/proc/{pid}/stat").read_text()
        return stat.split(")", 1)[1].split()[0] != "Z"
    except (ProcessLookupError, FileNotFoundError):
        return False


def main():
    if sha(PROFILE) != "b5b0746a40afbd7c9feb2bcf7aa6967189903673829cf2a8d4a2afc25237a08c":
        raise SystemExit("50a7f2a audit: use the reviewed profile source; refusing a different implementation.")
    files = [PROFILE, GUARD, PLAN / "profile-local/profile.json", PLAN / "profile-local.log"]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in files}
    OUT.mkdir(exist_ok=False)
    cases = {}
    for mode in ("load_hang", "eval_hang", "success", "oom", "train_error", "environment_error",
                 "initial_progress_error", "output_error", "end_progress_error"):
        attempt = OUT / mode
        start = time.monotonic()
        # Use files: the independent helper inherits stdout/stderr. Captured
        # pipes would make communicate() wait for it after the worker exits,
        # hiding the orphan-helper interval this probe needs to observe.
        stdout_path, stderr_path = OUT / f"{mode}.stdout.txt", OUT / f"{mode}.stderr.txt"
        with stdout_path.open("w") as stdout_file, stderr_path.open("w") as stderr_file:
            completed = subprocess.run([sys.executable, "-c", CHILD, str(ROOT), str(attempt), mode],
                                       cwd=ROOT, stdout=stdout_file, stderr=stderr_file, timeout=15,
                                       start_new_session=True)
        elapsed = time.monotonic() - start
        pids = [int(line.split("=", 1)[1]) for line in stdout_path.read_text().splitlines()
                if line.startswith("WATCHDOG_PID=")]
        assert len(pids) == 1
        watchdog_alive = alive(pids[0])
        if watchdog_alive:
            os.killpg(pids[0], signal.SIGKILL)
        rows = ([json.loads(line) for line in (attempt / "progress.jsonl").read_text().splitlines()]
                if (attempt / "progress.jsonl").exists() else [])
        report = json.loads((attempt / "profile.json").read_text()) if (attempt / "profile.json").exists() else None
        assert not rows or rows[0]["stage"] == "start"
        if mode in ("load_hang", "eval_hang"):
            assert completed.returncode == -signal.SIGKILL and elapsed < 10
            assert not any(r["stage"] == "end" for r in rows) and report is None
            assert sum(r["stage"] == "config_start" for r in rows) == 1
            assert sum(r["stage"] == "update_done" for r in rows) == (0 if mode == "load_hang" else 10)
        elif mode == "success":
            assert completed.returncode == 0 and report["status"] == "complete"
            assert len(report["configs"]) == 4 and sum(r["stage"] == "update_done" for r in rows) == 40
            assert sum(r["stage"] == "dev_eval_done" for r in rows) == 4
            assert not watchdog_alive
        elif mode in ("oom", "train_error"):
            assert completed.returncode == 1 and len(report["configs"]) == 0
            assert report["status"].startswith("stopped: OOM" if mode == "oom" else "stopped: error")
            assert sum(r["stage"] == "config_start" for r in rows) == 1
            assert rows[-1]["stage"] == "end" and not watchdog_alive
        else:
            assert completed.returncode == 1 and not watchdog_alive
            if mode == "environment_error":
                assert report is None and len(rows) == 1
            elif mode == "initial_progress_error":
                assert report is None and rows == []
            elif mode == "output_error":
                assert report is None and rows[-1]["stage"] == "dev_eval_done"
            else:
                assert mode == "end_progress_error"
                assert report["status"] == "complete" and rows[-1]["stage"] == "dev_eval_done"
        cases[mode] = {"exit_code": completed.returncode, "process_wall_s_including_imports": elapsed,
                       "progress_records": len(rows), "last_stage": rows[-1]["stage"] if rows else None,
                       "watchdog_alive_after_worker_exit": watchdog_alive,
                       "orphan_watchdog_killed_by_audit_parent": watchdog_alive,
                       "completed_configs": None if report is None else len(report["configs"])}
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in files}
    result = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "reviewed_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "input_sha256": hashes, "cases": cases,
              "hard_deadline_on_in_config_load_and_eval": "PASS: actual SIGKILL, GIL-holding CPU fixture",
              "first_error_stops_and_normal_cancel": "PASS",
              "unhandled_exception_cancels_watchdog": "PASS: no surviving helper on injected setup/output/progress exceptions",
              "original_oom_attempt_unchanged": True, "gpu_work": False,
              "deadline_and_cleanup_hold": "CLOSED at 50a7f2a",
              "paid_profile_clearance": "not cleared"}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
