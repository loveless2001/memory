"""FOLLOWUP local analysis: F1 kernel-distance, F2 context-only control,
F3 sink-head monitor. Consumes the two Modal outputs (followup-f1f2 slices,
followup-f3-headfeats + f2-zeroshot-probe) plus local scores/manifest/surface
features. Emits the three verdicts, updated arm-table rows, and the three
requested artifacts.

Run:  .venv/bin/python3 plans/260718-0155-followup-f1f2f3/analyze-followup-f1-f2-f3.py
"""
import glob
import json
from collections import Counter

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

ROOT = "/home/lenovo/projects/memory"
PLAN = f"{ROOT}/plans/260717-2319-probe-sufficiency-arms"
OUT = f"{ROOT}/plans/260718-0155-followup-f1f2f3"
SINKS, RECENT, CTX, SPAN, T_LAT = 4, 1024, 4096, 1024, 1024
S_FULL = CTX - RECENT - SINKS                       # 3068
rng = np.random.default_rng(51235)


def doc_of(iid):
    return iid[4:].rsplit("_", 2)[0]


def lattice(S):
    """kept source positions for source length S (item-invariant stride kernel,
    empirically round(k*(S-1)/(T_LAT-1)))."""
    k = np.arange(T_LAT)
    return np.unique(np.round(k * (S - 1) / (T_LAT - 1)).astype(int))


def cluster_bootstrap_auc(y, s, groups, n=2000):
    """doc-level cluster bootstrap 95% CI for AUC."""
    uniq = np.unique(groups)
    idx_by = {g: np.flatnonzero(groups == g) for g in uniq}
    aucs = []
    for _ in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by[g] for g in pick])
        yy = y[idx]
        if yy.min() == yy.max():
            continue
        aucs.append(roc_auc_score(yy, s[idx]))
    lo, hi = np.percentile(aucs, [2.5, 97.5])
    return round(float(lo), 4), round(float(hi), 4)


# ----------------------------------------------------------------------------
# shared inputs
# ----------------------------------------------------------------------------
sf = json.load(open(f"{ROOT}/preprobe-data/surface-features.json"))
manifest = {m["item_id"]: m for m in json.load(
    open(f"{PLAN}/probe-capture-manifest.json"))}
za = np.load(f"{PLAN}/arm-scores-all.npz", allow_pickle=True)
arm_ids = np.array([str(i) for i in za["item_ids"]])
arm_idx = {i: k for k, i in enumerate(arm_ids)}
c2 = np.asarray(za["c2_mlp"], dtype=float)          # best read-side arm
c2_lin = np.asarray(za["c2_lin"], dtype=float)


def needle_src(iid, S):
    """needle source positions (compactor space, [0,S)) from corpus metadata.
    ctx position = chunk_rel_start + ans_rel_offset*SPAN (char~token ratio),
    source = ctx - SINKS; span width = ans_n_tokens. None if unlocatable or in
    the recent-raw window (never compacted)."""
    v = sf.get(iid)
    r = manifest.get(iid)
    if not v or not r or v.get("ans_found_in_span") != 1 \
            or v.get("ans_rel_offset") is None:
        return None
    ans_ctx = r["chunk_rel_start"] + v["ans_rel_offset"] * SPAN
    n_tok = max(1, int(v["ans_n_tokens"]))
    lo = int(round(ans_ctx))
    src = [c - SINKS for c in range(lo, lo + n_tok)
           if SINKS <= c < CTX - RECENT and 0 <= c - SINKS < S]
    return np.array(src) if src else None


def kernel_feats(src, S):
    kept = lattice(S)
    d = np.abs(src[:, None] - kept[None, :]).min(1)
    return dict(frac_needle_kept=float((d == 0).mean()),
                d_min=float(d.min()), d_mean=float(d.mean()))


# ============================================================================
# F1 — kernel-distance mechanics feature
# ============================================================================
def run_f1():
    slices = sorted(glob.glob(f"{OUT}/f1f2-slice-*.npz")) or \
        sorted(glob.glob(f"{OUT}/scaled-slice-*.npz"))
    ids, keep, S, y = [], [], [], []
    for p in slices:
        z = np.load(p, allow_pickle=True)
        ids += [str(i) for i in z["item_ids"]]
        keep.append(z["keepcount"]); S.append(z["S"]); y.append(z["y"])
    keep = np.concatenate(keep); S = np.concatenate(S); y = np.concatenate(y)
    print(f"[F1] loaded {len(ids)} context-only test items")

    # exact kernel features from GPU keepcount (test-only quantities)
    rows = []
    for k, iid in enumerate(ids):
        src = needle_src(iid, int(S[k]))
        if src is None:
            continue
        keptpos = np.flatnonzero(keep[k][:int(S[k])] > 0)
        d = np.abs(src[:, None] - keptpos[None, :]).min(1)
        rows.append((iid, int(y[k]),
                     float((d == 0).mean()), float(d.min()), float(d.mean())))
    fid = np.array([r[0] for r in rows])
    fy = np.array([r[1] for r in rows])
    frac = np.array([r[2] for r in rows]); dmin = np.array([r[3] for r in rows])
    dmean = np.array([r[4] for r in rows])
    grp = np.array([doc_of(i) for i in fid])
    print(f"[F1] needle-locatable test items: {len(fid)} "
          f"({len(fid)/len(ids):.1%})")

    def uni(sig, name):
        s = sig if roc_auc_score(fy, sig) >= 0.5 else -sig
        a = roc_auc_score(fy, s)
        lo, hi = cluster_bootstrap_auc(fy, s, grp)
        return {"feature": name, "auc": round(float(a), 4), "ci95": [lo, hi],
                "oriented": "raw" if a == roc_auc_score(fy, sig) else "flipped"}
    f1_uni = {n: uni(v, n) for n, v in
              [("d_min", dmin), ("d_mean", dmean),
               ("frac_needle_kept", frac)]}

    # mechanics-with-kernel arm: c0 surface features + analytic kernel feats,
    # fit on TRAIN, eval TEST. kernel feats analytic (S_FULL lattice) for all.
    def c0_vec(iid):
        v = sf[iid]
        ro = v["ans_rel_offset"]
        return [float(v["ans_n_tokens"]), float(ro if ro is not None else -1.0),
                float(v["ans_found_in_span"]), float(v["rarity_mean"]),
                float(v["rarity_min"])]

    def kfeat_analytic(iid):
        # assume full-length geometry S_FULL for uniform train/test features
        src = needle_src(iid, S_FULL)
        if src is None:
            return None
        return kernel_feats(src, S_FULL)

    def bucket(iid):
        import hashlib
        return int(hashlib.sha256(doc_of(iid).encode()).hexdigest()[:8],
                   16) / 0xFFFFFFFF
    Xc0, Xk, yy, sp, gg = [], [], [], [], []
    for iid in arm_ids:
        if iid.startswith("mh:"):
            continue
        kf = kfeat_analytic(iid)
        if kf is None:
            continue
        Xc0.append(c0_vec(iid))
        Xk.append([kf["frac_needle_kept"], kf["d_min"], kf["d_mean"]])
        yy.append(int(za["y"][arm_idx[iid]]))
        b = bucket(iid); sp.append(0 if b < 0.6 else (1 if b < 0.7 else 2))
        gg.append(doc_of(iid))
    Xc0 = np.array(Xc0); Xk = np.array(Xk); yy = np.array(yy)
    sp = np.array(sp); gg = np.array(gg)
    tr, te = sp == 0, sp == 2

    def fit_eval(X):
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        clf = LogisticRegression(C=1.0, max_iter=3000)
        clf.fit((X[tr] - mu) / sd, yy[tr])
        s = clf.decision_function((X - mu) / sd)
        a = roc_auc_score(yy[te], s[te])
        lo, hi = cluster_bootstrap_auc(yy[te], s[te], gg[te])
        return round(float(a), 4), [lo, hi]
    c0_auc, c0_ci = fit_eval(Xc0)
    arm_auc, arm_ci = fit_eval(np.hstack([Xc0, Xk]))
    konly_auc, konly_ci = fit_eval(Xk)

    # c2-residualization: does c2's score correlate with d_min? (test, evicted)
    c2_test = np.array([c2[arm_idx[i]] for i in fid])
    rho, pval = spearmanr(c2_test, dmin)
    rho_frac, _ = spearmanr(c2_test, frac)

    if arm_auc >= 0.75:
        branch, verdict = "i", ("subsampling loss IS mechanics-routable given "
                                "the kernel; paper keeps branch (i)")
    elif arm_auc >= 0.60:
        branch, verdict = "ii", "partial; branch (ii)"
    else:
        branch, verdict = "iii", "smear dominates; branch (iii)"

    out = {
        "n_context_only_items": len(ids),
        "n_needle_locatable": int(len(fid)),
        "F1_uni": f1_uni,
        "mechanics_with_kernel_arm": {
            "c0_only_auc": c0_auc, "c0_only_ci": c0_ci,
            "kernel_only_auc": konly_auc, "kernel_only_ci": konly_ci,
            "c0_plus_kernel_auc": arm_auc, "c0_plus_kernel_ci": arm_ci,
            "delta_over_c0": round(arm_auc - c0_auc, 4)},
        "c2_residualization": {
            "spearman_c2_vs_dmin": round(float(rho), 4), "p": float(pval),
            "spearman_c2_vs_frac_needle_kept": round(float(rho_frac), 4)},
        "branch": branch, "verdict": verdict,
        "kept_kernel": "stride ~S/1024 (=2.998 at S=3068) delta lattice, "
                       "head- and item-invariant; density 1/3",
    }
    np.savez_compressed(f"{OUT}/f1-kernel-features.npz",
                        item_ids=fid, y=fy, frac_needle_kept=frac,
                        d_min=dmin, d_mean=dmean)
    json.dump(out, open(f"{OUT}/f1-verdict.json", "w"), indent=1)
    print("[F1]", json.dumps(out, indent=1))
    return out


# ============================================================================
# F2 — context-only probe control
# ============================================================================
def run_f2():
    slices = sorted(glob.glob(f"{OUT}/f1f2-slice-*.npz")) or \
        sorted(glob.glob(f"{OUT}/scaled-slice-*.npz"))
    ids, res, y = [], [], []
    for p in slices:
        z = np.load(p, allow_pickle=True)
        ids += [str(i) for i in z["item_ids"]]
        res.append(z["residual30"].astype(np.float32)); y.append(z["y"])
    res = np.concatenate(res); y = np.concatenate(y).astype(int)
    grp = np.array([doc_of(i) for i in ids])
    print(f"[F2] {len(ids)} context-only residuals")

    # (b) zero-shot: apply question-conditioned layer-30 probe to context-only
    zp = np.load(f"{ROOT}/plans/260718-0155-followup-f1f2f3/"
                 "f2-zeroshot-probe.npz")
    mu, sd, w, c = zp["mu"], zp["sd"], zp["w"], float(zp["c"])
    s_zero = ((res - mu) / sd) @ w + c
    zs_auc = roc_auc_score(y, s_zero)
    zs_ci = cluster_bootstrap_auc(y, s_zero, grp)

    # (a) refit on context-only states, doc-level 5-fold OOF AUC
    oof = np.zeros(len(y))
    gkf = GroupKFold(n_splits=5)
    for trf, tef in gkf.split(res, y, grp):
        mu2, sd2 = res[trf].mean(0), res[trf].std(0) + 1e-6
        clf = LogisticRegression(C=1.0, max_iter=2000)
        clf.fit((res[trf] - mu2) / sd2, y[trf])
        oof[tef] = clf.decision_function((res[tef] - mu2) / sd2)
    rf_auc = roc_auc_score(y, oof)
    rf_ci = cluster_bootstrap_auc(y, oof, grp)

    out = {
        "n": len(ids),
        "F2_refit_auc": round(float(rf_auc), 4), "F2_refit_ci95": list(rf_ci),
        "F2_zeroshot_auc": round(float(zs_auc), 4),
        "F2_zeroshot_ci95": list(zs_ci),
        "question_conditioned_probe_sanity": {
            "train_auc": float(zp["train_auc"]), "val_auc": float(zp["val_auc"]),
            "test_auc": float(zp["test_auc"])},
        "reading": None,
    }
    c2_ref = float(zp["test_auc"])
    if rf_auc >= c2_ref - 0.03:
        out["reading"] = ("probe reads memory content (refit ~ c2 %.3f); the "
                          "0.85 is a genuine sufficiency readout" % c2_ref)
    elif rf_auc <= 0.6:
        out["reading"] = ("near chance -> 0.85 is substantially answer-"
                          "confidence; downgrade to behavioral-divergence "
                          "predictor")
    else:
        out["reading"] = ("intermediate: content is partially decodable "
                          "without the question")
    json.dump(out, open(f"{OUT}/f2-verdict.json", "w"), indent=1)
    print("[F2]", json.dumps(out, indent=1))
    return out


# ============================================================================
# F3 — standalone sink-head monitor
# ============================================================================
def run_f3():
    z = np.load(f"{OUT}/f3-headfeats.npz", allow_pickle=True)
    ids = np.array([str(i) for i in z["item_ids"]])
    X, y, split, dom, p2 = (z["feats"], z["y"], z["split"], z["domain"],
                            z["p2"])
    grp = np.array([doc_of(i) for i in ids])
    tr, te = split == 0, split == 2

    def fit(Xin):
        mu, sd = Xin[tr].mean(0), Xin[tr].std(0) + 1e-9
        clf = LogisticRegression(C=1.0, max_iter=3000)
        clf.fit((Xin[tr] - mu) / sd, y[tr])
        return clf.decision_function((Xin - mu) / sd)
    s = fit(X)
    auc = roc_auc_score(y[te], s[te])
    ci = cluster_bootstrap_auc(y[te], s[te], grp[te])
    per_dom = {}
    for d in np.unique(dom[te]):
        mte = te & (dom == d)
        per_dom[d] = round(float(roc_auc_score(y[mte], s[mte])), 4)

    # p2 + sinkheads combined
    s_combo = fit(np.hstack([X, p2[:, None]]))
    combo_auc = round(float(roc_auc_score(y[te], s_combo[te])), 4)

    # ---- GT22-style weighted end-to-end for p2+sinkheads ------------------
    pop_rows = []
    for p in sorted(glob.glob(f"{ROOT}/preprobe-data/*-slice-*.json")):
        if "capture" in p or "c05" in p or "relabel" in p:
            continue
        pop_rows.extend(json.load(open(p))["rows"])
    ev = [r for r in pop_rows if r["evicted_still"] == 1]
    pop = Counter((r["domain"], r["y_still"]) for r in ev)
    frac_evicted = len(ev) / len(pop_rows)
    raw_ok = np.array([manifest.get(i, {}).get("raw_correct", 1)
                       for i in ids], dtype=bool)

    def weighted_op(mask, sc, taus=None):
        idx = np.flatnonzero(mask)
        samp = Counter((dom[k], y[k]) for k in idx)
        wv = np.array([pop[(dom[k], y[k])] / samp[(dom[k], y[k])] for k in idx])
        ss, yy, rc = sc[idx], y[idx], raw_ok[idx]
        if taus is None:
            taus = np.quantile(ss, np.linspace(0.02, 0.98, 97))
        curve = []
        for t in taus:
            ex = ss >= t
            lost = float((wv * ((yy == 1) & ~ex & rc)).sum()
                         / max((wv * rc).sum(), 1e-9))
            ev_exp = float((wv * ex).sum() / wv.sum())
            curve.append({"tau": float(t),
                          "lost_prior_correct": round(lost, 4),
                          "expand_evicted": round(ev_exp, 4),
                          "expand_all_est": round(ev_exp * frac_evicted, 4)})
        return curve
    val_curve = weighted_op(split == 1, s_combo)
    ok = [c for c in val_curve if c["lost_prior_correct"] <= 0.146]
    chosen = min(ok, key=lambda c: c["expand_evicted"]) if ok else None
    test_at = weighted_op(split == 2, s_combo,
                          taus=[chosen["tau"]] if chosen else None)[0]

    out = {
        "F3_AUC": round(float(auc), 4), "F3_ci95": list(ci),
        "per_domain": per_dom,
        "p2_plus_sinkheads_auc": combo_auc,
        "F3_e2e_p2_plus_sinkheads": {
            "val_chosen_tau": chosen, "test_at_tau": test_at,
            "comparators": {"p2_free_auc": 0.638, "full_stack_auc": 0.854,
                            "stack_gate_e2e": {"lost": 0.146, "expand": 0.050},
                            "refreshed_gate": {"lost": 0.146, "expand": 0.147}}},
        "ladder": "p2 free 0.638 -> sinkheads (+2 hooks) %.3f -> stack 0.854"
                  % auc,
    }
    json.dump(out, open(f"{OUT}/f3-monitor.json", "w"), indent=1)
    print("[F3]", json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    r1 = run_f1()
    r2 = run_f2()
    r3 = run_f3()
    json.dump({"F1": r1, "F2": r2, "F3": r3},
              open(f"{OUT}/followup-all-verdicts.json", "w"), indent=1)
    print("\n=== DONE ===")
