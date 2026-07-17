"""PREPROBE E1 sample builder: 2,000 evicted (needle) rows stratified
domain x y_still x needle-rarity tercile (rarity_min from E2's surface
pass; tercile boundaries computed over all evicted rows). Seeded; strata
short of quota are topped up from the same domain x y cell.

Writes plans/260717-1903-preprobe-e1-e2/e1-sample-items.json with every
field the relabel runner needs plus y_still (instance A's label).
"""

import glob
import json
import random
from collections import defaultdict

import numpy as np

PLAN = "plans/260717-1903-preprobe-e1-e2"
random.seed(51234)
TARGET = 2000

rows = []
for p in sorted(glob.glob("preprobe-data/*-slice-*.json")):
    with open(p) as f:
        rows.extend(json.load(f)["rows"])
with open("preprobe-data/surface-features.json") as f:
    surf = json.load(f)

ev = [r for r in rows if r["evicted_still"] == 1 and r["item_id"] in surf]
rar = np.array([surf[r["item_id"]]["rarity_min"] for r in ev])
t1, t2 = np.quantile(rar, [1 / 3, 2 / 3])
print(f"evicted rows {len(ev)}, rarity_min tercile bounds: {t1:.3f} {t2:.3f}")


def tercile(v):
    return 0 if v <= t1 else (1 if v <= t2 else 2)


strata = defaultdict(list)
for r, v in zip(ev, rar):
    strata[(r["domain"], r["y_still"], tercile(v))].append(r)

cells = sorted(strata)
assert len(cells) == 24
base, extra = divmod(TARGET, len(cells))
quota = {c: base + (1 if i < extra else 0) for i, c in enumerate(cells)}

sample, short = [], []
for c in cells:
    pool = strata[c]
    take = min(quota[c], len(pool))
    sample.extend(random.sample(pool, take))
    if take < quota[c]:
        short.append((c, quota[c] - take))
for c, missing in short:  # top up from same domain x y, any tercile
    dom, yv, _ = c
    pool = [r for cc in cells if cc[0] == dom and cc[1] == yv
            for r in strata[cc] if r not in sample]
    sample.extend(random.sample(pool, missing))
assert len(sample) == TARGET

out = []
for r in sample:
    out.append({
        "item_id": r["item_id"], "doc_id": r["doc_id"], "domain": r["domain"],
        "question": r["question"], "options": r["options"], "gold": r["gold"],
        "pred_raw": r["pred_raw"], "chunk_rel_start": r["chunk_rel_start"],
        "y_still": r["y_still"], "overlap_still": r["overlap_still"],
        "raw_correct": int(r["raw_correct"]),
        "rarity_min": surf[r["item_id"]]["rarity_min"],
        "rarity_tercile": tercile(surf[r["item_id"]]["rarity_min"])})
path = f"{PLAN}/e1-sample-items.json"
with open(path, "w") as f:
    json.dump(out, f)
from collections import Counter
print(Counter((r["domain"], r["y_still"]) for r in out))
print(f"tercile bounds ({t1:.4f}, {t2:.4f}) -> {path}")
