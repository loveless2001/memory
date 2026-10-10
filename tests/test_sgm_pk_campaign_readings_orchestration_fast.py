"""Fast orchestration test of the P2.5 campaign readings (complements the slow tiny e2e): binding of cells, parity
and the model evaluation are replaced by fakes; the REAL registered decision rules consume synthetic, schema-valid
rows (256 episodes x 4 queries, shared episode hashes). Covers seed-key types, the two-phase order (BOTH oracle
interfaces before any other reserved access; codex 21617 R1), independent per-N gating in both mixed outcomes, the
all-control conjunction, and the start/end dependency binding (R2): a real decision-rule mutation in a copied tree
is refused before any evidence/population access, and a manifest or checkpoint change during the run turns every
reading "unavailable" with the computed values kept."""

import importlib.util
import json
import random
import shutil
from pathlib import Path

import pytest
from conftest import PK_ANALYSIS_MANIFEST, pk_current_memsub_manifest

ROOT = Path(__file__).resolve().parents[1]


def _load_readings(root: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, root / "scripts/sgm-p2p5-pk-campaign-readings.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rd = _load_readings(ROOT, "rdf")


@pytest.fixture(autouse=True)
def _current_memsub_manifest(monkeypatch, tmp_path):
    """Bind the readings to a private manifest copy for this checkout's memsub (see conftest)."""
    monkeypatch.setattr(rd, "MANIFEST", pk_current_memsub_manifest(tmp_path / "current-memsub-manifest.json"))


def rows_for(p_correct: dict, seed: int) -> list:
    """{intervention: probability correct} -> legacy-order rows over 16 batches x 16 episodes x 4 queries."""
    rng, rows = random.Random(seed), []
    for iv, p in p_correct.items():
        for b in range(16):
            for e in range(16):
                for q in range(4):
                    label = (b * 16 + e + q) % 64
                    ok = rng.random() < p
                    rows.append({"batch": b, "episode": e, "episode_hash": f"h{b}-{e}", "query": q, "key": q,
                                 "label": label, "pred": label if ok else (label + 1) % 64, "correct": ok,
                                 "intervention": iv})
    return rows


def run(monkeypatch, tmp_path, oracle_p, learned=0.9, control=0.1, during=None):
    """oracle_p: float or {n: p}. `during(calls)` runs inside every reserved evaluation (mid-run mutations)."""
    pilots = rd.expand_cells(json.loads(rd.GRID.read_text()))
    (tmp_path / "trained_parameters.safetensors").write_bytes(b"ckpt")
    monkeypatch.setattr(rd, "bind_cells", lambda *a, **k: ({c: tmp_path for c in pilots}, None))
    monkeypatch.setattr(rd, "parity", lambda *a, **k: None)
    calls = []

    def fake_reserved(cid, out, pilot, n, ivs, dest):
        calls.append((pilot["arm"], n, pilot["seed"], ivs))
        if during:
            during(calls)
        arm = pilot["arm"]
        p = (oracle_p.get(n) if isinstance(oracle_p, dict) else oracle_p) if arm == "oracle" else \
            {"learned": learned}.get(arm, control)
        rows = rows_for({iv: (p if iv == "none" else 0.02) for iv in ivs}, hash((cid, n)) % 1000)
        acc = sum(rd.P2D.episode_scores(rows, "none").values()) / rd.P2D.N_EPISODES
        return rows, {"rows_sha256": "x", "accuracy_none": acc}
    monkeypatch.setattr(rd, "reserved_rows", fake_reserved)
    return rd.readings(tmp_path, {}, rd.current_identity(), tmp_path / "out"), calls


def test_both_oracle_interfaces_precede_any_other_reserved_access(monkeypatch, tmp_path):
    rep, calls = run(monkeypatch, tmp_path, oracle_p=0.9)
    assert [(a, n, s) for a, n, s, _iv in calls[:4]] == [("oracle", 32, 0), ("oracle", 32, 1),
                                                          ("oracle", 16, 0), ("oracle", 16, 1)]
    assert all(a != "oracle" for a, *_ in calls[4:]) and all(iv == rd.POBS.FINAL_IVS for a, _n, _s, iv in calls[:4])
    for n in ("32", "16"):
        v = rep["n"][n]
        assert v["interface"] is True and set(v["labels"]) == set(rd.DR.CONTROLS)
        assert set(v["per_control"]["memory_off"]) == {"0", "1"}                  # rules key seeds as str
        assert v["reading"] == f"SCREEN PASS at N{n}"
    assert rep["end_binding"] == "verified"


@pytest.mark.parametrize("fail_n, pass_n", [(32, 16), (16, 32)])
def test_per_n_gating_is_independent_in_both_mixed_outcomes(monkeypatch, tmp_path, fail_n, pass_n):
    rep, calls = run(monkeypatch, tmp_path, oracle_p={fail_n: 0.1, pass_n: 0.9})
    assert "interface not established" in rep["n"][str(fail_n)]["reading"]
    assert rep["n"][str(pass_n)]["reading"] == f"SCREEN PASS at N{pass_n}"
    assert {n for a, n, *_ in calls if a != "oracle"} == {pass_n}               # failed N's corners untouched


def test_failed_interfaces_leave_other_corners_unevaluated(monkeypatch, tmp_path):
    rep, calls = run(monkeypatch, tmp_path, oracle_p=0.1)
    assert all(v["interface"] is False and "interface not established" in v["reading"] for v in rep["n"].values())
    assert {a for a, *_ in calls} == {"oracle"}


def test_no_gain_over_one_control_is_not_a_screen_pass(monkeypatch, tmp_path):
    rep, _ = run(monkeypatch, tmp_path, oracle_p=0.9, learned=0.5, control=0.5)
    assert all(v["reading"].startswith("screen not passed") for v in rep["n"].values())


def _copied_tree(tmp_path: Path) -> Path:
    """The files the readings binding consumes, copied with their repo-relative paths."""
    root = tmp_path / "tree"
    manifest = json.loads((ROOT / "configs/m4_sgm_p2p5_campaign_analysis_manifest.json").read_text())
    shutil.copytree(ROOT / "memsub", root / "memsub", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for rel in manifest["analysis"]:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, root / rel)
    pk_current_memsub_manifest(root / PK_ANALYSIS_MANIFEST, root)                 # private copy bound to the copy
    return root


def test_decision_rule_mutation_is_refused_before_any_access(monkeypatch, tmp_path):
    tree = _copied_tree(tmp_path)
    clean = _load_readings(tree, "rd_clean")
    assert clean.binding_problem(clean.current_identity()) is None                # the copy itself binds
    rules = tree / "scripts/sgm-p2p5-decision-rules.py"
    text = rules.read_text()
    assert "INTERFACE_MIN" in text
    rules.write_text(text.replace("0.50", "0.99", 1))                              # codex's private variant
    mutated = _load_readings(tree, "rd_mut")
    assert mutated.DR.INTERFACE_MIN == 0.99 and mutated.current_identity() == clean.current_identity()
    touched = []
    monkeypatch.setattr(mutated, "bind_cells", lambda *a, **k: touched.append("bind") or ({}, "x"))
    monkeypatch.setattr(mutated, "reserved_rows", lambda *a, **k: touched.append("reserved"))
    rep = mutated.readings(tmp_path / "ev", {}, mutated.current_identity(), tmp_path / "out")
    assert "scripts/sgm-p2p5-decision-rules.py" in rep["unavailable"] and touched == []
    assert all(v["reading"].startswith("unavailable") for v in rep["n"].values())


def test_unlisted_script_dependency_is_refused(tmp_path):
    tree = _copied_tree(tmp_path)
    mpath = tree / "configs/m4_sgm_p2p5_campaign_analysis_manifest.json"
    manifest = json.loads(mpath.read_text())
    del manifest["analysis"]["scripts/sgm-p2d-step2-decision-rules.py"]           # reached but not frozen
    mpath.write_text(json.dumps(manifest))
    r = _load_readings(tree, "rd_unlisted")
    assert "script closure differs" in r.binding_problem(r.current_identity())


@pytest.mark.parametrize("what", ["manifest", "checkpoint"])
def test_change_during_the_run_makes_every_reading_unavailable(monkeypatch, tmp_path, what):
    mcopy = tmp_path / "manifest.json"
    shutil.copy2(rd.MANIFEST, mcopy)
    monkeypatch.setattr(rd, "MANIFEST", mcopy)

    def during(calls):
        if len(calls) == 6:                                                         # inside phase 2
            target = mcopy if what == "manifest" else tmp_path / "trained_parameters.safetensors"
            target.write_bytes(target.read_bytes() + b" ")
    rep, _ = run(monkeypatch, tmp_path, oracle_p=0.9, during=during)
    assert what in rep["end_binding"] or ("identity" in rep["end_binding"] and what == "manifest")
    assert all(v["reading"].startswith("unavailable") and v["reading_before_end_binding_failure"] == f"SCREEN PASS at N{n}"
               for n, v in rep["n"].items())
