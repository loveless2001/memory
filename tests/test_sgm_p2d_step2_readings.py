"""P2D Step 2 decision rules (clarifications 1-3), synthetic rows only."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("p2d_readings", ROOT / "scripts" / "sgm-p2d-step2-readings.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _rows(correct_by_iv: dict, tag="h"):
    """256 episodes x 4 queries; correct_by_iv[iv](episode, query) -> bool."""
    return [{"batch": e // 16, "episode": e % 16, "episode_hash": f"{tag}{e}", "query": q,
             "correct": bool(fn(e, q)), "intervention": iv}
            for iv, fn in correct_by_iv.items() for e in range(256) for q in range(4)]


def test_paired_intervals_and_reproducible_rule():
    m = _mod()
    hi = _rows({"none": lambda e, q: q < 3})                     # 0.75
    lo = _rows({"none": lambda e, q: q < 1 or (e % 2 and q < 2)})  # 0.375
    p = m.paired(hi, lo)
    assert abs(p["diff"] - 0.375) < 1e-9 and p["lo"] > 0 and p["n"] == 256
    assert m.reproducible({"0": p, "1": p})
    tiny = m.paired(_rows({"none": lambda e, q: q < 1 or (e % 25 == 0 and q == 1)}),
                    _rows({"none": lambda e, q: q < 1}))
    assert not m.reproducible({"0": p, "1": tiny})                # < 0.05 in one seed fails


def test_misaligned_or_incomplete_rows_fail_closed():
    m = _mod()
    a = _rows({"none": lambda e, q: True})
    with pytest.raises(SystemExit):
        m.paired(a, _rows({"none": lambda e, q: True}, tag="other"))
    with pytest.raises(SystemExit):
        m.paired(a[:-1], a)


def test_memory_use_rule_uses_the_registered_ceiling():
    m = _mod()
    good = _rows({"none": lambda e, q: True, "bank_derange": lambda e, q: e % 64 == 0 and q == 0,
                  "read_offset": lambda e, q: False})
    assert m.memory_use(good)["pass"]
    bad = _rows({"none": lambda e, q: True, "bank_derange": lambda e, q: q == 0,   # 0.25 > 0.04
                 "read_offset": lambda e, q: False})
    assert not m.memory_use(bad)["pass"]


def test_alignment_conjunction_per_layer_and_zero_target_cannot_pass():
    m = _mod()
    base = {"1": {"median_distance": [5.0, 5.0]}, "3": {"median_distance": [5.0, 5.0]}}
    good = {"1": {"median_distance": [1.0, 9.0], "target_coupling": [0.3, 0.0], "other_coupling": [0.1, 0.0],
                  "read_spread": [2.0, 2.0]},
            "3": {"median_distance": [9.0, 0.5], "target_coupling": [0.0, 0.2], "other_coupling": [0.0, 0.05],
                  "read_spread": [2.0, 1.5]}}
    assert m.alignment_ok(good, base)["pass"]
    zero = {l: {**g, "target_coupling": [0.0, 0.0], "other_coupling": [0.0, 0.0]} for l, g in good.items()}
    assert not m.alignment_ok(zero, base)["pass"]                 # 0 >= 2*0 must not pass
    collapsed = {l: {**g, "read_spread": [0.2, 0.2]} for l, g in good.items()}
    assert not m.alignment_ok(collapsed, base)["pass"]
