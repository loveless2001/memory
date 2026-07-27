"""Independent P0.3/P0.4 verdict from the copied per-item artifact."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "p0-direction-200.json"
DEFAULT_OUTPUT = HERE / "p0-verdict.json"
DOMAINS = ("financial", "legal", "code", "literature")
REGISTERED_BUDGETS = {"0.25": 3072, "0.40": 2458, "0.90": 410}


def analyze_smoke(
    payload,
    *,
    expected_items=8,
    max_gpu_bytes=80 * 1024**3,
):
    rows = payload.get("rows", [])
    if payload.get("done") != expected_items or len(rows) != expected_items:
        raise ValueError(
            f"P0 smoke must contain {expected_items} completed rows"
        )
    item_ids = [row["item_id"] for row in rows]
    if (
        len(set(item_ids)) != expected_items
        or payload.get("sample_item_ids") != item_ids
    ):
        raise ValueError("P0 smoke item IDs differ from the registered sample")
    budget_audit = payload.get("budget_audit", {})
    if set(budget_audit) != set(REGISTERED_BUDGETS):
        raise ValueError("P0 smoke runtime budget audit is incomplete")
    for ratio, expected in REGISTERED_BUDGETS.items():
        row = budget_audit[ratio]
        if (
            row.get("target_retained") != expected
            or row.get("physical_length") != expected
            or row.get("kv_finite") is not True
        ):
            raise ValueError(f"P0 {ratio} runtime budget audit failed")
    finite_outputs = all(
        math.isfinite(float(row[key]))
        for row in rows
        for key in (
            "merge_kl",
            "eviction_kl",
            "streaming_kl",
            "attention_mass_min",
            "attention_mass_max",
            "attention_mass_variance",
        )
    )
    if (
        not finite_outputs
        or any(row["attention_mass_min"] < 0 for row in rows)
        or any(row["attention_mass_variance"] <= 0 for row in rows)
    ):
        raise ValueError("P0 smoke real-attention/output validity failed")
    peak_gpu_bytes = int(payload.get("peak_gpu_bytes", -1))
    if not 0 < peak_gpu_bytes < max_gpu_bytes:
        raise ValueError("P0 smoke peak GPU allocation exceeds the H100 limit")
    structure = payload.get("structure", {})
    if (
        structure.get("target_retained") != REGISTERED_BUDGETS["0.90"]
        or structure.get("non_singleton_blocks", 0) <= 0
        or structure.get("exact_slot_jaccard", 1) >= 1
        or structure.get("cache_tensor_identical") is not False
    ):
        raise ValueError("P0 smoke non-degeneracy audit failed")
    return {
        "pass": True,
        "items": expected_items,
        "retained_vectors": {
            ratio: budget_audit[ratio]["physical_length"]
            for ratio in REGISTERED_BUDGETS
        },
        "minimum_attention_variance": min(
            row["attention_mass_variance"] for row in rows
        ),
        "peak_gpu_bytes": peak_gpu_bytes,
    }


def _cluster_paired_ci(rows, difference, *, seed=20260727, n_resamples=20_000):
    by_document = {}
    for row in rows:
        by_document.setdefault(row["doc_id"], []).append(float(difference(row)))
    documents = sorted(by_document)
    if len(documents) < 2:
        raise ValueError("paired cluster interval requires at least two documents")
    rng = np.random.default_rng(seed)
    bootstrap_means = []
    for _ in range(n_resamples):
        chosen = rng.integers(0, len(documents), size=len(documents))
        values = [
            value
            for document_index in chosen
            for value in by_document[documents[document_index]]
        ]
        bootstrap_means.append(float(np.mean(values)))
    differences = [float(difference(row)) for row in rows]
    low, high = np.percentile(bootstrap_means, [2.5, 97.5])
    return {
        "n_items": len(rows),
        "n_documents": len(documents),
        "mean_diff": float(np.mean(differences)),
        "ci95": [float(low), float(high)],
        "excludes_zero": bool(low > 0 or high < 0),
    }


def analyze(payload, *, expected_items=200, n_resamples=20_000):
    rows = payload["rows"]
    if payload.get("done") != expected_items or len(rows) != expected_items:
        raise ValueError(
            f"P0 artifact must contain {expected_items} completed rows"
        )
    item_ids = [row["item_id"] for row in rows]
    if len(set(item_ids)) != expected_items:
        raise ValueError("P0 item IDs must be unique")
    if payload.get("sample_item_ids") != item_ids:
        raise ValueError("P0 row order differs from the registered sample")
    expected_per_domain = expected_items // len(DOMAINS)
    domain_counts = Counter(row["domain"] for row in rows)
    if domain_counts != Counter({domain: expected_per_domain for domain in DOMAINS}):
        raise ValueError(f"P0 domain balance mismatch: {dict(domain_counts)}")

    prior_rows = [row for row in rows if row["full_correct"]]
    if not prior_rows:
        raise ValueError("P0 has no full-context-prior-correct items")
    merge_lost = sum(row["merge_lost_prior_correct"] for row in prior_rows)
    eviction_lost = sum(
        row["eviction_lost_prior_correct"] for row in prior_rows
    )
    lost_ci = _cluster_paired_ci(
        prior_rows,
        lambda row: (
            row["merge_lost_prior_correct"]
            - row["eviction_lost_prior_correct"]
        ),
        n_resamples=n_resamples,
    )
    merge_lost_rate = merge_lost / len(prior_rows)
    eviction_lost_rate = eviction_lost / len(prior_rows)
    direction_pass = (
        merge_lost_rate < eviction_lost_rate and lost_ci["ci95"][1] < 0
    )

    structure = payload["structure"]
    degeneracy_pass = (
        structure["target_retained"] == 410
        and structure["non_singleton_blocks"] > 0
        and structure["exact_slot_jaccard"] < 1
        and not structure["cache_tensor_identical"]
        and structure["physical_max_abs_kv_difference"] > 0
        and structure["aligned_exact_max_abs_kv_difference"] == 0
    )
    finite_attention = all(
        math.isfinite(row[key])
        for row in rows
        for key in (
            "attention_mass_min",
            "attention_mass_max",
            "attention_mass_variance",
        )
    )
    attention_pass = (
        finite_attention
        and all(row["attention_mass_min"] >= 0 for row in rows)
        and all(row["attention_mass_variance"] > 0 for row in rows)
    )

    full_accuracy = float(np.mean([row["full_correct"] for row in rows]))
    merge_accuracy = float(np.mean([row["merge_correct"] for row in rows]))
    eviction_accuracy = float(
        np.mean([row["eviction_correct"] for row in rows])
    )
    accuracy_ci = _cluster_paired_ci(
        rows,
        lambda row: row["merge_correct"] - row["eviction_correct"],
        seed=20260728,
        n_resamples=n_resamples,
    )
    kl_ci = _cluster_paired_ci(
        rows,
        lambda row: row["merge_kl"] - row["eviction_kl"],
        seed=20260729,
        n_resamples=n_resamples,
    )
    sample_pass = len(rows) == expected_items and all(
        domain_counts[domain] == expected_per_domain for domain in DOMAINS
    )
    verdict = {
        "sample": {
            "n_items": len(rows),
            "n_documents": len({row["doc_id"] for row in rows}),
            "domain_counts": dict(sorted(domain_counts.items())),
            "prior_correct": len(prior_rows),
            "pass": sample_pass,
        },
        "p0_3": {
            "merge_lost_given_prior_correct": merge_lost_rate,
            "eviction_lost_given_prior_correct": eviction_lost_rate,
            "paired_merge_minus_eviction": lost_ci,
            "full_accuracy": full_accuracy,
            "merge_accuracy_delta": merge_accuracy - full_accuracy,
            "eviction_accuracy_delta": eviction_accuracy - full_accuracy,
            "paired_merge_minus_eviction_accuracy": accuracy_ci,
            "mean_merge_kl": float(np.mean([row["merge_kl"] for row in rows])),
            "mean_eviction_kl": float(
                np.mean([row["eviction_kl"] for row in rows])
            ),
            "paired_merge_minus_eviction_kl": kl_ci,
            "pass": direction_pass,
        },
        "p0_4": {
            **structure,
            "merge_streaming_prediction_equal_rate": float(
                np.mean(
                    [row["merge_streaming_prediction_equal"] for row in rows]
                )
            ),
            "pass": degeneracy_pass,
        },
        "real_attention": {
            "minimum": min(row["attention_mass_min"] for row in rows),
            "maximum": max(row["attention_mass_max"] for row in rows),
            "minimum_variance": min(
                row["attention_mass_variance"] for row in rows
            ),
            "pass": attention_pass,
        },
    }
    verdict["p0_pass"] = bool(
        sample_pass and direction_pass and degeneracy_pass and attention_pass
    )
    verdict["stop_q1_q3"] = not verdict["p0_pass"]
    return verdict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    with args.input.open() as handle:
        payload = json.load(handle)
    verdict = analyze(payload)
    with args.output.open("w") as handle:
        json.dump(verdict, handle, indent=1, allow_nan=False)
    print(json.dumps(verdict, indent=1))


if __name__ == "__main__":
    main()
