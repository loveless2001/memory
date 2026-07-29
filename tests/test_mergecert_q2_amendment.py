import copy
import hashlib
import json

import numpy as np
import pytest

from memsub.certification.mergecert_q2_context import (
    Q2_ACCOUNTING_ARRAY_FIELDS,
    Q2_CONTEXT_MECHANICS_VERSION,
    derive_q2_context_window,
    expected_q2_plan_fields,
    load_q2_amendment,
    q2_accounting_sha256,
    validate_q2_accounting_arrays,
    validate_q2_accounting_row,
    validate_q2_context_length,
)
from memsub.compaction import build_merge_plan


PROVEN_SHORT_ITEMS = (
    "mcq_code/00130_1230_28",
    "mcq_code/00130_204_27",
    "mcq_code/00130_239_29",
)


def _row(
    context_tokens=4096,
    ratio=0.25,
    item_id="fixture/item-long_3000_0",
    anchor=3000,
):
    requested = int(context_tokens * ratio)
    document_tokens = 6000 if context_tokens == 4096 else context_tokens
    context_start = max(0, document_tokens - context_tokens)
    return {
        "item_id": item_id,
        "ratio": ratio,
        "context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
        "source_document_token_count": document_tokens,
        "source_context_start": context_start,
        "source_context_end": context_start + context_tokens,
        "source_context_token_count": context_tokens,
        "model_input_token_count": context_tokens,
        "source_chunk_token_start": anchor,
        "source_chunk_context_start": anchor - context_start,
        "requested_eviction_start": 4,
        "requested_eviction_end": 4 + requested,
        "requested_evicted_token_count": requested,
        "physical_before_count": context_tokens,
        "physical_after_count": context_tokens - requested,
        "physical_removed_count": requested,
        "retained_token_count": context_tokens - requested,
        "merge_target_retained": context_tokens - requested,
        "merge_recent_start": build_merge_plan(
            context_tokens, ratio, sink_token_count=4
        ).recent_start,
    }


def test_q2_window_preserves_long_reference_and_proven_short_items():
    long = derive_q2_context_window(6000, 3000, 1024)
    assert long == {
        "source_document_token_count": 6000,
        "source_context_start": 1904,
        "source_context_end": 6000,
        "source_context_token_count": 4096,
        "model_input_token_count": 4096,
        "source_chunk_token_start": 3000,
        "source_chunk_context_start": 1096,
    }
    for item_id in PROVEN_SHORT_ITEMS:
        chunk = int(item_id.split("_")[-2])
        short = derive_q2_context_window(4073, chunk, 0)
        assert short["source_context_start"] == 0
        assert short["source_context_end"] == 4073
        assert short["source_context_token_count"] == 4073
        assert short["source_chunk_token_start"] == chunk


def test_q2_protocol_rejects_eight_tokens_and_accepts_nine():
    with pytest.raises(ValueError, match="retained"):
        validate_q2_context_length(8)
    validate_q2_context_length(9)


def test_q2_protocol_rejects_contexts_above_the_4096_token_cap():
    with pytest.raises(ValueError, match="4096"):
        validate_q2_context_length(4097)


@pytest.mark.parametrize(
    ("ratio", "retained", "recent_start"),
    ((0.25, 3072, 2562), (0.40, 2458, 2869)),
)
def test_q2_long_context_plan_fields_are_unchanged(ratio, retained, recent_start):
    fields = expected_q2_plan_fields(4096, ratio)
    old = build_merge_plan(4096, ratio, sink_token_count=4)
    assert fields["merge_target_retained"] == retained
    assert fields["merge_recent_start"] == recent_start
    assert old.target_retained == retained
    assert old.recent_start == recent_start


def test_q2_accounting_accepts_literal_long_and_short_rows_and_arrays():
    rows = [
        _row(4096, 0.40, "fixture/item-long_3000_0"),
        _row(4073, 0.40, "mcq_code/00130_1230_28", 1230),
    ]
    manifests = [
        {"item_id": "fixture/item-long_3000_0", "chunk_rel_start": 0},
        {"item_id": "mcq_code/00130_1230_28", "chunk_rel_start": 0},
    ]
    assert validate_q2_accounting_row(rows[0], manifests[0], 0.40) == rows[0]
    arrays = {
        field: np.asarray([row[field] for row in rows])
        for field in Q2_ACCOUNTING_ARRAY_FIELDS
    }
    audit = validate_q2_accounting_arrays(arrays, manifests, 0.40)
    assert audit["rows"] == 2
    assert audit["short_context_rows"] == 1
    assert audit["minimum_context_tokens"] == 4073
    assert audit["maximum_context_tokens"] == 4096
    assert audit["accounting_sha256"] == q2_accounting_sha256(rows)


@pytest.mark.parametrize(
    ("name", "mutate", "match"),
    [
        ("boolean integer", lambda row: row.__setitem__("physical_before_count", True), "physical_before_count"),
        ("shifted context start", lambda row: row.__setitem__("source_context_start", 1), "source_context_start"),
        ("shifted context end", lambda row: row.__setitem__("source_context_end", 4095), "source_context_end"),
        ("shifted eviction start", lambda row: row.__setitem__("requested_eviction_start", 5), "requested_eviction_start"),
        ("shifted eviction end", lambda row: row.__setitem__("requested_eviction_end", 1027), "requested_eviction_end"),
        ("wrong requested count", lambda row: row.__setitem__("requested_evicted_token_count", 1023), "requested_evicted_token_count"),
        ("physical before mismatch", lambda row: row.__setitem__("physical_before_count", 4095), "physical_before_count"),
        ("physical after mismatch", lambda row: row.__setitem__("physical_after_count", 3073), "physical_after_count"),
        ("physical removed mismatch", lambda row: row.__setitem__("physical_removed_count", 1023), "physical_removed_count"),
        ("wrong retained count", lambda row: row.__setitem__("retained_token_count", 3071), "retained_token_count"),
        ("wrong merge target", lambda row: row.__setitem__("merge_target_retained", 3071), "merge_target_retained"),
        ("wrong recent start", lambda row: row.__setitem__("merge_recent_start", 2563), "merge_recent_start"),
        ("unregistered ratio", lambda row: row.__setitem__("ratio", 0.30), "ratio"),
        ("wrong mechanics version", lambda row: row.__setitem__("context_mechanics_version", "old"), "context_mechanics_version"),
    ],
)
def test_q2_accounting_rejects_each_named_break(name, mutate, match):
    row = _row()
    mutate(row)
    with pytest.raises(ValueError, match=match):
        validate_q2_accounting_row(
            row,
            {"item_id": "fixture/item-long_3000_0", "chunk_rel_start": 0},
            0.25,
        )


def test_q2_accounting_rejects_manifest_item_and_anchor_mismatch():
    with pytest.raises(ValueError, match="item_id"):
        validate_q2_accounting_row(
            _row(),
            {"item_id": "fixture/other_3000_0", "chunk_rel_start": 0},
            0.25,
        )
    with pytest.raises(ValueError, match="source_context_start"):
        validate_q2_accounting_row(
            _row(),
            {"item_id": "fixture/item-long_3000_0", "chunk_rel_start": 2000},
            0.25,
        )


def test_q2_accounting_rejects_coherently_shifted_absolute_chunk_anchor():
    row = _row(4073, 0.25, "mcq_code/00130_1230_28", 1230)
    row["source_chunk_token_start"] = 1240
    row["source_chunk_context_start"] = 1240

    with pytest.raises(ValueError, match="source_chunk_token_start"):
        validate_q2_accounting_row(
            row,
            {"item_id": "mcq_code/00130_1230_28", "chunk_rel_start": 0},
            0.25,
        )


@pytest.mark.parametrize("ratio", (0.2500005, 0.4000005))
def test_q2_accounting_rejects_near_registered_ratios(ratio):
    registered = 0.25 if ratio < 0.3 else 0.40
    row = _row(4096, registered)
    row["ratio"] = ratio

    with pytest.raises(ValueError, match="ratio"):
        validate_q2_accounting_row(
            row,
            {"item_id": "fixture/item-long_3000_0", "chunk_rel_start": 0},
            registered,
        )


def test_q2_amendment_is_exact_and_hash_bound(tmp_path):
    source = "plans/260728-mergecert-q1/q2-amendment.json"
    digest = hashlib.sha256(open(source, "rb").read()).hexdigest()
    amendment = load_q2_amendment(source, digest)
    assert amendment["protocol_version"] == "mergecert-q2-amended-v2"
    changed = copy.deepcopy(amendment)
    changed["ratios"] = [0.25]
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        load_q2_amendment(path, digest)
