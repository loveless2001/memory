"""Segmenter: turn boundaries + token-count cap (spec B.2; BUILD.md P2).

Spans never cross a conversation turn; turns longer than the cap are split
into consecutive spans of at most `max_tokens` (default 2048, i.e. the
"1-2k token cap")."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MAX_TOKENS = 2048


@dataclass
class Segment:
    role: str
    token_start: int        # logical, thread-absolute
    token_end: int          # exclusive
    token_ids: list[int]
    text: str


def segment_turns(
    turns: list[dict],
    *,
    tokenizer,
    base_position: int = 0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[Segment]:
    """Segment a list of {role, text} turns into archivable spans.

    Each turn is tokenized independently (add_special_tokens=False) so that a
    span's token ids always concatenate back to the thread's token stream.
    """
    segments: list[Segment] = []
    pos = base_position
    for turn in turns:
        role, text = turn["role"], turn["text"]
        ids = tokenizer.encode(text, add_special_tokens=False)
        offset = 0
        while offset < len(ids):
            chunk_ids = ids[offset:offset + max_tokens]
            chunk_text = tokenizer.decode(chunk_ids)
            segments.append(Segment(
                role=role,
                token_start=pos,
                token_end=pos + len(chunk_ids),
                token_ids=list(chunk_ids),
                text=chunk_text,
            ))
            pos += len(chunk_ids)
            offset += len(chunk_ids)
        if not ids:  # empty turn still marks a boundary; skip storage
            continue
    return segments
