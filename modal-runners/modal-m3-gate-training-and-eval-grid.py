"""M3 gate training + the GATE.md §5 evaluation grid on Modal.

Consumes corpus-gate-labels/{all-labels.json, embeddings.npz}. Produces, in
the memsub-artifacts volume under gate-eval/:
  gate-checkpoint.pt (+ temperatures + config hash), eval-grid.json,
  cost-correctness-plane.png, reliability-curves.png.

Usage: modal run modal-runners/modal-m3-gate-training-and-eval-grid.py
"""

import json

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "matplotlib>=3.9"]

app = modal.App("memsub-m3-gate-eval")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
    .add_local_dir("memsub", "/root/repo/memsub")
)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
DOMAINS = ("financial", "legal", "code", "literature")
FRACTIONS = (0.25, 0.40)


@app.function(image=image, volumes={"/artifacts": artifacts}, timeout=14400,
              memory=65536, cpu=8)
def train_and_evaluate(seed: int = 0) -> dict:
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch
    from memsub.gate import (TrainConfig, end_to_end_lost_fact, make_splits,
                             threshold_sweep, train_gate)
    from memsub.gate.dual_encoder_expansion_gate import calibrate_temperature
    from memsub.gate.gate_evaluation_metrics import (
        auc_score, average_precision, baseline_decisions,
        expected_calibration_error, operating_point, precision_recall,
        reliability_curve)
    from memsub.gate.label_dataset_splits import (assert_no_doc_leakage,
                                                  build_dataset)

    os.makedirs("/artifacts/gate-eval", exist_ok=True)
    with open("/artifacts/corpus-gate-labels/all-labels.json") as f:
        rows = json.load(f)
    emb = np.load("/artifacts/corpus-gate-labels/embeddings.npz")
    ds = build_dataset(rows, emb["q_emb"], emb["b_emb"])
    print(f"dataset rows: {len(ds)}; positive rates:",
          {f: float(ds.y[ds.fraction == f].mean()) for f in FRACTIONS})

    cfg = TrainConfig(seed=seed)
    splits = make_splits(ds, mode="document")
    assert_no_doc_leakage(ds, splits)
    model = train_gate(ds, splits["train"], cfg)
    temps = calibrate_temperature(model, ds, splits["cal"])

    test_idx = np.flatnonzero(splits["test"])
    cal_idx = np.flatnonzero(splits["cal"])
    p_test = model.predict_proba(ds, test_idx)
    p_cal = model.predict_proba(ds, cal_idx)
    _, aux_test = model.predict_logits(ds, test_idx)
    aux_p_test = 1 / (1 + np.exp(-aux_test))

    grid: dict = {"config_hash": cfg.config_hash(), "temperatures": temps,
                  "n_rows": len(ds), "seed": seed}

    # GT7: per-fraction ECE + reliability on test
    grid["calibration"] = {}
    for f in FRACTIONS:
        m = ds.fraction[test_idx] == f
        grid["calibration"][f"{f:.2f}"] = {
            "ece": expected_calibration_error(p_test[m], ds.y[test_idx][m]),
            "reliability": reliability_curve(p_test[m], ds.y[test_idx][m]),
            "auc": auc_score(p_test[m], ds.y[test_idx][m]),
            "average_precision": average_precision(p_test[m], ds.y[test_idx][m]),
        }

    # GT9 operating point chosen on CAL, reported on TEST
    sweep_cal = threshold_sweep(ds, cal_idx, p_cal)
    op = operating_point(sweep_cal, target_lost=0.15, max_expand_rate=0.5)
    tau = op["threshold"]
    grid["operating_point_cal"] = op
    grid["gt9_test"] = end_to_end_lost_fact(ds, test_idx, p_test >= tau)
    grid["gt9_test"]["threshold"] = tau
    grid["gt9_test"].update(precision_recall(p_test, ds.y[test_idx], tau))

    # Plane: gate + classify curves, baseline points (test)
    grid["plane"] = {"gate": threshold_sweep(ds, test_idx, p_test),
                     "classify_and_expand": threshold_sweep(ds, test_idx, aux_p_test)}
    for name, dec in baseline_decisions(ds, test_idx, aux_p_test).items():
        grid["plane"][f"point_{name}"] = end_to_end_lost_fact(ds, test_idx, dec)

    # GT8: matched expand-rate dominance vs classify-and-expand
    grid["gt8_matched_expand"] = []
    for target in (0.1, 0.2, 0.3, 0.4, 0.5):
        pick = lambda sweep: min(
            sweep, key=lambda s: abs(s["expand_rate_all"] - target))
        g, c = pick(grid["plane"]["gate"]), pick(grid["plane"]["classify_and_expand"])
        grid["gt8_matched_expand"].append({
            "target_expand_rate": target,
            "gate_lost": g["lost_fact_rate_evicted_prior_correct"],
            "classify_lost": c["lost_fact_rate_evicted_prior_correct"],
            "gate_dominates": g["lost_fact_rate_evicted_prior_correct"]
                              < c["lost_fact_rate_evicted_prior_correct"]})

    # per domain × fraction table (test, at tau)
    grid["per_domain"] = {}
    for d in DOMAINS:
        for f in FRACTIONS:
            m = (ds.domain[test_idx] == d) & (ds.fraction[test_idx] == f)
            if m.sum() == 0:
                continue
            sub_idx = test_idx[m]
            e2e = end_to_end_lost_fact(ds, sub_idx, p_test[m] >= tau)
            e2e.update(precision_recall(p_test[m], ds.y[sub_idx], tau))
            e2e["ece"] = expected_calibration_error(p_test[m], ds.y[sub_idx])
            grid["per_domain"][f"{d}/{f:.2f}"] = e2e

    # GT6 leakage control: item-level split must score HIGHER
    item_splits = make_splits(ds, mode="item")
    m_item = train_gate(ds, item_splits["train"], cfg)
    it_idx = np.flatnonzero(item_splits["test"])
    grid["gt6"] = {
        "doc_split_auc": auc_score(p_test, ds.y[test_idx]),
        "item_split_auc": auc_score(m_item.predict_proba(ds, it_idx, calibrated=False),
                                    ds.y[it_idx]),
    }
    grid["gt6"]["leaky_higher"] = grid["gt6"]["item_split_auc"] > grid["gt6"]["doc_split_auc"]

    # LODO generalization rows
    grid["lodo"] = {}
    for held in DOMAINS:
        sp = make_splits(ds, mode="document", holdout_domain=held)
        m2 = train_gate(ds, sp["train"], cfg)
        calibrate_temperature(m2, ds, sp["cal"])
        hidx = np.flatnonzero(sp["test"])
        ph = m2.predict_proba(ds, hidx)
        grid["lodo"][held] = {
            "auc": auc_score(ph, ds.y[hidx]),
            "ece": expected_calibration_error(ph, ds.y[hidx]),
            **end_to_end_lost_fact(ds, hidx, ph >= tau)}

    torch.save({"state_dict": model.state_dict(), "temperatures": temps,
                "config": cfg.__dict__, "config_hash": cfg.config_hash(),
                "threshold": tau},
               "/artifacts/gate-eval/gate-checkpoint.pt")
    with open("/artifacts/gate-eval/eval-grid.json", "w") as f:
        json.dump(grid, f, indent=1, default=float)
    _plots(grid)
    artifacts.commit()
    return {"gt6": grid["gt6"], "gt7": {k: v["ece"] for k, v in grid["calibration"].items()},
            "gt8": grid["gt8_matched_expand"], "gt9": grid["gt9_test"],
            "op": {k: op[k] for k in ("threshold", "gt9_feasible", "expand_rate_all",
                                      "lost_fact_rate_evicted_prior_correct")}}


def _plots(grid: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 5))
    for name, style in (("gate", "-o"), ("classify_and_expand", "--s")):
        pts = sorted(grid["plane"][name], key=lambda s: s["expand_rate_all"])
        ax.plot([s["expand_rate_all"] for s in pts],
                [s["lost_fact_rate_evicted_prior_correct"] for s in pts],
                style, label=name, markersize=3)
    for name, marker in (("never_expand", "x"), ("always_expand", "*"),
                         ("oracle_expand", "D")):
        pt = grid["plane"][f"point_{name}"]
        ax.plot(pt["expand_rate_all"], pt["lost_fact_rate_evicted_prior_correct"],
                marker, markersize=10, label=name)
    ax.set_xlabel("expand rate (cost proxy)")
    ax.set_ylabel("lost-fact rate | prior-correct (evicted spans)")
    ax.legend(); ax.grid(alpha=0.3)
    ax.set_title("Cost / correctness plane (test split)")
    fig.savefig("/artifacts/gate-eval/cost-correctness-plane.png", dpi=150,
                bbox_inches="tight")

    fig, axes = plt.subplots(1, len(grid["calibration"]), figsize=(11, 4.5))
    for ax, (frac, cal) in zip(axes, grid["calibration"].items()):
        xs = [b["mean_pred"] for b in cal["reliability"]]
        ys = [b["empirical"] for b in cal["reliability"]]
        ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
        ax.plot(xs, ys, "-o")
        ax.set_title(f"evict {frac}: ECE={cal['ece']:.3f}")
        ax.set_xlabel("predicted p(insufficient)"); ax.set_ylabel("empirical")
    fig.savefig("/artifacts/gate-eval/reliability-curves.png", dpi=150,
                bbox_inches="tight")


@app.function(image=image, gpu="L4",
              volumes={"/artifacts": artifacts,
                       "/root/.cache/huggingface":
                       modal.Volume.from_name("memsub-hf-cache")},
              timeout=7200, memory=32768)
def evaluate_multihop() -> dict:
    """GATE.md §5 multi-hop slice, reported separately: two gate rows per
    composed question — (q, evicted block, y from counterfactual) and
    (q, survived block, y=0)."""
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch
    from memsub.compilers import Qwen3ShadowEmbedder
    from memsub.gate import DualEncoderExpansionGate, TrainConfig, end_to_end_lost_fact
    from memsub.gate.gate_evaluation_metrics import auc_score, precision_recall
    from memsub.gate.label_dataset_splits import GateDataset

    with open("/artifacts/corpus-gate-labels/multihop-slice.json") as f:
        slice_rows = json.load(f)
    ck = torch.load("/artifacts/gate-eval/gate-checkpoint.pt", weights_only=False)
    cfg = TrainConfig(**ck["config"])
    emb = Qwen3ShadowEmbedder(device="cuda", dtype="bfloat16")

    def batch_embed(texts, bs=64):
        return np.concatenate([emb.embed(texts[i:i + bs])
                               for i in range(0, len(texts), bs)]).astype(np.float32)

    q_texts = [r["question"] + " || recent: " + r["ctx_tail_gloss"] for r in slice_rows]
    q_emb = batch_embed(q_texts)
    ev_emb = batch_embed([r["evicted_block_gloss"] for r in slice_rows])
    sv_emb = batch_embed([r["survived_block_gloss"] for r in slice_rows])

    n = len(slice_rows)
    ds = GateDataset(
        item_id=np.array([f"mh_{i}_{k}" for k in ("ev", "sv") for i in range(n)]),
        doc_id=np.array([r["doc_id"] for r in slice_rows] * 2),
        domain=np.array([r["domain"] for r in slice_rows] * 2),
        fraction=np.full(2 * n, 0.25, dtype=np.float32),
        y=np.array([r["y"] for r in slice_rows] + [0] * n),
        overlap=np.array([1.0] * n + [0.0] * n, dtype=np.float32),
        evicted=np.array([1] * n + [0] * n),
        pointwise=np.ones(2 * n, dtype=np.int64),
        raw_correct=np.ones(2 * n, dtype=np.int64),  # teacher-filtered
        compact_correct=np.array(
            [r["compact_correct"] for r in slice_rows] * 2),
        q_emb=np.concatenate([q_emb, q_emb]),
        b_emb=np.concatenate([ev_emb, sv_emb]))

    model = DualEncoderExpansionGate(q_emb.shape[1], cfg)
    model.load_state_dict(ck["state_dict"])
    model.temperatures = ck["temperatures"]
    idx = np.arange(2 * n)
    p = model.predict_proba(ds, idx)
    tau = ck["threshold"]
    out = {
        "n_questions": n,
        "positive_rate_evicted_rows": float(ds.y[:n].mean()),
        "auc": auc_score(p, ds.y),
        **{f"pr_{k}": v for k, v in precision_recall(p, ds.y, tau).items()},
        "gate_at_tau": end_to_end_lost_fact(ds, idx, p >= tau),
        "never": end_to_end_lost_fact(ds, idx, np.zeros(2 * n, dtype=bool)),
        "oracle": end_to_end_lost_fact(ds, idx, ds.y == 1),
    }
    with open("/artifacts/gate-eval/multihop-eval.json", "w") as f:
        json.dump(out, f, indent=1, default=float)
    artifacts.commit()
    return out


@app.local_entrypoint()
def main(seed: int = 0):
    out = train_and_evaluate.remote(seed)
    print(json.dumps(out, indent=1, default=float))
