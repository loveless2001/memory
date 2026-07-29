"""MERGECERT Q2 — private unified merge relabel and capture fleet.

One real-attention prefill feeds both registered merge ratios.  Each immutable
NPZ chunk binds labels, visible merge mechanics, sink-head monitor features,
and all 37 last-prompt residual vectors to the same item order.
"""

import hashlib
import json
import math
import os
import time
from collections import Counter

import modal

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
RATIOS = (0.25, 0.40)
CTX = 4096
SINKS = 4
Q2_PROTOCOL_VERSION = "mergecert-q2-amended-v2"
Q2_CONTEXT_MECHANICS_VERSION = "mergecert-q2-context-mechanics-v2"
Q2_NAMESPACE_VERSION = "mergecert-q2-amended-v2"
CAPTURE_STATE_SCHEMA = "mergecert-q2-capture-state-v2"
CAPTURE_CHUNK_SCHEMA = "mergecert-q2-capture-chunk-v2"
CAPTURE_ROOT = "/artifacts/mergecert/q2-amended-v2"
LEGACY_CAPTURE_ROOT = "/artifacts/mergecert/q2"
Q2_AMENDMENT_IMAGE_PATH = (
    "/root/repo/plans/260728-mergecert-q1/q2-amendment.json"
)
Q2_AMENDMENT_SHA256 = (
    "7b510a5b0af827516894fe806281cfa877e2234135dccc297c8d8bd823a87b0a"
)
Q2_ITEMS = 30_847
Q2_SLICES = 8
CHUNK_ITEMS = 100
PILOT_ITEMS = 16
REGISTERED_PILOT_TAG = "amended-v2"
ANSWER_LETTERS = ("A", "B", "C", "D")
FINGERPRINT_SCHEMA = "memsub-compatibility-fingerprint-v1"
PILOT_VERDICT_SCHEMA = "mergecert-q2-pilot-verdict-v3-amended"
PILOT_VALIDATOR_VERSION = "mergecert-q2-pilot-validator-v3-amended"
PILOT_VERDICT_FILENAME = "pilot-verdict.json"
CAPTURE_SUMMARY_SCHEMA = "mergecert-q2-capture-summary-v2"
MANIFEST_PATH = "/artifacts/probe/capture-manifest.json"
Q1_TRIGGER_PATH = "/artifacts/mergecert-q1/q1-trigger.json"
Q1_TRIGGER_SHA256 = (
    "009d1ba2879b76174c13dffbea27a458b10d9a859cdb69046f3afac31a2af5a1"
)
Q1_BUDGET_MODE = "archived-m1-per-document-matched-physical-v1"
Q1_ADDENDUM_SHA256 = (
    "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509"
)
Q1_P0_VERDICT_SHA256 = (
    "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
)
HEADS = ((25, 14), (26, 26), (28, 19), (35, 15))
DOMAINS = ("financial", "legal", "code", "literature")
PINNED = (
    "torch==2.7.1",
    "transformers==4.55.2",
    "safetensors==0.5.3",
    "numpy>=1.26,<3",
    "hf_transfer",
)

app = modal.App("memsub-mergecert-q2-amended-v2-capture")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "MEMSUB_REFERENCE": "1"})
    .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
    .add_local_file(
        "plans/260728-mergecert-q1/q2-amendment.json",
        Q2_AMENDMENT_IMAGE_PATH,
    )
    .add_local_python_source("memsub")
)
hf_cache = modal.Volume.from_name("memsub-hf-cache", create_if_missing=True)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/root/.cache/huggingface": hf_cache, "/artifacts": artifacts}


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_q2_amendment(
    path: str | None = None,
) -> dict:
    """Load the exact amendment before touching its artifact namespace."""
    from memsub.certification import load_q2_amendment

    path = path or Q2_AMENDMENT_IMAGE_PATH
    amendment = load_q2_amendment(path, Q2_AMENDMENT_SHA256)
    with open(path, encoding="utf-8") as handle:
        encoded = handle.read()
    if _sha256_file(path) != Q2_AMENDMENT_SHA256:
        raise ValueError("Q2 amendment image bytes do not match the authority")
    return {
        "q2_amendment": amendment,
        "q2_amendment_json": encoded,
        "q2_amendment_sha256": Q2_AMENDMENT_SHA256,
        "q2_amendment_image_path": path,
    }


def _measure_q2_budget(
    full_cache, *, context_tokens: int, ratio: float
):
    """Measure the exact budget on a detached cache, never the source cache."""
    from memsub.certification import (
        expected_q2_plan_fields,
        validate_q2_accounting_row,
        validate_q2_context_length,
    )
    from memsub.compaction import build_merge_plan

    validate_q2_context_length(context_tokens)
    if full_cache.physical_length != context_tokens:
        raise ValueError("full cache length does not match the Q2 context")
    plan = build_merge_plan(context_tokens, ratio, sink_token_count=SINKS)
    expected = expected_q2_plan_fields(context_tokens, ratio)
    work = full_cache.clone_detached()
    physical_before = work.physical_length
    requested_start = expected["requested_eviction_start"]
    requested_end = expected["requested_eviction_end"]
    physical_removed = work.evict_logical_range(
        requested_start, requested_end
    )
    physical_after = work.physical_length
    accounting = {
        **expected,
        "physical_before_count": physical_before,
        "physical_after_count": physical_after,
        "physical_removed_count": physical_removed,
    }
    validation_row = {
        "item_id": "runtime-budget",
        "ratio": ratio,
        "context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
        "source_document_token_count": context_tokens,
        "source_context_start": 0,
        "source_context_end": context_tokens,
        "source_context_token_count": context_tokens,
        "model_input_token_count": context_tokens,
        "source_chunk_token_start": 0,
        "source_chunk_context_start": 0,
        **accounting,
    }
    validate_q2_accounting_row(validation_row, expected_ratio=ratio)
    if (
        plan.target_retained != accounting["merge_target_retained"]
        or plan.recent_start != accounting["merge_recent_start"]
    ):
        raise ValueError("measured Q2 budget differs from its merge plan")
    return accounting, plan


def _item_ids_sha256(item_ids: list[str]) -> str:
    encoded = json.dumps(
        item_ids, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _canonical_json_bytes(value) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()


def _fingerprint_record(fingerprint) -> dict:
    from memsub.fingerprint import CompatibilityFingerprint, FIELDS

    value = fingerprint.to_dict()
    if set(value) != set(FIELDS):
        raise ValueError("Q2 live compatibility fingerprint schema mismatch")
    canonical = CompatibilityFingerprint.from_dict(value)
    if canonical.to_dict() != value:
        raise ValueError("Q2 live compatibility fingerprint is noncanonical")
    return {
        "compatibility_fingerprint_schema": FINGERPRINT_SCHEMA,
        "compatibility_fingerprint": value,
        "compatibility_fingerprint_sha256": canonical.digest(),
    }


def _validate_fingerprint_record(
    state: dict, expected: dict | None = None
) -> dict:
    from memsub.fingerprint import CompatibilityFingerprint, FIELDS

    value = state.get("compatibility_fingerprint")
    if (
        state.get("compatibility_fingerprint_schema") != FINGERPRINT_SCHEMA
        or not isinstance(value, dict)
        or set(value) != set(FIELDS)
    ):
        raise ValueError("Q2 compatibility fingerprint schema mismatch")
    try:
        canonical = CompatibilityFingerprint.from_dict(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Q2 compatibility fingerprint is invalid") from exc
    record = {
        "compatibility_fingerprint_schema": FINGERPRINT_SCHEMA,
        "compatibility_fingerprint": canonical.to_dict(),
        "compatibility_fingerprint_sha256": canonical.digest(),
    }
    pinned = canonical.to_dict()
    if (
        canonical.to_dict() != value
        or state.get("compatibility_fingerprint_sha256")
        != canonical.digest()
        or not pinned["model_id"].startswith(f"{MODEL_ID}#cfg=sha256:")
        or pinned["attention_impl"] != "sdpa"
        or pinned["quantization"] != "bfloat16"
        or not pinned["runtime_version"].startswith(
            "hf-transformers-4.55.2+torch-2.7.1"
        )
        or (
            expected is not None
            and any(state.get(key) != expected.get(key) for key in record)
        )
    ):
        raise ValueError(
            "Q2 compatibility fingerprint differs from registered runtime"
        )
    return record


def _registered_pilot_dir() -> str:
    return f"{CAPTURE_ROOT}/pilot-{REGISTERED_PILOT_TAG}"


def _registered_pilot_verdict_path() -> str:
    return f"{_registered_pilot_dir()}/{PILOT_VERDICT_FILENAME}"


def _require_q1_trigger(path: str = Q1_TRIGGER_PATH) -> dict:
    from memsub.certification import load_q1_trigger

    try:
        return load_q1_trigger(path)
    except (FileNotFoundError, OSError) as exc:
        raise ValueError("Q2 is blocked until q1-trigger.json exists") from exc


def _validate_manifest_rows(manifest: list[dict]) -> None:
    from memsub.certification import eq_policy_v1

    required = {
        "item_id",
        "doc_id",
        "domain",
        "question",
        "options",
        "gold",
        "pred_raw",
        "chunk_rel_start",
        "y",
        "in_e1",
        "raw_correct",
        "pilot",
    }
    for index, row in enumerate(manifest):
        if not isinstance(row, dict) or not required <= set(row):
            raise ValueError(f"Q2 manifest row {index} schema mismatch")
        if (
            not isinstance(row["item_id"], str)
            or not row["item_id"]
            or not isinstance(row["doc_id"], str)
            or not row["doc_id"]
            or row["domain"] not in DOMAINS
            or not isinstance(row["question"], str)
            or not row["question"]
            or not isinstance(row["options"], list)
            or len(row["options"]) != len(ANSWER_LETTERS)
            or not all(
                isinstance(option, str) and bool(option.strip())
                for option in row["options"]
            )
            or row["gold"] not in ANSWER_LETTERS
            or row["pred_raw"] not in ANSWER_LETTERS
            or type(row["chunk_rel_start"]) is not int
            or row["chunk_rel_start"] < 0
            or type(row["y"]) is not int
            or row["y"] not in (0, 1)
            or type(row["in_e1"]) is not int
            or row["in_e1"] not in (0, 1)
            or type(row["raw_correct"]) is not int
            or row["raw_correct"] not in (0, 1)
            or type(row["pilot"]) is not int
            or row["pilot"] not in (0, 1)
            or row["raw_correct"]
            != int(eq_policy_v1(row["pred_raw"], row["gold"]))
        ):
            raise ValueError(f"Q2 manifest row {index} is invalid")


def _sorted_manifest() -> tuple[list[dict], str]:
    with open(MANIFEST_PATH) as handle:
        manifest = json.load(handle)
    if len(manifest) != Q2_ITEMS:
        raise ValueError(
            f"Q2 manifest must contain {Q2_ITEMS} rows, found {len(manifest)}"
        )
    item_ids = [row["item_id"] for row in manifest]
    if len(set(item_ids)) != Q2_ITEMS:
        raise ValueError("Q2 manifest item IDs must be unique")
    _validate_manifest_rows(manifest)
    manifest.sort(key=lambda row: (row["domain"], row["doc_id"], row["item_id"]))
    return manifest, _sha256_file(MANIFEST_PATH)


def _set_attention_mode(model, mode: str) -> None:
    model.config._attn_implementation = mode
    for layer in model.model.layers:
        layer.self_attn.config._attn_implementation = mode


def _answer_capture(runtime, cache, row: dict) -> tuple[str, list, list]:
    import numpy as np
    import torch

    model, tokenizer = runtime.model, runtime.tokenizer
    letters = ("A", "B", "C", "D")
    letter_ids = [
        tokenizer.encode(f" {letter}", add_special_tokens=False)[-1]
        for letter in letters
    ]
    options = "\n".join(
        f"{letter}. {option}"
        for letter, option in zip(letters, row["options"])
    )
    prompt = (
        f"\n\nQuestion: {row['question']}\n{options}\n"
        "Answer with a single letter.\nAnswer:"
    )
    prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
    work = cache.clone_detached()
    physical = work.physical_length
    logical = work.next_logical_position
    _set_attention_mode(model, "eager")
    try:
        with torch.inference_mode():
            count = len(prompt_ids)
            output = model(
                input_ids=torch.tensor(
                    [prompt_ids], dtype=torch.long, device=runtime.device
                ),
                attention_mask=torch.ones(
                    (1, physical + count),
                    dtype=torch.long,
                    device=runtime.device,
                ),
                position_ids=torch.arange(
                    logical, logical + count, device=runtime.device
                ).unsqueeze(0),
                past_key_values=work,
                cache_position=torch.arange(
                    physical, physical + count, device=runtime.device
                ),
                use_cache=True,
                output_attentions=True,
                output_hidden_states=True,
            )
        logits = output.logits[0, -1].float()
        scores = [float(logits[token_id]) for token_id in letter_ids]
        prediction = letters[scores.index(max(scores))]
        features = []
        for layer_index, head_index in HEADS:
            attention = output.attentions[layer_index][
                0, head_index, -1, :physical
            ].float()
            features.extend(
                [
                    float(attention[SINKS:physical].sum()),
                    float(attention[:SINKS].sum()),
                ]
            )
        residuals = np.stack(
            [
                hidden[0, -1].float().cpu().numpy()
                for hidden in output.hidden_states
            ]
        ).astype(np.float16)
    finally:
        _set_attention_mode(model, "sdpa")
    if residuals.shape != (37, 2560):
        raise ValueError(f"unexpected residual shape {residuals.shape}")
    return prediction, features, residuals


def _write_npz_atomic(path: str, arrays: dict) -> None:
    import numpy as np

    temporary = f"{path}.partial"
    with open(temporary, "wb") as handle:
        np.savez(handle, **arrays)
    os.replace(temporary, path)


def _stack_chunk(
    rows: list[dict], *, ratio: float, source_hash: str, amendment: dict
) -> dict:
    import numpy as np

    from memsub.certification import Q2_ACCOUNTING_INTEGER_FIELDS

    arrays = {
        "item_ids": np.asarray([row["item_id"] for row in rows]),
        "doc_ids": np.asarray([row["doc_id"] for row in rows]),
        "domain": np.asarray([row["domain"] for row in rows]),
        "pred_raw": np.asarray([row["pred_raw"] for row in rows]),
        "pred_merge": np.asarray([row["pred_merge"] for row in rows]),
        "y": np.asarray([row["y"] for row in rows], dtype=np.int8),
        "raw_correct": np.asarray(
            [row["raw_correct"] for row in rows], dtype=np.int8
        ),
        "in_e1": np.asarray([row["in_e1"] for row in rows], dtype=np.int8),
        "locator_found": np.asarray(
            [row["locator_found"] for row in rows], dtype=np.int8
        ),
        "merge_overlap": np.asarray(
            [row["merge_overlap"] for row in rows], dtype=np.float32
        ),
        "mechanics": np.asarray(
            [row["mechanics"] for row in rows], dtype=np.float32
        ),
        "sink_features": np.asarray(
            [row["sink_features"] for row in rows], dtype=np.float32
        ),
        "residuals": np.stack([row["residuals"] for row in rows]).astype(
            np.float16
        ),
        "ratio": np.asarray([row["ratio"] for row in rows], dtype=np.float64),
        "source_manifest_sha256": np.asarray([source_hash]),
        "item_id": np.asarray([row["item_id"] for row in rows]),
        "context_mechanics_version": np.asarray(
            [row["context_mechanics_version"] for row in rows]
        ),
        "capture_chunk_schema": np.asarray([CAPTURE_CHUNK_SCHEMA]),
        "q2_protocol_version": np.asarray([Q2_PROTOCOL_VERSION]),
        "q2_namespace_version": np.asarray([Q2_NAMESPACE_VERSION]),
        "q2_amendment_json": np.asarray([amendment["q2_amendment_json"]]),
        "q2_amendment_sha256": np.asarray(
            [amendment["q2_amendment_sha256"]]
        ),
    }
    for field in Q2_ACCOUNTING_INTEGER_FIELDS:
        arrays[field] = np.asarray(
            [row[field] for row in rows], dtype=np.int64
        )
    return arrays


def _validate_capture_arrays(
    arrays: dict,
    *,
    expected_rows: list[dict],
    expected_ratio: float,
    manifest_sha256: str,
    label: str,
) -> dict:
    import numpy as np

    from memsub.certification import (
        eq_policy_v1,
        validate_q2_accounting_arrays,
    )
    from memsub.compaction import validate_capture_chunk

    amendment = _require_q2_amendment()
    singleton_provenance = {
        "capture_chunk_schema": CAPTURE_CHUNK_SCHEMA,
        "q2_protocol_version": Q2_PROTOCOL_VERSION,
        "q2_namespace_version": Q2_NAMESPACE_VERSION,
        "q2_amendment_json": amendment["q2_amendment_json"],
        "q2_amendment_sha256": amendment["q2_amendment_sha256"],
    }
    for key, value in singleton_provenance.items():
        actual = np.asarray(arrays.get(key, [])).reshape(-1)
        if len(actual) != 1 or str(actual[0]) != value:
            raise ValueError(f"{label} {key} provenance mismatch")
    audit = validate_capture_chunk(arrays, expected_ratio=expected_ratio)
    expected = {
        "item_ids": np.asarray([row["item_id"] for row in expected_rows]),
        "doc_ids": np.asarray([row["doc_id"] for row in expected_rows]),
        "domain": np.asarray([row["domain"] for row in expected_rows]),
        "pred_raw": np.asarray([row["pred_raw"] for row in expected_rows]),
        "raw_correct": np.asarray(
            [row["raw_correct"] for row in expected_rows], dtype=np.int8
        ),
        "in_e1": np.asarray(
            [row["in_e1"] for row in expected_rows], dtype=np.int8
        ),
    }
    for key, values in expected.items():
        actual = np.asarray(arrays[key])
        if values.dtype.kind in ("U", "S", "O"):
            actual = actual.astype(str)
            values = values.astype(str)
        if not np.array_equal(actual, values):
            raise ValueError(f"{label} {key} differs from registered manifest")
    pred_raw = np.asarray(arrays["pred_raw"]).astype(str)
    pred_merge = np.asarray(arrays["pred_merge"]).astype(str)
    if not all(value in ANSWER_LETTERS for value in pred_raw) or not all(
        value in ANSWER_LETTERS for value in pred_merge
    ):
        raise ValueError(f"{label} predictions leave registered answer alphabet")
    expected_y = np.asarray(
        [
            int(not eq_policy_v1(merged, raw))
            for merged, raw in zip(pred_merge, pred_raw)
        ],
        dtype=np.int8,
    )
    if not np.array_equal(np.asarray(arrays["y"]), expected_y):
        raise ValueError(f"{label} y differs from eq_policy_v1")
    source_hash = np.asarray(arrays["source_manifest_sha256"]).reshape(-1)
    if (
        len(source_hash) != 1
        or str(source_hash[0]) != manifest_sha256
    ):
        raise ValueError(f"{label} source manifest hash mismatch")
    if audit["rows"] != len(expected_rows):
        raise ValueError(f"{label} row count mismatch")
    audit["context_accounting"] = validate_q2_accounting_arrays(
        arrays, expected_rows, expected_ratio
    )
    return audit


def _validate_capture_state(
    state: dict,
    *,
    output_dir: str,
    selected: list[dict],
    manifest_sha256: str,
    q1_trigger: dict,
    q1_trigger_sha256: str,
    slice_idx: int,
    n_slices: int,
    required_pilot_verdict_sha256: str | None = None,
    allow_namespaced_verdict: bool = False,
    expected_fingerprint: dict | None = None,
    artifact_label: str = "Q2",
) -> dict:
    amendment = _require_q2_amendment()
    fields = {
        "capture_state_schema",
        "q2_protocol_version",
        "q2_namespace_version",
        "q2_context_mechanics_version",
        "q2_amendment_json",
        "q2_amendment_sha256",
        "q2_amendment_image_path",
        "q1_trigger",
        "q1_trigger_sha256",
        "model_id",
        "ratios",
        "sink_token_count",
        "source_manifest_path",
        "source_manifest_sha256",
        "slice_idx",
        "n_slices",
        "registered_item_count",
        "registered_item_ids_sha256",
        "completed_count",
        "completed_item_ids",
        "chunks",
        "compute_seconds",
        "compatibility_fingerprint_schema",
        "compatibility_fingerprint",
        "compatibility_fingerprint_sha256",
    }
    if required_pilot_verdict_sha256 is not None:
        fields.add("required_pilot_verdict_sha256")
    if not isinstance(state, dict) or set(state) != fields:
        raise ValueError("existing Q2 state schema mismatch")
    registered_item_ids = [row["item_id"] for row in selected]
    done = state.get("completed_count")
    if (
        output_dir == LEGACY_CAPTURE_ROOT
        or not output_dir.startswith(f"{CAPTURE_ROOT}/")
        or state.get("capture_state_schema") != CAPTURE_STATE_SCHEMA
        or state.get("q2_protocol_version") != Q2_PROTOCOL_VERSION
        or state.get("q2_namespace_version") != Q2_NAMESPACE_VERSION
        or state.get("q2_context_mechanics_version")
        != Q2_CONTEXT_MECHANICS_VERSION
        or state.get("q2_amendment_json")
        != amendment["q2_amendment_json"]
        or state.get("q2_amendment_sha256")
        != amendment["q2_amendment_sha256"]
        or state.get("q2_amendment_image_path")
        != amendment["q2_amendment_image_path"]
        or state.get("q1_trigger") != q1_trigger
        or state.get("q1_trigger_sha256") != q1_trigger_sha256
        or state.get("model_id") != MODEL_ID
        or state.get("ratios") != list(RATIOS)
        or state.get("sink_token_count") != SINKS
        or state.get("source_manifest_path") != MANIFEST_PATH
        or state.get("source_manifest_sha256") != manifest_sha256
        or state.get("slice_idx") != slice_idx
        or state.get("n_slices") != n_slices
        or state.get("registered_item_count") != len(selected)
        or state.get("registered_item_ids_sha256")
        != _item_ids_sha256(registered_item_ids)
        or type(done) is not int
        or not 0 <= done <= len(selected)
        or state.get("completed_item_ids") != registered_item_ids[:done]
        or isinstance(state.get("compute_seconds"), bool)
        or not isinstance(state.get("compute_seconds"), (int, float))
        or not math.isfinite(float(state["compute_seconds"]))
        or float(state["compute_seconds"]) < 0
        or (
            required_pilot_verdict_sha256 is not None
            and state.get("required_pilot_verdict_sha256")
            != required_pilot_verdict_sha256
        )
    ):
        raise ValueError("existing Q2 state differs from registered inputs")
    fingerprint = _validate_fingerprint_record(
        state, expected=expected_fingerprint
    )
    if done != len(selected) and done % CHUNK_ITEMS:
        raise ValueError("existing Q2 state ends between committed chunks")
    expected_intervals = []
    start = 0
    while start < done:
        end = min(start + CHUNK_ITEMS, len(selected))
        expected_intervals.append((start, end))
        start = end
    chunks = state.get("chunks")
    if not isinstance(chunks, list) or len(chunks) != len(expected_intervals):
        raise ValueError("existing Q2 state chunk count mismatch")

    expected_files = {"state.json"}
    chunk_evidence = []
    for chunk, (start, end) in zip(chunks, expected_intervals):
        expected_rows = selected[start:end]
        expected_ids = [row["item_id"] for row in expected_rows]
        if (
            not isinstance(chunk, dict)
            or set(chunk) != {"start", "end", "item_ids_sha256", "files"}
            or chunk.get("start") != start
            or chunk.get("end") != end
            or chunk.get("item_ids_sha256")
            != _item_ids_sha256(expected_ids)
            or not isinstance(chunk.get("files"), dict)
            or set(chunk["files"]) != {
                f"{ratio:.2f}" for ratio in RATIOS
            }
        ):
            raise ValueError("existing Q2 state chunk coverage mismatch")
        for ratio in RATIOS:
            key = f"{ratio:.2f}"
            filename = f"ratio-{ratio:.2f}-rows-{start:05d}-{end:05d}.npz"
            path = f"{output_dir}/{filename}"
            expected_files.add(filename)
            file_row = chunk["files"][key]
            if (
                not isinstance(file_row, dict)
                or set(file_row) != {"path", "sha256", "audit"}
                or file_row.get("path") != path
                or not os.path.isfile(path)
                or _sha256_file(path) != file_row.get("sha256")
            ):
                raise ValueError(f"existing Q2 {key} chunk artifact mismatch")
            import numpy as np

            with np.load(path, allow_pickle=False) as archive:
                arrays = {name: archive[name] for name in archive.files}
            audit = _validate_capture_arrays(
                arrays,
                expected_rows=expected_rows,
                expected_ratio=ratio,
                manifest_sha256=manifest_sha256,
                label=f"{artifact_label} {key} chunk",
            )
            if file_row.get("audit") != audit:
                raise ValueError(f"existing Q2 {key} chunk audit mismatch")
            chunk_evidence.append(
                {
                    "ratio": ratio,
                    "path": path,
                    "sha256": file_row["sha256"],
                    "audit": audit,
                }
            )
    actual_files = set(os.listdir(output_dir))
    verdict_present = PILOT_VERDICT_FILENAME in actual_files
    if allow_namespaced_verdict and verdict_present:
        expected_files.add(PILOT_VERDICT_FILENAME)
    if actual_files != expected_files:
        raise ValueError(
            f"Q2 output namespace mismatch: expected {sorted(expected_files)}, "
            f"found {sorted(actual_files)}"
        )
    state_path = f"{output_dir}/state.json"
    if not os.path.isfile(state_path):
        raise ValueError("existing Q2 state file is missing")
    return {
        "state": {
            "path": state_path,
            "sha256": _sha256_file(state_path),
        },
        "chunks": chunk_evidence,
        **fingerprint,
    }


def _run_capture(
    *,
    slice_idx: int,
    n_slices: int,
    limit: int,
    output_name: str,
    verify_mode_parity: bool,
    required_pilot_verdict: dict | None = None,
) -> dict:
    import sys

    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch

    from memsub.certification import (
        derive_q2_context_window,
        eq_policy_v1,
        validate_q2_context_length,
    )
    from memsub.compaction import (
        locate_token_subsequence,
        mechanics_features,
        merge_cache,
        prefill_with_real_attention,
    )
    from memsub.reference_config import build_runtime

    q1_trigger = _require_q1_trigger(Q1_TRIGGER_PATH)
    amendment = _require_q2_amendment()
    q1_trigger_sha256 = _sha256_file(Q1_TRIGGER_PATH)
    manifest, manifest_sha256 = _sorted_manifest()
    selected = [
        row
        for row_index, row in enumerate(manifest)
        if row_index % n_slices == slice_idx
    ]
    if limit:
        selected = selected[:limit]
    registered_item_ids = [row["item_id"] for row in selected]
    output_dir = f"{CAPTURE_ROOT}/{output_name}"
    os.makedirs(output_dir, exist_ok=True)
    state_path = f"{output_dir}/state.json"
    required_pilot_verdict_sha256 = None
    if required_pilot_verdict is not None:
        canonical_pilot_verdict = _require_registered_pilot_verdict()
        if required_pilot_verdict != canonical_pilot_verdict:
            raise ValueError("Q2 slice pilot verdict does not match amended authority")
        required_pilot_verdict_sha256 = _sha256_file(
            _registered_pilot_verdict_path()
        )
    state = {
        "capture_state_schema": CAPTURE_STATE_SCHEMA,
        "q2_protocol_version": Q2_PROTOCOL_VERSION,
        "q2_namespace_version": Q2_NAMESPACE_VERSION,
        "q2_context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
        "q2_amendment_json": amendment["q2_amendment_json"],
        "q2_amendment_sha256": amendment["q2_amendment_sha256"],
        "q2_amendment_image_path": amendment["q2_amendment_image_path"],
        "q1_trigger": q1_trigger,
        "q1_trigger_sha256": q1_trigger_sha256,
        "model_id": MODEL_ID,
        "ratios": list(RATIOS),
        "sink_token_count": SINKS,
        "source_manifest_path": MANIFEST_PATH,
        "source_manifest_sha256": manifest_sha256,
        "slice_idx": slice_idx,
        "n_slices": n_slices,
        "registered_item_count": len(selected),
        "registered_item_ids_sha256": _item_ids_sha256(registered_item_ids),
        "completed_count": 0,
        "completed_item_ids": [],
        "chunks": [],
        "compute_seconds": 0.0,
    }
    if required_pilot_verdict_sha256 is not None:
        state["required_pilot_verdict_sha256"] = (
            required_pilot_verdict_sha256
        )
    resumed = False
    if os.path.exists(state_path):
        with open(state_path) as handle:
            prior = json.load(handle)
        _validate_capture_state(
            prior,
            output_dir=output_dir,
            selected=selected,
            manifest_sha256=manifest_sha256,
            q1_trigger=q1_trigger,
            q1_trigger_sha256=q1_trigger_sha256,
            slice_idx=slice_idx,
            n_slices=n_slices,
            required_pilot_verdict_sha256=(
                required_pilot_verdict_sha256
            ),
            allow_namespaced_verdict=(
                output_name == f"pilot-{REGISTERED_PILOT_TAG}"
            ),
        )
        if (
            output_name == f"pilot-{REGISTERED_PILOT_TAG}"
            and os.path.exists(_registered_pilot_verdict_path())
        ):
            _require_registered_pilot_verdict()
        state = prior
        resumed = True
    elif os.listdir(output_dir):
        raise ValueError(
            f"Q2 output namespace has files without valid state: {output_dir}"
        )
    done = int(state["completed_count"])

    needed_docs = {row["doc_id"] for row in selected[done:]}
    texts = {}
    if needed_docs:
        for domain in DOMAINS:
            with open(f"/artifacts/corpus/{domain}.jsonl") as handle:
                for line in handle:
                    record = json.loads(line)
                    if record["doc_id"] in needed_docs:
                        texts[record["doc_id"]] = record["text"]
    missing_docs = sorted(needed_docs - set(texts))
    if missing_docs:
        raise ValueError(f"Q2 source documents missing: {missing_docs[:10]}")

    runtime = build_runtime(reference=True)
    model, tokenizer = runtime.model, runtime.tokenizer
    fingerprint = runtime.fingerprint()
    fingerprint_record = _fingerprint_record(fingerprint)
    if resumed:
        _validate_fingerprint_record(state, expected=fingerprint_record)
    else:
        state.update(fingerprint_record)
    if required_pilot_verdict is not None and any(
        required_pilot_verdict.get(key) != value
        for key, value in fingerprint_record.items()
    ):
        raise ValueError(
            "Q2 live runtime differs from registered pilot fingerprint"
        )
    _set_attention_mode(model, "sdpa")
    doc_cache = {}
    chunk_rows = {ratio: [] for ratio in RATIOS}
    chunk_start = done
    checkpoint_started = time.monotonic()

    def flush(end: int) -> None:
        nonlocal checkpoint_started, chunk_start
        if end == chunk_start:
            return
        metadata = {
            "start": chunk_start,
            "end": end,
            "item_ids_sha256": _item_ids_sha256(
                registered_item_ids[chunk_start:end]
            ),
            "files": {},
        }
        for ratio in RATIOS:
            arrays = _stack_chunk(
                chunk_rows[ratio],
                ratio=ratio,
                source_hash=manifest_sha256,
                amendment=amendment,
            )
            audit = _validate_capture_arrays(
                arrays,
                expected_rows=selected[chunk_start:end],
                expected_ratio=ratio,
                manifest_sha256=manifest_sha256,
                label=f"Q2 {ratio:.2f} chunk",
            )
            filename = (
                f"ratio-{ratio:.2f}-rows-{chunk_start:05d}-{end:05d}.npz"
            )
            path = f"{output_dir}/{filename}"
            _write_npz_atomic(path, arrays)
            metadata["files"][f"{ratio:.2f}"] = {
                "path": path,
                "sha256": _sha256_file(path),
                "audit": audit,
            }
        state["chunks"].append(metadata)
        state["completed_count"] = end
        state["completed_item_ids"].extend(
            registered_item_ids[chunk_start:end]
        )
        state["compute_seconds"] += time.monotonic() - checkpoint_started
        with open(state_path, "w") as handle:
            json.dump(state, handle, indent=1, allow_nan=False)
        artifacts.commit()
        print(f"{output_name}: {end}/{len(selected)}", flush=True)
        for ratio in RATIOS:
            chunk_rows[ratio].clear()
        chunk_start = end
        checkpoint_started = time.monotonic()

    for row_index, row in enumerate(selected):
        if row_index < done:
            continue
        if row["doc_id"] not in doc_cache:
            doc_cache.clear()
            doc_cache[row["doc_id"]] = tokenizer.encode(
                texts[row["doc_id"]], add_special_tokens=False
            )
        document_ids = doc_cache[row["doc_id"]]
        chunk_absolute = int(row["item_id"].split("_")[-2])
        window = derive_q2_context_window(
            len(document_ids), chunk_absolute, row["chunk_rel_start"]
        )
        validate_q2_context_length(window["source_context_token_count"])
        context_ids = document_ids[
            window["source_context_start"] : window["source_context_end"]
        ]
        chunk_relative = window["source_chunk_context_start"]
        source_chunk_ids = document_ids[
            chunk_absolute : chunk_absolute + 1024
        ]
        gold_index = ord(row["gold"].strip().upper()[0]) - ord("A")
        answer_text = row["options"][gold_index].strip()
        answer_ids = tokenizer.encode(answer_text, add_special_tokens=False)
        located = locate_token_subsequence(source_chunk_ids, answer_ids)
        if located is None:
            needle_positions = [chunk_relative + 512]
            locator_found = 0
        else:
            needle_positions = [
                chunk_relative + position for position in located
            ]
            locator_found = 1
        if not all(0 <= position < len(context_ids) for position in needle_positions):
            raise ValueError(f"{row['item_id']}: located needle leaves context")

        full_cache, _, attention_mass = prefill_with_real_attention(
            runtime, context_ids
        )
        if (
            not torch.isfinite(attention_mass).all()
            or float(attention_mass.min()) < 0
            or float(attention_mass.var()) <= 0
        ):
            raise ValueError(f"{row['item_id']}: invalid real attention mass")
        for ratio in RATIOS:
            accounting, plan = _measure_q2_budget(
                full_cache, context_tokens=len(context_ids), ratio=ratio
            )
            merged_cache = merge_cache(full_cache, attention_mass, plan).cache
            mechanics = mechanics_features(
                plan, attention_mass, needle_positions
            )
            merge_overlap = max(
                0,
                min(plan.recent_start, chunk_relative + 1024)
                - max(SINKS, chunk_relative),
            ) / 1024
            prediction, sink_features, residuals = _answer_capture(
                runtime, merged_cache, row
            )
            if verify_mode_parity:
                parity_prediction = runtime.answer_letter(
                    "", row["question"], row["options"], cache=merged_cache
                )
                if prediction != parity_prediction:
                    raise ValueError(
                        f"{row['item_id']}: eager/SDPA argmax drift at {ratio}"
                    )
            chunk_rows[ratio].append(
                {
                    "item_id": row["item_id"],
                    "doc_id": row["doc_id"],
                    "domain": row["domain"],
                    "pred_raw": row["pred_raw"],
                    "pred_merge": prediction,
                    "y": int(
                        not eq_policy_v1(prediction, row["pred_raw"])
                    ),
                    "raw_correct": int(row["raw_correct"]),
                    "in_e1": int(row["in_e1"]),
                    "locator_found": locator_found,
                    "merge_overlap": merge_overlap,
                    "mechanics": [
                        float(mechanics.block_size),
                        mechanics.attention_mass_share,
                        mechanics.block_heterogeneity,
                        mechanics.distance_to_recent_window,
                    ],
                    "sink_features": sink_features,
                    "residuals": residuals,
                    "ratio": ratio,
                    "context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
                    **window,
                    **accounting,
                }
            )
            del merged_cache
        del full_cache, attention_mass
        end = row_index + 1
        if end % CHUNK_ITEMS == 0 or end == len(selected):
            flush(end)
            torch.cuda.empty_cache()
    if state["completed_count"] != len(selected):
        raise ValueError("Q2 capture stopped before its registered slice completed")
    return {
        "output": output_dir,
        "items": state["completed_count"],
        "chunks": len(state["chunks"]),
        "compute_seconds": state["compute_seconds"],
    }


@app.function(
    image=image,
    gpu="H100",
    volumes=VOLUMES,
    timeout=43_200,
    memory=65_536,
)
def q2_pilot(run_tag: str, limit: int = 16) -> dict:
    if run_tag != REGISTERED_PILOT_TAG or limit != PILOT_ITEMS:
        raise ValueError(
            "Q2 pilot requires run_tag amended-v2 and exactly 16 items"
        )
    return _run_capture(
        slice_idx=0,
        n_slices=1,
        limit=limit,
        output_name=f"pilot-{run_tag}",
        verify_mode_parity=True,
    )


@app.function(
    image=image,
    gpu="H100",
    volumes=VOLUMES,
    timeout=43_200,
    memory=65_536,
)
def q2_capture_slice(
    slice_idx: int, n_slices: int = Q2_SLICES
) -> dict:
    if n_slices != Q2_SLICES or not 0 <= slice_idx < Q2_SLICES:
        raise ValueError("Q2 uses the fixed registered eight-slice fleet")
    pilot_verdict = _require_registered_pilot_verdict()
    return _run_capture(
        slice_idx=slice_idx,
        n_slices=n_slices,
        limit=0,
        output_name=f"full-amended-v2-slice-{slice_idx:02d}",
        verify_mode_parity=False,
        required_pilot_verdict=pilot_verdict,
    )


def _validate_pilot_artifact(run_tag: str) -> dict:
    import numpy as np

    amendment = _require_q2_amendment()
    if run_tag != REGISTERED_PILOT_TAG:
        raise ValueError("legacy Q2 pilot namespaces cannot authorize amended Q2")
    q1_trigger = _require_q1_trigger(Q1_TRIGGER_PATH)
    q1_trigger_sha256 = _sha256_file(Q1_TRIGGER_PATH)
    manifest, manifest_sha256 = _sorted_manifest()
    selected = manifest[:PILOT_ITEMS]
    output_dir = f"{CAPTURE_ROOT}/pilot-{run_tag}"
    state_path = f"{output_dir}/state.json"
    if not os.path.exists(state_path):
        raise ValueError(f"missing Q2 pilot {run_tag}")
    with open(state_path) as handle:
        state = json.load(handle)
    evidence = _validate_capture_state(
        state,
        output_dir=output_dir,
        selected=selected,
        manifest_sha256=manifest_sha256,
        q1_trigger=q1_trigger,
        q1_trigger_sha256=q1_trigger_sha256,
        slice_idx=0,
        n_slices=1,
        allow_namespaced_verdict=(run_tag == REGISTERED_PILOT_TAG),
        artifact_label=f"Q2 pilot {run_tag}",
    )
    if state.get("completed_count") != PILOT_ITEMS:
        raise ValueError(f"Q2 pilot {run_tag} state/provenance mismatch")
    arrays_by_ratio = {}
    audits = {}
    artifacts_by_ratio = {}
    for row in evidence["chunks"]:
        key = f"{float(row['ratio']):.2f}"
        with np.load(row["path"], allow_pickle=False) as archive:
            arrays = {name: archive[name] for name in archive.files}
        arrays_by_ratio[key] = arrays
        audits[key] = row["audit"]
        artifacts_by_ratio[key] = {
            "path": row["path"],
            "sha256": row["sha256"],
            "audit": row["audit"],
        }
    return {
        "q2_amendment": amendment["q2_amendment"],
        "q2_amendment_sha256": amendment["q2_amendment_sha256"],
        "q1_trigger": q1_trigger,
        "q1_trigger_sha256": q1_trigger_sha256,
        "source_manifest": {
            "path": MANIFEST_PATH,
            "sha256": manifest_sha256,
        },
        "state": evidence["state"],
        "artifacts": artifacts_by_ratio,
        "compatibility_fingerprint_schema": evidence[
            "compatibility_fingerprint_schema"
        ],
        "compatibility_fingerprint": evidence[
            "compatibility_fingerprint"
        ],
        "compatibility_fingerprint_sha256": evidence[
            "compatibility_fingerprint_sha256"
        ],
        "arrays": arrays_by_ratio,
        "audits": audits,
    }


def _build_registered_pilot_verdict(evidence: dict) -> dict:
    return {
        "schema": PILOT_VERDICT_SCHEMA,
        "protocol": "MERGECERT-Q2",
        "protocol_version": Q2_PROTOCOL_VERSION,
        "namespace_version": Q2_NAMESPACE_VERSION,
        "context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
        "validator_version": PILOT_VALIDATOR_VERSION,
        "validation_mode": "single-registered-run",
        "run_tag": REGISTERED_PILOT_TAG,
        "run_tags": [REGISTERED_PILOT_TAG],
        "items": PILOT_ITEMS,
        "ratios": list(RATIOS),
        "q2_amendment": evidence["q2_amendment"],
        "q2_amendment_sha256": evidence["q2_amendment_sha256"],
        "q1_trigger": evidence["q1_trigger"],
        "q1_trigger_sha256": evidence["q1_trigger_sha256"],
        "source_manifest": evidence["source_manifest"],
        "state": evidence["state"],
        "artifacts": evidence["artifacts"],
        "compatibility_fingerprint_schema": evidence[
            "compatibility_fingerprint_schema"
        ],
        "compatibility_fingerprint": evidence[
            "compatibility_fingerprint"
        ],
        "compatibility_fingerprint_sha256": evidence[
            "compatibility_fingerprint_sha256"
        ],
        "audits": evidence["audits"],
        "comparisons": {},
        "pass": True,
    }


def _require_registered_pilot_verdict() -> dict:
    path = _registered_pilot_verdict_path()
    if not os.path.isfile(path):
        raise ValueError("registered Q2 pilot verdict is missing")
    evidence = _validate_pilot_artifact(REGISTERED_PILOT_TAG)
    expected = _build_registered_pilot_verdict(evidence)
    try:
        with open(path, "rb") as handle:
            encoded = handle.read()
        actual = json.loads(encoded)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("registered Q2 pilot verdict is invalid") from exc
    if actual != expected or encoded != _canonical_json_bytes(expected):
        raise ValueError("registered Q2 pilot verdict is stale or tampered")
    return expected


@app.function(image=image, volumes=VOLUMES, timeout=14_400, memory=32_768)
def validate_pilot() -> dict:
    import sys

    sys.path.insert(0, "/root/repo")
    import numpy as np

    _require_q2_amendment()
    registered_state = (
        f"{CAPTURE_ROOT}/pilot-{REGISTERED_PILOT_TAG}/state.json"
    )
    if os.path.exists(registered_state):
        evidence = _validate_pilot_artifact(REGISTERED_PILOT_TAG)
        output = _build_registered_pilot_verdict(evidence)
        verdict_path = _registered_pilot_verdict_path()
        encoded = _canonical_json_bytes(output)
        if os.path.exists(verdict_path):
            with open(verdict_path, "rb") as handle:
                if handle.read() != encoded:
                    raise ValueError(
                        "registered Q2 pilot verdict is stale or tampered"
                    )
        else:
            temporary = f"{verdict_path}.partial"
            with open(temporary, "wb") as handle:
                handle.write(encoded)
            os.replace(temporary, verdict_path)
    else:
        raise ValueError("registered amended Q2 pilot is missing")
    artifacts.commit()
    return output


@app.function(image=image, volumes=VOLUMES, timeout=600, memory=1_024)
def pilot_gate() -> dict:
    _require_q2_amendment()
    return _require_registered_pilot_verdict()


@app.function(image=image, volumes=VOLUMES, timeout=43_200, memory=65_536)
def freeze_capture_summary() -> dict:
    import sys

    sys.path.insert(0, "/root/repo")

    amendment = _require_q2_amendment()
    pilot_verdict = _require_registered_pilot_verdict()
    pilot_verdict_sha256 = _sha256_file(_registered_pilot_verdict_path())
    q1_trigger = _require_q1_trigger(Q1_TRIGGER_PATH)
    q1_trigger_sha256 = _sha256_file(Q1_TRIGGER_PATH)
    manifest, manifest_hash = _sorted_manifest()
    expected_ids = [row["item_id"] for row in manifest]
    coverage = {f"{ratio:.2f}": [] for ratio in RATIOS}
    positive = Counter()
    locator = Counter()
    domains = {f"{ratio:.2f}": Counter() for ratio in RATIOS}
    chunk_manifest = []
    compute_seconds = 0.0
    expected_fingerprint = {
        key: pilot_verdict[key]
        for key in (
            "compatibility_fingerprint_schema",
            "compatibility_fingerprint",
            "compatibility_fingerprint_sha256",
        )
    }
    for slice_idx in range(Q2_SLICES):
        output_dir = f"{CAPTURE_ROOT}/full-amended-v2-slice-{slice_idx:02d}"
        state_path = f"{output_dir}/state.json"
        with open(state_path) as handle:
            state = json.load(handle)
        selected = [
            row
            for row_index, row in enumerate(manifest)
            if row_index % Q2_SLICES == slice_idx
        ]
        evidence = _validate_capture_state(
            state,
            output_dir=output_dir,
            selected=selected,
            manifest_sha256=manifest_hash,
            q1_trigger=q1_trigger,
            q1_trigger_sha256=q1_trigger_sha256,
            slice_idx=slice_idx,
            n_slices=Q2_SLICES,
            required_pilot_verdict_sha256=pilot_verdict_sha256,
            expected_fingerprint=expected_fingerprint,
            artifact_label=f"Q2 amended slice {slice_idx}",
        )
        if state["completed_count"] != len(selected):
            raise ValueError(f"Q2 slice {slice_idx} state coverage mismatch")
        compute_seconds += float(state["compute_seconds"])
        for chunk in evidence["chunks"]:
            key = f"{float(chunk['ratio']):.2f}"
            audit = chunk["audit"]
            start = next(
                state_chunk["start"]
                for state_chunk in state["chunks"]
                if state_chunk["files"][key]["path"] == chunk["path"]
            )
            end = next(
                state_chunk["end"]
                for state_chunk in state["chunks"]
                if state_chunk["files"][key]["path"] == chunk["path"]
            )
            item_ids = [row["item_id"] for row in selected[start:end]]
            coverage[key].extend(item_ids)
            positive[key] += audit["positive_labels"]
            locator[key] += audit["locator_found"]
            domains[key].update(row["domain"] for row in selected[start:end])
            chunk_manifest.append(
                {
                    "ratio": chunk["ratio"],
                    "slice_idx": slice_idx,
                    "path": chunk["path"],
                    "sha256": chunk["sha256"],
                    "audit": audit,
                }
            )
    for ratio in RATIOS:
        key = f"{ratio:.2f}"
        if (
            len(coverage[key]) != Q2_ITEMS
            or len(set(coverage[key])) != Q2_ITEMS
            or set(coverage[key]) != set(expected_ids)
        ):
            raise ValueError(f"Q2 ratio {key} does not cover the full manifest")
    if set(coverage["0.25"]) != set(coverage["0.40"]):
        raise ValueError("Q2 ratios do not cover the same registered IDs")
    output = {
        "schema": CAPTURE_SUMMARY_SCHEMA,
        "protocol": "MERGECERT-Q2",
        "protocol_version": Q2_PROTOCOL_VERSION,
        "namespace_version": Q2_NAMESPACE_VERSION,
        "context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
        "q2_amendment": amendment["q2_amendment"],
        "q2_amendment_sha256": amendment["q2_amendment_sha256"],
        "q1_trigger": q1_trigger,
        "q1_trigger_sha256": q1_trigger_sha256,
        "model_id": MODEL_ID,
        "ratios": list(RATIOS),
        "source_manifest": {"path": MANIFEST_PATH, "sha256": manifest_hash},
        "source_manifest_sha256": manifest_hash,
        "pilot_verdict": {
            "path": _registered_pilot_verdict_path(),
            "sha256": pilot_verdict_sha256,
            "schema": pilot_verdict["schema"],
        },
        "items_per_ratio": Q2_ITEMS,
        "unique_items_per_ratio": {
            key: len(set(values)) for key, values in coverage.items()
        },
        "positive_labels": dict(positive),
        "positive_rates": {
            key: positive[key] / Q2_ITEMS for key in positive
        },
        "locator_found": dict(locator),
        "locator_rates": {
            key: locator[key] / Q2_ITEMS for key in locator
        },
        "domain_counts": {
            key: dict(sorted(counts.items()))
            for key, counts in domains.items()
        },
        "worker_compute_seconds": compute_seconds,
        "chunks": chunk_manifest,
        "pass": True,
    }
    os.makedirs(CAPTURE_ROOT, exist_ok=True)
    summary_path = f"{CAPTURE_ROOT}/capture-summary.json"
    encoded = _canonical_json_bytes(output)
    if os.path.exists(summary_path):
        with open(summary_path, "rb") as handle:
            if handle.read() != encoded:
                raise ValueError("frozen Q2 capture summary is stale or tampered")
    else:
        with open(summary_path, "xb") as handle:
            handle.write(encoded)
    artifacts.commit()
    return {
        "artifact": summary_path,
        "items_per_ratio": Q2_ITEMS,
        "chunks": len(chunk_manifest),
        "pass": True,
    }


@app.local_entrypoint()
def fleet() -> None:
    pilot_gate.remote()
    handles = [
        q2_capture_slice.spawn(slice_idx, Q2_SLICES)
        for slice_idx in range(Q2_SLICES)
    ]
    print(f"spawned amended-v2 Q2 fleet: {len(handles)} slices")
