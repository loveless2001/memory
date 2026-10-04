"""Summarise an M4-SGM P2 grid: run table + preregistered readings R1-R4.

    uv run python scripts/sgm-p2-grid-summary.py plans/261005-0210-m4-sgm-p0-p2/runs/<group>

Decision logic lives in memsub/sgm/p2_grid_readings.py (fail-closed: missing
or misaligned evidence is NON-EVALUABLE, never MET). R3 intervals are
episode-paired over hash-matched episodes.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memsub.sgm.p2_grid_readings import (  # noqa: E402
    REGISTERED_QUERIES, REGISTERED_STEPS, NonEvaluable, accuracy, readings)


def load(root: Path) -> dict:
    runs = {}
    for f in sorted(root.glob("*/metrics.json")):
        m = json.loads(f.read_text())
        rows = f.parent / "per_example_results.jsonl"
        m["_rows"] = [json.loads(l) for l in rows.read_text().splitlines()] if rows.exists() else []
        runs[(f.parent.name.split("-")[0], m["arm"], m["n_bindings"], m["seed"])] = m
    return runs


def table(runs) -> list[str]:
    fmt = lambda x: "—" if x is None else f"{x:.3f}"
    def acc_or_none(m, key):
        try:
            return accuracy(m, key)
        except NonEvaluable:
            return None
    rows = ["| tag | arm | N | seed | steps | acc ± hw | derange | read+3 | eff cells | occ | β value | β filler |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (tag, arm, n, seed), m in sorted(runs.items()):
        f = m["final"]["heldout_none"]
        beta = f.get("beta_by_token_class", {})
        rows.append(f"| {tag} | {arm} | {n} | {seed} | {m.get('steps', '?')} | "
                    f"{f['accuracy']:.3f} ± {f['accuracy_ci95_halfwidth_episode']:.3f} | "
                    f"{fmt(acc_or_none(m, 'heldout_bank_derange'))} | "
                    f"{fmt(acc_or_none(m, 'heldout_read_offset'))} | "
                    f"{f['effective_cells_mean']:.1f} | {f['occupancy_mean']:.0f} | "
                    f"{fmt(beta.get('value'))} | {fmt(beta.get('filler'))} |")
    return rows


def registered_ns(root: Path, runs: dict) -> tuple[list[int], list[str]]:
    grid = root / "grid.json"
    if not grid.exists():
        return sorted({k[2] for k in runs if k[0] == "main"}), ["grid.json missing: N set inferred"]
    g = json.loads(grid.read_text())
    notes = [f"registered steps (A1): {g['base']['steps']}"
             + ("" if g["base"]["steps"] == REGISTERED_STEPS else f" ≠ {REGISTERED_STEPS} — MISMATCH"),
             f"registered queries/episode: {g['base']['n_queries']}"
             + ("" if g["base"]["n_queries"] == REGISTERED_QUERIES
                else f" ≠ {REGISTERED_QUERIES} — MISMATCH")]
    ns = sorted({n for b in g["blocks"] if b.get("tag", "main") == "main" for n in b["n_bindings"]})
    return ns, notes


def main():
    root = Path(sys.argv[1])
    runs = load(root)
    ns, notes = registered_ns(root, runs)
    text = [f"# {root.name} — {len(runs)} runs", "", *[f"- {n}" for n in notes], "",
            *table(runs), "", "## Readings", ""]
    for name, r in readings(runs, ns).items():
        text.append(f"### {name}: {r['status']}" + (f" (N* = {r['n_star']})" if "n_star" in r else ""))
        text += [f"- {line}" for line in r["lines"]] + [""]
    print("\n".join(text))


if __name__ == "__main__":
    main()
