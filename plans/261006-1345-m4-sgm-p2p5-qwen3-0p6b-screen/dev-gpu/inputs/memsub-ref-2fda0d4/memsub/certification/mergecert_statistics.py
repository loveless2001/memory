"""Leakage-resistant statistics shared by MergeCert remote/local analyses."""

from __future__ import annotations

import hashlib

import numpy as np


def tie_aware_auc(y_true, scores) -> float:
    """ROC AUC from average ranks, including exact score ties."""
    y = np.asarray(y_true, dtype=int)
    values = np.asarray(scores, dtype=float)
    if y.shape != values.shape or y.ndim != 1:
        raise ValueError("AUC labels and scores must be aligned 1D arrays")
    if not np.isfinite(values).all():
        raise ValueError("AUC scores must be finite")
    positive = y == 1
    n_positive = int(positive.sum())
    n_negative = int((y == 0).sum())
    if n_positive == 0 or n_negative == 0:
        raise ValueError("AUC requires both label classes")
    order = np.argsort(values, kind="mergesort")
    sorted_values = values[order]
    sorted_ranks = np.empty(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and sorted_values[end] == sorted_values[start]:
            end += 1
        sorted_ranks[start:end] = (start + 1 + end) / 2
        start = end
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = sorted_ranks
    return float(
        (
            ranks[positive].sum()
            - n_positive * (n_positive + 1) / 2
        )
        / (n_positive * n_negative)
    )


def _document_bucket(doc_id: str) -> float:
    value = int(hashlib.sha256(doc_id.encode()).hexdigest()[:8], 16)
    return value / 0xFFFFFFFF


def document_split(
    doc_ids, *, train_end: float = 0.6, validation_end: float = 0.7
) -> np.ndarray:
    """Return 0/1/2 train/validation/test labels grouped by document."""
    if not 0 < train_end < validation_end < 1:
        raise ValueError("document split boundaries must be ordered in (0, 1)")
    buckets = np.asarray(
        [_document_bucket(str(doc_id)) for doc_id in doc_ids], dtype=float
    )
    return np.where(
        buckets < train_end,
        0,
        np.where(buckets < validation_end, 1, 2),
    ).astype(np.int8)


def standardize_train_only(values, train_mask):
    """Standardize with moments estimated exclusively from training rows."""
    matrix = np.asarray(values, dtype=float)
    train = np.asarray(train_mask, dtype=bool)
    if matrix.ndim != 2 or train.shape != (len(matrix),) or not train.any():
        raise ValueError("standardization needs a 2D matrix and training rows")
    if not np.isfinite(matrix).all():
        raise ValueError("standardization inputs must be finite")
    mean = matrix[train].mean(axis=0)
    scale = matrix[train].std(axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    return (matrix - mean) / scale, mean, scale


def cluster_bootstrap_auc(
    y_true,
    scores,
    document_ids,
    *,
    seed: int,
    n_resamples: int = 2_000,
) -> dict:
    """Document-cluster bootstrap interval for a fixed score vector."""
    y = np.asarray(y_true, dtype=int)
    values = np.asarray(scores, dtype=float)
    groups = np.asarray(document_ids).astype(str)
    if y.shape != values.shape or y.shape != groups.shape:
        raise ValueError("bootstrap labels, scores, and documents must align")
    documents = np.unique(groups)
    if len(documents) < 2:
        raise ValueError("cluster bootstrap requires at least two documents")
    _, document_inverse = np.unique(groups, return_inverse=True)
    _, score_inverse = np.unique(values, return_inverse=True)
    score_groups = int(score_inverse.max()) + 1
    rng = np.random.default_rng(seed)
    bootstraps = []
    for _ in range(n_resamples):
        selected = rng.integers(0, len(documents), size=len(documents))
        document_weights = np.bincount(
            selected, minlength=len(documents)
        )
        row_weights = document_weights[document_inverse]
        positive_by_score = np.bincount(
            score_inverse,
            weights=row_weights * (y == 1),
            minlength=score_groups,
        )
        negative_by_score = np.bincount(
            score_inverse,
            weights=row_weights * (y == 0),
            minlength=score_groups,
        )
        n_positive = positive_by_score.sum()
        n_negative = negative_by_score.sum()
        if n_positive == 0 or n_negative == 0:
            continue
        negative_before = np.cumsum(negative_by_score) - negative_by_score
        favorable_pairs = np.sum(
            positive_by_score
            * (negative_before + 0.5 * negative_by_score)
        )
        bootstraps.append(float(favorable_pairs / (n_positive * n_negative)))
    if not bootstraps:
        raise ValueError("no valid two-class cluster bootstrap resamples")
    low, high = np.percentile(bootstraps, [2.5, 97.5])
    return {
        "auc": tie_aware_auc(y, values),
        "ci95": [float(low), float(high)],
        "n_items": int(len(y)),
        "n_documents": int(len(documents)),
        "positive_rate": float(y.mean()),
        "n_resamples": int(len(bootstraps)),
    }


def cohen_kappa(first, second) -> dict:
    """Binary Cohen's kappa with both marginal base rates reported."""
    a = np.asarray(first, dtype=int)
    b = np.asarray(second, dtype=int)
    if a.shape != b.shape or a.ndim != 1 or not len(a):
        raise ValueError("kappa inputs must be aligned nonempty 1D arrays")
    if not np.isin(a, (0, 1)).all() or not np.isin(b, (0, 1)).all():
        raise ValueError("kappa inputs must be binary")
    first_rate = float(a.mean())
    second_rate = float(b.mean())
    observed = float((a == b).mean())
    expected = (
        first_rate * second_rate
        + (1 - first_rate) * (1 - second_rate)
    )
    if expected < 1:
        kappa = (observed - expected) / (1 - expected)
    else:
        kappa = 1.0 if observed == 1 else 0.0
    return {
        "n": int(len(a)),
        "kappa": float(kappa),
        "raw_agreement": observed,
        "expected_agreement": float(expected),
        "first_positive_rate": first_rate,
        "second_positive_rate": second_rate,
    }


def directional_failure_nesting(merge_failures, reference_failures) -> dict:
    """Fraction of merge failures contained in a reference failure set."""
    merge = np.asarray(merge_failures, dtype=int)
    reference = np.asarray(reference_failures, dtype=int)
    if merge.shape != reference.shape or merge.ndim != 1 or not len(merge):
        raise ValueError("nesting inputs must be aligned nonempty 1D arrays")
    if not np.isin(merge, (0, 1)).all() or not np.isin(
        reference, (0, 1)
    ).all():
        raise ValueError("nesting inputs must be binary")
    denominator = int(merge.sum())
    if denominator == 0:
        raise ValueError("directional nesting requires at least one merge failure")
    intersection = int(((merge == 1) & (reference == 1)).sum())
    return {
        "n": int(len(merge)),
        "merge_failure_rate": float(merge.mean()),
        "reference_failure_rate": float(reference.mean()),
        "merge_failure_denominator": denominator,
        "intersection": intersection,
        "novel_merge_failures": denominator - intersection,
        "nesting_fraction": intersection / denominator,
    }
