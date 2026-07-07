"""Full-stack amortized KV compactor: one Perceiver per transformer layer
(36 for Qwen3-4B), operating on a CompactedPrefixCache.

compact(): keeps pinned sinks raw, un-rotates the non-sink keys at their
logical positions (base-model RoPE), runs each layer's compactor, re-rotates
compact keys at evenly spaced output positions, and returns a new
CompactedPrefixCache whose logical positions are those output positions —
physical length sinks + t, logical cursor unchanged. Differentiable end to
end (training backprops through the returned cache into the latents).

The policy version binds the weights hash and max_certified_depth
(spec §4.6/§13.4): a retrained compactor is a new compaction policy.
"""

from __future__ import annotations

import json

import torch
import torch.nn as nn

from ..errors import CompatibilityError
from ..hashing import sha256_bytes
from ..runtime import CompactedPrefixCache
from .rope_rotation_helpers import apply_rotation, model_rope_cos_sin, unrotate
from .still_perceiver_layer_compactor import StillPerceiverLayerCompactor


class StillAmortizedKVCompactor(nn.Module):
    def __init__(self, config, t_latents: int):
        super().__init__()
        self.config = config
        self.t = t_latents
        self.layers = nn.ModuleList(
            StillPerceiverLayerCompactor(
                n_kv_heads=int(config.num_key_value_heads),
                head_dim=int(config.head_dim),
                t_latents=t_latents)
            for _ in range(int(config.num_hidden_layers)))
        self.max_certified_depth: int = 0   # set by certification (GT15)

    # -- policy identity -------------------------------------------------------
    def weights_hash(self) -> str:
        blobs = [p.detach().cpu().float().numpy().tobytes()
                 for p in self.parameters()]
        return sha256_bytes(b"".join(blobs))

    def policy_version(self) -> str:
        return (f"still-compact-v1:t{self.t}:depth{self.max_certified_depth}:"
                f"{self.weights_hash()[:23]}")

    # -- core operation --------------------------------------------------------
    def compact(self, cache: CompactedPrefixCache,
                t_out: int | None = None) -> CompactedPrefixCache:
        """Compress the non-sink resident prefix into t latents per layer."""
        t_out = t_out or self.t
        if t_out != self.t:
            raise ValueError("latent count is fixed by the trained bank")
        sink_n = len(cache.sink_physical_indices())
        positions = torch.tensor(cache.logical_positions[sink_n:])
        if len(positions) < 1:
            raise ValueError("nothing to compact")
        region_lo = int(positions[0])
        region_hi = int(positions[-1]) + 1
        # latent output positions: evenly spaced over the compacted range
        out_pos = torch.linspace(region_lo, region_hi - 1, self.t).round().long()

        dev = cache.layer_kv(0)[0].device
        cache_dt = cache.layer_kv(0)[0].dtype
        work_dt = next(self.parameters()).dtype  # fp32 during training
        cos_in, sin_in = model_rope_cos_sin(self.config, positions, work_dt, dev)
        cos_out, sin_out = model_rope_cos_sin(self.config, out_pos, work_dt, dev)

        keys_out, values_out = [], []
        for idx, layer in enumerate(self.layers):
            k, v = cache.layer_kv(idx)
            k_sink, v_sink = k[:, :, :sink_n], v[:, :, :sink_n]
            k_unrot = unrotate(k[:, :, sink_n:].to(work_dt), cos_in, sin_in)
            c_k_unrot, c_v = layer(k_unrot, v[:, :, sink_n:].to(work_dt),
                                   positions.to(dev), out_pos.to(dev))
            c_k = apply_rotation(c_k_unrot, cos_out, sin_out)
            keys_out.append(torch.cat([k_sink, c_k.to(cache_dt)], dim=2))
            values_out.append(torch.cat([v_sink, c_v.to(cache_dt)], dim=2))

        out = CompactedPrefixCache.from_tensors(
            keys_out, values_out,
            logical_positions=list(cache.logical_positions[:sink_n])
            + [int(p) for p in out_pos],
            next_logical_position=cache.next_logical_position,
            sink_token_count=cache.sink_token_count)
        return out

    # -- persistence -----------------------------------------------------------
    def save(self, path: str) -> None:
        from safetensors.torch import save_file
        meta = {"t": str(self.t),
                "max_certified_depth": str(self.max_certified_depth),
                "config": json.dumps({
                    "num_hidden_layers": int(self.config.num_hidden_layers),
                    "num_key_value_heads": int(self.config.num_key_value_heads),
                    "head_dim": int(self.config.head_dim),
                    "rope_theta": float(self.config.rope_theta)})}
        save_file(dict(self.state_dict()), path, metadata=meta)

    @classmethod
    def load(cls, path: str, config, device: str = "cpu",
             expected_hash_prefix: str | None = None) -> "StillAmortizedKVCompactor":
        from safetensors import safe_open
        from safetensors.torch import load_file
        with safe_open(path, framework="pt") as f:
            meta = f.metadata()
        model = cls(config, t_latents=int(meta["t"]))
        model.load_state_dict(load_file(path))
        model.max_certified_depth = int(meta.get("max_certified_depth", 0))
        if expected_hash_prefix and \
                not model.weights_hash().startswith(expected_hash_prefix):
            raise CompatibilityError("compactor weights hash mismatch")
        return model.to(device)


def slice_cache(cache: CompactedPrefixCache, lo: int, hi: int,
                ) -> CompactedPrefixCache:
    """Physical slice [lo, hi) keeping the slots' logical positions."""
    keys, vals = [], []
    for i in range(cache.num_layers):
        k, v = cache.layer_kv(i)
        keys.append(k[:, :, lo:hi])
        vals.append(v[:, :, lo:hi])
    return CompactedPrefixCache.from_tensors(
        keys, vals, logical_positions=list(cache.logical_positions[lo:hi]),
        next_logical_position=int(cache.logical_positions[hi - 1]) + 1,
        sink_token_count=cache.sink_token_count)


def concat_caches(a: CompactedPrefixCache, b: CompactedPrefixCache,
                  next_logical_position: int) -> CompactedPrefixCache:
    keys, vals = [], []
    for i in range(a.num_layers):
        ka, va = a.layer_kv(i)
        kb, vb = b.layer_kv(i)
        keys.append(torch.cat([ka, kb], dim=2))
        vals.append(torch.cat([va, vb], dim=2))
    return CompactedPrefixCache.from_tensors(
        keys, vals,
        logical_positions=list(a.logical_positions) + list(b.logical_positions),
        next_logical_position=next_logical_position,
        sink_token_count=a.sink_token_count)


def compact_prefix_keep_recent(compactor: StillAmortizedKVCompactor,
                               cache: CompactedPrefixCache,
                               recent_raw: int, depth: int = 1,
                               ) -> CompactedPrefixCache:
    """Deployment-shaped compaction (spec 4.5): compress the old prefix
    (optionally under a recurrence of `depth` equal segments), keep the most
    recent `recent_raw` slots exact."""
    total = cache.physical_length
    old_hi = total - recent_raw
    if depth <= 1:
        state = compactor.compact(slice_cache(cache, 0, old_hi))
    else:
        seg = (old_hi - 4) // depth
        state = None
        for i in range(depth):
            lo = 0 if i == 0 else 4 + i * seg
            hi = old_hi if i == depth - 1 else 4 + (i + 1) * seg
            chunk = slice_cache(cache, lo, hi)
            state = compactor.compact(
                chunk if state is None else
                concat_caches(state, chunk, int(cache.logical_positions[hi - 1]) + 1))
    tail = slice_cache(cache, old_hi, total)
    return concat_caches(state, tail, cache.next_logical_position)


def assert_depth_allowed(compactor: StillAmortizedKVCompactor,
                         requested_depth: int) -> None:
    """Resume paths must refuse to stack compactions beyond the certified
    recurrence depth (spec §13.4; GT15) — fall back to the substrate."""
    if requested_depth > compactor.max_certified_depth:
        raise CompatibilityError(
            f"recurrence depth {requested_depth} exceeds max_certified_depth "
            f"{compactor.max_certified_depth} — fall back to substrate")
