"""PROBE p3 fragility-ordering harness (built once, applied to every arm).

Ordinal fragility classes over the E1 A/B 2k overlap (nesting per
PREPROBE: B's failures are nearly a subset of A's):
  2 = lost under both A and B   (most fragile)
  1 = lost under A only
  0 = survived under A          (least fragile)
Rows with y_B=1 & y_A=0 fall outside the nesting; excluded and counted.

score_ordering(scores: {item_id: float}) -> Kendall tau-b + bootstrap CI
+ pairwise AUCs. A positive tau means the arm's insufficiency score
tracks the underlying fragility scalar, not one checkpoint's noise
(GT25: tau CI must exclude 0).
"""

import json

import numpy as np
from scipy.stats import kendalltau
from sklearn.metrics import roc_auc_score

PLAN_PRE = "plans/260717-1903-preprobe-e1-e2"


def load_classes():
    sample = {r["item_id"]: r for r in json.load(
        open(f"{PLAN_PRE}/e1-sample-items.json"))}
    relB = {r["item_id"]: r for r in json.load(
        open("preprobe-data/e1-relabel-B.state.json"))["rows"]}
    classes, excluded = {}, 0
    for iid, r in sample.items():
        if iid not in relB:
            continue
        ya, yb = r["y_still"], relB[iid]["y"]
        if ya == 1 and yb == 1:
            classes[iid] = 2
        elif ya == 1:
            classes[iid] = 1
        elif yb == 1:
            excluded += 1          # outside the nesting
        else:
            classes[iid] = 0
    return classes, excluded


def score_ordering(scores: dict, n_boot: int = 1000, seed: int = 0) -> dict:
    classes, excluded = load_classes()
    ids = [i for i in classes if i in scores]
    c = np.array([classes[i] for i in ids])
    s = np.array([scores[i] for i in ids], dtype=float)
    tau = kendalltau(s, c).statistic
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        idx = rng.choice(len(ids), len(ids), replace=True)
        if len(set(c[idx])) < 2:
            continue
        boots.append(kendalltau(s[idx], c[idx]).statistic)
    lo, hi = np.percentile(boots, [2.5, 97.5])

    def pair_auc(a, b):
        m = (c == a) | (c == b)
        if len(set(c[m])) < 2:
            return None
        return round(float(roc_auc_score((c[m] == max(a, b)).astype(int),
                                         s[m])), 4)
    return {"n": len(ids), "n_excluded_non_nested": excluded,
            "class_counts": {int(k): int((c == k).sum()) for k in (0, 1, 2)},
            "kendall_tau": round(float(tau), 4),
            "tau_ci95": [round(float(lo), 4), round(float(hi), 4)],
            "tau_ci_excludes_0": bool(lo > 0 or hi < 0),
            "auc_2v0": pair_auc(2, 0), "auc_2v1": pair_auc(2, 1),
            "auc_1v0": pair_auc(1, 0)}


if __name__ == "__main__":
    classes, excluded = load_classes()
    from collections import Counter
    print("classes:", Counter(classes.values()), "excluded:", excluded)
