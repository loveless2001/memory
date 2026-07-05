# memsub — System Architecture (MVP M0–M2)

Authoritative design: `unified_memory_substrate_spec_v0.3.6.1.md`; scope: `BUILD.md`.

## Layers

```
durable substrate   raw archive (content-addressed blobs) + span index (SQLite)
                    + summaries + embedding shadows + provenance graph
cache tier          CompactedPrefixCache (live KV) and safetensors delta
                    checkpoints — invalidated freely, always reconstructible
```

## Module map

```
memsub/
  fingerprint.py                     compatibility_fingerprint (spec 4.6), 14 fields,
                                     kernel probe hash; required by every KV write path
  hashing.py / ids.py / errors.py    sha256 canonical hashes, ULID ids, fail-closed errors
  store/blob_store.py                content-addressed FS store (store://blobs/sha256/..)
  store/sqlite_index.py              threads, spans, blocks, checkpoints, derived_from/
                                     supersedes edges, redaction generations
  archive/raw_archive.py             durable raw spans; reads fail closed on redaction
  archive/turn_boundary_segmenter.py turn boundaries + 1–2k token cap (spec B.2)
  schemas/memory_block.py            spec 6.1 verbatim; 1 primary rep, mandatory shadow
  schemas/thread_checkpoint.py       spec 6.2 verbatim; sampler_state best_effort
  runtime/compacted_prefix_cache.py  B.7 tier (a): DynamicCache subclass; logical
                                     positions per physical slot; sink pinning; mid-span
                                     eviction via index_select
  runtime/hf_model_runtime.py        custom decode loop: position_ids=LOGICAL (RoPE),
                                     cache_position=PHYSICAL (mask); prefill/extend/
                                     greedy/MCQ scoring; never model.generate()
  compilers/base_model_summarizer.py summaries by the base model (stub for CPU tests)
  compilers/embedding_shadow_indexer.py  Qwen3-Embedding-0.6B "shadow-v1" (hash stub for tests)
  selection/naive_topk_selector.py   cosine top-k over shadows (M3 scoring out of scope)
  selection/runtime_gated_expand.py  mode-A gate → RETRIEVED_EXACT injection
  compaction/sink_pinned_span_compactor.py  spec 7.3 flow; asserts sinks pre-mutation
  certification/pilot_mcq_pipeline.py      B.3 filters (a)+(b); eq_policy_v1
  certification/offline_certification_harness.py  spec 13.4; aggregation & pointwise
                                     axes strictly separate (no blended field)
  checkpoints/safetensors_delta_checkpoint_store.py  64-token pages, content-addressed →
                                     delta/CoW; mmap hydration, sinks first; hard
                                     fingerprint gate before any page read
  checkpoints/hydrate_or_fallback_resume.py  spec 7.4 fast/fallback paths
  redaction_graph_invalidator.py     GT5: derived_from closure + conservative KV-overlap
  substrate_facade.py                wiring; cli.py thin argparse CLI
  reference_config.py                reference (Qwen3-4B GPU) vs tiny (CPU) builders
```

## Key invariants
- No KV artifact written without a fingerprint; validation all-or-nothing, hard fail.
- Sink positions 0–3 pinned: compactor and cache raise before mutation; checkpoints
  record `sink_tokens_retained`; hydration loads sink pages first.
- Persisted KV is never reinterpreted under a different position policy: the
  compaction map stores every slot's logical position; continuation queries take
  logical RoPE positions.
- Redaction: derived_from closure invalidates blocks/checkpoints; any checkpoint whose
  logical coverage includes a redacted span is invalidated (stale survivors, spec 13.1).
- Certification reports the aggregation and pointwise axes separately, never blended.

## Compute split
- Local (low-RAM laptop): tiny random Qwen3-config model on CPU exercises all logic,
  including the dense-mask equivalence check of the position machinery.
- Modal (`modal-runners/modal-reference-golden-test-runner.py`): reference config
  (Qwen3-4B bf16, H100) runs GT1 at T∈{1k,8k}, GT4 semantic flip, smokes, and the
  B.3 pilot + certification. Artifacts persist in the `memsub-artifacts` volume.
