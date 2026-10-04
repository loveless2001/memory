"""M4-SGM P2 decision logic: fail-closed R2/R3 (#gravity 21084)."""

from __future__ import annotations

import copy

from memsub.sgm.p2_grid_readings import MET, NON_EVALUABLE, NOT_MET, readings

Q, EPISODES = 4, 4


def _run(arm, n, seed, acc_none, acc_offset=None, *, steps=1500, hash_tag="h"):
    """Synthetic run: every episode answers the first round(acc*Q) queries."""
    rows = []
    for iv, a in (("none", acc_none), ("read_offset", acc_offset if acc_offset is not None else acc_none),
                  ("bank_derange", 1 / 64)):
        k = round(a * Q)
        for e in range(EPISODES):
            for q in range(Q):
                rows.append({"batch": 0, "episode": e, "episode_hash": f"{hash_tag}{seed}-{e}",
                             "query": q, "correct": q < k, "intervention": iv})
    final = {f"heldout_{iv}": {"accuracy": a} for iv, a in
             (("none", acc_none), ("read_offset", acc_none if acc_offset is None else acc_offset),
              ("bank_derange", 1 / 64))}
    return {"arm": arm, "n_bindings": n, "seed": seed, "steps": steps, "readout": "taskhead",
            "n_queries": Q, "final_episodes": EPISODES, "final": final, "_rows": rows}


def _grid():
    runs = {}
    spec = {  # arm: {N: (acc_none, acc_offset)}
        "oracle": {4: (1.0, 0.0), 16: (1.0, 0.0)},
        "single_cell": {4: (1.0, None), 16: (0.25, None)},
        "random_fixed": {4: (1.0, 0.25), 16: (0.25, 0.25)},
        "learned": {4: (1.0, 0.25), 16: (0.75, 0.25)},
    }
    for arm, by_n in spec.items():
        for n, (a, off) in by_n.items():
            for s in (0, 1):
                runs[("main", arm, n, s)] = _run(arm, n, s, a, off)
    return runs


def test_complete_valid_grid_meets_r3_at_the_capacity_regime():
    out = readings(_grid(), [4, 16])
    assert out["R2"]["status"] == MET and out["R2"]["n_star"] == 16
    assert out["R3"]["status"] == MET


def test_missing_learned_seed_is_non_evaluable_not_met():
    runs = _grid()
    del runs[("main", "learned", 16, 1)]
    assert readings(runs, [4, 16])["R3"]["status"] == NON_EVALUABLE


def test_missing_control_arm_is_non_evaluable_not_met():
    runs = {k: v for k, v in _grid().items() if k[1] != "random_fixed"}
    assert readings(runs, [4, 16])["R3"]["status"] == NON_EVALUABLE


def test_episode_hash_mismatch_is_non_evaluable_without_crashing():
    runs = _grid()
    for r in runs[("main", "learned", 16, 0)]["_rows"]:
        r["episode_hash"] = "other-" + r["episode_hash"]
    out = readings(runs, [4, 16])
    assert out["R3"]["status"] == NON_EVALUABLE
    assert any("different episodes" in line for line in out["R3"]["lines"])


def test_duplicate_or_incomplete_query_rows_and_single_episode_are_non_evaluable():
    dup = _grid()
    rows = dup[("main", "learned", 16, 0)]["_rows"]
    rows.append(dict(rows[0]))
    assert readings(dup, [4, 16])["R3"]["status"] == NON_EVALUABLE
    gap = _grid()
    gap[("main", "learned", 16, 0)]["_rows"] = [
        r for r in gap[("main", "learned", 16, 0)]["_rows"] if not (r["episode"] == 1 and r["query"] == 2)]
    assert readings(gap, [4, 16])["R3"]["status"] == NON_EVALUABLE
    one = _grid()
    for m in one.values():
        m["_rows"] = [r for r in m["_rows"] if r["episode"] == 0]
    assert readings(one, [4, 16])["R3"]["status"] == NON_EVALUABLE


def test_unregistered_steps_or_missing_r2_evidence_is_non_evaluable():
    runs = _grid()
    runs[("main", "learned", 16, 0)]["steps"] = 600
    assert readings(runs, [4, 16])["R3"]["status"] == NON_EVALUABLE
    runs = _grid()
    del runs[("main", "single_cell", 4, 0)]
    out = readings(runs, [4, 16])
    assert out["R2"]["status"] == NON_EVALUABLE and out["R3"]["status"] == NON_EVALUABLE


def test_learned_tied_with_control_is_not_met():
    runs = _grid()
    for s in (0, 1):
        runs[("main", "learned", 16, s)] = _run("learned", 16, s, 0.25, 0.25)
    assert readings(runs, [4, 16])["R3"]["status"] == NOT_MET


def test_dropped_query_id_in_every_run_is_non_evaluable():
    runs = _grid()
    for m in runs.values():
        m["_rows"] = [r for r in m["_rows"] if r["query"] != 3]
    assert readings(runs, [4, 16])["R3"]["status"] == NON_EVALUABLE


def test_unselected_control_without_rows_is_non_evaluable():
    runs = _grid()
    for s in (0, 1):
        runs[("main", "random_fixed", 16, s)]["_rows"] = []
    assert readings(runs, [4, 16])["R3"]["status"] == NON_EVALUABLE


def test_identically_truncated_episodes_are_non_evaluable():
    runs = _grid()
    for m in runs.values():
        m["_rows"] = [r for r in m["_rows"] if r["episode"] < 2]
    assert readings(runs, [4, 16])["R3"]["status"] == NON_EVALUABLE


def test_unregistered_query_count_is_non_evaluable():
    runs = _grid()
    runs[("main", "learned", 16, 1)]["n_queries"] = 3
    assert readings(runs, [4, 16])["R3"]["status"] == NON_EVALUABLE
