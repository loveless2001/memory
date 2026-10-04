# M4-SGM — Sparse Growing Memory with Exact Recovery

**Codex implementation brief / research design v0.1**  
**Date:** 2026-10-04  
**Target repository:** `loveless2001/memory`  
**Inspected branch:** `mvp`  
**Inspected commit:** `f67ff34d643fad7014f587c1ed4526cefe8ee34a`  
**Status:** proposed experiment; no implementation or successful results implied  
**Initial authorization:** implement P0–P2 locally; do not launch paid/cloud runs or change production defaults.

## 0. Instruction to Codex

Read this brief and the repository documents identified in §2. Inspect the actual checkout before editing: it may have advanced beyond the inspected commit. Record the starting commit and any material interface differences. Preserve unrelated changes; do not reset or force-update the branch.

Implement **P0–P2 only** in the first pass: a CPU-testable sparse memory core, an explicit frozen-backbone integration, and a small synthetic learning/evaluation path. Later sections specify the intended research program, not permission to launch it. Do not equate scaffolding, green unit tests, or decreasing training loss with a successful memory experiment.

Use this brief as the scope authority for the new M4 experiment. Preserve the existing substrate, compatibility, redaction, position, and certification invariants. Do not edit historical reports to make them agree with a new result. Record the work in `M4-SGM.md`, with a separate implementation/validation report.

**Central question:** Can a growing, sparsely addressed recurrent memory improve long-history use at bounded neural access cost, and can query-conditioned monitoring plus exact retrieval repair its remaining failures?

There are three separate claims to test:

1. **Storage/read benefit:** the neural backend itself helps without archive expansion.
2. **Recovery benefit:** a calibrated decision and retrieval path improves actual answer correctness at a measured cost.
3. **Scaling benefit:** fixed local access remains useful as allocated state and history grow.

A win on one does not establish the other two.

## 1. Scope and interpretation

Call this backend **SGM**, not “the Spotlight implementation.” It is a Spotlight-inspired experiment attached to an existing frozen model. It does not reproduce a jointly pretrained sequence mixer. The concrete interpolation, update, integration, and evaluation choices below are this proposal's choices, not claims about Percepta's exact implementation. The available Percepta page establishes the growing-memory/linear-cost motivation; its technical body was not fully retrievable during preparation. The linked Gist was also unavailable. Neither is an executable dependency. [R9]

The first version keeps the house Qwen3 backbone frozen and adds trainable memory adapters at selected layers. It does not replace attention, retune the tokenizer, synthesize arbitrary KV banks, or train a new foundation model.

The existing archive remains the durable record. Neural state is disposable, model-bound operational state. An archived assertion is evidence of what a source said, **not certification that the assertion is true**. Provenance is not truth, and recording which cell received a write is not a complete explanation of that cell's contents.

Do not implement a full OptMem port, autonomous skill synthesis, glyph training, a “gravity” scheduling policy, vector-database infrastructure, vLLM integration, custom CUDA kernels, or an HTTP service in the first pass. Optional extensions appear in §20.

## 2. Repository facts and reuse map

The existing architecture already separates durable raw text/provenance from cache-grade state. Its `MemoryBlock` requires exactly one substrate-grade primary representation and a mandatory embedding shadow. Preserve that contract. [R1, R2]

The inspected `HFModelRuntime` uses a custom decode loop and separates logical RoPE positions from physical cache positions. Its main forward helpers are decorated with `torch.inference_mode()`. They cannot serve unchanged as the differentiable student-training path. [R3]

The inspected `RuntimeGatedExpander` expands a block's contiguous source range. Its `maybe_expand` uses a similarity threshold; it is not the research residual-state probe. Reuse archive validation and raw expansion, not the assumption that the current runtime already provides calibrated sufficiency detection. [R4]

The existing certification harness compares KV-based arms and distinguishes aggregation from pointwise loss. It does not directly represent a streaming sidecar state. Its silent-loss counter excludes errors after an expansion call, so M4 must additionally count errors **despite** expansion. Preserve the legacy definitions while adding new fields. [R5]

The clean E1FULL result remains **NO-SHIP**, with `max_certified_depth = 0`. Nothing in this brief authorizes loading that compactor into a default deployment path. [R6]

| Existing component | M4 treatment |
|---|---|
| `archive/raw_archive.py`, `store/blob_store.py`, `store/sqlite_index.py` | Reuse source storage and visibility/redaction checks; add versioned SGM metadata separately. |
| `schemas/memory_block.py` | Preserve primary/shadow invariants; use an auxiliary state reference or a separate manifest. |
| `runtime/compacted_prefix_cache.py` | Reuse bounded recent KV, sink pinning, and position bookkeeping. |
| `runtime/hf_model_runtime.py` | Leave ordinary inference unchanged; introduce a separate SGM runtime/training path. |
| `fingerprint.py`, checkpoint machinery | Reuse compatibility rules; fingerprint both the sidecar and KV influenced by it. |
| `selection/runtime_gated_expand.py` | Reuse validated raw expansion; do not treat similarity as sufficiency. |
| `gate/` and research probe runners | Reuse capture/evaluation patterns, not pretrained gates or historical AUCs. |
| `certification/` | Reuse metric definitions and paired analyses through a new stateful-arm runner. |
| `redaction_graph_invalidator.py` | Extend to live SGM state and SGM manifests; conservative invalidation is acceptable. |

The inspected environment pins Python `>=3.12,<3.13`, Torch `2.7.1`, Transformers `4.55.2`, and safetensors `0.5.3`. Do not silently upgrade these to make an integration work. [R7]

## 3. Architecture

```text
Authorized source span
        |
        +----> raw archive + source metadata + visibility cursor
        |
        +----> frozen model, streamed with bounded recent KV
                        |
                 trainable SGM adapters
                        |
                 sparse recurrent cells

Query (read-only; not a persistent write)
        |
        v
recent exact KV + SGM reads --> draft computation / probe features
                                      |
                               calibrated decision
                               /                 \
                          answer                recover
                                                  |
                            cell-linked candidates + independent archive search
                                                  |
                                   verified exact source expansion
                                                  |
                              replay query from its pre-query snapshot
```

“Recent exact KV” means retained, unmodified KV under the **SGM runtime**, not equality to the full-context, unmodified teacher's representations. The memory contribution changes subsequent computation.

The first system is single-threaded per session. Different sessions and evaluation episodes must have independent banks. A query may fork a scratch state; answering does not mutate the committed source-memory state.

## 4. Default experimental configuration

These are initial design settings, not empirically validated operating points. Commit the realized configuration before a run.

```yaml
experiment: m4-sgm-v0
mode: research_only
base_model: house_reference_from_reference_config
freeze_backbone: true
integration: residual_parallel_to_attention
selected_layers_zero_based: [8, 17, 26, 35]  # reference 36-layer model
memory_heads_per_layer: 4                   # independent of model KV heads
key_dim: 32
value_dim: 32
state_dtype: float32
adapter_dtype: float32
local_recent_tokens: 1024
pinned_sink_tokens: 4
router: shared_coordinate_mlp_over_projected_query_or_key
address_scale: 8.0
stencil: quadratic_bspline_3x3
update: weighted_delta_v1
read_order: read_before_write
allocation: lazy_on_nonzero_write
max_cells_per_layer_head: 1024
capacity_overflow: fail_closed
persistent_write_source: authorized_source_tokens_only
query_writes: false
retrieval_enabled: false                   # first backend tests
max_recovery_rounds: 2                     # later recovery stage
max_candidate_spans_per_round: 32
max_expanded_tokens_total: 2048
allow_paid_execution: false
```

For the tiny CPU model, use one or two valid layers, two heads, dimensions 8, a recent window of 32–64 tokens, and small cell budgets. Derive hidden size and layer count from its config. Record the resolved configuration, not only a preset name.

The sparse grid has signed integer coordinates and no preallocated rectangular extent. `max_cells` is a safety budget, not evidence of unlimited capacity. Address scale is fixed within a policy; changing it after writes would change addressing semantics and requires rebuilding state.

## 5. Neural memory core

### 5.1 State and addressing

For every selected layer `l` and memory head `h`, maintain a map:

```text
(ix: int, iy: int) -> S[l,h,ix,iy] of shape [d_key, d_value]
```

Cells are runtime state, **not trainable parameters**. Allocate zero-initialized cells on the first nonzero-weight authorized write. A read of an absent cell returns zero without allocating it.

From the selected layer's normalized pre-attention hidden vector `z_t`, produce:

```text
q_t = l2_normalize(W_q z_t)
k_t = l2_normalize(W_k z_t)
v_t = W_v z_t
beta_t = sigmoid(w_beta z_t + b_beta)
a_read  = address_scale * AddressMLP(q_t)
a_write = address_scale * AddressMLP(k_t)
```

`AddressMLP` has two real outputs and is shared between the read and write address maps within a bank. Query/key projections remain distinct. Do not bound addresses with a fixed-grid softmax or `tanh` and then claim unconstrained allocation.

No operation may score all allocated cells, construct a dense bounding rectangle, or copy the entire bank in the per-token fast path.

### 5.2 Explicit differentiable 3×3 interpolation

Use a quadratic B-spline stencil so integer cell selection does not remove all address gradients.

For one coordinate `x`:

```text
n = floor(x + 0.5)
f = x - n                         # -0.5 <= f < 0.5
indices = [n-1, n, n+1]
weights = [0.5*(0.5-f)^2, 0.75-f^2, 0.5*(0.5+f)^2]
```

Take the outer product of the x/y weights for nine cell weights. They are nonnegative and sum to one. The index choice is discrete; the interpolation weights retain piecewise-smooth coordinate gradients. Test finite differences away from stencil transitions, plus continuity at transitions.

This is a specific proposed surrogate. It does not guarantee that addresses learn useful organization. Do not label nearest-neighbor integer lookup with detached coordinates “learned differentiable addressing.”

### 5.3 Read and write

Read using the state **before** the current token's write:

```text
r_t = sum_c w_read[c] * transpose(S_c) @ q_t
```

Missing cells contribute zero; do not renormalize only over occupied cells. Occupied-weight fraction may be recorded as telemetry, not interpreted as calibrated confidence.

For each addressed write cell, apply:

```text
error_c = v_t - transpose(S_c) @ k_t
S_c_new = S_c + w_write[c] * beta_t * outer(k_t, error_c)
```

This is an associative delta update, not simple averaging. The initial proposal has no global decay or hidden overwrite heuristic. Any decay, clipping, or normalization change is a separately versioned policy/ablation.

Perform state arithmetic in FP32. Reject nonfinite state. Monitor state norms, update norms, repeated-key behavior, and interference. A finite matrix can still lose bindings; address growth does not establish exact storage.

### 5.4 Integration with the frozen model

At each selected layer, add the memory output alongside ordinary attention, before the layer's MLP:

```text
h_after_attention = h_residual + attention_output
h_after_attention += alpha * W_out(concat(memory_head_reads))
h_out = h_after_attention + MLP(post_attention_norm(h_after_attention))
```

Use the pinned model implementation to preserve its actual ordering and return contract. Implement an explicit adapter/wrapper with request-scoped state; do not patch global functions or rely on opaque, state-mutating forward hooks.

Initialize `alpha` small and nonzero, for example `sigmoid(-4)`, and `W_out` small but nonzero. Initializing both paths to zero can block useful gradients. `sgm_enabled=false` must bypass the adapter exactly and recover the original model's behavior within the existing numerical tolerance.

Backbone parameters have `requires_grad=False` and are absent from the optimizer. **Do not wrap the student forward in `no_grad()` or `inference_mode()`:** gradients must flow through frozen operations back into earlier adapters and memory writes. The teacher may run inference-only.

## 6. Causality and streaming contract

The candidate must ingest source text sequentially with bounded recent KV. It may not full-prefill the entire source and then present the resulting activations as a bounded-memory streaming experiment. Full-context processing is allowed only for the separately accounted teacher/reference.

For P0–P2, use a token-serial reference path. Preserve pinned sinks and at most `local_recent_tokens` other KV positions. Perform eviction at a defined step boundary and preserve logical position increments. Do not renumber old surviving tokens to their physical slots.

Each source token may read past state, contribute to current computation, and then write from that layer's pre-attention features. Later layers can depend on earlier-layer memory reads; provenance must account for that conservatively.

Persistent writes are allowed only during explicit ingestion of authorized source spans. Questions, options, gold answers, evaluator explanations, probe outputs, and generated answers never enter persistent memory in the pilot. Source text must not be encoded with future question/answer content. Query options may be supplied to the decoder as in the common baseline, but never to an offline memory-building stage.

Query at completed source-span boundaries in the first implementation. Each query uses the same pre-query source snapshot. Query scratch KV and any diagnostics are discarded afterward. Sequential interactions that intentionally alter the source history require new explicit source events.

Do not detach the ingested bank before the training query if the objective is supposed to train the write pathway. Detachment is appropriate at documented truncated-backpropagation boundaries or for evaluation snapshots, not as an accidental training shortcut.

## 7. Allocation, autograd, and operational limits

Use a simple sparse reference implementation first. Inference may update an owned dictionary of cell tensors. Training must replace state tensors with differentiable results rather than mutate tensors needed by backward. Keep the numerical read/write kernel functional.

Branching, retries, and replay must not alias mutable banks. A snapshot can be expensive in the CPU reference, but count that work separately; do not put a full dictionary/tensor clone into every ordinary read/write step.

Do not enable activation-checkpoint recomputation over side-effectful state updates in the first pass. It can write twice or produce a different forward. Add checkpointing only with explicit state replay and equivalence tests.

A capacity violation must fail atomically: no partial committed source cursor, local KV, or bank write. It must never silently evict a cell, merge arbitrary cells, or hash unrelated coordinates onto one slot. An experimental bounded-bank comparator may define such a policy explicitly, with its own identity.

The distinction between live state and trained parameters must survive save/load. New cells do not create optimizer entries. Optimizer parameter identity must remain stable as the bank grows.

## 8. Cold-start routing and learning diagnostics

Sparse addressing has a genuine cold-start problem: a read routed entirely to empty cells may provide no useful signal for moving toward a distant write. Interpolation fixes local differentiability, not global credit assignment.

Initialize read/write address outputs in an overlapping neighborhood with small, nonidentical coordinate variation. Keep update/read projections nonzero. Start with short synthetic episodes whose dependencies lie inside the full gradient horizon.

Provide a separate **oracle-address diagnostic**, using synthetic key identities only inside a clearly marked diagnostic arm. It answers whether the cell update and model interface can use correctly addressed memory. Oracle addresses must never appear in the learned-route arm or headline scores.

If needed later, a supervised address-pair warm-up may use source/query pairs from the training split only. Version it separately, report its supervision, and evaluate on disjoint keys/templates. It is not an unannounced rescue for a failed unassisted run.

Required telemetry includes per-group gradient and parameter-update norms for query/key projections, address MLP, value path, beta, output projection, and mix scale; allocation and occupancy; read/write overlap; address change on a fixed probe set; cross-example and cross-head routing variation; empty-read weight; state norms; and output dependence on memory.

Do not demand maximum routing entropy: a useful address can be sharp. Demand demonstrable learnability and task-relevant use. Check read-address perturbation, write-address perturbation, disabled memory, and shuffled memory as causal interventions. A decreasing loss with an unused or static address path does not establish learned routing.

## 9. Interfaces

Add an explicit runtime-state abstraction rather than pretending the sidecar is a `CompactedPrefixCache` or returning synthetic KV from the existing `compaction_fn` hook.

```python
@dataclass
class SGMSessionState:
    recent_kv: CompactedPrefixCache
    banks: SparseBankSet
    source_cursor: SourceCursor
    redaction_generation: int
    policy_id: str
    # Additional metadata is versioned; tensors are not serialized by dataclasses.

class SparseGrowingMemoryBackend:
    def new_state(self, config, fingerprint) -> SGMSessionState: ...
    def ingest_source(self, state, token_ids, source_ref, *, training=False): ...
    def evaluate_query(self, snapshot, prompt_ids, *, capture=False): ...
    def snapshot(self, state): ...
    def restore(self, manifest, expected_fingerprint): ...
```

The selected-layer adapter separately exposes a tensor-level read/update operation, returning new tensors and a bounded access trace. The orchestration layer handles source permissions, writes, capacity, and transactional commit.

The stateful evaluation runner needs a small arm protocol:

```text
prepare_source(source) -> opaque_snapshot
score_prompt(snapshot, prompt) -> logits, read_features, access_trace
score_continuation(snapshot, continuation) -> aligned_next_token_logits
footprint(snapshot) -> resident/cache/archive/accounting fields
```

Existing KV-only baselines get wrappers around their current runtime. SGM uses its own wrapper. Reuse metric functions without forcing unlike states into one cache class.

## 10. Provenance, visibility, and epistemic separation

Cells can receive writes from noncontiguous source spans. Do not represent their provenance by inventing one large contiguous raw range and retrieving everything in between.

Store direct-write postings in SQLite, coalesced per `(thread, layer, head, cell_coordinate, source_span)`. Suggested fields are source span/block IDs, source hash, source sequence range, write count, policy identity, and redaction generation. Index both cell-to-source and source-to-state access. Persist postings in batches, not one database commit per neural update.

A direct-write posting is a retrieval hint. It is **not complete causal lineage**: contextual activations and recurrent reads can carry older sources into later writes and recent KV. The first implementation records a conservative session influence range and invalidates the whole affected SGM session epoch on redaction.

All archive searches and expansions must filter by thread, permissions, source visibility cursor, and current redaction state before returning content. No cross-thread or future-source retrieval. A source indexed before ingestion is not automatically visible to the current query.

Preserve source kinds and trust levels. Add versioned claim/epistemic metadata where needed, such as user assertion, tool output, assistant inference, or generated summary. A generated summary must not be promoted to observed fact merely because it was archived or repeatedly retrieved. Trust labels are bookkeeping, not a model-security proof.

## 11. Persistence and invalidation

Keep a distinct SGM snapshot manifest referencing both recent-KV checkpoint material and sparse cell state. Use safetensors for tensors and canonical JSON for manifests; do not use pickle for externally supplied artifacts.

A manifest includes the base fingerprint, adapter/config hashes, state-format version, read/write-order version, router and update versions, address scale, selected layers/dimensions, source cursor, redaction generation, source hashes, recent-KV checkpoint reference, and training/certification IDs where applicable.

Both the neural bank **and recent KV affected by the adapter** must carry the SGM compatibility identity. Changing only the bank fingerprint would leave incompatible local activations reusable.

Do not make neural state a `MemoryBlock` primary representation. Retain raw/text as primary with a mandatory shadow; add an auxiliary SGM-state reference or a separate manifest keyed to the durable blocks. Do not fabricate a natural-language summary of a cell's unknowable contents to satisfy a schema.

Save/reload must preserve coordinates, state values, source cursor, logical/physical position metadata, and any state that affects decisions. Validate compatibility and redaction before hydrating neural tensors. Missing or incompatible artifacts use the ordinary substrate fallback, never a partial neural restore.

On relevant redaction: invalidate live session state, related SGM manifests, affected recent KV, retrieval postings, and derived summaries. Rebuild from allowed source text or use text-only fallback. Do not merely remove a direct posting and keep the cell: indirect influence can remain. Existing redaction semantics already recognize this problem for KV. [R8]

State is rebuildable only relative to an available compatible model/adapter/runtime and an explicit source sequence. After a policy/model change, rebuilding creates a new operational state, not guaranteed bitwise recovery of the old one.

## 12. Exact recovery: a later, independently measured stage

Do not enable recovery while first measuring backend benefit. Add it after the learned bank passes its synthetic checks.

The query-conditioned monitor is trained on the new backend's computation. Reuse capture patterns from PROBE, not old weights, thresholds, best-layer choices, or an assumed AUC. Replacing the memory mechanism changes its failure distribution. Sink-head statistics are optional features, not a universal detector.

Distinguish two labels:

```text
reference divergence: candidate answer differs from the full-context reference
actual failure: candidate answer is incorrect under an independent gold/rubric
```

They are not equivalent. Both candidate and reference can be wrong; the candidate can also improve on the reference. Report both where ground truth exists.

Capture decision features before generating the answer, such as late residual states at the last prompt token, memory read outputs, empty-read weight, source age, and bounded routing telemetry. Never give the online monitor teacher outputs, gold labels, or full-source text unavailable to the candidate.

Recovery candidates must combine:

```text
A. sources linked to the cells actually read
B. an independent query-driven search over the visible raw-source index
```

Path B is mandatory in the full recovery experiment: a router that went to the wrong place cannot be repaired solely by searching that wrong place's provenance. Compare A-only, B-only, and A+B as ablations.

For the first recovery runner, the existing naive shadow search can be used as an explicitly measured linear scan. Do not claim constant total system cost because the neural lookup is bounded. Later lexical/inverted indexes or a summary tree can replace the scan without changing archive authority.

Use a total candidate budget of 32 per round, reserving capacity for both routes. Deduplicate, enforce source visibility, rank, and expand within a total 2,048-token budget across at most two rounds. Retrieve exact original spans through archive validation; do not elevate retrieved instructions into a system role.

After expansion, replay the query from its pre-query snapshot with the exact evidence inserted before the question under the existing retrieval convention. Discard tentative query KV and logits from the previous attempt. Do not continue as though the evidence had been present all along.

Persistent SGM writes remain disabled during this replay. If evidence is unavailable or budget is exhausted, emit an explicit unresolved/abstention result in the research runner. Report coverage so abstaining on everything cannot masquerade as successful memory.

## 13. Training plan

### P0–P2 local work

Use the tiny random configuration for correctness and gradient checks. Since an untrained tiny language model is not expected to understand arbitrary natural-language questions, also provide a small synthetic task head over memory reads. Its results validate the memory mechanism only, not frozen-Qwen capability.

Provide a full-gradient short-episode mode first. Overfit a fixed small diagnostic set to test end-to-end learning, then run a separate held-out key/value and template split. Oracle-address runs, tiny task-head runs, and real frozen-LM runs must have different result labels.

### Authorized reference-model pilot, later

Train only SGM parameters. Use identical source streams and questions across baselines. Mix exact bindings, overwrite/correction, and integration tasks whose supporting sources lie beyond the local window. Include no-memory-needed examples to measure regression.

Use a versioned objective:

```text
L = gold answer NLL + lambda_KL * KL(full_context_teacher || candidate)
    + explicitly registered optional routing auxiliary terms
```

Start with equal NLL/KL weights for the proposed pilot and record any change before the next run. The coefficient is a proposed setting, not a validated optimum. Use full-vocabulary KL when feasible; reuse the repository's deduplicated teacher-support construction if truncation is necessary, and record that it is a truncated surrogate.

Score aligned target positions. Check the first predicted answer token and the final continuation boundary explicitly; a shared off-by-one bug can make two arms appear to agree. Keep teacher access offline and account for its compute separately.

For long sequences, record both state horizon and gradient horizon. Truncated backpropagation retains state but breaks distant credit assignment. A source written before a detach boundary cannot receive answer-loss gradients across that boundary. Do not claim long-horizon write training merely because the state survived. Use short-horizon curriculum/probes or an explicitly supported longer-gradient run.

Use single-device training first. If DDP is added, call the DDP wrapper itself, test cross-rank gradient/parameter equality, and record true global batch size. Do not repeat the historical `.module` synchronization failure.

## 14. Datasets and leakage controls

Partition documents, episodes, synthetic key/value families, and template families before generation or training, according to the intended generalization claim. Record hashes and actual overlap audits, not only random seeds.

Do not reuse the repeatedly inspected historical clean holdout as an untouched final test for model selection. It remains useful as a regression set. Reserve a new untouched final set before selecting architectures, thresholds, or hyperparameters; where independent data is unavailable, label the result a development result.

Source prefix, queries, gold targets, teacher traces, and tool-visible content must be separate fields. Online callbacks receive only deployment-available fields. Retain a test that deliberate injection of an oracle source ID or gold answer into a candidate callback fails validation.

Required task families:

| Family | What it isolates |
|---|---|
| Random key/value bindings beyond the local window | Exact details without easy parametric recall. |
| Repeated writes and explicit corrections | Latest valid value versus historical value, not destructive forgetting of history. |
| Similar names and nearby numbers | Binding interference and blended answers. |
| Noncontiguous multi-hop facts | Retrieval followed by integration. |
| Broad document integration | Distributional fidelity and task correctness beyond needles. |
| Deliberately wrong routing / crowded cells | Whether independent recovery works. |
| Restart, branch isolation, deletion | Operational correctness, not just answer scores. |
| Source assertions versus assistant guesses | Provenance handling without treating guesses as evidence. |
| Longer histories than training | Extrapolation, reported separately from in-distribution success. |

For synthetic extrapolation, propose source lengths 1K, 4K, 8K, 16K, and 32K tokens, using only lengths compatible with the actual runtime's position policy. Do not silently modify RoPE to make a length run. Mark unsupported points clearly.

## 15. Baselines and budget discipline

Use baselines in phases rather than launching every arm immediately.

| Arm | Purpose |
|---|---|
| Full-context frozen teacher | Quality reference; not a matched-cost baseline. |
| Local window plus pinned sinks | Minimum-cost memory-off baseline. |
| Fixed single associative bank, same adapter interface | Tests whether spatial allocation matters. |
| Fixed/random-address sparse bank, same update/interface | Tests whether learned addressing matters. |
| Learned SGM without recovery | Isolates the neural backend. |
| Archive retrieval without SGM | Tests whether ordinary recovery does all useful work. |
| Learned SGM plus calibrated recovery | Full system. |
| Existing compactor/merge artifacts, research-only | Historical comparisons, only with compatible provenance and rerun conditions. |

Keep two comparison panels:

**Matched-access panel:** fix local context, head dimensions, and accessed cells; allow allocated storage to vary. This tests access/capacity decoupling, not equal-memory superiority.

**Matched-storage panel:** compare total resident numerical bytes, including local KV and extra state; identify tolerances and unmatched costs. This tests quality at a storage budget. Trained parameter counts and compute must also be disclosed.

A fourfold larger bank is not free. Raising `max_cells` does not by itself create useful capacity: report cells actually allocated, written, and subsequently read, not just the configured ceiling. An unbounded coordinate space does not guarantee that a trained router learns to explore or use it. A frozen dense transformer with a sidecar is not automatically as fast as a native sparse-memory model. Measure the actual implementation.

## 16. Evaluation and certification

Implement a new stateful-arm runner and reuse the two-axis reporting principle. Do not label sidecar-cell count as a KV eviction fraction or claim equal retained-vector budgets across unlike state representations.

### Mandatory output groups

**Distribution/integration:** teacher-to-candidate KL on registered continuation windows, gold integration accuracy, accuracy delta, and per-domain results. Label legacy short-continuation KL separately from extended generation diagnostics.

**Pointwise:** overall answer accuracy, wrong answers among reference-correct queries, legacy silent loss without expansion, wrong answers despite expansion, and final unresolved/abstention counts. Record numerator and denominator for each rate; use null/undefined rather than invented zero when a denominator is empty.

**Recovery:** candidate-source recall when support is known, expanded tokens, bytes, rounds, latency, error versus retrieval-budget frontier, monitor AUROC/AUPRC, calibration, false negatives, and coverage. A high AUC alone does not establish a good operating point.

**Scaling:** allocated/resident cells, neural bytes, recent-KV bytes, metadata/posting bytes, adapter parameters, cells read/written per token, allocation failures, prefill/ingestion time, p50/p95 query latency, checkpoint cost, and replay cost. Separate teacher/training cost from candidate inference cost.

Bootstrap paired differences at document/episode level, not as independent tokens or repeated questions from the same source. Report multiple training seeds for the reference pilot; three is the proposed minimum. Keep per-example traces and source IDs so failures are auditable.

Preserve historical certification and NO-SHIP verdicts. SGM requires a new certificate describing its tested history lengths, local window, cell budgets, update counts, recovery policy, and data distribution. Do not reuse `max_certified_depth` as an unbounded-memory guarantee.

### Preregistered decision rules

P0–P2 success means engineering correctness and a clearly labeled learning demonstration, not deployment readiness.

Before a paid pilot, commit a registration file defining its primary task set, primary comparator, seeds, byte/access budgets, accuracy non-inferiority margin, KL rule, and stop conditions. For an exploratory synthetic screen, use a proposed minimum 5-percentage-point exact-answer gain over the stronger of the local-only and fixed/random-address controls on old-information queries, with a paired interval excluding zero. Treat this as a screening rule, not a general scientific constant.

For a production-like house comparison, retain at least the existing strict distinction between pointwise gain and distributional acceptability: a pointwise win does not override a failed registered KL/accuracy gate. An inconclusive interval is not a pass. Any relaxed criterion needs a new explicit registration, not a post-hoc relabeling.

A recovery result is useful only if actual final error improves at matched retrieval budget/coverage, or recovery cost falls at matched actual error. A scaling claim requires unchanged access limits, explicit additional storage accounting, and measured quality at each length.

## 17. Required tests

Use `SGM-*` identifiers rather than reusing occupied golden-test numbers. Preserve all existing tests.

| ID | Acceptance test |
|---|---|
| SGM-01 | Disabled adapter reproduces the original tiny runtime and does not mutate source state. |
| SGM-02 | Interpolation weights are nonnegative, sum to one, are continuous across stencil changes, and pass finite differences away from boundaries. |
| SGM-03 | Address gradients reach both read and write projections in a constructed nonempty case; optimizer parameter identities remain unchanged after allocation. |
| SGM-04 | Only addressed cells change; absent reads do not allocate; coordinates support negatives and distant sparse positions. |
| SGM-05 | Read-before-write and causal masking prevent reading current/future writes. Later source suffixes cannot alter earlier outputs. |
| SGM-06 | Delta update matches a small explicit reference; repeated binding, new value, and independent keys exercise overwrite/interference behavior. |
| SGM-07 | Candidate local KV stays bounded, sinks survive, and logical/physical positions agree with the intended serial reference. |
| SGM-08 | No query, option, target, evaluator label, or generated answer becomes a persistent write. |
| SGM-09 | Session reset, query fork, and retry have no cross-session or cross-query state leakage. |
| SGM-10 | Save/reload yields equivalent next-token behavior; any relevant fingerprint mutation rejects both bank and influenced KV. |
| SGM-11 | Redaction invalidates indirect influence, not just direct cell postings; stale live state cannot be read. |
| SGM-12 | A forced wrong-address case remains recoverable through the independent archive path when evidence exists. Later-stage test. |
| SGM-13 | Recovery respects permissions, source cursor, token budget, and round budget; replay starts before the query. Later-stage test. |
| SGM-14 | A wrong answer after retrieval increments final-error metrics; a dummy expand call cannot erase an error. |
| SGM-15 | Student gradients reach adapters through frozen layers; backbone gradients/weight changes remain absent. |
| SGM-16 | Per-token neural reads/writes remain bounded when distant cell count increases; no hidden full-bank copy or scan. |
| SGM-17 | Capacity overflow leaves no partially committed bank, source cursor, or KV update. |
| SGM-18 | Teacher/student target alignment catches first-token and continuation-boundary off-by-one errors. |
| SGM-19 | Tiny synthetic task-head overfit and held-out results are distinct from real frozen-LM results and oracle-routing diagnostics. |
| SGM-20 | Policy-changed gate/certificate is rejected; absence of a certificate never enables a deployment default. |

Do not weaken tests to accommodate an architecture mistake. For a stage not yet implemented, report its test as not implemented rather than passing it with a stub.

## 18. Suggested file layout and implementation phases

```text
M4-SGM.md
M4-SGM-IMPLEMENTATION-REPORT.md
configs/m4_sgm_tiny.json
configs/m4_sgm_reference.json
memsub/sgm/
    config.py
    interpolation.py
    sparse_cell_bank.py
    delta_memory.py
    layer_adapter.py
    session_state.py
    provenance_index.py
    snapshot_store.py
memsub/runtime/sgm_model_runtime.py
memsub/certification/stateful_memory_arm.py
memsub/certification/sgm_evaluation.py
examples/sgm_tiny_demo.py
scripts/sgm_synthetic_pilot.py
tests/test_sgm_*.py
```

Add modules only when their stage requires them. Do not introduce an empty class for every future concept.

| Phase | Deliverable | Stop condition |
|---|---|---|
| P0 — compatibility audit | Starting-commit report, resolved config, baseline tests, adapter-off equivalence. | No unrelated behavior change. |
| P1 — sparse core | Interpolation, delta cells, access accounting, causal/autograd/capacity tests. | Failure of learning-path or sparsity checks blocks integration. |
| P2 — local model integration | Tiny frozen-backbone wrapper, bounded streaming, source/query separation, snapshot isolation, synthetic task-head pilot. | Report learned, oracle, and untrained-LM results separately. No cloud execution. |
| P3 — reference pilot | Explicitly authorized frozen-Qwen training and registered backend-only comparisons. | Stop on dead routing, unused memory, or failed screening. |
| P4 — recovery and certification | Policy-specific probe training, independent archive retrieval, redaction-safe persistence, house evaluations. | No gate/certification inheritance; no shipping on a single-axis win. |
| P5 — optional hierarchy/retention | Independently tested summary tree and retention/allocation ablations. | Requires an established backend/system baseline. |

The first Codex pass should make P0–P2 executable and document the later interfaces. It must not report P3–P5 complete because launch scripts or placeholder methods exist.

## 19. Complexity and memory accounting

With `L_s` selected layers and `H_s` memory heads, each token performs at most `9 * L_s * H_s` cell reads and, for source tokens, the same number of cell writes. Read and write addresses may differ; do not call their combined work “nine cells total.”

For the proposed four-layer/four-head setting, that is up to 144 reads and 144 writes per source token. The per-cell arithmetic is proportional to `d_key * d_value`.

Neural state bytes are:

```text
sum_over_layer_head(N_cells[layer,head] * d_key * d_value * bytes_per_element)
```

At the proposed maximum of 1,024 cells in each of 16 banks and FP32 32×32 matrices, matrices alone occupy 64 MiB. This is derived arithmetic, not measured process memory. Local KV, adapters, activations, dictionary overhead, postings, checkpoints, and raw storage are additional.

Expected hash lookup cost and fixed access count are not a universal constant-latency guarantee. Allocation, synchronization, memory hierarchy, snapshotting, and Python overhead must be profiled. The reference serial implementation is for correctness and measurement, not a claim of production throughput.

The archive/provenance store grows with source history. Retrieval and replay may be expensive. Every report must distinguish bounded **neural lookup** from total system work.

## 20. Optional extensions after the base experiment

### Hierarchical summaries: the OptMem-like component

Build a derived summary tree over durable source spans, with child IDs, source coverage, source hashes, and invalidation dependencies. Leaves point to existing raw source. Summaries are rebuildable caches, not replacement truth.

Use the tree as an additional navigation/candidate source for recovery. It is not required for SGM reads or writes. Compare flat retrieval, hierarchy-only retrieval, and combined retrieval at matched returned-token budgets and actual final error.

Do not claim equivalence to the unavailable Gist or import an external installer automatically. A source/licensing review is required before copying external code.

### Importance-based retention: the Memory Gravity component

Treat “gravity” as a proposed measurable policy over residency/allocation/recovery priority, not a magic semantic field. Candidate features include prior usefulness, recurrence, unresolved corrections, and estimated access cost.

Begin with metadata-only scoring and a controlled ablation against recency, frequency, and random controls. Do not alter learned coordinates, merge cells, or move cell contents without a defined migration/replay protocol. Changing residency is different from changing semantic addresses.

Never let an importance policy drop provenance, bypass deletion, or suppress retrieval of exact contradictory evidence. Utility must be measured on later queries, not inferred from how meaningful an anchor appears.

### Glyphs and procedures

Defer both. A glyph can later be an explicit anchor to source IDs; it is not evidence that compressed state retains the sources. Extracting executable skills introduces a separate validation/security problem and is outside this memory experiment.

## 21. Result artifacts and final handoff

Each actual run should emit:

```text
run_manifest.json             # code/config/model/policy IDs and resource use
split_manifest.json           # source/item/template partitions and overlap audit
routing_telemetry.jsonl       # bounded traces and gradient/mobility diagnostics
per_example_results.jsonl     # raw predictions, labels, support and recovery info
metrics.json                  # separate axes, final errors, coverage, budgets
report.md                     # decisions, limits, regressions, next evidence needed
```

Tensor/checkpoint files live in a distinct versioned experiment namespace. Do not overwrite historical `memsub-artifacts` results or assume missing remote corpora are mounted locally. Provide a synthetic fallback and identify unavailable artifacts explicitly.

Proposed local commands, to be created by this work:

```bash
uv run pytest tests/ -q
uv run python examples/sgm_tiny_demo.py
uv run python scripts/sgm_synthetic_pilot.py --config configs/m4_sgm_tiny.json
```

The final Codex report must state files changed, tests actually executed, the resolved local environment, measured synthetic results, training-path/gradient evidence, remaining unimplemented stages, and whether any baseline behavior changed. Never invent a GPU run, timing, certification, or success claim.

**Desired outcome of the first pass:** an auditable experimental implementation that can distinguish “the memory learned,” “the interface can read correctly addressed memory,” and “the archive rescued an otherwise failing model.”

## 22. Source and verification record

Repository source references below were inspected at the commit named at the top. Historical experiment results are reported by the repository; they were not rerun while preparing this brief. New algorithms, interfaces, default settings, and acceptance proposals in this document are design recommendations.

- **[R1]** `docs/system-architecture.md`: durable/cache split, module map, policy-scoped probes, position and redaction invariants.
- **[R2]** `memsub/schemas/memory_block.py`: primary representation and mandatory embedding-shadow constraints.
- **[R3]** `memsub/runtime/hf_model_runtime.py`: inference-only helpers, custom continuation, logical/physical positions.
- **[R4]** `memsub/selection/runtime_gated_expand.py`: contiguous-span expansion and current similarity-threshold runtime gate.
- **[R5]** `memsub/certification/offline_certification_harness.py`: KV-only interface, separate metrics, silent-loss denominator and post-expansion exclusion.
- **[R6]** `E1FULL-REPORT.md`, clean replacement section: NO-SHIP, `max_certified_depth=0`, paired pointwise/distributional results.
- **[R7]** `pyproject.toml`: pinned environment and local/reference split.
- **[R8]** `memsub/redaction_graph_invalidator.py`: derived-from closure and conservative contextual-KV invalidation.
- **[R9]** Percepta, *Spotlight Memory*, dated October 2, 2026. High-level motivation only; technical-body retrieval was incomplete during preparation.

Canonical repository source URL pattern:

```text
https://github.com/loveless2001/memory/blob/f67ff34d643fad7014f587c1ed4526cefe8ee34a/<path>
```

External inspiration supplied by the user:

```text
https://www.percepta.ai/blog/spotlight-memory
https://gist.github.com/VictorTaelin/91837951a5ce5b38f341ec1ba1df6449
```

Before extending beyond P2, also reread the current `unified_memory_substrate_spec_v0.3.7.md`, `BUILD.md`, `ESCAPE-REPORT.md`, PROBE/FOLLOWUP reports, clean E1FULL artifacts, and relevant tests. Historical probe or merge findings must not be extrapolated into performance guarantees for this backend.