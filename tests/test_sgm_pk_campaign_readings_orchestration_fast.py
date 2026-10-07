"""Fast orchestration test of the P2.5 campaign readings (complements the slow tiny e2e): binding, parity and the
model evaluation are replaced by fakes; the REAL registered decision rules consume synthetic, schema-valid rows
(256 episodes x 4 queries, shared episode hashes). Catches seed-key types, oracle-first gating, the all-control
conjunction and the 'interface failed -> other corners unevaluated' rule in seconds."""

import importlib.util
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rdf", ROOT / "scripts/sgm-p2p5-pk-campaign-readings.py")
rd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rd)


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


def run(monkeypatch, tmp_path, oracle_p: float, learned=0.9, control=0.1):
    pilots = rd.expand_cells(__import__("json").loads(rd.GRID.read_text()))
    monkeypatch.setattr(rd, "bind_cells", lambda *a, **k: ({c: tmp_path for c in pilots}, None))
    monkeypatch.setattr(rd, "parity", lambda *a, **k: None)
    calls = []

    def fake_reserved(cid, out, pilot, n, ivs, dest):
        calls.append((pilot["arm"], n))
        arm = pilot["arm"]
        p = {"oracle": oracle_p, "learned": learned}.get(arm, control)
        probs = {iv: (p if iv == "none" else 0.02) for iv in ivs}           # memory use: derange/offset collapse
        rows = rows_for(probs, hash((cid, n)) % 1000)
        acc = sum(rd.P2D.episode_scores(rows, "none").values()) / rd.P2D.N_EPISODES
        return rows, {"rows_sha256": "x", "accuracy_none": acc}
    monkeypatch.setattr(rd, "reserved_rows", fake_reserved)
    return rd.readings(tmp_path, {}, rd.current_identity(), tmp_path / "out"), calls


def test_interface_pass_reads_every_n_with_string_seed_keys(monkeypatch, tmp_path):
    rep, calls = run(monkeypatch, tmp_path, oracle_p=0.9)
    for n in ("32", "16"):
        v = rep["n"][n]
        assert v["interface"] is True and set(v["labels"]) == set(rd.DR.CONTROLS)
        assert set(v["per_control"]["memory_off"]) == {"0", "1"}                  # rules key seeds as str
        assert v["reading"] == f"SCREEN PASS at N{n}"
    assert calls[:2] == [("oracle", 32), ("oracle", 32)]                          # oracle interface FIRST


def test_failed_interface_leaves_other_corners_unevaluated(monkeypatch, tmp_path):
    rep, calls = run(monkeypatch, tmp_path, oracle_p=0.1)
    assert all(v["interface"] is False and "interface not established" in v["reading"] for v in rep["n"].values())
    assert {a for a, _n in calls} == {"oracle"}                                  # reserved learned/controls untouched


def test_no_gain_over_one_control_is_not_a_screen_pass(monkeypatch, tmp_path):
    rep, _ = run(monkeypatch, tmp_path, oracle_p=0.9, learned=0.5, control=0.5)
    assert all(v["reading"].startswith("screen not passed") for v in rep["n"].values())
