"""Raw indexer / embedding shadows (spec 8.1 — mandatory infrastructure).

Every block gets an embedding shadow and a raw pointer; no block may be
created without passing through the indexer. Reference embedder:
Qwen3-Embedding-0.6B, recorded as policy "shadow-v1" (BUILD.md 2.4).
"""

from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np

from ..hashing import sha256_bytes, sha256_text
from ..schemas import EmbeddingShadow
from ..store import BlobStore


class Embedder(Protocol):
    embedding_model_id: str
    embedding_model_hash: str
    embedding_dim: int
    embedding_policy_version: str

    def embed(self, texts: list[str]) -> np.ndarray: ...


class Qwen3ShadowEmbedder:
    """Qwen3-Embedding-0.6B, last-token pooling, L2-normalized (shadow-v1)."""

    embedding_policy_version = "shadow-v1"

    def __init__(self, model_id: str = "Qwen/Qwen3-Embedding-0.6B",
                 device: str = "cuda", dtype: str = "float32"):
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side="left")
        self.model = AutoModel.from_pretrained(
            model_id, torch_dtype=getattr(torch, dtype)).to(device).eval()
        self.device = device
        self.embedding_model_id = model_id
        self.embedding_model_hash = sha256_text(model_id + ":" + dtype)
        self.embedding_dim = int(self.model.config.hidden_size)

    def embed(self, texts: list[str]) -> np.ndarray:
        import torch
        with torch.inference_mode():
            batch = self.tokenizer(texts, padding=True, truncation=True,
                                   max_length=2048, return_tensors="pt").to(self.device)
            hidden = self.model(**batch).last_hidden_state
            vecs = hidden[:, -1]  # left padding → last token is real
            vecs = torch.nn.functional.normalize(vecs, dim=-1)
            return vecs.float().cpu().numpy()


class HashStubEmbedder:
    """Deterministic bag-of-ngrams hash embedding for CPU logic tests.
    Similar texts share ngrams, so top-k selection behaves sensibly."""

    embedding_policy_version = "shadow-stub-hash-v1"
    embedding_model_id = "hash-ngram-stub"
    embedding_model_hash = sha256_text("hash-ngram-stub")
    embedding_dim = 256

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.embedding_dim), dtype=np.float32)
        for row, text in enumerate(texts):
            words = text.lower().split()
            for w in words:
                idx = int.from_bytes(hashlib.sha256(w.encode()).digest()[:4], "big")
                out[row, idx % self.embedding_dim] += 1.0
            norm = np.linalg.norm(out[row])
            if norm > 0:
                out[row] /= norm
        return out


class EmbeddingShadowIndexer:
    def __init__(self, embedder: Embedder, blobs: BlobStore):
        self.embedder = embedder
        self.blobs = blobs

    def build_shadow(self, gloss_text: str, *, created_from: str,
                     source_hash: str, redaction_generation: int = 0) -> EmbeddingShadow:
        vec = self.embedder.embed([gloss_text])[0].astype(np.float32)
        vec_bytes = vec.tobytes()
        return EmbeddingShadow(
            text_gloss_uri=self.blobs.put_text(gloss_text),
            embedding_uri=self.blobs.put(vec_bytes),
            embedding_model_id=self.embedder.embedding_model_id,
            embedding_model_hash=self.embedder.embedding_model_hash,
            embedding_dim=self.embedder.embedding_dim,
            embedding_policy_version=self.embedder.embedding_policy_version,
            created_from_representation=created_from,
            source_hash=source_hash,
            redaction_generation=redaction_generation,
            checksum=sha256_bytes(vec_bytes),
        )

    def load_vector(self, shadow: EmbeddingShadow) -> np.ndarray:
        data = self.blobs.get(shadow.embedding_uri)
        return np.frombuffer(data, dtype=np.float32).copy()
