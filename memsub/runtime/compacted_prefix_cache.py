"""CompactedPrefixCache — the B.7 tier (a) KV-injection artifact.

HF DynamicCache subclass tracking the logical position of every physical
slot. Core semantics (BUILD.md P1):

  * physical cache length K, logical thread length T, offset = T - K;
  * continuation tokens receive LOGICAL positions for RoPE (position_ids)
    while mask/cache bookkeeping runs on PHYSICAL indices (cache_position) —
    surviving keys keep their original rotations, so relative attention
    geometry is exact (spec 12);
  * sink pages (logical positions 0..3) are always resident: any eviction
    plan touching them raises before the cache is modified (spec 13.2, GT2).

Pure PyTorch; no kernels. The decode loop lives in HFModelRuntime.
"""

from __future__ import annotations

import torch
from transformers.cache_utils import DynamicCache

from ..errors import SinkEvictionError

SINK_TOKEN_COUNT = 4  # k=4, positions 0-3 (spec 13.2; BUILD.md 6)


class CompactedPrefixCache(DynamicCache):
    def __init__(self, sink_token_count: int = SINK_TOKEN_COUNT):
        super().__init__()
        self.sink_token_count = sink_token_count
        # logical position of each physical slot, in physical order
        self.logical_positions: list[int] = []
        self.next_logical_position: int = 0

    # -- construction ---------------------------------------------------------
    @classmethod
    def from_prefill(cls, cache: DynamicCache, prefill_length: int,
                     sink_token_count: int = SINK_TOKEN_COUNT) -> "CompactedPrefixCache":
        """Adopt the K/V tensors of a fresh full prefill (no eviction yet)."""
        out = cls(sink_token_count)
        for layer_idx in range(len(cache.layers)):
            keys, values = cache.layers[layer_idx].keys, cache.layers[layer_idx].values
            out.update(keys, values, layer_idx)
        out.logical_positions = list(range(prefill_length))
        out.next_logical_position = prefill_length
        return out

    @classmethod
    def from_tensors(cls, keys_per_layer: list[torch.Tensor],
                     values_per_layer: list[torch.Tensor],
                     logical_positions: list[int], next_logical_position: int,
                     sink_token_count: int = SINK_TOKEN_COUNT) -> "CompactedPrefixCache":
        """Rebuild from hydrated checkpoint pages (M2)."""
        out = cls(sink_token_count)
        for layer_idx, (k, v) in enumerate(zip(keys_per_layer, values_per_layer)):
            out.update(k, v, layer_idx)
        out.logical_positions = list(logical_positions)
        out.next_logical_position = next_logical_position
        return out

    # -- geometry -------------------------------------------------------------
    @property
    def physical_length(self) -> int:
        return len(self.logical_positions)

    @property
    def logical_offset(self) -> int:
        """Stored offset T - K: evicted-token count in front of the cursor."""
        return self.next_logical_position - self.physical_length

    def note_appended(self, n: int) -> None:
        """Record that n continuation tokens were appended by model.forward."""
        start = self.next_logical_position
        self.logical_positions.extend(range(start, start + n))
        self.next_logical_position = start + n

    def sink_physical_indices(self) -> list[int]:
        return [i for i, p in enumerate(self.logical_positions)
                if p < self.sink_token_count]

    # -- eviction (M1) ----------------------------------------------------------
    def evict_logical_range(self, start: int, end: int) -> int:
        """Evict all resident slots with logical position in [start, end).

        Raises SinkEvictionError BEFORE touching any tensor if the plan would
        evict a pinned sink position (GT2). Returns evicted slot count."""
        if start < self.sink_token_count:
            raise SinkEvictionError(
                f"eviction plan [{start}, {end}) covers pinned sink positions "
                f"0-{self.sink_token_count - 1}")
        keep = [i for i, p in enumerate(self.logical_positions)
                if not (start <= p < end)]
        evicted = self.physical_length - len(keep)
        if evicted == 0:
            return 0
        device = self.layers[0].keys.device
        keep_idx = torch.tensor(keep, dtype=torch.long, device=device)
        for layer in self.layers:
            layer.keys = layer.keys.index_select(2, keep_idx)
            layer.values = layer.values.index_select(2, keep_idx)
        self.logical_positions = [self.logical_positions[i] for i in keep]
        return evicted

    def evict_logical_positions(self, positions: list[int]) -> int:
        """Evict an arbitrary (non-contiguous) set of logical positions.
        Same sink guarantee as evict_logical_range: raises before any tensor
        is touched if a pinned sink position is in the plan."""
        targets = set(positions)
        sinks = [p for p in targets if p < self.sink_token_count]
        if sinks:
            raise SinkEvictionError(
                f"eviction plan contains pinned sink positions {sorted(sinks)}")
        keep = [i for i, p in enumerate(self.logical_positions)
                if p not in targets]
        evicted = self.physical_length - len(keep)
        if evicted == 0:
            return 0
        device = self.layers[0].keys.device
        keep_idx = torch.tensor(keep, dtype=torch.long, device=device)
        for layer in self.layers:
            layer.keys = layer.keys.index_select(2, keep_idx)
            layer.values = layer.values.index_select(2, keep_idx)
        self.logical_positions = [self.logical_positions[i] for i in keep]
        return evicted

    # -- serialization support (M2) ---------------------------------------------
    def layer_kv(self, layer_idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        layer = self.layers[layer_idx]
        return layer.keys, layer.values

    @property
    def num_layers(self) -> int:
        return len(self.layers)

    def clone_detached(self) -> "CompactedPrefixCache":
        out = CompactedPrefixCache(self.sink_token_count)
        for i in range(self.num_layers):
            k, v = self.layer_kv(i)
            out.update(k.detach().clone(), v.detach().clone(), i)
        out.logical_positions = list(self.logical_positions)
        out.next_logical_position = self.next_logical_position
        return out
