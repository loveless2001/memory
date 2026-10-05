"""P2C registered decision rules (prereg v0.2 `0c8d358`, sha b1bafbbd…).

The classifier, linear contrasts, half status and every fail-closed check are
the UNCHANGED P2G rules (`sgm-p2g-decision-rules.py`), imported, never copied;
only the P2C five-row reading table is new.
"""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "p2g_rules", Path(__file__).with_name("sgm-p2g-decision-rules.py"))
P2G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P2G)


def q_reading(gain_label: str, mem: bool, half: bool | None) -> str:
    """Prereg P2C ordered table (rows 1-5); total over every flag combination.
    gain is exactly gain_label == reproducible gain (codex 21387)."""
    if gain_label not in (P2G.GAIN, P2G.LOSS, P2G.EXCLUDED, P2G.NEITHER):
        raise SystemExit(f"unknown contrast label {gain_label!r}")
    if type(mem) is not bool or (half is not None and type(half) is not bool):
        raise SystemExit("malformed mem/half flags")
    if gain_label != P2G.GAIN:
        return f"no reproducible gain; curriculum-v2 contrast is {gain_label}"
    if not mem:
        return "reproducible gain without registered memory-use evidence"
    return {True: "SUPPORTS: the label-free filler-length curriculum reproducibly beats v2 at N and "
                  "recovers >= half of the filler-off-training reference",
            False: "reproducible gain with memory use; >= half reference recovery not established",
            None: "reproducible gain with memory use; reference comparison unavailable "
                  "(reference prerequisite not met)"}[half]
