"""P2D paid-launch guard, tested locally without Modal (codex 21135)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest

from memsub.sgm.p2d_launch_guard import (
    AttemptLedger, ReplayRefused, WATCHDOG_EXIT_CODE, admission_ledger, cell_timeout_seconds)

ROOT = Path(__file__).resolve().parents[1]


def _runner():
    spec = importlib.util.spec_from_file_location(
        "p2d_runner", ROOT / "modal-runners" / "modal-m4-sgm-p2d-diagnostics-grid.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_registered_grid_is_admitted_with_seed_specific_timeouts():
    cells, ledger, _ = _runner().plan(ROOT / "configs" / "m4_sgm_p2d_grid.json",
                                      ROOT / "plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v2")
    assert len(cells) == 12 and ledger["admitted"] and ledger["reserved_total_usd"] <= 15.0
    t = ledger["cell_timeouts_s"]
    assert t["long-learned-n32-s0"] != t["long-learned-n32-s1"]          # per seed, not rounded worst


def test_over_budget_configuration_is_rejected():
    # codex 21135: rounded worst-seed durations for both seeds (3042 timeout-min) must fail
    rounded = {f"c{i}": int(3042 * 60 / 12) for i in range(12)}
    with pytest.raises(ValueError, match="exceeds cap"):
        admission_ledger(rounded)


def test_attempt_ledger_refuses_replays_before_training():
    store: dict = {}
    led = AttemptLedger(store, max_replays=1)
    assert led.begin("cell") == 1
    with pytest.raises(ReplayRefused, match="replay of a started cell"):
        led.begin("cell")
    with pytest.raises(ReplayRefused, match="allowance exhausted"):
        led.begin("cell")
    assert store["cell"] == 3 and led.begin("other") == 1


def test_watchdog_kills_a_hung_process():
    code = ("import time; from memsub.sgm.p2d_launch_guard import start_watchdog; "
            "start_watchdog(0.5); time.sleep(30)")
    t0 = time.monotonic()
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, timeout=20)
    assert proc.returncode == WATCHDOG_EXIT_CODE and time.monotonic() - t0 < 10
