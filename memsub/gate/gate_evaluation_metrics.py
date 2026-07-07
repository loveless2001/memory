"""Gate evaluation metrics (GATE.md §5; spec §17.6).

All metrics are computed offline from stored per-item predictions — the
labeling pass recorded both the compacted and raw answers, so the
cost/correctness plane needs no further model forwards.

end-to-end lost-fact semantics (pairs against the M1 baselines): an item is
SILENTLY LOST iff its compacted answer is wrong AND the gate did not expand.
Expanded items are never silently lost (the expansion is visible), and their
answer becomes the raw-span answer. Rates are reported both raw and
conditioned on raw_correct (the V2 lesson: the conditioned metric has a
zero noise floor).
"""

from __future__ import annotations

import numpy as np

from .label_dataset_splits import GateDataset


def expected_calibration_error(p: np.ndarray, y: np.ndarray,
                               n_bins: int = 15) -> float:
    edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        if m.sum() == 0:
            continue
        ece += (m.mean()) * abs(p[m].mean() - y[m].mean())
    return float(ece)


def reliability_curve(p: np.ndarray, y: np.ndarray, n_bins: int = 15) -> list[dict]:
    edges = np.linspace(0, 1, n_bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        if m.sum() == 0:
            continue
        out.append({"bin_lo": float(lo), "bin_hi": float(hi),
                    "mean_pred": float(p[m].mean()),
                    "empirical": float(y[m].mean()), "count": int(m.sum())})
    return out


def auc_score(p: np.ndarray, y: np.ndarray) -> float:
    """Rank-based ROC AUC (no sklearn dependency)."""
    order = np.argsort(p)
    ranks = np.empty(len(p)); ranks[order] = np.arange(len(p))
    pos = ranks[y == 1]
    n_pos, n_neg = int((y == 1).sum()), int((y == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return 0.5
    return float((pos.sum() - n_pos * (n_pos - 1) / 2) / (n_pos * n_neg))


def average_precision(p: np.ndarray, y: np.ndarray) -> float:
    order = np.argsort(-p)
    y_sorted = y[order]
    cum_tp = np.cumsum(y_sorted)
    precision_at_k = cum_tp / (np.arange(len(y_sorted)) + 1)
    n_pos = max(int(y.sum()), 1)
    return float((precision_at_k * y_sorted).sum() / n_pos)


def precision_recall(p: np.ndarray, y: np.ndarray, threshold: float) -> dict:
    pred = p >= threshold
    tp = int((pred & (y == 1)).sum())
    return {
        "threshold": float(threshold),
        "precision": tp / max(int(pred.sum()), 1),
        "recall": tp / max(int((y == 1).sum()), 1),
        "expand_rate": float(pred.mean()),
    }


def end_to_end_lost_fact(ds: GateDataset, idx: np.ndarray,
                         expand: np.ndarray) -> dict:
    """Silent-loss and answer-accuracy bookkeeping over rows idx, given a
    boolean expand decision per row. Evicted-span rows are the pointwise
    population that pairs against M1's baselines."""
    ev = ds.evicted[idx] == 1
    silent = (~expand) & (ds.compact_correct[idx] == 0)
    answered_correct = np.where(expand, ds.raw_correct[idx],
                                ds.compact_correct[idx])
    prior = ds.raw_correct[idx] == 1
    return {
        "n_rows": int(len(idx)),
        "n_evicted_rows": int(ev.sum()),
        "expand_rate_all": float(expand.mean()),
        "expand_rate_evicted": float(expand[ev].mean()) if ev.any() else 0.0,
        "lost_fact_rate_evicted": float(silent[ev].mean()) if ev.any() else 0.0,
        "lost_fact_rate_evicted_prior_correct":
            float(silent[ev & prior].mean()) if (ev & prior).any() else 0.0,
        "answer_accuracy_evicted":
            float(answered_correct[ev].mean()) if ev.any() else 0.0,
    }


def baseline_decisions(ds: GateDataset, idx: np.ndarray,
                       aux_p: np.ndarray | None = None,
                       aux_threshold: float = 0.5) -> dict[str, np.ndarray]:
    n = len(idx)
    out = {
        "never_expand": np.zeros(n, dtype=bool),
        "always_expand": np.ones(n, dtype=bool),
        "oracle_expand": ds.y[idx] == 1,
    }
    if aux_p is not None:
        out["classify_and_expand"] = aux_p >= aux_threshold
    return out


def threshold_sweep(ds: GateDataset, idx: np.ndarray, p: np.ndarray,
                    n_points: int = 41) -> list[dict]:
    """Cost/correctness plane: (expand_rate, lost_fact) across thresholds."""
    qs = np.unique(np.quantile(p, np.linspace(0, 1, n_points)))
    out = []
    for tau in qs:
        e2e = end_to_end_lost_fact(ds, idx, p >= tau)
        out.append({"threshold": float(tau), **e2e,
                    **{k: v for k, v in precision_recall(p, ds.y[idx], tau).items()
                       if k in ("precision", "recall")}})
    return out


def operating_point(sweep: list[dict], *, target_lost: float,
                    max_expand_rate: float) -> dict:
    """Choose the cheapest threshold meeting the lost-fact target within the
    expand budget (GT9); if unreachable, return the frontier point with the
    lowest conditioned loss inside the budget — honesty over tuning."""
    feasible = [s for s in sweep
                if s["lost_fact_rate_evicted_prior_correct"] <= target_lost
                and s["expand_rate_all"] <= max_expand_rate]
    if feasible:
        best = min(feasible, key=lambda s: s["expand_rate_all"])
        return {**best, "gt9_feasible": True}
    in_budget = [s for s in sweep if s["expand_rate_all"] <= max_expand_rate]
    best = min(in_budget or sweep,
               key=lambda s: s["lost_fact_rate_evicted_prior_correct"])
    return {**best, "gt9_feasible": False}
