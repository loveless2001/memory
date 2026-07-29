"""MERGECERT Q2 — private routability probes and F5 fifth-regime row."""

import glob
import hashlib
import json
import os

import modal

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
RATIOS = (0.25, 0.40)
SEEDS = (0, 1, 2)
TRAIN_END = 0.6
VALIDATION_END = 0.7
RESIDUAL_LAYERS = (
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
    10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
    20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
    30, 31, 32, 33, 34, 35, 36,
)
CAPTURE_ROOT = "/artifacts/mergecert/q2-amended-v2"
LEGACY_CAPTURE_ROOT = "/artifacts/mergecert/q2"
CAPTURE_SUMMARY = "/artifacts/mergecert/q2-amended-v2/capture-summary.json"
ROUTABILITY_OUTPUT = "/artifacts/mergecert/q2-amended-v2/routability.json"
SCORES_OUTPUT = "/artifacts/mergecert/q2-amended-v2/scores.npz"
MANIFEST_PATH = "/artifacts/probe/capture-manifest.json"
SURFACE_PATH = "/artifacts/preprobe/surface-features.json"
FACT_TYPES_SOURCE = "/artifacts/preprobe/fact-types.state.json"
FACT_TYPES_COMPLETE = "/artifacts/mergecert/q2-amended-v2/fact-types-complete.json"
EMBEDDINGS_PATH = "/artifacts/corpus-gate-labels/embeddings.npz"
SHADOW_CHECKPOINT = "/artifacts/gate-eval/gate-checkpoint.pt"
COMPACTOR_SINK_PATH = "/artifacts/probe/followup-f3-headfeats.npz"
EVICTION_SINK_GLOB = "/artifacts/probe/followup2-f5-eviction-slice-*.npz"
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
Q2_PROTOCOL_VERSION = "mergecert-q2-amended-v2"
Q2_CONTEXT_MECHANICS_VERSION = "mergecert-q2-context-mechanics-v2"
Q2_NAMESPACE_VERSION = "mergecert-q2-amended-v2"
CAPTURE_SUMMARY_SCHEMA = "mergecert-q2-capture-summary-v2"
ROUTABILITY_SCHEMA = "mergecert-q2-routability-amended-v2"
SCORE_SCHEMA = "mergecert-q2-scores-amended-v2"
PILOT_VERDICT_SCHEMA = "mergecert-q2-pilot-verdict-v3-amended"
PILOT_VALIDATOR_VERSION = "mergecert-q2-pilot-validator-v3-amended"
Q2_AMENDMENT_IMAGE_PATH = (
    "/root/repo/plans/260728-mergecert-q1/q2-amendment.json"
)
Q2_AMENDMENT_SHA256 = (
    "7b510a5b0af827516894fe806281cfa877e2234135dccc297c8d8bd823a87b0a"
)
ARM_NAMES = (
    "c0_refit",
    "mechanics_refit",
    "shadow_zero_shot",
    "shadow_refit",
    "sink_compactor_zero_shot",
    "sink_eviction_zero_shot",
    "sink_refit",
    "residual_linear",
    "residual_mlp",
)
FACT_LEVELS = ("number", "name/entity", "code symbol", "date", "common phrase")
DOMAINS = ("financial", "legal", "code", "literature")
PINNED = (
    "torch==2.7.1",
    "numpy>=1.26,<3",
    "scikit-learn==1.5.2",
    "transformers==4.55.2",
    "safetensors==0.5.3",
    "hf_transfer",
)

app = modal.App("memsub-mergecert-q2-amended-v2-probes")
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


def _routability_source_hashes(
    capture_summary_sha256: str, amendment: dict
) -> dict:
    """Return every source digest consumed by the routability artifact."""
    return {
        "q1_trigger": _sha256_file(Q1_TRIGGER_PATH),
        "q2_amendment": amendment["q2_amendment_sha256"],
        "capture_summary": capture_summary_sha256,
        "manifest": _sha256_file(MANIFEST_PATH),
        "surface": _sha256_file(SURFACE_PATH),
        "fact_types": _sha256_file(FACT_TYPES_COMPLETE),
        "embeddings": _sha256_file(EMBEDDINGS_PATH),
        "shadow_checkpoint": _sha256_file(SHADOW_CHECKPOINT),
        "compactor_sink": _sha256_file(COMPACTOR_SINK_PATH),
        "eviction_sink_files": {
            path: _sha256_file(path)
            for path in sorted(glob.glob(EVICTION_SINK_GLOB))
        },
    }


def _require_q1_trigger(path: str | None = None) -> dict:
    path = path or Q1_TRIGGER_PATH
    from memsub.certification import load_q1_trigger

    try:
        return load_q1_trigger(path)
    except (FileNotFoundError, OSError) as exc:
        raise ValueError("Q2 is blocked until q1-trigger.json exists") from exc


def _require_q2_amendment(path: str | None = None) -> dict:
    """Load the one settled Q2 authority from the image-bound artifact."""
    from memsub.certification import load_q2_amendment

    amendment_path = path or Q2_AMENDMENT_IMAGE_PATH
    amendment = load_q2_amendment(amendment_path, Q2_AMENDMENT_SHA256)
    with open(amendment_path, encoding="utf-8") as handle:
        amendment_json = handle.read()
    if _sha256_file(amendment_path) != Q2_AMENDMENT_SHA256:
        raise ValueError("Q2 amendment image bytes do not match the authority")
    return {
        "q2_amendment": amendment,
        "q2_amendment_json": amendment_json,
        "q2_amendment_sha256": Q2_AMENDMENT_SHA256,
    }


def _canonical_json_bytes(value: dict) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode()


def _is_sha256(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_amended_pilot_verdict(
    summary: dict,
    q1_trigger: dict,
    q1_trigger_sha256: str,
    amendment: dict,
) -> dict:
    metadata = summary.get("pilot_verdict")
    expected_path = (
        f"{CAPTURE_ROOT}/pilot-amended-v2/pilot-verdict.json"
    )
    if (
        not isinstance(metadata, dict)
        or set(metadata) != {"path", "sha256", "schema"}
        or metadata.get("path") != expected_path
        or metadata.get("schema") != PILOT_VERDICT_SCHEMA
        or not _is_sha256(metadata.get("sha256"))
        or not os.path.isfile(expected_path)
        or _sha256_file(expected_path) != metadata["sha256"]
    ):
        raise ValueError("Q2 amended pilot verdict artifact is missing or drifted")
    try:
        with open(expected_path, "rb") as handle:
            encoded = handle.read()
        verdict = json.loads(encoded)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Q2 amended pilot verdict is invalid") from exc
    if not isinstance(verdict, dict):
        raise ValueError("Q2 amended pilot verdict is invalid")
    required = {
        "schema", "protocol", "protocol_version", "namespace_version",
        "context_mechanics_version", "validator_version", "validation_mode",
        "run_tag", "run_tags", "items", "ratios", "q2_amendment",
        "q2_amendment_sha256", "q1_trigger", "q1_trigger_sha256",
        "source_manifest", "state", "artifacts",
        "compatibility_fingerprint_schema", "compatibility_fingerprint",
        "compatibility_fingerprint_sha256", "audits", "comparisons", "pass",
    }
    source_manifest = verdict.get("source_manifest")
    state = verdict.get("state")
    artifacts_by_ratio = verdict.get("artifacts")
    from memsub.fingerprint import CompatibilityFingerprint

    try:
        fingerprint = CompatibilityFingerprint.from_dict(
            verdict.get("compatibility_fingerprint")
        )
    except (TypeError, ValueError):
        fingerprint = None
    if (
        set(verdict) != required
        or encoded != _canonical_json_bytes(verdict)
        or verdict["schema"] != PILOT_VERDICT_SCHEMA
        or verdict["protocol"] != "MERGECERT-Q2"
        or verdict["protocol_version"] != Q2_PROTOCOL_VERSION
        or verdict["namespace_version"] != Q2_NAMESPACE_VERSION
        or verdict["context_mechanics_version"]
        != Q2_CONTEXT_MECHANICS_VERSION
        or verdict["validator_version"] != PILOT_VALIDATOR_VERSION
        or verdict["validation_mode"] != "single-registered-run"
        or verdict["run_tag"] != "amended-v2"
        or verdict["run_tags"] != ["amended-v2"]
        or verdict["items"] != 16
        or verdict["ratios"] != list(RATIOS)
        or verdict["q2_amendment"] != amendment["q2_amendment"]
        or verdict["q2_amendment_sha256"]
        != amendment["q2_amendment_sha256"]
        or verdict["q1_trigger"] != q1_trigger
        or verdict["q1_trigger_sha256"] != q1_trigger_sha256
        or source_manifest != summary.get("source_manifest")
        or not isinstance(state, dict)
        or set(state) != {"path", "sha256"}
        or not _is_sha256(state.get("sha256"))
        or not isinstance(artifacts_by_ratio, dict)
        or set(artifacts_by_ratio) != {"0.25", "0.40"}
        or any(
            not isinstance(row, dict)
            or set(row) != {"path", "sha256", "audit"}
            or not _is_sha256(row.get("sha256"))
            or not isinstance(row.get("audit"), dict)
            for row in artifacts_by_ratio.values()
        )
        or verdict["compatibility_fingerprint_schema"]
        != "memsub-compatibility-fingerprint-v1"
        or fingerprint is None
        or verdict["compatibility_fingerprint_sha256"]
        != fingerprint.digest()
        or not isinstance(verdict["audits"], dict)
        or set(verdict["audits"]) != {"0.25", "0.40"}
        or verdict["comparisons"] != {}
        or verdict["pass"] is not True
    ):
        raise ValueError("Q2 amended pilot verdict contract is invalid")
    return verdict


def _require_gate_and_capture() -> tuple[dict, dict, str]:
    if CAPTURE_SUMMARY.startswith(f"{LEGACY_CAPTURE_ROOT}/"):
        raise ValueError("Q2 probes reject the legacy capture root; use amended v2")
    q1_trigger = _require_q1_trigger()
    q1_trigger_sha256 = _sha256_file(Q1_TRIGGER_PATH)
    amendment = _require_q2_amendment()
    if not os.path.exists(CAPTURE_SUMMARY):
        raise ValueError("Q2 probes require the frozen amended capture summary")
    with open(CAPTURE_SUMMARY) as handle:
        summary = json.load(handle)
    required_fields = {
        "schema", "protocol", "protocol_version", "namespace_version",
        "context_mechanics_version", "q2_amendment", "q2_amendment_sha256",
        "q1_trigger", "q1_trigger_sha256", "model_id", "ratios",
        "source_manifest", "source_manifest_sha256", "pilot_verdict",
        "items_per_ratio", "unique_items_per_ratio", "positive_labels",
        "positive_rates", "locator_found", "locator_rates", "domain_counts",
        "worker_compute_seconds", "chunks", "pass",
    }
    if not isinstance(summary, dict) or "q2_amendment" not in summary:
        raise ValueError("Q2 capture summary amendment is missing")
    if not isinstance(summary, dict) or set(summary) != required_fields:
        raise ValueError("Q2 probes require the complete amended capture summary")
    if (
        summary["schema"] != CAPTURE_SUMMARY_SCHEMA
        or summary["protocol"] != "MERGECERT-Q2"
        or summary["protocol_version"] != Q2_PROTOCOL_VERSION
    ):
        raise ValueError("Q2 capture summary schema/protocol mismatch")
    if summary["namespace_version"] != Q2_NAMESPACE_VERSION:
        raise ValueError("Q2 capture summary namespace mismatch")
    if summary["context_mechanics_version"] != Q2_CONTEXT_MECHANICS_VERSION:
        raise ValueError("Q2 capture summary context mechanics mismatch")
    if (
        summary["q2_amendment"] != amendment["q2_amendment"]
        or summary["q2_amendment_sha256"] != amendment["q2_amendment_sha256"]
    ):
        raise ValueError("Q2 capture summary amendment mismatch")
    if (
        summary["pass"] is not True
        or summary["q1_trigger"] != q1_trigger
        or summary["q1_trigger_sha256"] != q1_trigger_sha256
    ):
        raise ValueError("Q2 capture summary is not bound to the Q1 trigger")
    if (
        summary["model_id"] != MODEL_ID
        or summary["ratios"] != list(RATIOS)
        or not isinstance(summary["source_manifest"], dict)
        or summary["source_manifest"].get("sha256")
        != summary["source_manifest_sha256"]
        or not isinstance(summary["chunks"], list)
        or not summary["chunks"]
    ):
        raise ValueError("Q2 capture summary contract is incomplete")
    _require_amended_pilot_verdict(
        summary, q1_trigger, q1_trigger_sha256, amendment
    )
    return q1_trigger, summary, q1_trigger_sha256


def _require_frozen_manifest(capture_summary: dict, path: str | None = None) -> list[dict]:
    """Load the manifest only when it still matches the frozen capture input."""
    manifest_path = path or MANIFEST_PATH
    if _sha256_file(manifest_path) != capture_summary["source_manifest_sha256"]:
        raise ValueError("Q2 probe manifest hash differs from frozen capture summary")
    with open(manifest_path) as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, list):
        raise ValueError("Q2 probe manifest must be a list")
    return manifest


def _require_complete_fact_types(
    capture_summary: dict, q1_trigger: dict, q1_trigger_sha256: str
) -> dict:
    """Reject stale fact-type state before it can enter amended Q2 probes."""
    if not os.path.exists(FACT_TYPES_COMPLETE):
        raise ValueError("run complete_fact_types before Q2 probes")
    with open(FACT_TYPES_COMPLETE) as handle:
        state = json.load(handle)
    amendment = _require_q2_amendment()
    required_fields = {
        "source_path", "source_sha256", "manifest_sha256", "q1_trigger",
        "q1_trigger_sha256", "q2_protocol_version", "q2_namespace_version",
        "q2_context_mechanics_version", "q2_amendment_json",
        "q2_amendment_sha256", "types", "completed_missing_item_ids",
    }
    if not isinstance(state, dict) or set(state) != required_fields:
        raise ValueError("completed fact types use an incomplete state schema")
    if (
        state["source_path"] != FACT_TYPES_SOURCE
        or state["source_sha256"] != _sha256_file(FACT_TYPES_SOURCE)
        or state["manifest_sha256"] != capture_summary["source_manifest_sha256"]
        or state["q1_trigger"] != q1_trigger
        or state["q1_trigger_sha256"] != q1_trigger_sha256
        or state["q2_protocol_version"] != Q2_PROTOCOL_VERSION
        or state["q2_namespace_version"] != Q2_NAMESPACE_VERSION
        or state["q2_context_mechanics_version"] != Q2_CONTEXT_MECHANICS_VERSION
        or state["q2_amendment_json"] != amendment["q2_amendment_json"]
        or state["q2_amendment_sha256"] != amendment["q2_amendment_sha256"]
        or not isinstance(state["types"], dict)
        or not isinstance(state["completed_missing_item_ids"], list)
    ):
        raise ValueError("completed fact types do not match amended Q2 inputs")
    return state


FACT_TYPES = {
    "A": "number",
    "B": "name/entity",
    "C": "code symbol",
    "D": "date",
    "E": "common phrase",
}
FACT_PROMPT = """Classify the TYPE of this quiz answer.

Question: {question}
Answer: {answer}

Types:
A. number or quantity
B. name or entity (person, company, place, organization)
C. code symbol or identifier (variable, function, path, hex, technical token)
D. date or time
E. common phrase (ordinary words, none of the above)

Answer with a single letter.
Answer:"""


@app.function(image=image, gpu="L4", volumes=VOLUMES, timeout=14_400)
def complete_fact_types() -> dict:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    q1_trigger, capture_summary, q1_trigger_sha256 = _require_gate_and_capture()
    amendment = _require_q2_amendment()
    manifest = _require_frozen_manifest(capture_summary)
    with open(FACT_TYPES_SOURCE) as handle:
        source = json.load(handle)
    source_types = source["types"]
    state = {
        "source_path": FACT_TYPES_SOURCE,
        "source_sha256": _sha256_file(FACT_TYPES_SOURCE),
        "manifest_sha256": _sha256_file(MANIFEST_PATH),
        "q1_trigger": q1_trigger,
        "q1_trigger_sha256": q1_trigger_sha256,
        "q2_protocol_version": Q2_PROTOCOL_VERSION,
        "q2_namespace_version": Q2_NAMESPACE_VERSION,
        "q2_context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
        "q2_amendment_json": amendment["q2_amendment_json"],
        "q2_amendment_sha256": amendment["q2_amendment_sha256"],
        "types": dict(source_types),
        "completed_missing_item_ids": [],
    }
    if os.path.exists(FACT_TYPES_COMPLETE):
        with open(FACT_TYPES_COMPLETE) as handle:
            prior = json.load(handle)
        if (
            prior.get("source_sha256") != state["source_sha256"]
            or prior.get("manifest_sha256") != state["manifest_sha256"]
            or prior.get("q1_trigger") != q1_trigger
            or prior.get("q1_trigger_sha256") != q1_trigger_sha256
            or prior.get("q2_protocol_version") != Q2_PROTOCOL_VERSION
            or prior.get("q2_namespace_version") != Q2_NAMESPACE_VERSION
            or prior.get("q2_context_mechanics_version")
            != Q2_CONTEXT_MECHANICS_VERSION
            or prior.get("q2_amendment_json")
            != amendment["q2_amendment_json"]
            or prior.get("q2_amendment_sha256")
            != amendment["q2_amendment_sha256"]
        ):
            raise ValueError("existing completed fact types use different inputs")
        state = prior
    missing = sorted(
        (row for row in manifest if row["item_id"] not in state["types"]),
        key=lambda row: row["item_id"],
    )
    if not missing:
        return {
            "manifest_items": len(manifest),
            "source_items": len(source_types),
            "completed_items": len(state["types"]),
            "new_items": len(state["completed_missing_item_ids"]),
        }
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
    ).to("cuda").eval()
    letter_ids = [
        tokenizer.encode(f" {letter}", add_special_tokens=False)[-1]
        for letter in FACT_TYPES
    ]
    os.makedirs(os.path.dirname(FACT_TYPES_COMPLETE), exist_ok=True)
    with torch.inference_mode():
        for row_index, row in enumerate(missing):
            gold_index = ord(row["gold"].strip().upper()[0]) - ord("A")
            answer = row["options"][gold_index].strip()
            prompt = FACT_PROMPT.format(
                question=row["question"][:600], answer=answer[:200]
            )
            token_ids = tokenizer.encode(prompt, add_special_tokens=False)
            logits = model(
                input_ids=torch.tensor([token_ids], device="cuda")
            ).logits[0, -1]
            scores = [float(logits[token_id]) for token_id in letter_ids]
            letter = list(FACT_TYPES)[scores.index(max(scores))]
            state["types"][row["item_id"]] = FACT_TYPES[letter]
            state["completed_missing_item_ids"].append(row["item_id"])
            if (row_index + 1) % 100 == 0 or row_index + 1 == len(missing):
                with open(FACT_TYPES_COMPLETE, "w") as handle:
                    json.dump(state, handle, indent=1, allow_nan=False)
                artifacts.commit()
                print(
                    f"fact types: {row_index + 1}/{len(missing)} missing",
                    flush=True,
                )
    if set(state["types"]) != {row["item_id"] for row in manifest}:
        raise ValueError("completed fact types do not exactly cover Q2 manifest")
    return {
        "manifest_items": len(manifest),
        "source_items": len(source_types),
        "completed_items": len(state["types"]),
        "new_items": len(state["completed_missing_item_ids"]),
    }


def _apply_linear(values, fit: dict):
    import numpy as np

    matrix = np.asarray(values, dtype=np.float32)
    normalized = (matrix - fit["mean"]) / fit["scale"]
    return normalized @ fit["weight"] + fit["bias"]


def _fit_linear(values, labels, train_mask, *, seed: int, epochs: int = 12):
    import numpy as np
    import torch

    from memsub.certification.mergecert_statistics import standardize_train_only

    matrix = np.asarray(values, dtype=np.float32)
    y = np.asarray(labels, dtype=np.float32)
    train = np.asarray(train_mask, dtype=bool)
    normalized, mean, scale = standardize_train_only(matrix, train)
    x_tensor = torch.from_numpy(normalized.astype(np.float32)).to("cuda")
    y_tensor = torch.from_numpy(y).to("cuda")
    torch.manual_seed(seed)
    layer = torch.nn.Linear(matrix.shape[1], 1).to("cuda")
    optimizer = torch.optim.AdamW(
        layer.parameters(), lr=1e-3, weight_decay=1e-4
    )
    train_indices = torch.from_numpy(np.flatnonzero(train)).to("cuda")
    for _ in range(epochs):
        permutation = train_indices[
            torch.randperm(len(train_indices), device="cuda")
        ]
        for start in range(0, len(permutation), 4096):
            selected = permutation[start : start + 4096]
            optimizer.zero_grad()
            logits = layer(x_tensor[selected]).squeeze(-1)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                logits, y_tensor[selected]
            )
            loss.backward()
            optimizer.step()
    with torch.inference_mode():
        scores = layer(x_tensor).squeeze(-1).cpu().numpy()
    fit = {
        "mean": mean.astype(np.float32),
        "scale": scale.astype(np.float32),
        "weight": layer.weight.detach().cpu().numpy()[0].astype(np.float32),
        "bias": float(layer.bias.detach().cpu()),
    }
    del x_tensor, y_tensor, layer
    return scores, fit


def _fit_mlp(values, labels, train_mask, validation_mask, *, seed: int):
    import numpy as np
    import torch

    from memsub.certification.mergecert_statistics import (
        standardize_train_only,
        tie_aware_auc,
    )

    matrix = np.asarray(values, dtype=np.float32)
    y = np.asarray(labels, dtype=np.float32)
    train = np.asarray(train_mask, dtype=bool)
    validation = np.asarray(validation_mask, dtype=bool)
    normalized, _, _ = standardize_train_only(matrix, train)
    x_tensor = torch.from_numpy(normalized.astype(np.float32)).to("cuda")
    y_tensor = torch.from_numpy(y).to("cuda")
    train_indices = torch.from_numpy(np.flatnonzero(train)).to("cuda")
    torch.manual_seed(seed)
    network = torch.nn.Sequential(
        torch.nn.Linear(matrix.shape[1], 256),
        torch.nn.GELU(),
        torch.nn.Dropout(0.1),
        torch.nn.Linear(256, 1),
    ).to("cuda")
    optimizer = torch.optim.AdamW(
        network.parameters(), lr=1e-3, weight_decay=1e-4
    )
    best_auc = -1.0
    best_state = None
    patience = 0
    for _ in range(200):
        network.train()
        permutation = train_indices[
            torch.randperm(len(train_indices), device="cuda")
        ]
        for start in range(0, len(permutation), 4096):
            selected = permutation[start : start + 4096]
            optimizer.zero_grad()
            logits = network(x_tensor[selected]).squeeze(-1)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                logits, y_tensor[selected]
            )
            loss.backward()
            optimizer.step()
        network.eval()
        with torch.inference_mode():
            validation_scores = (
                network(x_tensor[validation]).squeeze(-1).cpu().numpy()
            )
        validation_auc = tie_aware_auc(
            y[validation].astype(int), validation_scores
        )
        if validation_auc > best_auc + 1e-7:
            best_auc = validation_auc
            best_state = {
                key: value.detach().clone()
                for key, value in network.state_dict().items()
            }
            patience = 0
        else:
            patience += 1
            if patience >= 20:
                break
    network.load_state_dict(best_state)
    network.eval()
    with torch.inference_mode():
        scores = network(x_tensor).squeeze(-1).cpu().numpy()
    del x_tensor, y_tensor, network
    return scores


def _metric(labels, scores, split, documents, domains, *, seed: int):
    import numpy as np

    from memsub.certification.mergecert_statistics import (
        cluster_bootstrap_auc,
        tie_aware_auc,
    )

    y = np.asarray(labels, dtype=int)
    values = np.asarray(scores, dtype=float)
    test = np.asarray(split) == 2
    result = cluster_bootstrap_auc(
        y[test],
        values[test],
        np.asarray(documents)[test],
        seed=seed,
        n_resamples=2_000,
    )
    result["per_domain_auc"] = {}
    domain_values = np.asarray(domains)
    for domain in DOMAINS:
        mask = test & (domain_values == domain)
        if mask.sum() and len(np.unique(y[mask])) == 2:
            result["per_domain_auc"][domain] = tie_aware_auc(
                y[mask], values[mask]
            )
    return result


def _source_sink_models(manifest_by_id: dict):
    import numpy as np

    from memsub.certification.mergecert_statistics import document_split

    compactor = np.load(COMPACTOR_SINK_PATH, allow_pickle=False)
    compactor_ids = compactor["item_ids"].astype(str)
    def document_of(item_id: str) -> str:
        if item_id in manifest_by_id:
            return manifest_by_id[item_id]["doc_id"]
        if not item_id.startswith("mcq_"):
            raise ValueError(f"cannot reconstruct source document for {item_id}")
        return item_id[4:].rsplit("_", 2)[0]

    compactor_docs = np.asarray([document_of(item_id) for item_id in compactor_ids])
    compactor_split = document_split(compactor_docs)
    _, compactor_fit = _fit_linear(
        compactor["feats"],
        compactor["y"],
        compactor_split == 0,
        seed=SEEDS[0],
    )

    ids = []
    features = []
    labels = []
    for path in sorted(glob.glob(EVICTION_SINK_GLOB)):
        archive = np.load(path, allow_pickle=False)
        ids.extend(archive["item_ids"].astype(str).tolist())
        features.append(archive["feats"])
        labels.append(archive["y"])
    if not features:
        raise ValueError("eviction F5 source captures are missing")
    eviction_ids = np.asarray(ids)
    eviction_features = np.concatenate(features)
    eviction_labels = np.concatenate(labels)
    eviction_docs = np.asarray([document_of(item_id) for item_id in eviction_ids])
    eviction_split = document_split(eviction_docs)
    _, eviction_fit = _fit_linear(
        eviction_features,
        eviction_labels,
        eviction_split == 0,
        seed=SEEDS[0],
    )
    return compactor_fit, eviction_fit


def _c0_distance(merge_recent_start, source_chunk_context_start):
    """Return the captured distance from the answer anchor to the recent span."""
    import numpy as np

    return np.asarray(merge_recent_start, dtype=np.float32) - (
        np.asarray(source_chunk_context_start, dtype=np.float32) + 1024
    )


def _empty_capture_target(count: int, *, residual_path: str | None = None):
    import numpy as np

    from memsub.certification import Q2_ACCOUNTING_ARRAY_FIELDS

    target = {
        "y": np.empty(count, dtype=np.int8),
        "mechanics": np.empty((count, 4), dtype=np.float32),
        "sink": np.empty((count, 8), dtype=np.float32),
        "overlap": np.empty(count, dtype=np.float32),
        "residuals": (
            np.memmap(
                residual_path,
                mode="w+",
                dtype=np.float16,
                shape=(count, 37, 2560),
            )
            if residual_path is not None
            else np.empty((count, 37, 2560), dtype=np.float16)
        ),
        "seen": np.zeros(count, dtype=bool),
        "chunk_accounting_audits": [],
    }
    for field in Q2_ACCOUNTING_ARRAY_FIELDS:
        if field == "item_id":
            target[field] = np.empty(count, dtype="U256")
        elif field == "ratio":
            target[field] = np.empty(count, dtype=np.float64)
        elif field == "context_mechanics_version":
            target[field] = np.empty(count, dtype="U256")
        else:
            target[field] = np.empty(count, dtype=np.int64)
    return target


def _assemble_capture_chunks(
    capture_summary: dict,
    manifest: list[dict],
    *,
    ratios=RATIOS,
    residual_dir: str | None = None,
):
    """Validate immutable chunks and assemble all score/accounting vectors."""
    import numpy as np

    from memsub.certification import validate_q2_accounting_arrays
    from memsub.compaction import validate_capture_chunk

    manifest_by_id = {row["item_id"]: row for row in manifest}
    if len(manifest_by_id) != len(manifest):
        raise ValueError("Q2 probe manifest contains duplicate item IDs")
    index_by_id = {row["item_id"]: index for index, row in enumerate(manifest)}
    captured = {}
    for ratio in ratios:
        key = f"{ratio:.2f}"
        residual_path = (
            f"{residual_dir}/mergecert-residual-{key}.dat"
            if residual_dir is not None
            else None
        )
        captured[key] = _empty_capture_target(
            len(manifest), residual_path=residual_path
        )
    for chunk in capture_summary["chunks"]:
        try:
            ratio = float(chunk["ratio"])
            key = f"{ratio:.2f}"
            expected_hash = chunk["sha256"]
            path = chunk["path"]
            frozen_audit = chunk["audit"]["context_accounting"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Q2 capture summary chunk is incomplete") from exc
        if key not in captured:
            raise ValueError("Q2 capture summary contains an unregistered ratio")
        if path.startswith(f"{LEGACY_CAPTURE_ROOT}/"):
            raise ValueError("Q2 probes reject legacy capture chunks")
        if _sha256_file(path) != expected_hash:
            raise ValueError("Q2 capture chunk hash differs from frozen summary")
        with np.load(path, allow_pickle=False) as archive:
            arrays = {name: archive[name] for name in archive.files}
        source_manifest = np.asarray(
            arrays["source_manifest_sha256"]
        ).reshape(-1)
        if (
            len(source_manifest) != 1
            or str(source_manifest[0])
            != capture_summary["source_manifest_sha256"]
        ):
            raise ValueError("Q2 capture chunk manifest hash differs from frozen summary")
        capture_audit = validate_capture_chunk(arrays, expected_ratio=ratio)
        chunk_ids = arrays["item_ids"].astype(str)
        if any(item_id not in index_by_id for item_id in chunk_ids):
            raise ValueError("Q2 capture chunk contains an item outside the manifest")
        indices = np.asarray([index_by_id[item_id] for item_id in chunk_ids])
        target = captured[key]
        if target["seen"][indices].any():
            raise ValueError("duplicate Q2 capture item during assembly")
        expected_rows = [manifest_by_id[item_id] for item_id in chunk_ids]
        accounting_audit = validate_q2_accounting_arrays(
            arrays, expected_rows, ratio
        )
        if accounting_audit != frozen_audit:
            raise ValueError("Q2 capture accounting audit differs from frozen summary")
        if capture_audit != {
            key: chunk["audit"][key] for key in capture_audit
        }:
            raise ValueError("Q2 capture audit differs from frozen summary")
        target["y"][indices] = arrays["y"]
        target["mechanics"][indices] = arrays["mechanics"]
        target["sink"][indices] = arrays["sink_features"]
        target["overlap"][indices] = arrays["merge_overlap"]
        target["residuals"][indices] = arrays["residuals"]
        for field in target:
            if field in arrays and field not in {
                "y", "mechanics", "sink", "overlap", "residuals", "seen",
            }:
                target[field][indices] = arrays[field]
        target["seen"][indices] = True
        target["chunk_accounting_audits"].append(accounting_audit)
    for key, target in captured.items():
        if not target["seen"].all():
            raise ValueError(f"Q2 capture assembly has missing rows for ratio {key}")
        target["accounting_audit"] = validate_q2_accounting_arrays(
            target, manifest, float(key)
        )
    return captured


@app.function(
    image=image,
    gpu="L4",
    volumes=VOLUMES,
    timeout=43_200,
    memory=65_536,
    cpu=8,
)
def run_probes() -> dict:
    import sys

    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch

    from memsub.certification.mergecert_statistics import (
        document_split,
        tie_aware_auc,
    )
    from memsub.gate import DualEncoderExpansionGate, TrainConfig, train_gate
    from memsub.gate.label_dataset_splits import GateDataset

    q1_trigger, capture_summary, q1_trigger_sha256 = _require_gate_and_capture()
    manifest = _require_frozen_manifest(capture_summary)
    manifest.sort(key=lambda row: (row["domain"], row["doc_id"], row["item_id"]))
    count = len(manifest)
    if count != 30_847:
        raise ValueError("Q2 probe manifest count mismatch")
    manifest_by_id = {row["item_id"]: row for row in manifest}
    item_ids = np.asarray([row["item_id"] for row in manifest])
    index_by_id = {item_id: index for index, item_id in enumerate(item_ids)}
    documents = np.asarray([row["doc_id"] for row in manifest])
    domains = np.asarray([row["domain"] for row in manifest])
    in_e1 = np.asarray([row["in_e1"] for row in manifest], dtype=np.int8)
    split = document_split(
        documents,
        train_end=TRAIN_END,
        validation_end=VALIDATION_END,
    )
    if len(set(documents[split == 0]) & set(documents[split != 0])):
        raise ValueError("Q2 document split leaked")

    captured = _assemble_capture_chunks(
        capture_summary, manifest, residual_dir="/tmp"
    )

    with open(SURFACE_PATH) as handle:
        surface = json.load(handle)
    fact_type_payload = _require_complete_fact_types(
        capture_summary, q1_trigger, q1_trigger_sha256
    )
    fact_types = fact_type_payload["types"]
    if not set(item_ids) <= set(surface) or set(item_ids) != set(fact_types):
        raise ValueError("surface/fact-type joins do not cover Q2 manifest")

    embeddings = np.load(EMBEDDINGS_PATH, allow_pickle=False)
    embedding_index = {
        item_id: index
        for index, item_id in enumerate(embeddings["item_ids"].astype(str))
    }
    if not set(item_ids) <= set(embedding_index):
        raise ValueError("shadow embeddings do not cover Q2 manifest")
    embedding_rows = np.asarray([embedding_index[item_id] for item_id in item_ids])
    q_embeddings = embeddings["q_emb"][embedding_rows].astype(np.float32)
    b_embeddings = embeddings["b_emb"][embedding_rows].astype(np.float32)
    shadow_checkpoint = torch.load(SHADOW_CHECKPOINT, weights_only=False)
    compactor_sink_fit, eviction_sink_fit = _source_sink_models(manifest_by_id)

    ratio_scores = {}
    ratio_results = {}
    ratio_small_design = {}
    ratio_shadow_datasets = {}
    for ratio_index, ratio in enumerate(RATIOS):
        key = f"{ratio:.2f}"
        target = captured[key]
        y = target["y"].astype(int)
        train = split == 0
        validation = split == 1
        offsets = np.asarray(
            [
                np.nan
                if surface[item_id]["ans_rel_offset"] is None
                else surface[item_id]["ans_rel_offset"]
                for item_id in item_ids
            ],
            dtype=float,
        )
        offset_median = float(np.nanmedian(offsets[train]))
        offsets = np.where(np.isnan(offsets), offset_median, offsets)
        distance = _c0_distance(
            target["merge_recent_start"],
            target["source_chunk_context_start"],
        )
        c0 = np.asarray(
            [
                [
                    surface[item_id]["rarity_min"],
                    surface[item_id]["rarity_mean"],
                    offsets[index],
                    surface[item_id]["ans_found_in_span"],
                    distance[index],
                    target["overlap"][index],
                    *[
                        int(fact_types[item_id] == level)
                        for level in FACT_LEVELS[:-1]
                    ],
                ]
                for index, item_id in enumerate(item_ids)
            ],
            dtype=np.float32,
        )
        ratio_small_design[key] = c0
        scores = {}
        scores["c0_refit"], _ = _fit_linear(
            c0, y, train, seed=SEEDS[0]
        )
        mechanics_seed_scores = [
            _fit_linear(
                target["mechanics"], y, train, seed=seed
            )[0]
            for seed in SEEDS
        ]
        scores["mechanics_refit"] = np.mean(mechanics_seed_scores, axis=0)

        shadow_ds = GateDataset(
            item_id=item_ids,
            doc_id=documents,
            domain=domains,
            fraction=np.full(count, ratio, dtype=np.float32),
            y=y,
            overlap=target["overlap"],
            evicted=(target["overlap"] > 0.5).astype(np.int8),
            pointwise=np.ones(count, dtype=np.int8),
            raw_correct=np.asarray(
                [row["raw_correct"] for row in manifest], dtype=np.int8
            ),
            compact_correct=(1 - y).astype(np.int8),
            q_emb=q_embeddings,
            b_emb=b_embeddings,
        )
        ratio_shadow_datasets[key] = shadow_ds
        zero_model = DualEncoderExpansionGate(q_embeddings.shape[1], TrainConfig())
        zero_model.load_state_dict(shadow_checkpoint["state_dict"])
        zero_model.temperatures = shadow_checkpoint.get("temperatures", {})
        scores["shadow_zero_shot"] = zero_model.predict_logits(
            shadow_ds, np.arange(count)
        )[0]
        shadow_seed_scores = []
        for seed in SEEDS:
            model = train_gate(
                shadow_ds,
                train,
                TrainConfig(seed=seed),
                device="cuda",
            ).cpu()
            shadow_seed_scores.append(
                model.predict_logits(shadow_ds, np.arange(count))[0]
            )
        scores["shadow_refit"] = np.mean(shadow_seed_scores, axis=0)

        scores["sink_compactor_zero_shot"] = _apply_linear(
            target["sink"], compactor_sink_fit
        )
        scores["sink_eviction_zero_shot"] = _apply_linear(
            target["sink"], eviction_sink_fit
        )
        scores["sink_refit"], _ = _fit_linear(
            target["sink"], y, train, seed=SEEDS[0]
        )

        best_layer = None
        best_validation_auc = -1.0
        best_linear_scores = None
        layer_curve = []
        for layer_index in RESIDUAL_LAYERS:
            layer_scores, _ = _fit_linear(
                target["residuals"][:, layer_index].astype(np.float32),
                y,
                train,
                seed=SEEDS[0],
                epochs=8,
            )
            validation_auc = tie_aware_auc(
                y[validation], layer_scores[validation]
            )
            layer_curve.append(validation_auc)
            if validation_auc > best_validation_auc:
                best_layer = layer_index
                best_validation_auc = validation_auc
                best_linear_scores = layer_scores
        scores["residual_linear"] = best_linear_scores
        mlp_seed_scores = [
            _fit_mlp(
                target["residuals"][:, best_layer].astype(np.float32),
                y,
                train,
                validation,
                seed=seed,
            )
            for seed in SEEDS
        ]
        scores["residual_mlp"] = np.mean(mlp_seed_scores, axis=0)
        ratio_scores[key] = scores
        arm_results = {}
        for arm_index, arm_name in enumerate(ARM_NAMES):
            arm_results[arm_name] = _metric(
                y,
                scores[arm_name],
                split,
                documents,
                domains,
                seed=20260727 + ratio_index * 100 + arm_index,
            )
        arm_results["mechanics_refit"]["seed_test_aucs"] = [
            tie_aware_auc(y[split == 2], values[split == 2])
            for values in mechanics_seed_scores
        ]
        arm_results["shadow_refit"]["seed_test_aucs"] = [
            tie_aware_auc(y[split == 2], values[split == 2])
            for values in shadow_seed_scores
        ]
        arm_results["residual_mlp"]["seed_test_aucs"] = [
            tie_aware_auc(y[split == 2], values[split == 2])
            for values in mlp_seed_scores
        ]
        arm_results["residual_linear"]["selected_layer"] = best_layer
        arm_results["residual_linear"]["validation_layer_curve"] = layer_curve
        ratio_results[key] = {
            "items": count,
            "positive_rate": float(y.mean()),
            "split_counts": {
                "train": int((split == 0).sum()),
                "validation": int((split == 1).sum()),
                "test": int((split == 2).sum()),
            },
            "arms": arm_results,
        }

    pooled_labels = np.concatenate(
        [captured[f"{ratio:.2f}"]["y"].astype(int) for ratio in RATIOS]
    )
    pooled_split = np.tile(split, len(RATIOS))
    pooled_documents = np.tile(documents, len(RATIOS))
    pooled_domains = np.tile(domains, len(RATIOS))
    ratio_covariate = np.concatenate(
        [np.full(count, ratio, dtype=np.float32) for ratio in RATIOS]
    )[:, None]
    pooled_scores = {}
    pooled_c0 = np.concatenate(
        [ratio_small_design[f"{ratio:.2f}"] for ratio in RATIOS]
    )
    pooled_scores["c0_refit"], _ = _fit_linear(
        np.concatenate([pooled_c0, ratio_covariate], axis=1),
        pooled_labels,
        pooled_split == 0,
        seed=SEEDS[0],
    )
    pooled_mechanics = np.concatenate(
        [captured[f"{ratio:.2f}"]["mechanics"] for ratio in RATIOS]
    )
    pooled_mechanics_seed = [
        _fit_linear(
            np.concatenate([pooled_mechanics, ratio_covariate], axis=1),
            pooled_labels,
            pooled_split == 0,
            seed=seed,
        )[0]
        for seed in SEEDS
    ]
    pooled_scores["mechanics_refit"] = np.mean(
        pooled_mechanics_seed, axis=0
    )
    pooled_shadow = GateDataset(
        item_id=np.tile(item_ids, len(RATIOS)),
        doc_id=pooled_documents,
        domain=pooled_domains,
        fraction=np.concatenate(
            [np.full(count, ratio, dtype=np.float32) for ratio in RATIOS]
        ),
        y=pooled_labels,
        overlap=np.concatenate(
            [captured[f"{ratio:.2f}"]["overlap"] for ratio in RATIOS]
        ),
        evicted=np.concatenate(
            [
                (captured[f"{ratio:.2f}"]["overlap"] > 0.5).astype(np.int8)
                for ratio in RATIOS
            ]
        ),
        pointwise=np.ones(2 * count, dtype=np.int8),
        raw_correct=np.tile(
            np.asarray([row["raw_correct"] for row in manifest], dtype=np.int8),
            len(RATIOS),
        ),
        compact_correct=(1 - pooled_labels).astype(np.int8),
        q_emb=np.tile(q_embeddings, (len(RATIOS), 1)),
        b_emb=np.tile(b_embeddings, (len(RATIOS), 1)),
    )
    pooled_scores["shadow_zero_shot"] = np.concatenate(
        [
            ratio_scores[f"{ratio:.2f}"]["shadow_zero_shot"]
            for ratio in RATIOS
        ]
    )
    pooled_shadow_seed = []
    for seed in SEEDS:
        model = train_gate(
            pooled_shadow,
            pooled_split == 0,
            TrainConfig(seed=seed),
            device="cuda",
        ).cpu()
        pooled_shadow_seed.append(
            model.predict_logits(pooled_shadow, np.arange(2 * count))[0]
        )
    pooled_scores["shadow_refit"] = np.mean(pooled_shadow_seed, axis=0)
    pooled_sink = np.concatenate(
        [captured[f"{ratio:.2f}"]["sink"] for ratio in RATIOS]
    )
    pooled_scores["sink_compactor_zero_shot"] = _apply_linear(
        pooled_sink, compactor_sink_fit
    )
    pooled_scores["sink_eviction_zero_shot"] = _apply_linear(
        pooled_sink, eviction_sink_fit
    )
    pooled_scores["sink_refit"], _ = _fit_linear(
        np.concatenate([pooled_sink, ratio_covariate], axis=1),
        pooled_labels,
        pooled_split == 0,
        seed=SEEDS[0],
    )

    best_layer = None
    best_validation_auc = -1.0
    best_scores = None
    pooled_layer_curve = []
    for layer_index in RESIDUAL_LAYERS:
        values = np.concatenate(
            [
                captured[f"{ratio:.2f}"]["residuals"][
                    :, layer_index
                ].astype(np.float32)
                for ratio in RATIOS
            ]
        )
        layer_scores, _ = _fit_linear(
            np.concatenate([values, ratio_covariate], axis=1),
            pooled_labels,
            pooled_split == 0,
            seed=SEEDS[0],
            epochs=8,
        )
        validation_auc = tie_aware_auc(
            pooled_labels[pooled_split == 1],
            layer_scores[pooled_split == 1],
        )
        pooled_layer_curve.append(validation_auc)
        if validation_auc > best_validation_auc:
            best_layer = layer_index
            best_validation_auc = validation_auc
            best_scores = layer_scores
    pooled_scores["residual_linear"] = best_scores
    pooled_best_values = np.concatenate(
        [
            captured[f"{ratio:.2f}"]["residuals"][
                :, best_layer
            ].astype(np.float32)
            for ratio in RATIOS
        ]
    )
    pooled_mlp_seed = [
        _fit_mlp(
            np.concatenate([pooled_best_values, ratio_covariate], axis=1),
            pooled_labels,
            pooled_split == 0,
            pooled_split == 1,
            seed=seed,
        )
        for seed in SEEDS
    ]
    pooled_scores["residual_mlp"] = np.mean(pooled_mlp_seed, axis=0)
    pooled_results = {
        arm_name: _metric(
            pooled_labels,
            pooled_scores[arm_name],
            pooled_split,
            pooled_documents,
            pooled_domains,
            seed=20261000 + arm_index,
        )
        for arm_index, arm_name in enumerate(ARM_NAMES)
    }
    pooled_results["residual_linear"]["selected_layer"] = best_layer
    pooled_results["residual_linear"][
        "validation_layer_curve"
    ] = pooled_layer_curve

    amendment = _require_q2_amendment()
    capture_summary_sha256 = _sha256_file(CAPTURE_SUMMARY)
    accounting_audit = {
        f"{ratio:.2f}": captured[f"{ratio:.2f}"]["accounting_audit"]
        for ratio in RATIOS
    }
    accounting_audit_sha256 = hashlib.sha256(
        json.dumps(
            accounting_audit, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    output = {
        "schema": ROUTABILITY_SCHEMA,
        "q2_amendment": amendment["q2_amendment"],
        "q2_amendment_sha256": amendment["q2_amendment_sha256"],
        "protocol_version": Q2_PROTOCOL_VERSION,
        "namespace_version": Q2_NAMESPACE_VERSION,
        "context_mechanics_version": Q2_CONTEXT_MECHANICS_VERSION,
        "q1_trigger": q1_trigger,
        "q1_trigger_sha256": q1_trigger_sha256,
        "model_id": MODEL_ID,
        "ratios": list(RATIOS),
        "seeds": list(SEEDS),
        "split": {
            "method": "sha256 document bucket",
            "train": f"< {TRAIN_END}",
            "validation": f"[{TRAIN_END}, {VALIDATION_END})",
            "test": f">= {VALIDATION_END}",
        },
        "source_hashes": _routability_source_hashes(
            capture_summary_sha256, amendment
        ),
        "capture_summary_sha256": capture_summary_sha256,
        "manifest_sha256": _sha256_file(MANIFEST_PATH),
        "accounting_audit": accounting_audit,
        "accounting_audit_sha256": accounting_audit_sha256,
        "score_schema": SCORE_SCHEMA,
        "ratios_results": ratio_results,
        "pooled": {
            "items": 2 * count,
            "positive_rate": float(pooled_labels.mean()),
            "arms": pooled_results,
        },
    }
    flat_item_ids = np.tile(item_ids, len(RATIOS))
    flat_ratios = np.concatenate(
        [np.full(count, ratio, dtype=np.float64) for ratio in RATIOS]
    )
    score_arrays = {
        "score_schema": np.asarray([SCORE_SCHEMA]),
        "q2_amendment_json": np.asarray([amendment["q2_amendment_json"]]),
        "q2_amendment_sha256": np.asarray([amendment["q2_amendment_sha256"]]),
        "q2_protocol_version": np.asarray([Q2_PROTOCOL_VERSION]),
        "q2_namespace_version": np.asarray([Q2_NAMESPACE_VERSION]),
        "q2_context_mechanics_version": np.asarray([
            Q2_CONTEXT_MECHANICS_VERSION
        ]),
        "capture_summary_sha256": np.asarray([capture_summary_sha256]),
        "source_manifest_sha256": np.asarray([
            output["manifest_sha256"]
        ]),
        "accounting_audit_sha256": np.asarray([accounting_audit_sha256]),
        "q1_trigger_json": np.asarray(
            [json.dumps(q1_trigger, sort_keys=True, separators=(",", ":"))]
        ),
        "q1_trigger_sha256": np.asarray([q1_trigger_sha256]),
        "item_ids": flat_item_ids,
        "doc_ids": pooled_documents,
        "domain": pooled_domains,
        "y": pooled_labels.astype(np.int8),
        "split": pooled_split.astype(np.int8),
        "in_e1": np.tile(in_e1, len(RATIOS)),
    }
    from memsub.certification import Q2_ACCOUNTING_ARRAY_FIELDS

    for field in Q2_ACCOUNTING_ARRAY_FIELDS:
        score_arrays[field] = np.concatenate(
            [captured[f"{ratio:.2f}"][field] for ratio in RATIOS]
        )
    for arm_name in ARM_NAMES:
        score_arrays[f"{arm_name}_separate"] = np.concatenate(
            [ratio_scores[f"{ratio:.2f}"][arm_name] for ratio in RATIOS]
        ).astype(np.float32)
        score_arrays[f"{arm_name}_pooled"] = np.asarray(
            pooled_scores[arm_name], dtype=np.float32
        )
    os.makedirs(os.path.dirname(ROUTABILITY_OUTPUT), exist_ok=True)
    np.savez_compressed(SCORES_OUTPUT, **score_arrays)
    output["scores_sha256"] = _sha256_file(SCORES_OUTPUT)
    with open(ROUTABILITY_OUTPUT, "w") as handle:
        json.dump(output, handle, indent=1, allow_nan=False)
    artifacts.commit()
    return {
        "routability": ROUTABILITY_OUTPUT,
        "scores": SCORES_OUTPUT,
        "items": 2 * count,
        "scores_sha256": output["scores_sha256"],
    }
