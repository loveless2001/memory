"""P2D paid-launch guard (M4-SGM.md § P2D Step 2 budget; codex 21133/21135).

Plain Python so it is testable without Modal:
  * `cell_timeout_seconds` — per-cell wall budget from the cell's OWN
    seed-specific v2 wall time (never a rounded worst case);
  * `admission_ledger` — reserves spend for every attempt and refuses a
    configuration whose reservation exceeds the cap;
  * `AttemptLedger` — ATOMIC per-cell claims (`put(..., skip_if_exists=True)`,
    as Modal Dict provides). Only the first attempt of a cell may train; a
    replay claims one of the reserved replay slots and exits; once slots are
    exhausted a global HALT key stops every later attempt of every cell;
  * `Watchdog` — an independent OS process that SIGKILLs this process at the
    deadline, so it fires even while a C call holds the GIL. Cancel it in a
    `finally`; containers are single-use as well.
CPU limits on Modal are soft (throttling), memory limits are hard; the
ledger therefore carries an explicit CPU-overuse margin instead of claiming
the resource tuple bounds spend.
"""

from __future__ import annotations

import os

CAP_USD = 15.00
CPU_CORES, MEMORY_GIB = 4, 8
CPU_USD_PER_CORE_S, MEM_USD_PER_GIB_S = 0.0000131, 0.00000222   # Modal standard rates
TIMEOUT_MULTIPLIER = 1.4
STARTUP_LIMIT_S = 300            # Modal startup_timeout per attempt
TEARDOWN_ALLOWANCE_S = 60
MAX_REPLAYS_PER_CELL = 1
EARLY_DEADLINE_S = 120           # bounds imports + claim RPCs (+ replay exit)
IMAGE_BUILD_USD = 0.30
CPU_OVERUSE_FRACTION = 0.10      # soft CPU limit: billed usage may exceed request
FIXED_MARGIN_USD = 1.50

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
    replays = n * MAX_REPLAYS_PER_CELL * (STARTUP_LIMIT_S + EARLY_DEADLINE_S) * rate
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
    """A replay of an already-claimed cell: exit without training."""


class AllowanceExhausted(ReplayRefused):
    """Replay slots exhausted, or a HALT is in force: stop all work."""


HALT_KEY = "__halt__"


class AttemptLedger:
    """Atomic claims over a store exposing put(key, value, skip_if_exists=True)
    -> bool (True iff this call created the key) and get(key, default)."""

    def __init__(self, store, max_replays: int = MAX_REPLAYS_PER_CELL):
        self.store, self.max_replays = store, max_replays

    def begin(self, cell: str) -> int:
        if self.store.get(HALT_KEY, None):
            raise AllowanceExhausted(f"{cell}: HALT in force; no work")
        if self.store.put(f"{cell}#attempt1", True, skip_if_exists=True):
            return 1                                    # the only attempt that may train
        for r in range(1, self.max_replays + 1):
            if self.store.put(f"{cell}#replay{r}", True, skip_if_exists=True):
                raise ReplayRefused(f"{cell}: replay {r} of a claimed cell; no training")
        self.store.put(HALT_KEY, cell, skip_if_exists=True)
        raise AllowanceExhausted(f"{cell}: replay allowance exhausted; HALT set")


class Watchdog:
    """Independent sleeper process that SIGKILLs `pid` after `seconds`."""

    def __init__(self, seconds: float, pid: int | None = None):
        import subprocess
        target = os.getpid() if pid is None else pid
        self.proc = subprocess.Popen(["/bin/sh", "-c", f"sleep {seconds:.3f}; kill -KILL {target}"],
                                     start_new_session=True)

    def cancel(self) -> None:
        import signal
        if self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGKILL)   # sh AND its sleep child
        self.proc.wait()
