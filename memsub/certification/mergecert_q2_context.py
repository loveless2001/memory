"""Pure, fail-closed accounting for the settled MergeCert Q2 amendment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from memsub.compaction import build_merge_plan


Q2_AMENDMENT_SCHEMA = "mergecert-q2-amendment-v1"
Q2_PROTOCOL_VERSION = "mergecert-q2-amended-v2"
Q2_CONTEXT_MECHANICS_VERSION = "mergecert-q2-context-mechanics-v2"
Q2_NAMESPACE_VERSION = "mergecert-q2-amended-v2"
Q2_RATIOS = (0.25, 0.40)
Q2_SINK_TOKEN_COUNT = 4
Q2_REFERENCE_CONTEXT_TOKENS = 4096
Q2_MINIMUM_CONTEXT_TOKENS = 9

Q2_ACCOUNTING_INTEGER_FIELDS = (
    "source_document_token_count",
    "source_context_start",
    "source_context_end",
    "source_context_token_count",
    "model_input_token_count",
    "source_chunk_token_start",
    "source_chunk_context_start",
    "requested_eviction_start",
    "requested_eviction_end",
    "requested_evicted_token_count",
    "physical_before_count",
    "physical_after_count",
    "physical_removed_count",
    "retained_token_count",
    "merge_target_retained",
    "merge_recent_start",
)
Q2_ACCOUNTING_ARRAY_FIELDS = (
    "item_id",
    "ratio",
    "context_mechanics_version",
    *Q2_ACCOUNTING_INTEGER_FIELDS,
)

_AMENDMENT_PAYLOAD = {
    "schema": Q2_AMENDMENT_SCHEMA,
    "protocol": "MERGECERT-Q2",
    "protocol_version": Q2_PROTOCOL_VERSION,
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
    "sink_token_count": Q2_SINK_TOKEN_COUNT,
    "reference_context_tokens": Q2_REFERENCE_CONTEXT_TOKENS,
    "minimum_context_tokens": Q2_MINIMUM_CONTEXT_TOKENS,
    "budget_mode": "per-item-actual-context-matched-physical-v2",
    "context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
    "namespace_version": Q2_NAMESPACE_VERSION,
    "remote_root": "/artifacts/mergecert/q2-amended-v2",
    "context_rule": "canonical registered source window capped at 4096 pinned-tokenizer tokens",
    "requested_eviction_rule": "floor(source_context_token_count * ratio) from logical position 4",
    "physical_budget_rule": "measure removal on an independent full-cache clone and give merge the measured retained count",
    "merge_plan_rule": "build_merge_plan(source_context_token_count, exact registered ratio, sink_token_count=4)",
    "legacy_fixed_context_evidence_authorizes": False,
    "forbidden": [
        "padding", "runtime-skip", "replacement", "population-filter",
        "label-change", "silent-budget-change", "legacy-state-resume",
    ],
    "rerun_gate": {
        "new_pilot_items": 16,
        "pilot_review_required_before_fleet": True,
        "new_fleet_slices": 8,
        "fleet_items": 30847,
        "fresh_authorization_required": True,
    },
}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _require_int(row: dict, field: str) -> int:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be a non-boolean integer")
    return value


def _require_ratio(value: object, expected_ratio: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("ratio must be an exact registered ratio")
    ratio = float(value)
    if ratio not in Q2_RATIOS or (expected_ratio is not None and ratio != expected_ratio):
        raise ValueError("ratio does not match the registered arm")
    return ratio


def load_q2_amendment(path: str | Path, expected_sha256: str | None = None) -> dict:
    """Load the sole Q2 authority, optionally binding its byte digest."""
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("q2 amendment sha256 does not match")
    try:
        amendment = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("q2 amendment is not valid JSON") from exc
    if amendment != _AMENDMENT_PAYLOAD:
        raise ValueError("q2 amendment payload is not the settled authority")
    return amendment


def derive_q2_context_window(document_tokens: int, chunk_token_start: int, chunk_rel_start: int) -> dict:
    """Clamp the registered source window without padding short documents."""
    for name, value in (("document_tokens", document_tokens), ("chunk_token_start", chunk_token_start), ("chunk_rel_start", chunk_rel_start)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be a non-boolean integer")
    if document_tokens <= 0 or not 0 <= chunk_token_start < document_tokens or chunk_rel_start < 0:
        raise ValueError("invalid source document or chunk anchor")
    context_start = min(
        max(0, chunk_token_start - chunk_rel_start),
        max(0, document_tokens - Q2_REFERENCE_CONTEXT_TOKENS),
    )
    context_end = min(document_tokens, context_start + Q2_REFERENCE_CONTEXT_TOKENS)
    context_tokens = context_end - context_start
    return {
        "source_document_token_count": document_tokens,
        "source_context_start": context_start,
        "source_context_end": context_end,
        "source_context_token_count": context_tokens,
        "model_input_token_count": context_tokens,
        "source_chunk_token_start": chunk_token_start,
        "source_chunk_context_start": chunk_token_start - context_start,
    }


def validate_q2_context_length(context_tokens: int) -> None:
    if isinstance(context_tokens, bool) or not isinstance(context_tokens, int):
        raise ValueError("context_tokens must be a non-boolean integer")
    for ratio in Q2_RATIOS:
        plan = build_merge_plan(context_tokens, ratio, sink_token_count=Q2_SINK_TOKEN_COUNT)
        requested = int(context_tokens * ratio)
        expected_target = context_tokens - requested
        if plan.target_retained != expected_target or plan.target_retained - Q2_SINK_TOKEN_COUNT < 2:
            raise ValueError("Q2 context violates the amended retained budget")


def expected_q2_plan_fields(context_tokens: int, ratio: float) -> dict:
    validate_q2_context_length(context_tokens)
    ratio = _require_ratio(ratio)
    plan = build_merge_plan(context_tokens, ratio, sink_token_count=Q2_SINK_TOKEN_COUNT)
    requested = int(context_tokens * ratio)
    if plan.target_retained != context_tokens - requested:
        raise ValueError("merge_target_retained violates the amended budget")
    return {
        "requested_eviction_start": Q2_SINK_TOKEN_COUNT,
        "requested_eviction_end": Q2_SINK_TOKEN_COUNT + requested,
        "requested_evicted_token_count": requested,
        "retained_token_count": plan.target_retained,
        "merge_target_retained": plan.target_retained,
        "merge_recent_start": plan.recent_start,
    }


def validate_q2_accounting_row(row: dict, manifest_row: dict | None = None, expected_ratio: float | None = None) -> dict:
    """Validate one complete amended-Q2 accounting record."""
    if not isinstance(row, dict):
        raise ValueError("accounting row must be a dict")
    missing = set(Q2_ACCOUNTING_ARRAY_FIELDS) - set(row)
    if missing:
        raise ValueError(f"accounting row missing fields: {sorted(missing)}")
    for field in Q2_ACCOUNTING_INTEGER_FIELDS:
        _require_int(row, field)
    if not isinstance(row["item_id"], str) or not row["item_id"]:
        raise ValueError("item_id must be a non-empty string")
    ratio = _require_ratio(row["ratio"], expected_ratio)
    if row["context_mechanics_version"] != Q2_CONTEXT_MECHANICS_VERSION:
        raise ValueError("context_mechanics_version does not match the amendment")
    n = row["source_context_token_count"]
    validate_q2_context_length(n)
    if row["model_input_token_count"] != n:
        raise ValueError("model_input_token_count does not match source_context_token_count")
    if row["source_context_end"] - row["source_context_start"] != n:
        raise ValueError("source_context_end does not match source_context_start")
    if not 0 <= row["source_context_start"] <= row["source_context_end"] <= row["source_document_token_count"]:
        raise ValueError("source_context_start/source_context_end lie outside source document")
    if row["source_chunk_context_start"] != row["source_chunk_token_start"] - row["source_context_start"]:
        raise ValueError("source_chunk_context_start does not match source_chunk_token_start")
    expected = expected_q2_plan_fields(n, ratio)
    for field in ("requested_eviction_start", "requested_eviction_end", "requested_evicted_token_count", "retained_token_count", "merge_target_retained", "merge_recent_start"):
        if row[field] != expected[field]:
            raise ValueError(f"{field} does not match amended Q2 accounting")
    if row["physical_before_count"] != n:
        raise ValueError("physical_before_count does not match source_context_token_count")
    if row["physical_after_count"] != row["retained_token_count"]:
        raise ValueError("physical_after_count does not match retained_token_count")
    if row["physical_removed_count"] != row["requested_evicted_token_count"]:
        raise ValueError("physical_removed_count does not match requested_evicted_token_count")
    if row["physical_before_count"] - row["physical_after_count"] != row["physical_removed_count"]:
        raise ValueError("physical_before_count/physical_after_count mismatch")
    if manifest_row is not None:
        if row["item_id"] != manifest_row.get("item_id"):
            raise ValueError("item_id does not match manifest row")
        window = derive_q2_context_window(
            row["source_document_token_count"], row["source_chunk_token_start"], manifest_row.get("chunk_rel_start")
        )
        for field in ("source_context_start", "source_context_end", "source_context_token_count", "model_input_token_count", "source_chunk_context_start"):
            if row[field] != window[field]:
                raise ValueError(f"{field} does not match manifest anchor")
    return {field: row[field] for field in Q2_ACCOUNTING_ARRAY_FIELDS}


def _array_value(value: object) -> object:
    return value.item() if hasattr(value, "item") else value


def validate_q2_accounting_arrays(arrays: dict, expected_rows: list[dict], expected_ratio: float) -> dict:
    """Reconstruct, validate, and fingerprint ordered accounting arrays."""
    _require_ratio(expected_ratio, expected_ratio)
    missing = set(Q2_ACCOUNTING_ARRAY_FIELDS) - set(arrays)
    if missing:
        raise ValueError(f"accounting arrays missing fields: {sorted(missing)}")
    rows = len(expected_rows)
    for field in Q2_ACCOUNTING_ARRAY_FIELDS:
        try:
            size = len(arrays[field])
        except TypeError as exc:
            raise ValueError(f"{field} must be a one-dimensional accounting array") from exc
        if size != rows:
            raise ValueError(f"{field} length does not match expected manifest rows")
    validated = []
    for index, manifest_row in enumerate(expected_rows):
        row = {field: _array_value(arrays[field][index]) for field in Q2_ACCOUNTING_ARRAY_FIELDS}
        validated.append(validate_q2_accounting_row(row, manifest_row, expected_ratio))
    contexts = [row["source_context_token_count"] for row in validated]
    return {
        "schema": "mergecert-q2-accounting-audit-v1",
        "rows": rows,
        "ratio": expected_ratio,
        "short_context_rows": sum(value < Q2_REFERENCE_CONTEXT_TOKENS for value in contexts),
        "minimum_context_tokens": min(contexts) if contexts else 0,
        "maximum_context_tokens": max(contexts) if contexts else 0,
        "accounting_sha256": q2_accounting_sha256(validated),
    }


def q2_accounting_sha256(rows: list[dict]) -> str:
    """Return a canonical ordered SHA-256 that includes item IDs and ratios."""
    normalized = [
        {field: row[field] for field in Q2_ACCOUNTING_ARRAY_FIELDS}
        for row in rows
    ]
    return hashlib.sha256(_canonical_json(normalized)).hexdigest()
