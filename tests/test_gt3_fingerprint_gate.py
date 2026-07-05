"""GT3 — Fingerprint gate (M2).

Mutate any single fingerprint field on a stored checkpoint -> resume MUST
take the fallback path (summary/full re-prefill), never load KV.
Parameterized over every field in the fingerprint schema (spec 4.6).
"""

import json

import pytest

from memsub.fingerprint import FIELDS


def _mutate(value):
    if value is None:
        return "sha256:injected-adapter"
    return value + "-MUTATED" if isinstance(value, str) else f"{value}-MUTATED"


def _build_thread_with_checkpoint(substrate):
    thread_id = substrate.new_thread()
    substrate.append_turns(thread_id, [
        {"role": "user", "text": "alpha " * 60},
        {"role": "assistant", "text": "beta " * 60},
        {"role": "user", "text": "gamma " * 60},
    ])
    cache = substrate.prefill_thread(thread_id)
    substrate.compact_under_pressure(thread_id, cache, target_evict_tokens=64)
    ckpt = substrate.checkpoint(thread_id, cache)
    return thread_id, ckpt


@pytest.mark.golden
@pytest.mark.parametrize("mutated_field", FIELDS)
def test_gt3_single_field_mutation_forces_fallback(substrate, mutated_field):
    thread_id, ckpt = _build_thread_with_checkpoint(substrate)

    # Mutate exactly one fingerprint field on the STORED checkpoint.
    row = substrate.index.get_checkpoint_row(ckpt.checkpoint_id)
    body = json.loads(row["body_json"])
    body["compatibility_fingerprint"][mutated_field] = _mutate(
        body["compatibility_fingerprint"][mutated_field])
    substrate.index.conn.execute(
        "UPDATE checkpoints SET body_json = ? WHERE checkpoint_id = ?",
        (json.dumps(body), ckpt.checkpoint_id))
    substrate.index.conn.commit()

    # Track KV blob reads: fallback must never open a KV page.
    kv_page_uris = {p["storage_uri"] for p in json.loads(
        substrate.blobs.get(ckpt.kv_page_table_uri))["pages"]}
    opened = []
    original_path_for = substrate.blobs.path_for

    def tracking_path_for(uri):
        if uri in kv_page_uris:
            opened.append(uri)
        return original_path_for(uri)

    substrate.blobs.path_for = tracking_path_for
    try:
        outcome = substrate.resume(thread_id, ckpt.checkpoint_id)
    finally:
        substrate.blobs.path_for = original_path_for

    assert outcome.path_taken in ("fallback_summary", "fallback_full")
    assert "CompatibilityError" in outcome.reason
    assert opened == [], "fallback path must never load KV pages"
    assert outcome.cache.physical_length > 0  # re-prefill actually happened


@pytest.mark.golden
def test_gt3_unmutated_checkpoint_hydrates(substrate):
    thread_id, ckpt = _build_thread_with_checkpoint(substrate)
    outcome = substrate.resume(thread_id, ckpt.checkpoint_id)
    assert outcome.path_taken == "hydrate"
