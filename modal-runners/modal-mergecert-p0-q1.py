"""MERGECERT P0/Q1 — private port verification and M1 placement.

The runner is deliberately evaluation-only.  P0 must pass before Q1 is
launched; every artifact stays on the private ``memsub-artifacts`` volume.
"""

import hashlib
import json
import os

import modal

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
UPSTREAM_COMMIT = "cd4ed948d62231449dbab9669608bbb4fd220713"
RATIOS = (0.25, 0.40, 0.90)
Q1_RATIOS = (0.25, 0.40)
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
    .add_local_dir("memsub", "/root/repo/memsub")
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
        "seed": SEED,
    }


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
        "addendum_sha256": _sha256_file(addendum_path),
        "p0_verdict_sha256": _sha256_file(p0_verdict_path),
        "settled_p0": settled,
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


def _require_registered_q1_context_length(
    doc_id: str, context_ids: list[int]
) -> None:
    if len(context_ids) != 4096:
        raise ValueError(
            f"{doc_id}: archived M1 source context has {len(context_ids)} "
            "tokens; registered Q1 requires exactly 4096"
        )


def _load_q1_contexts(tokenizer, archived_reports: dict) -> tuple[list, dict]:
    from memsub.certification import McqItem

    with open(Q1_ITEMS_PATH) as handle:
        items = [McqItem(**row) for row in json.load(handle)]
    source_hashes = {
        "corpus_manifest_sha256": _sha256_file(
            "/artifacts/corpus/manifest.json"
        ),
        "all_items_sha256": _sha256_file(Q1_ITEMS_PATH),
    }
    by_doc = {}
    for item in items:
        by_doc.setdefault(item.doc_id, []).append(item)

    needed_docs = {
        report["eval_protocol"]["context_doc_id"]
        for domain in DOMAINS
        for report in archived_reports[domain][0.25]
    }
    texts = {}
    for domain in DOMAINS:
        with open(f"/artifacts/corpus/{domain}.jsonl") as handle:
            for line in handle:
                row = json.loads(line)
                if row["doc_id"] in needed_docs:
                    texts[row["doc_id"]] = row["text"]
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
            document_ids = tokenizer.encode(
                texts[doc_id], add_special_tokens=False
            )
            ctx_start = max(0, anchor.chunk_token_start - 1024)
            source_context_ids = document_ids[ctx_start : ctx_start + 4096]
            _require_registered_q1_context_length(doc_id, source_context_ids)
            context_text = tokenizer.decode(source_context_ids)
            context_ids = tokenizer.encode(
                context_text, add_special_tokens=False
            )
            if len(context_ids) != 4096:
                raise ValueError(
                    f"{doc_id}: archived M1 context re-encodes to "
                    f"{len(context_ids)}, expected 4096"
                )
            reference_span = int(len(context_ids) * 0.25)
            lo = max(
                SINKS,
                min(
                    anchor.chunk_token_start - ctx_start,
                    len(context_ids) - reference_span,
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


def _q1_eviction_range(ratio: float, anchor: int) -> tuple[int, int]:
    span = int(4096 * ratio)
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
    full_predictions: dict,
) -> dict:
    import torch

    from memsub.certification import eq_policy_v1

    continuation_ids = runtime.tokenizer.encode(
        CONTINUATION_TEXT, add_special_tokens=False
    )
    if candidate_cache.physical_length != 4096 - int(4096 * ratio):
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
        "context_token_count": 4096,
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
    report: dict, archive: dict, *, archive_name: str
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
        "doc_id": report["doc_id"],
        "pass": not mismatches,
        "mismatches": mismatches,
    }


def _run_q1(*, documents: int, output_path: str, require_full: bool) -> dict:
    import sys

    sys.path.insert(0, "/root/repo")
    import torch

    from memsub.compaction import (
        build_merge_plan,
        merge_cache,
        prefill_with_real_attention,
    )
    from memsub.reference_config import build_runtime

    gate = _load_q1_authorization()
    archive_files, archived_reports = _q1_archive_files()
    runtime = build_runtime(reference=True)
    fingerprint = runtime.fingerprint()
    contexts, source_hashes = _load_q1_contexts(
        runtime.tokenizer, archived_reports
    )
    if require_full and documents != Q1_EXPECTED_DOCUMENTS:
        raise ValueError(
            f"Q1 certification is registered at {Q1_EXPECTED_DOCUMENTS} documents"
        )
    contexts = contexts[:documents]
    selected_doc_ids = [context["doc_id"] for context in contexts]
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
    state = {
        "provenance": _q1_provenance(),
        "compatibility_fingerprint": fingerprint.to_dict(),
        "compatibility_fingerprint_sha256": fingerprint.digest(),
        "q1_authorization": gate,
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
                "target_retained": 4096 - int(4096 * ratio),
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
        if prior.get("provenance") != _q1_provenance():
            raise ValueError("existing Q1 artifact uses a different Q1 provenance")
        state = prior

    def save() -> None:
        state["peak_gpu_bytes"] = int(torch.cuda.max_memory_allocated())
        checks = state["archived_m1"]["replay_checks"]
        state["archived_m1"]["replay_pass"] = bool(checks) and all(
            check["pass"] for check in checks
        )
        with open(output_path, "w") as handle:
            json.dump(state, handle, indent=1, allow_nan=False)
        artifacts.commit()

    torch.cuda.reset_peak_memory_stats()
    for document_index, context in enumerate(contexts):
        if document_index < state["done_documents"]:
            continue
        full_cache, _, attention_mass = prefill_with_real_attention(
            runtime, context["context_ids"]
        )
        if (
            not torch.isfinite(attention_mass).all()
            or float(attention_mass.min()) < 0
            or float(attention_mass.var()) <= 0
        ):
            raise ValueError(f"{context['doc_id']}: invalid real attention mass")

        all_items = context["aggregations"] + context["needles"]
        full_predictions = {
            item.item_id: runtime.answer_letter(
                "", item.question, item.options, cache=full_cache
            )
            for item in all_items
        }
        candidate_caches = {"control-0.00": full_cache.clone_detached()}
        for ratio in Q1_RATIOS:
            eviction = full_cache.clone_detached()
            start, end = _q1_eviction_range(
                ratio, context["eviction_anchor"]
            )
            evicted = eviction.evict_logical_range(start, end)
            if evicted != int(4096 * ratio):
                raise ValueError(
                    f"{context['doc_id']}: eviction {ratio:.2f} removed "
                    f"{evicted}, expected {int(4096 * ratio)}"
                )
            candidate_caches[f"eviction-{ratio:.2f}"] = eviction
            plan = build_merge_plan(4096, ratio, sink_token_count=SINKS)
            candidate_caches[f"merge-{ratio:.2f}"] = merge_cache(
                full_cache, attention_mass, plan
            ).cache

        document_record = {
            "doc_id": context["doc_id"],
            "domain": context["domain"],
            "context_start": context["context_start"],
            "context_sha256": context["context_sha256"],
            "context_token_count": 4096,
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
                full_cache=full_cache,
                candidate_cache=candidate_caches[arm_name],
                ratio=ratio,
                policy=policy,
                full_predictions=full_predictions,
            )
            state["arms"][arm_name]["reports"].append(report)
            if ratio in (0.0, 0.25, 0.40) and arm_name.startswith(
                ("control", "eviction")
            ):
                archive = archived_reports[context["domain"]][ratio][
                    context["archive_index"]
                ]
                archive_name = (
                    f"{context['domain']}-evict{ratio:.2f}.json"
                )
                check = _verify_archived_replay(
                    report, archive, archive_name=archive_name
                )
                state["archived_m1"]["replay_checks"].append(check)
                if not check["pass"]:
                    save()
                    raise ValueError(
                        f"{context['doc_id']}: archived M1 replay failed for "
                        f"{arm_name}: {check['mismatches'][:3]}"
                    )
        state["done_documents"] = document_index + 1
        save()
        print(
            f"Q1: {state['done_documents']}/{len(contexts)} documents",
            flush=True,
        )
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
