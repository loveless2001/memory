"""Independent Q1 matched-budget analysis over copied per-document evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from memsub.certification.experiment_protocol import paired_metric_cis


HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "q1-certification.json"
DEFAULT_OUTPUT = HERE / "q1-verdict.json"
DEFAULT_TABLE = HERE / "q1-table.md"
DOMAINS = ("financial", "legal", "code", "literature")
RATIOS = (0.25, 0.40, 0.90)
EXPECTED_ARMS = {
    "control-0.00",
    *(f"eviction-{ratio:.2f}" for ratio in RATIOS),
    *(f"merge-{ratio:.2f}" for ratio in RATIOS),
}
EXPECTED_REFERENCES = {
    "frozen_subsample": {
        "mean_kl": 0.2566,
        "accuracy_delta": 0.063,
        "lost_prior": 0.188,
    },
    "unfrozen_compactor": {
        "mean_kl": 0.1385,
        "accuracy_delta": 0.042,
        "lost_prior": 0.083,
    },
}
EXPECTED_REFERENCE_SOURCES = {
    "frozen_subsample": {
        "path": "plans/260719-0318-fullrecipe-campaign/plan.md",
        "sha256": "5017c76fa4715eb4f883ae1e2bd7cb26bbe0518aac9dfe2a53cff7ccdfb85dce",
    },
    "unfrozen_compactor": {
        "path": (
            "plans/260719-2328-e1full-unfrozen-full-recipe/"
            "summary-e1full-clean-v1-n60.json"
        ),
        "sha256": "a7636b54148e7133237af68bf63fbc23811d5ce80417f8447711a89a559dc2a8",
    },
}


def _expected_budget(ratio: float) -> int:
    return 4096 - int(4096 * ratio)


def _partition(report: dict) -> tuple:
    source_hashes = report.get("source_hashes", {})
    return (
        report["doc_id"],
        report["domain"],
        report["context_sha256"],
        report["context_token_count"],
        tuple(report["needle_item_ids"]),
        tuple(report["aggregation_item_ids"]),
        source_hashes.get("corpus_manifest_sha256"),
        source_hashes.get("all_items_sha256"),
        source_hashes.get("source_document_sha256"),
    )


def _summary(reports: list[dict]) -> dict:
    return {
        "documents": len(reports),
        "aggregation_probes": sum(
            row["aggregation_axis"]["probe_count"] for row in reports
        ),
        "needle_probes": sum(
            row["pointwise_axis"]["needle_probe_count"] for row in reports
        ),
        "mean_kl": float(
            np.mean([row["aggregation_axis"]["mean_kl"] for row in reports])
        ),
        "accuracy_delta": float(
            np.mean(
                [row["aggregation_axis"]["accuracy_delta"] for row in reports]
            )
        ),
        "lost_fact": float(
            np.mean(
                [
                    row["pointwise_axis"]["lost_fact_incident_rate"]
                    for row in reports
                ]
            )
        ),
        "lost_prior": float(
            np.mean(
                [
                    row["pointwise_axis"][
                        "lost_fact_rate_given_prior_correct"
                    ]
                    for row in reports
                ]
            )
        ),
    }


def _format_ci(interval: dict) -> str:
    low, high = interval["ci95"]
    return f"{interval['mean_diff']:+.4f} [{low:+.4f}, {high:+.4f}]"


def _markdown(
    summaries: dict,
    intervals: dict,
    references: dict,
) -> str:
    lines = [
        "| arm (matched budget) | agg KL | agg accDelta | "
        "pointwise lost|prior | merge - eviction 95% CIs |",
        "|---|---:|---:|---:|---|",
    ]
    for label, key in (
        ("eviction 0.25 (existing row)", "eviction-0.25"),
        ("eviction 0.40 (existing row)", "eviction-0.40"),
        ("eviction 0.90 (new comparator)", "eviction-0.90"),
    ):
        row = summaries[key]
        lines.append(
            f"| {label} | {row['mean_kl']:.4f} | "
            f"{row['accuracy_delta']:+.3f} | {row['lost_prior']:.3f} | - |"
        )
    for label, key in (
        ("frozen subsample (reference)", "frozen_subsample"),
        ("unfrozen compactor (reference)", "unfrozen_compactor"),
    ):
        row = references[key]
        lines.append(
            f"| {label} | {row['mean_kl']:.4f} | "
            f"{row['accuracy_delta']:+.3f} | {row['lost_prior']:.3f} | - |"
        )
    for ratio in RATIOS:
        key = f"merge-{ratio:.2f}"
        row = summaries[key]
        ci = intervals[f"{ratio:.2f}"]
        ci_text = "; ".join(
            (
                f"KL {_format_ci(ci['mean_kl'])}",
                f"accDelta {_format_ci(ci['acc_delta'])}",
                f"lost|prior {_format_ci(ci['lost_prior'])}",
            )
        )
        lines.append(
            f"| MERGE {ratio:.2f} | {row['mean_kl']:.4f} | "
            f"{row['accuracy_delta']:+.3f} | {row['lost_prior']:.3f} | "
            f"{ci_text} |"
        )
    control = summaries["control-0.00"]
    lines.append(
        f"| zero-compression control | {control['mean_kl']:.4f} | "
        f"{control['accuracy_delta']:+.3f} | {control['lost_prior']:.3f} | - |"
    )
    return "\n".join(lines) + "\n"


def analyze(payload, *, expected_documents=20, n_resamples=20_000):
    provenance = payload.get("provenance", {})
    if provenance.get("model_id") != "Qwen/Qwen3-4B-Instruct-2507":
        raise ValueError("Q1 model provenance mismatch")
    if provenance.get("ratios") != list(RATIOS):
        raise ValueError("Q1 ratio provenance mismatch")
    if provenance.get("sink_token_count") != 4:
        raise ValueError("Q1 sink provenance mismatch")

    gate = payload.get("q1_gate", {})
    if gate.get("p0_pass") is not True or not gate.get("p0_verdict_sha256"):
        raise ValueError("Q1 cannot be analyzed without a passing P0 gate")

    archived = payload.get("archived_m1", {})
    if archived.get("replay_pass") is not True:
        raise ValueError("archived M1 replay did not pass")
    expected_archive_files = {
        f"{domain}-evict{ratio:.2f}.json"
        for domain in DOMAINS
        for ratio in (0.0, 0.25, 0.40)
    }
    archive_files = archived.get("files", {})
    if set(archive_files) != expected_archive_files or any(
        not row.get("sha256") for row in archive_files.values()
    ):
        raise ValueError("archived M1 file hashes are incomplete")
    replay_checks = archived.get("replay_checks", [])
    if len(replay_checks) != expected_documents * 3 or any(
        check.get("pass") is not True or check.get("mismatches")
        for check in replay_checks
    ):
        raise ValueError("archived M1 replay checks are incomplete or failed")

    references = payload.get("references")
    if references != EXPECTED_REFERENCES:
        raise ValueError("Q1 reference rows differ from the registered values")
    if payload.get("reference_sources") != EXPECTED_REFERENCE_SOURCES:
        raise ValueError("Q1 reference source hashes differ from registration")

    source_hashes = payload.get("source_hashes", {})
    if not source_hashes.get("corpus_manifest_sha256") or not source_hashes.get(
        "all_items_sha256"
    ):
        raise ValueError("Q1 top-level source hashes are incomplete")

    documents = payload.get("documents", [])
    if (
        len(documents) != expected_documents
        or payload.get("done_documents") != expected_documents
    ):
        raise ValueError(
            f"Q1 requires {expected_documents} completed documents"
        )
    doc_ids = [row["doc_id"] for row in documents]
    if len(set(doc_ids)) != expected_documents:
        raise ValueError("Q1 document IDs must be unique")
    expected_per_domain = expected_documents // len(DOMAINS)
    domains = Counter(row["domain"] for row in documents)
    if domains != Counter(
        {domain: expected_per_domain for domain in DOMAINS}
    ):
        raise ValueError(f"Q1 domain balance mismatch: {dict(domains)}")
    for document in documents:
        hashes = document.get("source_hashes", {})
        if (
            hashes.get("corpus_manifest_sha256")
            != source_hashes["corpus_manifest_sha256"]
            or hashes.get("all_items_sha256")
            != source_hashes["all_items_sha256"]
            or not hashes.get("source_document_sha256")
        ):
            raise ValueError("Q1 document source hashes are incomplete")
    registered_partitions = [_partition(row) for row in documents]

    arms = payload.get("arms", {})
    if set(arms) != EXPECTED_ARMS:
        raise ValueError("Q1 artifact does not contain every registered arm")
    for arm_name, arm in arms.items():
        ratio = float(arm["ratio"])
        expected_budget = _expected_budget(ratio)
        if arm.get("target_retained") != expected_budget:
            raise ValueError(f"{arm_name} arm budget mismatch")
        reports = arm.get("reports", [])
        if len(reports) != expected_documents:
            raise ValueError(f"{arm_name} report count mismatch")
        if any(
            report.get("source_hashes") != document.get("source_hashes")
            for report, document in zip(reports, documents)
        ):
            raise ValueError(f"{arm_name} source hash provenance is incomplete")
        if [_partition(row) for row in reports] != registered_partitions:
            raise ValueError(f"{arm_name} item/context partition drift")
        if any(row.get("target_retained") != expected_budget for row in reports):
            raise ValueError(f"{arm_name} per-report budget mismatch")

    control = arms["control-0.00"]["reports"]
    if any(
        row["aggregation_axis"]["mean_kl"] != 0
        or row["aggregation_axis"]["accuracy_delta"] != 0
        or row["pointwise_axis"]["lost_fact_rate_given_prior_correct"] != 0
        for row in control
    ):
        raise ValueError("zero-compression control is not exactly zero")

    reports_by_arm = {
        arm_name: arm["reports"] for arm_name, arm in arms.items()
    }
    summaries = {
        arm_name: _summary(reports)
        for arm_name, reports in reports_by_arm.items()
    }
    intervals = {}
    for ratio_index, ratio in enumerate(RATIOS):
        eviction = f"eviction-{ratio:.2f}"
        merge = f"merge-{ratio:.2f}"
        intervals[f"{ratio:.2f}"] = paired_metric_cis(
            {eviction: reports_by_arm[eviction], merge: reports_by_arm[merge]},
            reference_arm=eviction,
            candidate_arms=(merge,),
            seed=20260727 + ratio_index * 10,
            n_resamples=n_resamples,
        )[merge]

    return {
        "pass": True,
        "documents": expected_documents,
        "domain_counts": dict(sorted(domains.items())),
        "archived_m1_replay_pass": True,
        "summaries": summaries,
        "references": references,
        "paired_merge_minus_eviction": intervals,
        "markdown_table": _markdown(summaries, intervals, references),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    args = parser.parse_args()
    with args.input.open() as handle:
        payload = json.load(handle)
    verdict = analyze(payload)
    with args.output.open("w") as handle:
        json.dump(verdict, handle, indent=1, allow_nan=False)
    args.table.write_text(verdict["markdown_table"])
    print(json.dumps(verdict, indent=1))


if __name__ == "__main__":
    main()
