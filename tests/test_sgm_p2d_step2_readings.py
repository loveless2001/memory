"""P2D Step 2 decision rules (clarifications 1-3; codex 21141), synthetic rows."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

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


def _readings():
    spec = importlib.util.spec_from_file_location("p2d_readings", ROOT / "scripts" / "sgm-p2d-step2-readings.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_partial_mode_skips_missing_cells_but_rejects_invalid_complete_inputs(tmp_path, monkeypatch):
    m = _readings()
    args = SimpleNamespace(mirror=tmp_path, source_sha="source", partial=True)
    problems = {"done": None, "lost": "missing ['metrics.json']"}
    validator = SimpleNamespace(validate=lambda _path, rid, *_args: problems[rid])
    monkeypatch.setattr(m, "bind_treatment", lambda rid, *_args: tmp_path / rid)
    available, coverage = m.select_treatments({"done": {}, "lost": {}}, args, {}, validator)
    assert set(available) == {"done"} and coverage["lost"]["status"] == "incomplete"
    problems["lost"] = "mismatch ['trained_parameters_sha256']"
    with pytest.raises(SystemExit, match="parameter"):
        m.select_treatments({"done": {}, "lost": {}}, args, {}, validator)


def test_full_mode_does_not_accept_missing_cells(tmp_path):
    m = _readings()
    args = SimpleNamespace(mirror=tmp_path, source_sha="source", partial=False)
    validator = SimpleNamespace(validate=lambda *_args: "missing ['metrics.json']")
    with pytest.raises(SystemExit, match="artifact validation failed"):
        m.select_treatments({"lost": {}}, args, {}, validator)


@pytest.mark.parametrize("seeds", [{}, {"0": {}}, {"1": {}}])
def test_missing_pairs_never_receive_gain_or_alignment_readings(seeds):
    m = _readings()
    r = m.summarize_cell("addrsup", seeds)
    assert r["reproducible_gain_vs_v2"] is None
    assert r["alignment_both_seeds"] is None and r["memory_use_both_seeds"] is None
    assert r["evaluation_status"] == ("descriptive_single_seed" if seeds else "unevaluable")


def test_complete_pair_keeps_registered_both_seed_threshold():
    m = _readings()
    def seed(diff):
        return {"vs_v2": {"diff": diff, "lo": 0.01}, "alignment": {"pass": True},
                "memory_use": {"pass": True}}
    fail = m.summarize_cell("addrsup", {"0": seed(0.1), "1": seed(0.04)})
    assert not fail["reproducible_gain_vs_v2"]
    assert fail["reading"] == "alignment improved; no registered reproducible gain"
    success = m.summarize_cell("addrsup", {"0": seed(0.1), "1": seed(0.1)})
    assert success["reproducible_gain_vs_v2"] and success["reading"].startswith("SUPPORTS")
