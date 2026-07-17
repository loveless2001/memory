"""PROBE arm c0.5 analysis: interference-geometry features (corpus-only)
univariate AUCs + logistic stacked on c0's feature groups. Same rows and
split as the E2 c0 fit (E2 sample, sha256 doc bucket <0.7 / >=0.7).
BAR: beat c0's upper CI 0.575; stretch 0.60.

Output: plans/260717-2319-probe-sufficiency-arms/c05-analysis.json
"""

import csv
import hashlib
import json

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

PLAN = "plans/260717-2319-probe-sufficiency-arms"
rng = np.random.default_rng(20260718)

C05F = ["n_siblings", "n_exact_answer", "sibling_density",
        "nearest_ngram_sim", "top5_ngram_sim_mean", "key_distinct",
        "mean_sibling_cos", "ans_found_in_region"]

c05 = {}
for s in range(4):
    for r in json.load(open(f"preprobe-data/c05-features-slice-0{s}.json"))["rows"]:
        c05[r["item_id"]] = r

# c0 feature matrix (E2 sample rows only — the comparable population)
rows = []
for r in csv.DictReader(open("plans/260717-1903-preprobe-e1-e2/e2-feature-matrix.csv")):
    if r["item_id"] in c05:
        rows.append(r)
print(f"joined {len(rows)} rows")

FACT = ["number", "name/entity", "code symbol", "date"]
y = np.array([int(r["y"]) for r in rows])


def c0_design(r):
    return [float(r["rarity_min"]), float(r["rarity_mean"]),
            float(r["ans_rel_offset"]), float(r["ans_found"]),
            float(r["dist_to_raw"]), float(r["overlap"])] + \
        [int(r["fact_type"] == f) for f in FACT]


def c05_design(r):
    c = c05[r["item_id"]]
    return [float(c[k]) for k in C05F]


uni = {}
for ki, k in enumerate(C05F):
    v = np.array([c05_design(r)[ki] for r in rows])
    a = roc_auc_score(y, v)
    uni[k] = round(max(a, 1 - a), 4)

bucket = np.array([int(hashlib.sha256(r["doc_id"].encode()).hexdigest()[:8],
                       16) / 0xFFFFFFFF for r in rows])
tr, te = bucket < 0.7, bucket >= 0.7
out = {"n": len(rows), "univariate_auc": uni}

for name, design in (("c05_only", c05_design),
                     ("c05_plus_c0", lambda r: c0_design(r) + c05_design(r)),
                     ("c0_check", c0_design)):
    X = np.array([design(r) for r in rows], dtype=float)
    sc = StandardScaler().fit(X[tr])
    clf = LogisticRegression(max_iter=2000).fit(sc.transform(X[tr]), y[tr])
    p = clf.predict_proba(sc.transform(X[te]))[:, 1]
    a = roc_auc_score(y[te], p)
    # cluster bootstrap over docs
    docs = {}
    te_rows = [r for r, m in zip(rows, te) if m]
    for i, r in enumerate(te_rows):
        docs.setdefault(r["doc_id"], []).append(i)
    keys = sorted(docs)
    yt = y[te]
    boots = []
    for _ in range(1000):
        idx = np.concatenate([docs[keys[j]] for j in
                              rng.choice(len(keys), len(keys), replace=True)])
        if len(set(yt[idx])) > 1:
            boots.append(roc_auc_score(yt[idx], p[idx]))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    out[name] = {"test_auc": round(float(a), 4),
                 "ci95": [round(float(lo), 4), round(float(hi), 4)]}

out["bar"] = {"beats_c0_upper_ci_0.575":
              out["c05_plus_c0"]["ci95"][0] > 0.575,
              "stretch_0.60": out["c05_plus_c0"]["test_auc"] >= 0.60}
with open(f"{PLAN}/c05-analysis.json", "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
