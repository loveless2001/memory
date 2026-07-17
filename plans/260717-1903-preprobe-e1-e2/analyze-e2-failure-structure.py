"""PREPROBE E2 analysis: univariate feature AUCs against y, the 5-feature
logistic c0 (doc-level splits, evicted-only sample), cluster-bootstrap CI,
and a 30-item qualitative dump for manual tagging.

Inputs (repo-root relative):
  plans/260717-1903-preprobe-e1-e2/e2-sample-items.json
  preprobe-data/surface-features.json      (from Modal surface_pass)
  preprobe-data/fact-types.state.json      (from Modal fact_type_pass)
  preprobe-data/*-slice-*.json             (for chunk_gloss in the dump)

Outputs (plans/260717-1903-preprobe-e1-e2/):
  e2-feature-matrix.csv  e2-c0-model.json  e2-analysis.json
  e2-qualitative-30.json
"""

import glob
import json
import hashlib
import random

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

PLAN = "plans/260717-1903-preprobe-e1-e2"
random.seed(20260717)
rng = np.random.default_rng(20260717)

with open(f"{PLAN}/e2-sample-items.json") as f:
    sample = json.load(f)
with open("preprobe-data/surface-features.json") as f:
    surf = json.load(f)
with open("preprobe-data/fact-types.state.json") as f:
    ftypes = json.load(f)["types"]

FACT_LEVELS = ["number", "name/entity", "code symbol", "date", "common phrase"]
DOMAINS = ["financial", "legal", "code", "literature"]

rows = []
for it in sample:
    s = surf.get(it["item_id"])
    if s is None or it["item_id"] not in ftypes:
        continue
    dist_to_raw = 3072 - (it["chunk_rel_start"] + 1024)  # tokens from span end
    rows.append({
        "item_id": it["item_id"], "doc_id": it["doc_id"],
        "domain": it["domain"], "y": it["y"],
        "rarity_min": s["rarity_min"], "rarity_mean": s["rarity_mean"],
        "ans_rel_offset": s["ans_rel_offset"],
        "ans_found": s["ans_found_in_span"],
        "span_len": s["span_len"], "dist_to_raw": dist_to_raw,
        "overlap": it["overlap_still"], "fact_type": ftypes[it["item_id"]],
    })
print(f"joined rows: {len(rows)} / {len(sample)}")
y = np.array([r["y"] for r in rows])

# impute missing answer offset with the observed median (answer paraphrased
# or split across the span boundary); keep the found flag as its own signal
offsets = [r["ans_rel_offset"] for r in rows if r["ans_rel_offset"] is not None]
med_off = float(np.median(offsets))
for r in rows:
    if r["ans_rel_offset"] is None:
        r["ans_rel_offset"] = med_off

# ---- univariate AUCs --------------------------------------------------------
uni = {}
for feat in ("rarity_min", "rarity_mean", "ans_rel_offset", "ans_found",
             "span_len", "dist_to_raw", "overlap"):
    v = np.array([r[feat] for r in rows], dtype=float)
    auc = roc_auc_score(y, v)
    uni[feat] = round(max(auc, 1 - auc), 4)  # direction-free
for level in FACT_LEVELS:
    v = np.array([int(r["fact_type"] == level) for r in rows], dtype=float)
    auc = roc_auc_score(y, v)
    uni[f"fact_type={level}"] = round(max(auc, 1 - auc), 4)
for level in DOMAINS:
    v = np.array([int(r["domain"] == level) for r in rows], dtype=float)
    auc = roc_auc_score(y, v)
    uni[f"domain={level}"] = round(max(auc, 1 - auc), 4)

# ---- c0: 5-feature-group logistic, doc-level splits -------------------------
# groups: (1) rarity (min+mean) (2) fact type one-hot (3) answer position
# (4) distance-to-raw-window (5) block overlap.  Domain excluded from c0
# (reported as a +domain variant); doc-level split guards leakage.


def doc_bucket(doc_id: str) -> float:
    h = hashlib.sha256(doc_id.encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def design(rows, with_domain=False):
    cols = []
    for r in rows:
        x = [r["rarity_min"], r["rarity_mean"], r["ans_rel_offset"],
             r["ans_found"], r["dist_to_raw"], r["overlap"]]
        x += [int(r["fact_type"] == l) for l in FACT_LEVELS[:-1]]
        if with_domain:
            x += [int(r["domain"] == d) for d in DOMAINS[:-1]]
        cols.append(x)
    return np.array(cols, dtype=float)


buckets = np.array([doc_bucket(r["doc_id"]) for r in rows])
train_m, test_m = buckets < 0.7, buckets >= 0.7
out = {"n": len(rows), "n_train": int(train_m.sum()),
       "n_test": int(test_m.sum()), "univariate_auc": uni,
       "flagged_ge_060": sorted([k for k, v in uni.items() if v >= 0.60])}

models = {}
for name, with_dom in (("c0", False), ("c0_plus_domain", True)):
    X = design(rows, with_dom)
    sc = StandardScaler().fit(X[train_m])
    clf = LogisticRegression(max_iter=2000, C=1.0)
    clf.fit(sc.transform(X[train_m]), y[train_m])
    p = clf.predict_proba(sc.transform(X[test_m]))[:, 1]
    auc = roc_auc_score(y[test_m], p)
    # cluster bootstrap over test docs
    test_rows = [r for r, m in zip(rows, test_m) if m]
    docs = sorted({r["doc_id"] for r in test_rows})
    by_doc = {}
    for i, r in enumerate(test_rows):
        by_doc.setdefault(r["doc_id"], []).append(i)
    yt = y[test_m]
    boots = []
    for _ in range(1000):
        pick = rng.choice(len(docs), len(docs), replace=True)
        idx = np.concatenate([by_doc[docs[j]] for j in pick])
        if len(set(yt[idx])) < 2:
            continue
        boots.append(roc_auc_score(yt[idx], p[idx]))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    per_dom = {}
    for d in DOMAINS:
        m = np.array([r["domain"] == d for r in test_rows])
        if m.sum() and len(set(yt[m])) > 1:
            per_dom[d] = round(roc_auc_score(yt[m], p[m]), 4)
    out[name] = {"test_auc": round(auc, 4),
                 "ci95": [round(lo, 4), round(hi, 4)],
                 "per_domain_test_auc": per_dom}
    models[name] = {"scaler_mean": sc.mean_.tolist(),
                    "scaler_scale": sc.scale_.tolist(),
                    "coef": clf.coef_[0].tolist(),
                    "intercept": float(clf.intercept_[0])}

feat_names = ["rarity_min", "rarity_mean", "ans_rel_offset", "ans_found",
              "dist_to_raw", "overlap"] + \
             [f"fact={l}" for l in FACT_LEVELS[:-1]]
out["c0_coefficients"] = dict(zip(feat_names, [round(c, 4) for c in
                                               models["c0"]["coef"]]))
out["fact_type_dist"] = {}
for level in FACT_LEVELS:
    m = np.array([r["fact_type"] == level for r in rows])
    out["fact_type_dist"][level] = {
        "n": int(m.sum()), "y1_rate": round(float(y[m].mean()), 4) if m.sum() else None}

with open(f"{PLAN}/e2-analysis.json", "w") as f:
    json.dump(out, f, indent=1)
with open(f"{PLAN}/e2-c0-model.json", "w") as f:
    json.dump({"feature_names": feat_names, **models["c0"],
               "split": "sha256 doc bucket <0.7 train / >=0.7 test",
               "seed": 20260717}, f, indent=1)
with open(f"{PLAN}/e2-feature-matrix.csv", "w") as f:
    hdr = ["item_id", "doc_id", "domain", "y", "rarity_min", "rarity_mean",
           "ans_rel_offset", "ans_found", "span_len", "dist_to_raw",
           "overlap", "fact_type"]
    f.write(",".join(hdr) + "\n")
    for r in rows:
        f.write(",".join(str(r[k]).replace(",", ";") for k in hdr) + "\n")

# ---- qualitative dump: 30 random y=1 items ---------------------------------
gloss = {}
for p in sorted(glob.glob("preprobe-data/*-slice-*.json")):
    for r in json.load(open(p))["rows"]:
        gloss[r["item_id"]] = r
y1_ids = [r["item_id"] for r in rows if r["y"] == 1]
dump = []
for iid in random.sample(y1_ids, 30):
    g = gloss[iid]
    dump.append({
        "item_id": iid, "domain": g["domain"], "question": g["question"],
        "options": g["options"], "gold": g["gold"],
        "pred_raw": g["pred_raw"], "pred_compact_still": g["pred_compact_still"],
        "fact_type": ftypes.get(iid),
        "rarity_min": surf[iid]["rarity_min"],
        "chunk_gloss": g["chunk_gloss"][:600]})
with open(f"{PLAN}/e2-qualitative-30.json", "w") as f:
    json.dump(dump, f, indent=1)
print(json.dumps({k: out[k] for k in ("n", "c0", "c0_plus_domain",
                                      "flagged_ge_060")}, indent=1))
print("univariate:", json.dumps(uni, indent=1))
