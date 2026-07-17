"""PROBE capture manifest builder: union of the E2 matched sample and the
E1 2k sample (all evicted-only), with every field the capture runner
needs (options/gold/pred_raw for the trial + self-check prompts,
chunk_rel_start for the needle mask, y_still as the label). Also emits
the 1k P0 pilot subset (125 per domain x y cell), pilot items flagged
inline so the capture runner can filter on them.

Writes plans/260717-2319-probe-sufficiency-arms/probe-capture-manifest.json
"""

import glob
import json
import random
from collections import defaultdict

random.seed(51235)
PLAN = "plans/260717-2319-probe-sufficiency-arms"

rows = {}
for p in sorted(glob.glob("preprobe-data/*-slice-*.json")):
    for r in json.load(open(p))["rows"]:
        rows[r["item_id"]] = r

e2 = json.load(open("plans/260717-1903-preprobe-e1-e2/e2-sample-items.json"))
e1 = json.load(open("plans/260717-1903-preprobe-e1-e2/e1-sample-items.json"))
ids = {it["item_id"] for it in e2} | {it["item_id"] for it in e1}
e1_ids = {it["item_id"] for it in e1}

manifest = []
for iid in sorted(ids):
    r = rows[iid]
    manifest.append({
        "item_id": iid, "doc_id": r["doc_id"], "domain": r["domain"],
        "question": r["question"], "options": r["options"], "gold": r["gold"],
        "pred_raw": r["pred_raw"], "chunk_rel_start": r["chunk_rel_start"],
        "y": r["y_still"], "in_e1": int(iid in e1_ids),
        "raw_correct": int(r["raw_correct"]), "pilot": 0})

# pilot: 125 per domain x y cell, preferring items ALSO in E1 (they serve
# p3 later) then filling from the rest
by_cell = defaultdict(list)
for m in manifest:
    by_cell[(m["domain"], m["y"])].append(m)
for cell, items in sorted(by_cell.items()):
    pref = [m for m in items if m["in_e1"]]
    rest = [m for m in items if not m["in_e1"]]
    random.shuffle(pref)
    random.shuffle(rest)
    for m in (pref + rest)[:125]:
        m["pilot"] = 1

path = f"{PLAN}/probe-capture-manifest.json"
with open(path, "w") as f:
    json.dump(manifest, f)
n_pilot = sum(m["pilot"] for m in manifest)
print(f"manifest {len(manifest)} items ({sum(m['in_e1'] for m in manifest)} "
      f"from E1) · pilot {n_pilot} -> {path}")
