"""GT5 — Redaction traces the graph (M0).

Redact a source span -> every derived artifact (summary, shadow, checkpoint
pages, consolidated blocks) reachable via derived_from is invalidated; a
subsequent read of any of them fails closed; redaction_generation increments.
"""

import pytest

from memsub.errors import RedactionError


def _build(substrate):
    thread_id = substrate.new_thread()
    substrate.append_turns(thread_id, [
        {"role": "user", "text": "the secret launch code is 7743 " * 10},
        {"role": "assistant", "text": "acknowledged, storing the plan " * 12},
        {"role": "user", "text": "unrelated follow-up chatter " * 12},
    ])
    cache = substrate.prefill_thread(thread_id)
    results = substrate.compact_under_pressure(thread_id, cache, target_evict_tokens=48)
    assert results, "test requires at least one compacted block"
    ckpt = substrate.checkpoint(thread_id, cache)
    return thread_id, cache, results, ckpt


@pytest.mark.golden
def test_gt5_redaction_invalidates_all_derived_artifacts(substrate):
    thread_id, cache, results, ckpt = _build(substrate)
    block = results[0].block
    span_id = block.derived_from[0]
    gen_before = substrate.index.get_thread(thread_id)["redaction_generation"]

    report = substrate.redact(span_id)

    # redaction_generation increments.
    assert report.redaction_generation == gen_before + 1
    assert substrate.index.get_thread(thread_id)["redaction_generation"] == gen_before + 1

    # The derived block (carrying summary + shadow) is invalidated.
    assert block.block_id in report.invalidated_blocks
    assert substrate.index.get_block_row(block.block_id)["invalidated"] == 1

    # The checkpoint whose KV was computed in the span's presence is invalidated.
    assert ckpt.checkpoint_id in report.invalidated_checkpoints

    # Subsequent reads fail closed.
    with pytest.raises(RedactionError):
        substrate.archive.get_span_text(span_id)
    with pytest.raises(RedactionError):
        substrate.expander.expand_block(block)
    with pytest.raises(RedactionError):
        substrate.checkpoints.load_checkpoint(ckpt.checkpoint_id)
    with pytest.raises(RedactionError):
        substrate.checkpoints.hydrate(ckpt.checkpoint_id,
                                      substrate.runtime.fingerprint())

    # Invalidated blocks disappear from selection and the L1 fallback.
    assert all(b.block_id != block.block_id for b in substrate.blocks(thread_id))
    outcome = substrate.resume(thread_id)
    assert outcome.path_taken.startswith("fallback")


@pytest.mark.golden
def test_gt5_resume_survives_when_redaction_kills_every_block(substrate):
    """If redaction invalidates ALL blocks, the L0 fallback must re-prefill
    from surviving spans only — never read the redacted span, never crash."""
    thread_id = substrate.new_thread()
    substrate.append_turns(thread_id, [
        {"role": "user", "text": "opener " * 30},
        {"role": "assistant", "text": "sensitive middle content " * 20},
        {"role": "user", "text": "harmless tail " * 20},
    ])
    cache = substrate.prefill_thread(thread_id)
    results = substrate.compact_under_pressure(thread_id, cache, 1)  # one block
    assert len(results) == 1
    substrate.redact(results[0].block.derived_from[0])
    assert not substrate.blocks(thread_id)  # every block invalidated

    outcome = substrate.resume(thread_id)
    assert outcome.path_taken == "fallback_full"
    assert outcome.prefill_token_count > 0


@pytest.mark.golden
def test_gt5_redaction_of_unrelated_span_leaves_artifacts_alive(substrate):
    thread_id, cache, results, ckpt = _build(substrate)
    block = results[0].block
    spans = substrate.archive.spans_for_thread(thread_id)
    unrelated = [r for r in spans
                 if r["token_start"] >= block.source.token_end][-1]

    substrate.redact(unrelated["span_id"])

    # Block derived from a different span stays live...
    assert substrate.index.get_block_row(block.block_id)["invalidated"] == 0
    # ...but the checkpoint covering the whole thread still dies (stale
    # survivors carry the redacted span's influence, spec 13.1).
    assert substrate.index.get_checkpoint_row(ckpt.checkpoint_id)["invalidated"] == 1
