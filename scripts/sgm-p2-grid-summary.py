"""Summarise an M4-SGM P2 grid into a table + preregistered readings R1-R4.

    uv run python scripts/sgm-p2-grid-summary.py plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v1

Intervals: per-run episode-level 95% half-widths; arm differences combine
them conservatively (sqrt(h1^2 + h2^2)), although same-seed arms share the
exact evaluation episodes.
"""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

CHANCE = 1 / 64


def load(root: Path) -> dict:
    runs = {}
    for f in sorted(root.glob("*/metrics.json")):
        m = json.loads(f.read_text())
        tag = f.parent.name.split("-")[0]
        runs[(tag, m["arm"], m["n_bindings"], m["seed"])] = m
    return runs


def acc(m, key="heldout_none"):
    r = m["final"].get(key)
    return (r["accuracy"], r["accuracy_ci95_halfwidth_episode"]) if r else (None, None)


def table(runs) -> list[str]:
    rows = ["| tag | arm | N | seed | acc ± hw | shuffle | read+3 | eff cells | occ | β value | β filler |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for (tag, arm, n, seed), m in sorted(runs.items()):
        a, h = acc(m); f = m["final"]["heldout_none"]
        beta = f.get("beta_by_token_class", {})
        sh = acc(m, "heldout_shuffle")[0]; ro = acc(m, "heldout_read_offset")[0]
        fmt = lambda x: "—" if x is None else f"{x:.3f}"
        rows.append(f"| {tag} | {arm} | {n} | {seed} | {a:.3f} ± {h:.3f} | {fmt(sh)} | {fmt(ro)} | "
                    f"{f['effective_cells_mean']:.1f} | {f['occupancy_mean']:.0f} | "
                    f"{fmt(beta.get('value'))} | {fmt(beta.get('filler'))} |")
    return rows


def readings(runs) -> list[str]:
    main = defaultdict(dict)
    for (tag, arm, n, seed), m in runs.items():
        if tag == "main":
            main[(arm, n)][seed] = m
    ns = sorted({n for _, n in main})
    mean = lambda arm, n: (sum(acc(m)[0] for m in main[(arm, n)].values())
                           / len(main[(arm, n)])) if main.get((arm, n)) else None
    out = ["R1 interface (oracle vs chance 0.016): " + ", ".join(
        f"N={n}: {mean('oracle', n):.3f}" for n in ns if mean("oracle", n) is not None)]
    n_star = next((n for n in ns if None not in (mean("single_cell", n), mean("oracle", n))
                   and mean("single_cell", n) <= mean("oracle", n) - 0.20), None)
    out.append(f"R2 capacity regime: N* = {n_star}")
    r3 = []
    for n in ns:
        if n_star is None or n < n_star or not main.get(("learned", n)):
            continue
        ok_all = True
        for seed, lm in main[("learned", n)].items():
            la, lh = acc(lm)
            rivals = [main[(arm, n)][seed] for arm in ("single_cell", "random_fixed")
                      if seed in main.get((arm, n), {})]
            best = max(rivals, key=lambda m: acc(m)[0])
            ba, bh = acc(best)
            off = acc(lm, "heldout_read_offset")[0]
            gain_ok = la - ba >= 0.05 and la - ba > math.hypot(lh, bh)
            off_ok = off is not None and la - off > lh
            r3.append(f"  N={n} s{seed}: learned {la:.3f} vs best control {ba:.3f} "
                      f"(gain {la - ba:+.3f}, ±{math.hypot(lh, bh):.3f}); read+3 {off:.3f} "
                      f"→ {'PASS' if gain_ok and off_ok else 'no'}")
            ok_all &= gain_ok and off_ok
        r3.append(f"  N={n}: {'R3 MET (both seeds)' if ok_all else 'not met'}")
    out.append("R3 learned routing:" + ("\n" + "\n".join(r3) if r3 else " not evaluable (no N*)"))
    r4 = [f"{arm}/N={n}/s{s}: {acc(m, 'heldout_shuffle')[0]:.3f}"
          for (arm, n), seeds in sorted(main.items()) for s, m in seeds.items()
          if arm != "memory_off" and acc(m)[0] > 4 * CHANCE]
    out.append("R4 shuffle on arms above 4x chance: " + (", ".join(r4) or "none above 4x chance"))
    return out


def main():
    root = Path(sys.argv[1])
    runs = load(root)
    text = [f"# {root.name} — {len(runs)} runs", "", *table(runs), "", "## Readings", "",
            *[f"- {r}" for r in readings(runs)]]
    print("\n".join(text))


if __name__ == "__main__":
    main()
