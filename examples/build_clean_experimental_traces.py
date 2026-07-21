"""Build paper-ready traces from the signed clean E1FULL artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RELATIVE = (
    "plans/260719-2328-e1full-unfrozen-full-recipe/"
    "summary-e1full-clean-v1-n60.json"
)
DEFAULT_SOURCE = ROOT / SOURCE_RELATIVE
DEFAULT_OUTPUT_DIR = ROOT / "examples/experimental-traces"
DEFAULT_JSON_OUTPUT = DEFAULT_OUTPUT_DIR / "clean-e1full-traces.json"
DEFAULT_MARKDOWN_OUTPUT = DEFAULT_OUTPUT_DIR / "README.md"

CHECKPOINT_NAME = "e1full-clean-v1-t1024-T8k"
EXPECTED_HOLDOUT_SHA = (
    "64043bca6642b877af7366d4980a3bd9794184ff49e1702a4ef8a3db7398882d"
)
EXPECTED_MANIFEST_SHA = (
    "16e3ef0e7b9062218dc4f43a7ca53821c2194884b1c0580c62da2c9fba066aff"
)
EXPECTED_CHECKPOINT_SHA = (
    "c00b2437fdd813ccdf7469eff7433ccd2b02f356766d4f7a12305441b3a46099"
)
EXPECTED_POLICY = "still-compact-v1:t1024:depth0:sha256:c00b2437fdd813cc"
EXPECTED_OVERLAP_AUDIT = {
    "training_documents": 35353,
    "training_items": 94056,
    "certification_documents": 60,
    "certification_items": 193,
    "document_overlap": [],
    "item_overlap": [],
}
ARMS = ("eviction-matched", "compactor-d1", "compactor-d4", "control-0")


def validate_source(source: dict[str, Any]) -> None:
    provenance = source["provenance"]
    summary = source["summary"]
    checks = {
        "holdout_sha256": (
            provenance["holdout_sha256"], EXPECTED_HOLDOUT_SHA),
        "training_manifest_sha256": (
            provenance["training_manifest_sha256"], EXPECTED_MANIFEST_SHA),
        "checkpoint_weights": (
            provenance["checkpoint_weights"][CHECKPOINT_NAME],
            f"sha256:{EXPECTED_CHECKPOINT_SHA}"),
        "overlap_audit": (
            provenance["overlap_audit"], EXPECTED_OVERLAP_AUDIT),
        "n_documents": (summary["n_documents"], 60),
        "gt13_point_pass": (
            summary["gt13_point_pass"],
            {"compactor-d1": False, "compactor-d4": False}),
        "gt13_ship": (summary["gt13_ship"], False),
        "gt15_max_certified_depth": (
            summary["gt15_max_certified_depth"], 0),
        "policy": (
            summary[f"policy_version_{CHECKPOINT_NAME}"], EXPECTED_POLICY),
    }
    for name, (actual, expected) in checks.items():
        if actual != expected:
            raise ValueError(
                f"{name}: expected {expected!r}, got {actual!r}")


def _index_reports(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    reports = source["reports"]
    missing_arms = set(ARMS) - set(reports)
    if missing_arms:
        raise ValueError(f"missing arms: {sorted(missing_arms)}")

    indexed: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        by_document: dict[str, Any] = {}
        for report in reports[arm]:
            document_id = report["eval_protocol"]["doc_id"]
            if document_id in by_document:
                raise ValueError(f"duplicate document {document_id!r} in {arm}")
            by_document[document_id] = report
        indexed[arm] = by_document

    expected_documents = set(indexed[ARMS[0]])
    for arm in ARMS[1:]:
        if set(indexed[arm]) != expected_documents:
            raise ValueError(f"document alignment differs for {arm}")

    for document_id in sorted(expected_documents):
        reference_records = _records_by_item(indexed[ARMS[0]][document_id])
        reference_ids = set(reference_records)
        for arm in ARMS[1:]:
            records = _records_by_item(indexed[arm][document_id])
            if set(records) != reference_ids:
                raise ValueError(
                    f"probe alignment differs for {arm} on {document_id}")
            for item_id in reference_ids:
                reference = reference_records[item_id]
                candidate = records[item_id]
                for field in ("question", "options", "gold",
                              "pred_full_context"):
                    if candidate[field] != reference[field]:
                        raise ValueError(
                            f"{field} differs for {arm} on {item_id}")
    return indexed


def _records_by_item(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for record in report["probe_records"]:
        item_id = record["item_id"]
        if item_id in records:
            raise ValueError(f"duplicate probe record {item_id!r}")
        records[item_id] = record
    return records


def _document_analysis(
    indexed: dict[str, dict[str, Any]], document_id: str
) -> dict[str, float | int]:
    eviction = indexed["eviction-matched"][document_id]
    depth1 = indexed["compactor-d1"][document_id]
    depth4 = indexed["compactor-d4"][document_id]
    eviction_records = _records_by_item(eviction)
    depth1_records = _records_by_item(depth1)
    depth4_records = _records_by_item(depth4)

    recovered = sum(
        record["pred_full_context"] == record["gold"]
        and record["pred_compacted"] != record["gold"]
        and depth1_records[item_id]["pred_compacted"] == record["gold"]
        for item_id, record in eviction_records.items()
    )
    depth4_lost = sum(
        record["pred_full_context"] == record["gold"]
        and record["pred_compacted"] == record["gold"]
        and depth4_records[item_id]["pred_compacted"] != record["gold"]
        for item_id, record in depth1_records.items()
    )
    eviction_minus_depth1_lost = (
        eviction["pointwise_axis"]["lost_fact_incident_rate"]
        - depth1["pointwise_axis"]["lost_fact_incident_rate"]
    )
    depth1_minus_eviction_kl = (
        depth1["aggregation_axis"]["mean_kl"]
        - eviction["aggregation_axis"]["mean_kl"]
    )
    depth4_minus_depth1_kl = (
        depth4["aggregation_axis"]["mean_kl"]
        - depth1["aggregation_axis"]["mean_kl"]
    )
    return {
        "recovered_item_count": recovered,
        "eviction_minus_depth1_lost_fact_rate": eviction_minus_depth1_lost,
        "depth1_minus_eviction_kl": depth1_minus_eviction_kl,
        "depth1_preserved_depth4_lost_count": depth4_lost,
        "depth4_minus_depth1_kl": depth4_minus_depth1_kl,
    }


def _select_documents(
    indexed: dict[str, dict[str, Any]],
) -> list[tuple[str, str, dict[str, float | int]]]:
    analyses = {
        document_id: _document_analysis(indexed, document_id)
        for document_id in indexed[ARMS[0]]
    }
    selected: list[tuple[str, str, dict[str, float | int]]] = []
    used: set[str] = set()

    selectors = (
        (
            "pointwise_recovery",
            lambda row: row["recovered_item_count"] > 0,
            lambda item: (
                -item[1]["recovered_item_count"],
                -item[1]["eviction_minus_depth1_lost_fact_rate"],
                item[0],
            ),
        ),
        (
            "axis_disagreement",
            lambda row: (
                row["eviction_minus_depth1_lost_fact_rate"] > 0
                and row["depth1_minus_eviction_kl"] > 0
            ),
            lambda item: (
                -item[1]["eviction_minus_depth1_lost_fact_rate"],
                -item[1]["depth1_minus_eviction_kl"],
                item[0],
            ),
        ),
        (
            "depth4_collapse",
            lambda row: (
                row["depth1_preserved_depth4_lost_count"] > 0
                and row["depth4_minus_depth1_kl"] > 0
            ),
            lambda item: (
                -item[1]["depth1_preserved_depth4_lost_count"],
                -item[1]["depth4_minus_depth1_kl"],
                item[0],
            ),
        ),
    )

    for category, eligible, sort_key in selectors:
        candidates = [
            item for item in analyses.items()
            if item[0] not in used and eligible(item[1])
        ]
        if not candidates:
            raise ValueError(f"no distinct eligible document for {category}")
        document_id, analysis = sorted(candidates, key=sort_key)[0]
        selected.append((category, document_id, analysis))
        used.add(document_id)
    return selected


def _arm_metrics(report: dict[str, Any]) -> dict[str, float]:
    return {
        "aggregation_mean_kl": report["aggregation_axis"]["mean_kl"],
        "aggregation_accuracy_delta": (
            report["aggregation_axis"]["accuracy_delta"]),
        "lost_fact_incident_rate": (
            report["pointwise_axis"]["lost_fact_incident_rate"]),
        "lost_fact_rate_given_prior_correct": (
            report["pointwise_axis"][
                "lost_fact_rate_given_prior_correct"]),
    }


def _selection_reason(
    category: str, analysis: dict[str, float | int]
) -> str:
    if category == "pointwise_recovery":
        return (
            f"Depth 1 recovers {analysis['recovered_item_count']} "
            "prior-correct item(s) lost by matched eviction."
        )
    if category == "axis_disagreement":
        return (
            "Depth 1 lowers the document lost-fact rate by "
            f"{analysis['eviction_minus_depth1_lost_fact_rate']:.4f} while "
            "raising aggregation KL by "
            f"{analysis['depth1_minus_eviction_kl']:.4f}."
        )
    return (
        f"Depth 4 loses {analysis['depth1_preserved_depth4_lost_count']} "
        "prior-correct item(s) preserved by depth 1 while adding "
        f"{analysis['depth4_minus_depth1_kl']:.4f} aggregation KL."
    )


def _build_trace(
    indexed: dict[str, dict[str, Any]],
    category: str,
    document_id: str,
    analysis: dict[str, float | int],
) -> dict[str, Any]:
    reference_records = _records_by_item(
        indexed["eviction-matched"][document_id])
    arm_records = {
        arm: _records_by_item(indexed[arm][document_id])
        for arm in ARMS
    }
    probe_records = []
    for item_id in sorted(reference_records):
        record = reference_records[item_id]
        probe_records.append({
            "item_id": item_id,
            "question": record["question"],
            "options": record["options"],
            "gold": record["gold"],
            "pred_full_context": record["pred_full_context"],
            "pred_compacted_by_arm": {
                arm: arm_records[arm][item_id]["pred_compacted"]
                for arm in ARMS
            },
        })
    return {
        "category": category,
        "document_id": document_id,
        "domain": document_id.split("/", 1)[0],
        "selection_reason": _selection_reason(category, analysis),
        "selection_metrics": analysis,
        "arm_metrics": {
            arm: _arm_metrics(indexed[arm][document_id])
            for arm in ARMS
        },
        "probe_records": probe_records,
    }


def build_gallery(source: dict[str, Any]) -> dict[str, Any]:
    validate_source(source)
    indexed = _index_reports(source)
    traces = [
        _build_trace(indexed, category, document_id, analysis)
        for category, document_id, analysis in _select_documents(indexed)
    ]
    return {
        "schema_version": "clean-e1full-trace-gallery-v1",
        "source_artifact": SOURCE_RELATIVE,
        "evidence_scope": (
            "Real held-out certification traces. Aggregation metrics are "
            "document-level; probe records are pointwise items. These are "
            "not token-level generation logs or attention dumps."
        ),
        "provenance": {
            "holdout_sha256": EXPECTED_HOLDOUT_SHA,
            "training_manifest_sha256": EXPECTED_MANIFEST_SHA,
            "checkpoint_name": CHECKPOINT_NAME,
            "checkpoint_weights_sha256": EXPECTED_CHECKPOINT_SHA,
            "overlap_audit": source["provenance"]["overlap_audit"],
        },
        "verdict": {
            "gt13": "NO-SHIP",
            "gt13_ship": False,
            "max_certified_depth": 0,
            "policy": EXPECTED_POLICY,
        },
        "traces": traces,
    }


def _format_metric(value: float) -> str:
    return f"{value:.4f}"


def render_markdown(gallery: dict[str, Any]) -> str:
    provenance = gallery["provenance"]
    verdict = gallery["verdict"]
    lines = [
        "# Real Held-Out E1FULL Certification Traces",
        "",
        "These three examples are selected deterministically from the signed clean",
        "certification artifact. They are real held-out certification traces,",
        "not token-level generation logs or attention dumps.",
        "",
        f"- Verdict: **{verdict['gt13']}**, certified depth "
        f"`{verdict['max_certified_depth']}`",
        f"- Policy: `{verdict['policy']}`",
        f"- Checkpoint weights SHA-256: "
        f"`{provenance['checkpoint_weights_sha256']}`",
        f"- Holdout SHA-256: `{provenance['holdout_sha256']}`",
        f"- Training manifest SHA-256: "
        f"`{provenance['training_manifest_sha256']}`",
        "- Overlap audit: 0 documents, 0 items",
        f"- Source: [`{gallery['source_artifact']}`]"
        f"(../../{gallery['source_artifact']})",
        "",
        "Aggregation metrics below are document-level. Question records are the",
        "pointwise probes stored in the signed artifact.",
        "",
    ]
    titles = {
        "pointwise_recovery": "Pointwise Recovery",
        "axis_disagreement": "Axis Disagreement",
        "depth4_collapse": "Depth-4 Collapse",
    }
    for index, trace in enumerate(gallery["traces"], start=1):
        lines.extend([
            f"## {index}. {titles[trace['category']]}",
            "",
            f"Document: `{trace['document_id']}` ({trace['domain']})",
            "",
            trace["selection_reason"],
            "",
            "| Arm | Aggregation KL | Accuracy delta | Lost fact | Lost given prior correct |",
            "|---|---:|---:|---:|---:|",
        ])
        for arm in ARMS:
            metrics = trace["arm_metrics"][arm]
            lines.append(
                f"| `{arm}` | "
                f"{_format_metric(metrics['aggregation_mean_kl'])} | "
                f"{_format_metric(metrics['aggregation_accuracy_delta'])} | "
                f"{_format_metric(metrics['lost_fact_incident_rate'])} | "
                f"{_format_metric(metrics['lost_fact_rate_given_prior_correct'])} |"
            )
        lines.append("")
        for record in trace["probe_records"]:
            lines.extend([
                f"### `{record['item_id']}`",
                "",
                record["question"].strip(),
                "",
            ])
            for option_index, option in enumerate(record["options"]):
                label = chr(ord("A") + option_index)
                lines.append(f"- {label}. {option.strip()}")
            predictions = record["pred_compacted_by_arm"]
            lines.extend([
                "",
                "| Gold | Full context | Eviction | Depth 1 | Depth 4 | Control |",
                "|---:|---:|---:|---:|---:|---:|",
                f"| {record['gold']} | {record['pred_full_context']} | "
                f"{predictions['eviction-matched']} | "
                f"{predictions['compactor-d1']} | "
                f"{predictions['compactor-d4']} | "
                f"{predictions['control-0']} |",
                "",
            ])
    return "\n".join(lines).rstrip() + "\n"


def generate(
    source_path: Path,
    json_path: Path,
    markdown_path: Path,
) -> None:
    source = json.loads(source_path.read_text())
    gallery = build_gallery(source)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(gallery, indent=2, sort_keys=True) + "\n")
    markdown_path.write_text(render_markdown(gallery))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the clean E1FULL experimental trace gallery.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument(
        "--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    args = parser.parse_args()
    generate(args.source, args.json_output, args.markdown_output)
    print(f"wrote {args.json_output}")
    print(f"wrote {args.markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
