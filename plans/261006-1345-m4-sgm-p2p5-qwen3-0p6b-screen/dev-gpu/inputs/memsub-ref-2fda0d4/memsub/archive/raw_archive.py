"""Raw transcript archive + span index (spec 8.1, B.2).

The only durable tier (spec 4.6): every cache-grade artifact must be
reconstructible from here at re-prefill cost. Reads fail closed on redaction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..errors import RedactionError
from ..hashing import sha256_json
from ..ids import new_span_id
from ..store import BlobStore, SqliteIndex


@dataclass
class ArchivedSpan:
    span_id: str
    thread_id: str
    token_start: int
    token_end: int          # exclusive
    role: str
    text: str
    token_ids: list[int]
    content_hash: str


class RawArchive:
    def __init__(self, index: SqliteIndex, blobs: BlobStore):
        self.index = index
        self.blobs = blobs

    def archive_span(self, thread_id: str, *, token_start: int, token_end: int,
                     role: str, text: str, token_ids: list[int]) -> ArchivedSpan:
        """Persist one segmented span. token range is logical [start, end)."""
        if token_end - token_start != len(token_ids):
            raise ValueError("token range does not match token_ids length")
        span_id = new_span_id()
        text_uri = self.blobs.put_text(text)
        tokens_uri = self.blobs.put(json.dumps(token_ids).encode())
        content_hash = sha256_json({"text": text, "token_ids": token_ids})
        self.index.insert_span(
            span_id=span_id, thread_id=thread_id, token_start=token_start,
            token_end=token_end, role=role, text_uri=text_uri,
            tokens_uri=tokens_uri, content_hash=content_hash,
        )
        return ArchivedSpan(span_id, thread_id, token_start, token_end, role,
                            text, token_ids, content_hash)

    def _row_or_fail(self, span_id: str):
        row = self.index.get_span(span_id)
        if row is None:
            raise KeyError(f"unknown span {span_id}")
        if row["redacted"]:
            raise RedactionError(f"span {span_id} is redacted (fail closed)")
        return row

    def get_span_text(self, span_id: str) -> str:
        return self.blobs.get_text(self._row_or_fail(span_id)["text_uri"])

    def get_span_tokens(self, span_id: str) -> list[int]:
        return json.loads(self.blobs.get(self._row_or_fail(span_id)["tokens_uri"]))

    def spans_for_thread(self, thread_id: str):
        return self.index.spans_for_thread(thread_id)

    def spans_overlapping(self, thread_id: str, token_start: int, token_end: int):
        return [r for r in self.index.spans_for_thread(thread_id)
                if r["token_start"] < token_end and r["token_end"] > token_start]

    def full_text(self, thread_id: str) -> str:
        """Reconstruct the full transcript (L0 fallback path). Fails closed if
        any span is redacted."""
        parts = []
        for row in self.index.spans_for_thread(thread_id):
            parts.append(self.get_span_text(row["span_id"]))
        return "".join(parts)

    def full_token_ids(self, thread_id: str) -> list[int]:
        out: list[int] = []
        for row in self.index.spans_for_thread(thread_id):
            out.extend(self.get_span_tokens(row["span_id"]))
        return out
