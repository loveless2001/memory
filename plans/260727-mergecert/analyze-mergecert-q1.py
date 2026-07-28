"""Independent Q1 matched-budget analysis over copied per-document evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from memsub.certification.experiment_protocol import paired_metric_cis


HERE = Path(__file__).resolve().parent
Q1_ARTIFACT_DIR = HERE.parent / "260728-mergecert-q1"
DEFAULT_INPUT = Q1_ARTIFACT_DIR / "q1-certification.json"
DEFAULT_OUTPUT = Q1_ARTIFACT_DIR / "q1-verdict.json"
DEFAULT_TABLE = Q1_ARTIFACT_DIR / "q1-table.md"
DOMAINS = ("financial", "legal", "code", "literature")
RATIOS = (0.25, 0.40)
BUDGET_MODE = "archived-m1-per-document-matched-physical-v1"
ADDENDUM_SHA256 = (
    "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509"
)
P0_VERDICT_SHA256 = (
    "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
)
EXPECTED_ARMS = {
    "control-0.00",
    *(f"eviction-{ratio:.2f}" for ratio in RATIOS),
    *(f"merge-{ratio:.2f}" for ratio in RATIOS),
}
SETTLED_P0 = {
    "p0_3_pass": False,
    "p0_4_pass": True,
    "real_attention_pass": True,
    "p0_pass": False,
    "stop_q1_q3": True,
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


def _expected_document_budget(
    source_context_token_count: int,
    model_input_token_count: int,
    ratio: float,
    *,
    evicted_token_count: int | None = None,
    eviction_source_start: int = 4,
    eviction_source_end: int | None = None,
    physical_before_count: int | None = None,
    physical_after_count: int | None = None,
) -> dict:
    requested_evicted = int(source_context_token_count * ratio)
    source_end = (
        eviction_source_start + requested_evicted
        if eviction_source_end is None
        else eviction_source_end
    )
    evicted = (
        requested_evicted
        if evicted_token_count is None
        else evicted_token_count
    )
    physical_before = (
        model_input_token_count
        if physical_before_count is None
        else physical_before_count
    )
    physical_after = (
        physical_before - evicted
        if physical_after_count is None
        else physical_after_count
    )
    retained = physical_after
    return {
        "source_context_token_count": source_context_token_count,
        "model_input_token_count": model_input_token_count,
        "requested_evicted_token_count": requested_evicted,
        "eviction_source_start": eviction_source_start,
        "eviction_source_end": source_end,
        "physical_before_count": physical_before,
        "physical_after_count": physical_after,
        "evicted_token_count": evicted,
        "retained_token_count": retained,
        "merge_target_retained": retained,
    }


def _is_strict_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _partition(report: dict) -> tuple:
    source_hashes = report.get("source_hashes", {})
    return (
        report["doc_id"],
        report["domain"],
        report["context_sha256"],
        report["source_context_token_count"],
        report["model_input_token_count"],
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


def per_domain_summaries(reports_by_arm: dict) -> dict:
    return {
        domain: {
            arm_name: _summary(
                [report for report in reports if report["domain"] == domain]
            )
            for arm_name, reports in sorted(reports_by_arm.items())
        }
        for domain in DOMAINS
    }


def classify_registered_readings(intervals: dict) -> dict:
    favorable = []
    pointwise = []
    aggregation = []
    for ratio in ("0.25", "0.40"):
        row = intervals[ratio]
        if row["lost_prior"]["ci95"][1] < 0:
            pointwise.append(f"{ratio}:lost_prior")
        if row["mean_kl"]["ci95"][1] < 0:
            aggregation.append(f"{ratio}:mean_kl")
        if row["acc_delta"]["ci95"][0] > 0:
            aggregation.append(f"{ratio}:acc_delta")
    favorable.extend(pointwise)
    favorable.extend(aggregation)
    return {
        "r1": "R1" if pointwise else "R2",
        "r3": "aggregation-positive"
        if aggregation
        else "aggregation-negative",
        "pointwise_favorable": pointwise,
        "aggregation_favorable": aggregation,
        "favorable_intervals": favorable,
        "run_q2_q3": bool(favorable),
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
    if provenance.get("budget_mode") != BUDGET_MODE:
        raise ValueError("Q1 budget provenance mismatch")

    authorization = payload.get("q1_authorization", {})
    if (
        authorization.get("protocol") != "MERGECERT-Q1"
        or authorization.get("budget_mode") != BUDGET_MODE
        or authorization.get("addendum_sha256") != ADDENDUM_SHA256
        or authorization.get("p0_verdict_sha256") != P0_VERDICT_SHA256
        or authorization.get("settled_p0") != SETTLED_P0
    ):
        raise ValueError("Q1 authorization does not match settled negative P0")

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
        or not _is_strict_int(payload.get("done_documents"))
        or payload["done_documents"] != expected_documents
    ):
        raise ValueError(
            f"Q1 requires {expected_documents} completed documents"
        )
    doc_ids = [row["doc_id"] for row in documents]
    if len(set(doc_ids)) != expected_documents:
        raise ValueError("Q1 document IDs must be unique")
    if payload.get("sample_doc_ids") != doc_ids:
        raise ValueError("Q1 sample document IDs differ from analyzed documents")
    expected_replay = {
        (
            doc_id,
            f"{doc_id.split('/', 1)[0]}-evict{ratio:.2f}.json",
        )
        for doc_id in doc_ids
        for ratio in (0.0, 0.25, 0.40)
    }
    actual_replay = [
        (check.get("doc_id"), check.get("archive"))
        for check in replay_checks
    ]
    if len(set(actual_replay)) != len(actual_replay) or set(
        actual_replay
    ) != expected_replay:
        raise ValueError("archived M1 replay matrix is not exact")
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
        source_tokens = document.get("source_context_token_count")
        model_tokens = document.get("model_input_token_count")
        if (
            not _is_strict_int(source_tokens)
            or source_tokens <= 4
            or not _is_strict_int(model_tokens)
            or model_tokens <= 4
            or document.get("context_token_count") != model_tokens
        ):
            raise ValueError("Q1 document token-length audit is invalid")
        budgets = document.get("budgets", {})
        if set(budgets) != {"0.25", "0.40"}:
            raise ValueError("Q1 document per-document budget audit mismatch")
        for ratio in RATIOS:
            ratio_text = f"{ratio:.2f}"
            actual_evicted = budgets[ratio_text].get(
                "evicted_token_count"
            )
            source_start = budgets[ratio_text].get(
                "eviction_source_start"
            )
            source_end = budgets[ratio_text].get("eviction_source_end")
            physical_before = budgets[ratio_text].get(
                "physical_before_count"
            )
            physical_after = budgets[ratio_text].get(
                "physical_after_count"
            )
            expected_removed = (
                max(
                    0,
                    min(source_end, physical_before)
                    - min(max(source_start, 0), physical_before),
                )
                if all(
                    _is_strict_int(value)
                    for value in (
                        source_start,
                        source_end,
                        physical_before,
                    )
                )
                else None
            )
            if (
                not all(
                    _is_strict_int(value)
                    for value in (
                        actual_evicted,
                        source_start,
                        source_end,
                        physical_before,
                        physical_after,
                    )
                )
                or actual_evicted <= 0
                or source_start < 4
                or source_end - source_start != int(source_tokens * ratio)
                or physical_before != model_tokens
                or physical_before - physical_after != actual_evicted
                or actual_evicted != expected_removed
                or physical_after <= 4
                or budgets[ratio_text]
                != _expected_document_budget(
                    source_tokens,
                    model_tokens,
                    ratio,
                    evicted_token_count=actual_evicted,
                    eviction_source_start=source_start,
                    eviction_source_end=source_end,
                    physical_before_count=physical_before,
                    physical_after_count=physical_after,
                )
            ):
                raise ValueError(
                    "Q1 document per-document budget audit mismatch"
                )
    registered_partitions = [_partition(row) for row in documents]

    arms = payload.get("arms", {})
    if set(arms) != EXPECTED_ARMS:
        raise ValueError("Q1 artifact does not contain exactly the registered arms")
    for arm_name, arm in arms.items():
        registered_ratio = float(arm_name.rsplit("-", 1)[1])
        if arm.get("ratio") != registered_ratio:
            raise ValueError(f"{arm_name} arm ratio mismatch")
        if arm.get("budget_mode") != BUDGET_MODE:
            raise ValueError(f"{arm_name} arm budget mode mismatch")
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
        for report, document in zip(reports, documents):
            ratio = registered_ratio
            if ratio == 0.0:
                expected_budget = {
                    "requested_evicted_token_count": 0,
                    "eviction_source_start": 0,
                    "eviction_source_end": 0,
                    "physical_before_count": document[
                        "model_input_token_count"
                    ],
                    "physical_after_count": document[
                        "model_input_token_count"
                    ],
                    "evicted_token_count": 0,
                    "retained_token_count": document[
                        "model_input_token_count"
                    ],
                }
            else:
                expected_budget = document["budgets"][f"{ratio:.2f}"]
            if (
                report.get("requested_evicted_token_count")
                != expected_budget["requested_evicted_token_count"]
                or report.get("eviction_source_start")
                != expected_budget["eviction_source_start"]
                or report.get("eviction_source_end")
                != expected_budget["eviction_source_end"]
                or report.get("physical_before_count")
                != expected_budget["physical_before_count"]
                or report.get("physical_after_count")
                != expected_budget["physical_after_count"]
                or report.get("evicted_token_count")
                != expected_budget["evicted_token_count"]
                or report.get("target_retained")
                != expected_budget["retained_token_count"]
            ):
                raise ValueError(
                    f"{arm_name} per-document budget mismatch for "
                    f"{document['doc_id']}"
                )

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
    domains_by_arm = per_domain_summaries(reports_by_arm)
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

    readings = classify_registered_readings(intervals)

    return {
        "pass": True,
        "budget_mode": BUDGET_MODE,
        "authorization": {
            "protocol": "MERGECERT-Q1",
            "budget_mode": BUDGET_MODE,
            "addendum_sha256": ADDENDUM_SHA256,
            "p0_verdict_sha256": P0_VERDICT_SHA256,
        },
        "documents": expected_documents,
        "sample_doc_ids": doc_ids,
        "archive_replay_matrix": [
            {"doc_id": doc_id, "archive": archive}
            for doc_id, archive in actual_replay
        ],
        "domain_counts": dict(sorted(domains.items())),
        "archived_m1_replay_pass": True,
        "summaries": summaries,
        "references": references,
        "paired_merge_minus_eviction": intervals,
        "registered_readings": readings,
        "per_domain": domains_by_arm,
        "per_document_budgets": {
            document["doc_id"]: document["budgets"]
            for document in documents
        },
        "run_q2_q3": readings["run_q2_q3"],
        "favorable_intervals": readings["favorable_intervals"],
        "markdown_table": _markdown(summaries, intervals, references),
    }


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--expected-documents", type=int, default=20)
    parser.add_argument("--n-resamples", type=int, default=20_000)
    parser.add_argument("--trigger", type=Path)
    args = parser.parse_args()
    with args.input.open() as handle:
        payload = json.load(handle)
    verdict = analyze(
        payload,
        expected_documents=args.expected_documents,
        n_resamples=args.n_resamples,
    )
    with args.output.open("w") as handle:
        json.dump(verdict, handle, indent=1, allow_nan=False)
    args.table.write_text(verdict["markdown_table"])
    if args.expected_documents == 20 and args.trigger:
        authorization = payload["q1_authorization"]
        readings = verdict["registered_readings"]
        trigger = {
            "protocol": "MERGECERT-Q1",
            "budget_mode": BUDGET_MODE,
            "run_q2_q3": readings["run_q2_q3"],
            "favorable_intervals": readings["favorable_intervals"],
            "q1_verdict_sha256": _sha256_file(args.output),
            "addendum_sha256": authorization["addendum_sha256"],
            "p0_verdict_sha256": authorization["p0_verdict_sha256"],
        }
        with args.trigger.open("w") as handle:
            json.dump(trigger, handle, indent=1, allow_nan=False)
    print(json.dumps(verdict, indent=1))


if __name__ == "__main__":
    main()
