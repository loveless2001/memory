# Project Changelog

## 2026-07-06 — MVP M0–M2 initial implementation (branch `mvp`)

- Repo re-initialized on orphan branch `mvp` (previous Zep history retired).
- **P0**: pinned environment (py3.12, torch 2.7.1, transformers 4.55.2,
  safetensors 0.5.3); `compatibility_fingerprint` module with operational
  `kernel_numeric_profile_hash` (env + fixed-input probe). First commit per
  BUILD.md ground rule 1.
- **P1**: `CompactedPrefixCache` (HF Cache subclass, pure PyTorch): logical
  RoPE positions decoupled from physical mask positions; GT1 identity round
  trip green (memory + disk restore paths) plus a dense-masked-forward
  equivalence test of the eviction geometry.
- **P2**: raw archive (content-addressed blobs + SQLite span index),
  turn-boundary segmenter with 1–2k token cap.
- **P3 (M0)**: base-model summaries, Qwen3-Embedding shadows (`shadow-v1`),
  naive top-k selector, runtime-gated EXPAND via RETRIEVED_EXACT.
- **P4 (M1)**: sink-pinned compaction/eviction (`evict-oldest-nonsink-v1`),
  MemoryBlock creation with provenance edges, offline certification harness
  (spec 13.4) with strictly separated aggregation/pointwise axes, B.3 pilot
  MCQ pipeline with counterfactual filters, eq_policy_v1.
- **P5 (M2)**: safetensors delta checkpoints (64-token content-addressed
  pages → delta + CoW lineage), mmap hydration with sink pages first,
  fingerprint-gated hydrate-or-fallback resume.
- Golden tests GT1–GT5 implemented; local suite green on tiny config;
  reference runs executed on Modal (H100) — see
  `plans/reports/build-260706-0150-memsub-mvp-final-report.md`.
- Explicitly deferred per BUILD.md 7: M3 selector/gate, M3.5 compactor,
  vLLM tier, HTTP API, channels/soft-slots/latent compression, any training.

## 2026-07-06 (later) — B.3 four-domain test corpus + 2k-item MCQ set

- Assembled real corpus per spec B.3 domains into `memsub-artifacts` volume:
  SEC 10-K filings, US court opinions, permissive-license code, literature —
  7,232 docs, ~155M est. tokens (`modal-runners/modal-b3-corpus-pipeline.py`).
- Generated 2,000 filter-verified MCQ items (500/domain, 4×H100 parallel).
- Certified untrained eviction at 0.40 over 12 contexts: aggregation axis
  nearly unmoved (KL ~1e-2, no MCQ delta), pointwise axis flips where the
  needle chunk is evicted — spec 4.7 two-workload split reproduced on real data.
- Report: plans/reports/corpus-260706-0341-b3-four-domain-corpus-run.md
