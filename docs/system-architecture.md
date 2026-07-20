# memsub — System Architecture (M0–M3.5 + research campaigns)

Authoritative design: `unified_memory_substrate_spec_v0.3.7.md` (M0–M2 built
against v0.3.6.1); scope: `BUILD.md` for the MVP, campaign briefs
(`GATE.md`, `COMPACTOR.md`, `PROBE.md`, `FULLRECIPE.md`, `ESCAPE.md`,
`E1FULL.md`) for everything after M2.

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

  -- M3 decision layer (GATE.md / ABLATION.md) --
  gate/dual_encoder_expansion_gate.py    frozen-shadow dual encoder + temperature
                                         calibration; mechanics features dominate
  gate/label_dataset_splits.py           GateDataset + document-level splits
  gate/gate_evaluation_metrics.py        AUC/ECE, threshold sweep, operating point,
                                         baseline decision rows (never/always/oracle)
  gate/domain_recalibration.py           per-domain temperature + Platt escalation
  gate/expansion_budget_harness.py       end-to-end lost-fact vs expand-rate
  gate/set_scoring_selector.py           WP2 s1/s2 grouped multi-hop expansion

  -- M3.5 compaction policy (COMPACTOR.md) --
  compactor/still_perceiver_layer_compactor.py  per-layer Perceiver: t latent queries
                                         per KV head, B=2 blocks, QK-norm, logit
                                         scale d_l (the ESCAPE lever), identity init
  compactor/still_amortized_kv_compactor.py     36-layer stack over a
                                         CompactedPrefixCache; un-rotate -> compact ->
                                         re-rotate at output positions; policy_version
                                         binds weights hash + max_certified_depth
  compactor/rope_rotation_helpers.py     model/internal RoPE apply + unrotate
  compactor/compactor_training_objective.py  forward KL on answer tokens, top-200
                                         teacher support with gold forced in (set-
                                         support; the pre-f214c0f multiset variant is
                                         reachable only via an explicit legacy flag)
```

## Research-campaign harnesses (`modal-runners/`, not runtime code)

```
fullrecipe-instrumented-ddp-training-inner-script.py  torchrun target: true batch 32
                                     (explicit grad all-reduce — the M3.5 script
                                     bypassed the DDP wrapper and never synced),
                                     step-tagged resume, GT27 tripwire + NaN abort,
                                     --lever {e1_sqrt_scale, e2_learned_temp,
                                     e3_anchor_noise, e4_content_seed}
fullrecipe-entropy-telemetry-capture-module.py  I1: per-layer block-1 cross-attn row
                                     entropy + argmax-kernel histograms on a fixed
                                     128-item probe batch (the collapse detector)
modal-fullrecipe-i2-*.py             I2: per-checkpoint GT16 relabel fused with
                                     kept-kernel capture -> d_min AUC trajectory
modal-escape-g1g2-*.py               init-time per-group gradient forensics
modal-m35-certification-and-gate-refresh.py  certify_arms / relabel_slice /
                                     refresh_gate / wp2_eval (all policy-parameterized)
modal-probe-*, modal-followup*       read-side probe capture/training, sink-head
                                     monitor, context-only controls
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
- A trained compaction policy is identified by `compaction_policy_version`
  (weights hash + certified depth); relabels, gates, and probes are
  policy-scoped artifacts — a policy change invalidates them along with the
  caches (measured: label base rates and best probe layer both move).
- E1-class checkpoints (ESCAPE lever) are trained AND deployed at logit scale
  √d_l = 16: every harness takes `--lever e1_sqrt_scale`. Loading such a
  checkpoint at the canonical scale silently changes its routing.
- Compactor certification carries two mandatory pre-training diagnostics
  (spec v0.3.7 §13.4): init-time gradient forensics and cross-attention
  entropy telemetry — a compactor can optimize its loss for thousands of
  steps while its routing pathway receives ~zero gradient.

## Compute split
- Local (low-RAM laptop): tiny random Qwen3-config model on CPU exercises all logic,
  including the dense-mask equivalence check of the position machinery.
- Modal (`modal-runners/modal-reference-golden-test-runner.py`): reference config
  (Qwen3-4B bf16, H100) runs GT1 at T∈{1k,8k}, GT4 semantic flip, smokes, and the
  B.3 pilot + certification. Artifacts persist in the `memsub-artifacts` volume.
