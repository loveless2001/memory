"""memsub — Unified Memory Substrate MVP (M0-M2).

Text substrate with raw archive + summaries + embedding shadows (M0),
sink-pinned compaction/eviction with offline certification (M1), and
safetensors delta checkpoints with hydrate-or-fallback resume (M2).

Reference config: Qwen/Qwen3-4B-Instruct-2507, bf16, single GPU, HF
transformers runtime (spec Appendix B.1). KV artifacts are caches; the raw
archive + summaries + provenance graph is the only durable layer (spec 4.6).
"""

__version__ = "0.1.0"
