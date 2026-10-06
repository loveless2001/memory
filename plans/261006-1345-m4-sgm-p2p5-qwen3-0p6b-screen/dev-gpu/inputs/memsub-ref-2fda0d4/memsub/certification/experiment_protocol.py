"""Pure helpers for leakage-free, reproducible certification experiments."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


def canonical_sha256(value: Any) -> str:
    """Hash JSON-compatible data with stable ordering and strict numbers."""
    blob = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def select_holdout_documents(
    items: Sequence[Mapping[str, Any]],
    document_lengths: Mapping[str, int],
    *,
    domains: Sequence[str],
    docs_per_domain: int,
    context_tokens: int = 4096,
    recent_raw: int = 1024,
    item_span_tokens: int = 1024,
    anchor_lookback: int = 512,
    max_items_per_axis: int = 8,
) -> list[dict[str, Any]]:
    """Select a balanced deterministic holdout matching certification use."""
    by_doc: dict[str, list[Mapping[str, Any]]] = {}
    for item in items:
        by_doc.setdefault(str(item["doc_id"]), []).append(item)

    selected: list[dict[str, Any]] = []
    for domain in domains:
        eligible: list[dict[str, Any]] = []
        for doc_id in sorted(d for d in by_doc if d.startswith(f"{domain}/")):
            doc_items = sorted(
                by_doc[doc_id],
                key=lambda item: (int(item["chunk_token_start"]),
                                  str(item["item_id"])),
            )
            doc_len = int(document_lengths.get(doc_id, 0))
            if not doc_items or doc_len < context_tokens:
                continue
            anchor = doc_items[0]
            ctx_start = max(
                0,
                min(int(anchor["chunk_token_start"]) - anchor_lookback,
                    doc_len - context_tokens),
            )
            needle_limit = context_tokens - recent_raw - item_span_tokens
            needles = [
                item for item in doc_items
                if 4 <= int(item["chunk_token_start"]) - ctx_start < needle_limit
            ][:max_items_per_axis]
            needle_ids = {str(item["item_id"]) for item in needles}
            aggregations = [
                item for item in doc_items
                if str(item["item_id"]) not in needle_ids
            ][:max_items_per_axis]
            if not needles or not aggregations:
                continue
            eligible.append({
                "doc_id": doc_id,
                "domain": domain,
                "ctx_start": ctx_start,
                "needle_item_ids": [str(item["item_id"]) for item in needles],
                "aggregation_item_ids": [
                    str(item["item_id"]) for item in aggregations
                ],
            })

        if len(eligible) < docs_per_domain:
            raise ValueError(
                f"{domain}: needed {docs_per_domain} eligible documents, "
                f"found {len(eligible)}"
            )
        selected.extend(eligible[:docs_per_domain])
    return selected


def assert_train_eval_disjoint(
    training_rows: Sequence[Mapping[str, Any]],
    certification_documents: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return overlap provenance or raise before a contaminated evaluation."""
    train_docs = {str(row["doc_id"]) for row in training_rows}
    train_items = {str(row["item_id"]) for row in training_rows}
    cert_docs = {str(row["doc_id"]) for row in certification_documents}
    cert_items = {
        str(item_id)
        for row in certification_documents
        for key in ("needle_item_ids", "aggregation_item_ids")
        for item_id in row[key]
    }
    doc_overlap = sorted(train_docs & cert_docs)
    item_overlap = sorted(train_items & cert_items)
    if doc_overlap:
        raise ValueError(
            f"training/certification document overlap: {doc_overlap[:10]}"
        )
    if item_overlap:
        raise ValueError(
            f"training/certification item overlap: {item_overlap[:10]}"
        )
    return {
        "training_documents": len(train_docs),
        "training_items": len(train_items),
        "certification_documents": len(cert_docs),
        "certification_items": len(cert_items),
        "document_overlap": doc_overlap,
        "item_overlap": item_overlap,
    }


def build_training_manifest(
    items: Sequence[Mapping[str, Any]],
    *,
    traced_ids: set[str],
    holdout_doc_ids: set[str],
    domains: Sequence[str],
    domain_cap: int,
    balance_to_smallest: bool = False,
) -> dict[str, Any]:
    """Build a balanced training manifest after whole-document exclusion."""
    by_domain: dict[str, list[Mapping[str, Any]]] = {
        domain: [] for domain in domains
    }
    excluded_traced: set[str] = set()
    heldout_counts = {domain: 0 for domain in domains}
    raw_counts = {domain: 0 for domain in domains}
    seen_training_ids: set[str] = set()
    duplicate_item_ids: set[str] = set()
    for item in items:
        doc_id = str(item["doc_id"])
        item_id = str(item["item_id"])
        domain = doc_id.split("/", 1)[0]
        if domain not in by_domain:
            continue
        raw_counts[domain] += 1
        if doc_id in holdout_doc_ids:
            heldout_counts[domain] += 1
            if item_id in traced_ids:
                excluded_traced.add(item_id)
            continue
        if item_id in seen_training_ids:
            duplicate_item_ids.add(item_id)
            continue
        seen_training_ids.add(item_id)
        by_domain[domain].append(item)

    manifest: list[dict[str, Any]] = []
    remainder: list[str] = []
    counts: dict[str, dict[str, int]] = {}
    effective_cap = domain_cap
    if balance_to_smallest:
        effective_cap = min(
            domain_cap, *(len(by_domain[domain]) for domain in domains)
        )
    for domain in domains:
        rows = sorted(
            by_domain[domain],
            key=lambda item: (str(item["doc_id"]), str(item["item_id"])),
        )
        selected = rows[:effective_cap]
        counts[domain] = {
            "corpus": raw_counts[domain],
            "available_after_holdout": len(rows),
            "heldout_excluded": heldout_counts[domain],
            "selected": len(selected),
            "traced": sum(
                str(item["item_id"]) in traced_ids for item in selected
            ),
        }
        for item in selected:
            item_id = str(item["item_id"])
            has_trace = item_id in traced_ids
            manifest.append({
                "item_id": item_id,
                "doc_id": str(item["doc_id"]),
                "domain": domain,
                "has_trace": has_trace,
            })
            if not has_trace:
                remainder.append(item_id)

    selected_ids = {row["item_id"] for row in manifest}
    orphan_traced = traced_ids - selected_ids - excluded_traced
    return {
        "items": manifest,
        "remainder_item_ids": remainder,
        "counts": counts,
        "excluded_traced_item_ids": sorted(excluded_traced),
        "orphan_traced_item_ids": sorted(orphan_traced),
        "effective_domain_cap": effective_cap,
        "duplicate_item_ids": sorted(duplicate_item_ids),
    }
def paired_bootstrap_ci(
    reference: Sequence[float],
    candidate: Sequence[float],
    *,
    seed: int = 0,
    n_resamples: int = 20_000,
    higher_is_better: bool = False,
) -> dict[str, Any]:
    """Bootstrap paired candidate-minus-reference document differences."""
    import numpy as np

    if len(reference) != len(candidate):
        raise ValueError("paired inputs must have the same length")
    if len(reference) < 2:
        raise ValueError("paired inputs require at least two documents")
    diff = np.asarray(candidate, dtype=float) - np.asarray(reference, dtype=float)
    if not np.isfinite(diff).all():
        raise ValueError("paired inputs must contain only finite values")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(diff), size=(n_resamples, len(diff)))
    boots = diff[indices].mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {
        "n": int(len(diff)),
        "mean_diff": float(diff.mean()),
        "ci95": [float(lo), float(hi)],
        "excludes_zero": bool(lo > 0 or hi < 0),
        "documents_favoring_candidate": int(
            (diff > 0).sum() if higher_is_better else (diff < 0).sum()),
    }


_CERTIFICATION_METRICS = {
    "mean_kl": ("aggregation_axis", "mean_kl"),
    "acc_delta": ("aggregation_axis", "accuracy_delta"),
    "lost_fact": ("pointwise_axis", "lost_fact_incident_rate"),
    "lost_prior": (
        "pointwise_axis", "lost_fact_rate_given_prior_correct"
    ),
}


def paired_metric_cis(
    results: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    reference_arm: str,
    candidate_arms: Sequence[str],
    seed: int = 0,
    n_resamples: int = 20_000,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Compute the complete registered paired metric set for each arm."""
    output: dict[str, dict[str, dict[str, Any]]] = {}
    for arm_index, arm in enumerate(candidate_arms):
        output[arm] = {}
        for metric_index, (name, (axis, key)) in enumerate(
                _CERTIFICATION_METRICS.items()):
            reference = [float(row[axis][key])
                         for row in results[reference_arm]]
            candidate = [float(row[axis][key]) for row in results[arm]]
            output[arm][name] = paired_bootstrap_ci(
                reference, candidate,
                seed=seed + arm_index * len(_CERTIFICATION_METRICS)
                + metric_index,
                n_resamples=n_resamples,
                higher_is_better=name == "acc_delta",
            )
    return output


def max_contiguous_certified_depth(
    depth_passes: Sequence[tuple[int, bool]],
) -> int:
    """Return the deepest registered arm before the first failed depth."""
    max_depth = 0
    previous = 0
    for depth, passed in depth_passes:
        if depth <= previous:
            raise ValueError("certification depths must be strictly increasing")
        previous = depth
        if not passed:
            break
        max_depth = depth
    return max_depth
