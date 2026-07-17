"""PROBE P0 analysis: p1 attention-statistic battery AUCs + p2 self-check
floor on the 1k pilot, and the GT19 gate decision.

p1 bar: any single statistic >= 0.60 -> c1 proceeds as designed;
        all < 0.55 -> c1 demoted to per-head analysis inside c2's sweep.
p2: the floor ANY trained arm must beat; >= 0.62 changes the cost story.

Inputs: preprobe-data/probe-capture-pilot-slice-00.{state.json,npz}
Output: plans/260717-2319-probe-sufficiency-arms/p0-analysis.json
"""

import json

import numpy as np
from sklearn.metrics import roc_auc_score

PLAN = "plans/260717-2319-probe-sufficiency-arms"
STATS = ["m_lat", "m_sink", "m_rec", "ent_lat", "max_lat_abs", "max_lat_rel"]
STEPS = ["last_prompt", "decode1", "decode2", "decode3"]

state = json.load(open("preprobe-data/probe-capture-pilot-slice-00.state.json"))
z = np.load("preprobe-data/probe-capture-pilot-slice-00.npz")
rows = state["rows"]
ids = list(z["item_ids"])
attn = z["attn_stats"].astype(np.float32)          # [N, 4, 36, 32, 6]
by_id = {r["item_id"]: r for r in rows}
y = np.array([by_id[i]["y"] for i in ids])
print(f"pilot n={len(ids)} y+={y.mean():.3f}")


def auc(v):
    a = roc_auc_score(y, v)
    return max(a, 1 - a)


battery = {}
# derived lookback ratio needs m_lat and m_rec before aggregation
lookback = attn[..., 0] / (attn[..., 0] + attn[..., 2] + 1e-9)  # [N,4,36,32]
for si, sname in enumerate(STATS + ["lookback"]):
    base = lookback if sname == "lookback" else attn[..., si]   # [N,4,36,32]
    for step in range(4):
        v = base[:, step]                                        # [N,36,32]
        battery[f"{sname}/{STEPS[step]}/mean"] = auc(v.mean((1, 2)))
        battery[f"{sname}/{STEPS[step]}/max"] = auc(v.max((1, 2)))
    battery[f"{sname}/steps_mean/mean"] = auc(base.mean((1, 2, 3)))

top = sorted(battery.items(), key=lambda kv: -kv[1])[:15]
best_stat, best_auc = top[0]

p2 = np.array([by_id[i]["p2_insufficient"] for i in ids])
p2_auc = roc_auc_score(y, p2)
p2_auc = max(p2_auc, 1 - p2_auc)

# trial-pass consistency sanity: pred_trial != pred_raw should track y_A
mismatch = np.array([by_id[i]["pred_trial"] != by_id[i]["pred_raw"].strip()
                     .upper()[:1] for i in ids]).astype(float)
sanity_auc = roc_auc_score(y, mismatch)

# c3a quick look on pilot (aggregated means over layers/heads)
c3a = z["c3a"].astype(np.float32)                   # [N, 36, 8, 4]
c3a_battery = {}
for fi, fname in enumerate(["needle_share_ratio", "lstar_purity",
                            "lstar_entropy", "top_needle_frac"]):
    c3a_battery[f"c3a/{fname}/mean"] = auc(c3a[..., fi].mean((1, 2)))
    c3a_battery[f"c3a/{fname}/max"] = auc(c3a[..., fi].max((1, 2)))

if best_auc >= 0.60:
    gt19_c1 = "c1 PROCEEDS as designed (p1 bar met)"
elif best_auc < 0.55:
    gt19_c1 = "c1 DEMOTED to per-head analysis inside c2 sweep (all < 0.55)"
else:
    gt19_c1 = ("c1 proceeds cautiously (best in [0.55, 0.60): signal exists "
               "but weak; per-head featurization must add value)")

out = {"n": len(ids), "y_rate": float(y.mean()),
       "p1_battery_top15": {k: round(v, 4) for k, v in top},
       "p1_best": {"stat": best_stat, "auc": round(best_auc, 4)},
       "p2_selfcheck_auc": round(float(p2_auc), 4),
       "p2_direction_note": "score = P(No | sufficiency question)",
       "trial_mismatch_sanity_auc": round(float(sanity_auc), 4),
       "c3a_pilot_battery": {k: round(v, 4) for k, v in
                             sorted(c3a_battery.items(),
                                    key=lambda kv: -kv[1])},
       "gt19": {"c1_decision": gt19_c1,
                "p2_floor": round(float(p2_auc), 4),
                "p2_changes_cost_story": bool(p2_auc >= 0.62)}}
with open(f"{PLAN}/p0-analysis.json", "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
