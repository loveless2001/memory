# MergeCert Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port attention-weighted KV merging onto the house Qwen3
certification harness, execute the pre-registered P0/Q1/Q2/Q3 campaign, and
produce the private `MERGECERT-REPORT.md` for Tyler and Kevin.

**Architecture:** A pure, testable merge engine builds exact-budget
sink/summary/recent layouts and merges each layer/KV head with real accumulated
attention mass. Modal runners reuse the clean M1 holdout and standard
30,847-item probe manifest, capture real prefill attention online, and emit
resumable private-volume artifacts. Repo-side analyzers bind every reported
number to copied JSON/NPZ evidence and enforce the P0 stop condition before
Q1-Q3 can launch.

**Tech Stack:** Python 3.12, PyTorch 2.7.1, Transformers 4.55.2, NumPy,
scikit-learn in analysis images, pytest 8.3.4, Modal H100/L4.

## Global Constraints

- Base model: `Qwen/Qwen3-4B-Instruct-2507`, bf16, greedy letter-argmax,
  house compatibility fingerprint pinned.
- Upstream method: `jkdkr2439/KV-Merge` commit
  `cd4ed948d62231449dbab9669608bbb4fd220713`; record README and implementation
  hashes in every campaign manifest.
- Use real accumulated causal attention from the house model, reduced from
  query heads to their grouped KV head; never use the upstream KV-dot-product
  approximation.
- Pin logical positions 0-3 as exact sinks for merge, eviction, and
  StreamingLLM arms.
- Retained-vector budgets must exactly equal
  `4096 - int(4096 * fraction)`: 3072 at 0.25, 2458 at 0.40, and 410 at 0.90.
- Preserve the upstream real-benchmark split: after reserving four sinks, half
  of the retained non-sink budget is recent exact KV and half is summary KV.
  Partition the old region into exactly that many balanced contiguous blocks;
  singleton blocks at the 0.25 point are explicit carry-through summaries.
- No training, hyperparameter sweep, cross-model comparison, deployment
  certification, L3-default claim, or public artifact.
- P0.3 is a hard gate: if the registered 200-item direction check fails, stop
  all Q1-Q3 launches and write the negative report.
- All new result artifacts stay under private Modal volume
  `/artifacts/mergecert/` and are copied only into local
  `plans/260727-mergecert/`; do not push or publish them.

---

### Task 1: Exact-budget attention-weighted merge engine

**Files:**
- Create: `memsub/compaction/attention_weighted_kv_merge.py`
- Modify: `memsub/compaction/__init__.py`
- Test: `tests/test_attention_weighted_kv_merge.py`

**Interfaces:**
- Produces:
  `build_merge_plan(sequence_length: int, eviction_fraction: float,
  sink_token_count: int = 4) -> MergePlan`;
  `merge_cache(cache: CompactedPrefixCache, attention_mass: torch.Tensor,
  plan: MergePlan) -> MergeResult`;
  `mechanics_features(plan: MergePlan, attention_mass: torch.Tensor,
  needle_positions: Sequence[int]) -> MergeMechanics`.
- `attention_mass` has shape `[layers, kv_heads, sequence_length]`.
- `MergeResult.cache.physical_length` equals `plan.target_retained` exactly;
  its physical layout is `[exact sinks][block summaries][exact recent]`.

- [x] **Step 1: Write exact-budget plan tests**

```python
@pytest.mark.parametrize(
    ("fraction", "retained"), [(0.25, 3072), (0.40, 2458), (0.90, 410)]
)
def test_merge_plan_exactly_matches_house_budget(fraction, retained):
    plan = build_merge_plan(4096, fraction)
    assert plan.target_retained == retained
    assert 4 + plan.summary_count + plan.recent_count == retained
    assert plan.blocks[0].start == 4
    assert plan.blocks[-1].end == 4096 - plan.recent_count
    assert sum(b.size for b in plan.blocks) == 4096 - 4 - plan.recent_count
```

- [x] **Step 2: Run the plan tests and verify they fail**

Run:
`./.venv/bin/python -m pytest tests/test_attention_weighted_kv_merge.py -q`

Expected: collection failure because the merge module does not exist.

- [x] **Step 3: Implement immutable plan and diagnostics dataclasses**

Implement `MergeBlock`, `MergePlan`, `MergeMechanics`, and `MergeResult`.
Use `divmod(old_count, summary_count)` to create ordered blocks whose sizes
differ by at most one. Reject fractions outside `(0, 1)`, caches shorter than
the sink prefix, and budgets that cannot retain every sink.

- [x] **Step 4: Add weighted-KV behavior tests**

Build a two-layer synthetic `CompactedPrefixCache` with scalar K/V values and
attention mass that selects opposite endpoints in one block. Assert:

```python
assert result.cache.layer_kv(0)[0][0, 0, summary_slot, 0] == 20.0
assert result.cache.layer_kv(0)[1][0, 0, summary_slot, 0] == 200.0
assert result.cache.layer_kv(1)[0][0, 0, summary_slot, 0] == 10.0
assert result.cache.logical_positions[:4] == [0, 1, 2, 3]
assert result.cache.logical_positions[-plan.recent_count:] == list(
    range(4096 - plan.recent_count, 4096)
)
```

Also assert zero-mass blocks use a uniform mean, input tensors remain
unchanged, and sink/recent tensors remain bitwise equal.

- [x] **Step 5: Implement merge execution and mechanics features**

Accumulate weighted K/V in float32, normalize per layer/KV head within each
block, and cast back to the cache dtype. Assign each summary slot the final
logical position of its source block only as metadata; do not re-rotate the
already-RoPE-applied K vectors. Mechanics features use the located needle
tokens (or recorded fallback position): block size, needle attention-mass
share, `1 - H(mass)/log(block_size)` heterogeneity, and normalized distance
from the block end to the recent-window boundary.

- [x] **Step 6: Run focused and cache-regression tests**

Run:

```bash
./.venv/bin/python -m pytest tests/test_attention_weighted_kv_merge.py \
  tests/test_compacted_cache_position_math.py tests/test_gt2_sink_invariant.py -q
```

Expected: all pass.

- [x] **Step 7: Commit the merge engine**

```bash
git add memsub/compaction/attention_weighted_kv_merge.py \
  memsub/compaction/__init__.py tests/test_attention_weighted_kv_merge.py
git commit -m "feat: add exact-budget attention-weighted KV merge"
```

### Task 2: Real-attention collection with bounded GPU memory

**Files:**
- Create: `memsub/compaction/real_attention_mass.py`
- Modify: `memsub/compaction/__init__.py`
- Test: `tests/test_real_attention_mass.py`

**Interfaces:**
- Consumes eager-attention tensors shaped `[batch, query_heads, query, key]`.
- Produces:
  `reduce_gqa_attention(attention: torch.Tensor,
  num_key_value_heads: int) -> torch.Tensor` shaped
  `[batch, kv_heads, key]`;
  `prefill_with_real_attention(runtime: HFModelRuntime,
  token_ids: list[int]) -> tuple[CompactedPrefixCache, torch.Tensor,
  torch.Tensor]`.

- [ ] **Step 1: Write GQA reduction tests**

Use eight query heads and two KV heads with distinct constant masses. Verify
that heads 0-3 reduce to KV head 0, heads 4-7 to KV head 1, causal query rows
sum into received mass, and the returned shape is `[1, 2, key]`.

- [ ] **Step 2: Run the tests and verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_real_attention_mass.py -q`

- [ ] **Step 3: Implement online layer hooks**

Temporarily switch Qwen attention to `eager`; register one forward hook on
each `self_attn`. Each hook reduces `output[1]` immediately into
`[kv_heads, sequence]`, stores only that result, and returns
`(output[0], None)` so the full quadratic attention tensor is not retained in
the model output. Restore every hook and the prior attention implementation in
a `finally` block. Return the normal house `CompactedPrefixCache` plus stacked
mass `[layers, kv_heads, sequence]`.

- [ ] **Step 4: Add failure-restoration and shape tests**

Use fake attention modules to assert hook removal and mode restoration after
both success and a raised exception. Assert a mismatched query/KV-head count
fails closed.

- [ ] **Step 5: Run focused and full local tests**

Run:

```bash
./.venv/bin/python -m pytest tests/test_real_attention_mass.py \
  tests/test_attention_weighted_kv_merge.py -q
./.venv/bin/python -m pytest tests -q
```

- [ ] **Step 6: Commit real-attention collection**

```bash
git add memsub/compaction/real_attention_mass.py memsub/compaction/__init__.py \
  tests/test_real_attention_mass.py
git commit -m "feat: collect real GQA attention mass for KV merging"
```

### Task 3: P0 smoke, direction gate, and degeneracy audit

**Files:**
- Create: `modal-runners/modal-mergecert-p0-q1.py`
- Create: `plans/260727-mergecert/analyze-mergecert-p0.py`
- Create: `plans/260727-mergecert/source-provenance.json`
- Test: `tests/test_mergecert_campaign_contract.py`

**Interfaces:**
- Modal functions:
  `smoke(limit: int = 8) -> dict`;
  `p0_direction(n_items: int = 200) -> dict`;
  `q1_certify(...) -> dict` (Task 4 calls this only after P0 passes).
- Private artifacts:
  `/artifacts/mergecert/p0-smoke.json`,
  `/artifacts/mergecert/p0-direction-200.json`.

- [ ] **Step 1: Write static campaign-contract tests**

Assert the runner pins the upstream commit and hashes, ratios
`(0.25, 0.40, 0.90)`, sink count 4, model ID, fixed RNG seed, P0 sample size
200, and private output root. Assert no training function, optimizer, public
upload, or alternate model ID appears.

- [ ] **Step 2: Implement a resumable P0 runner**

Select 50 deterministic raw-correct items per domain from the standard probe
manifest whose located needle lies in the merge-old region at 0.90. For each
item, perform one real-attention prefill and compare full, exact-budget
oldest-nonsink eviction, exact-budget merge, and exact-budget
StreamingLLM-style sink+recent arms. Record greedy predictions and paired KL
over the fixed continuation text `" The discussion continued."`.

- [ ] **Step 3: Register the P0.3 pass predicate**

The direction reproduces only if, among full-context-prior-correct items,
merge has lower lost-fact rate than eviction and the paired
`merge - eviction` 95% document-cluster bootstrap interval lies below zero.
Report accuracy delta and KL as secondary house metrics; they cannot reverse
the registered pointwise gate.

- [ ] **Step 4: Register the P0.4 non-degeneracy predicate**

Report:

- exact-slot Jaccard between merge and StreamingLLM;
- number and size distribution of non-singleton merge blocks;
- fraction of MCQ predictions identical;
- paired continuation-KL difference;
- maximum absolute K/V difference on aligned exact slots.

Pass only if at least one non-singleton block exists, exact-slot Jaccard is
below 1, and the merged old region is not tensor-identical to the
StreamingLLM cache.

- [ ] **Step 5: Run an 8-item H100 smoke**

Run:
`UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run
modal-runners/modal-mergecert-p0-q1.py::smoke --limit 8`

Verify exact physical lengths `{0.25: 3072, 0.40: 2458, 0.90: 410}`, finite
mass and outputs, nonzero real-attention variance, and peak memory below the
H100 limit.

- [ ] **Step 6: Run and retrieve the 200-item P0 gate**

Run detached, wait for terminal completion, copy the JSON into
`plans/260727-mergecert/`, and run:

```bash
./.venv/bin/python plans/260727-mergecert/analyze-mergecert-p0.py
```

If P0.3 fails, skip Tasks 4-7 and execute Task 8’s negative-report branch.

- [ ] **Step 7: Commit P0 code and evidence**

```bash
git add modal-runners/modal-mergecert-p0-q1.py \
  plans/260727-mergecert tests/test_mergecert_campaign_contract.py
git commit -m "feat: add MergeCert P0 direction and degeneracy gates"
```

### Task 4: Q1 two-axis matched-budget certification

**Files:**
- Modify: `modal-runners/modal-mergecert-p0-q1.py`
- Create: `plans/260727-mergecert/analyze-mergecert-q1.py`
- Test: `tests/test_mergecert_campaign_contract.py`

**Interfaces:**
- Reuses the citable 20-context M1 protocol of record in
  `/artifacts/corpus-certification-full/` and the unchanged
  `OfflineCertificationHarness` metric semantics. The clean compactor holdout
  remains the source of the frozen/unfrozen reference rows only; it is not
  substituted for the brief's existing 0.25/0.40 eviction rows.
- Writes `/artifacts/mergecert/q1-certification.json`, containing per-document
  reports, paired CIs, source/reference-report hashes, exact budgets, and all arm
  summaries.

- [ ] **Step 1: Add Q1 provenance and arm tests**

Assert the Q1 artifact schema requires merge 0.25/0.40/0.90,
eviction 0.25/0.40/0.90, and control-0 rows; all reports carry selected
document and item IDs, corpus hashes, and the archived M1 report hashes.

- [ ] **Step 2: Implement the Q1 certification loop**

Reconstruct the exact four-domain × five-context partition from the archived
M1 reports and current hashed corpus. Before measuring merge, replay
control/0.25/0.40 eviction and require the per-probe predictions and aggregate
metrics to match the archived rows. For every verified context, prefill once
with real attention. Run the three merge ratios, three same-budget contiguous
eviction rows, and zero-control through the same KL, aggregation MCQ, and
pointwise needle scoring code used by M1. Preserve the archived reference
needle window, per-axis denominators, and greedy scoring; compute paired
document-cluster bootstrap CIs against same-ratio eviction for every merge
row.

- [ ] **Step 3: Run a two-document Q1 smoke**

Verify every arm uses the same context and item partitions, control KL and
accuracy delta are zero, and retained-vector counts are exact.

- [ ] **Step 4: Run full Q1 only after P0 pass**

Launch detached, monitor to completion, confirm no live tasks remain, retrieve
`q1-certification.json`, and run the analyzer to produce
`q1-verdict.json` and a Markdown table fragment with CIs. The 0.25/0.40
eviction cells remain labeled as archived existing rows; the 0.90 eviction
cell is a new registered comparator for the graceful-degradation reading.

- [ ] **Step 5: Commit Q1 evidence**

```bash
git add modal-runners/modal-mergecert-p0-q1.py \
  plans/260727-mergecert/analyze-mergecert-q1.py \
  plans/260727-mergecert/q1-*.json
git commit -m "docs: record MergeCert matched-budget placement"
```

### Task 5: Q2 unified merge relabel and capture fleet

**Files:**
- Create: `modal-runners/modal-mergecert-q2-capture.py`
- Modify: `tests/test_mergecert_campaign_contract.py`

**Interfaces:**
- Consumes `/artifacts/probe/capture-manifest.json` (30,847 items), existing
  raw predictions, shadow embeddings, and corpus texts.
- Writes resumable per-slice state and NPZ files under
  `/artifacts/mergecert/q2/` for ratios 0.25 and 0.40.
- Per ratio output: merge prediction/label, mechanics features `[N,4]`,
  sink-head features `[N,8]`, last-prompt residuals `[N,37,2560]`, item/doc
  IDs, domain, raw-correct, and `in_e1`.

- [ ] **Step 1: Add output-schema and resume-contract tests**

Assert shard state contains a completed count and row IDs; NPZ arrays must
have equal first dimensions, unique item IDs, finite values, and explicit
ratio/source hashes.

- [ ] **Step 2: Implement one-prefill/two-ratio capture**

Rebuild each manifest context exactly as the existing probe runner. Locate
the gold answer token span inside its 1,024-token source chunk, falling back
to the chunk midpoint with `needle_locator_found=0`. One real-attention
prefill feeds both ratio merges. For each ratio, run the question-conditioned
answer pass, capture the four registered sink heads
`(25,14),(26,26),(28,19),(35,15)` over merged-memory and sink regions, and
store the 37 last-token residual vectors.

- [ ] **Step 3: Run a 16-item pilot and validate labels**

Compare repeated pilot runs for bit-identical greedy labels, exact budgets,
valid mechanics ranges, and no eager/SDPA argmax drift.

- [ ] **Step 4: Launch the fixed capture fleet**

Use a fixed number of H100 slices with no adaptive tuning. Monitor per-slice
counts and app/task state until all 30,847 unique items exist for both ratios.
Retry only preempted/corrupt shards from their resume state.

- [ ] **Step 5: Validate and freeze the capture manifest**

Write `/artifacts/mergecert/q2/capture-summary.json` with shard hashes, item
coverage, positive rates, per-domain counts, locator rate, and actual compute
duration. Copy only summary/small evidence locally; keep multi-GB residual
shards on the private volume.

- [ ] **Step 6: Commit the Q2 capture runner**

```bash
git add modal-runners/modal-mergecert-q2-capture.py \
  tests/test_mergecert_campaign_contract.py
git commit -m "feat: add MergeCert routability capture fleet"
```

### Task 6: Q2 routability probes and F5 fifth-regime row

**Files:**
- Create: `modal-runners/modal-mergecert-q2-probes.py`
- Create: `plans/260727-mergecert/analyze-mergecert-q2.py`
- Test: `tests/test_mergecert_analysis.py`

**Interfaces:**
- Writes `/artifacts/mergecert/q2/routability.json` and
  `/artifacts/mergecert/q2/scores.npz`.
- Reports surface/c0, merge mechanics, shadow gate zero-shot/refit,
  sink-monitor zero-shot/refit, and best-layer residual linear/MLP refits on
  the existing SHA-256 document split.

- [ ] **Step 1: Write metric and split tests**

Use synthetic grouped data to test tie-aware AUC, document-disjoint
train/validation/test masks, document-cluster bootstrap CIs, and zero-shot
standardization using source-regime means/scales.

- [ ] **Step 2: Implement aligned feature assembly**

Join Q2 shards to existing surface features/fact types and shadow embeddings
by item ID. Never use labels or test rows for imputation, scaling, layer
selection, or calibration. Evaluate each ratio separately and a
pre-registered pooled ratio model with ratio as a covariate.

- [ ] **Step 3: Implement the five registered arm families**

- c0: refit the existing ten-feature surface model.
- mechanics: four new merge features only, three seeds.
- shadow: apply the existing eviction gate checkpoint zero-shot, then refit
  the same architecture on merge labels.
- sink monitor: fit source compactor and eviction monitors from their existing
  captures for two zero-shot rows, then refit the eight-scalar logistic.
- residual: validation-selected best layer linear probe and 256-hidden MLP,
  three seeds.

Report test AUC, document-cluster CI, per-domain AUC, sample/base rates, and
the fixed readings from `MERGECERT.md` without turning them into tuning
criteria.

- [ ] **Step 4: Run the probe job and retrieve compact evidence**

Run on L4, retrieve `routability.json` and scores for the E1 2k subset. The
F5 fifth-regime row must include merge refit plus compactor→merge and
eviction→merge zero-shot AUCs at 0.25 and 0.40.

- [ ] **Step 5: Run local independent analysis**

Recompute headline AUCs from `scores.npz`, verify them against the remote JSON
within `1e-6`, and emit `q2-verdict.json` plus the report table fragment.

- [ ] **Step 6: Commit Q2 analysis and evidence**

```bash
git add modal-runners/modal-mergecert-q2-probes.py \
  plans/260727-mergecert/analyze-mergecert-q2.py \
  plans/260727-mergecert/q2-*.json tests/test_mergecert_analysis.py
git commit -m "docs: record MergeCert routability placement"
```

### Task 7: Q3 fragility nesting on the E1 protocol

**Files:**
- Create: `plans/260727-mergecert/analyze-mergecert-q3.py`
- Modify: `tests/test_mergecert_analysis.py`

**Interfaces:**
- Uses the 2,000 rows with `in_e1=1` at merge ratio 0.40 and the existing
  A/B/FR/E1F relabel artifacts.
- Writes `plans/260727-mergecert/q3-fragility.json`.

- [ ] **Step 1: Add κ and nesting tests**

Test Cohen’s κ against hand-computed confusion matrices and define directional
nesting as `|failure_merge ∩ failure_ref| / |failure_merge|`. Require every
comparison to report both instances’ base rates, raw agreement, intersection,
novel-merge count, and denominator.

- [ ] **Step 2: Retrieve the four reference relabels**

Copy A/B/FR/E1F private-volume state files into a temporary local directory,
verify exactly 2,000 aligned unique IDs, and hash them in the Q3 provenance
block. Do not duplicate the large files into the final report bundle.

- [ ] **Step 3: Compute Q3 at the fixed 0.40 merge ratio**

Report merge base rate; κ and directional nesting against A, FR, and E1F;
per-domain cells; marginal-aware interpretation; and the minority of
merge-specific failures. B remains a within-lineage context row, not one of
the brief’s three headline comparisons.

- [ ] **Step 4: Commit Q3 evidence**

```bash
git add plans/260727-mergecert/analyze-mergecert-q3.py \
  plans/260727-mergecert/q3-fragility.json tests/test_mergecert_analysis.py
git commit -m "docs: record MergeCert fragility nesting"
```

### Task 8: Private report, artifact audit, and delivery handoff

**Files:**
- Create: `MERGECERT-REPORT.md`
- Create: `plans/260727-mergecert/artifact-manifest.json`
- Create: `plans/260727-mergecert/validate-mergecert-report.py`
- Modify: `docs/project-changelog.md` only after private delivery is confirmed.
- Test: `tests/test_mergecert_report.py`

**Interfaces:**
- The validator maps every required P0/Q1/Q2/Q3 report cell to an artifact
  path and JSON key, verifies hashes/counts/CIs, and rejects placeholders,
  public URLs, unsupported source-model numbers, or deployment claims.

- [ ] **Step 1: Write report-completeness tests**

Require the report header’s method-at-its-best framing; P0 real-attention
upgrade and sink addition; Q1 all reference/merge/control rows with CIs; Q2
all five arm families plus F5; Q3 κ/nesting/base rates; exact sections
`For the KV-Merge README` and `For the spec`; compute actuals; limitations;
and Tyler/Kevin private-delivery marking.

- [ ] **Step 2: Implement the artifact validator**

The validator loads all small evidence files, checks every table number against
its source value, proves ratios/budgets/sample counts, confirms P0 passed (or
selects the negative-report schema), and writes a SHA-256 manifest. It fails
on question-mark result cells, unfinished-marker strings, public upload links,
Qwen2.5 result rows, or claims that merge is deployment-certified.

- [ ] **Step 3: Write the evidence-backed private report**

State outcomes without changing the registered readings. The README section
must separate supported claims (with CIs) from unsupported claims kindly and
precisely. The spec section drafts §13.7 only if Q1/Q2 justify the fourth
training-free point; otherwise it drafts the measured negative placement.
Do not modify the public spec or papers in this campaign.

- [ ] **Step 4: Run complete verification**

Run:

```bash
./.venv/bin/python plans/260727-mergecert/validate-mergecert-report.py
./.venv/bin/python -m pytest tests -q
git diff --check
git status --short
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal app list
```

Expected: validator and all tests pass, no Modal tasks remain, and no
unexplained worktree changes exist.

- [ ] **Step 5: Prepare private delivery**

Keep report and evidence local/private. Present the exact report path and
artifact manifest to the user and request or use the user-approved private
channel for Tyler and Kevin. Do not push, publish, edit public papers/spec, or
update the changelog before delivery confirmation.

- [ ] **Step 6: Record delivery and commit final local state**

After Tyler/Kevin delivery is confirmed, add the dated delivery record to the
report header and project changelog, rerun the validator/tests, then commit:

```bash
git add MERGECERT.md MERGECERT-REPORT.md docs/project-changelog.md \
  plans/260727-mergecert docs/superpowers/plans/2026-07-27-mergecert-campaign.md
git commit -m "docs: complete private MergeCert placement campaign"
```
