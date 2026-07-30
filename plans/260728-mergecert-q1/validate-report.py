"""Fail-closed validation for the private MergeCert Q1 report bundle."""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import math
import re
from datetime import date
from pathlib import Path

from memsub.mergecert_q1_registration import (
    Q1_REGISTRATION_PENDING,
    Q1_REGISTRATION_SHA256,
    canonical_q1_registration_sha256,
    validate_q1_registration_schema,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_REPORT = ROOT / "MERGECERT-Q1-REPORT.md"
DEFAULT_MANIFEST = HERE / "artifact-manifest.json"
REQUIRED_HEADINGS = {
    "## Settled 0.90 result",
    "## Q1 — Moderate-ratio placement",
    "## Per-domain slices",
    "## Registered readings",
    "## Conditional Q2/Q3",
    "## Compute provenance",
    "## For the KV-Merge README",
    "## For the spec",
    "## Limitations",
}
EXPECTED_ARMS = {
    "control-0.00",
    "eviction-0.25",
    "eviction-0.40",
    "merge-0.25",
    "merge-0.40",
}
EXPECTED_DOMAINS = {"financial", "legal", "code", "literature"}
BUDGET_MODE = "archived-m1-per-document-matched-physical-v1"
TOKENIZER_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
Q1_REGISTRATION_SOURCE_PATH = HERE / "q1-registration-source.json"
with Q1_REGISTRATION_SOURCE_PATH.open() as _registration_handle:
    Q1_REGISTRATION_SOURCE = json.load(_registration_handle)
REGISTERED_FULL_DOC_IDS = Q1_REGISTRATION_SOURCE["population_doc_ids"]
REGISTERED_ARCHIVE_SHA256 = Q1_REGISTRATION_SOURCE["archive_sha256"]
REGISTERED_EVICTION_START = Q1_REGISTRATION_SOURCE[
    "eviction_source_start"
]
EXPECTED_UPSTREAM = {
    "commit": "cd4ed948d62231449dbab9669608bbb4fd220713",
    "files": {
        "README.md": (
            "edfd5236d99dab5d6e4bf80b74dd79a54ffd94cec4b7066511dc6fd7ae7cae17"
        ),
        "benchmarks/modal_kv_real_bench.py": (
            "518b2d2cd4b652f4cc83ef9c82593fe624301986e0e3e22780ee9f0bfe423bb8"
        ),
        "lego_server.py": (
            "f1df91c8af05cf4ea5000f4027450bf91e5e269f4e922da8979fc0885d6ff228"
        ),
    },
}
EXPECTED_ADDENDUM = {
    "path": "MERGECERT-Q1.md",
    "sha256": "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509",
}
EXPECTED_REGISTRATION_SOURCE = {
    "path": "plans/260728-mergecert-q1/q1-registration-source.json",
    "sha256": "6ab5b8cd8b63ff086795796220f458d5d3caf7127cc51c253102d473da45c9c4",
    "status": "source-evidence-only; finalized CPU extraction completed",
}
EXPECTED_SETTLED_P0 = {
    "verdict_path": "plans/260727-mergecert/p0-verdict.json",
    "verdict_sha256": (
        "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
    ),
    "raw_path": "plans/260727-mergecert/p0-direction-200.json",
    "raw_sha256": (
        "2d12ae1de090f3d93ba3cad97f68a49f543cd4a0398078c625e2641981f10f6c"
    ),
}
EXPECTED_PARENT_SOURCE_SHA256 = (
    "cbaaec6a20cb4e53ab36a56f377c91c6bd97b8028f1fd60e2c63bdb759576930"
)
EXPECTED_Q2_AMENDMENT = {
    "schema": "mergecert-q2-amendment-v1",
    "protocol": "MERGECERT-Q2",
    "protocol_version": "mergecert-q2-amended-v2",
    "settled_date": "2026-07-29",
    "status": "settled",
    "authority": "user-selected-option-2",
    "model_id": "Qwen/Qwen3-4B-Instruct-2507",
    "population": {
        "manifest_items": 30847,
        "selection": "unchanged-standard-30847-manifest",
        "item_ids_labels_and_order_rule_unchanged": True,
    },
    "ratios": [0.25, 0.4],
    "sink_token_count": 4,
    "reference_context_tokens": 4096,
    "minimum_context_tokens": 9,
    "budget_mode": "per-item-actual-context-matched-physical-v2",
    "context_mechanics_version": "mergecert-q2-context-mechanics-v2",
    "namespace_version": "mergecert-q2-amended-v2",
    "remote_root": "/artifacts/mergecert/q2-amended-v2",
    "context_rule": (
        "canonical registered source window capped at 4096 "
        "pinned-tokenizer tokens"
    ),
    "requested_eviction_rule": (
        "floor(source_context_token_count * ratio) from logical position 4"
    ),
    "physical_budget_rule": (
        "measure removal on an independent full-cache clone and give merge "
        "the measured retained count"
    ),
    "merge_plan_rule": (
        "build_merge_plan(source_context_token_count, exact registered "
        "ratio, sink_token_count=4)"
    ),
    "legacy_fixed_context_evidence_authorizes": False,
    "forbidden": [
        "padding",
        "runtime-skip",
        "replacement",
        "population-filter",
        "label-change",
        "silent-budget-change",
        "legacy-state-resume",
    ],
    "rerun_gate": {
        "new_pilot_items": 16,
        "pilot_review_required_before_fleet": True,
        "new_fleet_slices": 8,
        "fleet_items": 30847,
        "fresh_authorization_required": True,
    },
}
MARKDOWN_ESCAPE_PATTERN = re.compile(
    r"\\([\\`*_[\]{}()#+\-.!|>?~])"
)
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[([^\]\n]*)\]\([^)\n]*\)")
MARKDOWN_WRAPPER_PATTERN = re.compile(r"[*_~`]+")
HTML_TAG_PATTERN = re.compile(r"<[^>\n]+>")
PUBLIC_URL_PATTERN = re.compile(
    r"(?:(?:https?:)?//)[A-Za-z0-9]",
    re.IGNORECASE,
)
QUESTION_CELL_PATTERN = re.compile(r"\|\s*\?\s*\|")
QWEN25_PATTERN = re.compile(r"\bqwen2\.5\b", re.IGNORECASE)
CLAIM_SEGMENT_PATTERN = re.compile(
    r"(?:[.;,\n]+|\b(?:and|but)\b)",
    re.IGNORECASE,
)
NEGATION_PATTERN = re.compile(
    r"\b(?:not|no|never|unconfirmed|unrecorded|neither)\b",
    re.IGNORECASE,
)
DEPLOYMENT_PATTERN = re.compile(
    r"\b(?:deploy|deployed|deploying|deploys|deployment(?!-relevant\b))\b",
    re.IGNORECASE,
)
TRANSMISSION_PATTERN = re.compile(
    r"\b(?:transmission|delivery)\b",
    re.IGNORECASE,
)
REPORT_PATTERN = re.compile(r"\breport\b", re.IGNORECASE)
RECIPIENT_PATTERN = re.compile(r"\b(?:tyler|kevin)\b", re.IGNORECASE)
AFFIRMATIVE_PATTERN = re.compile(
    r"\b(?:succeed(?:ed|s|ing)?|success(?:ful(?:ly)?)?|"
    r"complet(?:e|ed|ion)|ready|certif(?:ied|ication)|"
    r"approv(?:ed|al)|production|live|operational|"
    r"sent|deliver(?:ed|y)|transmitt(?:ed|al)|shared|"
    r"receiv(?:e|ed|es|ing))\b",
    re.IGNORECASE,
)
EXPECTED_PHASE_LABELS = {
    "q1": "Q1",
    "q2_q3": "Q2/Q3",
}
MODAL_APP_ID = r"ap-[A-Za-z0-9]{22}"
APP_ID_PATTERN = re.compile(MODAL_APP_ID)
BILLING_SOURCE_PATTERN = re.compile(
    rf"Modal billing report (?P<date>\d{{4}}-\d{{2}}-\d{{2}}) "
    rf"for (?P<noun>app|apps) "
    rf"(?P<ids>{MODAL_APP_ID}(?:(?:, | and ){MODAL_APP_ID})*)"
)


def _renderer_module():
    path = HERE / "render-report.py"
    spec = importlib.util.spec_from_file_location(
        "mergecert_q1_report_renderer", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inspection_text(unescaped_report: str) -> str:
    normalized = MARKDOWN_ESCAPE_PATTERN.sub(r"\1", unescaped_report)
    normalized = MARKDOWN_LINK_PATTERN.sub(r"\1", normalized)
    normalized = HTML_TAG_PATTERN.sub("", normalized)
    return MARKDOWN_WRAPPER_PATTERN.sub("", normalized)


def _positive_claim(report: str) -> str | None:
    for segment in CLAIM_SEGMENT_PATTERN.split(report):
        if not segment.strip() or NEGATION_PATTERN.search(segment):
            continue
        if DEPLOYMENT_PATTERN.search(segment):
            return segment.strip()
        if TRANSMISSION_PATTERN.search(segment):
            return segment.strip()
        if (
            RECIPIENT_PATTERN.search(segment)
            and REPORT_PATTERN.search(segment)
        ):
            return segment.strip()
        if (
            RECIPIENT_PATTERN.search(segment)
            and AFFIRMATIVE_PATTERN.search(segment)
        ):
            return segment.strip()
    return None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _is_strict_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_sha256(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_q1_registration_binding() -> str:
    if Q1_REGISTRATION_SHA256 == Q1_REGISTRATION_PENDING:
        raise ValueError(
            "Q1 report is pending finalized registration extraction "
            "and independent review"
        )
    if not _is_sha256(Q1_REGISTRATION_SHA256):
        raise ValueError("Q1 finalized registration SHA-256 binding is invalid")
    return Q1_REGISTRATION_SHA256


def _validate_registered_documents(documents: list[dict]) -> dict[str, dict]:
    if (
        len(documents) != 20
        or [row.get("doc_id") for row in documents]
        != REGISTERED_FULL_DOC_IDS
    ):
        raise ValueError("Q1 finalized registration population is incomplete")
    by_doc = {row["doc_id"]: row for row in documents}
    for doc_id, document in by_doc.items():
        source_tokens = document.get("source_context_token_count")
        model_tokens = document.get("model_input_token_count")
        if (
            not _is_strict_int(document.get("context_start"))
            or document["context_start"]
            != max(
                0,
                Q1_REGISTRATION_SOURCE["anchor_chunk_token_start"][
                    doc_id
                ]
                - 1024,
            )
            or not _is_strict_int(source_tokens)
            or source_tokens <= 4
            or not _is_strict_int(model_tokens)
            or model_tokens <= 4
            or set(document.get("budgets", {})) != {"0.25", "0.40"}
        ):
            raise ValueError(
                "Q1 finalized registration context start or counts are invalid"
            )
        for ratio_text, budget in document["budgets"].items():
            fields = (
                "requested_evicted_token_count",
                "eviction_source_start",
                "eviction_source_end",
                "physical_before_count",
                "physical_after_count",
                "evicted_token_count",
                "retained_token_count",
                "merge_target_retained",
            )
            if set(budget) != set(fields) or not all(
                _is_strict_int(budget.get(field)) for field in fields
            ):
                raise ValueError("Q1 finalized registration counts are invalid")
            ratio = float(ratio_text)
            expected_removed = max(
                0,
                min(
                    budget["eviction_source_end"],
                    budget["physical_before_count"],
                )
                - min(
                    max(budget["eviction_source_start"], 0),
                    budget["physical_before_count"],
                ),
            )
            if (
                budget["eviction_source_start"]
                != REGISTERED_EVICTION_START[doc_id]
                or budget["requested_evicted_token_count"]
                != int(source_tokens * ratio)
                or budget["eviction_source_end"]
                - budget["eviction_source_start"]
                != budget["requested_evicted_token_count"]
                or budget["physical_before_count"] != model_tokens
                or budget["physical_before_count"]
                - budget["physical_after_count"]
                != budget["evicted_token_count"]
                or budget["evicted_token_count"] != expected_removed
                or budget["retained_token_count"]
                != budget["physical_after_count"]
                or budget["merge_target_retained"]
                != budget["physical_after_count"]
            ):
                raise ValueError("Q1 finalized registration budget is invalid")
    return by_doc


def _validate_file_hashes(evidence: dict) -> None:
    files = evidence.get("_files")
    if not isinstance(files, dict) or not files:
        raise ValueError("artifact hash metadata is missing")
    relative_paths = []
    for name, metadata in files.items():
        path = metadata.get("path")
        if not isinstance(path, Path) or not path.is_file():
            raise ValueError(f"artifact {name} is missing")
        actual_hash = _sha256(path)
        actual_bytes = path.stat().st_size
        if (
            metadata.get("sha256") != actual_hash
            or metadata.get("bytes") != actual_bytes
        ):
            raise ValueError(f"artifact hash or byte count drift for {name}")
        relative_path = metadata.get("relative_path")
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError(f"artifact path metadata is missing for {name}")
        relative_paths.append(relative_path)
    if len(relative_paths) != len(set(relative_paths)):
        raise ValueError("artifact paths are not unique")


def _validate_loaded_evidence(evidence: dict) -> None:
    for name in (
        "source",
        "p0",
        "registration",
        "q1",
        "trigger",
        "conditional",
        "compute",
    ):
        path = evidence["_files"][name]["path"]
        with path.open() as handle:
            loaded = json.load(handle)
        if json.dumps(loaded, sort_keys=True) != json.dumps(
            evidence[name], sort_keys=True
        ):
            raise ValueError(f"loaded evidence differs from hashed file {name}")
    for name in ("q2_amendment", "q2", "q3"):
        if name not in evidence:
            continue
        with evidence["_files"][name]["path"].open() as handle:
            loaded = json.load(handle)
        if json.dumps(loaded, sort_keys=True) != json.dumps(
            evidence[name], sort_keys=True
        ):
            raise ValueError(f"loaded evidence differs from hashed file {name}")


def _validate_source(evidence: dict) -> None:
    source = evidence.get("source", {})
    files = evidence["_files"]
    if (
        source.get("protocol") != "MERGECERT-Q1"
        or source.get("model_id") != "Qwen/Qwen3-4B-Instruct-2507"
        or source.get("ratios") != [0.25, 0.4]
        or source.get("sink_token_count") != 4
        or source.get("budget_mode") != BUDGET_MODE
        or source.get("settled_amendment_date") != "2026-07-29"
        or source.get("upstream_commit") != EXPECTED_UPSTREAM["commit"]
    ):
        raise ValueError("source provenance differs from registration")
    upstream_files = source.get("upstream_files")
    if upstream_files != EXPECTED_UPSTREAM["files"]:
        raise ValueError("source provenance file hashes are incomplete")
    addendum = source.get("addendum", {})
    registration_source = source.get("q1_registration_source", {})
    registration_binding = source.get("q1_registration", {})
    settled = source.get("settled_p0", {})
    if (
        addendum != EXPECTED_ADDENDUM
        or registration_source != EXPECTED_REGISTRATION_SOURCE
        or registration_binding
        != {
            "path": "plans/260728-mergecert-q1/q1-registration.json",
            "remote_path": (
                "/artifacts/mergecert-q1/q1-registration.json"
            ),
            "sha256": Q1_REGISTRATION_SHA256,
            "status": "finalized and hash-bound",
        }
        or settled != EXPECTED_SETTLED_P0
        or source.get("parent_source_provenance_sha256")
        != EXPECTED_PARENT_SOURCE_SHA256
    ):
        raise ValueError("source provenance differs from registration")
    if (
        addendum.get("sha256") != files["addendum"]["sha256"]
        or registration_source.get("sha256")
        != files["registration_source"]["sha256"]
        or registration_binding.get("sha256")
        != files["registration"]["sha256"]
        or settled.get("verdict_sha256") != files["p0"]["sha256"]
        or settled.get("raw_sha256") != files["p0_raw"]["sha256"]
        or source.get("parent_source_provenance_sha256")
        != files["parent_source"]["sha256"]
    ):
        raise ValueError("source provenance artifact hash mismatch")
    expected_paths = {
        "addendum": addendum.get("path"),
        "registration_source": registration_source.get("path"),
        "registration": registration_binding.get("path"),
        "p0": settled.get("verdict_path"),
        "p0_raw": settled.get("raw_path"),
    }
    if any(
        files[name]["relative_path"] != expected
        for name, expected in expected_paths.items()
    ):
        raise ValueError("source provenance artifact path mismatch")
    p0 = evidence.get("p0", {})
    if (
        p0.get("p0_3", {}).get("pass") is not False
        or p0.get("p0_4", {}).get("pass") is not True
        or p0.get("real_attention", {}).get("pass") is not True
        or p0.get("p0_pass") is not False
        or p0.get("stop_q1_q3") is not True
    ):
        raise ValueError("settled P0 verdict is not the registered negative")


def _expected_favorable(intervals: dict) -> tuple[list[str], list[str]]:
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
    return pointwise, aggregation


def _validate_interval(interval: dict, label: str) -> None:
    values = [interval.get("mean_diff"), *(interval.get("ci95") or [])]
    if (
        not isinstance(interval.get("ci95"), list)
        or len(interval["ci95"]) != 2
        or not all(_is_number(value) for value in values)
        or interval["ci95"][0] > interval["ci95"][1]
    ):
        raise ValueError(f"Q1 interval is malformed for {label}")


def _validate_q1(evidence: dict) -> None:
    expected_registration_sha256 = _require_q1_registration_binding()
    q1 = evidence.get("q1", {})
    registration = evidence.get("registration", {})
    if (
        canonical_q1_registration_sha256(registration)
        != expected_registration_sha256
    ):
        raise ValueError(
            "Q1 finalized registration differs from its literal binding"
        )
    tokenizer = registration.get("tokenizer", {})
    tokenizer_files = tokenizer.get("files_sha256", {})
    source_hashes = registration.get("source_hashes", {})
    source_document_sha256 = source_hashes.get(
        "source_document_sha256", {}
    )
    if (
        registration.get("schema") != "mergecert-q1-registration-v1"
        or registration.get("status") != "finalized"
        or registration.get("source_registration_sha256")
        != _sha256(Q1_REGISTRATION_SOURCE_PATH)
        or registration.get("model_id")
        != "Qwen/Qwen3-4B-Instruct-2507"
        or Q1_REGISTRATION_SOURCE.get("tokenizer_revision")
        != TOKENIZER_REVISION
        or tokenizer.get("model_id")
        != "Qwen/Qwen3-4B-Instruct-2507"
        or tokenizer.get("revision") != TOKENIZER_REVISION
        or not isinstance(tokenizer_files, dict)
        or not tokenizer_files
        or any(
            not isinstance(name, str) or not _is_sha256(digest)
            for name, digest in tokenizer_files.items()
        )
        or tokenizer.get("artifact_sha256")
        != hashlib.sha256(
            json.dumps(
                tokenizer_files,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        or registration.get("population_doc_ids") != REGISTERED_FULL_DOC_IDS
        or registration.get("smoke_doc_ids")
        != Q1_REGISTRATION_SOURCE["smoke_doc_ids"]
        or registration.get("archive_sha256")
        != REGISTERED_ARCHIVE_SHA256
        or registration.get("all_items_sha256")
        != Q1_REGISTRATION_SOURCE["all_items_sha256"]
        or source_hashes.get("all_items_sha256")
        != Q1_REGISTRATION_SOURCE["all_items_sha256"]
        or not _is_sha256(source_hashes.get("corpus_manifest_sha256"))
        or not isinstance(source_document_sha256, dict)
        or set(source_document_sha256) != set(REGISTERED_FULL_DOC_IDS)
        or any(
            not _is_sha256(digest)
            for digest in source_document_sha256.values()
        )
        or q1.get("q1_registration_sha256")
        != expected_registration_sha256
        or evidence["_files"]["registration"]["sha256"]
        != expected_registration_sha256
    ):
        raise ValueError(
            "Q1 finalized registration or source hash set is missing or differs"
        )
    registered_documents = registration.get("documents", [])
    registered_by_doc = _validate_registered_documents(
        registered_documents
    )
    if (
        q1.get("pass") is not True
        or not _is_strict_int(q1.get("documents"))
        or q1["documents"] != 20
        or q1.get("archived_m1_replay_pass") is not True
        or set(q1.get("summaries", {})) != EXPECTED_ARMS
        or set(q1.get("references", {}))
        != {"frozen_subsample", "unfrozen_compactor"}
        or set(q1.get("per_domain", {})) != EXPECTED_DOMAINS
        or q1.get("budget_mode") != BUDGET_MODE
        or q1.get("authorization")
        != {
            "protocol": "MERGECERT-Q1",
            "budget_mode": BUDGET_MODE,
            "addendum_sha256": EXPECTED_ADDENDUM["sha256"],
            "p0_verdict_sha256": EXPECTED_SETTLED_P0["verdict_sha256"],
        }
    ):
        raise ValueError("Q1 verdict is incomplete")
    per_document_budgets = q1.get("per_document_budgets", {})
    sample_doc_ids = q1.get("sample_doc_ids", [])
    domain_counts = q1.get("domain_counts", {})
    if (
        not isinstance(sample_doc_ids, list)
        or sample_doc_ids != REGISTERED_FULL_DOC_IDS
        or set(per_document_budgets) != set(sample_doc_ids)
    ):
        raise ValueError("Q1 per-document budgets are incomplete")
    if domain_counts != {domain: 5 for domain in EXPECTED_DOMAINS} or any(
        not _is_strict_int(value) for value in domain_counts.values()
    ):
        raise ValueError("Q1 domain counts are incomplete")
    expected_replay = {
        (
            doc_id,
            f"{doc_id.split('/', 1)[0]}-evict{ratio:.2f}.json",
            (
                "control-0.00"
                if ratio == 0.0
                else f"eviction-{ratio:.2f}"
            ),
            REGISTERED_ARCHIVE_SHA256[
                f"{doc_id.split('/', 1)[0]}-evict{ratio:.2f}.json"
            ],
        )
        for doc_id in sample_doc_ids
        for ratio in (0.0, 0.25, 0.40)
    }
    replay_matrix = q1.get("archive_replay_matrix", [])
    actual_replay = [
        (
            row.get("doc_id"),
            row.get("archive"),
            row.get("arm"),
            row.get("archive_sha256"),
        )
        for row in replay_matrix
        if isinstance(row, dict)
    ]
    if (
        len(actual_replay) != 60
        or len(set(actual_replay)) != 60
        or set(actual_replay) != expected_replay
    ):
        raise ValueError("Q1 archive replay matrix is incomplete")
    for doc_id, ratios in per_document_budgets.items():
        registered_document = registered_by_doc[doc_id]
        if set(ratios) != {"0.25", "0.40"}:
            raise ValueError(f"Q1 per-document budgets are incomplete for {doc_id}")
        for ratio_text, budget in ratios.items():
            source_tokens = budget.get("source_context_token_count")
            model_tokens = budget.get("model_input_token_count")
            actual_evicted = budget.get("evicted_token_count")
            requested_evicted = budget.get(
                "requested_evicted_token_count"
            )
            source_start = budget.get("eviction_source_start")
            source_end = budget.get("eviction_source_end")
            physical_before = budget.get("physical_before_count")
            physical_after = budget.get("physical_after_count")
            retained = budget.get("retained_token_count")
            merge_target = budget.get("merge_target_retained")
            ratio = float(ratio_text)
            counts = (
                source_tokens,
                model_tokens,
                actual_evicted,
                requested_evicted,
                source_start,
                source_end,
                physical_before,
                physical_after,
                retained,
                merge_target,
            )
            expected_removed = (
                max(
                    0,
                    min(source_end, physical_before)
                    - min(max(source_start, 0), physical_before),
                )
                if all(_is_strict_int(value) for value in counts)
                else None
            )
            if (
                not all(_is_strict_int(value) for value in counts)
                or source_tokens <= 4
                or model_tokens <= 4
                or actual_evicted <= 0
                or source_start != REGISTERED_EVICTION_START[doc_id]
                or requested_evicted != int(source_tokens * ratio)
                or source_end - source_start != requested_evicted
                or physical_before != model_tokens
                or physical_before - physical_after != actual_evicted
                or actual_evicted != expected_removed
                or physical_after <= 4
                or budget.get("retained_token_count")
                != physical_after
                or budget.get("merge_target_retained")
                != physical_after
            ):
                raise ValueError(
                    f"Q1 per-document budget is malformed for {doc_id}/{ratio_text}"
                )
            if budget != {
                "source_context_token_count": source_tokens,
                "model_input_token_count": model_tokens,
                **registered_document["budgets"][ratio_text],
            }:
                raise ValueError(
                    f"Q1 finalized registration budget differs for "
                    f"{doc_id}/{ratio_text}"
                )
    for domain, rows in q1["per_domain"].items():
        if set(rows) != EXPECTED_ARMS:
            raise ValueError(f"Q1 per-domain arms are incomplete for {domain}")
    numeric_fields = ("mean_kl", "accuracy_delta", "lost_prior")
    for group_name in ("summaries", "references"):
        for row_name, row in q1[group_name].items():
            if any(not _is_number(row.get(field)) for field in numeric_fields):
                raise ValueError(
                    f"Q1 numeric evidence is malformed for {row_name}"
                )
            if group_name == "summaries" and any(
                not _is_strict_int(row.get(field)) or row[field] < 0
                for field in (
                    "documents",
                    "aggregation_probes",
                    "needle_probes",
                )
            ):
                raise ValueError(
                    f"Q1 count evidence is malformed for {row_name}"
                )
    for domain, rows in q1["per_domain"].items():
        for arm, row in rows.items():
            if (
                any(not _is_number(row.get(field)) for field in numeric_fields)
                or any(
                    not _is_strict_int(row.get(field)) or row[field] < 0
                    for field in (
                        "documents",
                        "aggregation_probes",
                        "needle_probes",
                    )
                )
            ):
                raise ValueError(
                    f"Q1 numeric evidence is malformed for {domain}/{arm}"
                )
    intervals = q1.get("paired_merge_minus_eviction", {})
    if set(intervals) != {"0.25", "0.40"}:
        raise ValueError("Q1 paired intervals are incomplete")
    required_metrics = {"lost_prior", "mean_kl", "acc_delta"}
    allowed_metrics = required_metrics | {"lost_fact"}
    for ratio, row in intervals.items():
        if not required_metrics.issubset(row) or not set(row).issubset(
            allowed_metrics
        ):
            raise ValueError(f"Q1 paired metrics are incomplete for {ratio}")
        for metric, interval in row.items():
            _validate_interval(interval, f"{ratio}:{metric}")

    pointwise, aggregation = _expected_favorable(intervals)
    favorable = pointwise + aggregation
    readings = q1.get("registered_readings", {})
    expected = {
        "r1": "R1" if pointwise else "R2",
        "r3": (
            "aggregation-positive" if aggregation else "aggregation-negative"
        ),
        "pointwise_favorable": pointwise,
        "aggregation_favorable": aggregation,
        "favorable_intervals": favorable,
        "run_q2_q3": bool(favorable),
    }
    if readings != expected:
        raise ValueError("Q1 registered readings are inconsistent")
    if (
        q1.get("run_q2_q3") is not bool(favorable)
        or q1.get("favorable_intervals") != favorable
    ):
        raise ValueError("Q1 trigger fields are inconsistent")


def _validate_trigger(evidence: dict) -> None:
    trigger = evidence.get("trigger", {})
    q1 = evidence["q1"]
    source = evidence["source"]
    expected = {
        "protocol": "MERGECERT-Q1",
        "budget_mode": BUDGET_MODE,
        "run_q2_q3": q1["run_q2_q3"],
        "favorable_intervals": q1["favorable_intervals"],
        "q1_verdict_sha256": evidence["_files"]["q1"]["sha256"],
        "addendum_sha256": source["addendum"]["sha256"],
        "p0_verdict_sha256": source["settled_p0"]["verdict_sha256"],
    }
    if trigger != expected:
        raise ValueError("Q1 trigger differs from the registered verdict")


def _validate_q2_amendment(evidence: dict) -> dict:
    conditional = evidence["conditional"]
    declaration = conditional.get("q2_amendment")
    metadata = evidence["_files"].get("q2_amendment")
    if not isinstance(declaration, dict) or not isinstance(metadata, dict):
        raise ValueError("conditional Q2 amendment declaration is missing")
    if (
        declaration.get("path") != metadata.get("relative_path")
        or declaration.get("sha256") != metadata.get("sha256")
        or not _is_sha256(declaration.get("sha256"))
    ):
        raise ValueError("conditional Q2 amendment declaration drift")
    amendment = evidence.get("q2_amendment")
    if amendment != EXPECTED_Q2_AMENDMENT:
        raise ValueError("conditional Q2 amendment schema or payload drift")
    return amendment


def _validate_conditional(evidence: dict) -> str:
    conditional = evidence.get("conditional", {})
    trigger = evidence["trigger"]
    if (
        conditional.get("protocol") != "MERGECERT-Q1"
        or conditional.get("q1_trigger_sha256")
        != evidence["_files"]["trigger"]["sha256"]
    ):
        raise ValueError("conditional work is not bound to the Q1 trigger")
    if trigger["run_q2_q3"]:
        if conditional.get("status") != "completed":
            raise ValueError("conditional work was not completed after trigger")
        amendment = _validate_q2_amendment(evidence)
        versions = {
            "protocol_version": amendment["protocol_version"],
            "namespace_version": amendment["namespace_version"],
            "context_mechanics_version": amendment[
                "context_mechanics_version"
            ],
        }
        accounting_audit_sha256 = conditional.get(
            "context_accounting_audit_sha256"
        )
        if (
            any(conditional.get(name) != value for name, value in versions.items())
            or not _is_sha256(accounting_audit_sha256)
        ):
            raise ValueError("conditional Q2 amendment version or accounting audit drift")
        for name in ("q2", "q3"):
            if name not in evidence:
                raise ValueError(f"conditional {name.upper()} evidence drift")
            declaration = conditional.get(name, {})
            embedded_trigger = evidence[name].get("q1_trigger")
            embedded_hash = evidence[name].get("q1_trigger_sha256")
            expected_schema = (
                "mergecert-q2-verdict-amended-v2"
                if name == "q2"
                else "mergecert-q3-fragility-amended-v2"
            )
            if evidence[name].get("schema") != expected_schema:
                raise ValueError(
                    f"conditional {name.upper()} amended-v2 schema drift"
                )
            if name == "q2":
                f5_table = evidence[name].get("f5_markdown_table")
                if not isinstance(f5_table, str) or not f5_table.strip():
                    raise ValueError("conditional Q2 F5 evidence is missing")
            elif (
                evidence[name].get("q2_verdict_schema")
                != "mergecert-q2-verdict-amended-v2"
            ):
                raise ValueError("conditional Q3 Q2 verdict schema drift")
            if evidence[name].get("q2_amendment") != amendment:
                raise ValueError(
                    f"conditional {name.upper()} amendment evidence drift"
                )
            if evidence[name].get("q2_amendment_sha256") != evidence[
                "_files"
            ]["q2_amendment"]["sha256"]:
                raise ValueError(
                    f"conditional {name.upper()} amendment evidence drift"
                )
            for field, value in versions.items():
                if evidence[name].get(field) != value:
                    raise ValueError(
                        f"conditional {name.upper()} {field.replace('_', ' ')} drift"
                    )
            if (
                evidence[name].get("context_accounting_audit_sha256")
                != accounting_audit_sha256
            ):
                raise ValueError(
                    f"conditional {name.upper()} accounting audit drift"
                )
            if (
                declaration.get("path")
                != evidence["_files"][name]["relative_path"]
                or declaration.get("sha256")
                != evidence["_files"][name]["sha256"]
                or evidence[name].get("pass") is not True
                or embedded_trigger != trigger
                or embedded_hash
                != evidence["_files"]["trigger"]["sha256"]
            ):
                raise ValueError(f"conditional {name.upper()} amendment evidence drift")
        return "completed"
    renderer = _renderer_module()
    if (
        conditional.get("status") != "skipped"
        or conditional.get("reason") != renderer.SKIP_REASON
        or any(name in evidence for name in ("q2", "q3"))
    ):
        raise ValueError("conditional skip differs from the registered rule")
    return "skipped"


def _validate_compute(evidence: dict) -> float:
    compute = evidence.get("compute", {})
    ceiling = compute.get("ceiling_usd")
    total = compute.get("total_cost_usd")
    if not _is_number(ceiling) or float(ceiling) != 45.0:
        raise ValueError("compute ceiling is not the registered $45")
    if not _is_number(total) or float(total) > float(ceiling):
        raise ValueError("compute total exceeds the registered ceiling")
    phases = compute.get("phases")
    expected_phases = (
        {"q1", "q2_q3"}
        if evidence["trigger"]["run_q2_q3"]
        else {"q1"}
    )
    if not isinstance(phases, dict) or set(phases) != expected_phases:
        raise ValueError("compute billing records are missing")
    calculated = 0.0
    seen_app_ids = set()
    for phase_key, row in phases.items():
        phase = row.get("phase")
        if phase != EXPECTED_PHASE_LABELS[phase_key]:
            raise ValueError(f"compute phase binding is invalid for {phase_key}")
        cost = row.get("cost_usd")
        if (
            not _is_number(row.get("gpu_seconds"))
            or float(row["gpu_seconds"]) < 0
            or not _is_number(cost)
            or float(cost) < 0
        ):
            raise ValueError(f"billing numeric actuals are incomplete for {phase}")
        runs = row.get("runs")
        if (
            not isinstance(runs, list)
            or not runs
            or any(
                not isinstance(run, dict)
                or not isinstance(run.get("app_id"), str)
                or APP_ID_PATTERN.fullmatch(run["app_id"]) is None
                for run in runs
            )
        ):
            raise ValueError(f"billing app ID is incomplete for {phase}")
        app_ids = [run["app_id"] for run in runs]
        if (
            len(app_ids) != len(set(app_ids))
            or seen_app_ids.intersection(app_ids)
        ):
            raise ValueError(f"billing app ID is duplicated for {phase}")
        seen_app_ids.update(app_ids)
        source = row.get("source")
        source_match = (
            BILLING_SOURCE_PATTERN.fullmatch(source)
            if isinstance(source, str)
            else None
        )
        if source_match is None:
            raise ValueError(f"billing source is incomplete for {phase}")
        try:
            date.fromisoformat(source_match.group("date"))
        except ValueError as error:
            raise ValueError(f"billing date is invalid for {phase}") from error
        source_app_ids = APP_ID_PATTERN.findall(source_match.group("ids"))
        expected_noun = "app" if len(app_ids) == 1 else "apps"
        if (
            source_match.group("noun") != expected_noun
            or source_app_ids != app_ids
        ):
            raise ValueError(f"billing source is incomplete for {phase}")
        calculated += float(cost)
    if not math.isclose(calculated, float(total), rel_tol=0, abs_tol=1e-9):
        raise ValueError("compute total differs from billing records")
    return float(total)


def _validate_privacy(evidence: dict) -> str:
    privacy = evidence.get("privacy", {})
    if privacy != {
        "status": "local-private",
        "audience": ["Tyler", "Kevin"],
        "transmission_recorded": False,
    }:
        raise ValueError("privacy disposition is not local and untransmitted")
    return privacy["status"]


def validate_report_text(report: str, evidence: dict) -> dict:
    validate_q1_registration_schema(
        evidence["registration"],
        source_registration=Q1_REGISTRATION_SOURCE,
    )
    """Validate evidence and require byte-for-byte canonical report text."""

    _require_q1_registration_binding()
    _validate_file_hashes(evidence)
    _validate_source(evidence)
    _validate_q1(evidence)
    _validate_trigger(evidence)
    conditional_status = _validate_conditional(evidence)
    total = _validate_compute(evidence)
    privacy_status = _validate_privacy(evidence)
    _validate_loaded_evidence(evidence)

    unescaped_report = html.unescape(report)
    inspection_text = _inspection_text(unescaped_report)
    if (
        PUBLIC_URL_PATTERN.search(unescaped_report)
        or PUBLIC_URL_PATTERN.search(inspection_text)
    ):
        raise ValueError("report contains a public URL")
    if QUESTION_CELL_PATTERN.search(inspection_text):
        raise ValueError("report contains a question-mark result cell")
    if match := QWEN25_PATTERN.search(inspection_text):
        raise ValueError(f"report contains forbidden claim {match.group(0)}")
    if claim := _positive_claim(inspection_text):
        raise ValueError(f"report contains forbidden claim {claim}")
    if REQUIRED_HEADINGS - set(report.splitlines()):
        raise ValueError("report is missing a required heading")
    if "Private to Tyler and Kevin." not in report:
        raise ValueError("report is missing the private audience line")

    renderer = _renderer_module()
    if report != renderer.render_report(evidence):
        raise ValueError("report differs from deterministic evidence rendering")
    return {
        "pass": True,
        "conditional_status": conditional_status,
        "privacy_status": privacy_status,
        "total_cost_usd": total,
    }


def write_artifact_manifest(
    report_path: Path,
    evidence: dict,
    validation: dict,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict:
    """Write hashes and byte counts for the report and every loaded input."""

    report_path = Path(report_path)
    root = Path(evidence["_root"])
    entries = {
        report_path.resolve().relative_to(root.resolve()).as_posix(): {
            "sha256": _sha256(report_path),
            "bytes": report_path.stat().st_size,
        }
    }
    for metadata in evidence["_files"].values():
        entries[metadata["relative_path"]] = {
            "sha256": _sha256(metadata["path"]),
            "bytes": metadata["path"].stat().st_size,
        }
    manifest = {
        "validation": validation,
        "files": dict(sorted(entries.items())),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=1, allow_nan=False) + "\n"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-dir", type=Path, default=HERE)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    renderer = _renderer_module()
    evidence = renderer.load_evidence(args.plan_dir, root=args.root)
    report = args.report.read_text()
    result = validate_report_text(report, evidence)
    manifest = write_artifact_manifest(
        args.report, evidence, result, args.manifest
    )
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
