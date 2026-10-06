"""SubstrateFacade — wires store, archive, compilers, compaction, checkpoints
and resume into one object so the CLI and example smokes stay thin.

Lifecycle (spec 7.1-7.4): append turns -> segment -> archive -> prefill ->
compact under pressure -> checkpoint -> resume (hydrate-or-fallback).
"""

from __future__ import annotations

import json
from pathlib import Path

from .archive import RawArchive, segment_turns
from .checkpoints import HydrateOrFallbackResumer, SafetensorsDeltaCheckpointStore
from .compaction import SinkPinnedSpanCompactor
from .compilers import EmbeddingShadowIndexer
from .ids import new_thread_id
from .redaction_graph_invalidator import RedactionGraphInvalidator
from .runtime import CompactedPrefixCache, HFModelRuntime
from .schemas import MemoryBlock
from .selection import NaiveTopKSelector, RuntimeGatedExpander
from .store import BlobStore, SqliteIndex


class SubstrateFacade:
    def __init__(self, root: str | Path, runtime: HFModelRuntime,
                 summarizer, embedder, max_span_tokens: int = 2048):
        root = Path(root)
        self.index = SqliteIndex(root / "index.sqlite3")
        self.blobs = BlobStore(root)
        self.archive = RawArchive(self.index, self.blobs)
        self.runtime = runtime
        self.max_span_tokens = max_span_tokens
        self.shadow_indexer = EmbeddingShadowIndexer(embedder, self.blobs)
        self.compactor = SinkPinnedSpanCompactor(
            self.index, self.blobs, self.archive, summarizer, self.shadow_indexer)
        self.checkpoints = SafetensorsDeltaCheckpointStore(self.index, self.blobs)
        self.resumer = HydrateOrFallbackResumer(
            self.index, self.blobs, self.archive, self.checkpoints, runtime)
        self.selector = NaiveTopKSelector(embedder, self.blobs)
        self.expander = RuntimeGatedExpander(self.index, self.archive, self.selector)
        self.redactor = RedactionGraphInvalidator(self.index)

    # -- thread lifecycle ---------------------------------------------------------
    def new_thread(self) -> str:
        thread_id = new_thread_id()
        self.index.create_thread(thread_id)
        return thread_id

    def append_turns(self, thread_id: str, turns: list[dict]) -> list:
        """Segment (turn boundary + token cap) and archive new turns."""
        base = int(self.index.get_thread(thread_id)["next_logical_position"])
        segments = segment_turns(turns, tokenizer=self.runtime.tokenizer,
                                 base_position=base, max_tokens=self.max_span_tokens)
        spans = []
        for seg in segments:
            spans.append(self.archive.archive_span(
                thread_id, token_start=seg.token_start, token_end=seg.token_end,
                role=seg.role, text=seg.text, token_ids=seg.token_ids))
        if segments:
            self.index.set_next_logical_position(thread_id, segments[-1].token_end)
        return spans

    def prefill_thread(self, thread_id: str) -> CompactedPrefixCache:
        cache, _ = self.runtime.prefill(self.archive.full_token_ids(thread_id))
        return cache

    def blocks(self, thread_id: str) -> list[MemoryBlock]:
        return [MemoryBlock.from_dict(json.loads(r["body_json"]))
                for r in self.index.blocks_for_thread(thread_id)]

    def compact_under_pressure(self, thread_id: str, cache: CompactedPrefixCache,
                               target_evict_tokens: int) -> list:
        """Compact oldest non-sink spans until the target is covered."""
        results = []
        for row in self.compactor.plan_oldest_nonsink_spans(
                thread_id, cache, target_evict_tokens):
            results.append(self.compactor.compact_span(thread_id, cache, row))
        return results

    def checkpoint(self, thread_id: str, cache: CompactedPrefixCache,
                   fidelity=None):
        parent = self.index.latest_checkpoint(thread_id)
        return self.checkpoints.write_checkpoint(
            thread_id, cache, self.runtime.fingerprint(),
            [b.block_id for b in self.blocks(thread_id)],
            parent_checkpoint_id=parent["checkpoint_id"] if parent else None,
            fidelity=fidelity,
            surviving_token_ids=self.archive.full_token_ids(thread_id)[
                :cache.next_logical_position])

    def resume(self, thread_id: str, checkpoint_id: str | None = None):
        return self.resumer.resume(thread_id, checkpoint_id)

    def expand(self, thread_id: str, query: str, k: int = 1):
        return self.expander.maybe_expand(query, self.blocks(thread_id), k=k)

    def redact(self, span_id: str):
        return self.redactor.redact_span(span_id)
