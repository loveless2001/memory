"""P2D Step 2 decision rules (clarifications 1-3; codex 21141), synthetic rows."""

from __future__ import annotations

import importlib.util
import json
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


def _group(tmp_path, name, cells, launch=None):
    """A launched group whose mirror cells carry a manifest naming the group."""
    runs, mirror = tmp_path / name, tmp_path / f"{name}-mirror"
    for rid in cells:
        (mirror / rid).mkdir(parents=True, exist_ok=True)
        (mirror / rid / "run_manifest.json").write_text(json.dumps({"modal_group": name, "git_head": name}))
        for f in ("metrics.json", "per_example_results.jsonl", "trained_parameters.safetensors"):
            (mirror / rid / f).write_text(f"{name}/{rid}/{f}")
    return {"name": name, "runs": runs, "mirror": mirror, "registered": {rid: {"cfg": rid} for rid in cells},
            "launch": launch or {"git_head": name, "grid_sha256": f"grid-{name}"},
            "launch_provenance_sha256": f"lp-{name}", "grid_snapshot_sha256": f"gs-{name}"}


def _validator(problems):
    """problems[(group, rid)] -> validation reason (default None = valid)."""
    return SimpleNamespace(validate=lambda path, rid, *_a: problems.get((path.parent.name, rid)))


UNIVERSE = {rid: {"cfg": rid} for rid in ("a", "b")}


@pytest.fixture
def readings(monkeypatch):
    m = _readings()
    monkeypatch.setattr(m, "bind_treatment", lambda rid, pilot, g, *_a: g["mirror"] / rid)
    return m


def test_partial_mode_skips_missing_cells_but_rejects_invalid_complete_inputs(tmp_path, readings):
    v1 = _group(tmp_path, "v1", ["a", "b"])
    problems = {("v1-mirror", "b"): "missing ['metrics.json']"}
    available, coverage, index = readings.select_treatments(UNIVERSE, [v1], True, _validator(problems), "src")
    assert set(available) == {"a"} and coverage["b"]["status"] == "incomplete" and set(index) == {"a"}
    assert coverage["b"]["incomplete_in"] == [{"group": "v1", "reason": "missing ['metrics.json']"}]
    problems[("v1-mirror", "b")] = "mismatch ['trained_parameters_sha256']"
    with pytest.raises(SystemExit, match="parameter"):
        readings.select_treatments(UNIVERSE, [v1], True, _validator(problems), "src")


def test_full_mode_does_not_accept_missing_cells(tmp_path, readings):
    v1 = _group(tmp_path, "v1", ["a", "b"])
    problems = {("v1-mirror", "b"): "missing ['metrics.json']"}
    with pytest.raises(SystemExit, match="no group holds a valid complete cell"):
        readings.select_treatments(UNIVERSE, [v1], False, _validator(problems), "src")


def test_topup_completes_the_index_with_per_cell_group_provenance(tmp_path, readings):
    v1, topup = _group(tmp_path, "v1", ["a", "b"]), _group(tmp_path, "v1-topup", ["b"])
    problems = {("v1-mirror", "b"): "missing ['metrics.json']"}
    available, coverage, index = readings.select_treatments(UNIVERSE, [v1, topup], False,
                                                           _validator(problems), "src")
    assert available == {"a": v1["mirror"] / "a", "b": topup["mirror"] / "b"}
    assert index["a"]["group"] == "v1" and index["b"]["group"] == "v1-topup"
    assert index["b"]["manifest_modal_group"] == "v1-topup" and index["b"]["launch_git_head"] == "v1-topup"
    assert coverage["b"] == {"status": "valid_complete", "group": "v1-topup",
                             "incomplete_in": [{"group": "v1", "reason": "missing ['metrics.json']"}]}


def test_index_hashes_every_consumed_input_including_checkpoints(tmp_path, readings):
    import hashlib
    v1, topup = _group(tmp_path, "v1", ["a", "b"]), _group(tmp_path, "v1-topup", ["b"])
    cell = topup["mirror"] / "b"
    for f in ("per_example_results_step1500.jsonl", "trained_parameters_step1500.safetensors"):
        (cell / f).write_text(f"checkpoint {f}")
    problems = {("v1-mirror", "b"): "missing ['metrics.json']"}
    _a, _c, index = readings.select_treatments(UNIVERSE, [v1, topup], False, _validator(problems), "src")
    hashes = index["b"]["input_sha256"]
    assert set(hashes) == {"run_manifest.json", "metrics.json", "per_example_results.jsonl",
                           "trained_parameters.safetensors", "per_example_results_step1500.jsonl",
                           "trained_parameters_step1500.safetensors"}
    assert all(h == hashlib.sha256((cell / f).read_bytes()).hexdigest() for f, h in hashes.items())
    assert "per_example_results_step1500.jsonl" not in index["a"]["input_sha256"]


def _committed_group(m, grid_rel):
    """A primary group built from a COMMITTED grid file (no run artifacts needed)."""
    grid_path = ROOT / grid_rel
    validator = m.script("sgm-recover-and-validate-grid-artifacts")
    import hashlib
    return validator, {"name": grid_path.stem, "launch": {"grid_sha256": hashlib.sha256(grid_path.read_bytes()).hexdigest()},
                       "registered": validator.registered_cells(json.loads(grid_path.read_text()), m.RUNNER)}


def test_universe_is_the_registered_12_cell_grid_not_the_first_group():
    m = _readings()
    validator, v1 = _committed_group(m, "configs/m4_sgm_p2d_grid.json")
    assert len(m.registered_universe(v1, validator)) == 12
    validator, topup = _committed_group(m, "configs/m4_sgm_p2d_topup_grid.json")   # the six-cell top-up
    assert len(topup["registered"]) == 6
    with pytest.raises(SystemExit, match="does not launch the full registered grid .6 of 12"):
        m.registered_universe(topup, validator)
    forged = {**topup, "launch": dict(v1["launch"])}          # right hash, subset of cells
    with pytest.raises(SystemExit, match="full registered grid"):
        m.registered_universe(forged, validator)


def test_limits_describe_the_topup_not_no_retraining():
    src = (ROOT / "scripts" / "sgm-p2d-step2-readings.py").read_text()
    assert "without replacement or retraining" not in src
    assert "retrained the missing cells in a separate group" in src


def test_a_cell_valid_in_two_groups_is_ambiguous(tmp_path, readings):
    v1, topup = _group(tmp_path, "v1", ["a", "b"]), _group(tmp_path, "v1-topup", ["b"])
    with pytest.raises(SystemExit, match="valid in several groups"):
        readings.select_treatments(UNIVERSE, [v1, topup], False, _validator({}), "src")


@pytest.mark.parametrize("stray", ["unregistered", "config"])
def test_topup_cells_must_be_registered_with_identical_configs(tmp_path, readings, stray):
    v1 = _group(tmp_path, "v1", ["a", "b"])
    topup = _group(tmp_path, "v1-topup", ["c"] if stray == "unregistered" else ["b"])
    if stray == "config":
        topup["registered"]["b"] = {"cfg": "b", "steps": 4000}
    with pytest.raises(SystemExit, match="not a registered cell"):
        readings.select_treatments(UNIVERSE, [v1, topup], True, _validator({}), "src")


@pytest.mark.parametrize("key", ["name", "mirror"])
def test_duplicate_group_identities_are_rejected(tmp_path, readings, key):
    v1, other = _group(tmp_path, "v1", ["a"]), _group(tmp_path, "v1-topup", ["b"])
    other[key] = v1[key]
    with pytest.raises(SystemExit, match=f"duplicate group {key}"):
        readings.select_treatments(UNIVERSE, [v1, other], True, _validator({}), "src")


def test_bind_rejects_a_manifest_from_another_group(tmp_path):
    m = _readings()
    topup = _group(tmp_path, "v1-topup", ["b"])
    (topup["mirror"] / "b" / "run_manifest.json").write_text(json.dumps({"modal_group": "v1"}))
    with pytest.raises(SystemExit, match="modal_group is not this group"):
        m.bind_treatment("b", {}, topup, _validator({}), "src")


def _launched(tmp_path, name, grid, launch_extra=None):
    runs = tmp_path / name
    runs.mkdir()
    registered = tmp_path / f"{name}-registered.json"
    registered.write_text(json.dumps(grid))
    (runs / "grid.json").write_text(json.dumps(grid))
    import hashlib
    (runs / "launch_provenance.json").write_text(json.dumps({
        "grid_file": str(registered), "grid_sha256": hashlib.sha256(registered.read_bytes()).hexdigest(),
        "git_head": "h", **(launch_extra or {})}))
    return runs


def test_load_group_checks_its_own_grid_and_launch_source(tmp_path):
    m = _readings()
    validator = SimpleNamespace(registered_cells=lambda grid, _runner: {"a": {}})
    grid = {"final_seed_base": m.FINAL_BASE, "blocks": []}
    ok = m.load_group(_launched(tmp_path, "ok", grid, {"memsub_source_sha256": "src"}), tmp_path, validator, "src")
    assert ok["name"] == "ok" and ok["registered"] == {"a": {}}
    with pytest.raises(SystemExit, match="memsub source"):
        m.load_group(_launched(tmp_path, "src", grid, {"memsub_source_sha256": "other"}), tmp_path, validator, "src")
    runs = _launched(tmp_path, "edited", grid)
    (runs / "grid.json").write_text(json.dumps({**grid, "extra": 1}))
    with pytest.raises(SystemExit, match="grid identity"):
        m.load_group(runs, tmp_path, validator, "src")


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
