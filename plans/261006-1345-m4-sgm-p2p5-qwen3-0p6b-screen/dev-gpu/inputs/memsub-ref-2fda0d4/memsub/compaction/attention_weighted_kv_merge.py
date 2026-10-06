"""Attention-weighted KV merging with exact retained-vector budgets.

The port follows KV-Merge's real-benchmark layout: half of the retained
non-sink budget is recent exact KV and half is old-region summaries.  Unlike
the upstream floor-based partition, balanced blocks make the requested house
budget exact at every registered fraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch

from ..runtime import CompactedPrefixCache


@dataclass(frozen=True)
class MergeBlock:
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class MergePlan:
    sequence_length: int
    eviction_fraction: float
    sink_token_count: int
    target_retained: int
    summary_count: int
    recent_count: int
    recent_start: int
    blocks: tuple[MergeBlock, ...]


@dataclass(frozen=True)
class MergeResult:
    cache: CompactedPrefixCache
    plan: MergePlan


@dataclass(frozen=True)
class MergeMechanics:
    block_size: int
    attention_mass_share: float
    block_heterogeneity: float
    distance_to_recent_window: float
    merged: bool


def _require_valid_attention_mass(attention_mass: torch.Tensor) -> None:
    if not bool(torch.isfinite(attention_mass).all()) or bool(
        (attention_mass < 0).any()
    ):
        raise ValueError("attention mass must be finite and nonnegative")


def build_merge_plan(
    sequence_length: int,
    eviction_fraction: float,
    sink_token_count: int = 4,
) -> MergePlan:
    """Build the source-shaped merge layout at an exact house KV budget."""
    if not 0 < eviction_fraction < 1:
        raise ValueError("eviction_fraction must be between 0 and 1")
    if sequence_length <= sink_token_count:
        raise ValueError("sequence_length must exceed the pinned sink prefix")

    target_retained = sequence_length - int(sequence_length * eviction_fraction)
    non_sink_budget = target_retained - sink_token_count
    if non_sink_budget < 2:
        raise ValueError("retained budget must include sinks and summary/recent KV")

    recent_count = non_sink_budget // 2
    summary_count = non_sink_budget - recent_count
    old_count = sequence_length - sink_token_count - recent_count
    if summary_count > old_count:
        raise ValueError("summary budget exceeds the old nonsink region")

    base_size, larger_blocks = divmod(old_count, summary_count)
    blocks: list[MergeBlock] = []
    cursor = sink_token_count
    for block_index in range(summary_count):
        size = base_size + int(block_index < larger_blocks)
        blocks.append(MergeBlock(cursor, cursor + size))
        cursor += size

    recent_start = sequence_length - recent_count
    return MergePlan(
        sequence_length=sequence_length,
        eviction_fraction=eviction_fraction,
        sink_token_count=sink_token_count,
        target_retained=target_retained,
        summary_count=summary_count,
        recent_count=recent_count,
        recent_start=recent_start,
        blocks=tuple(blocks),
    )


def merge_cache(
    cache: CompactedPrefixCache,
    attention_mass: torch.Tensor,
    plan: MergePlan,
) -> MergeResult:
    """Replace each old-region block with its attention-weighted K/V mean."""
    if cache.physical_length != plan.sequence_length:
        raise ValueError("cache length does not match the merge plan")
    if cache.sink_token_count != plan.sink_token_count:
        raise ValueError("cache and merge plan use different sink prefixes")
    if attention_mass.shape[0] != cache.num_layers:
        raise ValueError("attention mass layer count does not match the cache")
    if attention_mass.shape[-1] != plan.sequence_length:
        raise ValueError("attention mass sequence length does not match the plan")
    _require_valid_attention_mass(attention_mass)

    block_lengths = torch.tensor(
        [block.size for block in plan.blocks],
        dtype=torch.long,
        device=attention_mass.device,
    )
    keys_out: list[torch.Tensor] = []
    values_out: list[torch.Tensor] = []
    for layer_index in range(cache.num_layers):
        keys, values = cache.layer_kv(layer_index)
        if keys.shape != values.shape:
            raise ValueError("key and value cache tensors must have matching shapes")
        if keys.shape[0] != 1:
            raise ValueError("KV merging currently supports batch size one")
        if keys.shape[1] != attention_mass.shape[1]:
            raise ValueError("attention mass KV-head count does not match the cache")

        layer_mass = attention_mass[layer_index].to(
            device=keys.device, dtype=torch.float32
        )
        layer_block_lengths = block_lengths.to(keys.device)
        lengths = layer_block_lengths.expand(keys.shape[1], -1)
        old_mass = layer_mass[:, plan.sink_token_count : plan.recent_start]
        block_totals = torch.segment_reduce(
            old_mass, "sum", lengths=lengths, axis=1
        )
        token_totals = torch.repeat_interleave(
            block_totals, layer_block_lengths, dim=1
        )
        uniform_weights = torch.repeat_interleave(
            layer_block_lengths.float().reciprocal(), layer_block_lengths
        )
        weights = torch.where(
            token_totals > 0,
            old_mass / token_totals.clamp_min(1e-12),
            uniform_weights.unsqueeze(0),
        )
        old_keys = keys[0, :, plan.sink_token_count : plan.recent_start].float()
        old_values = values[0, :, plan.sink_token_count : plan.recent_start].float()
        merged_keys = torch.segment_reduce(
            old_keys * weights.unsqueeze(-1), "sum", lengths=lengths, axis=1
        ).unsqueeze(0).to(keys.dtype)
        merged_values = torch.segment_reduce(
            old_values * weights.unsqueeze(-1), "sum", lengths=lengths, axis=1
        ).unsqueeze(0).to(values.dtype)

        keys_out.append(
            torch.cat(
                [
                    keys[:, :, : plan.sink_token_count],
                    merged_keys,
                    keys[:, :, plan.recent_start :],
                ],
                dim=2,
            )
        )
        values_out.append(
            torch.cat(
                [
                    values[:, :, : plan.sink_token_count],
                    merged_values,
                    values[:, :, plan.recent_start :],
                ],
                dim=2,
            )
        )

    logical_positions = [
        *cache.logical_positions[: plan.sink_token_count],
        *(cache.logical_positions[block.end - 1] for block in plan.blocks),
        *cache.logical_positions[plan.recent_start :],
    ]
    merged_cache = CompactedPrefixCache.from_tensors(
        keys_out,
        values_out,
        logical_positions=logical_positions,
        next_logical_position=cache.next_logical_position,
        sink_token_count=cache.sink_token_count,
    )
    return MergeResult(cache=merged_cache, plan=plan)


def mechanics_features(
    plan: MergePlan,
    attention_mass: torch.Tensor,
    needle_positions: Sequence[int],
) -> MergeMechanics:
    """Describe the merge block containing the located needle midpoint."""
    if attention_mass.ndim != 3 or attention_mass.shape[-1] != plan.sequence_length:
        raise ValueError("attention mass must have shape [layers, kv_heads, sequence]")
    _require_valid_attention_mass(attention_mass)
    positions = sorted(set(int(position) for position in needle_positions))
    if not positions:
        raise ValueError("needle_positions must not be empty")
    if positions[0] < 0 or positions[-1] >= plan.sequence_length:
        raise ValueError("needle position lies outside the merge plan")

    midpoint = (positions[0] + positions[-1]) // 2
    if midpoint < plan.sink_token_count or midpoint >= plan.recent_start:
        return MergeMechanics(
            block_size=1,
            attention_mass_share=1.0,
            block_heterogeneity=0.0,
            distance_to_recent_window=0.0,
            merged=False,
        )

    block = next(
        candidate
        for candidate in plan.blocks
        if candidate.start <= midpoint < candidate.end
    )
    mass = attention_mass.float().sum(dim=(0, 1))[block.start : block.end]
    total = mass.sum()
    if float(total) > 0:
        probabilities = mass / total
    else:
        probabilities = torch.full_like(mass, 1.0 / block.size)
    needle_in_block = [
        position - block.start
        for position in positions
        if block.start <= position < block.end
    ]
    share = float(probabilities[needle_in_block].sum()) if needle_in_block else 0.0
    if block.size == 1:
        heterogeneity = 0.0
    else:
        entropy = -(probabilities * probabilities.clamp_min(1e-12).log()).sum()
        heterogeneity = 1.0 - float(entropy / torch.log(
            torch.tensor(float(block.size), device=entropy.device)
        ))
    old_count = plan.recent_start - plan.sink_token_count
    distance = (plan.recent_start - block.end) / old_count
    return MergeMechanics(
        block_size=block.size,
        attention_mass_share=share,
        block_heterogeneity=heterogeneity,
        distance_to_recent_window=distance,
        merged=True,
    )
