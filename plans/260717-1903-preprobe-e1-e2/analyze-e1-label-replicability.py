"""PREPROBE E1 analysis: pairwise y agreement between compactor instances
A (shipped single-t1024-T8k, labels from the M3.5 relabel), B (reseed
t=1024) and C (t=512 sweep checkpoint). Cohen's kappa + raw agreement,
overall / restricted to y_A=1 / per-domain, plus a natural-prevalence
reweighted kappa (the stratified sample distorts marginals; kappa is
prevalence-sensitive). Emits the verdict line per PREPROBE.md's decision
rule verbatim.

Inputs:
  plans/260717-1903-preprobe-e1-e2/e1-sample-items.json
  preprobe-data/e1-relabel-B.state.json
  preprobe-data/e1-relabel-C.state.json
Output:
  plans/260717-1903-preprobe-e1-e2/e1-analysis.json
"""

import glob
import json

import numpy as np

PLAN = "plans/260717-1903-preprobe-e1-e2"

with open(f"{PLAN}/e1-sample-items.json") as f:
    sample = {r["item_id"]: r for r in json.load(f)}


def load_relabel(name):
    with open(f"preprobe-data/e1-relabel-{name}.state.json") as f:
        return {r["item_id"]: r for r in json.load(f)["rows"]}


rel = {n: load_relabel(n) for n in ("B", "C")}


def kappa(a, b):
    a, b = np.asarray(a), np.asarray(b)
    po = float((a == b).mean())
    pe = float((a == 1).mean() * (b == 1).mean()
               + (a == 0).mean() * (b == 0).mean())
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po


def weighted_kappa(a, b, w):
    a, b, w = np.asarray(a), np.asarray(b), np.asarray(w, dtype=float)
    w = w / w.sum()
    po = float(((a == b) * w).sum())
    pa1, pb1 = float(((a == 1) * w).sum()), float(((b == 1) * w).sum())
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po


# natural-prevalence weights: full evicted population share of each
# domain x y_A cell divided by its sample share
rows_all = []
for p in sorted(glob.glob("preprobe-data/*-slice-*.json")):
    rows_all.extend(json.load(open(p))["rows"])
ev_all = [r for r in rows_all if r["evicted_still"] == 1]
from collections import Counter
pop = Counter((r["domain"], r["y_still"]) for r in ev_all)
samp_c = Counter((r["domain"], r["y_still"]) for r in sample.values())

out = {}
for name, other in rel.items():
    ids = [i for i in sample if i in other]
    yA = [sample[i]["y_still"] for i in ids]
    yX = [other[i]["y"] for i in ids]
    dom = [sample[i]["domain"] for i in ids]
    k, po = kappa(yA, yX)
    res = {"n": len(ids), "kappa": round(k, 4), "raw_agreement": round(po, 4),
           "yA_rate": round(float(np.mean(yA)), 4),
           "yX_rate": round(float(np.mean(yX)), 4)}
    # loss-side agreement: rows instance A called y=1
    m1 = np.array(yA) == 1
    res["yA1_rows"] = {
        "n": int(m1.sum()),
        "p_yX1_given_yA1": round(float(np.array(yX)[m1].mean()), 4)}
    m1x = np.array(yX) == 1
    res["p_yA1_given_yX1"] = round(float(np.array(yA)[m1x].mean()), 4)
    inter = float((m1 & m1x).sum())
    res["positive_jaccard"] = round(inter / max((m1 | m1x).sum(), 1), 4)
    res["positive_f1"] = round(2 * inter / max(m1.sum() + m1x.sum(), 1), 4)
    per = {}
    for d in sorted(set(dom)):
        md = np.array(dom) == d
        kd, pod = kappa(np.array(yA)[md], np.array(yX)[md])
        per[d] = {"n": int(md.sum()), "kappa": round(kd, 4),
                  "raw": round(pod, 4)}
    res["per_domain"] = per
    w = [pop[(sample[i]["domain"], sample[i]["y_still"])]
         / samp_c[(sample[i]["domain"], sample[i]["y_still"])] for i in ids]
    kw, pow_ = weighted_kappa(yA, yX, w)
    res["natural_prevalence"] = {"kappa": round(kw, 4),
                                 "raw_agreement": round(pow_, 4)}
    out[f"A_vs_{name}"] = res

kab = out["A_vs_B"]["kappa"]
if kab >= 0.6:
    verdict = ("CONTENT-STRUCTURED: all probe arms viable; PROBE.md may "
               "claim checkpoint-independent sufficiency signal")
elif kab >= 0.3:
    verdict = ("PARTIALLY STABLE: read-side arms trained and evaluated "
               "per-checkpoint only; PROBE.md claims scoped accordingly; "
               "report the stable fraction")
else:
    verdict = ("INSTANCE NOISE: read-side arms (attention, hidden-state) "
               "are chasing an unlearnable target — PROBE.md becomes a "
               "self-scoring-compactor brief with the read-side arms "
               "documented as infeasible and E1 as the evidence")
out["verdict"] = {"kappa_A_B": kab, "rule_band": verdict}

with open(f"{PLAN}/e1-analysis.json", "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
