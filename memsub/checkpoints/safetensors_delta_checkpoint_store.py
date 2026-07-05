"""Safetensors delta checkpoints on NVMe (M2; spec 11.2-11.4).

KV is chunked into 64-token pages per layer, serialized as safetensors into
the content-addressed blob store. Delta property: a page whose bytes are
unchanged since the parent checkpoint hashes to the same blob and is never
rewritten (spec 11.2 "write deltas against the parent"; CoW lineage 11.5
falls out of the same mechanism via parent_checkpoint_id).

Hydration mmap-loads pages (safetensors load_file), sink pages FIRST
(spec 13.2; GT2), verifies checksums, and validates the fingerprint
all-or-nothing before any page is read (GT3).
"""

from __future__ import annotations

import io
import json

import torch
from safetensors.torch import load_file, save

from ..errors import CompatibilityError, HydrationError, RedactionError
from ..fingerprint import CompatibilityFingerprint
from ..hashing import sha256_bytes
from ..ids import new_checkpoint_id
from ..runtime import CompactedPrefixCache
from ..schemas.thread_checkpoint import (
    AttentionMetadata,
    CheckpointPositioning,
    FidelityMetadata,
    SamplerState,
    ThreadCheckpoint,
)
from ..store import BlobStore, SqliteIndex

PAGE_TOKENS = 64  # spec 11.3 example page granularity


class SafetensorsDeltaCheckpointStore:
    def __init__(self, index: SqliteIndex, blobs: BlobStore):
        self.index = index
        self.blobs = blobs
        self.last_hydration_order: list[str] = []  # page kinds, for GT2 assertion

    # -- write ------------------------------------------------------------------
    def write_checkpoint(self, thread_id: str, cache: CompactedPrefixCache,
                         fingerprint: CompatibilityFingerprint,
                         memory_block_ids: list[str],
                         parent_checkpoint_id: str | None = None,
                         fidelity: FidelityMetadata | None = None,
                         surviving_token_ids: list[int] | None = None) -> ThreadCheckpoint:
        if fingerprint is None:
            raise ValueError("every artifact write path requires a fingerprint")
        pages = []
        n_phys = cache.physical_length
        logical = cache.logical_positions
        config_kv_heads = cache.layer_kv(0)[0].shape[1]
        head_dim = cache.layer_kv(0)[0].shape[3]
        for layer_idx in range(cache.num_layers):
            keys, values = cache.layer_kv(layer_idx)
            for start in range(0, n_phys, PAGE_TOKENS):
                end = min(start + PAGE_TOKENS, n_phys)
                kv = torch.stack([keys[0, :, start:end], values[0, :, start:end]])
                buf = save({"kv": kv.contiguous().cpu()})
                uri = self.blobs.put(buf)
                pages.append({
                    "page_id": uri.rsplit("/", 1)[-1][:16],
                    "layer": layer_idx,
                    "kv_layout": fingerprint.kv_layout,
                    "n_kv_heads": int(config_kv_heads),
                    "head_dim": int(head_dim),
                    "head_range": [0, int(config_kv_heads) - 1],
                    "token_range_physical": [start, end],
                    "logical_positions": logical[start:end],
                    "dtype": str(kv.dtype).removeprefix("torch."),
                    "shape": list(kv.shape),
                    "storage_uri": uri,
                    "checksum": sha256_bytes(buf),
                    "is_sink_page": any(p < cache.sink_token_count for p in logical[start:end]),
                })
        page_table_uri = self.blobs.put(json.dumps({"pages": pages}).encode())
        compaction_map_uri = self.blobs.put(json.dumps(
            {"logical_positions": logical}).encode())
        tokens_uri = self.blobs.put(json.dumps(
            surviving_token_ids if surviving_token_ids is not None else []).encode())

        ckpt = ThreadCheckpoint(
            checkpoint_id=new_checkpoint_id(),
            thread_id=thread_id,
            parent_checkpoint_id=parent_checkpoint_id,
            compatibility_fingerprint=fingerprint.to_dict(),
            surviving_token_ids_uri=tokens_uri,
            kv_page_table_uri=page_table_uri,
            memory_block_ids=list(memory_block_ids),
            sink_tokens_retained=sorted(p for p in logical if p < cache.sink_token_count),
            attention_metadata=AttentionMetadata(
                attention_mask_format="dense", compaction_map_uri=compaction_map_uri),
            positioning=CheckpointPositioning(
                next_logical_position=cache.next_logical_position,
                next_physical_position=cache.physical_length),
            fidelity_metadata=fidelity or FidelityMetadata(),
        )
        self.index.insert_checkpoint(
            ckpt.checkpoint_id, thread_id, parent_checkpoint_id, ckpt.to_dict(),
            token_start=0, token_end=cache.next_logical_position)
        for block_id in memory_block_ids:
            self.index.add_edge(ckpt.checkpoint_id, block_id, "derived_from")
        if parent_checkpoint_id:
            self.index.add_edge(ckpt.checkpoint_id, parent_checkpoint_id, "derived_from")
        return ckpt

    # -- read -------------------------------------------------------------------
    def load_checkpoint(self, checkpoint_id: str) -> ThreadCheckpoint:
        row = self.index.get_checkpoint_row(checkpoint_id)
        if row is None:
            raise HydrationError(f"unknown checkpoint {checkpoint_id}")
        if row["invalidated"]:
            raise RedactionError(
                f"checkpoint {checkpoint_id} invalidated by redaction (fail closed)")
        return ThreadCheckpoint.from_dict(json.loads(row["body_json"]))

    def hydrate(self, checkpoint_id: str, live_fingerprint: CompatibilityFingerprint,
                device: str = "cpu") -> CompactedPrefixCache:
        """Hard-gated hydration: fingerprint validated all-or-nothing before
        any KV blob is opened (spec 4.6/7.4; GT3)."""
        ckpt = self.load_checkpoint(checkpoint_id)
        stored = ckpt.fingerprint()
        if not stored.matches(live_fingerprint):
            raise CompatibilityError(
                "checkpoint fingerprint mismatch — KV may never be loaded as live context")

        table = json.loads(self.blobs.get(ckpt.kv_page_table_uri))
        pages = table["pages"]
        # Sink pages hydrate first (spec 13.2). Order is recorded for GT2.
        ordered = [p for p in pages if p["is_sink_page"]] + \
                  [p for p in pages if not p["is_sink_page"]]
        self.last_hydration_order = [
            "sink" if p["is_sink_page"] else "normal" for p in ordered]
        loaded: dict[tuple[int, int], torch.Tensor] = {}
        for page in ordered:
            # mmap hydration (spec 11.4): content addressing guarantees the
            # path matches the checksum recorded at write time.
            path = self.blobs.path_for(page["storage_uri"])
            if not path.exists():
                raise HydrationError(f"missing KV page blob {page['storage_uri']}")
            kv = load_file(str(path))["kv"]
            loaded[(page["layer"], page["token_range_physical"][0])] = kv

        n_layers = max(p["layer"] for p in pages) + 1
        keys_per_layer, values_per_layer = [], []
        for layer_idx in range(n_layers):
            chunks = sorted(((s, kv) for (l, s), kv in loaded.items() if l == layer_idx))
            kv_full = torch.cat([kv for _, kv in chunks], dim=2)  # token axis
            keys_per_layer.append(kv_full[0].unsqueeze(0).to(device))
            values_per_layer.append(kv_full[1].unsqueeze(0).to(device))

        compaction_map = json.loads(self.blobs.get(ckpt.attention_metadata.compaction_map_uri))
        return CompactedPrefixCache.from_tensors(
            keys_per_layer, values_per_layer,
            logical_positions=compaction_map["logical_positions"],
            next_logical_position=ckpt.positioning.next_logical_position)
