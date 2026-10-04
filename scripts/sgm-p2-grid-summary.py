"""Summarise an M4-SGM P2 grid into a table + preregistered readings R1-R4.

    uv run python scripts/sgm-p2-grid-summary.py plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v1

Intervals: per-run episode-level 95% half-widths. R3 arm differences are
EPISODE-PAIRED: same-seed runs evaluate identical episodes (checked by
episode hash), so the learned-minus-control interval is computed from
per-episode accuracy differences.
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
        rows = f.parent / "per_example_results.jsonl"
        m["_rows"] = [json.loads(l) for l in rows.read_text().splitlines()] if rows.exists() else []
        tag = f.parent.name.split("-")[0]
        runs[(tag, m["arm"], m["n_bindings"], m["seed"])] = m
    return runs


def episode_acc(m, intervention="none") -> dict:
    eps = defaultdict(list)
    for r in m["_rows"]:
        if r["intervention"] == intervention:
            eps[(r["batch"], r["episode"], r["episode_hash"])].append(r["correct"])
    return {k: sum(v) / len(v) for k, v in eps.items()}


def paired(m_a, m_b, iv_a="none", iv_b="none"):
    """Mean per-episode accuracy difference a - b and its 95% half-width."""
    a, b = episode_acc(m_a, iv_a), episode_acc(m_b, iv_b)
    if not a or set(a) != set(b):
        return None, None
    d = [a[k] - b[k] for k in a]
    mean = sum(d) / len(d)
    sd = math.sqrt(sum((x - mean) ** 2 for x in d) / (len(d) - 1))
    return mean, 1.96 * sd / math.sqrt(len(d))


def acc(m, key="heldout_none"):
    r = m["final"].get(key)
    return (r["accuracy"], r["accuracy_ci95_halfwidth_episode"]) if r else (None, None)


def table(runs) -> list[str]:
    rows = ["| tag | arm | N | seed | acc ± hw | derange | read+3 | eff cells | occ | β value | β filler |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for (tag, arm, n, seed), m in sorted(runs.items()):
        a, h = acc(m); f = m["final"]["heldout_none"]
        beta = f.get("beta_by_token_class", {})
        sh = acc(m, "heldout_bank_derange")[0]; ro = acc(m, "heldout_read_offset")[0]
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
            la = acc(lm)[0]
            rivals = [main[(arm, n)][seed] for arm in ("single_cell", "random_fixed")
                      if seed in main.get((arm, n), {})]
            best = max(rivals, key=lambda m: acc(m)[0])
            gain, gh = paired(lm, best)
            drop, dh = paired(lm, lm, "none", "read_offset")
            gain_ok = gain is not None and gain >= 0.05 and gain - gh > 0
            off_ok = drop is not None and drop - dh > 0
            r3.append(f"  N={n} s{seed}: learned {la:.3f} vs {best['arm']} {acc(best)[0]:.3f} "
                      f"(paired gain {gain:+.3f} ± {gh:.3f}); read+3 paired drop "
                      f"{drop:+.3f} ± {dh:.3f} → {'PASS' if gain_ok and off_ok else 'no'}")
            ok_all &= gain_ok and off_ok
        r3.append(f"  N={n}: {'R3 MET (both seeds)' if ok_all else 'not met'}")
    out.append("R3 learned routing:" + ("\n" + "\n".join(r3) if r3 else " not evaluable (no N*)"))
    r4 = [f"{arm}/N={n}/s{s}: {acc(m, 'heldout_bank_derange')[0]:.3f}"
          for (arm, n), seeds in sorted(main.items()) for s, m in seeds.items()
          if arm != "memory_off" and acc(m)[0] > 4 * CHANCE]
    out.append("R4 bank-derange on arms above 4x chance: " + (", ".join(r4) or "none above 4x chance"))
    return out


def main():
    root = Path(sys.argv[1])
    runs = load(root)
    text = [f"# {root.name} — {len(runs)} runs", "", *table(runs), "", "## Readings", "",
            *[f"- {r}" for r in readings(runs)]]
    print("\n".join(text))


if __name__ == "__main__":
    main()
