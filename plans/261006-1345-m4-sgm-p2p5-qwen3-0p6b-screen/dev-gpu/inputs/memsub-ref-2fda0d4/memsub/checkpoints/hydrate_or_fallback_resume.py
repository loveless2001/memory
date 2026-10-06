"""Hydrate-or-fallback resume (M2; spec 7.4).

Fast path: fingerprint-checked KV hydration. Any CompatibilityError,
RedactionError, HydrationError or IntegrityError takes the fallback path:
re-prefill from the substrate (summaries + recent exact text, or the full
raw transcript). The fallback never touches KV blobs (GT3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from ..archive import RawArchive
from ..errors import CompatibilityError, HydrationError, IntegrityError, RedactionError
from ..runtime import CompactedPrefixCache, HFModelRuntime
from ..schemas import MemoryBlock
from ..store import BlobStore, SqliteIndex
from .safetensors_delta_checkpoint_store import SafetensorsDeltaCheckpointStore


@dataclass
class ResumeOutcome:
    path_taken: str                  # "hydrate" | "fallback_summary" | "fallback_full"
    cache: CompactedPrefixCache
    reason: Optional[str] = None
    prefill_token_count: int = 0


class HydrateOrFallbackResumer:
    def __init__(self, index: SqliteIndex, blobs: BlobStore, archive: RawArchive,
                 checkpoint_store: SafetensorsDeltaCheckpointStore,
                 runtime: HFModelRuntime):
        self.index = index
        self.blobs = blobs
        self.archive = archive
        self.checkpoints = checkpoint_store
        self.runtime = runtime

    def resume(self, thread_id: str, checkpoint_id: Optional[str] = None) -> ResumeOutcome:
        row = (self.index.get_checkpoint_row(checkpoint_id) if checkpoint_id
               else self.index.latest_checkpoint(thread_id))
        if row is not None:
            try:
                cache = self.checkpoints.hydrate(
                    row["checkpoint_id"], self.runtime.fingerprint(),
                    device=self.runtime.device)
                return ResumeOutcome(path_taken="hydrate", cache=cache)
            except (CompatibilityError, RedactionError, HydrationError, IntegrityError) as exc:
                fallback = self._fallback(thread_id)
                fallback.reason = f"{type(exc).__name__}: {exc}"
                return fallback
        return self._fallback(thread_id)

    def _live_blocks(self, thread_id: str) -> list[MemoryBlock]:
        return [MemoryBlock.from_dict(json.loads(r["body_json"]))
                for r in self.index.blocks_for_thread(thread_id)]

    def _fallback(self, thread_id: str) -> ResumeOutcome:
        """L1 summary prefill when blocks exist; L0 full re-prefill otherwise
        (spec 7.4 fallback path). Reads fail closed on redaction upstream."""
        blocks = self._live_blocks(thread_id)
        if blocks:
            parts = ["[COMPRESSED_MEMORY]"]
            covered: list[tuple[int, int]] = []
            for b in sorted(blocks, key=lambda b: b.positioning.logical_position_start):
                parts.append(self.blobs.get_text(b.primary.storage_uri))
                covered.append((b.source.token_start, b.source.token_end))
            parts.append("[/COMPRESSED_MEMORY]")
            # recent exact text = archived spans not covered by any block
            for row in self.archive.spans_for_thread(thread_id):
                if row["redacted"]:
                    continue
                if not any(s <= row["token_start"] and row["token_end"] <= e
                           for s, e in covered):
                    parts.append(self.archive.get_span_text(row["span_id"]))
            text = "\n".join(parts)
            path = "fallback_summary"
        else:
            # L0 re-prefill from surviving raw spans. Redacted spans are
            # excluded, not read: the thread resumes without their content
            # (reading them would fail closed, and must — GT5).
            text = "".join(
                self.archive.get_span_text(row["span_id"])
                for row in self.archive.spans_for_thread(thread_id)
                if not row["redacted"])
            path = "fallback_full"
        token_ids = self.runtime.tokenizer.encode(text, add_special_tokens=False)
        cache, _ = self.runtime.prefill(token_ids)
        return ResumeOutcome(path_taken=path, cache=cache,
                             prefill_token_count=len(token_ids))
