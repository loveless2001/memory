"""Position/RoPE machinery cross-check (spec 12).

After evicting a middle span, continuation over the compacted cache must be
mathematically identical to a dense forward over the FULL sequence with a 4D
attention mask that hides the evicted span from the continuation tokens:
surviving keys keep their original rotations and values, and continuation
tokens get logical RoPE positions. Any offset/mask bug breaks this equality.
"""

import pytest
import torch

from conftest import REFERENCE, corpus_token_ids

# fp32 CPU is near-exact; bf16 GPU compares different kernel paths (batched
# dense prefill vs incremental decode), so compare distributions, not logits.
PROB_TOL = 0.02 if REFERENCE else 1e-4


@pytest.mark.golden
def test_evicted_continuation_matches_dense_masked_forward(runtime):
    tokenizer = runtime.tokenizer
    T = 96
    ids = corpus_token_ids(tokenizer, T)
    cont_ids = tokenizer.encode(" and then the meeting ended",
                                add_special_tokens=False)
    evict_start, evict_end = 16, 48

    # Path A: compacted cache continuation.
    cache, _ = runtime.prefill(ids)
    cache.evict_logical_range(evict_start, evict_end)
    assert cache.physical_length == T - (evict_end - evict_start)
    assert cache.logical_offset == evict_end - evict_start
    logits_compact = runtime.forward_extend(cache, cont_ids)

    # Path B: dense forward, full sequence, 4D mask hiding the evicted span
    # from the continuation rows only (history rows keep full causal view,
    # matching the fact that surviving KV was computed in the span's presence).
    full = torch.tensor([ids + cont_ids], dtype=torch.long, device=runtime.device)
    total = full.shape[1]
    mask = torch.zeros((1, 1, total, total), dtype=torch.float32,
                       device=runtime.device)
    causal = torch.triu(torch.ones(total, total, dtype=torch.bool,
                                   device=runtime.device), diagonal=1)
    mask[0, 0][causal] = float("-inf")
    mask[0, 0, T:, evict_start:evict_end] = float("-inf")
    dtype = runtime.model.dtype
    with torch.inference_mode():
        out = runtime.model(input_ids=full, attention_mask=mask.to(dtype))
    logits_dense = out.logits[0, T:].float()

    probs_compact = torch.softmax(logits_compact, dim=-1)
    probs_dense = torch.softmax(logits_dense, dim=-1)
    assert (probs_compact.argmax(-1) == probs_dense.argmax(-1)).all(), \
        "argmax token diverged between compacted and dense-masked paths"
    max_delta = float((probs_compact - probs_dense).abs().max())
    assert max_delta < PROB_TOL, f"max prob delta {max_delta}"
