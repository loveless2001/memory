"""Capture real accumulated attention mass without retaining attention maps."""

from __future__ import annotations

import torch

from ..runtime import CompactedPrefixCache


def reduce_gqa_attention(
    attention: torch.Tensor,
    num_key_value_heads: int,
) -> torch.Tensor:
    """Sum received attention over causal queries and each GQA head group."""
    if attention.ndim != 4:
        raise ValueError("attention map must have four dimensions [B, H, Q, K]")
    batch, query_heads, query_length, key_length = attention.shape
    if num_key_value_heads <= 0:
        raise ValueError("num_key_value_heads must be positive")
    if query_heads % num_key_value_heads:
        raise ValueError("query head count must be divisible by KV head count")
    groups = query_heads // num_key_value_heads
    grouped = attention.reshape(
        batch,
        num_key_value_heads,
        groups,
        query_length,
        key_length,
    )
    return grouped.sum(dim=(2, 3), dtype=torch.float32)


@torch.inference_mode()
def prefill_with_real_attention(
    runtime,
    token_ids: list[int],
) -> tuple[CompactedPrefixCache, torch.Tensor, torch.Tensor]:
    """Prefill once while reducing each layer's eager map inside its hook."""
    model = runtime.model
    layers = list(model.model.layers)
    captured: list[torch.Tensor | None] = [None] * len(layers)
    prior_model_mode = model.config._attn_implementation
    prior_layer_modes = [
        layer.self_attn.config._attn_implementation for layer in layers
    ]
    handles = []

    def make_hook(layer_index: int):
        def collect(_module, _args, output):
            attention = output[1]
            if attention is None:
                raise RuntimeError("eager attention hook received no attention weights")
            reduced = reduce_gqa_attention(
                attention,
                num_key_value_heads=model.config.num_key_value_heads,
            )
            if reduced.shape[0] != 1:
                raise ValueError("real-attention prefill supports batch size one")
            captured[layer_index] = reduced[0].detach().cpu()
            return output[0], None

        return collect

    try:
        model.config._attn_implementation = "eager"
        for layer, hook in zip(layers, map(make_hook, range(len(layers)))):
            layer.self_attn.config._attn_implementation = "eager"
            handles.append(layer.self_attn.register_forward_hook(hook))
        input_ids = torch.tensor(
            [token_ids], dtype=torch.long, device=runtime.device
        )
        output = model(input_ids=input_ids, use_cache=True, logits_to_keep=1)
        if any(mass is None for mass in captured):
            missing = [i for i, mass in enumerate(captured) if mass is None]
            raise RuntimeError(f"attention hooks did not run for layers {missing}")
        cache = CompactedPrefixCache.from_prefill(
            output.past_key_values, len(token_ids)
        )
        mass = torch.stack([value for value in captured if value is not None])
        return cache, output.logits[0, -1].float(), mass
    finally:
        for handle in handles:
            handle.remove()
        model.config._attn_implementation = prior_model_mode
        for layer, prior_mode in zip(layers, prior_layer_modes):
            layer.self_attn.config._attn_implementation = prior_mode
