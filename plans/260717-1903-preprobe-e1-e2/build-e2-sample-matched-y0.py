"""PREPROBE E2 sample builder: all y_still=1 evicted (needle) rows plus a
matched y_still=0 evicted sample — same doc where possible (nearest span),
else same domain (nearest chunk position). Seeded, without replacement.

Writes plans/260717-1903-preprobe-e1-e2/e2-sample-items.json
(fields for the fact-type pass + local analysis join key = item_id).
"""

import glob
import json
import random
from collections import defaultdict

random.seed(20260717)

rows = []
for p in sorted(glob.glob("preprobe-data/*-slice-*.json")):
    with open(p) as f:
        rows.extend(json.load(f)["rows"])

ev = [r for r in rows if r["evicted_still"] == 1]
y1 = [r for r in ev if r["y_still"] == 1]
y0 = [r for r in ev if r["y_still"] == 0]

y0_by_doc = defaultdict(list)
y0_by_domain = defaultdict(list)
for r in y0:
    y0_by_doc[r["doc_id"]].append(r)
    y0_by_domain[r["domain"]].append(r)

used = set()
pairs = []
n_same_doc = 0
for r in y1:
    cand = [c for c in y0_by_doc.get(r["doc_id"], ())
            if c["item_id"] not in used]
    if cand:
        m = min(cand, key=lambda c: abs(c["chunk_rel_start"]
                                        - r["chunk_rel_start"]))
        n_same_doc += 1
    else:
        pool = [c for c in y0_by_domain[r["domain"]]
                if c["item_id"] not in used]
        # nearest chunk position among a seeded random subsample (speed)
        sub = random.sample(pool, min(400, len(pool)))
        m = min(sub, key=lambda c: abs(c["chunk_rel_start"]
                                       - r["chunk_rel_start"]))
    used.add(m["item_id"])
    pairs.append((r, m))

sample = []
for r, m in pairs:
    for row in (r, m):
        sample.append({
            "item_id": row["item_id"], "doc_id": row["doc_id"],
            "domain": row["domain"], "y": row["y_still"],
            "question": row["question"],
            "answer": row["options"][ord(row["gold"].strip()[0]) - 65].strip(),
            "chunk_rel_start": row["chunk_rel_start"],
            "overlap_still": row["overlap_still"],
            "raw_correct": int(row["raw_correct"]),
        })

out = "plans/260717-1903-preprobe-e1-e2/e2-sample-items.json"
with open(out, "w") as f:
    json.dump(sample, f)
print(f"y1={len(y1)} matched y0={len(pairs)} same-doc matches={n_same_doc} "
      f"total={len(sample)} -> {out}")
