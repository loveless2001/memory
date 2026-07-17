"""PROBE master analysis: arm comparison table (AUC + cluster-bootstrap
CI + per-domain + p3 fragility tau), the stack (val-fit, test-eval), and
GT20/GT21/GT25 verdicts.

Arms in the table: c0 floor, p2 floor, c0.5, c1-demoted, c2-lin, c2-mlp,
stack(c2+p2[+c0/c05]).

Inputs: preprobe-data/probe-readside-scores.npz (from the training
runner), c05 slices, e2 feature matrix, p3 harness.
Output: plans/260717-2319-probe-sufficiency-arms/arm-table.json
"""

import csv
import hashlib
import importlib.util
import json

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

PLAN = "plans/260717-2319-probe-sufficiency-arms"
rng = np.random.default_rng(20260718)

spec = importlib.util.spec_from_file_location(
    "p3", f"{PLAN}/fragility-ordering-harness-p3.py")
p3mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p3mod)

z = np.load("preprobe-data/probe-readside-scores.npz")
ids = [str(i) for i in z["item_ids"]]
split, y = z["split"], z["y"]
doc = np.array([i[4:].rsplit("_", 2)[0] for i in ids])
dom = np.array([d.split("/")[0] for d in doc])
te = split == 2
va = split == 1

c05 = {}
for s in range(4):
    for r in json.load(open(f"preprobe-data/c05-features-slice-0{s}.json"))["rows"]:
        c05[r["item_id"]] = r
c0feat = {}
for r in csv.DictReader(open("plans/260717-1903-preprobe-e1-e2/e2-feature-matrix.csv")):
    c0feat[r["item_id"]] = r

ARMS = {"p2": z["p2"], "c1d": z["c1d"], "c2_lin": z["c2_lin"],
        "c2_mlp": z["c2_mlp"]}

# stack: fit on val (out-of-fold scores), eval on test
C05F = ["n_siblings", "nearest_ngram_sim", "key_distinct", "sibling_density"]


def stack_design(k):
    iid = ids[k]
    x = [z["c2_lin"][k], z["c2_mlp"][k], z["p2"][k], z["c1d"][k]]
    c = c05.get(iid)
    x += [float(c[f]) for f in C05F] if c else [0.0] * len(C05F)
    f = c0feat.get(iid)
    x += [float(f["rarity_min"]), float(f["overlap"])] if f else [0.0, 0.0]
    return x


X = np.array([stack_design(k) for k in range(len(ids))])
mu, sd = X[va].mean(0), X[va].std(0) + 1e-9
clf = LogisticRegression(max_iter=2000).fit((X[va] - mu) / sd, y[va])
stack_scores = clf.decision_function((X - mu) / sd)
ARMS["stack"] = stack_scores


def cluster_ci(yt, s, docs, n_boot=1000):
    groups = {}
    for i, d in enumerate(docs):
        groups.setdefault(d, []).append(i)
    keys = sorted(groups)
    boots = []
    for _ in range(n_boot):
        idx = np.concatenate([groups[keys[j]] for j in
                              rng.choice(len(keys), len(keys), replace=True)])
        if len(set(yt[idx])) > 1:
            boots.append(roc_auc_score(yt[idx], s[idx]))
    return [round(float(v), 4) for v in np.percentile(boots, [2.5, 97.5])]


table = {}
for name, s in ARMS.items():
    a = roc_auc_score(y[te], s[te])
    flip = a < 0.5
    sv = -s if flip else s
    a = max(a, 1 - a)
    per = {d: round(float(roc_auc_score(y[te][dom[te] == d],
                                        sv[te][dom[te] == d])), 4)
           for d in sorted(set(dom[te]))}
    p3 = p3mod.score_ordering({ids[k]: float(sv[k]) for k in range(len(ids))})
    table[name] = {"test_auc": round(float(a), 4),
                   "ci95": cluster_ci(y[te], sv[te], doc[te]),
                   "per_domain": per, "flipped": bool(flip),
                   "p3_tau": p3["kendall_tau"], "p3_tau_ci": p3["tau_ci95"],
                   "p3_tau_excludes_0": p3["tau_ci_excludes_0"]}

best_name = max(table, key=lambda k: table[k]["test_auc"])
best = table[best_name]
table["_floors"] = {"c0": 0.5642, "c0_upper_ci": 0.575,
                    "c05_plus_c0": 0.5677}
table["_verdicts"] = {
    "GT20_some_arm_lower_ci_beats_0.575":
        {n: t["ci95"][0] > 0.575 for n, t in table.items()
         if not n.startswith("_")},
    "GT21_best": {"arm": best_name, "auc": best["test_auc"],
                  "target_0.65_met": best["test_auc"] >= 0.65,
                  "delta_over_c0": round(best["test_auc"] - 0.5642, 4),
                  "delta_over_p2": round(best["test_auc"]
                                         - table["p2"]["test_auc"], 4)},
    "GT25_best_arm_tau_excludes_0": best["p3_tau_excludes_0"],
}
with open(f"{PLAN}/arm-table.json", "w") as f:
    json.dump(table, f, indent=1)
np.savez_compressed(f"{PLAN}/arm-scores-all.npz",
                    item_ids=np.array(ids), split=split, y=y,
                    **{k: np.asarray(v) for k, v in ARMS.items()})
print(json.dumps(table, indent=1))
