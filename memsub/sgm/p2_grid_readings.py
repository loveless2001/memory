"""Preregistered P2 readings R1–R4 over a grid of run metrics (M4-SGM.md).

Fail-closed decision logic (#gravity 21084): a reading is MET only on
complete, registered, aligned evidence. Missing seeds or controls, wrong
registration (steps/readout), misaligned or duplicated per-example rows,
or fewer than 2 paired episodes make the reading NON-EVALUABLE — never MET.

`runs` maps (tag, arm, n_bindings, seed) -> metrics dict carrying `_rows`
(per_example_results). Only tag "main" enters R1–R4.
"""

from __future__ import annotations

import math
from collections import defaultdict

CHANCE = 1 / 64
REGISTERED_SEEDS = (0, 1)
REGISTERED_STEPS = 1500          # amendment A1
REGISTERED_READOUT = "taskhead"
CONTROLS = ("single_cell", "random_fixed")
MET, NOT_MET, NON_EVALUABLE = "MET", "NOT MET", "NON-EVALUABLE"


class NonEvaluable(Exception):
    """Evidence is missing, unregistered or misaligned."""


def accuracy(m: dict, key: str = "heldout_none") -> float:
    r = m["final"].get(key)
    if r is None:
        raise NonEvaluable(f"{m.get('arm')}: no {key} result")
    return r["accuracy"]


def episode_table(m: dict, intervention: str) -> dict[tuple, dict[int, bool]]:
    """(batch, episode, episode_hash) -> {query: correct}; rejects duplicates."""
    eps: dict[tuple, dict[int, bool]] = defaultdict(dict)
    for r in m.get("_rows", []):
        if r["intervention"] != intervention:
            continue
        key = (r["batch"], r["episode"], r["episode_hash"])
        if r["query"] in eps[key]:
            raise NonEvaluable(f"{m.get('arm')}/{intervention}: duplicate query row {key, r['query']}")
        eps[key][r["query"]] = bool(r["correct"])
    if not eps:
        raise NonEvaluable(f"{m.get('arm')}/{intervention}: no per-example rows")
    return eps


def paired_difference(m_a: dict, m_b: dict, iv_a: str = "none",
                      iv_b: str = "none") -> tuple[float, float]:
    """Mean per-episode accuracy difference a - b and its 95% half-width,
    over identical episodes (hash-matched) with identical complete query sets."""
    a, b = episode_table(m_a, iv_a), episode_table(m_b, iv_b)
    if set(a) != set(b):
        raise NonEvaluable("paired runs cover different episodes or episode hashes")
    queries = set(next(iter(a.values())))
    if queries != set(range(len(queries))):
        raise NonEvaluable("query ids are not a complete 0..Q-1 set")
    for key in a:
        if set(a[key]) != queries or set(b[key]) != queries:
            raise NonEvaluable(f"episode {key} has incomplete or mismatched query ids")
    if len(a) < 2:
        raise NonEvaluable("fewer than 2 paired episodes")
    d = [(sum(a[k].values()) - sum(b[k].values())) / len(queries) for k in a]
    mean = sum(d) / len(d)
    sd = math.sqrt(sum((x - mean) ** 2 for x in d) / (len(d) - 1))
    return mean, 1.96 * sd / math.sqrt(len(d))


def _main_index(runs: dict) -> dict[tuple[str, int], dict[int, dict]]:
    main: dict = defaultdict(dict)
    for (tag, arm, n, seed), m in runs.items():
        if tag == "main":
            main[(arm, n)][seed] = m
    return main


def _complete(main, arm: str, n: int) -> dict[int, dict]:
    seeds = main.get((arm, n), {})
    missing = [s for s in REGISTERED_SEEDS if s not in seeds]
    if missing:
        raise NonEvaluable(f"{arm}/N={n}: missing registered seeds {missing}")
    for s in REGISTERED_SEEDS:
        m = seeds[s]
        if m.get("steps") != REGISTERED_STEPS or m.get("readout") != REGISTERED_READOUT:
            raise NonEvaluable(f"{arm}/N={n}/s{s}: not the registered steps/readout")
    return seeds


def readings(runs: dict, ns: list[int]) -> dict:
    """ns = registered N values. Returns {R1..R4: {"status", "lines", ...}}."""
    main = _main_index(runs)
    out: dict = {}
    r1 = []
    for n in ns:
        try:
            r1.append(f"N={n}: oracle " + ", ".join(
                f"s{s} {accuracy(m):.3f}" for s, m in sorted(_complete(main, "oracle", n).items())))
        except NonEvaluable as e:
            r1.append(f"N={n}: {NON_EVALUABLE} ({e})")
    out["R1"] = {"status": "DESCRIPTIVE", "lines": r1}

    n_star, r2 = None, []
    try:
        for n in ns:
            single = _complete(main, "single_cell", n); oracle = _complete(main, "oracle", n)
            gap = (sum(accuracy(m) for m in oracle.values())
                   - sum(accuracy(m) for m in single.values())) / len(REGISTERED_SEEDS)
            r2.append(f"N={n}: oracle - single_cell = {gap:+.3f}")
            if gap >= 0.20:
                n_star = n
                break
        out["R2"] = {"status": MET if n_star is not None else NOT_MET, "n_star": n_star, "lines": r2}
    except NonEvaluable as e:
        out["R2"] = {"status": NON_EVALUABLE, "n_star": None, "lines": r2 + [str(e)]}

    out["R3"] = _r3(main, ns, out["R2"])
    r4 = []
    for (arm, n), seeds in sorted(main.items()):
        for s, m in sorted(seeds.items()):
            if arm == "memory_off":
                continue
            try:
                if accuracy(m) > 4 * CHANCE:
                    r4.append(f"{arm}/N={n}/s{s}: none {accuracy(m):.3f} → bank_derange "
                              f"{accuracy(m, 'heldout_bank_derange'):.3f}")
            except NonEvaluable as e:
                r4.append(f"{arm}/N={n}/s{s}: {NON_EVALUABLE} ({e})")
    out["R4"] = {"status": "DESCRIPTIVE", "lines": r4 or ["no memory arm above 4x chance"]}
    return out


def _r3(main, ns, r2: dict) -> dict:
    if r2["status"] != MET:
        return {"status": NON_EVALUABLE, "lines": [f"R2 is {r2['status']}: no N*"]}
    lines, statuses = [], []
    for n in [n for n in ns if n >= r2["n_star"]]:
        try:
            learned = _complete(main, "learned", n)
            controls = {arm: _complete(main, arm, n) for arm in CONTROLS}
            seed_ok = []
            for s in REGISTERED_SEEDS:
                best = max((controls[a][s] for a in CONTROLS), key=accuracy)
                gain, gh = paired_difference(learned[s], best)
                drop, dh = paired_difference(learned[s], learned[s], "none", "read_offset")
                ok = gain >= 0.05 and gain - gh > 0 and drop - dh > 0
                seed_ok.append(ok)
                lines.append(f"N={n} s{s}: learned {accuracy(learned[s]):.3f} vs {best['arm']} "
                             f"{accuracy(best):.3f}; paired gain {gain:+.3f} ± {gh:.3f}; "
                             f"read+3 paired drop {drop:+.3f} ± {dh:.3f} → {'pass' if ok else 'fail'}")
            statuses.append(MET if all(seed_ok) else NOT_MET)
            lines.append(f"N={n}: {statuses[-1]}")
        except NonEvaluable as e:
            statuses.append(NON_EVALUABLE)
            lines.append(f"N={n}: {NON_EVALUABLE} ({e})")
    status = (MET if MET in statuses else NON_EVALUABLE if NON_EVALUABLE in statuses
              else NOT_MET)
    return {"status": status, "lines": lines}
