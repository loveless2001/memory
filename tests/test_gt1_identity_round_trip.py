"""GT1 — Identity round trip (P1 gate).

full prefill -> snapshot -> restore at K = T -> continue N tokens. Logits
match the never-snapshotted continuation within kernel nondeterminism
tolerance (top-k token sets + max prob delta, not bitwise). T in {1k, 8k}
on the reference config; the tiny local config runs T=256 to validate the
position/cache machinery. This is the only test that surfaces spec 12's
silent position-corruption failure mode.
"""

import pytest

from conftest import GT1_MAX_PROB_DELTA, GT1_TOP_K, REFERENCE, corpus_token_ids

from memsub.runtime import CompactedPrefixCache

T_VALUES = [1024, 8192] if REFERENCE else [256]
N_CONTINUE = 32 if REFERENCE else 12


def _continue_from(runtime, cache, probe_token: int, n: int):
    logits = runtime.forward_extend(cache, [probe_token])[-1]
    return runtime.continue_greedy(cache, n, logits, top_k=GT1_TOP_K)


def _assert_steps_match(steps_a, steps_b):
    assert [s.token_id for s in steps_a] == [s.token_id for s in steps_b], \
        "greedy continuations diverged"
    for sa, sb in zip(steps_a, steps_b):
        assert set(sa.top_ids) == set(sb.top_ids), \
            f"top-{GT1_TOP_K} token sets differ: {sa.top_ids} vs {sb.top_ids}"
        pa = dict(zip(sa.top_ids, sa.top_probs))
        pb = dict(zip(sb.top_ids, sb.top_probs))
        max_delta = max(abs(pa[t] - pb[t]) for t in pa)
        assert max_delta < GT1_MAX_PROB_DELTA, f"max prob delta {max_delta}"


@pytest.mark.golden
@pytest.mark.parametrize("T", T_VALUES)
@pytest.mark.parametrize("restore_path", ["memory", "disk"])
def test_gt1_identity_round_trip(runtime, tmp_path, T, restore_path):
    ids = corpus_token_ids(runtime.tokenizer, T)
    probe = runtime.tokenizer.encode("\n", add_special_tokens=False)[0]

    # Reference: never snapshotted.
    cache_ref, _ = runtime.prefill(ids)
    steps_ref = _continue_from(runtime, cache_ref, probe, N_CONTINUE)

    # Candidate: prefill -> snapshot -> restore at K = T -> continue.
    cache_snap, _ = runtime.prefill(ids)
    assert cache_snap.physical_length == T and cache_snap.logical_offset == 0

    if restore_path == "memory":
        keys = [cache_snap.layer_kv(i)[0].clone() for i in range(cache_snap.num_layers)]
        values = [cache_snap.layer_kv(i)[1].clone() for i in range(cache_snap.num_layers)]
        restored = CompactedPrefixCache.from_tensors(
            keys, values, logical_positions=list(cache_snap.logical_positions),
            next_logical_position=cache_snap.next_logical_position)
    else:
        from memsub.checkpoints import SafetensorsDeltaCheckpointStore
        from memsub.store import BlobStore, SqliteIndex
        index = SqliteIndex(tmp_path / "index.sqlite3")
        store = SafetensorsDeltaCheckpointStore(index, BlobStore(tmp_path))
        index.create_thread("th_gt1")
        ckpt = store.write_checkpoint("th_gt1", cache_snap, runtime.fingerprint(),
                                      memory_block_ids=[], surviving_token_ids=ids)
        restored = store.hydrate(ckpt.checkpoint_id, runtime.fingerprint(),
                                 device=runtime.device)

    assert restored.physical_length == T
    assert restored.next_logical_position == T
    steps_cand = _continue_from(runtime, restored, probe, N_CONTINUE)
    _assert_steps_match(steps_ref, steps_cand)
