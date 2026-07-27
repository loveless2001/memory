"""MERGECERT Q2 — private unified merge relabel and capture fleet.

One real-attention prefill feeds both registered merge ratios.  Each immutable
NPZ chunk binds labels, visible merge mechanics, sink-head monitor features,
and all 37 last-prompt residual vectors to the same item order.
"""

import hashlib
import json
import os
import time
from collections import Counter

import modal

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
RATIOS = (0.25, 0.40)
CTX = 4096
SINKS = 4
Q2_ITEMS = 30_847
Q2_SLICES = 8
CHUNK_ITEMS = 100
CAPTURE_ROOT = "/artifacts/mergecert/q2"
MANIFEST_PATH = "/artifacts/probe/capture-manifest.json"
P0_VERDICT_PATH = "/artifacts/mergecert/p0-verdict.json"
HEADS = ((25, 14), (26, 26), (28, 19), (35, 15))
DOMAINS = ("financial", "legal", "code", "literature")
PINNED = (
    "torch==2.7.1",
    "transformers==4.55.2",
    "safetensors==0.5.3",
    "numpy>=1.26,<3",
    "hf_transfer",
)

app = modal.App("memsub-mergecert-q2-capture")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "MEMSUB_REFERENCE": "1"})
    .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
    .add_local_dir("memsub", "/root/repo/memsub")
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


def _item_ids_sha256(item_ids: list[str]) -> str:
    encoded = json.dumps(
        item_ids, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _require_p0_gate() -> dict:
    if not os.path.exists(P0_VERDICT_PATH):
        raise ValueError("Q2 is blocked until p0-verdict.json is on the volume")
    with open(P0_VERDICT_PATH) as handle:
        verdict = json.load(handle)
    if verdict.get("p0_pass") is not True or verdict.get("stop_q1_q3") is not False:
        raise ValueError("Q2 is blocked because the registered P0 gate did not pass")
    return {
        "p0_pass": True,
        "p0_verdict_sha256": _sha256_file(P0_VERDICT_PATH),
    }


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


def _stack_chunk(rows: list[dict], *, ratio: float, source_hash: str) -> dict:
    import numpy as np

    return {
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
        "ratio": np.asarray([ratio], dtype=np.float32),
        "source_manifest_sha256": np.asarray([source_hash]),
    }


def _run_capture(
    *,
    slice_idx: int,
    n_slices: int,
    limit: int,
    output_name: str,
    verify_mode_parity: bool,
) -> dict:
    import sys

    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch

    from memsub.certification import eq_policy_v1
    from memsub.compaction import (
        build_merge_plan,
        locate_token_subsequence,
        mechanics_features,
        merge_cache,
        prefill_with_real_attention,
        validate_capture_chunk,
    )
    from memsub.reference_config import build_runtime

    gate = _require_p0_gate()
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
    state = {
        "gate": gate,
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
    if os.path.exists(state_path):
        with open(state_path) as handle:
            prior = json.load(handle)
        if (
            prior.get("source_manifest_sha256") != manifest_sha256
            or prior.get("registered_item_ids_sha256")
            != _item_ids_sha256(registered_item_ids)
            or prior.get("gate") != gate
        ):
            raise ValueError("existing Q2 state uses different registered inputs")
        state = prior
    done = int(state["completed_count"])
    if state["completed_item_ids"] != registered_item_ids[:done]:
        raise ValueError("Q2 resume state item order is corrupt")

    needed_docs = {row["doc_id"] for row in selected[done:]}
    texts = {}
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
    state["compatibility_fingerprint"] = fingerprint.to_dict()
    state["compatibility_fingerprint_sha256"] = fingerprint.digest()
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
            )
            audit = validate_capture_chunk(arrays, expected_ratio=ratio)
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
        context_start = max(
            0,
            min(
                chunk_absolute - row["chunk_rel_start"],
                len(document_ids) - CTX,
            ),
        )
        context_ids = document_ids[context_start : context_start + CTX]
        if len(context_ids) != CTX:
            raise ValueError(f"{row['item_id']}: short Q2 context")
        chunk_relative = chunk_absolute - context_start
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
        if not all(0 <= position < CTX for position in needle_positions):
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
            plan = build_merge_plan(CTX, ratio, sink_token_count=SINKS)
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
    if run_tag not in ("a", "b") or limit != 16:
        raise ValueError("Q2 pilot requires run_tag a/b and exactly 16 items")
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
    return _run_capture(
        slice_idx=slice_idx,
        n_slices=n_slices,
        limit=0,
        output_name=f"full-slice-{slice_idx:02d}",
        verify_mode_parity=False,
    )


@app.function(image=image, volumes=VOLUMES, timeout=14_400, memory=32_768)
def validate_pilot() -> dict:
    import sys

    sys.path.insert(0, "/root/repo")
    import numpy as np

    for run_tag in ("a", "b"):
        state_path = f"{CAPTURE_ROOT}/pilot-{run_tag}/state.json"
        if not os.path.exists(state_path):
            raise ValueError(f"missing Q2 pilot {run_tag}")
    comparisons = {}
    for ratio in RATIOS:
        loaded = []
        for run_tag in ("a", "b"):
            with open(f"{CAPTURE_ROOT}/pilot-{run_tag}/state.json") as handle:
                state = json.load(handle)
            file_row = state["chunks"][0]["files"][f"{ratio:.2f}"]
            with np.load(file_row["path"], allow_pickle=False) as archive:
                loaded.append({key: archive[key] for key in archive.files})
        keys = sorted(set(loaded[0]) | set(loaded[1]))
        unequal = [
            key for key in keys if not np.array_equal(loaded[0][key], loaded[1][key])
        ]
        comparisons[f"{ratio:.2f}"] = {
            "bit_identical": not unequal,
            "unequal_arrays": unequal,
        }
        if unequal:
            raise ValueError(
                f"Q2 pilot is not bit-identical at {ratio:.2f}: {unequal}"
            )
    output = {
        "items": 16,
        "ratios": list(RATIOS),
        "comparisons": comparisons,
        "pass": True,
    }
    with open(f"{CAPTURE_ROOT}/pilot-verdict.json", "w") as handle:
        json.dump(output, handle, indent=1, allow_nan=False)
    artifacts.commit()
    return output


@app.function(image=image, volumes=VOLUMES, timeout=43_200, memory=65_536)
def freeze_capture_summary() -> dict:
    import sys

    sys.path.insert(0, "/root/repo")
    import numpy as np

    from memsub.compaction import validate_capture_chunk

    gate = _require_p0_gate()
    manifest, manifest_hash = _sorted_manifest()
    expected_ids = [row["item_id"] for row in manifest]
    coverage = {f"{ratio:.2f}": [] for ratio in RATIOS}
    positive = Counter()
    locator = Counter()
    domains = {f"{ratio:.2f}": Counter() for ratio in RATIOS}
    chunk_manifest = []
    compute_seconds = 0.0
    for slice_idx in range(Q2_SLICES):
        state_path = f"{CAPTURE_ROOT}/full-slice-{slice_idx:02d}/state.json"
        with open(state_path) as handle:
            state = json.load(handle)
        registered_ids = [
            row["item_id"]
            for row_index, row in enumerate(manifest)
            if row_index % Q2_SLICES == slice_idx
        ]
        if (
            state["source_manifest_sha256"] != manifest_hash
            or state["completed_count"] != len(registered_ids)
            or state["completed_item_ids"] != registered_ids
        ):
            raise ValueError(f"Q2 slice {slice_idx} state coverage mismatch")
        compute_seconds += float(state["compute_seconds"])
        for chunk in state["chunks"]:
            for ratio in RATIOS:
                key = f"{ratio:.2f}"
                file_row = chunk["files"][key]
                if _sha256_file(file_row["path"]) != file_row["sha256"]:
                    raise ValueError(f"Q2 chunk hash mismatch: {file_row['path']}")
                with np.load(file_row["path"], allow_pickle=False) as archive:
                    arrays = {name: archive[name] for name in archive.files}
                audit = validate_capture_chunk(
                    arrays, expected_ratio=ratio
                )
                item_ids = arrays["item_ids"].astype(str).tolist()
                expected_chunk_ids = registered_ids[
                    int(chunk["start"]) : int(chunk["end"])
                ]
                if item_ids != expected_chunk_ids:
                    raise ValueError("Q2 chunk differs from registered slice interval")
                if _item_ids_sha256(item_ids) != chunk["item_ids_sha256"]:
                    raise ValueError("Q2 chunk item order/hash mismatch")
                coverage[key].extend(item_ids)
                positive[key] += audit["positive_labels"]
                locator[key] += audit["locator_found"]
                domains[key].update(arrays["domain"].astype(str).tolist())
                chunk_manifest.append(
                    {
                        "ratio": ratio,
                        "slice_idx": slice_idx,
                        "path": file_row["path"],
                        "sha256": file_row["sha256"],
                        "rows": audit["rows"],
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
    output = {
        "gate": gate,
        "model_id": MODEL_ID,
        "ratios": list(RATIOS),
        "source_manifest_sha256": manifest_hash,
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
    with open(f"{CAPTURE_ROOT}/capture-summary.json", "w") as handle:
        json.dump(output, handle, indent=1, allow_nan=False)
    artifacts.commit()
    return {
        "artifact": f"{CAPTURE_ROOT}/capture-summary.json",
        "items_per_ratio": Q2_ITEMS,
        "chunks": len(chunk_manifest),
        "pass": True,
    }


@app.local_entrypoint()
def fleet() -> None:
    handles = [
        q2_capture_slice.spawn(slice_idx, Q2_SLICES)
        for slice_idx in range(Q2_SLICES)
    ]
    print(f"spawned fixed Q2 fleet: {len(handles)} slices")
