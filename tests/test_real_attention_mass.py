from types import SimpleNamespace

import pytest
import torch
from torch import nn
from transformers.cache_utils import DynamicCache

from memsub.compaction.real_attention_mass import (
    prefill_with_real_attention,
    reduce_gqa_attention,
)
from memsub.compaction.attention_weighted_kv_merge import (
    build_merge_plan,
    merge_cache,
)


def test_reduce_gqa_attention_accumulates_query_groups_into_shared_kv_heads():
    attention = torch.zeros((1, 4, 2, 3), dtype=torch.float32)
    attention[:, 0] = 1
    attention[:, 1] = 2
    attention[:, 2] = 3
    attention[:, 3] = 4

    mass = reduce_gqa_attention(attention, num_key_value_heads=2)

    assert mass.shape == (1, 2, 3)
    assert mass[0, 0].tolist() == [6, 6, 6]
    assert mass[0, 1].tolist() == [14, 14, 14]


def test_reduce_gqa_attention_rejects_a_nondivisible_head_mapping():
    attention = torch.ones((1, 5, 2, 3))

    with pytest.raises(ValueError, match="divisible"):
        reduce_gqa_attention(attention, num_key_value_heads=2)


def test_reduce_gqa_attention_rejects_a_nonpositive_kv_head_count():
    attention = torch.ones((1, 4, 2, 3))

    with pytest.raises(ValueError, match="positive"):
        reduce_gqa_attention(attention, num_key_value_heads=0)


def test_reduce_gqa_attention_requires_a_four_dimensional_attention_map():
    attention = torch.ones((4, 2, 3))

    with pytest.raises(ValueError, match="four dimensions"):
        reduce_gqa_attention(attention, num_key_value_heads=2)


class _FakeSelfAttention(nn.Module):
    def __init__(self, config, layer_index, fail=False):
        super().__init__()
        self.config = config
        self.layer_index = layer_index
        self.fail = fail

    def forward(self, hidden_states):
        if self.fail:
            raise RuntimeError("synthetic attention failure")
        batch, length, _ = hidden_states.shape
        attention = torch.full(
            (batch, self.config.num_attention_heads, length, length),
            float(self.layer_index + 1),
        )
        return hidden_states, attention


class _FakeDecoderLayer(nn.Module):
    def __init__(self, config, layer_index, fail=False):
        super().__init__()
        self.self_attn = _FakeSelfAttention(config, layer_index, fail)


class _FakeBackbone(nn.Module):
    def __init__(self, config, fail_layer=None):
        super().__init__()
        self.layers = nn.ModuleList(
            [
                _FakeDecoderLayer(config, layer_index, fail_layer == layer_index)
                for layer_index in range(2)
            ]
        )


class _FakeCausalLM(nn.Module):
    def __init__(self, fail_layer=None):
        super().__init__()
        self.config = SimpleNamespace(
            _attn_implementation="sdpa",
            num_attention_heads=4,
            num_key_value_heads=2,
        )
        self.model = _FakeBackbone(self.config, fail_layer)

    def forward(self, input_ids, use_cache, logits_to_keep):
        batch, length = input_ids.shape
        hidden = torch.zeros((batch, length, 1))
        cache = DynamicCache()
        for layer_index, layer in enumerate(self.model.layers):
            layer.self_attn(hidden)
            keys = torch.full((batch, 2, length, 1), float(layer_index))
            values = 10 * keys
            cache.update(keys, values, layer_index)
        return SimpleNamespace(
            past_key_values=cache,
            logits=torch.arange(5, dtype=torch.float32).view(1, 1, 5),
        )


def test_prefill_with_real_attention_returns_cache_logits_and_bounded_mass():
    model = _FakeCausalLM()
    runtime = SimpleNamespace(model=model, device="cpu")

    cache, logits, mass = prefill_with_real_attention(runtime, [11, 12, 13])

    assert cache.physical_length == 3
    assert logits.tolist() == [0, 1, 2, 3, 4]
    assert mass.shape == (2, 2, 3)
    assert mass[0].tolist() == [[6, 6, 6], [6, 6, 6]]
    assert mass[1].tolist() == [[12, 12, 12], [12, 12, 12]]
    assert model.config._attn_implementation == "sdpa"
    assert all(
        not layer.self_attn._forward_hooks for layer in model.model.layers
    )


def test_prefill_with_real_attention_restores_hooks_and_mode_after_failure():
    model = _FakeCausalLM(fail_layer=1)
    runtime = SimpleNamespace(model=model, device="cpu")

    with pytest.raises(RuntimeError, match="synthetic attention failure"):
        prefill_with_real_attention(runtime, [11, 12, 13])

    assert model.config._attn_implementation == "sdpa"
    assert all(
        not layer.self_attn._forward_hooks for layer in model.model.layers
    )


def test_prefill_with_real_attention_runs_through_real_qwen3(runtime):
    token_ids = runtime.tokenizer.encode(
        "A short attention audit.",
        add_special_tokens=False,
    )
    prior_mode = runtime.model.config._attn_implementation

    cache, logits, mass = prefill_with_real_attention(runtime, token_ids)

    assert cache.physical_length == len(token_ids)
    assert logits.shape == (runtime.model.config.vocab_size,)
    assert torch.isfinite(logits).all()
    assert mass.shape == (
        runtime.model.config.num_hidden_layers,
        runtime.model.config.num_key_value_heads,
        len(token_ids),
    )
    assert torch.isfinite(mass).all()
    assert (mass >= 0).all()
    assert runtime.model.config._attn_implementation == prior_mode
    assert all(
        not layer.self_attn._forward_hooks
        for layer in runtime.model.model.layers
    )


def test_real_qwen3_continuation_accepts_the_attention_merged_cache(runtime):
    seed_ids = runtime.tokenizer.encode(
        "Attention weighted cache merging must support continuation. ",
        add_special_tokens=False,
    )
    token_ids = (seed_ids * 4)[:24]
    continuation_ids = runtime.tokenizer.encode(
        " Continue.",
        add_special_tokens=False,
    )
    cache, _, mass = prefill_with_real_attention(runtime, token_ids)
    plan = build_merge_plan(len(token_ids), 0.5)
    merged = merge_cache(cache, mass, plan).cache

    logits = runtime.forward_extend(merged, continuation_ids)

    assert logits.shape == (
        len(continuation_ids),
        runtime.model.config.vocab_size,
    )
    assert torch.isfinite(logits).all()
    assert merged.physical_length == plan.target_retained + len(
        continuation_ids
    )
    assert merged.next_logical_position == len(token_ids) + len(
        continuation_ids
    )


def test_real_attention_api_is_available_from_compaction_package():
    from memsub.compaction import (
        prefill_with_real_attention as public_prefill,
        reduce_gqa_attention as public_reduce,
    )

    assert public_prefill is prefill_with_real_attention
    assert public_reduce is reduce_gqa_attention
