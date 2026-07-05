"""Naive top-k selector over embedding shadows (BUILD.md P3: "selector may
be naive top-k over shadows at this stage"). M3 scoring is out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..compilers.embedding_shadow_indexer import Embedder
from ..schemas import MemoryBlock
from ..store import BlobStore


@dataclass
class ScoredBlock:
    block_id: str
    score: float


class NaiveTopKSelector:
    def __init__(self, embedder: Embedder, blobs: BlobStore):
        self.embedder = embedder
        self.blobs = blobs

    def rank(self, query: str, blocks: list[MemoryBlock], k: int = 3) -> list[ScoredBlock]:
        candidates = [
            b for b in blocks
            if b.embedding_shadow.embedding_policy_version == self.embedder.embedding_policy_version
        ]
        if not candidates:
            return []
        qvec = self.embedder.embed([query])[0]
        scored = []
        for block in candidates:
            data = self.blobs.get(block.embedding_shadow.embedding_uri)
            vec = np.frombuffer(data, dtype=np.float32)
            denom = (np.linalg.norm(qvec) * np.linalg.norm(vec)) or 1.0
            scored.append(ScoredBlock(block.block_id, float(qvec @ vec / denom)))
        scored.sort(key=lambda s: -s.score)
        return scored[:k]
