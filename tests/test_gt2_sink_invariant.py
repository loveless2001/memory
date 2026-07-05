"""GT2 — Sink invariant (M1).

Any compaction plan that would evict positions 0-3 must raise BEFORE touching
the cache; the checkpoint records sink_tokens_retained; restore hydrates sink
pages first (spec 13.2).
"""

import pytest

from conftest import corpus_token_ids

from memsub.errors import SinkEvictionError


@pytest.mark.golden
def test_gt2_eviction_plan_touching_sinks_raises_before_mutation(runtime):
    ids = corpus_token_ids(runtime.tokenizer, 192)
    cache, _ = runtime.prefill(ids)
    before = [cache.layer_kv(i)[0].clone() for i in range(cache.num_layers)]

    with pytest.raises(SinkEvictionError):
        cache.evict_logical_range(0, 64)   # covers sink positions 0-3
    with pytest.raises(SinkEvictionError):
        cache.evict_logical_range(2, 10)

    # Cache untouched: same physical length, bitwise-identical tensors.
    assert cache.physical_length == len(ids)
    for i in range(cache.num_layers):
        assert (cache.layer_kv(i)[0] == before[i]).all()


@pytest.mark.golden
def test_gt2_compactor_path_asserts_sinks(substrate):
    thread_id = substrate.new_thread()
    substrate.append_turns(thread_id, [
        {"role": "user", "text": "sink opener " * 30},
        {"role": "assistant", "text": "reply " * 40},
    ])
    cache = substrate.prefill_thread(thread_id)
    first_span = substrate.archive.spans_for_thread(thread_id)[0]
    assert first_span["token_start"] == 0  # covers the sinks
    with pytest.raises(SinkEvictionError):
        substrate.compactor.compact_span(thread_id, cache, first_span)


@pytest.mark.golden
def test_gt2_checkpoint_records_sinks_and_hydrates_them_first(substrate):
    thread_id = substrate.new_thread()
    substrate.append_turns(thread_id, [
        {"role": "user", "text": "alpha " * 150},
        {"role": "assistant", "text": "beta " * 150},
        {"role": "user", "text": "gamma " * 150},
    ])
    cache = substrate.prefill_thread(thread_id)
    substrate.compact_under_pressure(thread_id, cache, target_evict_tokens=64)
    assert cache.logical_offset > 0  # eviction actually happened

    ckpt = substrate.checkpoint(thread_id, cache)
    assert ckpt.sink_tokens_retained == [0, 1, 2, 3]

    restored = substrate.checkpoints.hydrate(
        ckpt.checkpoint_id, substrate.runtime.fingerprint(),
        device=substrate.runtime.device)
    order = substrate.checkpoints.last_hydration_order
    assert order[0] == "sink"
    assert "sink" not in order[order.index("normal"):], \
        "all sink pages must hydrate before any normal page"
    assert set(restored.logical_positions[:4]) == {0, 1, 2, 3}
