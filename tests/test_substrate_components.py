"""Unit tests: fingerprint, blob store, segmenter, shadows, selector,
EXPAND, delta-checkpoint dedup."""

import dataclasses
import json

import pytest

from memsub.fingerprint import FIELDS
from memsub.store import BlobStore


def test_fingerprint_covers_schema_and_is_stable(runtime):
    fp1 = runtime.fingerprint()
    assert set(fp1.to_dict().keys()) == set(FIELDS)
    from memsub.fingerprint import compute_fingerprint
    fp2 = compute_fingerprint(
        runtime.model.config, runtime.tokenizer, model_id=runtime.model_id,
        attention_impl=runtime.attention_impl, quantization=runtime.quantization,
        device=runtime.device)
    assert fp1.matches(fp2), "fingerprint must be deterministic on one build"
    mutated = dataclasses.replace(fp1, quantization="int8")
    assert not fp1.matches(mutated)


def test_blob_store_content_addressing_and_integrity(tmp_path):
    store = BlobStore(tmp_path)
    uri1 = store.put(b"hello substrate")
    uri2 = store.put(b"hello substrate")
    assert uri1 == uri2, "identical content -> identical blob"
    assert store.get(uri1) == b"hello substrate"
    # Corrupt the blob on disk -> read fails closed.
    store.path_for(uri1).write_bytes(b"tampered")
    from memsub.errors import IntegrityError
    with pytest.raises(IntegrityError):
        store.get(uri1)


def test_segmenter_turn_boundaries_and_token_cap(runtime):
    from memsub.archive import segment_turns
    tokenizer = runtime.tokenizer
    turns = [
        {"role": "user", "text": "short question"},
        {"role": "assistant", "text": "word " * 300},  # > cap of 64
    ]
    segments = segment_turns(turns, tokenizer=tokenizer, max_tokens=64)
    assert segments[0].role == "user"
    assert all(seg.token_end - seg.token_start <= 64 for seg in segments)
    # spans never cross a turn boundary
    roles = [seg.role for seg in segments]
    assert roles == sorted(roles, key=lambda r: 0 if r == "user" else 1)
    # token ranges are contiguous from 0
    pos = 0
    for seg in segments:
        assert seg.token_start == pos
        pos = seg.token_end
    # concatenated span tokens reproduce each turn's token stream
    assistant_ids = [t for seg in segments if seg.role == "assistant"
                     for t in seg.token_ids]
    assert assistant_ids == tokenizer.encode("word " * 300, add_special_tokens=False)


def test_every_block_has_shadow_and_raw_pointer(substrate):
    thread_id = substrate.new_thread()
    substrate.append_turns(thread_id, [
        {"role": "user", "text": "alpha " * 60},
        {"role": "assistant", "text": "the project deadline is March 14 " * 10},
        {"role": "user", "text": "closing remarks " * 20},
    ])
    cache = substrate.prefill_thread(thread_id)
    results = substrate.compact_under_pressure(thread_id, cache, 48)
    assert results
    for res in results:
        block = res.block
        assert block.embedding_shadow.checksum.startswith("sha256:")
        assert block.source.uri.startswith("store://")
        assert block.derived_from, "GT5 depends on derived_from being populated"
        assert block.primary.format == "summary_text"
        assert block.primary.compatibility_fingerprint is None


def test_selector_and_runtime_gated_expand(substrate):
    thread_id = substrate.new_thread()
    substrate.append_turns(thread_id, [
        # opener span covers the pinned sinks and is never compacted
        {"role": "user", "text": "session opener greetings " * 8},
        {"role": "user", "text": "we discussed the vault security code today " * 8},
        {"role": "assistant", "text": "the weather in oslo was rainy all week " * 8},
        {"role": "user", "text": "trailing filler content " * 20},
    ])
    cache = substrate.prefill_thread(thread_id)
    substrate.compact_under_pressure(thread_id, cache, 160)
    blocks = substrate.blocks(thread_id)
    assert len(blocks) >= 2

    results = substrate.expand(thread_id, "what was the vault security code?")
    assert results, "gate should fire for an on-topic query"
    top = results[0]
    assert top.channel == "RETRIEVED_EXACT"
    assert "vault security code" in top.injection_text


def test_delta_checkpoints_share_unchanged_pages(substrate):
    thread_id = substrate.new_thread()
    substrate.append_turns(thread_id, [
        {"role": "user", "text": "alpha " * 120},
    ])
    cache = substrate.prefill_thread(thread_id)
    ckpt1 = substrate.checkpoint(thread_id, cache)
    pages1 = {p["storage_uri"] for p in json.loads(
        substrate.blobs.get(ckpt1.kv_page_table_uri))["pages"]}

    # Append tokens (no eviction) -> old pages must be reused byte-identical.
    extra = substrate.runtime.tokenizer.encode(" more text", add_special_tokens=False)
    substrate.runtime.forward_extend(cache, extra)
    ckpt2 = substrate.checkpoint(thread_id, cache)
    pages2 = {p["storage_uri"] for p in json.loads(
        substrate.blobs.get(ckpt2.kv_page_table_uri))["pages"]}

    assert ckpt2.parent_checkpoint_id == ckpt1.checkpoint_id  # CoW lineage
    shared = pages1 & pages2
    assert len(shared) >= len(pages1) // 2, \
        f"delta property broken: only {len(shared)} of {len(pages1)} pages shared"


def test_resume_fallback_when_no_checkpoint_exists(substrate):
    thread_id = substrate.new_thread()
    substrate.append_turns(thread_id, [{"role": "user", "text": "hello " * 40}])
    outcome = substrate.resume(thread_id)
    assert outcome.path_taken == "fallback_full"
    assert outcome.cache.physical_length > 0
