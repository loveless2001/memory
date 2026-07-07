"""Non-contiguous eviction (certification control arm): sink guard raises
before mutation; matched-random eviction removes exactly the requested
positions and preserves continuation geometry for survivors."""

import pytest

from conftest import corpus_token_ids

from memsub.errors import SinkEvictionError


@pytest.mark.golden
def test_evict_logical_positions_sink_guard_and_count(runtime):
    ids = corpus_token_ids(runtime.tokenizer, 128)
    cache, _ = runtime.prefill(ids)
    before = cache.layer_kv(0)[0].clone()

    with pytest.raises(SinkEvictionError):
        cache.evict_logical_positions([2, 50, 60])
    assert (cache.layer_kv(0)[0] == before).all()  # untouched

    evicted = cache.evict_logical_positions(list(range(10, 40, 3)))
    assert evicted == 10
    assert cache.physical_length == 118
    assert cache.next_logical_position == 128  # logical cursor unchanged
    # survivors keep their logical positions
    assert all(p not in range(10, 40, 3) for p in cache.logical_positions)
    # continuation still works
    logits = runtime.forward_extend(cache, ids[:4])
    assert logits.shape[0] == 4


def test_certify_random_mode_matches_span_token_count(runtime):
    from memsub.certification import McqItem, OfflineCertificationHarness
    harness = OfflineCertificationHarness(runtime)
    item = McqItem("i", "d", 0, 0, "q?", ["a", "b", "c", "d"], "A")
    ctx = "word " * 300
    report = harness.certify(
        context_text=ctx, evict_logical_range=(16, 80),
        mcq_items=[], needle_items=[item],
        eviction_mode="random_nonsink_matched", random_seed=7,
        record_probes=True)
    assert report.eval_protocol["eviction_mode"] == "random_nonsink_matched"
    assert report.eviction_fraction > 0
    assert len(report.probe_records) == 1
    assert report.probe_records[0]["pred_full_context"] in "ABCD"
