# memsub MVP (M0–M2) — BUILD.md fulfillment plan

Source of truth: `BUILD.md` (scope) + `unified_memory_substrate_spec_v0.3.6.1.md` (semantics).
Deliverable: Python library `memsub` + thin CLI. No training, no vLLM, no HTTP, no channels/soft-slots.

## Compute strategy
- Local (WSL2, 6.8GB RAM, 6GB RTX3060): logic tests on tiny random Qwen3-config model (CPU),
  stub summarizer/embedder. All GT logic paths covered locally.
- Modal (token present): reference-config runs — Qwen3-4B-Instruct-2507 bf16 on 24GB GPU (L4/A10G):
  GT1 at T∈{1k,8k}, GT4 certification with real needle probes, real summaries,
  Qwen3-Embedding-0.6B shadows, B.3 pilot MCQ pipeline (1–2k items), milestone smokes.

## Key design decisions
- CompactedPrefixCache = DynamicCache subclass + custom decode loop:
  `position_ids` carry LOGICAL positions (RoPE), `cache_position` carries PHYSICAL
  positions (mask sizing). Keys keep their original rotations; arbitrary mid-span
  eviction preserved geometry. `next_logical_position` tracked explicitly.
- Pages: 64-token safetensors pages, content-addressed → delta checkpoints and CoW
  lineage fall out of content addressing. Page table maps physical order → page ids
  + logical ranges (compaction_map).
- SQLite for all metadata (blocks, spans, checkpoints, derived_from/supersedes edges,
  redaction_generation). Blob store = content-addressed FS.
- Fingerprint module computed before any KV write; every artifact write path requires one.

## Phases (BUILD.md §3)
- [x] P0 env pin (torch 2.7.1 / transformers 4.55.2 / safetensors 0.5.3, py3.12),
      fingerprint module, repo skeleton, golden tests xfail    → first commit
- [x] P1 CompactedPrefixCache + GT1 (tiny local; reference on Modal)
- [x] P2 raw archive + span index + segmenter (turn boundary + 1–2k cap)
- [x] P3 summaries + shadows + runtime EXPAND (naive top-k selector)   → M0
- [x] P4 compaction/eviction, sink pinning, MemoryBlock, offline certification harness,
      pilot MCQ pipeline → M1 (GT2, GT4)
- [x] P5 safetensors delta checkpoints, mmap hydration, hydrate-or-fallback → M2 (GT3)
- [x] Modal app: full golden suite + smokes on reference config; report

## Status — COMPLETE (2026-07-06)
- 62/62 local tests green (tiny-model reference config).
- Modal reference runs green: GT1 T∈{1k,8k}, GT2–GT5, M0/M1/M2 smokes, pilot MCQ + certification.
- See plans/reports/build-260706-0150-memsub-mvp-final-report.md
