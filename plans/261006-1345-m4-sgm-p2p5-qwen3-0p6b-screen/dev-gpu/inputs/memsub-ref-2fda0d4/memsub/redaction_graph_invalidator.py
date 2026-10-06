"""Redaction traces the provenance graph (M0; spec 19.x, GT5).

Redacting a source span must invalidate every derived artifact reachable via
derived_from edges — summaries/shadows (inside blocks), consolidated blocks,
and checkpoints. Checkpoints are additionally invalidated by logical-range
overlap: KV computed in the presence of the redacted span partially encodes
it (stale survivors, spec 13.1), so any checkpoint whose coverage includes
the span fails closed even without an explicit edge. redaction_generation
increments on the thread.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .store import SqliteIndex


@dataclass
class RedactionReport:
    span_id: str
    redaction_generation: int
    invalidated_blocks: list[str] = field(default_factory=list)
    invalidated_checkpoints: list[str] = field(default_factory=list)


class RedactionGraphInvalidator:
    def __init__(self, index: SqliteIndex):
        self.index = index

    def redact_span(self, span_id: str) -> RedactionReport:
        span = self.index.get_span(span_id)
        if span is None:
            raise KeyError(f"unknown span {span_id}")
        thread_id = span["thread_id"]
        generation = self.index.bump_redaction_generation(thread_id)
        self.index.mark_span_redacted(span_id, generation)

        report = RedactionReport(span_id=span_id, redaction_generation=generation)

        # 1. Transitive closure over derived_from edges rooted at the span.
        frontier = [span_id]
        seen: set[str] = set()
        while frontier:
            parent = frontier.pop()
            for child in self.index.children_of(parent, "derived_from"):
                if child in seen:
                    continue
                seen.add(child)
                self.index.invalidate_artifact(child)
                if child.startswith("mb_"):
                    report.invalidated_blocks.append(child)
                elif child.startswith("ckpt_"):
                    report.invalidated_checkpoints.append(child)
                frontier.append(child)

        # 2. Conservative KV rule: any checkpoint of this thread whose logical
        #    coverage includes the span carries its influence (spec 13.1).
        for row in self.index.checkpoints_for_thread(thread_id):
            if row["invalidated"]:
                continue
            if row["token_start"] < span["token_end"] and row["token_end"] > span["token_start"]:
                self.index.invalidate_artifact(row["checkpoint_id"])
                report.invalidated_checkpoints.append(row["checkpoint_id"])

        return report
