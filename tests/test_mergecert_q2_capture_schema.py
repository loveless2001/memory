import numpy as np
import pytest

from memsub.compaction.merge_capture_schema import (
    locate_token_subsequence,
    validate_capture_chunk,
)


def _arrays(n=3, ratio=0.25):
    return {
        "item_ids": np.array([f"item-{i}" for i in range(n)]),
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
