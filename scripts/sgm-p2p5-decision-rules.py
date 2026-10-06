"""P2.5 registered decision rules (prereg v0.2 `3bf8737`, sha 0ce61a09…).

Intervals, the ordered classifier and every fail-closed check are the UNCHANGED
P2G rules (`sgm-p2g-decision-rules.py`, which imports the P2D rules); only the
P2.5 interface gate, the all-control conjunction and the reading table are new.
"""

import importlib.util
import math
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "p2g_rules", Path(__file__).with_name("sgm-p2g-decision-rules.py"))
P2G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P2G)

CONTROLS = ("memory_off", "single_cell", "random_fixed")
INTERFACE_MIN = 0.50
LABELS = (P2G.GAIN, P2G.LOSS, P2G.EXCLUDED, P2G.NEITHER)


def interface_ok(oracle_accuracy: dict) -> bool:
    """Oracle accuracy >= 0.50 on both seeds; finite values in [0, 1] or fail closed."""
    if set(oracle_accuracy) != set(P2G.SEEDS):
        raise SystemExit(f"interface needs seeds {P2G.SEEDS}, got {sorted(oracle_accuracy)}")
    vals = list(oracle_accuracy.values())
    if not all(isinstance(v, float) and math.isfinite(v) and 0.0 <= v <= 1.0 for v in vals):
        raise SystemExit(f"malformed oracle accuracies {oracle_accuracy!r}")
    return all(v >= INTERFACE_MIN for v in vals)


def control_labels(per_control: dict) -> dict:
    """label_c = classify(learned − c) for every registered control (no selection)."""
    if set(per_control) != set(CONTROLS):
        raise SystemExit(f"controls must be exactly {CONTROLS}")
    return {c: P2G.classify(per_control[c]) for c in CONTROLS}


def read_address_use(read_offset_per_seed: dict) -> str:
    """Narrow label (codex R3): lo <= 0 on any seed = use not established, not dead routing."""
    ok = all(P2G.check_interval(x)["lo"] > 0 for x in P2G._seeds(read_offset_per_seed).values())
    return "read-address use established" if ok else "read-address use not established"


def screen_reading(n: int, unavailable: str | None, interface: bool | None, labels: dict | None,
                   mem: bool | None) -> str:
    """Prereg v0.2 ordered, total table (rows 1-5)."""
    if unavailable is not None:
        return f"unavailable: {unavailable}"
    if type(interface) is not bool:
        raise SystemExit("interface flag must be a bool when the inputs are available")
    if not interface:
        return f"interface not established at N{n}; screen not read"
    if set(labels or {}) != set(CONTROLS) or not set(labels.values()) <= set(LABELS) or type(mem) is not bool:
        raise SystemExit("malformed control labels / memory flag")
    if all(v == P2G.GAIN for v in labels.values()):
        return (f"SCREEN PASS at N{n}" if mem
                else f"gain over every control without registered memory use at N{n}")
    return f"screen not passed at N{n}; per-control labels: " + ", ".join(f"{c}={labels[c]}" for c in CONTROLS)
