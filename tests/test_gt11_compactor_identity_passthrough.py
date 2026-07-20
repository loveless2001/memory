"""GT11 — near-pass-through at init (COMPACTOR.md §2.3).

With identity-style init and t = T (one latent per non-sink position), the
compact-cache continuation logits must match the full-cache logits BEFORE
any training. This is the cheap detector for RoPE-fix / re-rotation /
position-offset bugs (the spec §12 failure class). Nothing trains until
this is green.
"""

import pytest
import torch

from conftest import GT1_TOP_K, REFERENCE, corpus_token_ids

from memsub.compactor import StillAmortizedKVCompactor

T_TOTAL = 1028 if REFERENCE else 132   # sinks(4) + t latents
PROB_TOL = 0.05 if REFERENCE else 5e-3


@pytest.mark.golden
def test_gt11_identity_init_passthrough(runtime):
    torch.manual_seed(0)
    ids = corpus_token_ids(runtime.tokenizer, T_TOTAL)
    n_continue = 8

    cache_full, _ = runtime.prefill(ids)
    compactor = StillAmortizedKVCompactor(
        runtime.model.config, t_latents=T_TOTAL - 4).to(
        runtime.device, runtime.model.dtype)

    compact = compactor.compact(cache_full.clone_detached())
    assert compact.physical_length == T_TOTAL          # sinks + t
    assert compact.next_logical_position == T_TOTAL
    assert compact.logical_positions[:4] == [0, 1, 2, 3]

    probe = runtime.tokenizer.encode("\n", add_special_tokens=False)[0]
    logits_full = runtime.forward_extend(cache_full, [probe])[-1]
    with torch.inference_mode():
        logits_compact = runtime.forward_extend(compact.clone_detached(),
                                                [probe])[-1]

    p_full = torch.softmax(logits_full, -1)
    p_comp = torch.softmax(logits_compact, -1)
    top_full = set(torch.topk(p_full, GT1_TOP_K).indices.tolist())
    top_comp = set(torch.topk(p_comp, GT1_TOP_K).indices.tolist())
    overlap = len(top_full & top_comp)
    assert overlap >= GT1_TOP_K - 1, f"top-k sets diverged: {overlap}/{GT1_TOP_K}"
    max_delta = float((p_full - p_comp).abs().max())
    assert max_delta < PROB_TOL, f"max prob delta {max_delta}"

    # multi-step greedy agreement
    steps_full = runtime.continue_greedy(cache_full, n_continue,
                                         logits_full, top_k=GT1_TOP_K)
    with torch.inference_mode():
        steps_comp = runtime.continue_greedy(compact, n_continue,
                                             logits_compact, top_k=GT1_TOP_K)
    agree = sum(a.token_id == b.token_id
                for a, b in zip(steps_full, steps_comp))
    assert agree >= n_continue - 1, f"greedy agreement {agree}/{n_continue}"


@pytest.mark.golden
def test_gt15_depth_refusal_unit():
    """Resume paths refuse to stack compactions past max_certified_depth."""
    from transformers import Qwen3Config
    from memsub.compactor.still_amortized_kv_compactor import assert_depth_allowed
    from memsub.errors import CompatibilityError
    cfg = Qwen3Config(vocab_size=128, hidden_size=64, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2, head_dim=16)
    comp = StillAmortizedKVCompactor(cfg, t_latents=8)
    comp.max_certified_depth = 4
    assert_depth_allowed(comp, 4)
    with pytest.raises(CompatibilityError):
        assert_depth_allowed(comp, 5)


@pytest.mark.golden
def test_compactor_checkpoint_round_trips_experiment_provenance(tmp_path):
    """Weights bind the exact train/eval partition used to produce them."""
    from transformers import Qwen3Config
    cfg = Qwen3Config(vocab_size=128, hidden_size=64, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2, head_dim=16)
    comp = StillAmortizedKVCompactor(cfg, t_latents=8)
    comp.training_manifest_sha256 = "train-sha"
    comp.certification_holdout_sha256 = "holdout-sha"
    path = tmp_path / "compactor.safetensors"

    comp.save(str(path))
    loaded = StillAmortizedKVCompactor.load(str(path), cfg)

    assert loaded.training_manifest_sha256 == "train-sha"
    assert loaded.certification_holdout_sha256 == "holdout-sha"
