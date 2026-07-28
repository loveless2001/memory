"""MERGECERT P0/Q1 — private port verification and M1 placement.

The runner is deliberately evaluation-only.  P0 must pass before Q1 is
launched; every artifact stays on the private ``memsub-artifacts`` volume.
"""

import hashlib
import json
import math
import os

import modal

from memsub.fingerprint import CompatibilityFingerprint, FIELDS
from memsub.mergecert_q1_registration import (
    Q1_REGISTRATION_PENDING,
    Q1_REGISTRATION_SHA256,
    Q1_TOKENIZER_ARTIFACT_SHA256,
    Q1_TOKENIZER_FILES_SHA256,
    canonical_q1_registration_sha256,
    resolve_q1_tokenizer_snapshot,
    tokenizer_artifact_digests,
    validate_q1_registration_schema,
)

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
Q1_TOKENIZER_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
UPSTREAM_COMMIT = "cd4ed948d62231449dbab9669608bbb4fd220713"
RATIOS = (0.25, 0.40, 0.90)
Q1_RATIOS = (0.25, 0.40)
Q1_BUDGET_MODE = "archived-m1-per-document-matched-physical-v1"
Q1_ADDENDUM_SHA256 = (
    "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509"
)
Q1_P0_VERDICT_SHA256 = (
    "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
)
Q1_EXECUTION_SEMANTICS_VERSION = "mergecert-q1-execution-semantics-v1"
Q1_FINGERPRINT_SCHEMA = "memsub-compatibility-fingerprint-v1"
SINKS = 4
P0_ITEMS = 200
SEED = 20260727
ARTIFACT_ROOT = "/artifacts/mergecert"
CONTINUATION_TEXT = " The discussion continued."
P0_CHECKPOINT_EVERY = 10
Q1_CONTEXTS_PER_DOMAIN = 5
Q1_EXPECTED_DOCUMENTS = 20
Q1_ARCHIVE_ROOT = "/artifacts/corpus-certification-full"
Q1_ITEMS_PATH = "/artifacts/corpus-mcq-full/all-items.json"
Q1_ARTIFACT_ROOT = "/artifacts/mergecert-q1"
Q1_ADDENDUM_PATH = f"{Q1_ARTIFACT_ROOT}/MERGECERT-Q1.md"
Q1_P0_VERDICT_PATH = f"{Q1_ARTIFACT_ROOT}/p0-verdict.json"
Q1_REGISTRATION_PATH = f"{Q1_ARTIFACT_ROOT}/q1-registration.json"
Q1_REGISTRATION_SOURCE_PATH = (
    "/root/repo/plans/260728-mergecert-q1/q1-registration-source.json"
)
Q1_REGISTRATION_SOURCE_SHA256 = (
    "6ab5b8cd8b63ff086795796220f458d5d3caf7127cc51c253102d473da45c9c4"
)
Q1_OUTPUT = f"{Q1_ARTIFACT_ROOT}/q1-certification.json"
Q1_SMOKE_OUTPUT = f"{Q1_ARTIFACT_ROOT}/q1-smoke.json"
P0_VERDICT_PATH = "/artifacts/mergecert/p0-verdict.json"
DOMAINS = ("financial", "legal", "code", "literature")
PINNED = (
    "torch==2.7.1",
    "transformers==4.55.2",
    "safetensors==0.5.3",
    "numpy>=1.26,<3",
    "hf_transfer",
)
SOURCE_FILES = {
    "README.md": "edfd5236d99dab5d6e4bf80b74dd79a54ffd94cec4b7066511dc6fd7ae7cae17",
    "benchmarks/modal_kv_real_bench.py": (
        "518b2d2cd4b652f4cc83ef9c82593fe624301986e0e3e22780ee9f0bfe423bb8"
    ),
    "lego_server.py": "f1df91c8af05cf4ea5000f4027450bf91e5e269f4e922da8979fc0885d6ff228",
}
Q1_REFERENCES = {
    "frozen_subsample": {
        "mean_kl": 0.2566,
        "accuracy_delta": 0.063,
        "lost_prior": 0.188,
    },
    "unfrozen_compactor": {
        "mean_kl": 0.1385,
        "accuracy_delta": 0.042,
        "lost_prior": 0.083,
    },
}
Q1_REFERENCE_SOURCES = {
    "frozen_subsample": {
        "path": "plans/260719-0318-fullrecipe-campaign/plan.md",
        "sha256": "5017c76fa4715eb4f883ae1e2bd7cb26bbe0518aac9dfe2a53cff7ccdfb85dce",
    },
    "unfrozen_compactor": {
        "path": (
            "plans/260719-2328-e1full-unfrozen-full-recipe/"
            "summary-e1full-clean-v1-n60.json"
        ),
        "sha256": "a7636b54148e7133237af68bf63fbc23811d5ce80417f8447711a89a559dc2a8",
    },
}

app = modal.App("memsub-mergecert-p0-q1")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "MEMSUB_REFERENCE": "1"})
    .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
    .add_local_file(
        "plans/260728-mergecert-q1/q1-registration-source.json",
        Q1_REGISTRATION_SOURCE_PATH,
    )
    .add_local_python_source("memsub")
)
hf_cache = modal.Volume.from_name("memsub-hf-cache", create_if_missing=True)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/root/.cache/huggingface": hf_cache, "/artifacts": artifacts}


def _provenance() -> dict:
    return {
        "model_id": MODEL_ID,
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_files": SOURCE_FILES,
        "ratios": list(RATIOS),
        "sink_token_count": SINKS,
        "seed": SEED,
    }


def _q1_provenance() -> dict:
    return {
        "model_id": MODEL_ID,
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_files": SOURCE_FILES,
        "ratios": list(Q1_RATIOS),
        "sink_token_count": SINKS,
        "budget_mode": Q1_BUDGET_MODE,
        "seed": SEED,
        "execution_semantics": _q1_execution_semantics(),
    }


def _q1_execution_semantics() -> dict:
    return {
        "version": Q1_EXECUTION_SEMANTICS_VERSION,
        "archive_replay_prefill": {
            "attention_backend": "sdpa",
            "scope": "auxiliary-archive-replay-gate",
        },
        "reported_five_arm_prefill": {
            "attention_backend": "eager",
            "mode": "real-attention",
            "cache_policy": "single-common-prefill",
        },
        "continuation_and_scoring": {
            "attention_backend": "sdpa",
            "backend_state": "restored-configured",
        },
    }


def _q1_fingerprint_record(fingerprint: CompatibilityFingerprint) -> dict:
    value = fingerprint.to_dict()
    if set(value) != set(FIELDS):
        raise ValueError("Q1 live compatibility fingerprint schema mismatch")
    canonical = CompatibilityFingerprint.from_dict(value)
    if canonical.to_dict() != value:
        raise ValueError("Q1 live compatibility fingerprint is noncanonical")
    return {
        "compatibility_fingerprint_schema": Q1_FINGERPRINT_SCHEMA,
        "compatibility_fingerprint": value,
        "compatibility_fingerprint_sha256": canonical.digest(),
    }


def _validate_q1_fingerprint_record(
    state: dict,
    expected: dict,
) -> None:
    value = state.get("compatibility_fingerprint")
    if (
        state.get("compatibility_fingerprint_schema")
        != Q1_FINGERPRINT_SCHEMA
        or not isinstance(value, dict)
        or set(value) != set(FIELDS)
    ):
        raise ValueError("existing Q1 compatibility fingerprint schema mismatch")
    try:
        canonical = CompatibilityFingerprint.from_dict(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "existing Q1 compatibility fingerprint is invalid"
        ) from exc
    if (
        canonical.to_dict() != value
        or state.get("compatibility_fingerprint_sha256")
        != canonical.digest()
        or any(
            state.get(field) != expected.get(field)
            for field in (
                "compatibility_fingerprint_schema",
                "compatibility_fingerprint",
                "compatibility_fingerprint_sha256",
            )
        )
    ):
        raise ValueError(
            "existing Q1 compatibility fingerprint differs from live runtime"
        )


def _stable_rank(item_id: str) -> str:
    return hashlib.sha256(f"{SEED}:{item_id}".encode()).hexdigest()


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _runtime_budget_audit(full_cache, attention_mass):
    import torch

    from memsub.compaction import build_merge_plan, merge_cache

    audit = {}
    extreme_cache = None
    for ratio in RATIOS:
        plan = build_merge_plan(
            full_cache.physical_length,
            ratio,
            sink_token_count=SINKS,
        )
        candidate = merge_cache(full_cache, attention_mass, plan).cache
        kv_finite = all(
            bool(torch.isfinite(tensor).all())
            for layer_index in range(candidate.num_layers)
            for tensor in candidate.layer_kv(layer_index)
        )
        key = f"{ratio:.2f}"
        audit[key] = {
            "target_retained": plan.target_retained,
            "physical_length": candidate.physical_length,
            "kv_finite": kv_finite,
        }
        if ratio == 0.90:
            extreme_cache = candidate
    if extreme_cache is None:
        raise RuntimeError("registered extreme merge ratio is missing")
    return audit, extreme_cache


def _select_p0_rows(manifest: list[dict], recent_start: int) -> list[dict]:
    per_domain = P0_ITEMS // len(DOMAINS)
    selected = []
    for domain in DOMAINS:
        eligible = [
            row
            for row in manifest
            if row["domain"] == domain
            and row["raw_correct"]
            and SINKS <= row["chunk_rel_start"] + 512 < recent_start
        ]
        eligible.sort(key=lambda row: (_stable_rank(row["item_id"]), row["item_id"]))
        if len(eligible) < per_domain:
            raise ValueError(
                f"{domain}: need {per_domain} P0 rows, found {len(eligible)}"
            )
        selected.extend(eligible[:per_domain])
    return sorted(selected, key=lambda row: (row["domain"], _stable_rank(row["item_id"])))


def _run_p0(limit: int, out_name: str) -> dict:
    import sys

    sys.path.insert(0, "/root/repo")
    import torch

    from memsub.certification import eq_policy_v1
    from memsub.compaction import (
        build_merge_plan,
        merge_cache,
        prefill_with_real_attention,
    )
    from memsub.reference_config import build_runtime

    os.makedirs(ARTIFACT_ROOT, exist_ok=True)
    output_path = f"{ARTIFACT_ROOT}/{out_name}.json"
    with open("/artifacts/probe/capture-manifest.json") as handle:
        manifest = json.load(handle)
    plan = build_merge_plan(4096, 0.90, sink_token_count=SINKS)
    selected = _select_p0_rows(manifest, plan.recent_start)
    if limit:
        selected = selected[:limit]
    sample_item_ids = [row["item_id"] for row in selected]

    needed_docs = {row["doc_id"] for row in selected}
    texts = {}
    for domain in DOMAINS:
        with open(f"/artifacts/corpus/{domain}.jsonl") as handle:
            for line in handle:
                record = json.loads(line)
                if record["doc_id"] in needed_docs:
                    texts[record["doc_id"]] = record["text"]
    missing_docs = sorted(needed_docs - set(texts))
    if missing_docs:
        raise ValueError(f"P0 source documents missing: {missing_docs[:10]}")

    state = {
        "provenance": _provenance(),
        "sample_item_ids": sample_item_ids,
        "done": 0,
        "rows": [],
        "structure": None,
        "budget_audit": None,
        "superseded_artifact_sha256": None,
    }
    if os.path.exists(output_path):
        with open(output_path) as handle:
            prior = json.load(handle)
        if prior.get("sample_item_ids") != sample_item_ids:
            raise ValueError("existing P0 artifact uses a different registered sample")
        if prior.get("budget_audit") is not None:
            state = prior
        else:
            state["superseded_artifact_sha256"] = _sha256_file(output_path)

    runtime = build_runtime(reference=True)
    fingerprint = runtime.fingerprint()
    state["compatibility_fingerprint"] = fingerprint.to_dict()
    state["compatibility_fingerprint_sha256"] = fingerprint.digest()
    tokenizer = runtime.tokenizer
    continuation_ids = tokenizer.encode(
        CONTINUATION_TEXT, add_special_tokens=False
    )
    doc_cache: dict[str, list[int]] = {}
    torch.cuda.reset_peak_memory_stats()

    def save() -> None:
        state["peak_gpu_bytes"] = int(torch.cuda.max_memory_allocated())
        with open(output_path, "w") as handle:
            json.dump(state, handle, indent=1, allow_nan=False)
        artifacts.commit()

    for row_index, row in enumerate(selected):
        if row_index < state["done"]:
            continue
        if row["doc_id"] not in doc_cache:
            doc_cache.clear()
            doc_cache[row["doc_id"]] = tokenizer.encode(
                texts[row["doc_id"]], add_special_tokens=False
            )
        document_ids = doc_cache[row["doc_id"]]
        chunk_start = int(row["item_id"].split("_")[-2])
        context_start = max(
            0,
            min(
                chunk_start - row["chunk_rel_start"],
                len(document_ids) - plan.sequence_length,
            ),
        )
        context_ids = document_ids[
            context_start : context_start + plan.sequence_length
        ]
        if len(context_ids) != plan.sequence_length:
            raise ValueError(f"short P0 context for {row['item_id']}")

        full_cache, _, attention_mass = prefill_with_real_attention(
            runtime, context_ids
        )
        if state["budget_audit"] is None:
            state["budget_audit"], merged_cache = _runtime_budget_audit(
                full_cache, attention_mass
            )
        else:
            merged_cache = merge_cache(full_cache, attention_mass, plan).cache
        evicted_cache = full_cache.clone_detached()
        evicted_slots = evicted_cache.evict_logical_range(
            SINKS, SINKS + int(plan.sequence_length * 0.90)
        )
        streaming_cache = full_cache.clone_detached()
        streaming_slots = streaming_cache.evict_logical_range(
            SINKS, SINKS + int(plan.sequence_length * 0.90)
        )
        expected_evicted = plan.sequence_length - plan.target_retained
        if evicted_slots != expected_evicted or streaming_slots != expected_evicted:
            raise ValueError("P0 comparator budget mismatch")
        for arm_name, candidate in (
            ("merge", merged_cache),
            ("eviction", evicted_cache),
            ("streaming", streaming_cache),
        ):
            if candidate.physical_length != plan.target_retained:
                raise ValueError(
                    f"{arm_name} retained {candidate.physical_length}, "
                    f"expected {plan.target_retained}"
                )

        full_prediction = runtime.answer_letter(
            "", row["question"], row["options"], cache=full_cache
        )
        merge_prediction = runtime.answer_letter(
            "", row["question"], row["options"], cache=merged_cache
        )
        eviction_prediction = runtime.answer_letter(
            "", row["question"], row["options"], cache=evicted_cache
        )
        streaming_prediction = runtime.answer_letter(
            "", row["question"], row["options"], cache=streaming_cache
        )

        full_logits = runtime.forward_extend(
            full_cache.clone_detached(), continuation_ids
        )

        def mean_kl(candidate) -> float:
            candidate_logits = runtime.forward_extend(
                candidate.clone_detached(), continuation_ids
            )
            log_full = torch.log_softmax(full_logits, dim=-1)
            log_candidate = torch.log_softmax(candidate_logits, dim=-1)
            return float(
                (
                    log_full.exp() * (log_full - log_candidate)
                ).sum(dim=-1).mean()
            )

        full_correct = eq_policy_v1(full_prediction, row["gold"])
        result_row = {
            "item_id": row["item_id"],
            "doc_id": row["doc_id"],
            "domain": row["domain"],
            "gold": row["gold"],
            "full_prediction": full_prediction,
            "merge_prediction": merge_prediction,
            "eviction_prediction": eviction_prediction,
            "streaming_prediction": streaming_prediction,
            "full_correct": int(full_correct),
            "merge_correct": int(eq_policy_v1(merge_prediction, row["gold"])),
            "eviction_correct": int(
                eq_policy_v1(eviction_prediction, row["gold"])
            ),
            "streaming_correct": int(
                eq_policy_v1(streaming_prediction, row["gold"])
            ),
            "merge_lost_prior_correct": int(
                full_correct and not eq_policy_v1(merge_prediction, row["gold"])
            ),
            "eviction_lost_prior_correct": int(
                full_correct
                and not eq_policy_v1(eviction_prediction, row["gold"])
            ),
            "streaming_lost_prior_correct": int(
                full_correct
                and not eq_policy_v1(streaming_prediction, row["gold"])
            ),
            "merge_kl": mean_kl(merged_cache),
            "eviction_kl": mean_kl(evicted_cache),
            "streaming_kl": mean_kl(streaming_cache),
            "merge_streaming_prediction_equal": int(
                merge_prediction == streaming_prediction
            ),
            "attention_mass_min": float(attention_mass.min()),
            "attention_mass_max": float(attention_mass.max()),
            "attention_mass_variance": float(attention_mass.var()),
        }
        state["rows"].append(result_row)
        state["done"] = row_index + 1

        if state["structure"] is None:
            merge_exact = set(range(SINKS)) | set(
                range(plan.recent_start, plan.sequence_length)
            )
            streaming_exact = set(range(SINKS)) | set(
                range(
                    plan.sequence_length - (plan.target_retained - SINKS),
                    plan.sequence_length,
                )
            )
            common_exact = sorted(merge_exact & streaming_exact)
            merge_index = {
                logical: physical
                for physical, logical in enumerate(merged_cache.logical_positions)
            }
            streaming_index = {
                logical: physical
                for physical, logical in enumerate(
                    streaming_cache.logical_positions
                )
            }
            aligned_exact_max_abs = 0.0
            physical_max_abs = 0.0
            cache_equal = True
            for layer_index in range(full_cache.num_layers):
                for merge_tensor, stream_tensor in zip(
                    merged_cache.layer_kv(layer_index),
                    streaming_cache.layer_kv(layer_index),
                ):
                    cache_equal &= torch.equal(merge_tensor, stream_tensor)
                    physical_max_abs = max(
                        physical_max_abs,
                        float((merge_tensor.float() - stream_tensor.float()).abs().max()),
                    )
                    merge_slots = torch.tensor(
                        [merge_index[position] for position in common_exact],
                        device=merge_tensor.device,
                    )
                    stream_slots = torch.tensor(
                        [streaming_index[position] for position in common_exact],
                        device=stream_tensor.device,
                    )
                    aligned_exact_max_abs = max(
                        aligned_exact_max_abs,
                        float(
                            (
                                merge_tensor.index_select(2, merge_slots).float()
                                - stream_tensor.index_select(2, stream_slots).float()
                            ).abs().max()
                        ),
                    )
            block_sizes = [block.size for block in plan.blocks]
            state["structure"] = {
                "target_retained": plan.target_retained,
                "sink_slots": plan.sink_token_count,
                "summary_slots": plan.summary_count,
                "recent_exact_slots": plan.recent_count,
                "old_region_slots": sum(block_sizes),
                "non_singleton_blocks": sum(size > 1 for size in block_sizes),
                "block_size_min": min(block_sizes),
                "block_size_max": max(block_sizes),
                "block_size_counts": {
                    str(size): block_sizes.count(size)
                    for size in sorted(set(block_sizes))
                },
                "merge_exact_slots": len(merge_exact),
                "streaming_exact_slots": len(streaming_exact),
                "exact_slot_intersection": len(common_exact),
                "exact_slot_jaccard": (
                    len(common_exact) / len(merge_exact | streaming_exact)
                ),
                "aligned_exact_max_abs_kv_difference": aligned_exact_max_abs,
                "physical_max_abs_kv_difference": physical_max_abs,
                "cache_tensor_identical": bool(cache_equal),
            }

        if (
            state["done"] % P0_CHECKPOINT_EVERY == 0
            or state["done"] == len(selected)
        ):
            save()
            print(f"{out_name}: {state['done']}/{len(selected)}", flush=True)
            torch.cuda.empty_cache()

    save()
    prior_correct = sum(row["full_correct"] for row in state["rows"])
    return {
        "artifact": output_path,
        "items": len(state["rows"]),
        "prior_correct": prior_correct,
        "merge_lost_prior": sum(
            row["merge_lost_prior_correct"] for row in state["rows"]
        ),
        "eviction_lost_prior": sum(
            row["eviction_lost_prior_correct"] for row in state["rows"]
        ),
        "peak_gpu_bytes": state["peak_gpu_bytes"],
    }


def _load_q1_authorization(
    *,
    addendum_path: str = Q1_ADDENDUM_PATH,
    p0_verdict_path: str = Q1_P0_VERDICT_PATH,
) -> dict:
    if not os.path.exists(addendum_path) or not os.path.exists(p0_verdict_path):
        raise ValueError("Q1 addendum authorization files are missing")
    addendum_sha256 = _sha256_file(addendum_path)
    p0_verdict_sha256 = _sha256_file(p0_verdict_path)
    if (
        addendum_sha256 != Q1_ADDENDUM_SHA256
        or p0_verdict_sha256 != Q1_P0_VERDICT_SHA256
    ):
        raise ValueError("Q1 registered authorization hash mismatch")
    with open(p0_verdict_path) as handle:
        verdict = json.load(handle)
    settled = {
        "p0_3_pass": verdict.get("p0_3", {}).get("pass"),
        "p0_4_pass": verdict.get("p0_4", {}).get("pass"),
        "real_attention_pass": verdict.get("real_attention", {}).get("pass"),
        "p0_pass": verdict.get("p0_pass"),
        "stop_q1_q3": verdict.get("stop_q1_q3"),
    }
    expected = {
        "p0_3_pass": False,
        "p0_4_pass": True,
        "real_attention_pass": True,
        "p0_pass": False,
        "stop_q1_q3": True,
    }
    if settled != expected:
        raise ValueError("Q1 addendum requires the settled negative P0 verdict")
    return {
        "protocol": "MERGECERT-Q1",
        "budget_mode": Q1_BUDGET_MODE,
        "addendum_sha256": addendum_sha256,
        "p0_verdict_sha256": p0_verdict_sha256,
        "settled_p0": settled,
    }


def _load_q1_registration(
    *,
    registration_path: str = Q1_REGISTRATION_PATH,
    source_path: str = Q1_REGISTRATION_SOURCE_PATH,
) -> dict:
    if Q1_REGISTRATION_SHA256 == Q1_REGISTRATION_PENDING:
        raise ValueError(
            "Q1 finalized registration binding is pending CPU extraction "
            "and independent review"
        )
    if (
        not os.path.exists(registration_path)
        or not os.path.exists(source_path)
        or _sha256_file(source_path) != Q1_REGISTRATION_SOURCE_SHA256
    ):
        raise ValueError("Q1 finalized registration is missing or unbound")
    with open(source_path) as handle:
        source = json.load(handle)
    registration_sha256 = _sha256_file(registration_path)
    if registration_sha256 != Q1_REGISTRATION_SHA256:
        raise ValueError("Q1 finalized registration is missing or unbound")
    with open(registration_path) as handle:
        registration = json.load(handle)
    validate_q1_registration_schema(
        registration, source_registration=source
    )
    if (
        canonical_q1_registration_sha256(registration)
        != Q1_REGISTRATION_SHA256
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
        or registration.get("model_id") != MODEL_ID
        or source.get("tokenizer_revision") != Q1_TOKENIZER_REVISION
        or tokenizer.get("model_id") != MODEL_ID
        or tokenizer.get("revision") != Q1_TOKENIZER_REVISION
        or not isinstance(tokenizer_files, dict)
        or not tokenizer_files
        or any(
            not isinstance(name, str) or not _is_sha256(digest)
            for name, digest in tokenizer_files.items()
        )
        or tokenizer.get("artifact_sha256")
        != _json_sha256(tokenizer_files)
        or registration.get("source_registration_sha256")
        != Q1_REGISTRATION_SOURCE_SHA256
        or registration.get("population_doc_ids")
        != source["population_doc_ids"]
        or registration.get("smoke_doc_ids") != source["smoke_doc_ids"]
        or registration.get("all_items_sha256")
        != source["all_items_sha256"]
        or registration.get("archive_sha256")
        != source["archive_sha256"]
        or source_hashes.get("all_items_sha256")
        != source["all_items_sha256"]
        or not _is_sha256(
            source_hashes.get("corpus_manifest_sha256")
        )
        or not isinstance(source_document_sha256, dict)
        or set(source_document_sha256)
        != set(source["population_doc_ids"])
        or any(
            not _is_sha256(digest)
            for digest in source_document_sha256.values()
        )
    ):
        raise ValueError("Q1 finalized registration differs from source evidence")
    documents = registration.get("documents", [])
    if (
        len(documents) != Q1_EXPECTED_DOCUMENTS
        or [row.get("doc_id") for row in documents]
        != source["population_doc_ids"]
    ):
        raise ValueError("Q1 finalized registration population is incomplete")
    for document in documents:
        doc_id = document["doc_id"]
        source_tokens = document.get("source_context_token_count")
        model_tokens = document.get("model_input_token_count")
        if (
            not isinstance(document.get("context_start"), int)
            or isinstance(document["context_start"], bool)
            or document["context_start"]
            != max(
                0,
                source["anchor_chunk_token_start"][doc_id] - 1024,
            )
            or not isinstance(source_tokens, int)
            or isinstance(source_tokens, bool)
            or source_tokens <= SINKS
            or not isinstance(model_tokens, int)
            or isinstance(model_tokens, bool)
            or model_tokens <= SINKS
            or set(document.get("budgets", {})) != {"0.25", "0.40"}
        ):
            raise ValueError("Q1 finalized registration counts are invalid")
        for ratio in Q1_RATIOS:
            ratio_text = f"{ratio:.2f}"
            budget = document["budgets"][ratio_text]
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
            if set(budget) != set(fields) or any(
                not isinstance(budget.get(field), int)
                or isinstance(budget[field], bool)
                for field in fields
            ):
                raise ValueError("Q1 finalized registration counts are invalid")
            expected = _q1_document_budget(
                source_tokens,
                model_tokens,
                ratio,
                evicted_token_count=budget["evicted_token_count"],
                eviction_source_start=budget["eviction_source_start"],
                eviction_source_end=budget["eviction_source_end"],
                physical_before_count=budget["physical_before_count"],
                physical_after_count=budget["physical_after_count"],
            )
            if (
                budget["eviction_source_start"]
                != source["eviction_source_start"][doc_id]
                or budget["requested_evicted_token_count"]
                != int(source_tokens * ratio)
                or budget
                != {
                    key: value
                    for key, value in expected.items()
                    if key
                    not in (
                        "source_context_token_count",
                        "model_input_token_count",
                    )
                }
            ):
                raise ValueError("Q1 finalized registration budget is invalid")
    return {
        "sha256": registration_sha256,
        "payload": registration,
    }


def _q1_archive_files() -> tuple[dict, dict]:
    files = {}
    reports = {}
    for domain in DOMAINS:
        reports[domain] = {}
        for ratio in (0.0, 0.25, 0.40):
            name = f"{domain}-evict{ratio:.2f}.json"
            path = f"{Q1_ARCHIVE_ROOT}/{name}"
            if not os.path.exists(path):
                raise ValueError(f"missing archived M1 report: {path}")
            with open(path) as handle:
                rows = json.load(handle)
            if len(rows) != Q1_CONTEXTS_PER_DOMAIN:
                raise ValueError(
                    f"{name}: expected {Q1_CONTEXTS_PER_DOMAIN} reports, "
                    f"found {len(rows)}"
                )
            files[name] = {"path": path, "sha256": _sha256_file(path)}
            reports[domain][ratio] = rows
    return files, reports


def _reconstruct_q1_context_ids(
    tokenizer, text: str, *, chunk_token_start: int
) -> dict:
    document_ids = tokenizer.encode(text, add_special_tokens=False)
    context_start = max(0, chunk_token_start - 1024)
    source_context_ids = document_ids[context_start : context_start + 4096]
    if not source_context_ids:
        raise ValueError("archived M1 source context is empty")
    context_text = tokenizer.decode(source_context_ids)
    context_ids = tokenizer.encode(context_text, add_special_tokens=False)
    if len(context_ids) <= SINKS:
        raise ValueError("archived M1 model input is too short")
    return {
        "context_start": context_start,
        "source_context_ids": source_context_ids,
        "source_context_token_count": len(source_context_ids),
        "context_ids": context_ids,
        "model_input_token_count": len(context_ids),
    }


def _q1_document_budget(
    source_context_token_count: int,
    model_input_token_count: int,
    ratio: float,
    *,
    evicted_token_count: int | None = None,
    eviction_source_start: int | None = None,
    eviction_source_end: int | None = None,
    physical_before_count: int | None = None,
    physical_after_count: int | None = None,
) -> dict:
    if ratio not in Q1_RATIOS:
        raise ValueError(f"unregistered Q1 ratio: {ratio}")
    requested_evicted = int(source_context_token_count * ratio)
    source_start = (
        SINKS
        if eviction_source_start is None
        else eviction_source_start
    )
    source_end = (
        source_start + requested_evicted
        if eviction_source_end is None
        else eviction_source_end
    )
    evicted = (
        requested_evicted
        if evicted_token_count is None
        else evicted_token_count
    )
    physical_before = (
        model_input_token_count
        if physical_before_count is None
        else physical_before_count
    )
    physical_after = (
        physical_before - evicted
        if physical_after_count is None
        else physical_after_count
    )
    retained = physical_after
    counts = (
        source_context_token_count,
        model_input_token_count,
        source_start,
        source_end,
        physical_before,
        physical_after,
        evicted,
    )
    expected_physical_removed = max(
        0,
        min(source_end, physical_before)
        - min(max(source_start, 0), physical_before),
    )
    if (
        any(not isinstance(value, int) or isinstance(value, bool) for value in counts)
        or source_context_token_count <= SINKS
        or model_input_token_count <= SINKS
        or source_start < SINKS
        or source_end - source_start != requested_evicted
        or physical_before != model_input_token_count
        or physical_before - physical_after != evicted
        or evicted != expected_physical_removed
        or evicted <= 0
        or retained <= SINKS
    ):
        raise ValueError("Q1 per-document budget is invalid")
    return {
        "source_context_token_count": source_context_token_count,
        "model_input_token_count": model_input_token_count,
        "requested_evicted_token_count": requested_evicted,
        "eviction_source_start": source_start,
        "eviction_source_end": source_end,
        "physical_before_count": physical_before,
        "physical_after_count": physical_after,
        "evicted_token_count": evicted,
        "retained_token_count": retained,
        "merge_target_retained": retained,
    }


def _q1_merge_plan(model_input_token_count: int, target_retained: int):
    from memsub.compaction import build_merge_plan

    evicted = model_input_token_count - target_retained
    if evicted <= 0:
        raise ValueError("Q1 merge budget must evict at least one token")
    effective_fraction = math.nextafter(
        evicted / model_input_token_count, 1.0
    )
    plan = build_merge_plan(
        model_input_token_count,
        effective_fraction,
        sink_token_count=SINKS,
    )
    if plan.target_retained != target_retained:
        raise ValueError("Q1 merge plan did not reproduce the matched budget")
    return plan


def _load_q1_source_texts(
    doc_ids: list[str], *, corpus_root: str = "/artifacts/corpus"
) -> dict[str, str]:
    expected = set(doc_ids)
    texts = {}
    domains = {doc_id.split("/", 1)[0] for doc_id in doc_ids}
    for domain in sorted(domains):
        with open(f"{corpus_root}/{domain}.jsonl") as handle:
            for line in handle:
                row = json.loads(line)
                doc_id = row.get("doc_id")
                if doc_id not in expected:
                    continue
                if doc_id in texts:
                    raise ValueError(
                        f"duplicate Q1 source document row: {doc_id}"
                    )
                if not isinstance(row.get("text"), str):
                    raise ValueError(f"{doc_id}: Q1 source text is invalid")
                texts[doc_id] = row["text"]
    missing = sorted(expected - set(texts))
    if missing:
        raise ValueError(f"Q1 source documents missing: {missing[:10]}")
    return texts


def _verify_q1_source_integrity(
    registration: dict,
    doc_ids: list[str],
    *,
    corpus_root: str = "/artifacts/corpus",
    manifest_path: str = "/artifacts/corpus/manifest.json",
    items_path: str = Q1_ITEMS_PATH,
) -> tuple[dict[str, str], dict]:
    source_hashes = registration.get("source_hashes", {})
    if (
        _sha256_file(manifest_path)
        != source_hashes.get("corpus_manifest_sha256")
        or _sha256_file(items_path)
        != source_hashes.get("all_items_sha256")
    ):
        raise ValueError("Q1 source manifest or all-items hash drift")
    texts = _load_q1_source_texts(doc_ids, corpus_root=corpus_root)
    expected_documents = source_hashes.get("source_document_sha256", {})
    actual_documents = {
        doc_id: hashlib.sha256(texts[doc_id].encode("utf-8")).hexdigest()
        for doc_id in doc_ids
    }
    expected_selected = {
        doc_id: expected_documents.get(doc_id) for doc_id in doc_ids
    }
    if actual_documents != expected_selected:
        raise ValueError("Q1 source document hash drift")
    return texts, {
        "corpus_manifest_sha256": source_hashes[
            "corpus_manifest_sha256"
        ],
        "all_items_sha256": source_hashes["all_items_sha256"],
    }


def _verify_q1_tokenizer_integrity(registration: dict) -> dict[str, str]:
    """Verify the live offline snapshot before model construction."""

    snapshot = resolve_q1_tokenizer_snapshot()
    files_sha256 = tokenizer_artifact_digests(
        snapshot,
        expected_files_sha256=Q1_TOKENIZER_FILES_SHA256,
    )
    if (
        registration["tokenizer"]["files_sha256"] != files_sha256
        or registration["tokenizer"]["artifact_sha256"]
        != Q1_TOKENIZER_ARTIFACT_SHA256
    ):
        raise ValueError("Q1 live tokenizer differs from registration")
    return files_sha256


def _load_q1_contexts(
    tokenizer,
    archived_reports: dict,
    *,
    texts: dict[str, str],
    source_hashes: dict,
) -> tuple[list, dict]:
    from memsub.certification import McqItem

    with open(Q1_ITEMS_PATH) as handle:
        items = [McqItem(**row) for row in json.load(handle)]
    by_doc = {}
    for item in items:
        by_doc.setdefault(item.doc_id, []).append(item)

    needed_docs = {
        report["eval_protocol"]["context_doc_id"]
        for domain in DOMAINS
        for report in archived_reports[domain][0.25]
    }
    missing = sorted(needed_docs - set(texts))
    if missing:
        raise ValueError(f"Q1 source documents missing: {missing[:10]}")

    contexts = []
    for domain in DOMAINS:
        archive_rows = archived_reports[domain][0.25]
        for archive_index, archive in enumerate(archive_rows):
            doc_id = archive["eval_protocol"]["context_doc_id"]
            doc_items = by_doc.get(doc_id, [])
            if not doc_items:
                raise ValueError(f"Q1 items missing for {doc_id}")
            anchor = doc_items[0]
            reconstructed = _reconstruct_q1_context_ids(
                tokenizer,
                texts[doc_id],
                chunk_token_start=anchor.chunk_token_start,
            )
            ctx_start = reconstructed["context_start"]
            source_context_token_count = reconstructed[
                "source_context_token_count"
            ]
            context_ids = reconstructed["context_ids"]
            model_input_token_count = reconstructed[
                "model_input_token_count"
            ]
            reference_span = int(source_context_token_count * 0.25)
            lo = max(
                SINKS,
                min(
                    anchor.chunk_token_start - ctx_start,
                    source_context_token_count - reference_span,
                ),
            )
            needles = [
                item
                for item in doc_items
                if lo
                <= item.chunk_token_start - ctx_start
                < lo + reference_span
            ] or [anchor]
            needles = needles[:8]
            needle_ids = {item.item_id for item in needles}
            aggregations = [
                item for item in doc_items if item.item_id not in needle_ids
            ][:8]
            archived_needle_ids = [
                row["item_id"] for row in archive["probe_records"]
            ]
            if [item.item_id for item in needles] != archived_needle_ids:
                raise ValueError(
                    f"{doc_id}: reconstructed needle partition differs "
                    "from archived M1"
                )
            contexts.append(
                {
                    "doc_id": doc_id,
                    "domain": domain,
                    "archive_index": archive_index,
                    "context_start": ctx_start,
                    "context_ids": context_ids,
                    "source_context_token_count": (
                        source_context_token_count
                    ),
                    "model_input_token_count": model_input_token_count,
                    "context_sha256": _json_sha256(context_ids),
                    "source_hashes": {
                        **source_hashes,
                        "source_document_sha256": hashlib.sha256(
                            texts[doc_id].encode()
                        ).hexdigest(),
                    },
                    "eviction_anchor": lo,
                    "needles": needles,
                    "aggregations": aggregations,
                }
            )
    if len(contexts) != Q1_EXPECTED_DOCUMENTS:
        raise ValueError(
            f"Q1 reconstructed {len(contexts)} documents, "
            f"expected {Q1_EXPECTED_DOCUMENTS}"
        )
    return contexts, source_hashes


def _q1_eviction_range(
    ratio: float, anchor: int, source_context_token_count: int
) -> tuple[int, int]:
    span = int(source_context_token_count * ratio)
    if ratio == 0.90:
        return SINKS, SINKS + span
    return anchor, anchor + span


def _q1_report(
    runtime,
    *,
    context: dict,
    full_cache,
    candidate_cache,
    ratio: float,
    policy: str,
    budget: dict,
    full_predictions: dict,
) -> dict:
    import torch

    from memsub.certification import eq_policy_v1

    continuation_ids = runtime.tokenizer.encode(
        CONTINUATION_TEXT, add_special_tokens=False
    )
    if candidate_cache.physical_length != budget["retained_token_count"]:
        raise ValueError(f"{policy}: candidate retained-vector budget mismatch")
    full_logits = runtime.forward_extend(
        full_cache.clone_detached(), continuation_ids
    )
    candidate_logits = runtime.forward_extend(
        candidate_cache.clone_detached(), continuation_ids
    )
    log_full = torch.log_softmax(full_logits, dim=-1)
    log_candidate = torch.log_softmax(candidate_logits, dim=-1)
    mean_kl = float(
        (log_full.exp() * (log_full - log_candidate)).sum(dim=-1).mean()
    )

    def score(items, axis: str):
        rows = []
        for item in items:
            prediction = runtime.answer_letter(
                "", item.question, item.options, cache=candidate_cache
            )
            full_prediction = full_predictions[item.item_id]
            rows.append(
                {
                    "item_id": item.item_id,
                    "axis": axis,
                    "gold": item.gold_letter,
                    "full_prediction": full_prediction,
                    "candidate_prediction": prediction,
                    "full_correct": int(
                        eq_policy_v1(full_prediction, item.gold_letter)
                    ),
                    "candidate_correct": int(
                        eq_policy_v1(prediction, item.gold_letter)
                    ),
                }
            )
        return rows

    aggregation_rows = score(context["aggregations"], "aggregation")
    needle_rows = score(context["needles"], "pointwise")
    aggregation_count = len(aggregation_rows)
    needle_count = len(needle_rows)
    full_agg_correct = sum(row["full_correct"] for row in aggregation_rows)
    candidate_agg_correct = sum(
        row["candidate_correct"] for row in aggregation_rows
    )
    full_needle_correct = sum(row["full_correct"] for row in needle_rows)
    candidate_needle_correct = sum(
        row["candidate_correct"] for row in needle_rows
    )
    lost_prior = sum(
        row["full_correct"] and not row["candidate_correct"]
        for row in needle_rows
    )
    return {
        "doc_id": context["doc_id"],
        "domain": context["domain"],
        "context_start": context["context_start"],
        "context_sha256": context["context_sha256"],
        "source_context_token_count": context[
            "source_context_token_count"
        ],
        "model_input_token_count": context["model_input_token_count"],
        "context_token_count": context["model_input_token_count"],
        "requested_evicted_token_count": budget[
            "requested_evicted_token_count"
        ],
        "eviction_source_start": budget["eviction_source_start"],
        "eviction_source_end": budget["eviction_source_end"],
        "physical_before_count": budget["physical_before_count"],
        "physical_after_count": budget["physical_after_count"],
        "evicted_token_count": budget["evicted_token_count"],
        "target_retained": candidate_cache.physical_length,
        "source_hashes": context["source_hashes"],
        "needle_item_ids": [item.item_id for item in context["needles"]],
        "aggregation_item_ids": [
            item.item_id for item in context["aggregations"]
        ],
        "aggregation_axis": {
            "mean_kl": round(mean_kl, 6),
            "full_context_accuracy": round(
                full_agg_correct / max(aggregation_count, 1), 4
            ),
            "compacted_accuracy": round(
                candidate_agg_correct / max(aggregation_count, 1), 4
            ),
            "accuracy_delta": round(
                (candidate_agg_correct - full_agg_correct)
                / max(aggregation_count, 1),
                4,
            ),
            "probe_count": aggregation_count,
        },
        "pointwise_axis": {
            "needle_probe_count": needle_count,
            "needle_correct_before_eviction": full_needle_correct,
            "needle_correct_after_eviction": candidate_needle_correct,
            "expand_calls": 0,
            "lost_fact_incident_rate": round(
                (needle_count - candidate_needle_correct)
                / max(needle_count, 1),
                4,
            ),
            "lost_fact_rate_given_prior_correct": round(
                lost_prior / max(full_needle_correct, 1), 4
            ),
        },
        "policy": policy,
        "ratio": ratio,
        "continuation_text": CONTINUATION_TEXT,
        "probe_records": aggregation_rows + needle_rows,
    }


def _verify_archived_replay(
    report: dict,
    archive: dict,
    *,
    archive_name: str,
    archive_sha256: str,
    arm_name: str,
) -> dict:
    mismatches = []
    for axis in ("aggregation_axis", "pointwise_axis"):
        for key, archived_value in archive[axis].items():
            if key not in report[axis]:
                continue
            actual_value = report[axis][key]
            if isinstance(archived_value, (int, float)):
                if abs(float(actual_value) - float(archived_value)) > 1e-6:
                    mismatches.append(
                        f"{axis}.{key}: {actual_value} != {archived_value}"
                    )
            elif actual_value != archived_value:
                mismatches.append(
                    f"{axis}.{key}: {actual_value!r} != {archived_value!r}"
                )
    by_id = {
        row["item_id"]: row
        for row in report["probe_records"]
        if row["axis"] == "pointwise"
    }
    for archived_probe in archive["probe_records"]:
        actual = by_id.get(archived_probe["item_id"])
        if actual is None:
            mismatches.append(
                f"missing pointwise probe {archived_probe['item_id']}"
            )
            continue
        if actual["full_prediction"] != archived_probe["pred_full_context"]:
            mismatches.append(
                f"{archived_probe['item_id']}: full prediction drift"
            )
        if actual["candidate_prediction"] != archived_probe["pred_compacted"]:
            mismatches.append(
                f"{archived_probe['item_id']}: candidate prediction drift"
            )
    return {
        "archive": archive_name,
        "archive_sha256": archive_sha256,
        "arm": arm_name,
        "doc_id": report["doc_id"],
        "pass": not mismatches,
        "mismatches": mismatches,
    }


def _restore_q1_completed_prefix(
    state: dict,
    selected_doc_ids: list[str],
) -> None:
    done = state.get("done_documents")
    arm_names = (
        "control-0.00",
        *[f"eviction-{ratio:.2f}" for ratio in Q1_RATIOS],
        *[f"merge-{ratio:.2f}" for ratio in Q1_RATIOS],
    )
    replay_arms = (
        "control-0.00",
        *[f"eviction-{ratio:.2f}" for ratio in Q1_RATIOS],
    )
    if (
        not isinstance(done, int)
        or isinstance(done, bool)
        or not 0 <= done <= len(selected_doc_ids)
        or set(state.get("arms", {})) != set(arm_names)
    ):
        raise ValueError("existing Q1 artifact has invalid progress")
    completed_doc_ids = selected_doc_ids[:done]
    documents = state.get("documents")
    if (
        not isinstance(documents, list)
        or len(documents) < done
        or [row.get("doc_id") for row in documents[:done]]
        != completed_doc_ids
    ):
        raise ValueError("existing Q1 artifact has invalid document progress")
    for arm_name in arm_names:
        reports = state["arms"][arm_name].get("reports")
        if (
            not isinstance(reports, list)
            or len(reports) < done
            or [row.get("doc_id") for row in reports[:done]]
            != completed_doc_ids
        ):
            raise ValueError("existing Q1 artifact has invalid arm progress")
        del reports[done:]
    checks = state.get("archived_m1", {}).get("replay_checks")
    expected_replay_prefix = [
        (doc_id, arm_name)
        for doc_id in completed_doc_ids
        for arm_name in replay_arms
    ]
    if (
        not isinstance(checks, list)
        or len(checks) < len(expected_replay_prefix)
        or [
            (row.get("doc_id"), row.get("arm"))
            for row in checks[: len(expected_replay_prefix)]
        ]
        != expected_replay_prefix
        or not all(
            row.get("pass") is True
            for row in checks[: len(expected_replay_prefix)]
        )
    ):
        raise ValueError("existing Q1 artifact has invalid replay progress")
    del documents[done:]
    del checks[len(expected_replay_prefix) :]
    state["archived_m1"]["replay_pass"] = (
        done == len(selected_doc_ids) and bool(checks)
    )


def _resume_q1_state(
    prior: dict,
    fresh: dict,
    selected_doc_ids: list[str],
) -> dict:
    if prior.get("sample_doc_ids") != fresh.get("sample_doc_ids"):
        raise ValueError("existing Q1 artifact uses a different sample")
    if prior.get("q1_authorization") != fresh.get("q1_authorization"):
        raise ValueError("existing Q1 artifact uses a different authorization")
    if (
        prior.get("q1_registration_sha256")
        != fresh.get("q1_registration_sha256")
    ):
        raise ValueError("existing Q1 artifact uses a different registration")
    done = prior.get("done_documents")
    if (
        not isinstance(done, int)
        or isinstance(done, bool)
        or not 0 <= done <= len(selected_doc_ids)
    ):
        raise ValueError("existing Q1 artifact has invalid progress")
    if done == 0:
        legacy_provenance = dict(fresh["provenance"])
        legacy_provenance.pop("execution_semantics")
        if prior.get("provenance") not in (
            fresh["provenance"],
            legacy_provenance,
        ):
            raise ValueError(
                "existing Q1 artifact uses a different Q1 provenance"
            )
        _restore_q1_completed_prefix(prior, selected_doc_ids)
        return fresh
    if (
        prior.get("execution_semantics")
        != fresh.get("execution_semantics")
        or prior.get("provenance", {}).get("execution_semantics")
        != fresh.get("provenance", {}).get("execution_semantics")
    ):
        raise ValueError(
            "existing Q1 artifact uses different execution semantics"
        )
    if prior.get("provenance") != fresh.get("provenance"):
        raise ValueError("existing Q1 artifact uses a different Q1 provenance")
    _validate_q1_fingerprint_record(prior, fresh)
    _restore_q1_completed_prefix(prior, selected_doc_ids)
    return prior


def _run_q1(*, documents: int, output_path: str, require_full: bool) -> dict:
    import sys

    sys.path.insert(0, "/root/repo")
    import torch

    from memsub.compaction import (
        merge_cache,
        prefill_with_real_attention,
    )
    from memsub.reference_config import build_runtime

    gate = _load_q1_authorization()
    registration_record = _load_q1_registration()
    registration = registration_record["payload"]
    archive_files, archived_reports = _q1_archive_files()
    if (
        {
            name: row["sha256"] for name, row in archive_files.items()
        }
        != registration["archive_sha256"]
    ):
        raise ValueError("Q1 archive files differ from finalized registration")
    texts, source_hashes = _verify_q1_source_integrity(
        registration,
        registration["population_doc_ids"],
    )
    _verify_q1_tokenizer_integrity(registration)
    runtime = build_runtime(
        reference=True,
        revision="cdbee75f17c01a7cc42f958dc650907174af0554",
        local_files_only=True,
    )
    fingerprint = runtime.fingerprint()
    contexts, source_hashes = _load_q1_contexts(
        runtime.tokenizer,
        archived_reports,
        texts=texts,
        source_hashes=source_hashes,
    )
    if require_full and documents != Q1_EXPECTED_DOCUMENTS:
        raise ValueError(
            f"Q1 certification is registered at {Q1_EXPECTED_DOCUMENTS} documents"
        )
    contexts = contexts[:documents]
    selected_doc_ids = [context["doc_id"] for context in contexts]
    expected_doc_ids = (
        registration["population_doc_ids"]
        if require_full
        else registration["smoke_doc_ids"]
    )
    if selected_doc_ids != expected_doc_ids:
        raise ValueError("Q1 selected documents differ from finalized registration")
    registered_documents = {
        row["doc_id"]: row for row in registration["documents"]
    }
    for context in contexts:
        registered = registered_documents[context["doc_id"]]
        for field in (
            "context_start",
            "source_context_token_count",
            "model_input_token_count",
        ):
            if context[field] != registered[field]:
                raise ValueError(
                    f"{context['doc_id']}: finalized registration {field} drift"
                )
    arm_specs = [
        ("control-0.00", "zero-compression-control", 0.0),
        *[
            (f"eviction-{ratio:.2f}", "contiguous-eviction", ratio)
            for ratio in Q1_RATIOS
        ],
        *[
            (f"merge-{ratio:.2f}", "attention-weighted-merge", ratio)
            for ratio in Q1_RATIOS
        ],
    ]
    fingerprint_record = _q1_fingerprint_record(fingerprint)
    state = {
        "provenance": _q1_provenance(),
        "execution_semantics": _q1_execution_semantics(),
        **fingerprint_record,
        "q1_authorization": gate,
        "q1_registration_sha256": registration_record["sha256"],
        "archived_m1": {
            "files": archive_files,
            "replay_checks": [],
            "replay_pass": False,
        },
        "references": Q1_REFERENCES,
        "reference_sources": Q1_REFERENCE_SOURCES,
        "source_hashes": source_hashes,
        "sample_doc_ids": selected_doc_ids,
        "documents": [],
        "arms": {
            name: {
                "policy": policy,
                "ratio": ratio,
                "budget_mode": Q1_BUDGET_MODE,
                "reports": [],
            }
            for name, policy, ratio in arm_specs
        },
        "done_documents": 0,
    }
    if os.path.exists(output_path):
        with open(output_path) as handle:
            prior = json.load(handle)
        if prior.get("sample_doc_ids") != selected_doc_ids:
            raise ValueError("existing Q1 artifact uses a different sample")
        if prior.get("q1_authorization") != gate:
            raise ValueError("existing Q1 artifact uses a different authorization")
        if (
            prior.get("q1_registration_sha256")
            != registration_record["sha256"]
        ):
            raise ValueError("existing Q1 artifact uses a different registration")
        state = _resume_q1_state(prior, state, selected_doc_ids)

    def save() -> None:
        state["peak_gpu_bytes"] = int(torch.cuda.max_memory_allocated())
        checks = state["archived_m1"]["replay_checks"]
        state["archived_m1"]["replay_pass"] = (
            len(checks) == len(selected_doc_ids) * 3
            and all(check["pass"] for check in checks)
        )
        with open(output_path, "w") as handle:
            json.dump(state, handle, indent=1, allow_nan=False)
        artifacts.commit()

    torch.cuda.reset_peak_memory_stats()
    for document_index, context in enumerate(contexts):
        if document_index < state["done_documents"]:
            continue
        replay_full_cache, _ = runtime.prefill(context["context_ids"])

        all_items = context["aggregations"] + context["needles"]
        replay_full_predictions = {
            item.item_id: runtime.answer_letter(
                "", item.question, item.options, cache=replay_full_cache
            )
            for item in all_items
        }
        replay_candidate_caches = {
            "control-0.00": replay_full_cache.clone_detached()
        }
        candidate_budgets = {
            "control-0.00": {
                "source_context_token_count": context[
                    "source_context_token_count"
                ],
                "model_input_token_count": context[
                    "model_input_token_count"
                ],
                "requested_evicted_token_count": 0,
                "eviction_source_start": 0,
                "eviction_source_end": 0,
                "physical_before_count": context[
                    "model_input_token_count"
                ],
                "physical_after_count": context[
                    "model_input_token_count"
                ],
                "evicted_token_count": 0,
                "retained_token_count": context[
                    "model_input_token_count"
                ],
                "merge_target_retained": context[
                    "model_input_token_count"
                ],
            }
        }
        for ratio in Q1_RATIOS:
            replay_eviction = replay_full_cache.clone_detached()
            physical_before = replay_eviction.physical_length
            start, end = _q1_eviction_range(
                ratio,
                context["eviction_anchor"],
                context["source_context_token_count"],
            )
            evicted = replay_eviction.evict_logical_range(start, end)
            physical_after = replay_eviction.physical_length
            budget = _q1_document_budget(
                context["source_context_token_count"],
                context["model_input_token_count"],
                ratio,
                evicted_token_count=evicted,
                eviction_source_start=start,
                eviction_source_end=end,
                physical_before_count=physical_before,
                physical_after_count=physical_after,
            )
            registered_budget = registered_documents[context["doc_id"]][
                "budgets"
            ][f"{ratio:.2f}"]
            if budget != {
                "source_context_token_count": context[
                    "source_context_token_count"
                ],
                "model_input_token_count": context[
                    "model_input_token_count"
                ],
                **registered_budget,
            }:
                raise ValueError(
                    f"{context['doc_id']}: finalized registration budget drift"
                )
            if (
                replay_eviction.physical_length
                != budget["retained_token_count"]
            ):
                raise ValueError("Q1 measured eviction budget is inconsistent")
            replay_candidate_caches[
                f"eviction-{ratio:.2f}"
            ] = replay_eviction
            candidate_budgets[f"eviction-{ratio:.2f}"] = budget
            candidate_budgets[f"merge-{ratio:.2f}"] = budget

        replay_specs = [
            ("control-0.00", "zero-compression-control", 0.0),
            *[
                (f"eviction-{ratio:.2f}", "contiguous-eviction", ratio)
                for ratio in Q1_RATIOS
            ],
        ]
        for arm_name, policy, ratio in replay_specs:
            replay_report = _q1_report(
                runtime,
                context=context,
                full_cache=replay_full_cache,
                candidate_cache=replay_candidate_caches[arm_name],
                ratio=ratio,
                policy=policy,
                budget=candidate_budgets[arm_name],
                full_predictions=replay_full_predictions,
            )
            archive = archived_reports[context["domain"]][ratio][
                context["archive_index"]
            ]
            archive_name = f"{context['domain']}-evict{ratio:.2f}.json"
            check = _verify_archived_replay(
                replay_report,
                archive,
                archive_name=archive_name,
                archive_sha256=archive_files[archive_name]["sha256"],
                arm_name=arm_name,
            )
            state["archived_m1"]["replay_checks"].append(check)
            if not check["pass"]:
                save()
                raise ValueError(
                    f"{context['doc_id']}: archived M1 replay failed for "
                    f"{arm_name}: {check['mismatches'][:3]}"
                )

        del replay_report, replay_candidate_caches
        del replay_full_predictions, replay_full_cache
        del replay_eviction
        q1_full_cache, _, attention_mass = prefill_with_real_attention(
            runtime, context["context_ids"]
        )
        if (
            not torch.isfinite(attention_mass).all()
            or float(attention_mass.min()) < 0
            or float(attention_mass.var()) <= 0
        ):
            raise ValueError(f"{context['doc_id']}: invalid real attention mass")
        full_predictions = {
            item.item_id: runtime.answer_letter(
                "", item.question, item.options, cache=q1_full_cache
            )
            for item in all_items
        }
        candidate_caches = {
            "control-0.00": q1_full_cache.clone_detached()
        }
        for ratio in Q1_RATIOS:
            eviction = q1_full_cache.clone_detached()
            start, end = _q1_eviction_range(
                ratio,
                context["eviction_anchor"],
                context["source_context_token_count"],
            )
            evicted = eviction.evict_logical_range(start, end)
            budget = candidate_budgets[f"eviction-{ratio:.2f}"]
            if (
                eviction.physical_length
                != budget["retained_token_count"]
                or evicted != budget["evicted_token_count"]
            ):
                raise ValueError("Q1 measured eviction budget is inconsistent")
            candidate_caches[f"eviction-{ratio:.2f}"] = eviction
            plan = _q1_merge_plan(
                context["model_input_token_count"],
                budget["merge_target_retained"],
            )
            candidate_caches[f"merge-{ratio:.2f}"] = merge_cache(
                q1_full_cache, attention_mass, plan
            ).cache

        document_record = {
            "doc_id": context["doc_id"],
            "domain": context["domain"],
            "context_start": context["context_start"],
            "context_sha256": context["context_sha256"],
            "source_context_token_count": context[
                "source_context_token_count"
            ],
            "model_input_token_count": context["model_input_token_count"],
            "context_token_count": context["model_input_token_count"],
            "budgets": {
                f"{ratio:.2f}": candidate_budgets[
                    f"eviction-{ratio:.2f}"
                ]
                for ratio in Q1_RATIOS
            },
            "source_hashes": context["source_hashes"],
            "needle_item_ids": [
                item.item_id for item in context["needles"]
            ],
            "aggregation_item_ids": [
                item.item_id for item in context["aggregations"]
            ],
            "attention_mass_min": float(attention_mass.min()),
            "attention_mass_max": float(attention_mass.max()),
            "attention_mass_variance": float(attention_mass.var()),
        }
        state["documents"].append(document_record)
        for arm_name, policy, ratio in arm_specs:
            report = _q1_report(
                runtime,
                context=context,
                full_cache=q1_full_cache,
                candidate_cache=candidate_caches[arm_name],
                ratio=ratio,
                policy=policy,
                budget=candidate_budgets[arm_name],
                full_predictions=full_predictions,
            )
            state["arms"][arm_name]["reports"].append(report)
        state["done_documents"] = document_index + 1
        save()
        print(
            f"Q1: {state['done_documents']}/{len(contexts)} documents",
            flush=True,
        )
        del candidate_caches, q1_full_cache, full_predictions
        del attention_mass, eviction
        torch.cuda.empty_cache()

    save()
    if not state["archived_m1"]["replay_pass"]:
        raise ValueError("Q1 archived M1 replay did not pass")
    return {
        "artifact": output_path,
        "documents": state["done_documents"],
        "archive_replay_pass": state["archived_m1"]["replay_pass"],
        "peak_gpu_bytes": state["peak_gpu_bytes"],
    }


@app.function(
    image=image,
    gpu="H100",
    volumes=VOLUMES,
    timeout=43_200,
    memory=65_536,
)
def smoke(limit: int = 8) -> dict:
    return _run_p0(limit, "p0-smoke")


@app.function(
    image=image,
    gpu="H100",
    volumes=VOLUMES,
    timeout=43_200,
    memory=65_536,
)
def p0_direction(n_items: int = P0_ITEMS) -> dict:
    if n_items != P0_ITEMS:
        raise ValueError(f"P0 direction is registered at exactly {P0_ITEMS} items")
    return _run_p0(n_items, "p0-direction-200")


@app.function(
    image=image,
    gpu="H100",
    volumes=VOLUMES,
    timeout=43_200,
    memory=65_536,
)
def q1_addendum_smoke(documents: int = 2) -> dict:
    if documents != 2:
        raise ValueError("Q1 smoke is registered at exactly two documents")
    return _run_q1(
        documents=documents,
        output_path=Q1_SMOKE_OUTPUT,
        require_full=False,
    )


@app.function(
    image=image,
    gpu="H100",
    volumes=VOLUMES,
    timeout=43_200,
    memory=65_536,
)
def q1_addendum_certify(contexts_per_domain: int = Q1_CONTEXTS_PER_DOMAIN) -> dict:
    if contexts_per_domain != Q1_CONTEXTS_PER_DOMAIN:
        raise ValueError(
            "Q1 is registered at exactly five contexts per domain"
        )
    return _run_q1(
        documents=Q1_EXPECTED_DOCUMENTS,
        output_path=Q1_OUTPUT,
        require_full=True,
    )
