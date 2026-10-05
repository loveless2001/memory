"""P2D paid-launch guard (M4-SGM.md § P2D Step 2 budget; codex 21133/21135).

Plain Python so it is testable without Modal:
  * `cell_timeout_seconds` — per-cell wall budget from the cell's OWN
    seed-specific v2 wall time (never a rounded worst case);
  * `admission_ledger` — reserves spend for every attempt and refuses a
    configuration whose reservation exceeds the cap;
  * `AttemptLedger` — per-cell attempt counter in a key-value store (Modal
    Dict in production). The first action of every attempt; any replay of a
    started cell exits before training, and replays beyond the reserved
    allowance are refused;
  * `start_watchdog` — hard process exit (os._exit) at the cell deadline, so
    a hung training step cannot outlive its reservation.
CPU limits on Modal are soft (throttling), memory limits are hard; the
ledger therefore carries an explicit CPU-overuse margin instead of claiming
the resource tuple bounds spend.
"""

from __future__ import annotations

import os
import threading

CAP_USD = 15.00
CPU_CORES, MEMORY_GIB = 4, 8
CPU_USD_PER_CORE_S, MEM_USD_PER_GIB_S = 0.0000131, 0.00000222   # Modal standard rates
TIMEOUT_MULTIPLIER = 1.4
STARTUP_LIMIT_S = 300            # Modal startup_timeout per attempt
TEARDOWN_ALLOWANCE_S = 60
MAX_REPLAYS_PER_CELL = 1
REPLAY_EXIT_S = 60               # replay: counter check then immediate exit
IMAGE_BUILD_USD = 0.30
CPU_OVERUSE_FRACTION = 0.10      # soft CPU limit: billed usage may exceed request
FIXED_MARGIN_USD = 1.50
WATCHDOG_EXIT_CODE = 86

# multiplier on the cell's own v2 wall time before the timeout multiplier
ARM_WALL_FACTOR = {"filleroff": 1.0, "long": 3.0, "addrsup": 1.1}


def usd_per_second() -> tuple[float, float]:
    """(total, cpu-only) USD per container-second at requested resources."""
    cpu = CPU_CORES * CPU_USD_PER_CORE_S
    return cpu + MEMORY_GIB * MEM_USD_PER_GIB_S, cpu


def cell_timeout_seconds(tag: str, v2_wall_seconds: float) -> int:
    return int(TIMEOUT_MULTIPLIER * ARM_WALL_FACTOR[tag] * v2_wall_seconds)


def admission_ledger(timeouts: dict[str, int], cap: float = CAP_USD) -> dict:
    """Reserve spend for every attempt; raise if over the cap."""
    rate, cpu_rate = usd_per_second()
    train = sum(timeouts.values()) * rate
    n = len(timeouts)
    startup = n * (STARTUP_LIMIT_S + TEARDOWN_ALLOWANCE_S) * rate
    replays = n * MAX_REPLAYS_PER_CELL * (STARTUP_LIMIT_S + REPLAY_EXIT_S) * rate
    cpu_over = CPU_OVERUSE_FRACTION * sum(timeouts.values()) * cpu_rate
    ledger = {"cells": n, "usd_per_container_hour": rate * 3600,
              "train_timeouts_usd": train, "startup_teardown_usd": startup,
              "replay_allowance_usd": replays, "image_build_usd": IMAGE_BUILD_USD,
              "cpu_overuse_margin_usd": cpu_over, "fixed_margin_usd": FIXED_MARGIN_USD}
    ledger["reserved_total_usd"] = sum(v for k, v in ledger.items() if k.endswith("_usd"))
    ledger["cap_usd"], ledger["admitted"] = cap, ledger["reserved_total_usd"] <= cap
    if not ledger["admitted"]:
        raise ValueError(f"reservation ${ledger['reserved_total_usd']:.2f} exceeds cap ${cap:.2f}")
    return ledger


class ReplayRefused(Exception):
    """A replay of an already-started cell: exit without training."""


class AttemptLedger:
    """Per-cell attempt counter over a dict-like store (Modal Dict)."""

    def __init__(self, store, max_replays: int = MAX_REPLAYS_PER_CELL):
        self.store, self.max_replays = store, max_replays

    def begin(self, cell: str) -> int:
        attempt = int(self.store.get(cell, 0)) + 1
        self.store[cell] = attempt          # recorded before any training work
        if attempt > 1:
            reason = ("replay allowance exhausted" if attempt > 1 + self.max_replays
                      else "replay of a started cell")
            raise ReplayRefused(f"{cell}: attempt {attempt} ({reason}); no training")
        return attempt


def start_watchdog(seconds: float, exit_code: int = WATCHDOG_EXIT_CODE) -> threading.Timer:
    """Hard deadline: os._exit kills the process even inside a hung C op."""
    timer = threading.Timer(seconds, os._exit, args=(exit_code,))
    timer.daemon = True
    timer.start()
    return timer
