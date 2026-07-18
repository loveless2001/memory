"""FOLLOWUP2 analysis: F4 (nonlinear/multi-layer context-only probe) and
F5 (sink-head monitor under eviction). Consumes the two Modal capture sets
plus the compactor-regime F3 head features for cross-regime transfer.

Run: .venv/bin/python3 plans/260719-0105-followup2-f4f5/analyze-followup2-f4-f5.py
"""
import glob
import hashlib
import json

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

ROOT = "/home/lenovo/projects/memory"
OUT = f"{ROOT}/plans/260719-0105-followup2-f4f5"
PROBE = f"{ROOT}/plans/260717-2319-probe-sufficiency-arms"
F1 = f"{ROOT}/plans/260718-0155-followup-f1f2f3"
LAYERS = [10, 15, 20, 25, 30, 36]
rng = np.random.default_rng(51235)


def doc_of(iid):
    return iid[4:].rsplit("_", 2)[0]


def bucket(iid):
    return int(hashlib.sha256(doc_of(iid).encode()).hexdigest()[:8],
               16) / 0xFFFFFFFF


def cluster_ci(y, s, groups, n=2000):
    uniq = np.unique(groups)
    by = {g: np.flatnonzero(groups == g) for g in uniq}
    a = []
    for _ in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([by[g] for g in pick])
        yy = y[idx]
        if yy.min() != yy.max():
            a.append(roc_auc_score(yy, s[idx]))
    return [round(float(np.percentile(a, 2.5)), 4),
            round(float(np.percentile(a, 97.5)), 4)]


def oof_linear(X, y, grp):
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(X, y, grp):
        sc = StandardScaler().fit(X[tr])
        clf = LogisticRegression(C=1.0, max_iter=2000).fit(sc.transform(X[tr]),
                                                           y[tr])
        oof[te] = clf.decision_function(sc.transform(X[te]))
    return oof


def oof_mlp(X, y, grp, seed):
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(X, y, grp):
        sc = StandardScaler().fit(X[tr])
        clf = MLPClassifier(hidden_layer_sizes=(256,), activation="relu",
                            alpha=1e-4, max_iter=200, early_stopping=True,
                            n_iter_no_change=15, random_state=seed)
        clf.fit(sc.transform(X[tr]), y[tr])
        oof[te] = clf.predict_proba(sc.transform(X[te]))[:, 1]
    return oof


# ============================================================================
# F4 — nonlinear / multi-layer context-only probe
# ============================================================================
def run_f4():
    ids, res, y, dom = [], [], [], []
    for p in sorted(glob.glob(f"{OUT}/f4-slice-*.npz")):
        z = np.load(p, allow_pickle=True)
        ids += [str(i) for i in z["item_ids"]]
        res.append(z["residual"].astype(np.float32)); y.append(z["y"])
        dom.append(z["domain"])
    res = np.concatenate(res); y = np.concatenate(y).astype(int)
    grp = np.array([doc_of(i) for i in ids])
    print(f"[F4] {len(ids)} context-only items, {res.shape[1]} layers")

    cells = {}
    # (a) per-layer linear sweep
    for li, lname in enumerate(LAYERS):
        s = oof_linear(res[:, li], y, grp)
        cells[f"linear_L{lname}"] = {
            "auc": round(float(roc_auc_score(y, s)), 4),
            "ci95": cluster_ci(y, s, grp)}
        print(f"[F4] linear L{lname}: {cells[f'linear_L{lname}']['auc']}")
    best_li = max(range(len(LAYERS)),
                  key=lambda i: cells[f"linear_L{LAYERS[i]}"]["auc"])
    # (b) MLP on best layer, 3 seeds
    mlp_auc = []
    for seed in (0, 1, 2):
        s = oof_mlp(res[:, best_li], y, grp, seed)
        mlp_auc.append(roc_auc_score(y, s))
    cells[f"mlp_L{LAYERS[best_li]}_3seed"] = {
        "auc": round(float(np.mean(mlp_auc)), 4),
        "sd": round(float(np.std(mlp_auc)), 4)}
    print(f"[F4] MLP L{LAYERS[best_li]}: {np.mean(mlp_auc):.4f}")
    # (c) concat-of-layers linear + MLP
    Xcat = res.reshape(len(ids), -1)
    s_lin = oof_linear(Xcat, y, grp)
    cells["concat_linear"] = {"auc": round(float(roc_auc_score(y, s_lin)), 4),
                              "ci95": cluster_ci(y, s_lin, grp)}
    s_mlp = oof_mlp(Xcat, y, grp, 0)
    cells["concat_mlp"] = {"auc": round(float(roc_auc_score(y, s_mlp)), 4)}
    print(f"[F4] concat lin {cells['concat_linear']['auc']} "
          f"mlp {cells['concat_mlp']['auc']}")

    all_auc = [c["auc"] for c in cells.values()]
    mx = max(all_auc)
    if mx >= 0.60:
        verdict = ("null NARROWS: best context-only probe %.3f is decodable "
                   "above 0.60 (still far below question-conditioned 0.85); "
                   "relational claim softens to 'dominant signal is "
                   "query-conditioned'" % mx)
        decision = "narrows"
    elif mx <= 0.55:
        verdict = ("null UPGRADES: no decodable signal (linear or nonlinear, "
                   "any probed layer) reaches 0.55; best %.3f" % mx)
        decision = "upgrades"
    else:
        verdict = ("marginal: best %.3f in [0.55,0.60]; keep layer-30-linear "
                   "framing plus measured band" % mx)
        decision = "marginal"
    out = {"n": len(ids), "layers": LAYERS, "cells": cells,
           "max_auc": round(float(mx), 4), "decision": decision,
           "verdict": verdict,
           "question_conditioned_ref": 0.813}
    json.dump(out, open(f"{OUT}/f4-verdict.json", "w"), indent=1)
    print("[F4]", verdict)
    return out


# ============================================================================
# F5 — sink-head monitor under eviction
# ============================================================================
def run_f5():
    ids, X, y, dom, rc = [], [], [], [], []
    for p in sorted(glob.glob(f"{OUT}/f5-slice-*.npz")):
        z = np.load(p, allow_pickle=True)
        ids += [str(i) for i in z["item_ids"]]
        X.append(z["feats"]); y.append(z["y"]); dom.append(z["domain"])
        rc.append(z["raw_correct"])
    X = np.concatenate(X); y = np.concatenate(y).astype(int)
    dom = np.concatenate(dom)
    grp = np.array([doc_of(i) for i in ids])
    b = np.array([bucket(i) for i in ids])
    tr, te = b < 0.6, b >= 0.7
    print(f"[F5] {len(ids)} eviction items; y+ {y.mean():.3f}; "
          f"train {tr.sum()} test {te.sum()}")

    # refit eviction monitor (bucket split, mirrors F3)
    sc = StandardScaler().fit(X[tr])
    clf_ev = LogisticRegression(C=1.0, max_iter=3000).fit(sc.transform(X[tr]),
                                                          y[tr])
    s_ev = clf_ev.decision_function(sc.transform(X))
    auc_refit = roc_auc_score(y[te], s_ev[te])
    ci_refit = cluster_ci(y[te], s_ev[te], grp[te])
    per_dom = {d: round(float(roc_auc_score(
        y[te & (dom == d)], s_ev[te & (dom == d)])), 4)
        for d in np.unique(dom[te]) if (te & (dom == d)).sum() > 20
        and len(np.unique(y[te & (dom == d)])) == 2}

    # ---- cross-regime transfer with the compactor F3 monitor -------------
    zf3 = np.load(f"{F1}/f3-headfeats.npz", allow_pickle=True)
    Xc = zf3["feats"]; yc = zf3["y"].astype(int)
    idc = np.array([str(i) for i in zf3["item_ids"]])
    grpc = np.array([doc_of(i) for i in idc])
    bc = np.array([bucket(i) for i in idc])
    trc, tec = bc < 0.6, bc >= 0.7
    scc = StandardScaler().fit(Xc[trc])
    clf_cp = LogisticRegression(C=1.0, max_iter=3000).fit(scc.transform(Xc[trc]),
                                                          yc[trc])
    # compactor monitor -> eviction test states (zero-shot)
    s_cp_on_ev = clf_cp.decision_function(scc.transform(X[te]))
    auc_cp2ev = roc_auc_score(y[te], s_cp_on_ev)
    # eviction monitor -> compactor test states (zero-shot)
    s_ev_on_cp = clf_ev.decision_function(sc.transform(Xc[tec]))
    auc_ev2cp = roc_auc_score(yc[tec], s_ev_on_cp)
    # compactor in-regime refit (reference)
    auc_cp_refit = roc_auc_score(yc[tec], clf_cp.decision_function(
        scc.transform(Xc[tec])))

    shadow_gate = 0.622   # M3 A2 evicted-only mechanics AUC
    general = auc_refit >= shadow_gate
    out = {
        "n": len(ids), "frac": 0.40, "y_pos_rate": round(float(y.mean()), 4),
        "F5_refit_auc": round(float(auc_refit), 4), "F5_refit_ci95": ci_refit,
        "per_domain": per_dom,
        "transfer": {
            "compactor_monitor_on_eviction": round(float(auc_cp2ev), 4),
            "eviction_monitor_on_compactor": round(float(auc_ev2cp), 4),
            "compactor_refit_reference": round(float(auc_cp_refit), 4),
            "eviction_refit_reference": round(float(auc_refit), 4)},
        "shadow_gate_evicted_only": shadow_gate,
        "regime_general": bool(general),
        "verdict": (
            "middle rung is regime-GENERAL: eviction sink-head monitor %.3f "
            ">= shadow-gate mechanics %.3f" % (auc_refit, shadow_gate)
            if general else
            "eviction sink-head monitor %.3f < shadow-gate mechanics %.3f: "
            "the monitor is a synthesis/subsampling-regime instrument; under "
            "eviction, mechanics features remain the cheap tier"
            % (auc_refit, shadow_gate)),
    }
    json.dump(out, open(f"{OUT}/f5-verdict.json", "w"), indent=1)
    print("[F5]", json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    r4 = run_f4()
    r5 = run_f5()
    json.dump({"F4": r4, "F5": r5},
              open(f"{OUT}/followup2-all-verdicts.json", "w"), indent=1)
    print("\n=== DONE ===")
