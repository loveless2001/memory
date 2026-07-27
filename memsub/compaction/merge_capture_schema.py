"""Pure schema helpers for resumable MergeCert Q2 capture chunks."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


REQUIRED_CAPTURE_KEYS = {
    "item_ids",
    "doc_ids",
    "domain",
    "pred_raw",
    "pred_merge",
    "y",
    "raw_correct",
    "in_e1",
    "locator_found",
    "merge_overlap",
    "mechanics",
    "sink_features",
    "residuals",
    "ratio",
    "source_manifest_sha256",
}


def locate_token_subsequence(
    tokens: Sequence[int], needle: Sequence[int]
) -> tuple[int, ...] | None:
    """Return the first exact token-subsequence span, or ``None``."""
    haystack = tuple(int(token) for token in tokens)
    target = tuple(int(token) for token in needle)
    if not target or len(target) > len(haystack):
        return None
    for start in range(len(haystack) - len(target) + 1):
        if haystack[start : start + len(target)] == target:
            return tuple(range(start, start + len(target)))
    return None


def _require_finite(name: str, values: np.ndarray) -> None:
    if not np.issubdtype(values.dtype, np.number):
        raise ValueError(f"{name} must be numeric")
    if not np.isfinite(values).all():
        raise ValueError(f"{name} must contain only finite values")


def validate_capture_chunk(
    arrays: dict[str, np.ndarray], *, expected_ratio: float
) -> dict:
    """Validate one immutable per-ratio Q2 NPZ chunk."""
    missing = REQUIRED_CAPTURE_KEYS - set(arrays)
    if missing:
        raise ValueError(f"capture chunk missing keys: {sorted(missing)}")
    ratio = np.asarray(arrays["ratio"])
    if ratio.shape != (1,) or not np.isclose(
        float(ratio[0]), expected_ratio, rtol=0, atol=1e-6
    ):
        raise ValueError("capture chunk ratio does not match its registered arm")
    source_hash = np.asarray(arrays["source_manifest_sha256"])
    if source_hash.shape != (1,) or not str(source_hash[0]):
        raise ValueError("capture chunk source manifest hash is missing")

    item_ids = np.asarray(arrays["item_ids"]).astype(str)
    rows = len(item_ids)
    if len(set(item_ids.tolist())) != rows:
        raise ValueError("capture chunk item IDs must be unique")
    row_keys = REQUIRED_CAPTURE_KEYS - {"ratio", "source_manifest_sha256"}
    for key in row_keys:
        values = np.asarray(arrays[key])
        if values.ndim == 0 or values.shape[0] != rows:
            raise ValueError(f"{key} first dimension must equal item count")

    mechanics = np.asarray(arrays["mechanics"])
    merge_overlap = np.asarray(arrays["merge_overlap"])
    sink_features = np.asarray(arrays["sink_features"])
    residuals = np.asarray(arrays["residuals"])
    if mechanics.shape != (rows, 4):
        raise ValueError("mechanics must have shape [N, 4]")
    if merge_overlap.shape != (rows,):
        raise ValueError("merge overlap must have shape [N]")
    if sink_features.shape != (rows, 8):
        raise ValueError("sink features must have shape [N, 8]")
    if residuals.shape != (rows, 37, 2560):
        raise ValueError("residual capture must have shape [N, 37, 2560]")
    _require_finite("mechanics", mechanics)
    _require_finite("merge overlap", merge_overlap)
    _require_finite("sink features", sink_features)
    _require_finite("residuals", residuals)
    if rows and (
        (mechanics[:, 0] < 1).any()
        or (mechanics[:, 1:] < -1e-6).any()
        or (mechanics[:, 1:] > 1 + 1e-6).any()
    ):
        raise ValueError("mechanics values lie outside registered ranges")
    if rows and (
        (merge_overlap < -1e-6).any() or (merge_overlap > 1 + 1e-6).any()
    ):
        raise ValueError("merge overlap lies outside [0, 1]")
    if rows and (
        (sink_features < -2e-3).any()
        or (sink_features > 1 + 2e-3).any()
    ):
        raise ValueError("sink features lie outside attention-mass ranges")

    for key in ("y", "raw_correct", "in_e1", "locator_found"):
        values = np.asarray(arrays[key])
        if rows and not np.isin(values, (0, 1)).all():
            raise ValueError(f"{key} must be binary")
    return {
        "rows": rows,
        "unique_item_ids": len(set(item_ids.tolist())),
        "locator_found": int(np.asarray(arrays["locator_found"]).sum()),
        "positive_labels": int(np.asarray(arrays["y"]).sum()),
    }
