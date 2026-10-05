"""P2D paid-launch guard, tested locally without Modal (codex 21135/21139)."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from memsub.sgm.p2d_launch_guard import (
    HALT_KEY, AllowanceExhausted, AttemptLedger, ReplayRefused, admission_ledger)

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v2"


def _runner():
    spec = importlib.util.spec_from_file_location(
        "p2d_runner", ROOT / "modal-runners" / "modal-m4-sgm-p2d-diagnostics-grid.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class AtomicStore:
    """Local stand-in for modal.Dict: put(skip_if_exists) is atomic."""

    def __init__(self):
        self.data, self.lock = {}, threading.Lock()

    def get(self, key, default=None):
        with self.lock:
            return self.data.get(key, default)

    def put(self, key, value, *, skip_if_exists=False):
        with self.lock:
            if skip_if_exists and key in self.data:
                return False
            self.data[key] = value
            return True


def test_registered_grid_is_admitted_with_seed_specific_timeouts():
    cells, ledger, _ = _runner().plan(ROOT / "configs" / "m4_sgm_p2d_grid.json", V2)
    assert len(cells) == 12 and ledger["admitted"] and ledger["reserved_total_usd"] <= 15.0
    t = ledger["cell_timeouts_s"]
    assert t["long-learned-n32-s0"] != t["long-learned-n32-s1"]
    assert len(t) == len(cells)


def test_over_budget_configuration_is_rejected():
    rounded = {f"c{i}": int(3042 * 60 / 12) for i in range(12)}   # codex 21135 worst case
    with pytest.raises(ValueError, match="exceeds cap"):
        admission_ledger(rounded)


def test_duplicate_run_ids_are_rejected_before_the_ledger(tmp_path):
    grid = json.loads((ROOT / "configs" / "m4_sgm_p2d_grid.json").read_text())
    dup = copy.deepcopy(grid)
    dup["blocks"].append(copy.deepcopy(grid["blocks"][0]))
    path = tmp_path / "dup.json"
    path.write_text(json.dumps(dup))
    with pytest.raises(ValueError, match="duplicate run ids"):
        _runner().plan(path, V2)


def test_concurrent_claims_admit_exactly_one_training_attempt():
    store, results = AtomicStore(), []
    barrier = threading.Barrier(8)

    def claim():
        barrier.wait()
        try:
            results.append(AttemptLedger(store, max_replays=1).begin("cell"))
        except ReplayRefused as e:
            results.append(type(e).__name__)

    threads = [threading.Thread(target=claim) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(1) == 1                                  # one trainer
    assert results.count("ReplayRefused") == 1                    # one reserved replay slot
    assert results.count("AllowanceExhausted") == 6
    assert store.get(HALT_KEY) == "cell"


def test_halt_stops_every_later_attempt_of_every_cell():
    store = AtomicStore()
    store.put(HALT_KEY, "x")
    with pytest.raises(AllowanceExhausted):
        AttemptLedger(store).begin("fresh-cell")


def test_watchdog_kills_a_process_holding_the_gil():
    code = ("import ctypes; from memsub.sgm.p2d_launch_guard import Watchdog; "
            "Watchdog(0.5); ctypes.PyDLL(None).usleep(8_000_000)")
    t0 = time.monotonic()
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, timeout=30)
    assert proc.returncode == -9 and time.monotonic() - t0 < 4


def test_cancelled_watchdog_never_fires():
    code = ("import time; from memsub.sgm.p2d_launch_guard import Watchdog; "
            "w = Watchdog(0.5); w.cancel(); time.sleep(1.5); print('alive')")
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, timeout=30,
                          capture_output=True, text=True)
    assert proc.returncode == 0 and "alive" in proc.stdout


def _done(rid):
    return {"run_id": rid, "status": "done",
            "metrics": {"final": {"heldout_none": {"accuracy": 0.5}}, "per_example": []}}


def test_exhaustion_from_a_later_cell_stops_and_verifies(tmp_path):
    """codex 21142: completion-order results; checked stop + verified shutdown."""
    calls = []
    results = iter([_done("a"), {"run_id": "z", "status": "allowance_exhausted", "reason": "x"},
                    _done("never-written")])
    status = _runner().consume(results, tmp_path, lambda: calls.append("stop"),
                               lambda: {"app_state": "stopped", "app_containers": 0, "verified": True})
    assert status == "halted" and calls == ["stop"]
    assert (tmp_path / "a" / "metrics.json").exists() and not (tmp_path / "never-written").exists()
    assert json.loads((tmp_path / "shutdown.json").read_text())["status"] == "halted"


def test_failed_or_unverified_stop_is_surfaced_as_unresolved(tmp_path):
    def boom():
        raise subprocess.CalledProcessError(1, ["modal", "app", "stop"])
    ex = {"run_id": "z", "status": "allowance_exhausted", "reason": "x"}
    # stop errors (e.g. already stopped) are recorded but verification still decides
    assert _runner().consume(iter([ex]), tmp_path, boom, lambda: {"verified": True}) == "halted"
    assert "CalledProcessError" in json.loads((tmp_path / "shutdown.json").read_text())["stop_error"]
    (tmp_path / "shutdown.json").unlink()
    def verify_boom():
        raise subprocess.TimeoutExpired(["modal"], 120)
    assert _runner().consume(iter([ex]), tmp_path, boom, verify_boom) == "shutdown_unresolved"
    assert "TimeoutExpired" in json.loads((tmp_path / "shutdown.json").read_text())["verify_error"]
    (tmp_path / "shutdown.json").unlink()
    assert _runner().consume(iter([ex]), tmp_path, lambda: None,
                             lambda: {"app_state": "running", "app_containers": 3, "verified": False}
                             ) == "shutdown_unresolved"


def test_launcher_requests_completion_order_outputs():
    src = (ROOT / "modal-runners" / "modal-m4-sgm-p2d-diagnostics-grid.py").read_text()
    assert "order_outputs=False" in src and 'check=True' in src


def test_verify_stopped_parses_cli_json(monkeypatch):
    runner = _runner()
    outs = {"app": [{"App ID": "ap-x", "State": "running", "Tasks": "3"}],
            "container": [{"Container ID": "ta-1", "App ID": "ap-x"}]}

    def fake_run(cmd, **kw):
        key = "app" if cmd[3] == "app" else "container"   # [python, -m, modal, <group>, ...]
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(outs[key]), stderr="")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.verify_stopped("ap-x")["verified"] is False
    outs["app"], outs["container"] = [], []                      # stopped apps drop out of the list
    assert runner.verify_stopped("ap-x")["verified"] is True
    outs["app"] = [{"App ID": "ap-x", "Status": "stopped"}]       # listed without a State column
    assert runner.verify_stopped("ap-x")["verified"] is False
    outs["app"] = [{"App ID": "ap-x", "State": "stopped", "Tasks": "0"}]
    assert runner.verify_stopped("ap-x")["verified"] is True
    outs["container"] = [{"Container ID": "ta-9", "App ID": "ap-other"}]   # other apps' containers ok
    assert runner.verify_stopped("ap-x")["verified"] is True


def test_shutdown_commands_use_launch_interpreter_noninteractive_and_bounded(monkeypatch):
    """codex 21145: exact argv, --yes, check=True, timeout."""
    runner, calls = _runner(), []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.stop_app("ap-x")
    runner.verify_stopped("ap-x")
    assert calls[0][0] == [sys.executable, "-m", "modal", "app", "stop", "--yes", "ap-x"]
    assert calls[1][0] == [sys.executable, "-m", "modal", "app", "list", "--json"]
    assert calls[2][0] == [sys.executable, "-m", "modal", "container", "list", "--json"]
    assert all(kw["check"] is True and kw["timeout"] == 120 for _, kw in calls)
