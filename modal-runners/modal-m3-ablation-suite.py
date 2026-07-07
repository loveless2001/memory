"""M3 ablation suite (ABLATION.md A1-A5) — re-analysis of stored labels +
embeddings plus small retrains. No new corpus, no new labeling passes, no
architecture changes (A2 variants are input ablations: zeroed embeddings or
zeroed features through the identical model).

Usage: modal run modal-runners/modal-m3-ablation-suite.py
Writes gate-eval/ablation-results.json and updates gate-eval/eval-grid.json
with evicted_only + CI fields.
"""

import json

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3"]
app = modal.App("memsub-m3-ablation")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
    .add_local_dir("memsub", "/root/repo/memsub")
)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
DOMAINS = ("financial", "legal", "code", "literature")
FRACTIONS = (0.25, 0.40)
TAU = 0.4879339294253414   # GT9 operating point from the 07-07 run
SEEDS = (0, 1, 2)


@app.function(image=image, gpu="L4", volumes={"/artifacts": artifacts},
              timeout=14400, memory=65536, cpu=8)
def run_ablations() -> dict:
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    from memsub.gate import TrainConfig, end_to_end_lost_fact, make_splits, train_gate
    from memsub.gate.domain_recalibration import recalibrate_domain
    from memsub.gate.dual_encoder_expansion_gate import calibrate_temperature
    from memsub.gate.gate_evaluation_metrics import (
        auc_score, average_precision, expected_calibration_error,
        precision_recall)
    from memsub.gate.label_dataset_splits import build_dataset

    with open("/artifacts/corpus-gate-labels/all-labels.json") as f:
        rows = json.load(f)
    emb = np.load("/artifacts/corpus-gate-labels/embeddings.npz")
    ds = build_dataset(rows, emb["q_emb"], emb["b_emb"])
    splits = make_splits(ds, mode="document")
    test_idx = np.flatnonzero(splits["test"])
    cal_idx = np.flatnonzero(splits["cal"])
    results: dict = {}

    def variant_dataset(kind: str):
        if kind == "full":
            return ds
        import dataclasses as dc
        clone = ds.subset(np.ones(len(ds), dtype=bool))
        if kind == "features_only":
            clone.q_emb = np.zeros_like(ds.q_emb)
            clone.b_emb = np.zeros_like(ds.b_emb)
        elif kind == "embeddings_only":
            clone.fraction = np.zeros_like(ds.fraction)
            clone.overlap = np.zeros_like(ds.overlap)
            clone.evicted = np.zeros_like(ds.evicted)
            clone.domain = np.array(["none"] * len(ds))  # onehot -> all zero
        return clone

    def evicted_only_metrics(model, dvar, temp_refit: bool) -> dict:
        ev_test = test_idx[ds.evicted[test_idx] == 1]
        ev_cal = cal_idx[ds.evicted[cal_idx] == 1]
        if temp_refit:  # A1: re-fit temperature on evicted-only cal subset
            calibrate_temperature(model, dvar, np.isin(
                np.arange(len(ds)), ev_cal))
        p = model.predict_proba(dvar, ev_test)
        y = ds.y[ev_test]
        out = {"auc": auc_score(p, y), "pr_auc": average_precision(p, y),
               **precision_recall(p, y, TAU),
               "ece": expected_calibration_error(p, y)}
        for f in FRACTIONS:
            m = ds.fraction[ev_test] == f
            out[f"auc_{f:.2f}"] = auc_score(p[m], y[m])
            out[f"ece_{f:.2f}"] = expected_calibration_error(p[m], y[m])
        for d in DOMAINS:
            m = ds.domain[ev_test] == d
            out[f"auc_{d}"] = auc_score(p[m], y[m])
        return out

    # ---- A2 + A4: 3 variants x 3 seeds -----------------------------------
    results["a2_decomposition"] = {}
    gt9_by_seed = []
    for kind in ("full", "features_only", "embeddings_only"):
        dvar = variant_dataset(kind)
        per_seed = []
        for seed in SEEDS:
            model = train_gate(dvar, splits["train"], TrainConfig(seed=seed), device="cuda").cpu()
            calibrate_temperature(model, dvar, splits["cal"])
            m = evicted_only_metrics(model, dvar, temp_refit=False)
            # pooled AUC too, for the A1 contrast
            p_all = model.predict_proba(dvar, test_idx)
            m["pooled_auc"] = auc_score(p_all, ds.y[test_idx])
            per_seed.append(m)
            if kind == "full":
                ev = test_idx[ds.evicted[test_idx] == 1]
                e2e = end_to_end_lost_fact(
                    ds, test_idx, model.predict_proba(dvar, test_idx) >= TAU)
                gt9_by_seed.append(e2e)
        agg = {k: {"mean": float(np.mean([s[k] for s in per_seed])),
                   "sd": float(np.std([s[k] for s in per_seed]))}
               for k in per_seed[0] if isinstance(per_seed[0][k], float)}
        results["a2_decomposition"][kind] = agg

    results["a4_gt9_seeds"] = {
        k: {"mean": float(np.mean([s[k] for s in gt9_by_seed])),
            "sd": float(np.std([s[k] for s in gt9_by_seed]))}
        for k in ("lost_fact_rate_evicted_prior_correct", "expand_rate_all")}

    # ---- A1: evicted-only metrics for the shipped model (seed 0) ---------
    model = train_gate(ds, splits["train"], TrainConfig(seed=0), device="cuda").cpu()
    calibrate_temperature(model, ds, splits["cal"])
    results["a1_pooled_vs_evicted"] = {
        "pooled_auc": auc_score(model.predict_proba(ds, test_idx), ds.y[test_idx]),
        "evicted_only": evicted_only_metrics(model, ds, temp_refit=True),
    }

    # ---- A4: bootstrap CIs (1k resamples over test rows per cell) --------
    rng = np.random.default_rng(0)
    p_test = model.predict_proba(ds, test_idx)

    def bootstrap_ci(idx_pool: np.ndarray, stat_fn, n=1000):
        stats = []
        for _ in range(n):
            take = rng.integers(0, len(idx_pool), len(idx_pool))
            stats.append(stat_fn(idx_pool[take]))
        lo, hi = np.percentile(stats, [2.5, 97.5])
        return {"point": float(stat_fn(idx_pool)), "ci95": [float(lo), float(hi)]}

    ev_rows = np.flatnonzero(ds.evicted[test_idx] == 1)  # positions in test_idx
    results["a4_bootstrap"] = {
        "lost_fact_evicted": bootstrap_ci(
            ev_rows, lambda r: float(((p_test[r] < TAU) &
                                      (ds.compact_correct[test_idx[r]] == 0)).mean())),
        "expand_rate_all": bootstrap_ci(
            np.arange(len(test_idx)), lambda r: float((p_test[r] >= TAU).mean())),
        "auc_evicted_only": bootstrap_ci(
            ev_rows, lambda r: auc_score(p_test[r], ds.y[test_idx[r]])),
    }
    up = results["a4_bootstrap"]["lost_fact_evicted"]["ci95"][1]
    results["a4_gt9_verdict"] = {
        "upper_ci": up, "pass_by_upper_ci": bool(up <= 0.15),
        "note": "if False: frontier reported honestly per GATE.md GT9 escape clause"}

    # ---- A3: canonical never-expand rows under the M3 protocol -----------
    results["a3_canonical_never_expand"] = {}
    for f in FRACTIONS:
        m = (ds.evicted[test_idx] == 1) & (ds.fraction[test_idx] == f)
        rows_f = test_idx[m]
        results["a3_canonical_never_expand"][f"{f:.2f}"] = {
            "lost_fact_rate": float((ds.compact_correct[rows_f] == 0).mean()),
            "n_rows": int(m.sum())}

    # ---- A5: LODO recalibration check (post ECE <= 0.05 per domain) ------
    results["a5_lodo_recalibration"] = {}
    for held in DOMAINS:
        sp = make_splits(ds, mode="document", holdout_domain=held)
        m2 = train_gate(ds, sp["train"], TrainConfig(seed=0), device="cuda").cpu()
        hidx = np.flatnonzero(sp["test"])
        logits, _ = m2.predict_logits(ds, hidx)
        rng2 = np.random.default_rng(7)
        fit_sel = rng2.choice(len(hidx), 200, replace=False)
        eval_sel = np.setdiff1d(np.arange(len(hidx)), fit_sel)
        rec = recalibrate_domain(held, logits[fit_sel], ds.y[hidx][fit_sel],
                                 logits[eval_sel], ds.y[hidx][eval_sel])
        results["a5_lodo_recalibration"][held] = rec.__dict__

    with open("/artifacts/gate-eval/ablation-results.json", "w") as f:
        json.dump(results, f, indent=1, default=float)
    # merge evicted-only + CI fields into eval-grid.json (A1 deliverable)
    with open("/artifacts/gate-eval/eval-grid.json") as f:
        grid = json.load(f)
    grid["evicted_only"] = results["a1_pooled_vs_evicted"]["evicted_only"]
    grid["bootstrap_ci"] = results["a4_bootstrap"]
    grid["canonical_never_expand"] = results["a3_canonical_never_expand"]
    with open("/artifacts/gate-eval/eval-grid.json", "w") as f:
        json.dump(grid, f, indent=1, default=float)
    artifacts.commit()
    return results


@app.local_entrypoint()
def main():
    print(json.dumps(run_ablations.remote(), indent=1, default=float))
