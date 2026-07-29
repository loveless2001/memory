import numpy as np
import pytest
from pathlib import Path

from memsub.certification.mergecert_q2_context import (
    Q2_CONTEXT_MECHANICS_VERSION,
)
from memsub.compaction.merge_capture_schema import (
    locate_token_subsequence,
    validate_capture_chunk,
)


def _arrays(n=3, ratio=0.25):
    arrays = {
        "item_ids": np.array(
            [
                "fixture/item-0_3000_0",
                "mcq_code/00130_1230_28",
                "fixture/item-2_3000_0",
            ][:n]
        ),
        "doc_ids": np.array([f"doc-{i}" for i in range(n)]),
        "domain": np.array(
            ["financial", "legal", "code", "literature"][:n]
        ),
        "pred_raw": np.array(["A"] * n),
        "pred_merge": np.array(["A"] * n),
        "y": np.zeros(n, dtype=np.int8),
        "raw_correct": np.ones(n, dtype=np.int8),
        "in_e1": np.zeros(n, dtype=np.int8),
        "locator_found": np.ones(n, dtype=np.int8),
        "merge_overlap": np.full(n, 0.75, dtype=np.float32),
        "mechanics": np.tile(
            np.array([[2.0, 0.5, 0.25, 0.75]], dtype=np.float32),
            (n, 1),
        ),
        "sink_features": np.tile(
            np.array([[0.8, 0.1] * 4], dtype=np.float32), (n, 1)
        ),
        "residuals": np.zeros((n, 37, 2560), dtype=np.float16),
        "ratio": np.array([ratio], dtype=np.float32),
        "source_manifest_sha256": np.array(["manifest-sha"]),
    }
    if n != 3 or ratio != 0.25:
        raise ValueError("the literal amended-Q2 fixture is fixed at 3 rows")
    arrays.update(
        {
            "item_id": np.array(
                [
                    "fixture/item-0_3000_0",
                    "mcq_code/00130_1230_28",
                    "fixture/item-2_3000_0",
                ]
            ),
            "ratio": np.full(3, 0.25, dtype=np.float64),
            "context_mechanics_version": np.array(
                [Q2_CONTEXT_MECHANICS_VERSION] * 3
            ),
            "source_document_token_count": np.array(
                [6000, 4073, 5000], dtype=np.int64
            ),
            "source_context_start": np.array(
                [1904, 0, 904], dtype=np.int64
            ),
            "source_context_end": np.array(
                [6000, 4073, 5000], dtype=np.int64
            ),
            "source_context_token_count": np.array(
                [4096, 4073, 4096], dtype=np.int64
            ),
            "model_input_token_count": np.array(
                [4096, 4073, 4096], dtype=np.int64
            ),
            "source_chunk_token_start": np.array(
                [3000, 1230, 3000], dtype=np.int64
            ),
            "source_chunk_context_start": np.array(
                [1096, 1230, 2096], dtype=np.int64
            ),
            "requested_eviction_start": np.array([4, 4, 4], dtype=np.int64),
            "requested_eviction_end": np.array(
                [1028, 1022, 1028], dtype=np.int64
            ),
            "requested_evicted_token_count": np.array(
                [1024, 1018, 1024], dtype=np.int64
            ),
            "physical_before_count": np.array(
                [4096, 4073, 4096], dtype=np.int64
            ),
            "physical_after_count": np.array(
                [3072, 3055, 3072], dtype=np.int64
            ),
            "physical_removed_count": np.array(
                [1024, 1018, 1024], dtype=np.int64
            ),
            "retained_token_count": np.array(
                [3072, 3055, 3072], dtype=np.int64
            ),
            "merge_target_retained": np.array(
                [3072, 3055, 3072], dtype=np.int64
            ),
            "merge_recent_start": np.array(
                [2562, 2548, 3127], dtype=np.int64
            ),
            "capture_chunk_schema": np.array(["mergecert-q2-capture-chunk-v2"]),
            "q2_protocol_version": np.array(["mergecert-q2-amended-v2"]),
            "q2_namespace_version": np.array(["mergecert-q2-amended-v2"]),
            "q2_amendment_json": np.array(
                [
                    Path(
                        "plans/260728-mergecert-q1/q2-amendment.json"
                    ).read_text()
                ]
            ),
            "q2_amendment_sha256": np.array(
                ["7b510a5b0af827516894fe806281cfa877e2234135dccc297c8d8bd823a87b0a"]
            ),
        }
    )
    return arrays


def test_locate_token_subsequence_returns_every_exact_span_position():
    assert locate_token_subsequence([1, 2, 3, 2, 3, 4], [2, 3]) == (1, 2)
    assert locate_token_subsequence([1, 2, 3], [8]) is None
    assert locate_token_subsequence([1, 2, 3], []) is None


def test_capture_chunk_schema_accepts_aligned_finite_arrays():
    audit = validate_capture_chunk(_arrays(), expected_ratio=0.25)

    assert audit["rows"] == 3
    assert audit["unique_item_ids"] == 3
    assert audit["locator_found"] == 3
    assert audit["positive_labels"] == 0


def test_capture_chunk_schema_accepts_legacy_singleton_and_amended_row_ratios():
    legacy = _arrays()
    legacy["ratio"] = np.array([0.25], dtype=np.float64)
    amended = _arrays()

    assert validate_capture_chunk(legacy, expected_ratio=0.25)["rows"] == 3
    assert validate_capture_chunk(amended, expected_ratio=0.25)["rows"] == 3


@pytest.mark.parametrize(
    "ratio",
    (
        np.array([0.2500005], dtype=np.float64),
        np.full(3, 0.2500005, dtype=np.float64),
    ),
)
def test_capture_chunk_schema_rejects_near_registered_ratios(ratio):
    arrays = _arrays()
    arrays["ratio"] = ratio

    with pytest.raises(ValueError, match="ratio"):
        validate_capture_chunk(arrays, expected_ratio=0.25)


@pytest.mark.parametrize(
    "ratio",
    (
        np.array([0.25, 0.40, 0.25], dtype=np.float64),
        np.array([[0.25, 0.25, 0.25]], dtype=np.float64),
        np.array([0.25, np.nan, 0.25], dtype=np.float64),
    ),
)
def test_capture_chunk_schema_rejects_mixed_wrong_shape_or_nonfinite_ratios(ratio):
    arrays = _arrays()
    arrays["ratio"] = ratio

    with pytest.raises(ValueError, match="ratio"):
        validate_capture_chunk(arrays, expected_ratio=0.25)


def test_q2_capture_arrays_reject_short_rows_with_fixed_4096_mechanics(
    monkeypatch,
):
    from tests.test_mergecert_campaign_contract import _load_module, Q2_RUNNER

    runner = _load_module(Q2_RUNNER, "mergecert_q2_capture_arrays")
    monkeypatch.setattr(
        runner,
        "Q2_AMENDMENT_IMAGE_PATH",
        "plans/260728-mergecert-q1/q2-amendment.json",
    )
    arrays = _arrays()
    expected_rows = [
        {
                "item_id": "fixture/item-0_3000_0", "doc_id": "doc-0", "domain": "financial",
            "pred_raw": "A", "raw_correct": 1, "in_e1": 0,
            "chunk_rel_start": 1096,
        },
        {
                "item_id": "mcq_code/00130_1230_28", "doc_id": "doc-1", "domain": "legal",
            "pred_raw": "A", "raw_correct": 1, "in_e1": 0,
            "chunk_rel_start": 1230,
        },
        {
                "item_id": "fixture/item-2_3000_0", "doc_id": "doc-2", "domain": "code",
            "pred_raw": "A", "raw_correct": 1, "in_e1": 0,
            "chunk_rel_start": 2096,
        },
    ]
    arrays["source_context_token_count"][1] = 4096
    arrays["model_input_token_count"][1] = 4096
    arrays["source_context_end"][1] = 4096
    arrays["physical_before_count"][1] = 4096
    arrays["physical_after_count"][1] = 3072
    arrays["requested_eviction_end"][1] = 1028
    arrays["requested_evicted_token_count"][1] = 1024
    arrays["physical_removed_count"][1] = 1024
    arrays["retained_token_count"][1] = 3072
    arrays["merge_target_retained"][1] = 3072
    arrays["merge_recent_start"][1] = 2562

    with pytest.raises(ValueError, match="source_context"):
        runner._validate_capture_arrays(
            arrays,
            expected_rows=expected_rows,
            expected_ratio=0.25,
            manifest_sha256="manifest-sha",
            label="test chunk",
        )


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda z: z.update(item_ids=np.array(["dup", "dup", "x"])), "unique"),
        (lambda z: z.update(mechanics=np.zeros((2, 4))), "first dimension"),
        (
            lambda z: z["mechanics"].__setitem__((0, 1), 1.5),
            "mechanics",
        ),
        (
            lambda z: z["sink_features"].__setitem__((0, 0), np.nan),
            "finite",
        ),
        (
            lambda z: z.update(residuals=np.zeros((3, 36, 2560))),
            "residual",
        ),
        (
            lambda z: z.update(ratio=np.array([0.40], dtype=np.float32)),
            "ratio",
        ),
    ],
)
def test_capture_chunk_schema_fails_closed_on_corruption(mutation, match):
    arrays = _arrays()
    mutation(arrays)

    with pytest.raises(ValueError, match=match):
        validate_capture_chunk(arrays, expected_ratio=0.25)
