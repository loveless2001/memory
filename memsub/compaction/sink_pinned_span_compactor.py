"""Compaction event (spec 7.3): convert a span into a durable MemoryBlock,
evict its KV from the live cache, record cheap online risk metadata.

Policy: untrained eviction, oldest-non-sink-first ("evict-oldest-nonsink-v1",
fingerprint compaction_policy_version). Sinks (logical 0-3) are asserted
against BEFORE the cache is touched (spec 13.2, GT2).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..archive import RawArchive
from ..compilers.base_model_summarizer import Summarizer
from ..compilers.embedding_shadow_indexer import EmbeddingShadowIndexer
from ..errors import SinkEvictionError
from ..hashing import sha256_text
from ..ids import new_block_id
from ..runtime import CompactedPrefixCache
from ..schemas import MemoryBlock, Positioning, Quality, Representation, Source
from ..schemas.thread_checkpoint import FidelityMetadata
from ..store import BlobStore, SqliteIndex


@dataclass
class CompactionResult:
    block: MemoryBlock
    evicted_slots: int
    fidelity: FidelityMetadata


class SinkPinnedSpanCompactor:
    def __init__(self, index: SqliteIndex, blobs: BlobStore, archive: RawArchive,
                 summarizer: Summarizer, shadow_indexer: EmbeddingShadowIndexer):
        self.index = index
        self.blobs = blobs
        self.archive = archive
        self.summarizer = summarizer
        self.shadow_indexer = shadow_indexer

    def compact_span(self, thread_id: str, cache: CompactedPrefixCache,
                     span_row, *, semantic_kind: str = "conversation_span",
                     derived_from_extra: list[str] | None = None,
                     offline_certification_id: str | None = None) -> CompactionResult:
        """Compact one archived span: summarize -> MemoryBlock (+shadow) ->
        evict KV -> online risk estimate (spec 7.3 pseudo-flow)."""
        start, end = span_row["token_start"], span_row["token_end"]
        # Sink assertion happens in the compactor path (BUILD.md P4) and again
        # inside the cache; both raise before any tensor is modified.
        if start < cache.sink_token_count:
            raise SinkEvictionError(
                f"span [{start}, {end}) overlaps pinned sinks 0-{cache.sink_token_count - 1}")

        span_text = self.archive.get_span_text(span_row["span_id"])  # fails closed
        summary = self.summarizer.summarize(span_text)
        summary_uri = self.blobs.put_text(summary)

        shadow = self.shadow_indexer.build_shadow(
            summary, created_from="summary_text",
            source_hash=span_row["content_hash"],
            redaction_generation=span_row["redaction_generation"])

        total_before = cache.physical_length
        evicted = cache.evict_logical_range(start, end)
        loss_estimate = evicted / max(total_before, 1)

        block = MemoryBlock(
            block_id=new_block_id(),
            thread_id=thread_id,
            semantic_kind=semantic_kind,
            channel="COMPRESSED_MEMORY",
            derived_from=[span_row["span_id"], *(derived_from_extra or [])],
            supersedes=[],
            source=Source(
                type="conversation_span",
                uri=span_row["text_uri"],
                token_start=start,
                token_end=end,
                hash=span_row["content_hash"],
                redaction_generation=span_row["redaction_generation"],
            ),
            representations=[Representation(
                role="primary", format="summary_text", dtype="text",
                storage_uri=summary_uri, checksum=sha256_text(summary),
                compatibility_fingerprint=None,
                created_from_representation="raw_text_pointer",
            )],
            embedding_shadow=shadow,
            positioning=Positioning(
                logical_position_start=start,
                logical_position_end=end,
                rope_base_offset=start,
                position_scheme="absolute",
            ),
            quality=Quality(loss_estimate=round(loss_estimate, 4), consolidation_depth=1),
        )

        self.index.insert_block(block.block_id, thread_id, block.to_dict())
        for parent in block.derived_from:
            self.index.add_edge(block.block_id, parent, "derived_from")

        # Online risk report: cheap metadata only — never a synchronous
        # full-context KL (spec 13.4). Probes run in the offline harness.
        fidelity = FidelityMetadata(
            offline_certification_id=offline_certification_id,
            online_risk_estimate=round(loss_estimate, 4),
            sampled_probe_count=0,
            lost_fact_risk_estimate=0.0,
        )
        return CompactionResult(block=block, evicted_slots=evicted, fidelity=fidelity)

    def plan_oldest_nonsink_spans(self, thread_id: str, cache: CompactedPrefixCache,
                                  target_evict_tokens: int) -> list:
        """Eviction plan: oldest archived spans first, never sinks, stop once
        the target is covered. Returns span rows to compact."""
        plan, covered = [], 0
        for row in self.archive.spans_for_thread(thread_id):
            if row["redacted"]:
                continue
            if row["token_start"] < cache.sink_token_count:
                continue  # sink-covering span is never planned
            if row["token_end"] > cache.next_logical_position:
                break
            plan.append(row)
            covered += row["token_end"] - row["token_start"]
            if covered >= target_evict_tokens:
                break
        return plan
