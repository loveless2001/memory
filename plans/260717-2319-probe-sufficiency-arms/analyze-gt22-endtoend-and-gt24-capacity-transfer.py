"""PROBE GT22 + GT24.

GT22 — end-to-end weighted operating point: plug the best arm's score
into the gate role (expand iff score >= tau). tau chosen on the val split
(weighted) to hit lost-fact|prior-correct <= 0.146 with minimum expand;
reported on test with natural-prevalence weights (captured sample is
all-y1 + matched-y0; weights = population (domain x y) count / sample
count over evicted rows). expand_rate_all reconstructed assuming zero
non-evicted expansion (evicted fraction 0.832 of all rows) — stated
assumption, matches the overlap-driven gate's behavior.
Comparators: refreshed gate 0.146 @ 0.147, never-expand 0.189 @ 0,
oracle 0 @ 0.170.

GT24 — capacity transfer: best arm (trained on y_A, t=1024) evaluated
against y_C (t=512 relabels) on the captured E1 rows; report the drop.

Output: plans/260717-2319-probe-sufficiency-arms/gt22-gt24.json
"""

import glob
import json
from collections import Counter

import numpy as np
from sklearn.metrics import roc_auc_score

PLAN = "plans/260717-2319-probe-sufficiency-arms"

table = json.load(open(f"{PLAN}/arm-table.json"))
best_name = table["_verdicts"]["GT21_best"]["arm"]
z = np.load(f"{PLAN}/arm-scores-all.npz")
ids = [str(i) for i in z["item_ids"]]
score = np.asarray(z[best_name], dtype=float)
if table[best_name].get("flipped"):
    score = -score
y, split = z["y"], z["split"]
dom = np.array([i[4:].split("/")[0] for i in ids])

manifest = {m["item_id"]: m for m in json.load(
    open(f"{PLAN}/probe-capture-manifest.json"))}
raw_ok = np.array([manifest.get(i, {}).get("raw_correct", 1)
                   for i in ids], dtype=bool)   # mh rows unused in GT22

# natural-prevalence weights over the evicted population
pop_rows = []
for p in sorted(glob.glob("preprobe-data/*-slice-*.json")):
    if "capture" in p or "c05" in p or "relabel" in p:
        continue
    pop_rows.extend(json.load(open(p))["rows"])
ev = [r for r in pop_rows if r["evicted_still"] == 1]
pop = Counter((r["domain"], r["y_still"]) for r in ev)
n_all_rows = len(pop_rows)
frac_evicted = len(ev) / n_all_rows

out = {"best_arm": best_name}


def weighted_op(mask, taus=None):
    """weighted lost-fact|prior-correct and expand over evicted rows."""
    idx = np.flatnonzero(mask)
    samp = Counter((dom[k], y[k]) for k in idx)
    w = np.array([pop[(dom[k], y[k])] / samp[(dom[k], y[k])] for k in idx])
    s, yy, rc = score[idx], y[idx], raw_ok[idx]
    if taus is None:
        taus = np.quantile(s, np.linspace(0.02, 0.98, 97))
    curve = []
    for t in taus:
        ex = s >= t
        lost = float((w * ((yy == 1) & ~ex & rc)).sum()
                     / max((w * rc).sum(), 1e-9))
        expand_ev = float((w * ex).sum() / w.sum())
        curve.append({"tau": float(t), "lost_prior_correct": round(lost, 4),
                      "expand_evicted": round(expand_ev, 4),
                      "expand_all_est": round(expand_ev * frac_evicted, 4)})
    return curve


val_curve = weighted_op(split == 1)
ok = [c for c in val_curve if c["lost_prior_correct"] <= 0.146]
chosen = min(ok, key=lambda c: c["expand_evicted"]) if ok else None
test_curve = weighted_op(split == 2,
                         taus=[chosen["tau"]] if chosen else None)
full_test_curve = weighted_op(split == 2)
never = weighted_op(split == 2, taus=[np.inf])[0]
out["gt22"] = {
    "assumption": "non-evicted rows never expanded; expand_all = "
                  f"expand_evicted * {frac_evicted:.3f}",
    "val_chosen_tau": chosen,
    "test_at_tau": test_curve[0] if chosen else None,
    "never_expand_test": never,
    "comparators": {"refreshed_gate": {"lost": 0.146, "expand_all": 0.147},
                    "oracle": {"lost": 0.0, "expand_all": 0.170},
                    "never_expand_protocol": 0.189},
    "test_frontier": full_test_curve[::8],
}
if chosen:
    t = test_curve[0]
    out["gt22"]["win_condition_strictly_inside_gate"] = bool(
        t["lost_prior_correct"] <= 0.146 and t["expand_all_est"] < 0.147)

# ---- GT24: capacity transfer ------------------------------------------
relC = {r["item_id"]: r["y"] for r in json.load(
    open("preprobe-data/e1-relabel-C.state.json"))["rows"]}
e1_idx = [k for k, i in enumerate(ids) if i in relC]
yC = np.array([relC[ids[k]] for k in e1_idx])
yA = y[e1_idx]
sc = score[e1_idx]
out["gt24"] = {
    "n_e1_rows_captured": len(e1_idx),
    "auc_vs_yA_same_rows": round(float(roc_auc_score(yA, sc)), 4),
    "auc_vs_yC_t512": round(float(roc_auc_score(yC, sc)), 4),
    "note": "E1 rows span all splits; all-rows numbers include in-sample "
            "scores — the held-out subset is the honest pair",
}
out["gt24"]["drop"] = round(out["gt24"]["auc_vs_yA_same_rows"]
                            - out["gt24"]["auc_vs_yC_t512"], 4)
ho = [j for j, k in enumerate(e1_idx) if split[k] == 2]
if len(ho) > 50:
    out["gt24"]["heldout"] = {
        "n": len(ho),
        "auc_vs_yA": round(float(roc_auc_score(yA[ho], sc[ho])), 4),
        "auc_vs_yC": round(float(roc_auc_score(yC[ho], sc[ho])), 4)}
    out["gt24"]["heldout"]["drop"] = round(
        out["gt24"]["heldout"]["auc_vs_yA"]
        - out["gt24"]["heldout"]["auc_vs_yC"], 4)

with open(f"{PLAN}/gt22-gt24.json", "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "gt22"} |
                 {"gt22": {kk: vv for kk, vv in out["gt22"].items()
                           if kk != "test_frontier"}}, indent=1))
