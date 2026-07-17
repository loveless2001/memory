"""PROBE GT23 — multi-hop retry with the best arm's per-query
insufficiency score as the ENTRY signal.

Design (documented deviation from wp2's per-block scoring): the arm
scores the QUERY against the compact context; evicted-vs-survived is
system metadata, so the selector expands the evicted candidate (block A)
iff score >= tau_entry, never the survived block. tau fit on doc-bucket
train (<0.7) at target recall 0.85 (same target as wp2 fit_tau_entry);
wp2's block accounting kept: 2 blocks/query, oracle = needed/total.

Targets: expand <= 1.5x oracle at lost <= 0.08; comparators M3 gate
2.33x, s1 2.24x, s2 2.15x.

Output: plans/260717-2319-probe-sufficiency-arms/gt23.json
"""

import hashlib
import json

import numpy as np

PLAN = "plans/260717-2319-probe-sufficiency-arms"

table = json.load(open(f"{PLAN}/arm-table.json"))
best_name = table["_verdicts"]["GT21_best"]["arm"]
z = np.load(f"{PLAN}/arm-scores-all.npz")
ids = [str(i) for i in z["item_ids"]]
score = np.asarray(z[best_name], dtype=float)
if table[best_name].get("flipped"):
    score = -score

mh_rows = json.load(open("preprobe-data/multihop-slice.json"))
mh_idx = {int(i.split(":")[1].split("_")[0]): k
          for k, i in enumerate(ids) if i.startswith("mh:")}
rows = [(mh_idx[n], r) for n, r in enumerate(mh_rows) if n in mh_idx]
s = np.array([score[k] for k, _ in rows])
y = np.array([r["y"] for _, r in rows])
cc = np.array([r["compact_correct"] for _, r in rows])
bucket = np.array([int(hashlib.sha256(r["doc_id"].encode()).hexdigest()[:8],
                       16) / 0xFFFFFFFF for _, r in rows])
tr, te = bucket < 0.7, bucket >= 0.7

# tau: smallest threshold family — pick tau maximizing precision subject
# to train recall >= 0.85 (mirrors fit_tau_entry's recall target)
taus = np.quantile(s[tr], np.linspace(0.01, 0.99, 197))
best_tau, best_prec = None, -1
for t in taus:
    ex = s[tr] >= t
    rec = ex[y[tr] == 1].mean()
    if rec >= 0.85:
        prec = y[tr][ex].mean() if ex.any() else 0
        if prec > best_prec:
            best_prec, best_tau = prec, float(t)

ex = s[te] >= best_tau
n = int(te.sum())
recall = float(ex[y[te] == 1].mean())
exp_blocks = float(ex.sum() / (2 * n))
oracle = float(y[te].sum() / (2 * n))
lost = float(((y[te] == 1) & ~ex & (cc[te] == 0)).sum()
             / max((y[te] == 1).sum(), 1))
out = {
    "best_arm": best_name, "n_test_queries": n, "tau_entry": best_tau,
    "recall": round(recall, 4),
    "expand_rate_blocks": round(exp_blocks, 4),
    "oracle_rate_blocks": round(oracle, 4),
    "expand_over_oracle": round(exp_blocks / max(oracle, 1e-9), 4),
    "lost_fact_rate": round(lost, 4),
    "comparators": {"m3_gate": 2.33, "s1": 2.24, "s2": 2.15},
    "design_note": "entry-gated retry: evicted block expanded iff arm "
                   "score >= tau; survived block never expanded "
                   "(evicted-vs-survived is system metadata)",
}
out["gt23_pass"] = bool(out["expand_over_oracle"] <= 1.5
                        and out["lost_fact_rate"] <= 0.08
                        and recall >= 0.85)
with open(f"{PLAN}/gt23.json", "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
