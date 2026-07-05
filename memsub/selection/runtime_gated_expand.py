"""Runtime-gated EXPAND (M0; spec 7.2 mode A, 4.7).

The runtime (not the model) decides when compressed memory is insufficient
and injects the exact raw span through the RETRIEVED_EXACT channel. The gate
here is a similarity threshold over the naive selector — the calibrated
dual-encoder gate is M3 and out of scope (BUILD.md 7).

Reads fail closed on redaction (GT5): expansion goes through RawArchive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..archive import RawArchive
from ..errors import RedactionError
from ..schemas import MemoryBlock
from ..store import SqliteIndex
from .naive_topk_selector import NaiveTopKSelector


@dataclass
class ExpandResult:
    block_id: str
    span_id: str
    channel: str            # always RETRIEVED_EXACT
    injection_text: str
    score: float


class RuntimeGatedExpander:
    def __init__(self, index: SqliteIndex, archive: RawArchive,
                 selector: NaiveTopKSelector, threshold: float = 0.30):
        self.index = index
        self.archive = archive
        self.selector = selector
        self.threshold = threshold

    def expand_block(self, block: MemoryBlock, score: float = 1.0) -> ExpandResult:
        """EXPAND(block_id): fetch the exact raw source span for a block.
        Raises RedactionError if the block or its source span is redacted."""
        row = self.index.get_block_row(block.block_id)
        if row is None or row["invalidated"]:
            raise RedactionError(f"block {block.block_id} is invalidated (fail closed)")
        span_rows = self.archive.spans_overlapping(
            block.thread_id, block.source.token_start, block.source.token_end)
        texts = [self.archive.get_span_text(r["span_id"]) for r in span_rows]  # fails closed
        raw = "".join(texts)
        injection = (f"[RETRIEVED_EXACT block={block.block_id} "
                     f"tokens={block.source.token_start}-{block.source.token_end}]\n"
                     f"{raw}\n[/RETRIEVED_EXACT]")
        span_id = span_rows[0]["span_id"] if span_rows else ""
        return ExpandResult(block.block_id, span_id, "RETRIEVED_EXACT", injection, score)

    def maybe_expand(self, query: str, blocks: list[MemoryBlock],
                     k: int = 1) -> Optional[list[ExpandResult]]:
        """Mode A gate: expand top-k blocks whose selector score clears the
        threshold; None when compressed memory is judged sufficient."""
        ranked = self.selector.rank(query, blocks, k=k)
        hits = [s for s in ranked if s.score >= self.threshold]
        if not hits:
            return None
        by_id = {b.block_id: b for b in blocks}
        return [self.expand_block(by_id[s.block_id], s.score) for s in hits]
