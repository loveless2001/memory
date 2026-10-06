"""MemoryBlock schema — extracted verbatim from spec 6.1 (BUILD.md 5).

MVP invariants: exactly one role="primary" representation, substrate-grade
(text or raw pointer, compatibility_fingerprint null); embedding_shadow is
mandatory; derived_from / supersedes populated (GT5 depends on them).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Source:
    type: str                      # conversation_span | document_span | tool_log | generated_reasoning
    uri: str
    token_start: int
    token_end: int
    hash: str
    redaction_generation: int = 0


@dataclass
class Representation:
    role: str                      # primary | auxiliary
    format: str                    # summary_text | raw_text_pointer | kv_pages
    dtype: str
    storage_uri: str
    checksum: str
    compatibility_fingerprint: Optional[dict] = None
    created_from_representation: Optional[str] = None
    shape: Optional[list[int]] = None


@dataclass
class EmbeddingShadow:
    text_gloss_uri: str
    embedding_uri: str
    embedding_model_id: str
    embedding_model_hash: str
    embedding_dim: int
    embedding_policy_version: str  # "shadow-v1" for the reference embedder
    created_from_representation: str
    source_hash: str
    redaction_generation: int
    checksum: str


@dataclass
class Positioning:
    logical_position_start: int
    logical_position_end: int
    physical_position_start: Optional[int] = None
    rope_base_offset: Optional[int] = None
    position_scheme: str = "absolute"


@dataclass
class Quality:
    importance: float = 0.5
    freshness: float = 1.0
    confidence: float = 0.5
    loss_estimate: float = 0.0
    consolidation_depth: int = 0
    pin: bool = False


@dataclass
class Security:
    trust_level: str = "user"      # system | user | tool | untrusted_external
    encrypted: bool = False
    signed_by_runtime: bool = False


@dataclass
class MemoryBlock:
    block_id: str
    thread_id: str
    semantic_kind: str
    channel: str
    source: Source
    representations: list[Representation]
    embedding_shadow: EmbeddingShadow
    positioning: Positioning
    derived_from: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    quality: Quality = field(default_factory=Quality)
    security: Security = field(default_factory=Security)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        primaries = [r for r in self.representations if r.role == "primary"]
        if len(primaries) != 1:
            raise ValueError("MemoryBlock requires exactly one primary representation")
        if primaries[0].compatibility_fingerprint is not None:
            raise ValueError("primary representation must be substrate-grade (fingerprint null)")
        if self.embedding_shadow is None:
            raise ValueError("embedding_shadow is mandatory on every block")

    @property
    def primary(self) -> Representation:
        return next(r for r in self.representations if r.role == "primary")

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryBlock":
        d = dict(d)
        d["source"] = Source(**d["source"])
        d["representations"] = [Representation(**r) for r in d["representations"]]
        d["embedding_shadow"] = EmbeddingShadow(**d["embedding_shadow"])
        d["positioning"] = Positioning(**d["positioning"])
        d["quality"] = Quality(**d["quality"])
        d["security"] = Security(**d["security"])
        return cls(**d)
