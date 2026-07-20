# Unified Memory Substrate for Long-Context LLM Threads

**Technical Specification — Draft v0.3.7**
**Date:** 2026-06-10
**Status:** tightened architecture spec
**Primary goal:** smooth a stack of context/KV/cache-compression methods into one coherent runtime interface, without requiring the base model to learn a large zoo of special tokens.

**Changes from v0.2:** see Changelog at end. **v0.3.2 note:** the v0.3 revision was produced against a stale v0.2 base and silently dropped the deselect-regime and decoupled-gate-training material; v0.3.1 restores it under the new numbering (§13.7, §17.5, Appendix A), restores the §13.6 selection rationale, reconciles §7.2 with the §17.2 EXPAND contract, defines the kernel numeric profile hash, and applies the v0.3.2 consistency patch: canonical channel enum, summary-text representation naming, online-risk compaction wording, cache-reversible deselection wording, model-visible EXPAND block IDs, and citation-needed markers for system-specific appendix claims. **v0.3.3** integrates the verified Still results (O'Neill et al., arXiv:2606.07878) — amortized KV synthesis as the third compaction regime, recurrence-depth certification, KV-level consolidation, and empirical anchors for the §8.3 loss target and §12 position rules — and adds Appendix B, a reference MVP build with a concrete target model and training pipeline. **v0.3.4** makes the spec's implicit design thesis explicit: pointwise exact recall and aggregative long-context understanding are two antagonistic workloads that no single representation serves (§4.7), with two-axis certification reporting (§13.4) and query-type routing in the expansion gate (§17). **v0.3.5** adds §11.7, a compute-accounting section: the substrate's mechanisms primarily buy memory capacity and bandwidth, not FLOPs — the section states per-mechanism compute ledgers, amortization horizons, the store-vs-recompute break-even, and the normative rules that follow. **v0.3.6** adds §11.8: branching and compression are orthogonal concerns that compose over the shared page substrate (one architecture, two operations) — with a single hostile cell, branching-under-recurrent-absorption, resolved by a routing rule rather than a second architecture. **v0.3.7** is the empirical-closure revision: the MVP campaigns (2026-07) produced the first L3 configuration to pass a §13.4 predicate — an unfrozen amortized compactor certified on the task-anchored predicate at matched budget (the distributional predicate is not yet met; the two dissociate, which §6.2 records), added as a recommended opt-in L3 policy rather than a default flip; training-time saturation diagnostics added to compactor certification (§13.4); §17.3's relational definition of sufficiency, §13.6's sink-as-sensor, and regime-relative fragility upgraded from design claims to measured results; dedup compiler added (§8.1). Headline changes: (1) the `MemoryBlock` schema now separates `semantic_kind` from representation format; (2) a canonical `compatibility_fingerprint` replaces ad hoc compatibility fingerprints; (3) embedding shadows now carry explicit versioning and invalidation metadata; (4) `EXPAND` has a clearer runtime/model contract and answer-equivalence labeling protocol; (5) fidelity evaluation is split into offline certification and online risk metadata; (6) the MVP core is visually separated from research extensions; (7) a worked end-to-end example was added.

---

## 1. Executive Summary

This spec defines a runtime and model-interface design for long-lived LLM conversation threads that combine:

- recent exact KV cache,
- compressed long-term memory,
- disk-backed persistence,
- resumable thread checkpoints,
- exact raw-context expansion when compressed memory is insufficient.

The central design choice is to introduce a **MemoryBlock intermediate representation (IR)** and a small set of typed **input channels**. Different memory techniques—Memento-style summaries, latent context compression, compressed KV, disk-backed KV pages, retrieved text, and future state-vector caches—compile into the same model-facing interface:

```text
recent exact context
+ typed memory slots / memory KV banks
+ optional exact retrieved expansions
```

**Substrate vs cache (the v0.2 framing).** The only tier of this system that is durable across model updates, quantization changes, and runtime upgrades is **text plus provenance metadata** (raw transcripts, summaries, pointers, hashes). Every KV- or state-level artifact is bound to an exact (model, tokenizer, adapter, quantization, runtime) tuple and is invalidated whenever any element of that tuple changes. Therefore:

```text
substrate  = raw archive + summaries + provenance     (durable, source of truth)
cache      = compacted KV, soft slots, state vectors  (regenerable, TTL-bounded)
```

Everything in this spec that persists KV or latent state is an **acceleration tier over the substrate**, never the substrate itself. Resume paths, garbage collection, and storage budgeting all follow from this distinction.

The model should not need to learn many protocol markers for memory management. For non-textual content (soft slots, KV banks), the runtime carries type and provenance using side metadata, channel embeddings, attention masks, and/or separate K/V banks. For textual content, the existing chat-template special tokens are retained as the channel mechanism (see §4.2 for the narrowed claim).

---

## 2. Problem Statement

Long-running LLM threads hit several linked bottlenecks:

1. **KV cache grows linearly with sequence length.**
   - Exact continuation is expensive in GPU memory.
   - Very long contexts also increase attention cost.

2. **Text-only summaries are lossy.**
   - Summaries are portable and cheap, but they lose implicit latent state.
   - Restarting from summary text alone is weaker than preserving the compacted KV state induced by that summary.

3. **Multiple compression techniques use incompatible interfaces.**
   - Some use special text tokens.
   - Some produce latent vectors.
   - Some manipulate KV pages.
   - Some rely on retrieval or expansion tools.

4. **A single state vector is not enough for general continuation.**
   - Attention is query-dependent retrieval over a set.
   - A viable compressed state usually needs either multiple state vectors, synthetic memory slots, or a decoder that regenerates K/V-like banks.

5. **Resume should be fast and high-fidelity.**
   - Re-prefilling from the whole transcript is expensive.
   - Re-prefilling from summaries alone loses state.
   - Restoring compacted KV checkpoints from disk is the practical middle ground.

6. **Eviction is not free even when the surviving KV is byte-correct.**
   - Removing KV entries changes the softmax normalization seen by all subsequent queries.
   - Surviving KV was computed in the presence of the evicted span and partially encodes it.
   - Fidelity after eviction is therefore empirical and model-dependent, not guaranteed by construction (§13).

---

## 3. Non-Goals

This draft does **not** attempt to specify:

- a new base Transformer architecture;
- exact training recipes for a production latent compressor;
- model-specific kernel implementations;
- an API for user-supplied hidden activations;
- a final standard for all vendors.

The goal is to define a clean runtime abstraction that can host several memory approaches without producing protocol-token clutter.

---

## 4. Core Design Principles

### 4.1 One memory IR, many backends

Every memory source compiles into a `MemoryBlock`. Examples:

```text
Memento summary            → MemoryBlock
LCLM latent context        → MemoryBlock
Compressed KV pages        → MemoryBlock
Disk-backed checkpoint     → MemoryBlock
Retrieved raw text chunk   → MemoryBlock
Future recurrent states    → MemoryBlock
```

### 4.2 Channels for non-textual content; templates for text

v0.1 stated a blanket preference for side-channel metadata over special tokens. That claim was too broad. Chat templates — which are special-token channels — are how every production model already segments SYSTEM/USER/ASSISTANT/TOOL content, they work, and they cost nothing architecturally. The narrowed claim:

```text
textual content      → existing chat-template special tokens (no change)
non-textual content  → typed channels (metadata, channel embeddings,
                       separate K/V banks, attention masks/biases)
```

The channel machinery is **necessary** for non-textual content because soft slots and KV banks have no tokens to delimit: there is nothing to wrap a delimiter around. It is **optional** for text, and the default is to not invent new textual delimiters where the template already provides them.

What this spec still rejects is the proliferation of *memory-protocol* tokens (`<|memory_start|>`, `<|latent_block|>`, `<|cache_resume|>`, per-compressor markers) that the model must be trained to emit and parse. Memory bookkeeping lives in runtime metadata, not in the token stream. The one deliberate exception is `EXPAND(block_id)`, which is an ordinary tool call (§17).

### 4.3 Preserve operable state, not just human-readable text

The runtime should persist the **state needed to continue**, not merely a transcript.

For old generated reasoning, the best checkpoint is often:

```text
summary text
+ surviving summary KV
+ compaction metadata
+ raw evicted block pointer
```

not just:

```text
summary text only
```

This principle is subordinate to §4.6: operable state accelerates continuation but never replaces the textual record as source of truth.

### 4.4 Store exact source separately

Compressed memory is a lossy map. Keep raw source-of-truth text or records in a separate archive and expose an `EXPAND(block_id)` operation when exact details are needed.

### 4.5 Exact local context, compressed long-term memory

Use a hybrid memory layout:

```text
recent window      → exact KV on GPU
older stable spans → compressed memory blocks
raw transcript     → disk/object store
checkpoints        → disk-backed compacted KV/state
```

### 4.6 Text is the substrate; KV is a cache

Every KV/state artifact carries a hard `compatibility_fingerprint`. This is stronger than a loose tuple because small changes in template, RoPE policy, KV layout, or compaction policy can make persisted state semantically invalid while still byte-readable.

```json
{
  "model_id": "model-name-or-hash",
  "tokenizer_hash": "sha256:...",
  "chat_template_hash": "sha256:...",
  "rope_config_hash": "sha256:...",
  "sliding_window_config": "none | local-4096 | hybrid-...",
  "attention_impl": "flash-attn-x.y | paged-attn-x.y | custom",
  "kv_layout": "mha | gqa | mqa | mla_latent",
  "quantization": "bf16 | fp16 | int8 | gguf-q4_k_m",
  "adapter_hash": "sha256:... | null",
  "runtime_version": "vllm-x.y | llamacpp-x.y | custom",
  "compaction_policy_version": "compact-v1",
  "position_policy_version": "pos-v1",
  "channel_registry_version": "memchan-v1",
  "kernel_numeric_profile_hash": "sha256:..."
}
```

For trained compactors (§8.1), `compaction_policy_version` must incorporate the compactor's weights hash and its `max_certified_depth` (§13.4); a retrained or further-trained compactor is a new compaction policy and invalidates checkpoints produced under the old one.

`kernel_numeric_profile_hash` must be operationally defined or omitted — recommended: a hash over (attention/gemm kernel versions, dtype flags, deterministic-mode flags) concatenated with the output of a fixed numeric probe (forward pass over a canned input, hashed at reduced precision). Without an operational definition the field is decorative.

Changing any field invalidates cache-grade artifacts unless the runtime has an explicit, tested compatibility rule for that field. In a deployment with a model release cadence of weeks-to-months, the expected lifetime of the entire L2-L4 store is bounded by that cadence.

Consequences:

- The raw archive + summaries + provenance graph is the **only** layer with durability guarantees. It must be complete and self-sufficient: any KV/state tier must be reconstructible from it, at re-prefill cost.
- KV/state tiers are caches with an implicit TTL equal to deployment lifetime. Storage budgeting, replication, and backup policy treat them as such: no backups, cheap storage, aggressive GC.
- A model migration is handled by bulk-invalidating the cache tiers and lazily re-deriving them per thread on next resume — never by attempting cross-model KV translation in production paths (see §22, Q5).
- "Checkpoint" in this spec means *cached resume state*, not *durable record*. The durable record is the archive.
- Compatibility validation is a **hard fail**. A checkpoint that fails fingerprint validation may be used only as a diagnostic artifact, never as live context.

---

### 4.7 Two workloads, one substrate (new in v0.3.4)

"Long context" conflates a serving problem (fit the tokens) with two distinct capability problems that bifurcate the moment full attention becomes unaffordable:

```text
pointwise      needle-class: the answer is concentrated in exact bytes
               (an ID, a number, a verbatim clause) with near-zero
               redundancy against the surrounding context.
               INCOMPRESSIBLE: any lossy transform destroys it at a rate
               proportional to the compression ratio.
               optimal mechanism: selection / indexing / exact lookup.

aggregative    integration-class: summarization, theme tracking, most
               reasoning over documents. The answer lives in DISTRIBUTED,
               REDUNDANT information. Compression-tolerant — and mildly
               compression-benefited (denoising).
               optimal mechanism: synthesis / absorption.
```

The two are antagonistic, not merely different: compression bought for the aggregative workload is paid for in needle fidelity, and exact retention kept for needles is memory compression was meant to free. Empirical anchor: a single Still compact cache holds 90% on common-word extraction while needle retrieval collapses to 3.3–6.7% — one artifact, two workloads, opposite outcomes (§17.1).

This spec is therefore a **routed two-path architecture**, not compression with a safety valve. Compressed tiers (summaries, compact KV, recurrent state) serve the aggregative axis; the raw archive plus EXPAND serves the pointwise axis losslessly; the calibrated gate (§17) is the router that classifies, per query, which problem it is facing. The deselect regime (§13.7) is the same resolution pushed to attention granularity. EXPAND is not a fallback for compression *failure* — it is the co-equal path for a workload class that provably cannot be served by a lossy representation.

The hardest case is the middle of the spectrum: multi-hop retrieval-then-integration (find k exact facts scattered across the context, then reason over them jointly) requires both mechanisms within one query — the gate must fire several times correctly and the aggregation must then run over the expanded exact content. This is recorded as the spec's known weakest regime and the priority case for §17.6 evaluation design.

Corollary for evaluation: blended long-context scores (RULER-style aggregates) hide exactly this tradeoff — a method can win the aggregate while being needle-dead. Certification reports the two axes separately and never blends them (§13.4).

## 5. System Overview

### 5.1 High-level architecture

```text
              ┌─────────────────────┐
              │ Raw transcript/files │   ← durable substrate
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ Segmenter            │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ Memory Compiler      │
              │ - summarize          │
              │ - latent encode      │
              │ - compact KV         │
              │ - index raw source   │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ MemoryBlock Store    │   ← cache tiers
              │ GPU / CPU / NVMe     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ Runtime Selector     │
              │ budget-aware choose  │
              └──────────┬──────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────┐
│ Model Runtime                                    │
│ recent exact KV + memory slots/KV + expansions   │
└─────────────────────────────────────────────────┘
```

### 5.2 Model-facing view

The decoder sees a small canonical runtime channel enum:

```text
NORMAL_TEXT         ordinary chat-template text; role metadata distinguishes
                    SYSTEM / USER / ASSISTANT / TOOL where applicable
COMPRESSED_MEMORY   summaries, soft memory slots, compacted memory banks
RETRIEVED_EXACT     exact raw spans fetched through EXPAND or retrieval
TOOL_OBSERVATION    tool outputs and tool logs when not already represented
                    by the chat template
CONTROL             minimal operations such as EXPAND
```

The existing chat-template roles are **role metadata inside `NORMAL_TEXT`**, not separate memory-substrate channels. Non-textual content uses the explicit channels above because soft slots and K/V banks cannot be delimited by ordinary text.

---

## 6. Core Abstractions

## 6.1 MemoryBlock

A `MemoryBlock` is the durable unit of context memory. v0.3 tightens the v0.2 schema by separating:

```text
semantic identity       what the block means / where it came from
physical representation how that memory is currently stored
```

A block's `semantic_kind` is not `compressed_kv` or `latent`; those are representation formats. A summary, its induced KV, an embedding shadow, soft slots, and a later latent encoding can all be representations of the same block.

Recommended semantic kinds:

```text
conversation_span
assistant_reasoning_span
document_span
tool_observation
user_profile_memory
system_instruction_span
retrieved_external_span
consolidated_span
```

Recommended representation formats:

```text
raw_text_pointer
summary_text
text_gloss
embedding_vector
kv_pages
soft_slots
latent_tokens
state_snapshot
retrieved_text
```

Schema:

```json
{
  "block_id": "mb_01HZ...",
  "thread_id": "th_01HZ...",
  "semantic_kind": "conversation_span | assistant_reasoning_span | document_span | tool_observation | user_profile_memory | system_instruction_span | retrieved_external_span | consolidated_span",
  "channel": "NORMAL_TEXT | COMPRESSED_MEMORY | RETRIEVED_EXACT | TOOL_OBSERVATION | CONTROL",
  "derived_from": ["mb_prev"],
  "supersedes": [],
  "source": {
    "type": "conversation_span | document_span | tool_log | generated_reasoning",
    "uri": "store://raw/thread/th_01/span/0007",
    "token_start": 12000,
    "token_end": 18500,
    "hash": "sha256:...",
    "redaction_generation": 0
  },
  "representations": [
    {
      "role": "primary",
      "format": "summary_text",
      "dtype": "text",
      "storage_uri": "store://summaries/th_01/mb_01.txt",
      "checksum": "sha256:...",
      "compatibility_fingerprint": null,
      "created_from_representation": "raw_text_pointer"
    },
    {
      "role": "auxiliary",
      "format": "kv_pages",
      "dtype": "bf16",
      "shape": [64, 4096],
      "storage_uri": "mmap://kv_store/thread/th_01/block/mb_01",
      "checksum": "sha256:...",
      "compatibility_fingerprint": {
        "model_id": "model-name-or-hash",
        "tokenizer_hash": "sha256:...",
        "chat_template_hash": "sha256:...",
        "rope_config_hash": "sha256:...",
        "sliding_window_config": "none | local-4096 | hybrid-...",
        "attention_impl": "flash-attn-x.y | paged-attn-x.y | custom",
        "kv_layout": "mha | gqa | mqa | mla_latent",
        "quantization": "bf16",
        "adapter_hash": "sha256:... | null",
        "runtime_version": "vllm-x.y | llamacpp-x.y | custom",
        "compaction_policy_version": "compact-v1",
        "position_policy_version": "pos-v1",
        "channel_registry_version": "memchan-v1",
        "kernel_numeric_profile_hash": "sha256:..."
      },
      "created_from_representation": "summary_text"
    }
  ],
  "embedding_shadow": {
    "text_gloss_uri": "store://gloss/th_01/mb_01.txt",
    "embedding_uri": "store://embeds/th_01/mb_01.vec",
    "embedding_model_id": "embed-model-name-or-hash",
    "embedding_model_hash": "sha256:...",
    "embedding_dim": 1536,
    "embedding_policy_version": "shadow-v1",
    "created_from_representation": "summary_text",
    "source_hash": "sha256:...",
    "redaction_generation": 0,
    "checksum": "sha256:..."
  },
  "positioning": {
    "logical_position_start": 12000,
    "logical_position_end": 18500,
    "physical_position_start": 2048,
    "rope_base_offset": 12000,
    "position_scheme": "absolute | compacted | segment_local | relative"
  },
  "quality": {
    "importance": 0.72,
    "freshness": 0.94,
    "confidence": 0.81,
    "loss_estimate": 0.03,
    "consolidation_depth": 1,
    "pin": false
  },
  "security": {
    "trust_level": "system | user | tool | untrusted_external",
    "encrypted": true,
    "signed_by_runtime": true
  },
  "created_at": "2026-06-09T00:00:00Z",
  "updated_at": "2026-06-09T00:00:00Z"
}
```

Schema rules:

- Exactly one representation has `role: "primary"`. The primary representation must be **substrate-grade**: text or a raw pointer, with `compatibility_fingerprint: null`. It survives model migrations.
- `auxiliary` representations are cache-grade. Each carries its own `compatibility_fingerprint` and is independently invalidatable. Dropping every auxiliary representation must never lose information — only speed.
- `semantic_kind` describes the source and purpose of the memory. `representations[].format` describes storage. Do not encode storage as semantic kind.
- `embedding_shadow` is **mandatory** for every block. The selector needs a relevance signal for latent/KV blocks, and latent tensors are not directly comparable to a text query; the shadow provides a text gloss plus embedding.
- Embedding shadows are derived artifacts. They are not durable like raw text, and they are not model-bound like KV. They carry their own embedding-model metadata and are invalidated whenever the source hash, redaction generation, text-gloss policy, or embedding model changes.
- `derived_from` records lineage. `supersedes` marks blocks made redundant by consolidation (§8.4); superseded blocks become GC candidates once no live checkpoint references them.

### Required properties

A `MemoryBlock` must provide:

- a stable ID;
- a semantic kind;
- provenance back to raw source;
- a substrate-grade primary representation;
- per-representation compatibility metadata for cache-grade forms;
- embedding-shadow metadata for selection;
- position metadata;
- integrity checksums;
- channel/type metadata.

---

## 6.2 ThreadCheckpoint

A checkpoint captures enough runtime state to resume a thread without full transcript re-prefill. Per §4.6, a checkpoint is a **cache object**: it accelerates resume but the thread is always fully recoverable from the archive without it.

```json
{
  "checkpoint_id": "ckpt_01HZ...",
  "thread_id": "th_01HZ...",
  "parent_checkpoint_id": "ckpt_prev",
  "compatibility_fingerprint": {
    "model_id": "model-name-or-hash",
    "tokenizer_hash": "sha256:...",
    "chat_template_hash": "sha256:...",
    "rope_config_hash": "sha256:...",
    "sliding_window_config": "none | local-4096 | hybrid-...",
    "attention_impl": "flash-attn-x.y | paged-attn-x.y | custom",
    "kv_layout": "mha | gqa | mqa | mla_latent",
    "quantization": "bf16 | fp16 | int8 | gguf-q4_k_m",
    "adapter_hash": "sha256:... | null",
    "runtime_version": "vllm-x.y | llamacpp-x.y | custom",
    "compaction_policy_version": "compact-v1",
    "position_policy_version": "pos-v1",
    "channel_registry_version": "memchan-v1",
    "kernel_numeric_profile_hash": "sha256:..."
  },
  "surviving_token_ids_uri": "mmap://.../tokens",
  "kv_page_table_uri": "mmap://.../kv_page_table",
  "memory_block_ids": ["mb_1", "mb_2", "mb_3"],
  "sink_tokens_retained": [0, 1, 2, 3],
  "attention_metadata": {
    "attention_mask_format": "paged | block_sparse | dense",
    "compaction_map_uri": "mmap://.../compaction_map",
    "channel_bias_version": "memchan-v1"
  },
  "positioning": {
    "next_logical_position": 21544,
    "next_physical_position": 3072,
    "rope_state": "serialized-or-derived"
  },
  "sampler_state": {
    "rng_seed": 12345,
    "temperature": 0.7,
    "top_p": 0.95,
    "reproducibility": "best_effort"
  },
  "fidelity_metadata": {
    "offline_certification_id": "evfid-v1:model-build:policy:evict-ratio",
    "online_risk_estimate": 0.07,
    "sampled_probe_count": 16,
    "lost_fact_risk_estimate": 0.012,
    "measured_at": "2026-06-09T00:00:00Z"
  },
  "created_at": "2026-06-09T00:00:00Z"
}
```

Notes:

- `sampler_state.reproducibility` is `best_effort` by design: batching effects and kernel nondeterminism break bitwise reproducibility on most production runtimes. The seed is retained for debugging single-request replays, not as a determinism guarantee.
- `sink_tokens_retained` is mandatory whenever any eviction has occurred (§13).
- `fidelity_metadata` is split between an **offline certification** for the build/policy and an **online risk estimate** for this checkpoint. Production resume must never require synchronous full-context comparison (§13.4).
- `compatibility_fingerprint` validation is all-or-nothing. Partial matches require explicit compatibility rules recorded by the runtime.

### Checkpoint levels

| Level | Contents | Resume cost | Fidelity | Durability |
|---|---|---:|---|---|
| L0 | raw transcript only | high | exact after full prefill | durable (substrate) |
| L1 | summaries + raw pointers | medium | lossy, model-independent | durable (substrate) |
| L2 | latent memory blocks + recent text | medium-low | empirical, model-bound | cache |
| L3 | compacted KV checkpoint | low | **empirical, model-bound** (§13) | cache |
| L4 | full KV checkpoint | lowest | exact for this model build | cache |

v0.1 labeled L3 fidelity "high." v0.2 corrected this: L3 fidelity depends on the compaction method and on whether the model was trained for compacted continuation. v0.3 further specifies that L3 must reference an offline certification ID plus per-checkpoint online risk metadata before it becomes the default resume path.

**First task-certified L3 configuration (v0.3.7).** As of 2026-07, one configuration has passed the §13.4 **task-anchored** predicate at matched retained budget, at recurrence depth 1: a Still-class amortized compactor trained with reduced attention logit scale (√d_l — see the saturation diagnostics in §13.4). Against the eviction baseline it certifies with aggregation accuracy delta +0.042 vs −0.049 and pointwise silent loss 0.153 vs 0.597 (3.9× lower); the **distributional** predicate is NOT met (teacher KL 0.1385 vs eviction's 0.1218 — kernel mobility closed 46% of the frozen lineage's gap without crossing the line), and the two registered predicates therefore dissociate: the compactor answers better while imitating the teacher's distribution less exactly than deletion does. Depth-4 recurrence without recurrence training collapses (KL 14.2); `max_certified_depth = 0` under the distributional predicate, depth 1 under the task-anchored one. Policy version `still-compact-v1:t1024:depth0:sha256:8238173715edc8f1`. **The recommended L3 default remains evict-oldest-nonsink**; the unfrozen compactor is the recommended **opt-in** L3 policy for task-anchored deployments where its `compatibility_fingerprint` applies, paired with the residual-stream probe stack as the routing tier (evicted-only AUC 0.857; end-to-end it matches never-expand's silent-loss at 0.5% expansion and reaches 0.049 at 9.1%). Untrained eviction fails the task-anchored predicate and frozen-kernel compactors fail both; full tables in the E1FULL campaign report.

Recommended default: **L3 compacted KV checkpoint, gated by measured fidelity**, with L1 as the durable fallback that always exists.

### Invalidation and migration

```text
on compatibility_fingerprint mismatch:
  1. mark all affected L2-L4 objects invalid
  2. resume affected threads via L1 (summary prefill) or L0 (full prefill)
  3. lazily regenerate cache tiers per thread on next activity
  4. GC invalid objects on normal schedule
never attempt cross-build KV reuse or translation in production paths
```

---

## 6.3 Channel

A channel is a typed input lane. It can be implemented as:

1. token type embeddings;
2. soft memory embeddings;
3. separate K/V banks;
4. attention masks and biases;
5. cross-attention memory.

Per §4.2, channels are required only for non-textual lanes. Implementations 1–5 all require either adapter training or runtime modification; none is available off-the-shelf. This is acceptable because channels only become load-bearing at Phase 4+ (§21), by which point adapter training is already on the critical path for soft slots.

### Channel registry v1

```json
{
  "0": "NORMAL_TEXT",
  "1": "COMPRESSED_MEMORY",
  "2": "RETRIEVED_EXACT",
  "3": "TOOL_OBSERVATION",
  "4": "CONTROL"
}
```

`NORMAL_TEXT` carries the standard chat-template roles as side metadata, for example:

```json
{
  "channel": "NORMAL_TEXT",
  "role": "SYSTEM | USER | ASSISTANT | TOOL"
}
```

This prevents drift between runtime channels and chat-template roles: SYSTEM/USER/ASSISTANT/TOOL are textual roles, while `COMPRESSED_MEMORY`, `RETRIEVED_EXACT`, `TOOL_OBSERVATION`, and `CONTROL` are substrate channels.

### Embedding-level implementation

For token-like input:

\[
x_i = E_{token}(t_i) + E_{pos}(p_i) + E_{channel}(c_i)
\]

For soft memory slots:

\[
x_i = z_i + E_{pos}(p_i) + E_{channel}(c_i)
\]

For direct K/V memory banks:

\[
K = [K_{recent}, K_{memory}, K_{retrieved}, K_{tool}]
\]

\[
V = [V_{recent}, V_{memory}, V_{retrieved}, V_{tool}]
\]

Optional per-channel attention bias:

\[
\mathrm{Attn}(q,K,V,c) = \mathrm{softmax}\left(\frac{qK^T}{\sqrt{d}} + b_c\right)V
\]

---

## 7. Runtime Flow

## 7.1 New thread

```text
1. Create thread_id.
2. Initialize empty raw transcript archive.
3. Initialize empty MemoryBlock index.
4. Prefill system prompt and first user message normally.
5. Pin attention-sink tokens (first k positions, k≈4) — never evictable (§13).
6. Generate with standard KV cache.
7. Periodically segment, compact, and checkpoint.
```

## 7.2 During generation

```text
while generating:
  append token to recent exact KV

  if block boundary detected:
    produce or extract summary/memory representation
    compact evictable span (sink tokens excluded; §13)
    create MemoryBlock
    estimate online risk metadata (§13.4)
    update checkpoint

  if memory pressure high:
    move cold KV pages GPU → CPU/NVMe
    preserve page table metadata

  if exact detail needed:
    mode A (default): selector + expansion gate trigger runtime-gated
      expansion (§17.2A)
    mode B (debug/research): model emits EXPAND(block_id) against a
      selector-filtered candidate inventory (§17.2B)
    runtime injects raw source into RETRIEVED_EXACT channel
```

## 7.3 Compaction event

A compaction event converts a long span into a durable memory block.

```text
input:
  span tokens
  span KV pages
  raw transcript pointer
  optional model-generated summary

output:
  MemoryBlock (primary: summary text; auxiliary: surviving KV)
  updated compacted KV
  checkpoint with fidelity metadata
```

Pseudo-flow:

```python
def compact_span(thread, span):
    assert not overlaps(span, thread.sink_tokens)   # §13: sinks never evicted

    raw_uri = archive_raw_span(thread.id, span.tokens)

    summary = maybe_generate_summary(span)
    summary_kv = preserve_kv_for_summary_path(span, summary)

    memory_block = MemoryBlock(
        semantic_kind="assistant_reasoning_span",
        channel="COMPRESSED_MEMORY",
        source={"uri": raw_uri, "token_start": span.start, "token_end": span.end},
        representations=[
            {"role": "primary", "format": "summary_text", "storage_uri": persist_text(summary)},
            {"role": "auxiliary", "format": "kv_pages",
             "storage_uri": persist(summary_kv),
             "compatibility_fingerprint": current_compatibility_fingerprint()},
        ],
        positioning=derive_position_metadata(span),
        embedding_shadow=index_span(span, summary),
    )

    evict_original_span_kv(span)
    fidelity_metadata = estimate_online_risk(thread, span, policy_certification_id())   # §13.4
    register_memory_block(memory_block)
    record_checkpoint_risk_metadata(thread, memory_block, fidelity_metadata)
    return memory_block, fidelity_metadata
```

---

## 7.4 Resume existing thread

Fast path:

```text
1. Load latest ThreadCheckpoint.
2. Validate model/tokenizer/runtime/adapter hashes.
   On mismatch → fallback path (no cross-build reuse; §6.2).
3. Hydrate compacted KV pages and memory banks.
4. Restore position/attention metadata, including sink retention map.
5. Append new user message.
6. Continue generation.
```

Fallback path:

```text
1. Load raw transcript and MemoryBlocks (primary representations only).
2. Select memory blocks under budget.
3. Re-prefill compressed memory + recent exact text.
4. Continue generation.
5. Lazily regenerate auxiliary representations for hot blocks.
```

Exact recovery path:

```text
1. If compressed memory is insufficient, call EXPAND(block_id).   (§17)
2. Fetch raw source span.
3. Inject raw text through RETRIEVED_EXACT channel.
4. Continue with exact context locally.
```

---

## 8. Memory Compiler

The memory compiler converts raw or intermediate context into `MemoryBlock`s.

### 8.1 Supported compilers

| Compiler | Input | Output | Use case | Status |
|---|---|---|---|---|
| Raw indexer | raw text | pointer + text gloss + embeddings | selection shadow + exact fallback | **mandatory** |
| Dedup compiler | (near-)verbatim repeat of an archived span | pointer to canonical archived copy | lossless ∞-ratio compression of boilerplate (repeated tool headers, quoted spans, license blocks); no certification needed — nothing is lost; exact-match brittle by design, any mismatch falls through to the lossy tiers | v0.3.7, cheap |
| Summary compiler | old generated text | summary text + optional summary KV | Memento-like thread compaction | core |
| KV compressor | old KV pages | compressed KV pages / memory slots | cache-level compaction | core — validated instantiation: amortized synthesis (Still) |
| Latent compiler | raw document/context chunk | soft latent tokens | pre-KV context compression | Phase 5 |
| State compiler | recurrent hidden states | state vectors / slots | state-cache experiments | research |

**Validated KV-compressor instantiation (new in v0.3.3).** Amortized KV synthesis — Still (O'Neill et al., 2026, arXiv:2606.07878) — fills this row concretely: one small Perceiver per transformer layer (latent queries cross-attend the layer's full KV, project to compact keys/values), trained once against a frozen base model, producing a compact cache in a single forward pass. Canonical cost on a 4B base: ~50M parameters (~1% of base), 1500 steps at effective batch 32 on 8×H200 — squarely single-lab scale. Reported operating range: 8×–200× compression at 8k–128k contexts, beating amortized selection (KV-Distill) by 8–22 RULER points under matched training. Two structural facts matter for this spec: synthesis is not subset-bound (a compact slot blends arbitrarily many source positions, escaping the ceiling of eviction/selection), and amortization makes compaction a forward pass, enabling iterative re-compaction (§8.4). Constraints: one compactor per base checkpoint (its weights hash and certified recurrence depth are part of `compaction_policy_version`, §4.6), and a horizon-validity envelope (§13.4).

v0.1 listed the raw indexer as one compiler among several. v0.2 reclassifies it as mandatory infrastructure: every block needs an embedding shadow for the selector (§6.1, §9), and every block needs a raw pointer for EXPAND. No block may be created without passing through the indexer.

### 8.2 Compiler contract

```python
class MemoryCompiler:
    def compile(self, span: Span, budget: Budget) -> MemoryBlock:
        ...

    def estimate_loss(self, block: MemoryBlock) -> float:
        ...

    def expand(self, block_id: str) -> RawSpan:
        ...
```

### 8.3 Loss target

The ideal compiler preserves future behavior, not raw tensors:

\[
\min \mathrm{KL}\left(
  p_{full}(x_{t+1} \mid x_{\le t}),
  p_{compressed}(x_{t+1} \mid M_t, x_{recent})
\right)
\]

Secondary losses may include:

- hidden-state matching;
- attention-output matching;
- low-rank KV summary matching (note: Still's ablation makes the case against reconstruction objectives as the primary loss — a residual-MSE-trained compactor ties the KL-trained one on answer accuracy while producing ~3× worse KL/CE against the full-context teacher, i.e., tensor reconstruction preserves answerability while drifting the output distribution; behavioral KL remains the paper-facing and spec-facing objective);
- answer-level task loss;
- expansion-decision loss (promoted to a first-class problem in §17).

### 8.4 Consolidation

Long-lived threads accumulate blocks faster than budgets grow. The compiler therefore also runs **consolidation** passes, analogous to hierarchical re-summarization:

```text
trigger: block count or aggregate shadow-relevance entropy exceeds threshold
input:   k adjacent or topically-clustered blocks
output:  one consolidated block
           derived_from = [the k block ids]
           supersedes   = [the k block ids]
           primary      = merged summary (re-generated, not concatenated)
           source       = union of source spans (provenance preserved)
```

Rules:

- Consolidation never touches the raw archive; it only restructures the summary/cache layers. EXPAND on a consolidated block resolves through `source` to the union of original spans, with sub-span selection by the expansion gate (§17).
- Superseded blocks are retained until no live checkpoint references them, then GC'd.
- Consolidation depth is recorded; the selector may penalize deep consolidation (each pass compounds summary loss) via `loss_estimate`.
- **KV-level consolidation (new in v0.3.3).** Amortized compactors (§8.1) extend consolidation below the text layer: because compaction is a forward pass, already-compact KV can be re-compacted as new context arrives (Still's iterative chunked schedule, with a one-chunk raw-KV lookahead buffer that prevents compounding infidelity — an independent rediscovery of this spec's recent-exact-window principle). Two caveats bind: validity is limited to the compactor's certified recurrence depth (§13.4), and the retained cache under a fixed local ratio grows linearly at 1/c, not O(1) — so iterative KV consolidation is a complement to, not a substitute for, recurrent absorption (§16.4), which remains the only constant-state tier.

---

## 9. Memory Selector

The selector chooses which memory blocks enter the active model context.

### 9.1 Inputs

```text
current user message
recent conversation state
available MemoryBlocks
GPU/CPU/NVMe budget
latency target
quality target
```

### 9.2 Scoring function

A simple baseline (explicitly a placeholder — see 9.5):

\[
score(b) =
  \alpha \cdot relevance(b, q)
+ \beta \cdot importance(b)
+ \gamma \cdot freshness(b)
+ \delta \cdot pinned(b)
- \lambda \cdot cost(b)
- \mu \cdot loss\_estimate(b)
\]

`relevance(b, q)` is computed against the block's **embedding shadow**, never against the latent/KV payload directly — latent tensors are not comparable to a text query. This is why the shadow is mandatory (§6.1).

### 9.3 Selection policy

```python
def select_blocks(query, blocks, budget):
    scored = [(score(block, query), block) for block in blocks]
    selected = knapsack(scored, budget)
    return selected
```

### 9.4 Budgets

Recommended budget axes:

```text
max_gpu_kv_pages
max_memory_slots
max_soft_tokens
max_retrieved_raw_tokens
max_resume_latency_ms
max_nvme_read_mb
```

### 9.5 Status of the scoring function

The linear form with six free hyperparameters is a Phase-0 baseline, not a design commitment. The weights should be fit against the quality metrics in §20 (held-out long-thread evals), and the expected end state is a learned selector — plausibly trained jointly with the expansion gate (§17), since "which blocks to load" and "when loaded blocks are insufficient" are two halves of one sufficiency estimate.

---

## 10. Attention Integration Options

## 10.1 Option A: typed text

Simplest implementation: summary/retrieved/tool text enters as ordinary tokens through the existing chat template.

Pros:

- zero model changes — works with any off-the-shelf instruction model today;
- debug-friendly;
- degrades gracefully to ordinary prompting.

Cons:

- still consumes sequence length;
- cannot represent latent/compressed memory;
- per-token channel labels are bookkeeping-only (selector/provenance/GC) — the model does not see them.

v0.1 claimed Option A "requires model support for channel embeddings if not using special tokens." Corrected: Option A needs neither. The chat template *is* the textual channel mechanism (§4.2). Channel IDs in Option A exist purely on the runtime side.

## 10.2 Option B: soft memory slots

Compressed memory enters as continuous embeddings.

```text
MemoryBlock → adapter → z_1...z_m
```

Pros:

- fewer visible tokens;
- can represent non-linguistic state;
- good common target for different compilers.

Cons:

- requires runtime support for `input_embeds`;
- requires adapter training — this is where channel embeddings genuinely become necessary;
- position handling is delicate.

## 10.3 Option C: direct K/V banks

Memory enters as precomputed or decoded K/V.

```text
MemoryBlock → memory_KV
attention reads [recent_KV, memory_KV]
```

Pros:

- attention-native;
- best for persisted compacted KV;
- avoids embedding/prefill overhead.

Cons:

- runtime-specific;
- model/version compatibility is strict (§4.6 — these artifacts are cache-grade);
- position and RoPE handling must match exactly;
- subject to the eviction-fidelity constraints of §13 whenever the bank is a strict subset of originally-computed KV.

### Recommended implementation path

```text
Phase 1: typed text fallback        (no training)
Phase 2: compacted KV checkpoints   (no training; fidelity-gated)
Phase 3: soft memory slots          (adapter training begins)
Phase 4: direct multi-bank K/V      (trained compaction)
```

---

## 11. Disk-Backed Persistence

## 11.1 Storage tiers

```text
GPU VRAM   hot recent KV / active memory banks
CPU RAM    warm cache pages and page tables
NVMe mmap  compacted KV checkpoints and cold pages
Object     raw archive and rarely used blocks      ← only durable tier
```

## 11.2 Storage arithmetic (new in v0.2)

Per-token KV size:

```text
bytes/token = 2 (K and V) × n_layers × n_kv_heads × head_dim × bytes_per_elem
```

Representative numbers at bf16:

| Model class | Layers | KV heads | head_dim | KB/token | GB per 100k tokens |
|---|---:|---:|---:|---:|---:|
| 7B MHA (32 KV heads) | 32 | 32 | 128 | 512 | ~51 |
| 8B GQA (Llama-3-style) | 32 | 8 | 128 | 128 | ~12.8 |
| 7B GQA (Qwen2.5-style) | 28 | 4 | 128 | 56 | ~5.6 |
| MLA (DeepSeek-style) | per-layer latent (~576 dims) instead of K/V heads | | | ~5–70 depending on depth | layout differs entirely |

Implications:

- **Multi-tenant persistence of full KV (L4) is rarely economical.** A service with 10⁵ active long threads at 100k tokens each on a GQA-7B model is ~0.5 PB of cache-grade data with a TTL of one deployment cycle. L4 is for premium/debug paths only.
- **Compaction ratio is the budget lever.** L3 storage cost is (surviving fraction) × the table above; the spec's economics depend on aggressive eviction, which is exactly why §13's fidelity constraints matter.
- **Checkpoint cadence × KV size = NVMe write amplification.** Per-compaction checkpointing of a multi-GB KV state will burn NVMe endurance. Checkpoints should write **deltas against the parent checkpoint** (new/changed pages only — the page table makes this natural), with periodic full snapshots. The `checkpoint_policy` API field (§18.3) selects cadence; the default `on_compaction` policy must be delta-based.
- **GQA/MQA/MLA must be first-class in the page schema** (11.3). v0.1's example shape assumed MHA, which overstates costs 8–16× for modern models and does not describe MLA at all.

## 11.3 Page layout

Suggested KV page object, generalized:

```json
{
  "page_id": "kvp_01HZ...",
  "block_id": "mb_01HZ...",
  "layer": 17,
  "kv_layout": "mha | gqa | mqa | mla_latent",
  "n_kv_heads": 4,
  "head_dim": 128,
  "head_range": [0, 3],
  "token_range_physical": [2048, 2111],
  "token_range_logical": [12000, 12063],
  "dtype": "bf16",
  "shape": [2, 4, 64, 128],
  "storage_uri": "mmap://.../page_00017",
  "checksum": "sha256:..."
}
```

Where the leading dimension `2` represents `K` and `V` for `mha|gqa|mqa` layouts. For `mla_latent`, the page stores the per-layer compressed latent (plus decoupled RoPE key components) and `shape` follows the latent layout; the K/V-pair framing does not apply and `head_range` is null. Runtimes must reject pages whose `kv_layout` they cannot interpret — this is part of the compatibility gate, not a soft warning.

## 11.4 Resume hydration

```python
def hydrate_checkpoint(checkpoint_id):
    ckpt = load_checkpoint(checkpoint_id)
    validate_compatibility(ckpt)          # hard fail → fallback path (§7.4)

    page_table = mmap_load(ckpt.kv_page_table_uri)
    hot_pages = prefetch_recent_pages(page_table)
    memory_banks = map_memory_blocks(ckpt.memory_block_ids)

    return RuntimeState(
        page_table=page_table,
        hot_pages=hot_pages,
        memory_banks=memory_banks,
        positioning=ckpt.positioning
    )
```

## 11.5 Copy-on-write branching

For branching conversations:

```text
root checkpoint
  ├── branch A checkpoint
  └── branch B checkpoint
```

Use copy-on-write page references:

- old compacted pages are shared;
- only new divergent pages are written;
- garbage collection traces reachable checkpoints.

Delta-based checkpoints (11.2) and CoW branching share the same page-table mechanism.

## 11.6 Concurrent branches and join semantics (new in v0.2)

§11.5 assumes sequential branching: conversation forks that diverge and stay diverged. Parallel-reasoning decoding techniques (Appendix A: parallel reasoning via interleaved decoding) create a second branching mode: **concurrent branches within a single generation**, where one model decodes multiple reasoning branches per step into one sequence and one cache, and the branches later converge.

The fork half is already covered: concurrent branches are CoW references over the shared page table, identical to §11.5. Two things are new.

**Join.** When concurrent branches converge, the runtime needs merge semantics — which the sequential model never required. Options, in increasing fidelity:

```text
summary join     branches emit a fused summary; branch scratch becomes a
                 completed reasoning block → compact and evict (§14), keep
                 the join summary and its KV
selective join   one winning branch's pages are retained in the main line;
                 losing branches → compact-and-evict as above
full join        all branch pages retained (interleaved); main line
                 continues attending to everything — cheapest at join time,
                 defers the memory cost
```

Recommended default: summary join, because a joined parallel region is a *self-delimiting completed reasoning unit* — the cleanest compaction target in the system. This also resolves a gap in §7.2, where block-boundary detection is heuristic: fork/join markers are explicit segmentation signals, and runtimes supporting parallel decoding should prefer them over heuristics. For recurrent-state memory tiers (§16.4), summary join is not just preferred but effectively mandatory: recurrent states are cumulative and order-dependent, and no validated merge operator for two branch states exists.

**Interleaved-region pages.** A parallel-decoded region leaves branch tokens physically interleaved in the cache under a block-sparse attention mask, with token order decoupled from position indices. Compacting, persisting, or hydrating such a region is valid only if the mask and position metadata travel with the pages — this is precisely what `attention_metadata` (mask format + compaction map) in the checkpoint schema (§6.2) exists to carry, and interleaved regions are the concrete case that makes those fields load-bearing rather than speculative. A runtime that cannot interpret the recorded mask format must treat the region as opaque and fall back to re-prefill from the substrate.

## 11.7 Compute accounting (new in v0.3.5)

The spec accounts meticulously for bytes (§11.2) and fidelity (§13.4) but, before this section, not for FLOPs. The omission invites a correct critique: **most of this substrate's mechanisms buy memory capacity and bandwidth, not compute.** This section states where the compute goes, per mechanism, in the spec's own terms.

### 11.7.1 Three resources, two phases

Long-context inference binds on three resources at different phases:

```text
prefill   COMPUTE-bound: O(T²) attention + O(T) FFN over the prefix
decode    BANDWIDTH-bound: the live KV state streams past the compute
          units once per generated token; FLOPs are rarely the limiter
capacity  what bounds concurrent threads per device: live KV bytes
```

Every tier and regime in this spec attacks a specific vertex; none attacks all three. The per-mechanism ledger:

### 11.7.2 Per-mechanism ledger

```text
compaction event (§7.3, any compiler)
  pays:    summary generation or compactor forward at compaction time;
           if compaction runs AFTER a full prefill, first-turn compute is
           UNCHANGED OR INCREASED — structurally, post-prefill compaction
           cannot reduce the cost of the turn that triggers it
  buys:    every subsequent token attends over physical length K, not
           logical length T → decode attention FLOPs and KV bandwidth
           scale down by the compression ratio for the rest of the thread
  ledger:  an AMORTIZED INVESTMENT with horizon
              ≈ compaction_cost / ((T−K) · per-token attention cost)
           long-horizon threads amortize quickly; single-shot QA never
           amortizes and is compute-NEGATIVE under this substrate

chunked / iterative compaction (§8.4)
  the only evict-regime path that reduces PREFILL compute itself: each
  chunk prefills against a compact prefix (length N·t + c·t) instead of
  the full history, cutting the quadratic attention term by roughly the
  local ratio c. Bounded by max_certified_depth (§13.4).

deselect (§13.7)
  buys:    per-step decode attention FLOPs and bandwidth ∝ selected
           subset, not full cache
  pays:    indexer forward per step + prefetch machinery; and the full
           KV must still be PRODUCED — prefill compute unchanged, total
           storage unchanged. A within-session decode optimization only.

absorb (§16.4)
  buys:    constant per-token memory-path cost regardless of history —
           the best decode asymptotics in the spec; prefill chunks
           naturally
  pays:    one-off training compute (acquisition paths, §16.4); a small
           constant per-token update/read (~10² tokens' worth of
           attention)

untrained eviction (§13.3)
  the cheapest-compute regime: near-zero compaction cost, same decode
  savings as any compaction. It pays in FIDELITY rather than FLOPs,
  which is why it is certification-gated rather than compute-gated.

EXPAND (§17)
  every expansion re-injects raw tokens: prefill compute for the
  expanded span plus enlarged decode attention while it remains in
  context. AN OVER-FIRING GATE IS A COMPUTE REGRESSION CHANNEL — it
  silently converts the compression savings back into prefill. The
  always-expand baseline (§17.6) is exactly the ceiling of this
  regression; observed expand-rate belongs in the online risk report.

selector + gate (§9, §17)
  one small-encoder forward over a candidate set per turn (or per step,
  for deselect-style operation); shadows are computed once at compile
  time and amortized. Negligible against a single backbone token at 4B+
  scale. The classify-and-expand baseline costs ~zero compute.

offline certification (§13.4)
  a real line item, easy to forget: teacher passes require FULL-CONTEXT
  forward runs over the held-out set, at every (build × policy × depth)
  cell. Scales linearly in eval items × context length and re-runs on
  every fingerprint change. Online risk telemetry is cheap by design —
  that asymmetry is the point of the v0.3 split.
```

### 11.7.3 Store vs recompute at resume

Hydration is IO-bound; re-prefill is compute-bound. The decision is economic, not architectural:

```text
store wins when   resume_rate × prefill_cost($, latency)
                    >  storage_cost over the artifact's TTL (§4.6)
                       + checkpoint write cost

reference build (B.1, 32k thread):
  L3 @ 8×  ≈ 560 MiB  → hydrate ≈ 0.1 s off PCIe-4 NVMe, ~zero GPU
  re-prefill 32k       → seconds of GPU time, real marginal cost
  NVMe at research scale → effectively free
  ⇒ per-resume, the checkpoint wins on both latency and cost
```

The crossover is real at fleet scale: petabytes of TTL-bounded cache versus elastic recompute is a cost-engineering question, and "recompute, don't store" is the rational default for **cold threads** (low resume probability). Consequence: the §7.4 fallback path is not merely a safety path — it is the economically correct *primary* path for cold threads, and garbage collection should be resume-probability-aware rather than purely age-based.

### 11.7.4 Normative rules

```text
R1  compaction is an amortized investment: checkpoint_policy should be
    conditioned on expected thread longevity; never compact threads
    predicted to be single-shot
R2  only chunked/iterative compaction and absorption reduce prefill
    compute; post-prefill compaction never reduces first-turn cost —
    do not claim otherwise in any derived material
R3  expand-rate is a first-class online risk metric: the gate's compute
    regression is bounded by the always-expand baseline and must be
    monitored against it
R4  resume default: hydrate for warm threads, re-prefill from substrate
    for cold threads; GC keys on resume probability
R5  certification compute is part of a compaction policy's cost; a policy
    too expensive to re-certify on the deployment cadence (§4.6) is too
    expensive to operate
```

## 11.8 Branching and compression compose; one cell does not (new in v0.3.6)

A natural worry is that supporting both branching (parallel reasoning §11.6, CoW conversation forks §11.5, speculative decoding §11.7) and compression (§13's regimes) requires two separate architectures. It does not. They are **orthogonal concerns over one shared substrate**:

```text
compression   rewrites the CONTENTS of pages (many tokens → fewer)
branching     manipulates REFERENCES to pages (copy-on-write fork, join)
```

Contents and references are independent axes, so the operations compose in either order: a compacted page can be CoW-shared, and a forked branch can be compacted. This is one architecture — the MemoryBlock store plus a page table — carrying two operations, not a fork in the design. Orthogonality here is the enabling property, not an obstacle: independent concerns compose without combinatorial blowup.

The composition holds for every tier **except recurrent absorption (§16.4)**, and the reason is a concrete state property, not a preference. Branching requires cheap forking and merging of state. KV pages are random-access and additive, so they fork (share a reference) and merge (concatenate/select page sets) cheaply. A recurrent state is cumulative and order-dependent: it can be snapshotted but not split into coherent partial states, and it has no defined merge. The §11.6 recurrent-join caveat, the §16.4 join limitation, and the speculative-decoding non-forkability note (§11.7) are three surfacings of this one fact.

The structure is therefore a 2×2 with a single hostile cell:

```text
                    compress: KV pages       compress: recurrent state
  branch: yes       composes freely          NO cheap fork / merge
  branch: no        composes trivially       composes trivially
```

Resolution is a **routing rule, not a second architecture**:

```text
branchy workloads (parallel reasoning, speculative decoding,
  conversation trees)            → page-compressible tiers
                                    (evict / synthesize / deselect)
linear, long-horizon, low-branch  → recurrent absorption tier (§16.4)
```

Underlying principle: branching wants state that is **separable and addressable**; synthesis-style compression wants state that is **entangled and dense**. These pull in opposite directions, and recurrent absorption sits at the entangled extreme — the one tier where the two concerns stop composing. KV-page compression sits in the middle: entangled contents but still addressable pages, which is why it composes with branching while still buying real compression. That middle position is a substantive reason the page abstraction is this spec's load-bearing choice.

---

## 12. Position and RoPE Handling

Position metadata is a high-risk area.

### 12.1 Required distinction

```text
logical position: original position in full thread
physical position: compacted runtime position
segment-local position: position inside compressed block
RoPE offset: rotational embedding state used by model/runtime
```

### 12.2 Failure mode

A loaded KV tensor may have the right bytes but wrong meaning if its position metadata is wrong.

Example:

```text
K/V computed at logical position 15000
restored as if computed at position 3000
→ attention geometry shifts
→ continuation quality degrades
```

### 12.3 Position policy options

| Policy | Description | Pros | Cons |
|---|---|---|---|
| Preserve logical positions | keep original RoPE positions | high fidelity | large gaps / scaling concerns |
| Compact physical positions | remap to shorter sequence | efficient | requires trained compaction/masking |
| Segment-local positions | each block has local positions | good for chunks | needs block identity/bias |
| Relative memory positions | memory slots use relative scheme | flexible | model/runtime changes |

Recommended default for early prototypes:

```text
preserve exact runtime semantics of whichever compaction method generated the checkpoint.
Never reinterpret persisted KV under a different position policy.
```

### 12.4 Scope of the prohibition (new in v0.2)

The rule above is scoped to **persisted checkpoints crossing a session or build boundary**, where reinterpretation cannot be behaviorally validated. It does not forbid *runtime* position manipulation within a single build and session: parallel-reasoning decoding deliberately decouples token generation order from position indices and assigns branch slots under a custom mask, and this demonstrably works (Appendix A). The distinction:

```text
runtime, same build, same session   position remapping is a decoding
                                    technique; validated by construction
                                    against the live model

persisted, across sessions/builds   position reinterpretation is silent
                                    corruption risk; forbidden — record the
                                    scheme that produced the KV and restore
                                    under exactly that scheme
```

A region produced under a nonstandard position assignment (e.g., interleaved parallel decoding) may be persisted, but only with its full position map and mask metadata, and may only be hydrated under the same interpretation (§11.6).

**Implementation validation (new in v0.3.3).** The Still compactor (§8.1) independently converged on this section's machinery because the implementation forced it: synthesizing mixtures of already-rotated keys "mixes content with phase and is empirically unstable," so the compactor inverse-rotates keys into a position-free frame, compacts under its own internal RoPE, and re-rotates compact keys at chosen output positions; for continuation, the cache stores an explicit offset so new tokens receive RoPE phases as if the full original prefix were present — physical cache length and logical sequence length deliberately decoupled. That is this spec's `physical_position` / `logical_position` / `rope_base_offset` triple, discovered from engineering necessity rather than design.

---

## 13. Eviction Fidelity and Attention Renormalization (new in v0.2)

This section makes explicit a constraint that v0.1 left implicit and that governs the entire L2–L3 design: **evicting KV is not a neutral operation even when every surviving byte is correct.**

### 13.1 Two mechanisms of degradation

**Softmax renormalization.** Every future query's attention distribution is normalized over the set of surviving keys. Removing a span's KV redistributes that span's attention mass over everything that remains. Tokens that previously attended 30% to the evicted span now spread that mass elsewhere — including onto the summary KV, in proportions the model was never trained to expect.

**Stale survivors.** The surviving KV (including the summary's induced KV) was computed *in the presence of* the evicted span. Under causal attention, the summary tokens attended to the span while being encoded; their K/V vectors partially encode it. After eviction, future tokens attend to representations of a context that no longer exists in the cache. This is, in fact, why summary-KV retention works at all — the summary KV smuggles span information forward — but it is an uncontracted, untrained channel for an off-the-shelf model.

### 13.2 Attention sinks

Empirically, autoregressive Transformers dump large amounts of attention mass onto the first few sequence positions regardless of content (the "attention sink" phenomenon identified in streaming-attention research). Evicting those positions destabilizes generation outright, far beyond gradual quality loss.

**Requirement:** the first *k* token positions of a thread (k≈4, tunable per model) are pinned and never evictable. The checkpoint records them (`sink_tokens_retained`, §6.2), the compactor asserts against them (§7.3), and hydration restores them before any other page. Implementations should additionally support pinning high-attention-mass anchors identified at runtime. Base models pretrained with architectural sink mitigations reduce this requirement to a single known slot — see §13.6 for the options and the recommended model criterion.

### 13.3 Trained vs untrained compaction

The fidelity of compacted continuation falls into two regimes:

```text
trained compaction    model was trained/fine-tuned to continue from
                      compacted state (gist-style compression tokens,
                      beacon-style condensing, learned KV merging)
                      → fidelity is a property of training; can be high
                        and is characterized on the training distribution

amortized-producer    frozen model + compactor TRAINED to synthesize
compaction            compact KV the frozen model reads well (Still-class,
                      §8.1) — the training contract is one-sided: the
                      producer adapts to the consumer; backbone untouched.
                      Fidelity is trained but bounded by the producer's
                      training distribution (context lengths, domains,
                      recurrence depth — §13.4) and by bounded exact
                      recall (§17.1)

untrained eviction    off-the-shelf model + heuristic eviction
                      (recency, attention-mass, redundancy scoring)
                      → fidelity is purely empirical, degrades with
                        eviction fraction, and varies by model and task
```

Phases 1–2 of this spec operate in the untrained regime by design (no training required). The consequence is procedural: **no untrained-eviction configuration may be promoted to the default resume path without passing the fidelity gate below.** v0.1's labeling of L3 as "high fidelity" was an assertion without a mechanism; v0.2 replaces it with a measurement requirement.

### 13.4 Fidelity gate

Every (model build, compaction policy, eviction fraction) configuration must be characterized before production use. v0.3 splits the fidelity gate into an expensive **offline certification** and a lightweight **online risk report**.

**Offline certification** is the only place that requires a full-context reference:

```text
protocol:
  1. sample held-out long threads from the target distribution
  2. for each, compute next-token distributions under
       a) full context (reference)
       b) compacted state (candidate)
  3. report:
       mean KL(a || b) over continuation windows
       answer accuracy delta on span-grounded QA probes
       lost-fact incident rate (facts in evicted span, probed later,
         answered wrongly WITHOUT an EXPAND call — the silent failure)
       gate-utilization probes for recurrent/absorptive models (§16.4)
  4. report the two workload axes (§4.7) SEPARATELY and never as a
     blended score:
       aggregation axis  = KL + answer-accuracy delta on integrative probes
       pointwise axis    = needle / lost-fact instrument
     a configuration is certified per-axis; shipping a configuration
     certified only on the aggregation axis requires the expansion gate
     to be active and calibrated (§17) for pointwise traffic
  5. gate: configuration ships only if all metrics are within budget
  6. for trained compactors used iteratively: certify AT THE DEPLOYMENT
     RECURRENCE DEPTH and emit max_certified_depth. Validity does not
     extrapolate past trained depth: an 8k-horizon Still compactor
     stacked 128 times (128k) collapses to 1.5% — BELOW the no-context
     floor — despite retaining MORE cache than a 32k-horizon compactor
     (17,408 vs 8,192 slots); the binding variable is training-time
     recurrence depth, not budget. Post-hoc calibration that holds
     single-pass can miscalibrate under recurrence (Still §M.2).
     Resume paths must refuse to stack compactions beyond
     max_certified_depth and fall back to the substrate.
  7. for trained compactors, run the pre-training diagnostics (below)
     and attach their records to the certification
  8. emit an offline_certification_id bound to the compatibility_fingerprint,
     compaction policy, eviction fraction, max_certified_depth where
     applicable, and eval suite version
```

**Trained-compactor pre-training diagnostics (v0.3.7, measured).** A
compactor can optimize its loss while never learning to route — the loss
curve lies. Two cheap checks are therefore mandatory: (1) *gradient
forensics at init* — per-parameter-group gradient norms on one
forward/backward; routing projections (W_Q, W_K) sitting 10–12
orders of magnitude below the value pathway indicates logit-scale-induced
softmax saturation (observed under the canonical d_l logit scale at
identity init; resolved by √d_l or a learned temperature). (2)
*Cross-attention entropy telemetry during training* — entropy pinned at
the numerical floor with a bitwise-static argmax kernel means the
artifact is a positional subsampler regardless of its loss, and must be
certified as such.

**Online risk report** is cheap checkpoint metadata, not a synchronous teacher comparison:

```text
checkpoint metadata:
  offline_certification_id
  online_risk_estimate
  sampled_probe_count
  lost_fact_risk_estimate
  observed_expand_rate
  fallback_count_since_checkpoint
```

The online estimate may use small probes, selector/gate confidence, loss estimates, and production telemetry. It must not pretend to be a full-context KL measurement unless a full teacher run actually happened.

### 13.5 Design consequences

- Eviction fraction is a quality dial, not a free win; the storage economics of §11.2 must be read jointly with this section.
- The EXPAND mechanism (§17) is the safety valve for fidelity loss — but only if the expansion gate is calibrated, which is why §17 is first-class.
- Trained compaction (Phase 4+) is the long-term answer; the untrained phases are scaffolding with measured, bounded loss.
- The most principled trained-compaction mechanism is **recurrent absorption** — folding evicted spans into a fixed-size recurrent state rather than deleting them (§16.4) — which makes the post-eviction regime the training regime rather than a corruption of it.

### 13.6 Architectural mitigations at the base-model level (implementation note)

The sink phenomenon (§13.2) and, partially, the renormalization problem (§13.1) can be addressed at the attention-mechanism level. These mitigations are **base-model choices**, not substrate mechanisms. They belong in model-selection notes and Appendix A, while the normative runtime requirement remains simple:

```text
for arbitrary frozen models:
  pin sink tokens
  treat eviction fidelity as empirical
  pass the fidelity gate
```

Candidate mitigations:

| Mitigation | Mechanism | Fixes sinks | Fixes renorm (§13.1) | Status in this spec |
|---|---|---|---|---|
| Off-by-one softmax (softmax₁) | +1 in softmax denominator ≡ phantom key with fixed logit 0, zero value | yes | no | base-model option; not a runtime fix |
| Learnable per-head sink logits | phantom key with learned logit per head, no value vector | yes | no | preferred criterion when selecting a compatible base model; verify implementation claims per model |
| Explicit sink/register tokens | trainable always-visible token(s) heads can park mass on | yes | no | viable but may create content/outlier hotspots |
| Gated attention | sigmoid gate on attention output gives heads an off-switch | yes at the causal level | no | useful watchlist item; not assumed by the substrate |
| Sigmoid / unnormalized attention | independent per-key scoring, no normalization, no competition between keys | by construction | yes | research-grade; would simplify §13.1 if adopted |

Every row except unnormalized attention still operates inside softmax: evicting real keys still redistributes their mass. Therefore these mitigations reduce catastrophic sink-eviction failures but do not remove the fidelity gate. **Measured (v0.3.7):** the sink phenomenon doubles as a sensor — anomalous sink mass plus depressed memory-region mass on a handful of late-layer heads predicts insufficiency at 0.74–0.79 AUC across every compression regime tested (eviction, frozen subsampling, content-routed synthesis), with zero-shot transfer between regimes; this is the recommended cheap tier of the expansion-gate ladder (§17.5).

Rationale for the per-head sink-logit preference (restored in v0.3.1): the abstain threshold is learned independently per head and layer rather than fixed globally (vs. softmax₁); the sink carries no value vector, so it cannot become a content/outlier hotspot (vs. register tokens); and it requires no change to the attention operator itself (vs. gating or sigmoid attention), which leaves the substrate's KV page, masking, and position machinery untouched. On such models, the §13.2 pinning requirement reduces to preserving one known, special-cased slot. Production-scale precedents exist in the gpt-oss lineage (learned sink logits, with native FlashAttention support) and the Qwen3-Next lineage (gated attention) [citation_needed]; these claims reflect literature as of early 2026 and must be re-verified per model before formal citation.

### 13.7 Three regimes for old KV: evict, absorb, deselect (restored in v0.3.1)

The spec distinguishes three strategies for KV that has left the recent window:

```text
evict      delete KV permanently         lossy, irreversible, renorm risk
                                         (§13.1–13.4; Phases 1–2)

absorb     fold KV into a fixed-size     lossy, but the post-compaction
           recurrent state               regime is the TRAINING regime
                                         (§16.4; Phase 4)

deselect   retain all KV (offloaded),    non-destructive and cache-
           load only query-critical      reversible per step; a chunk
           chunks per decoding step      skipped this step is recoverable
                                         next step, but logit fidelity
                                         depends on the sparse-attention /
                                         indexer training regime
                                         (sparse attention + offload;
                                          Appendix A)
```

Deselection — the strategy of the MLA/NSA/DSA lineage and its derivatives — sidesteps §13.1 differently than absorption: each step still renormalizes over its selected subset, but selection is query-adaptive and cache-reversible, so no K/V bytes are destroyed even though logits can still differ from full dense attention if the selection policy is imperfect. It is in effect a continuous, attention-granularity EXPAND in which the learned indexer plays the role of the §17 gate at every step.

Scope limits, so the three regimes are not conflated: deselection reduces the **GPU-resident** footprint only — the full KV still exists offloaded, so §11.2 total-storage economics are unchanged and every artifact remains cache-grade under §4.6, session- and build-bound, with no provenance or cross-session story. It is a within-session serving pattern *inside* the substrate, not a substitute for it. It is also only available when the backbone was trained (or architected) for sparse attention; for arbitrary frozen dense models, bolted-on training-free selection degrades at aggressive sparsity, and the evict/absorb machinery of this section remains the operative regime. Implementation tiers and the system lineage are in Appendix A.

The transferable result for this spec is the **decoupled training of the decision layer**: see §17.5.

---

## 14. Memento-Style Integration

### 14.1 Goal

Compress completed generated reasoning blocks while preserving a continuation state.

### 14.2 Preferred runtime behavior

```text
1. Model generates reasoning block.
2. Model or runtime produces compact summary/memento.
3. Runtime marks old block as evictable (sinks excluded; §13.2).
4. Runtime keeps summary tokens and their induced KV.
5. Runtime evicts old block KV.
6. Runtime creates MemoryBlock for compacted summary/KV state.
7. Runtime samples a fidelity measurement (§13.4).
```

### 14.3 Fidelity caveat (new in v0.2)

Step 4–5's "keep summary KV, drop span KV" pattern works to the degree that the summary KV carries the span forward (§13.1) — which is uncontracted behavior for an off-the-shelf model. Expect:

- gradual degradation that grows with the evicted fraction and with how much later reasoning depends on *non-summarized* details of the span;
- the silent-failure mode: the model answers from the lossy summary with full confidence instead of calling EXPAND. The lost-fact incident rate (§13.4) is the metric that catches this.

A model lightly fine-tuned on (summary-KV-only → continuation) data moves this from heuristic to trained compaction and should be the first training investment after Phase 3.

### 14.4 Avoiding token soup

Early training may use special delimiters. Final runtime should move boundaries into metadata:

```text
span metadata:
  compressible = true
  summary_span = [a,b]
  evict_span = [c,d]
```

The model should learn:

```text
write compact memento when useful
```

not:

```text
manage every low-level cache delimiter manually
```

---

## 15. Latent Context Compression Integration

### 15.1 Goal

Compress old static or semi-static context **before** decoder prefill.

### 15.2 Flow

```text
raw chunk of N tokens
    ↓ encoder
one or more latent vectors
    ↓ adapter
soft memory slots or decoder-compatible latent tokens
    ↓ decoder prefill/generation
```

### 15.3 Use cases

- long documents;
- old conversation turns;
- tool logs;
- retrieved corpora;
- stable background context.

### 15.4 Exact expansion

Each latent block must point to raw source:

```text
latent block mb_17
  source_uri = raw://thread/segment/17
```

When exact recall is needed:

```text
EXPAND(mb_17)
```

Runtime injects raw text through `RETRIEVED_EXACT` channel. The decision of *when* to expand is governed by §17.

---

## 16. State-Vector / Memory-Slot Integration

### 16.1 Avoid single-vector collapse

A single last-token hidden state is generally insufficient. Preferred representation:

```text
M_t = {s_1, s_2, ..., s_r}
```

where `r` is a small number of memory states/slots.

### 16.2 State-to-KV decoder

Optional adapter:

\[
S_t \rightarrow (\hat K^{(l)}_{mem}, \hat V^{(l)}_{mem})_{l=1}^{L}
\]

The decoder attends over:

```text
recent exact KV + generated memory KV
```

### 16.3 Training target

Do not train only to reconstruct raw K/V. Train to preserve next-token behavior:

\[
\mathcal{L} = KL(p_{full\_KV} \,\|\, p_{state\_memory})
\]

Optional auxiliary losses:

- attention output matching;
- hidden-state matching;
- retrieval task accuracy;
- expansion decision accuracy (see §17).

### 16.4 Recurrent absorption memory (new in v0.2)

The strongest realization of this section is a **recurrent memory block** in the model itself: evicted spans are folded into a fixed-size recurrent state instead of deleted. Lineage: Compressive Transformer → Infini-attention (per-head associative matrix updated with old KV segments, read by query, mixed with local attention through a learned gate) → Titans (deep memory module with surprise-based online updates); SSM/attention hybrids (Mamba-class blocks interleaved with attention layers) bake the same mechanism into the layer stack.

**Relationship to §13.** Absorption converts eviction from corruption into the training regime: the attention mass that previously went to an evicted span has a contracted destination — the memory read path — and the model is trained with exactly that structure. Note the precise claim: the local softmax still renormalizes over surviving keys (the memory contribution is gated in outside the softmax); the fix is the **training contract**, not the recurrence itself. This is the most principled instantiation of trained compaction (§13.3) and the recommended Phase 4 mechanism. It does not remove the sink requirement (§13.2, §13.6) for the local window.

**State as checkpoint artifact.** The recurrent state is a dramatically better persistence object than KV pages:

```text
size        O(d_k × d_v) per head per layer, constant in context length
            e.g. 32 layers × 32 heads × 128×128 @ bf16 ≈ 33 MB total —
            a few hundred tokens' worth of KV, for unbounded history
position    position-free; most of §12 does not apply
branching   CoW snapshot of the state at fork points is trivial and cheap
durability  cache-grade, MORE model-bound than KV: the state is meaningful
            only to the weights that learned the write/read rule (§4.6)
```

The corresponding limitation: the state is **cumulative, order-dependent, and opaque**. It does not decompose into pages — no token-granular reuse, no radix-style partial prefix sharing, no mid-state eviction; the §11 page machinery is replaced by whole-state snapshots for this tier (exact-prefix state caching still works). Branch **join** (§11.6) is harder than for pages: merging two branch states is ill-defined — candidate operators (sum, learned merge) are unvalidated — so summary join is effectively mandatory for recurrent-tier branches. Serving support for hybrid-state models exists (Jamba-class in mainstream runtimes) but is years less mature than KV paging.

**Cost model.**

```text
inference   per-token memory update/read ≈ attending to ~10^2 extra tokens;
            negligible against any practical local window. Long-context
            throughput improves (bounded local attention). Prefill stays
            parallel: segment-level recurrence (Infini-style) or
            chunked-parallel scans with mature kernels (Mamba2/GLA/DeltaNet
            line). Titans-style deep memory ≈ 2–3× the update cost with
            far less kernel maturity.

training    see acquisition paths below; per-token cost of hybrid
            architectures ≈ pure transformer or slightly below.
```

**Acquisition paths**, in increasing cost:

```text
path 1   SELECT  use a base model that ships a recurrent/linear block
                 (Gated-DeltaNet hybrids, Jamba-class, RWKV-class).
                 Zero training; kernels and serving come free.
                 → recommended default, same logic as §13.6: select for
                   the property, don't build it. Note Gated-DeltaNet
                   hybrids also satisfy the §13.6 gated-attention row.

path 2   RETROFIT  linearization/distillation of a pretrained transformer
                 (attention-transfer + LoRA, or distillation into SSM
                 blocks); small parameter budget, 10^7–10^9 tokens,
                 single-node scale at 1–8B. Bolt-on continual pretraining
                 of the memory path (Infini-style) is the same tier.

path 3   PRETRAIN  from-scratch hybrid; no architecture cost premium, but
                 useful scale requires cluster-class compute. Relevant
                 only for research-scale instrumentation models.
```

**Two failure modes specific to the retrofit path** (recorded from the replication literature [citation_needed]; verify before formal citation):

- **Gate collapse.** The local-vs-memory gate receives gradient only from dependencies that span beyond the local window. Trained on ordinary-length data, the gate collapses to local-only and the memory module is architecturally present but functionally dead. The dominant cost of path 2 is curating genuinely long-range-dependent training data, not compute. The fidelity gate (§13.4) must include a gate-utilization probe to detect this.
- **Recall gap.** A linear-attention state is a bounded associative store; exact-detail recall (numbers, identifiers, verbatim spans) degrades measurably versus full attention. This is acceptable **only because EXPAND exists** — and it raises the stakes on §17, because absorption fails smoothly and silently, making under-expansion harder to notice, not easier. Recurrent-tier deployments must report lost-fact incident rate (§13.4) against a full-attention baseline.

---

## 17. The Expansion Decision

`EXPAND(block_id)` is the calibrated escape hatch from lossy memory. The runtime mechanics are straightforward — fetch the raw source span and inject it through the retrieved-exact channel — but the **decision** is hard: knowing when compressed memory is insufficient for the current query.

### 17.1 Failure asymmetry

```text
over-expansion    model expands when compressed memory was sufficient
                  → cost failure: wasted tokens, latency, lost compression win
                  → visible and bounded

under-expansion   model answers from lossy memory as if it were exact
                  → correctness failure: confident confabulation of details
                    that were present in the evicted span
                  → invisible at generation time; worst failure mode
```

Because costs are asymmetric and the bad case is silent, the gate must be **calibrated**, not merely accurate: its expansion probability should track the true probability that compressed memory is insufficient.

**Empirical anchor (new in v0.3.3).** The Still results quantify exactly this failure profile for trained compaction: under iterative compaction at 32k, the compact cache holds 90.0% on common-word extraction while single- and multi-key needle retrieval collapse to 6.7% and 3.3% (0.0% at 64k) — broad semantic evidence preserved, exact strings unrecoverable, with no signal at generation time distinguishing the two. The paper's own scoping ("this does not establish arbitrary open-ended generation or exact recall") is this section's premise stated from the compressor side: a calibrated expansion gate is structurally mandatory for synthesis-based compaction, not an optimization. Needle-style probes over evicted spans are accordingly the canonical lost-fact instrument (§13.4).

### 17.2 Runtime/model contract

There are two supported EXPAND modes.

```text
A. Runtime-gated automatic expansion (default)
   - the model does not see arbitrary block IDs;
   - selector + expansion gate choose candidate blocks;
   - runtime injects exact retrieved text before or during answering;
   - best for production and normal chat.

B. Model-visible expansion (debug/research)
   - runtime exposes a small candidate inventory:
       block_id, short gloss, source kind, time range, confidence/loss estimate;
   - model may call EXPAND(block_id);
   - useful for agentic workflows and for collecting gate-training data.
```

The default path is A. Path B is optional and should expose only a small, selector-filtered candidate list to avoid making block IDs part of the normal language protocol.

### 17.3 What sufficiency means

A block's compressed representation is sufficient for query *q* iff the model's answer conditioned on compressed memory plus recent context is equivalent to its answer conditioned on the raw span plus recent context:

```text
answer(q | M_compressed, recent_context) ≡ answer(q | R_raw, recent_context)
```

This is checkable offline and gives a direct supervision signal.

### 17.4 Answer-equivalence function

The symbol `≡` must be task-specific. v0.2 left this implicit; v0.3 makes it part of the training contract.

| Task type | Equivalence test |
|---|---|
| Exact factual answer | normalized exact match, alias table, numeric tolerance |
| Multi-fact answer | set overlap with required facts; all critical facts must match |
| Open-ended explanation | entailment/judge model with calibrated confidence and contradiction check |
| Code/debug answer | tests, static assertions, or structured expected output |
| Citation-grounded answer | same supporting span or provenance-equivalent source |
| Safety/policy answer | stricter contradiction-sensitive judge; no equivalence by style alone |

Noisy equivalence labels poison the gate: paraphrases may be marked insufficient, or subtly wrong answers may be marked sufficient. The equivalence function should therefore be versioned and recorded with the training/evaluation data.

### 17.5 Training signal

```text
construct triplets (q, M_compressed, R_raw) from held-out threads:
  1. answer q under M_compressed              → a_c
  2. answer q under R_raw                     → a_r
  3. evaluate equivalence under eq_policy_vN  → eq(a_c, a_r)
  4. label y = not eq(a_c, a_r)               (insufficient → should expand)

train the gate on (q, selected block shadows, loss_estimates, recent state) → y
```

Gate implementations, in increasing ambition:

```text
a) external classifier over (query embedding, block shadow, loss_estimate)
b) prompted self-check by the base model (cheap, poorly calibrated)
c) trained head on the model's hidden state at answer time —
   an answerability/abstention head over compressed memory
```

Option (c) is plausibly trainable jointly with the selector (§9.5), since block selection and expansion are two stages of one sufficiency estimate.

**Measured results (v0.3.7).** The 2026-07 campaigns established: (i)
the counterfactual, query-relative definition of sufficiency in §17.3 is
empirically confirmed — with the query absent, no probe (linear or MLP,
across a six-layer sweep or their concatenation) recovers a sufficiency
signal from the model's state over compressed memory (max AUC 0.508 vs
0.813 query-conditioned); sufficiency is a property of (query, memory)
pairs, not of memory states. (ii) Gate signal class is regime-dependent:
text-shadow gates suffice under eviction (mechanics-driven), go blind
under learned compaction, while hidden-state probes read divergence at
0.80–0.86 across regimes (retrained per policy — the best read-out
layer moves with the compressor); the sink-head monitor (§13.6) is the
regime-general cheap tier. (iii) The text-shadow gate's marginal
silent-loss reduction falls monotonically as compressor quality rises
and reaches **zero** at the best certified configuration
(72% → 22.5% → 9.0% → 0% across four compressor generations); the
§13.4 mandatory-gate rule still attaches formally (pointwise loss stays
above the noise floor), but at that point only the hidden-state tier
retains routing power — it matches never-expand cheaply and can push
below it — so the routing layer for certified synthesis configurations
is the probe stack, not the text-shadow gate. (iv) Fragility (which
facts a compressor loses) is largely content-intrinsic: failure sets
shrink roughly monotonically and nested as compressors improve, even
across a kernel-class change (nesting 0.78–0.94; κ 0.745 across
same-kernel reseeds, 0.28–0.42 across regimes with the drop mostly
marginal-driven), with a real minority (~9–21%) of regime-specific
failures. Gate labels and calibration still do not survive a
compaction-policy change (base rates and the novel-failure minority
both move) — §4.6 invalidation extends to the decision layer's
training data, not only to cache artifacts.

**Decoupled training of option (a) — the recommended starting point (restored in v0.3.1).** Recent sparse-attention serving work [citation_needed] demonstrates that the decision layer can be trained entirely **without loading the backbone**: the indexer/gate is formulated as a standard dual-encoder retrieval model — one encoder over the query/recent state, one over block embedding shadows — and trained with ordinary contrastive retrieval frameworks at single-node cost (FlashMemory-class systems, Appendix A; days-old at time of writing — verify before citation). The recipe:

```text
architecture   dual encoder: f(query state) · g(block embedding shadow)
               scores both selection (§9) and expansion-need (this section)

features       query workload type (pointwise vs aggregative, §4.7) is
               likely the single most predictive input for the expansion
               decision and should be available to the gate — either
               implicitly via the query encoder or as an explicit
               auxiliary classification head

supervision    two compatible sources:
                 1. counterfactual labels from the §17.5 triplet
                    construction above, under a versioned eq_policy
                    (§17.4) — exact but requires running the backbone
                    offline per triplet
                 2. teacher attention statistics: run the backbone offline
                    over held-out threads once, dump per-chunk attention
                    mass, train the encoder to predict it — cheaper per
                    label, noisier signal; useful for pretraining the
                    encoder before fine-tuning on counterfactual labels

cost           backbone used only offline for label generation;
               gate training itself is sentence-transformers-tier —
               single node, well within small-lab resources

payoff         one trained model serves as the learned selector (§9.5)
               and the expansion gate (a); calibration is then measured
               and corrected per §17.6 (the dual-encoder gives scores,
               not calibrated probabilities — temperature-scale or
               isotonic-fit on held-out triplets before deployment)

invalidation   the gate is trained over embedding shadows and therefore
               inherits their versioning (§6.1): a change of embedding
               model or shadow policy invalidates the gate's calibration
               and requires retraining or at minimum recalibration
```

This makes the decision layer the **cheapest trainable component in the system** — train it early (Phase 3, before any backbone-touching work), both for its own value and to generate the calibration data §17.6 requires.

### 17.6 Evaluation protocol

```text
required metrics:
  expansion precision   of the EXPAND calls made, fraction that were needed
  expansion recall      of the cases where expansion was needed, fraction
                        where EXPAND was called
  calibration           ECE / reliability curve of gate probability vs
                        empirical insufficiency rate
  lost-fact incident    facts in evicted spans, probed later, answered
                        wrongly without expansion (§13.4)
  budget exhaustion     cases where the gate wanted expansion but budget
                        prevented it, reported separately from success

required baselines:
  never-expand          lower bound; measures raw compression damage
  always-expand         upper bound on correctness; measures cost ceiling
  classify-and-expand   cheap interpretable baseline (§4.7): classify the
                        query as pointwise vs aggregative, expand iff
                        pointwise — the trained gate must beat this to
                        justify its existence
  oracle-expand         expand exactly when y=1; the target frontier

evaluation mix: include multi-hop retrieval-then-integration items
explicitly (§4.7's middle of the spectrum); report them as their own
slice, since they stress gate recall and post-expansion aggregation
jointly and are predictably the weakest cell

a gate is production-ready when it sits near the oracle frontier on the
cost/correctness plane, with calibration error within budget
```

### 17.7 Budgeting

EXPAND consumes `max_retrieved_raw_tokens` from the selector budget (§9.4). The gate must be budget-aware: under tight budgets it should prioritize expansions by expected answer impact, and the runtime must surface budget exhaustion to the model so it can hedge rather than silently dropping the expansion.

---

## 18. Public Runtime API Sketch

### 18.1 Create thread

```http
POST /threads
```

```json
{
  "model": "model-id",
  "memory_profile": "balanced | exact | low_ram | research",
  "channel_registry": "memchan-v1"
}
```

### 18.2 Append message

```http
POST /threads/{thread_id}/messages
```

```json
{
  "role": "user",
  "content": "Can we resume the compacted KV checkpoint?",
  "attachments": []
}
```

### 18.3 Generate

```http
POST /threads/{thread_id}/generate
```

```json
{
  "max_tokens": 2048,
  "checkpoint_policy": "periodic | on_compaction | manual",
  "checkpoint_mode": "delta | full_snapshot",
  "memory_budget": {
    "max_gpu_kv_mb": 4096,
    "max_memory_slots": 256,
    "max_retrieved_tokens": 8192,
    "max_resume_latency_ms": 500
  }
}
```

### 18.4 Resume

```http
POST /threads/{thread_id}/resume
```

```json
{
  "checkpoint_id": "latest",
  "fallback": "latent_prefill | summary_prefill | full_prefill"
}
```

### 18.5 Expand

```http
POST /threads/{thread_id}/memory/{block_id}/expand
```

```json
{
  "token_budget": 4096,
  "reason": "Need exact numeric detail from prior block"
}
```

### 18.6 Branch

```http
POST /threads/{thread_id}/branch
```

```json
{
  "from_checkpoint_id": "ckpt_01HZ...",
  "branch_name": "alternative-design"
}
```

---

## 19. Security and Integrity

### 19.1 Never accept user-supplied KV as trusted state

KV/state checkpoints must be produced by the trusted runtime. User-provided hidden states or KV tensors are not safe to inject.

Risks:

- model hijacking;
- prompt-injection encoded in latent form;
- corrupted attention state;
- data exfiltration;
- cross-user leakage.

### 19.2 Provenance is mandatory

Every memory block must record:

```text
source URI
source hash
trust level
creator
model/runtime version
```

### 19.3 Memory channels should preserve trust boundaries

For example:

```text
SYSTEM memory       high trust
USER memory         user trust
TOOL memory         tool-specific trust
EXTERNAL retrieval  untrusted until validated
```

The model/runtime can apply channel-specific attention bias, filtering, or quoting rules. Note that channel-bias-as-trust-enforcement is unproven; until validated, trust enforcement should rely on runtime-side filtering of what enters the context, not on the model attending less to low-trust channels.

### 19.4 Encryption and isolation

Persistent KV/state may contain sensitive content not visible in text. Treat it as user data:

- encrypt at rest;
- isolate per tenant/user/thread;
- sign checkpoints;
- garbage collect deleted threads (including all cache-grade representations and embedding shadows — deletion must trace the full derivation graph via `derived_from`);
- prevent cross-model accidental loading.

### 19.5 Latent memory governance is a deployment blocker, not an open question

v0.1 listed "how do we inspect, redact, and govern non-textual memory" among open research questions. For multi-tenant production it is stronger than that: soft slots and state vectors **cannot currently be moderated, audited, or selectively redacted**, because their information content is not inspectable. Consequences for this spec:

- Phases 0–3 (text + KV-of-text tiers) are deployable under standard data-governance regimes, because every cache artifact is derived from inspectable text with recorded provenance and can be redacted by deleting the artifact and re-deriving from redacted text.
- Phases 4–6 (soft slots, latent blocks, adaptive state) are **research-grade until a latent-inspection or redaction-by-reconstruction story exists**. Minimum bar for production: (a) every latent block's primary text representation is the unit of moderation, (b) redaction of a source span hard-invalidates every derived latent artifact via the provenance graph, and (c) latent artifacts never outlive their source's retention window.

This constraint is recorded here rather than in §22 so it is read as a gate on the roadmap, not as future work.

---

## 20. Observability and Evaluation

### 20.1 Runtime metrics

```text
prefill_tokens_saved
kv_bytes_gpu
kv_bytes_cpu
kv_bytes_nvme
checkpoint_write_latency
checkpoint_restore_latency
checkpoint_delta_size
nvme_write_amplification
cache_hit_rate
page_fault_rate
tokens_per_second
memory_blocks_selected
expand_calls_per_1k_tokens
observed_expand_rate_vs_always_expand_ceiling   (§11.7 R3)
compaction_compute_seconds_per_thread
certification_compute_hours_per_policy          (§11.7)
```

### 20.2 Quality metrics

```text
next-token KL vs full-context baseline        (per §13.4 fidelity gate)
answer exact-match on retrieval tasks
long-range reasoning accuracy
summary drift rate
consolidation depth vs accuracy curve         (§8.4)
expansion precision/recall                    (per §17.4 protocol)
expansion gate calibration (ECE)              (per §17.4)
lost-fact incident rate                       (the silent-failure metric)
branch resume consistency
```

### 20.3 Debug views

Recommended developer tools:

```text
memory timeline
block provenance viewer (derived_from / supersedes graph)
attention-over-memory heatmap
checkpoint diff tool
expand-call trace with gate probabilities
position-map inspector
fidelity-report dashboard per (model build × compaction policy)
```

---

## 21. Implementation Phases

v0.3 separates the deployable MVP core from research extensions. This prevents the document from reading as if soft slots, latent compression, recurrent absorption, and adaptive state caching are all required for the first system.

### 21.1 MVP core: Phases 0-3

#### Phase 0 — Text-only baseline

```text
raw transcript archive
+ summaries
+ mandatory raw indexer (shadows + pointers)
+ normal re-prefill on resume
```

Purpose:

- establish the durable substrate;
- test segmentation and summaries;
- no runtime KV injection required.

#### Phase 1 — Memento-like compaction

```text
summary generation
+ evict old reasoning blocks (sinks pinned)
+ keep compacted summary path
+ offline fidelity certification stood up (§13.4)
```

Purpose:

- reduce active KV length;
- introduce compaction metadata;
- characterize untrained-eviction quality per model.

#### Phase 2 — Disk-backed compacted KV checkpoints

```text
persist compacted surviving KV (delta-based)
+ mmap/NVMe restore
+ compatibility_fingerprint checks and invalidation-on-migration
+ online checkpoint risk metadata
```

Purpose:

- fast resume;
- cached, not durable, thread state.

#### Phase 3 — Unified MemoryBlock IR

```text
all summaries/KV/checkpoints/retrieval chunks represented as MemoryBlocks
+ selector
+ expansion gate v1: decoupled dual-encoder over block shadows,
  trained per §17.5 (backbone used offline for labels only)
+ consolidation passes (§8.4)
```

Purpose:

- avoid one-off integrations;
- enable branch/copy-on-write semantics;
- get expansion calibration data flowing before any model training.

#### Phase 3.5 — Amortized KV compactor (new in v0.3.3)

```text
train a Still-class per-layer compactor against the frozen base (§8.1)
+ forward-KL objective vs full-context teacher (§8.3)
+ offline certification incl. recurrence depth (§13.4)
+ compactor hash + max_certified_depth into compaction_policy_version
```

Purpose: trained compaction quality without touching the backbone — compactor-only training at single-node cost. Sits between the MVP core and the research extensions because it trains a module but not the model; deployable under the same governance regime as Phases 0–3 (the compact cache is derived from inspectable text with recorded provenance). Reference build: Appendix B.

### 21.2 Research extensions: Phases 4-6

These phases require adapter/model training and are gated by latent-memory governance (§19.5).

#### Phase 4 — Soft memory slots

```text
MemoryBlock → adapter → soft slots
+ channel embeddings (first point where they are required)
+ KL training vs full context
+ trained expansion head (§17.5c)
+ latent-governance gate per §19.5
+ recurrent absorption track (§16.4): prefer path-1 base-model selection;
  path-2 retrofit with gate-utilization probes if no suitable base exists
```

Purpose:

- reduce reliance on visible text summaries;
- common target for latent/context/state compression.

#### Phase 5 — Latent context compression

```text
old static context → encoder → latent blocks
+ raw expansion fallback
```

Purpose:

- avoid full decoder prefill for old context;
- reduce KV before it is created.

#### Phase 6 — Adaptive state caching

```text
learn which states/slots to preserve
+ query-aware memory selection (selector + gate trained jointly)
+ recurrent or slot-based update
```

Purpose:

- move toward minimal sufficient state;
- reduce fixed segmentation artifacts.

---

## 22. Open Research Questions

1. **Minimal sufficient state**
   - What is the smallest operable state that preserves future logits under a distribution of future queries?

2. **Joint K/V preservation**
   - Can we preserve the attention operator directly instead of preserving K and V independently?

3. **Adaptive state selection**
   - Which states should be made permanent?
   - Can the runtime learn when to checkpoint, summarize, expand, or discard?

4. **Position-invariant memory**
   - Can memory slots avoid fragile absolute-position semantics?

5. **Cross-model portability**
   - Can a memory block generated by one model be consumed by another through an adapter?
   - (Production answer for now: no — invalidate and re-derive, per §6.2. This question is about whether an adapter can ever beat re-prefill on cost. Streaming dual-model systems — a fast interaction model paired with a background reasoner — already face this in-product, and implicitly answer it the same way: share text-level state, never KV. See Appendix A.)

6. **Renormalization-aware eviction**
   - Can eviction policies compensate for softmax-mass redistribution (e.g., learned rescaling of surviving logits, or merging evicted mass into anchors) rather than ignoring it?

7. **Compression vs decomposition**
   - When should the system preserve memory, and when should it decompose/recompute instead?

(Latent-memory governance, formerly Q6, moved to §19.5 as a deployment gate.)

---

## 23. Recommended MVP

### 23.1 MVP scope

The most practical first prototype is the MVP core from §21.1:

```text
1. Use a normal decoder runtime.
2. Keep recent exact KV on GPU; pin sink tokens.
3. Segment old thread history.
4. Generate compact summaries for old spans; index everything (shadows + pointers).
5. Archive raw spans on disk.
6. Persist compacted KV checkpoints (delta-based) after summaries.
7. Stand up offline fidelity certification before making compacted resume the default.
8. On resume, load compacted KV from disk; fall back to summary prefill on any compatibility mismatch.
9. If exact recall is needed, use runtime-gated EXPAND; expose model-visible EXPAND only for debug/research.
10. Log selector/gate decisions for §17 training data.
```

MVP interface:

```text
recent exact KV
+ summary/memory blocks
+ raw expansion fallback
+ disk checkpoint restore
```

Do **not** begin with many special tokens. Begin with the existing chat template, runtime metadata, and one visible operation in debug/research mode:

```text
EXPAND(block_id)
```

Everything else should be represented as side metadata or internal memory blocks.

### 23.2 Tiny end-to-end example

```text
Thread state at t=18,500:
  raw span S7 = assistant reasoning block, tokens 12,000-18,500
  recent exact KV = tokens 18,501-now
  sink tokens = positions 0-3, pinned

Compaction:
  1. Archive S7 raw text:
       store://raw/thread/th_01/span/0007
  2. Generate summary text:
       "We decided the durable substrate is text+provenance..."
  3. Preserve summary-path KV under current compatibility_fingerprint.
  4. Evict original S7 KV, excluding pinned sinks.
  5. Create MemoryBlock:
       semantic_kind = assistant_reasoning_span
       primary representation = summary_text
       auxiliary representation = kv_pages
       embedding_shadow = gloss + embedding over summary/source
  6. Write delta checkpoint:
       parent = ckpt_prev
       changed_pages = summary KV + page-table diff
       offline_certification_id = evfid-v1:...
       online_risk_estimate = 0.07

Resume later:
  1. Validate compatibility_fingerprint.
  2. Hydrate compacted KV pages.
  3. Append new user message.
  4. Selector loads `mb_s7` as relevant; `mb_s7.source` points to raw span S7 / 0007.
  5. Expansion gate decides whether summary memory is enough.

If exact detail is needed:
  1. EXPAND(mb_s7) fetches raw span S7 / 0007.
  2. Runtime injects the raw text through RETRIEVED_EXACT.
  3. Answer proceeds with exact local evidence.
```

---

## 24. One-Sentence Architecture

A long-thread LLM runtime should treat **text plus provenance as the durable memory substrate** and everything else — exact recent KV for local continuation, compressed memory blocks for old context, disk-backed compacted checkpoints for fast resume — as **fidelity-gated, regenerable cache tiers over it**, with raw expansion as the calibrated escape hatch when compression is insufficient.

---

## Appendix A — Related Systems and the Novelty Boundary

This spec does not invent most of its components; it unifies them. The table maps the nearest existing systems onto the layers of this design and states what each lacks relative to the spec. (Compiled from literature and systems knowledge as of early 2026 — verify citations before formal publication; system-specific claims marked `[citation_needed]` are non-normative until sourced.)

| System / line of work | Layer it covers | What it provides | What it lacks relative to this spec |
|---|---|---|---|
| MemGPT / Letta | OS-style memory hierarchy | text-level paging between context and external store, self-editing memory | no KV/state-level persistence; no behavioral-loss compression; no compatibility/fidelity machinery |
| vLLM prefix caching, SGLang RadixAttention | exact KV reuse | automatic sharing of identical prefixes within a deployment | exact-match only; no compression, no durability semantics, no provenance, invalidated silently across builds |
| LMCache, Mooncake | KV transport / disaggregation | moving and pooling KV across nodes and storage tiers | cache layer only; no lossy memory tiers, no selector, no expansion |
| CacheGen | KV compression for transmission | lossy encoding of KV for network/disk transfer | single technique; no IR, no raw fallback, no decision layer |
| Gist tokens, AutoCompressors, ICAE, Activation Beacon | learned context compression | trained compaction into soft tokens / condensed KV with behavioral objectives | per-technique interfaces; no runtime substrate, no provenance, no expansion contract |
| H2O, SnapKV, DMC, StreamingLLM | eviction / merging policies | runtime KV reduction heuristics; the attention-sink finding (StreamingLLM) | runtime-internal and ephemeral; no durability, no raw fallback, no fidelity gating contract |
| RAG frameworks (LlamaIndex etc.) | text retrieval | chunking, embedding, retrieval into prompt | text-only; no state preservation, no continuation semantics |
| Vendor memory features (product-level) | cross-session text memory | curated user memories injected as text | opaque, text-only, not a runtime abstraction |
| Recurrent absorption memory (Compressive Transformer, Infini-attention, Titans, SSM/attention hybrids, linearization retrofits) | in-model memory mechanism | fixed-size, position-free recurrent state absorbing evicted/old context; trained gate between local attention and memory path; constant-cost long context | bounded exact recall (needs EXPAND); state is opaque and order-dependent (no paging, hard joins); maximally model-bound; gate collapse risk on retrofit — adopted by this spec as the preferred Phase 4 mechanism (§16.4) |
| Amortized KV synthesis (Still; neighbors: KV-Distill = amortized selection, Attention Matching = per-context synthesis, Cartridges = per-context prefix tuning, KVZip = query-agnostic selection) | trained KV compiler over a frozen base | per-layer Perceiver trained once (forward-KL vs full-context teacher, answer-side tokens); single-forward-pass compaction; 8×–200× at 8k–128k; position-free compaction with logical/physical offset accounting; iterative re-compaction with lookahead buffer | per-base-checkpoint compactor (model-bound, fingerprint-tracked); horizon-validity envelope — fails below no-context floor past trained recurrence depth; exact-recall collapse under recurrence (needle ≈ 0 while semantic evidence holds) → requires this spec's EXPAND gate; adopted as the §8.1 KV-compressor instantiation and "Phase 3.5" |
| Sparse attention + KV offload — the "deselect" regime (MLA → NSA → DSA lightning indexer → FlashMemory/LSA; training-free: Quest, InfLLM, ShadowKV) [citation_needed] | within-session serving pattern | retain all KV (offloaded), load only query-critical chunks per decoding step via a learned or heuristic indexer; lookahead prefetch hides PCIe latency; MLA × sparsity compose multiplicatively; GPU-resident KV ~10–15% of baseline reported with neutral accuracy [citation_needed] | reduces GPU footprint only — total storage unchanged; session/build-bound, no provenance, no cross-session memory; requires sparse-trained backbones for logit-faithful/cache-reversible operation [citation_needed] (training-free variants degrade at aggressive sparsity); a serving pattern **inside** this substrate (§13.7), not an alternative to it |

**Note on the deselect regime and implementation tiers (restored in v0.3.1).** This line is the third pole of §13.7 and the in-house long-context stack of the DeepSeek lineage (MLA in V2/V3, native sparse attention in NSA, the DSA lightning indexer in V3.2+, with FlashMemory-class lookahead systems built on V4 by third parties [citation_needed] — the latter days-old and unverified at time of writing). Implementation cost splits into tiers: **(0)** consuming sparse-trained backbones via mainstream serving engines is turnkey but inherits frontier-scale model sizes; **(1)** training-free selection on dense 7–8B models (Quest/InfLLM/ShadowKV-style) is research-repo-grade, days of work, lossy at aggressive sparsity; **(2)** training the decision layer decoupled from the backbone is single-node cheap and is the transferable result this spec adopts — promoted to the main body as the recommended construction for the selector and expansion gate (§17.5, Phase 3); **(3)** production per-step selection (sparse-gather kernels, async prefetch pipelines, scheduler integration) is dedicated systems work; adopt it by backbone selection, per the recurring select-don't-build principle (§13.6, §16.4).
| Full-duplex / streaming interaction models (TML Interaction Models, Moshi, Nemotron VoiceChat) | real-time input layer | time-aligned interleaved input/output streams (~200ms micro-turns), natively multimodal typed channels co-trained from scratch | no long-term memory tier; persistent streaming sequence grows without bound; a **consumer** of this substrate, not an alternative to it |
| Parallel reasoning via interleaved decoding (Parallel Decoding within One Sequence, ParaThinker, Group Think, APR) | decoding-time runtime pattern | multiple reasoning branches decoded concurrently — one or more tokens per branch per step — interleaved into one sequence/cache under custom masks and position slots; fork/join (spawn/join) operations; within-generation KV reuse across stages | no persistence, provenance, or compaction story; join semantics ad hoc per method; a runtime pattern **inside** this substrate (§11.6, §12.4), not an alternative to it |

**Note on parallel-reasoning decoding.** This family operates inside the substrate's runtime abstractions and pressure-tests three of them. First, it routinely decouples token generation order from position indices within a live cache, which forced the §12.4 scope clarification: position reinterpretation is a validated runtime technique within a build/session and a forbidden corruption risk across persisted boundaries. Second, it introduces concurrent branching with convergence, which sequential CoW branching did not cover — hence the join semantics of §11.6. Third, it produces physically interleaved cache regions under block-sparse masks, the concrete case that makes the checkpoint schema's `attention_metadata` load-bearing. It also supplies two free wins: fork/join markers are explicit segmentation signals (replacing §7.2's heuristic boundary detection where available), and a joined parallel region is a self-delimiting completed reasoning block — the ideal Memento compaction target (§14). ParaThinker's reuse of reasoning-stage KV during summarization is a within-generation instance of §4.3's "preserve operable state."

**Note on streaming interaction models.** This line of work sits below the substrate rather than beside it, and it sharpens three of the spec's claims. First, it is the extreme case of the problem statement: a ~5 Hz multimodal stream appends tokens continuously regardless of information content, so hours-long ambient sessions exhaust any context window far faster than chat, and most of the stream (silence, static frames) is precisely the "old stable spans" the compaction tier targets — with the constraint that EXPAND latency is unacceptable inside the real-time loop and must route through the slow path. Second, the published dual-model design (a fast interaction model paired with an asynchronous background reasoner) is a product-level instance of §4.6: two models sharing one conversation can only exchange substrate-grade state, since their KV is mutually incompatible by construction; the MemoryBlock primary representation is the natural interchange format for that split. Third, these models realize typed channels as interleaved, time-aligned streams with modality embeddings **trained from scratch** — supporting both halves of §4.2: channels are the right abstraction for non-textual content, and they require training rather than retrofit. One extension they force: positions in these systems are wall-clock-aligned, so §12's logical/physical distinction gains a temporal axis ("logical time"), and eviction of time-aligned streams remains subject to the §13 renormalization and sink constraints.

**The novelty boundary.** Individually, every row exists. What does not exist as a unified design, and what this spec contributes, is:

1. a single IR (`MemoryBlock`) spanning text, latent, and KV representations with semantic-identity/physical-representation separation;
2. mandatory provenance + compatibility hashing that makes the substrate/cache distinction enforceable;
3. a budget-aware selector and a calibrated expansion gate as the decision layer over all tiers;
4. a fidelity-gate contract that turns "eviction quality" from an assumption into a measured, per-build property;
5. copy-on-write, delta-based checkpoint/branch semantics over the same page abstraction.

A reviewer should evaluate the spec on (1)–(5), not on the per-tier mechanisms, which are imported.

---

## Appendix B — Reference MVP Build (new in v0.3.3)

A concrete instantiation of the MVP core (§21.1) plus Phase 3.5, sized for a small lab with single-node GPU access. Everything below is one defensible configuration, not the only one; substitutions are noted where they are safe.

### B.1 Target model and fingerprint

```text
base model      Qwen/Qwen3-4B-Instruct-2507 (Apache-2.0)
rationale       dense GQA; the published Still validation target, so the
                compactor recipe, hyperparameters, and headline numbers
                transfer without re-derivation; small enough that the
                teacher passes for gate labels run on one GPU
geometry        L=36 layers, H_kv=8, d=128 → ~144 KiB/token KV at bf16
                (1.125 GiB @ 8k, 4.5 GiB @ 32k, 9 GiB @ 64k)
serving         vLLM, bf16, pinned versions; fingerprint frozen on day 1
                (model hash, tokenizer/template hashes, RoPE config,
                attention impl, kv_layout=gqa, quantization=bf16,
                compaction_policy_version, position_policy_version)
hardware        1× 80GB-class GPU for substrate + gate work;
                4–8× H100/H200 for the Phase 3.5 compactor run
embedding model Qwen3-Embedding-0.6B for shadows and the dual-encoder
                gate (shadow-v1 in every embedding_shadow record)
```

Rule: no fidelity or gate data is generated before the fingerprint is frozen. A quantization or runtime change afterward invalidates the data, not just the caches (§4.6).

### B.2 Substrate components (Phases 0–2)

```text
raw archive     content-addressed object store (filesystem or S3-style),
                SQLite/Postgres index for spans, hashes, redaction_generation
segmenter       turn boundaries + token-count cap (1–2k-token spans);
                fork/join markers where available (§11.6)
summaries       generated by the base model itself; primary representation
sink policy     pin positions 0–3 (§13.2); assert in the compactor path
checkpoints     delta-based compacted-KV via paged-cache snapshot to NVMe;
                hydrate-or-fallback per §7.4
```

### B.3 Data pipeline (shared by certification, compactor, and gate)

Mirror the Still recipe, which is exactly the spec's counterfactual construction with a cheap equivalence function:

```text
1. corpus        long documents in 3–4 domains relevant to deployment
                 (e.g., financial filings, legal, code, literature);
                 ~100–150k items, ~1B context tokens at 8k
2. items         extractive MCQs generated by the base model from random
                 ~1k-token sub-chunks of each document
3. filters       (a) teacher-verified answerable WITH context;
                 (b) discard items the model answers WITHOUT context
                 — filter (b) is what makes every item a counterfactual
                 probe: correct answer ⇒ the information flowed through
                 the (compact) cache
4. eq_policy     MCQ letter exact-match = eq_policy_v1 (§17.4) — trivially
                 cheap, versioned, low-noise
5. probes        held-out needle-style items over to-be-evicted spans =
                 the lost-fact instrument (§13.4, §17.1)
```

### B.4 Phase 3.5 — compactor training

```text
architecture    Still canonical: per-layer Perceiver, d_l=256, B=2 blocks,
                cross-attention every block, no FFN, identity-style init,
                RoPE-fix (un-rotate → internal RoPE → re-rotate), β=0;
                t=128–1024 latents depending on target ratio (~50M params)
objective       forward KL vs full-context teacher, answer-side tokens,
                top-200 teacher support with gold token forced in
optimizer       AdamW lr 4e-5, warmup 100, constant; effective batch 32;
                ~1500 steps
budget tiers    full repro: 8×H200, hours-to-a-day per checkpoint
                reduced:    1×H200/H100 + grad accumulation, T=4k, t=512
                            (validated regime in the paper's ablations),
                            a few days
certification   §13.4 offline protocol on held-out items: KL vs teacher,
                MCQ delta, lost-fact incident rate; iterative checkpoints
                certified AT deployment depth → max_certified_depth
```

### B.5 Gate training (Phase 3 deliverable)

```text
labels          run the frozen base offline on (q, M_compact) and (q, R_raw);
                y = answers differ under eq_policy_v1 — the corpus above
                already has gold answers, so labeling is two forward passes
                per item
model           dual encoder over Qwen3-Embedding-0.6B: f(query+recent gloss)
                · g(block shadow); contrastive training, single GPU, hours
calibration     temperature scaling on held-out triplets; report ECE
evaluation      §17.6 in full: expansion P/R, reliability curve, lost-fact
                incident rate, against never-/always-/classify-and-expand/
                oracle-expand; multi-hop slice reported separately
```

### B.6 Milestones and kill criteria

```text
M0  text substrate + shadows + EXPAND-by-runtime          (no training)
M1  compaction/eviction + sinks + offline certification    (no training)
M2  NVMe delta checkpoints, hydrate-or-fallback resume     (no training)
M3  MemoryBlock IR + selector + calibrated gate            (gate training)
M3.5 certified Still-class compactor replaces untrained
     eviction as the default L3 path                       (compactor training)

kill criteria   M1: if untrained eviction at the target ratio fails the
                fidelity gate on every setting, skip directly to M3.5
                rather than tuning heuristics. M3: if the gate cannot beat
                always-expand on the cost/correctness plane at acceptable
                ECE, the compression win is illusory for this workload —
                stop and re-scope before training anything.
```

The deliverable of B.5 alone — a calibrated sufficiency gate evaluated against oracle baselines — is a self-contained publishable result and generates the calibration data every later phase consumes.

### B.7 Hardware and software bill of materials (new in v0.3.3)

The non-model substrate is deliberately commodity. One nonstandard engineering artifact exists in the entire build (KV injection, below); everything else is standard tooling.

```text
HARDWARE (everything except the Phase 3.5 compactor run)
  machine        single box
  GPU            1× 24–80 GB (24 GB runs Qwen3-4B bf16 to ~32k context;
                 48–80 GB removes all planning)
  RAM            64–128 GB (CPU staging tier for checkpoint pages)
  storage        1–2 TB PCIe-4.0 NVMe (~5–7 GB/s)
                 sizing: full-KV (L4) 32k checkpoint ≈ 4.5 GiB;
                 compacted (L3, 8×) ≈ 560 MiB; hydration < 1 s for L3.
                 Delta checkpoints make write endurance a non-issue at
                 single-user scale; TBW budgeting starts at service scale.
  rented         4–8× H100/H200 by the day, ONLY for B.4 compactor training

SOFTWARE
  core           Python, PyTorch, HF transformers (PINNED — a transformers
                 upgrade touching RoPE/cache code is a runtime_version
                 change under §4.6 and invalidates certification data,
                 not just caches), safetensors (mmap-able bf16 checkpoint
                 serialization), vLLM (optional, serving tier only)
  retrieval      FAISS (flat/HNSW in RAM at 10^3–10^6 blocks),
                 sentence-transformers for the dual-encoder gate
  metadata       SQLite (span index, hashes, derived_from/supersedes graph,
                 redaction_generation); Postgres only if multi-user
  archive        filesystem or any S3-compatible object store,
                 content-addressed
  orchestration  plain Python + cron-level scheduling; no queues, no
                 Kubernetes — at MVP scale added infrastructure is overhead
                 without function
  eval           RULER generator + the B.3 MCQ pipeline as plain scripts

THE ONE CUSTOM ARTIFACT — KV injection into the runtime
  tier (a)       custom HF Cache subclass (CompactedPrefixCache pattern):
                 physical length K, stored offset T−K added to continuation
                 positions before RoPE. Pure PyTorch, no kernels.
                 SUFFICIENT for all of M0–M3.5 (certification, gate work).
  tier (b)       vLLM paged-cache injection (allocate K physical slots,
                 copy K/V, offset positions): proven feasible at near-full
                 decode throughput in the Still prototype, but a patch-level
                 integration, not a supported API. Optional serving polish;
                 not on the MVP critical path.
  non-required   custom attention kernels — avoided entirely by the β=0
                 policy (B.4); FlexAttention/kernel work enters only if the
                 bias channel is ever enabled, which this build forbids.
```

Total bill, excluding rented compactor hours: a workstation a small lab already owns.

---

## Changelog v0.3.6 → v0.3.7

- **First task-certified L3 configuration (§6.2):** unfrozen amortized compactor (√d_l logit scale) ships on the §13.4 task-anchored predicate at matched budget, depth 1 (distributional predicate not met — the predicates dissociate, recorded as such); recommended as an opt-in L3 policy with the probe-stack routing tier, default unchanged; full certification table in the E1FULL campaign report.
- **§13.4:** mandatory trained-compactor diagnostics added as protocol step 7 — init-time gradient forensics (saturation detection) and cross-attention entropy telemetry (subsampler detection); motivated by an observed configuration that optimized its loss for 1,500 steps at every data scale while its routing pathway received ~zero gradient.
- **§13.6:** sink-as-sensor upgraded to a measured, regime-general result (0.73–0.76 AUC refit; 0.72–0.76 zero-shot across eviction↔frozen↔unfrozen regimes).
- **§17.5:** relational sufficiency empirically confirmed; regime-dependent gate-class ladder recorded; monotone-declining-but-nonzero gate value; fragility measured as within-regime stable / cross-regime relative, extending §4.6 invalidation to gate labels and calibration.
- **§8.1:** dedup compiler row (lossless pointer tier for verbatim repeats).

---

## Changelog v0.3.5 → v0.3.6

- **§11.8 (Branching and compression compose; one cell does not):** branching and compression framed as orthogonal concerns over the shared page substrate (compression rewrites page contents, branching manipulates page references) — one architecture, two composable operations; the 2×2 with the single hostile cell (branching under recurrent absorption) unified with the §11.6 join, §16.4 join, and §11.7 speculative-decoding non-forkability notes as one underlying state property; resolved by a routing rule (branchy → page-compressible tiers; linear low-branch → absorb tier) rather than a second architecture; articulates separable-and-addressable vs entangled-and-dense as the reason the page abstraction is load-bearing.

---

## Changelog v0.3.4 → v0.3.5

- **§11.7 (Compute accounting):** three-resource/two-phase framing; per-mechanism compute ledgers in the spec's own terms (compaction as an amortized investment with an explicit horizon formula; chunked compaction and absorption as the only prefill-reducing paths; deselect as decode-only; untrained eviction as paying in fidelity rather than FLOPs; EXPAND over-firing as a compute regression channel bounded by always-expand; certification as a recurring line item); store-vs-recompute break-even with reference-build numbers and the cold-thread consequence that re-prefill is the economically primary resume path; normative rules R1–R5; §20.1 metrics extended accordingly.

---

## Changelog v0.3.3 → v0.3.4

- **§4.7 (Two workloads, one substrate):** the pointwise/aggregative dichotomy stated as a design principle — incompressible vs compression-tolerant information, antagonistic optimization targets, the spec reframed as a routed two-path architecture with EXPAND as a co-equal path rather than a failure fallback; multi-hop retrieval-then-integration recorded as the known weakest regime.
- **§13.4:** certification must report the aggregation and pointwise axes separately, never blended; aggregation-only certification requires an active calibrated gate for pointwise traffic; protocol steps renumbered.
- **§17.5/§17.6:** query workload type added as a gate feature; classify-and-expand added as the interpretable baseline the trained gate must beat; multi-hop slice required in the evaluation mix. B.5 updated to match.

---

## Changelog v0.3.2 → v0.3.3

- **Still integration (arXiv:2606.07878, verified against full text):** §8.1 gains amortized KV synthesis as the validated KV-compressor instantiation; §13.3 gains the amortized-producer (trained-producer/frozen-consumer) regime; §13.4 gains recurrence-depth certification with `max_certified_depth` and refuse-past-depth resume semantics; §8.4 gains KV-level consolidation with the lookahead-buffer note and the linear-growth caveat distinguishing it from §16.4; §12.4 gains the implementation-validation note (position-free compaction, logical/physical offset); §17.1 gains the empirical anchor (semantic evidence preserved at 90% while needle retrieval collapses to ~0 under recurrence); §8.3 gains the residual-MSE ablation as support for the behavioral-KL objective; §4.6 requires compactor weights hash + certified depth in `compaction_policy_version`; Appendix A gains the amortized-KV-synthesis row; §21 gains Phase 3.5.
- **B.7 (bill of materials):** commodity hardware sizing from the B.1 KV geometry, pinned software stack with the §4.6 version-pinning rationale, and the single custom artifact (two-tier KV injection) isolated explicitly; custom kernels excluded by the β=0 policy.
- **Appendix B (Reference MVP Build):** concrete target model (Qwen3-4B-Instruct-2507) with frozen fingerprint, substrate component choices, a shared data pipeline (extractive MCQ counterfactuals with no-context filtering as eq_policy_v1, needle probes as the lost-fact instrument), Still-canonical compactor training at two budget tiers, dual-encoder gate training and calibration, and milestones M0–M3.5 with kill criteria.

---

## Changelog v0.3.1 → v0.3.2

- **Representation naming consistency (§7.3):** changed the compaction pseudo-code primary representation from `format: "text"` to `format: "summary_text"` to match the schema's representation enum.
- **Canonical channel enum (§5.2, §6.1, §6.3):** collapsed model-facing roles and runtime channels into one channel registry: `NORMAL_TEXT`, `COMPRESSED_MEMORY`, `RETRIEVED_EXACT`, `TOOL_OBSERVATION`, and `CONTROL`; SYSTEM/USER/ASSISTANT/TOOL now appear as role metadata inside `NORMAL_TEXT`.
- **Online risk wording (§7.2, §7.3):** replaced synchronous-sounding `measure_fidelity_delta` language with `estimate_online_risk` / checkpoint risk metadata, preserving §13.4's split between offline certification and online risk reporting.
- **Deselect precision (§13.7, Appendix A):** replaced "lossless" phrasing with "non-destructive/cache-reversible" and clarified that logit fidelity depends on the sparse-attention/indexer training regime.
- **EXPAND ID consistency (§23):** changed `EXPAND(S7)` to `EXPAND(mb_s7)`, with `mb_s7.source` pointing to raw span S7 / 0007.
- **Citation hygiene (§13.6, §16.4, §17.5, Appendix A):** marked system-specific and days-old external claims with `[citation_needed]` so they cannot be mistaken for normative spec requirements.

---

## Changelog v0.3 → v0.3.1

- **Restored material dropped by a stale-base merge in v0.3:** the evict/absorb/deselect trichotomy (now §13.7), the decoupled dual-encoder construction for the selector/expansion gate (§17.5, wired to the versioned eq_policy of §17.4 and the embedding-shadow invalidation rules of §6.1), the Appendix A sparse-attention/KV-offload row with implementation tiers, and the Phase 3 decoupled-gate wording.
- **§13.6:** selection rationale and production precedents restored inside the non-normative implementation-note framing.
- **§7.2:** reconciled with the §17.2 EXPAND contract (mode A runtime-gated default; mode B model-visible for debug/research).
- **§4.6:** `kernel_numeric_profile_hash` given an operational definition; undefined fields are decorative.

---

## Changelog v0.2 → v0.3

- **MemoryBlock schema tightened (§6.1):** `kind` renamed to `semantic_kind`; storage forms moved exclusively into `representations[].format`; block identity no longer conflates memory meaning with KV/latent/text representation.
- **Canonical compatibility fingerprint (§4.6, §6.2):** ad hoc model compatibility tuples replaced by one explicit fingerprint covering model, tokenizer, chat template, RoPE, attention implementation, KV layout, quantization, adapters, runtime, compaction policy, position policy, channel registry, and numeric kernel profile.
- **Embedding shadow metadata (§6.1):** `embedding_shadow_uri` replaced by a structured `embedding_shadow` object with embedding-model/version/redaction metadata and invalidation rules.
- **Checkpoint fidelity split (§6.2, §13.4):** full-context KL comparison moved to offline certification; per-checkpoint state now records lightweight online risk metadata rather than pretending to perform synchronous teacher comparisons.
- **EXPAND contract clarified (§17):** runtime-gated automatic expansion is the default; model-visible block IDs are limited to debug/research candidate inventories. Answer-equivalence labeling is now task-specific and versioned.
- **Implementation roadmap separated (§21):** Phases 0-3 are the deployable MVP core; Phases 4-6 are research extensions requiring adapter/model training and latent-memory governance.
- **Recommended MVP sharpened (§23):** added a concrete end-to-end compaction/resume/EXPAND example.
- **Architecture-mitigation claims softened (§13.6):** base-model attention mitigations are implementation notes and selection criteria, not normative substrate requirements.

---

## Changelog v0.1 → v0.2

- **Substrate/cache reframing (§1, §4.6, §6.2, §24):** text + provenance declared the only durable tier; all KV/state artifacts reframed as TTL-bounded caches; invalidation-and-rederive migration policy specified; "high fidelity" label on L3 replaced with measured fidelity.
- **Eviction fidelity (§2.6, new §13):** softmax renormalization and stale-survivor mechanisms documented; mandatory sink-token pinning; trained-vs-untrained compaction regimes distinguished; fidelity gate protocol added and wired into checkpoints, compaction flow, Phase 1, and the MVP. Added §13.6 surveying architectural sink/renormalization mitigations (softmax₁, learnable per-head sink logits, register tokens, gated attention, sigmoid attention); learnable per-head sink logits adopted as the preferred base-model criterion for substrate deployments; sigmoid attention flagged on the architecture watchlist as dissolving §13.1 (cross-linked to Q6).
- **Channel claim narrowed (§4.2, §6.3, §10.1):** chat templates retained as the textual channel mechanism; channel machinery reserved for non-textual content; Option A corrected to require no model changes.
- **Expansion decision promoted (new §17):** failure asymmetry, sufficiency definition, counterfactual training-signal construction, gate implementations (including an answerability-head variant), full evaluation protocol with oracle/never/always baselines, and budget awareness.
- **Related-systems appendix (Appendix A):** positioning against MemGPT/Letta, vLLM/SGLang, LMCache/Mooncake, CacheGen, gist/AutoCompressor/ICAE/Beacon, H2O/SnapKV/DMC/StreamingLLM, RAG frameworks; explicit novelty boundary. Added full-duplex/streaming interaction models (TML Interaction Models, Moshi, Nemotron VoiceChat) as a consumer layer below the substrate, with implications for §4.2, §4.6, §12, and Q5. Added parallel reasoning via interleaved decoding (Parallel Decoding within One Sequence, ParaThinker, Group Think, APR) as a runtime pattern inside the substrate, motivating new §11.6 (concurrent branches and join semantics) and §12.4 (scope of the position-reinterpretation prohibition).
- **Storage arithmetic (§11.2):** per-token KV math for MHA/GQA/MLA; multi-tenant L4 economics; delta-based checkpoints to control NVMe write amplification; page schema generalized with `kv_layout` (§11.3).
- **MemoryBlock schema (§6.1):** single `representation` replaced by `representations[]` with primary (substrate-grade) vs auxiliary (cache-grade) roles; mandatory `embedding_shadow`; `derived_from`/`supersedes` lineage.
- **Consolidation (§8.4):** hierarchical re-summarization with provenance-preserving merge, supersession, and GC rules; raw indexer reclassified as mandatory infrastructure (§8.1).
- **Selector (§9.2, §9.5):** relevance defined over embedding shadows; linear scoring marked as Phase-0 placeholder; learned selector flagged as plausibly joint with the expansion gate.
- **Security (§19.3–19.5):** channel-bias trust enforcement marked unproven; deletion required to trace the derivation graph; latent-memory governance moved from open question to deployment gate on Phases 4–6.
- **Misc:** sampler reproducibility marked best-effort; sink retention and fidelity report added to checkpoint schema; new open question on renormalization-aware eviction.
- **Recurrent absorption memory (new §16.4):** eviction-as-absorption adopted as the preferred Phase 4 trained-compaction mechanism (Compressive Transformer / Infini-attention / Titans / SSM-hybrid lineage); state-vs-pages checkpoint analysis (constant-size, position-free, maximally model-bound); inference/training cost model; three acquisition paths (select > retrofit > pretrain) with gate-collapse and recall-gap warnings on the retrofit path; cross-wired into §13.5, §11.6 (recurrent joins are summary-join-only), Phase 4, and Appendix A.