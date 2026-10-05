"""P2D Step 2 decision rules (clarifications 1-3; codex 21141), synthetic rows."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _rules():
    spec = importlib.util.spec_from_file_location("p2d_rules", ROOT / "scripts" / "sgm-p2d-step2-decision-rules.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _rows(correct_by_iv: dict, tag="h"):
    """256 episodes x 4 queries with schema-valid rows."""
    rows = []
    for iv, fn in correct_by_iv.items():
        for e in range(256):
            for q in range(4):
                ok = bool(fn(e, q))
                rows.append({"batch": e // 16, "episode": e % 16, "episode_hash": f"{tag}{e}", "query": q,
                             "key": 10000 + q, "label": 5, "pred": 5 if ok else 6, "correct": ok,
                             "intervention": iv})
    return rows


GEO = {"1": {"median_distance": [1.0, 9.0], "target_coupling": [0.3, 0.0], "other_coupling": [0.1, 0.0],
             "read_spread": [2.0, 2.0]},
       "3": {"median_distance": [9.0, 0.5], "target_coupling": [0.0, 0.2], "other_coupling": [0.0, 0.05],
             "read_spread": [2.0, 1.5]}}
BASE = {l: {"median_distance": [5.0, 5.0], "target_coupling": [0.1, 0.1], "other_coupling": [0.1, 0.1],
            "read_spread": [1.0, 1.0]} for l in ("1", "3")}


def test_paired_intervals_and_reproducible_rule():
    m = _rules()
    hi = _rows({"none": lambda e, q: q < 3})
    lo = _rows({"none": lambda e, q: q < 1 or (e % 2 and q < 2)})
    p = m.paired(hi, lo)
    assert abs(p["diff"] - 0.375) < 1e-9 and p["lo"] > 0 and p["n"] == 256
    assert m.reproducible({"0": p, "1": p})
    tiny = m.paired(_rows({"none": lambda e, q: q < 1 or (e % 25 == 0 and q == 1)}),
                    _rows({"none": lambda e, q: q < 1}))
    assert not m.reproducible({"0": p, "1": tiny})


def test_invalid_rows_fail_closed():
    m = _rules()
    good = _rows({"none": lambda e, q: True})
    bad_type = [dict(r, correct=2) if i == 0 else r for i, r in enumerate(good)]
    with pytest.raises(SystemExit):
        m.paired(bad_type, good)                            # non-boolean correct
    bad_flag = [dict(r, pred=7) if i == 0 else r for i, r in enumerate(good)]
    with pytest.raises(SystemExit):
        m.paired(bad_flag, good)                            # correct but pred != label
    with pytest.raises(SystemExit):
        m.paired(good, _rows({"none": lambda e, q: True}, tag="other"))   # misaligned hashes
    with pytest.raises(SystemExit):
        m.paired(good[:-1], good)                           # incomplete


def test_empty_or_partial_coverage_cannot_pass():
    m = _rules()
    with pytest.raises(SystemExit):
        m.reproducible({})
    with pytest.raises(SystemExit):
        m.reproducible({"0": {"diff": 1.0, "lo": 1.0}})
    with pytest.raises(SystemExit):
        m.alignment_ok({}, {})
    one_head = {l: {k: v[:1] for k, v in g.items()} for l, g in GEO.items()}
    with pytest.raises(SystemExit):
        m.alignment_ok(one_head, BASE)


def test_memory_use_rule_uses_the_registered_ceiling():
    m = _rules()
    good = _rows({"none": lambda e, q: True, "bank_derange": lambda e, q: e % 64 == 0 and q == 0,
                  "read_offset": lambda e, q: False})
    assert m.memory_use(good)["pass"]
    bad = _rows({"none": lambda e, q: True, "bank_derange": lambda e, q: q == 0,
                 "read_offset": lambda e, q: False})
    assert not m.memory_use(bad)["pass"]


def test_alignment_conjunction_zero_target_and_collapse():
    m = _rules()
    assert m.alignment_ok(GEO, BASE)["pass"]
    zero = {l: {**g, "target_coupling": [0.0, 0.0], "other_coupling": [0.0, 0.0]} for l, g in GEO.items()}
    assert not m.alignment_ok(zero, BASE)["pass"]
    collapsed = {l: {**g, "read_spread": [0.2, 0.2]} for l, g in GEO.items()}
    assert not m.alignment_ok(collapsed, BASE)["pass"]


def test_registered_reading_wording():
    m = _rules()
    assert m.addrsup_reading(False, True, True) == "alignment improved; no registered reproducible gain"
    assert m.addrsup_reading(True, True, True).startswith("SUPPORTS")
    assert "unresolved" in m.addrsup_reading(True, False, True)
    r = m.long_reading(True, False)
    assert r["4500_vs_own_1500"] == "reproducible gain" and "not established" in r["overall"]
    assert m.long_reading(True, True)["overall"] == "budget effect for this recipe"
