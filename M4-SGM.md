# M4-SGM — Sparse Growing Memory (research-only)

Status: **P0–P2 IN PROGRESS** (started 2026-10-05). Authorized in #gravity
msg 21068 ("commit the changes first then go, use modal for compute").
Design brief: [plans/261005-0210-m4-sgm-p0-p2/m4-sgm-design-spec-v0.1.md](plans/261005-0210-m4-sgm-p0-p2/m4-sgm-design-spec-v0.1.md).
Reviews: claude msg 21059 / [report](plans/reports/claude-261005-0155-m4-sgm-spec-review.md),
codex msgs 21060/21061/21063, convergence msgs 21064–21066.

This is a new experiment line. It does not reopen the reader/retrieval
campaign paused on 2026-09-11 (CONTEXT-POLICY.md). E1FULL stays NO-SHIP,
`max_certified_depth = 0`. Nothing here is wired into a deployment default.

## Starting point (P0)

- Commit: `53af8c3` on `mvp` (brief inspected `f67ff34`; the only differences
  are the three commits that recorded pre-existing worktree content: an
  artifact `.gitignore`, the paused campaign, the spec review). No
  interface the brief relies on changed.
- Environment: Python 3.12.13, torch 2.7.1+cpu, transformers 4.55.2,
  safetensors 0.5.3 (pinned; not upgraded).
- Baseline suite before M4: 562 passed, 53 failed, 2 skipped. The 53
  failures (`test_mergecert_q1_report.py`, 2 in
  `test_mergecert_campaign_contract.py`) reproduce on a clean `f67ff34`
  worktree: recorded MergeCert-Q1 provenance hashes no longer match the
  addendum edited by `f044ab2`. Pre-existing; historical provenance is not
  edited by M4.

## Agreed amendments to the brief (21064–21066)

1. P0–P2 reference = token-serial ingestion, full gradients, small nonzero
   output init (as briefed). Chunked ingestion, detached-source-feature
   training, a write gate and a Qwen3-0.6B pilot are registered follow-ups.
2. Phase-tagged tests (below); P2 is ephemeral/synthetic — SGM-10/11 are P4
   and real-archive sessions must not be accepted before them.
3. State is rebuilt after every optimizer step (fresh episodes per step).
4. Main memory controls re-ingest the source under each arm; query-time
   interventions are labelled diagnostics.
5. `ingest_source` is one transaction (fork + commit); rollback fixtures for
   overflow after an earlier layer wrote and late in a span.
6. Bounded load sweep vs the fixed single-bank control; routing failure is
   judged by causal address interventions + task results, not occupancy.
7. P3 registration will carry a descriptive, non-gating retrieval reference
   (existing shadow search is embedding/cosine; lexical is a separate arm).

## Registered deviation

`feature_shift=2` (projections see `[z_t, z_{t-1}]`, the delta-rule short-conv
idea) is used in the tiny P2 grid because a frozen RANDOM 4-layer backbone
does not reliably carry the key into the value token's hidden state. It is
part of the policy identity, the reference config keeps `feature_shift=1`,
and the grid includes a `noshift` ablation.

## Test map (phase of first requirement)

| ID | Phase | Status |
|---|---|---|
| SGM-01,02,03,04,05,06,07,08,09,15,16,17 | P1–P2 | implemented (`tests/test_sgm_*.py`) |
| SGM-19 | P2 | implemented (result labels) |
| SGM-18 | P3 | NOT IMPLEMENTED (no teacher/continuation scoring in P2) |
| SGM-10, SGM-11 | P4 | NOT IMPLEMENTED (no persistence / real archive in P2) |
| SGM-12, SGM-13, SGM-14, SGM-20 | P4 | NOT IMPLEMENTED (recovery / certification) |

## P2 synthetic load sweep — preregistration (frozen before launch)

Grid: `configs/m4_sgm_p2_grid.json` (49 runs, Modal CPU). Tiny frozen random
Qwen3 (4 layers, hidden 64), SGM at layers (1, 3), 2 heads, d_k = d_v = 8,
recent window 32 + 4 sinks, filler 40 → every binding is outside recent KV
at query time. N bindings ∈ {4, 8, 16, 32, 64}; 4 queries/episode; held-out
key and filler families; 600 steps × batch 16; seeds {0, 1}.

Arms: `learned`; `single_cell` (one cell, weight 1 — fixed single bank);
`random_fixed` (AddressMLP frozen, routing receives no gradient, init spread
4 cells); `oracle` (DIAGNOSTIC: address = key identity); `memory_off`
(re-ingested with SGM disabled). Ablations: `noshift` (learned/oracle at
N = 16, feature_shift = 1); `lmread` (frozen random LM-head readout, N = 16).

Readings (held-out, episode-level 95% intervals, both seeds):

- **R1 interface:** oracle accuracy well above chance (1/64) at every N. If
  oracle fails, the update/readout path is broken → stop and debug.
- **R2 capacity regime:** the smallest N where `single_cell` falls ≥ 20 pp
  below `oracle` is N*. No N* in range → the sweep cannot test routing.
- **R3 learned routing:** at some N ≥ N*, `learned` beats the stronger of
  `single_cell` / `random_fixed` by ≥ 5 pp in both seeds with intervals
  excluding zero, AND the read-offset diagnostic lowers `learned`
  accuracy. Otherwise "learned routing not demonstrated"; if `learned` ≈
  `single_cell` with few effective cells, the collapse hypothesis is
  supported for this design.
- **R4 memory use:** the shuffle diagnostic drops every memory arm toward chance.

These are mechanism readings on a random backbone. They do not establish
anything about frozen pretrained Qwen, recovery, or scaling.

### Amendment A1 (pre-launch, 2026-10-05, from the 3-run `sanity-v1` check)

Sanity (N = 16, 300 steps, seed 0, held-out): oracle **0.991** (shuffle
0.042, read-offset 0.013, query-off 0.013) — the update/readout interface
learns and generalises to unseen key families. `learned` 0.015 and
`single_cell` 0.016 (chance 0.016): flat at 300 steps; learned addresses
spread 1.0 → 1.9 cells and occupancy 43 → 77 cells/bank without task gain.

Reading note: the oracle arm also sends every non-binding token to a junk
cell, so it isolates filler writes for free. `learned` / `single_cell` /
`random_fixed` must learn write selectivity themselves (β gate or routing):
with β ≈ 0.5, 40 filler writes into the same few cells overwrite the
bindings. R1 therefore tests the interface under perfect addressing AND
perfect write isolation.

Changes (made before the grid launched): steps 600 → 1500 for every arm;
added per-token-class write-gate telemetry (`beta_by_token_class`:
sink / key / value / filler); Modal timeout 4 h → 6 h. Readings R1–R4 are unchanged.

### Grid `p2-load-sweep-v1` — STOPPED (2026-10-05)

I launched it at `080147a` while codex's audit findings (#gravity
21074/21075) were open. Stopped at codex's request (21077); app wall time 5 m 58 s (02:52:02–02:58:00), billed $1.15. Only the
three `memory_off` (steps = 0) runs completed; they are kept but superseded.
None of its results are evidence for R1–R4.

### Amendment A2 (audit fixes, before any replacement grid)

Every finding from codex's audit (21074/21075) is accepted:

1. **R4 intervention.** The within-bank coordinate shuffle was a no-op for
   `single_cell`. The registered memory-use check is now `bank_derange`
   (episode b queries episode (b+1) mod B's complete banks), which is valid for
   every arm. `coord_shuffle` remains an extra diagnostic and is N/A for
   `single_cell`. R4 now reads "bank_derange drops every memory arm toward chance".
2. **Paired episodes.** Evaluation episodes are pre-generated once, and
   interventions use their own RNG. A test asserts identical (source, query,
   label) tuples across all interventions. R3's learned-minus-control gain and
   read-offset drop are now **episode-paired** intervals computed from aligned
   per-example rows (checked by episode hash), replacing the per-arm half-widths.
3. **Live state ↔ weights.** State records `runtime_uuid:Σ param._version`. A
   different runtime, or any optimizer step, rejects both the bank and its
   adapter-influenced KV.
4. **Provenance.** Each run records the git HEAD, the grid sha256, the sha256 of
   the executed memsub source tree, and the trained adapters + task head
   (`trained_parameters.safetensors` + sha256). The launcher refuses a dirty
   tree for memsub, the runner or the grid file.
5. **Fresh final episodes.** The final-eval seed base changes from 777_001 to
   9_100_003. sanity-v1 results (seed base 777_001, inspected) are **development** evidence.
6. Smaller fixes:
   - a no-logits query path for task-head arms
   - per-layer q/k/v/β/address/out gradient and update norms, where `None` means
     no gradient reached that group
   - known limits, documented: in task-head arms the last selected layer's
     `out_proj`/α is an expected dead path. Multi-token queries transiently hold
     the whole prompt in KV before eviction; the pilot uses 1-token queries.
     `random_fixed` is a fixed coordinate map over *learned* q/k.

7. **Fail-closed readings** (codex 21084): `memsub/sgm/p2_grid_readings.py`.
   R2 and R3 require the registered seeds {0, 1}, both controls, the
   registered steps (1500), the task-head readout and n_queries = 4. Paired rows
   must have hash-matched episodes, exactly the registered query ids {0,1,2,3}
   (not inferred from the rows), the recorded `final_episodes` count in both
   runs, and at least 2 episodes. Both controls' rows are validated before the
   stronger one is chosen (codex 21088). Anything missing or misaligned is NON-EVALUABLE, never MET.
   R3 = MET only if some N ≥ N* passes in both seeds; otherwise NON-EVALUABLE
   if any eligible N is non-evaluable, else NOT MET. Thresholds and seeds are
   unchanged.

The replacement grid (`p2-load-sweep-v2`, same arms, N, seeds and steps as A1)
launches only after codex reviews the fix commit.

Spend (Modal billing report, hourly, 2026-10-05): smoke $0.008, sanity-v1
$0.190, stopped v1 $1.153 (app wall 5 m 58 s); M4 total **$1.35**.

## P2 result — `p2-load-sweep-v2` (2026-10-05)

App `ap-x299g630mcI7eabiyB7kOL`, launched 03:53 from `1d62903` (clean tree).
Grid sha `5d01e67d…`; executed memsub source sha `a89284ea…`; final-eval seed
base 9_100_003. **49 of 49 cells returned.** One container was preempted;
Modal restarted that input and it completed. The serial validation pass
(`c75d9f9`, cleared in #gravity 21105) marked **all 49 cells `stream_ok`**:
complete artifacts, provenance bound to the registered config, schema-valid
rows consistent with the metrics, and local copies identical to the volume.
No recovery or retry was needed, and no `attempts.json` selection is required.
Files: `runs/p2-load-sweep-v2/summary.md` and `artifact_validation.json`.
Per-example rows are in `runs/p2-load-sweep-v2-per-example-results.tar.gz`.

Held-out accuracy (chance 0.016), seeds 0 / 1:

| N | oracle (diag.) | learned | single_cell | random_fixed |
|---|---|---|---|---|
| 4 | 1.000 / 0.999 | **0.882 / 0.926** | 0.557 / 0.523 | 0.079 / 0.100 |
| 8 | 1.000 / 1.000 | **0.877 / 0.903** | 0.111 / 0.075 | 0.045 / 0.043 |
| 16 | 1.000 / 1.000 | 0.052 / 0.593 | 0.038 / 0.038 | 0.022 / 0.025 |
| 32 | 0.999 / 0.999 | 0.021 / 0.021 | 0.021 / 0.017 | 0.020 / 0.014 |
| 64 | 1.000 / 1.000 | 0.020 / 0.018 | 0.020 / 0.017 | 0.019 / 0.015 |

Preregistered readings:

- **R1 interface:** oracle ≥ 0.999 at every N. Under perfect addressing and
  write isolation, the update/readout path stores and retrieves up to 64
  bindings, and it generalizes to held-out key families.
- **R2:** MET, with **N\* = 4**: single_cell is 0.46 below oracle already at
  N = 4.
- **R3 learned routing: MET at N = 4 and N = 8 (both seeds).** The paired
  gain over the stronger control (single_cell) is +0.33 / +0.40 at N = 4
  and +0.77 / +0.83 at N = 8. The read-offset diagnostic drops learned
  accuracy by 0.86–0.91 (paired), so the learned addresses are used. **It is
  NOT MET at N = 16** (seed 0 fails, seed 1 passes: 0.593), and NOT MET at N = 32 and 64, where
  learned is at chance.
- **R4 memory use:** bank_derange drops every main memory arm that started
  above 4× chance to 0.011–0.020, i.e. chance.

Mechanism notes (descriptive, not registered):

- Learned write gating emerges where routing works. At N = 4, mean β is 0.83–0.85
  on value tokens and 0.25–0.37 on filler. At N ≥ 32, β on value tokens is at or
  below β on filler. Learned banks spread to 30–48 occupied cells and 16–25
  effective cells at N ≤ 8: well beyond one 3×3 neighbourhood, and no
  single-cell collapse.
- The cause of the large-N failure is **unresolved**. The oracle supplies both
  correct addressing AND isolation of filler writes. Its 64-binding success
  shows this backend works under that oracle policy; it does not isolate
  optimisation or credit assignment as the cause of the learned arm's failure.
  Learned, single_cell and random_fixed all sit at chance from N = 32.
  random_fixed (a frozen coordinate map over learned q/k) is worse than
  single_cell at N ≤ 8.
- Ablations at N = 16. `noshift`: learned 0.065 / 0.061 and oracle 0.990 / 0.995;
  with oracle addresses the key shift is unnecessary, and the learned
  comparison is inconclusive given the seed spread of the main N = 16 learned
  cells. `lmread` (frozen random LM head): oracle 0.898, learned 0.047.

Scope: mechanism evidence on a frozen RANDOM tiny backbone with a task head
and `feature_shift = 2`. It says nothing about frozen pretrained Qwen,
recovery, or long-history scaling. **Learned routing is useful at N = 4–8,
seed-sensitive at N = 16, and not demonstrated at N = 32–64 within 1500
steps. The relative roles of optimization, representation, address
collisions and filler-write interference remain unresolved.** (Wording per
codex's completed-result audit, #gravity 21110, which independently
reproduced the paired intervals: N = 4 +0.325 [0.290, 0.360] / +0.402
[0.369, 0.435]; N = 8 +0.766 [0.739, 0.792] / +0.828 [0.806, 0.850].)

Spend (Modal billing, hourly): v2 **$12.72**. M4 total: smoke $0.008, sanity
$0.190, stopped v1 $1.153, v2 $12.722, for **$14.07**.

## P2D — diagnosing learned failure at N ≥ 16 (user chose option (a), #gravity 21113)

Preregistered before any P2D measurement. P2 results stay frozen under
their identity. Candidate causes: filler-write interference, address
learning / collisions, optimization budget, representation.

### Step 1 — local, $0, descriptive (revised per codex 21117 / 21120)

Observer: `scripts/sgm-p2d-address-telemetry-from-saved-runs.py` plus
`memsub/sgm/p2d_address_diagnostics.py`. The memsub observer adds two
telemetry-only traces, `write_coords` and `read_q`. A regression test
compares bank tensors, reads and logits against the frozen `1d62903` code
bitwise.

Exactly the 20 registered cells: `learned` and `random_fixed` × N ∈
{4, 8, 16, 32, 64} × seeds {0, 1}, reloaded from the v2 volume mirror. Per cell:

1. **Integrity:** parameter sha256 equals the manifest. **Dev equivalence:**
   the frozen-v2 runtime (memsub extracted from `1d62903`) and the observer,
   with the same checkpoint on the same dev episodes (seed 4242, eval_batches
   × batch), produce bitwise-equal task-head logits and labels. The dev
   aggregate equals the run's last logged dev evaluation.
2. **Compatibility check** (separate, not telemetry): replaying the old
   final set (9_100_003 + seed) reproduces the saved per-example predictions.
3. **Dev telemetry** (4 dev batches × 16), per layer/head. Stencil
   relations use the actual positive-weight B-spline supports. *Spatial
   coupling* Σ_c w_a(c) w_b(c) is only the spatial factor of read gain:
   β (q·k) and the content residual also matter. Measures:
   - alignment of each query's read to its binding's value write (Euclidean
     distance, stencil intersection, spatial coupling)
   - binding-pair stencil intersection and spatial coupling
   - filler writes intersecting any binding, and their max spatial coupling
4. **Fixed-final-query filler test:** keep the final query's q and read
   stencil fixed, and read the bank snapshot before the tail filler and after
   it. Report task-head accuracy, paired correct→wrong and wrong→correct
   transitions, and the relative read change.

Readings are descriptive only:
- Geometry can be consistent with a mechanism but does not prove it, and
  cannot establish a unique cause. In particular, low collision plus
  misalignment does not establish inadequate q/k representation.
- A pre→post accuracy drop supports harmful bank changes from tail-filler
  writes, conditional on that query representation. It does not show that
  every error is overwritten content, or include query/KV-mediated effects.
- Step 1 results inform the final Step 2 preregistration.

### Step 1 results (2026-10-05; evidence audit PASS, #gravity 21128)

Artifacts: `plans/261005-0210-m4-sgm-p0-p2/p2d/step1-address-telemetry.json`
(sha256 `5f1a643f…`) and `step1-run.log`. Observer `4e282de`, memsub source
`729cb242…`. All 20 registered cells: 64 dev episodes / 256 queries each.
Every cell passed bitwise frozen-v2 dev equivalence, the 1024-row old-final
compatibility replay, and the snapshot invariants. Values are per layer
(L1 / L3) and head (h0 / h1).

| cells | read→bound-write distance (pooled median) | fixed-query acc pre→post filler | correct→wrong / wrong→correct |
|---|---|---|---|
| learned N=4 | L1 0.39–0.63, L3 0.15–0.21 | 0.926→0.863, 0.977→0.914 | 19/3, 16/0 |
| learned N=8 | L1 0.35–0.55, L3 0.43–0.88 | 0.949→0.895, 0.977→0.902 | 19/5, 19/0 |
| learned N=16 | s0: L1 3.3/4.5, L3 0.6; s1: L1 1.82/0.47, L3 0.6 | 0.055→0.051, 0.672→0.605 | 8/7, 22/5 |
| learned N=32 | L1 5.5–6.9, L3 1.5–3.1 | 0.023→0.020, 0.027→0.023 | 3/2, 5/4 |
| learned N=64 | L1 6.8–8.3, L3 8.0–19.2 | 0.012→0.012, 0.012→0.000 | 3/3, 3/0 |
| random_fixed | 2.2–9.5 everywhere | N=4 post 0.086/0.105, N=8 s1 0.0625; else ≤ 0.027 | — |

Narrowed descriptive readings (per codex 21128):

- **N = 32 / 64.** Replacing the post-filler bank with the pre-filler bank,
  while keeping the final query representation, does not rescue accuracy:
  the pre-filler read is already at 0.012–0.027. This does **not** rank filler
  as an overall cause. Its effects on training, source KV and the query
  representation are untested, so `learned_filler_off` stays in Step 2.
  Reads lie far from their bindings' writes. That is an observation
  consistent with read/write address misalignment, not a demonstrated cause.
- **Overlapping supports with working retrieval** (N = 4 / 8: binding-pair
  stencil intersection L1 0.60–0.76, L3 ≈ 1.0; ~97–100% of filler writes
  intersect a binding stencil) show that disjoint stencils are unnecessary
  here. They do **not** identify q·k and β as the separation mechanism:
  spatial weight differences and head/layer contributions remain possible.
- **Tail-filler writes** cost the working runs a modest net amount on the
  fixed-query test: about 6–8 points, with 16–19 correct→wrong against
  0–5 wrong→correct. This holds conditional on the query representation.
- **random_fixed** is not at chance throughout. N = 4 dev post-filler
  accuracy is 0.086 / 0.105 and N = 8 s1 is 0.0625 (chance 0.0156): limited
  gains. Its frozen MLP maps learned q/k, so its misalignment is an
  observation, not inevitable because the map is fixed.
- **Geometric alignment alone is not sufficient.** At N = 16 s0, L3 has a
  ~0.61–0.63-cell median distance and near-perfect stencil intersection, yet
  the pre-filler read scores 0.055.

### Step 2 — FINAL PREREGISTRATION (draft for codex audit; nothing implemented or launched)

Design per codex 21118 / 21129 and the Step 1 results. Experiment group
`p2d-diagnostics-v1`; a new memsub source identity is recorded at launch.
Everything not listed below is identical to the v2 recipe: the tiny frozen
random Qwen3; SGM at layers (1, 3), 2 heads, d_k = d_v = 8,
`feature_shift = 2`; recent window 32 + 4 sinks; filler 40; 4 queries;
batch 16; AdamW lr 3e-3; train seed = cell seed; held-out key and filler
families. No adaptive λ, no checkpoint selection, no held-out supervision,
no post-hoc repair.

**Arms (12 cells, seeds {0, 1}):**

| arm | N | steps | change vs v2 `learned` |
|---|---|---|---|
| `learned_filler_off` | 16, 64 | 1500 | Tail-filler write steps are skipped in training and evaluation: no delta update, no allocation. Reads, residual contribution and learned β on sink/key/value tokens are unchanged. |
| `learned_long` | 16, 32 | 4500 | One continuous run (same init, data stream, optimizer, lr). Checkpoints after 1500 and 4500 updates; both are evaluated as fixed endpoints. |
| `learned_addr_supervised` | 32, 64 | 1500 | Ongoing auxiliary pair loss (details below). |

**Auxiliary loss (`learned_addr_supervised`), registered exactly:**

- For each training query q with bound value token v, at each selected
  layer l and head h:
  - a_r = scale · AddressMLP_l(q_{l,h}.detach()), where q is the query
    token's read query vector;
  - a_w = scale · AddressMLP_l(k_{l,h}.detach()), where k is the value
    token's write key at ingest.
- L_aux = λ · mean over (batch, query, layer, head, coordinate) of
  (a_r − a_w)², with **λ = 0.1** fixed, active at every step (ongoing
  supervision, not warm-up), using training-split binding pairs only.
  Total loss = task CE (unchanged, full gradient) + L_aux.
- Graph: q and k are captured as detached telemetry, and the auxiliary
  coordinates are recomputed through the live AddressMLP parameters. So L_aux
  sends gradient **only into AddressMLP**, not into q/k/v/β/out projections
  or upstream features. A test asserts the gradient destinations.
- Evaluation uses no auxiliary signal.

**Evaluation (all arms):**

- Fresh common final set, seed base **9_300_011**: 16 batches × 16 episodes
  × 4 queries, held-out families.
- The frozen v2 `learned` checkpoints for N ∈ {16, 32, 64} × {0, 1} are
  re-evaluated on the same fresh set (local CPU) as same-N, same-seed
  baselines.
- Interventions as in v2: bank_derange, coord_shuffle, read_offset, query_off.
- Step 1 observer telemetry on dev seed 4242:
  - pooled read→bound-write distance
  - target spatial coupling vs mean other-binding spatial coupling
  - query read-address spread (std across keys)
  - occupancy and effective cells
  - β by token class
- Episode-paired 95% intervals throughout.

**Registered readings (diagnostic effects; no R3 pass conferred; no
pretrained or scaling claim):**

- *Reproducible gain:* in both seeds, the paired accuracy difference vs the
  same-N, same-seed frozen v2 learned checkpoint is ≥ 0.05, with a 95%
  lower bound > 0.
- *Alignment improved, not collapsed:*
  - the pooled median read→bound-write distance falls vs the baseline at
    both layers;
  - target coupling ≥ 2 × mean other-binding coupling;
  - the query read-address spread is ≥ 1 cell.
- `learned_addr_supervised`:
  - **Reproducible gain + non-collapsed alignment + memory use**
    (the memory-use rule in clarification 3) supports the
    usefulness of this supervised routing-training recipe. It does not show
    credit assignment was the unique original blocker.
  - **Alignment improves, accuracy does not:** alignment alone was insufficient.
  - **Alignment does not improve, or collapses:** the probe failed to
    establish the intended intervention, and the cause remains unresolved.
- `learned_filler_off`: a reproducible gain supports harm from tail-filler
  writes for this recipe. It does not establish filler as the sole cause.
- `learned_long`: a reproducible 4500-step gain over its own 1500-step
  checkpoint (and over v2) is a budget effect for this recipe.

Long-prefix continuity and the budget guard are defined in clarifications
4 and 5 below; these replace all earlier wording.

**Registration clarifications (codex 21132, committed before implementation):**

1. **Evaluation sets.**
   - Final set = seed **9_300_011 + cell seed**: 16 batches × 16 episodes
     × 4 queries, held-out families. Each treatment cell and the frozen v2
     learned baseline at the same N and seed use this identical set
     (matching episode hashes).
   - **Accuracy and memory interventions run on this final set.**
     Geometry/telemetry runs on dev 4242 (4 batches × 16 = 64 episodes).
   - Intervals follow the v2 procedure. Each episode's score is the mean of
     its 4 query hits; differences are paired on matching episode hashes;
     the interval is mean ± 1.96 · sample_sd / √n_episodes (256 final, 64 dev).
   - The reproducible-gain rule (≥ 0.05 and lower bound > 0, in both seeds)
     is applied separately to each `learned_long` contrast: 4500 vs its own
     1500, and 4500 vs v2.
2. **Collapse / alignment criteria** (dev, per selected layer and head,
   reported for all four heads):
   - (a) pooled median read→bound-write distance < the frozen baseline's
     for the same layer/head;
   - (b) target coupling > 0, where target coupling is the mean over queries
     of the spatial coupling between the read stencil and the bound value's
     write stencil;
   - (c) target ≥ 2 × other coupling, where other coupling is the mean over
     queries of the mean coupling to the N − 1 other bindings' writes in the
     SAME episode;
   - (d) read spread ≥ 1 cell, where spread is the per-episode sample std
     (ddof = 1) of the queried keys' read coordinates, averaged over the two
     coordinates, then averaged over episodes.
   - **"Alignment improved, not collapsed"** requires, in **both seeds**,
     that for **every selected layer at least one head** satisfies (a)–(d).
3. **Memory use** (final set; the registered near-chance ceiling is 0.04,
   not literal chance):
   - bank_derange accuracy ≤ 0.04;
   - paired (none − bank_derange) lower bound > 0;
   - paired (none − read_offset) lower bound > 0.
4. **Long-prefix continuity** (descriptive).
   - Compare the 1500-step `learned_long` checkpoint with v2's file hash, and
     with its tensors if the hashes differ.
   - An unexplained tensor mismatch is labelled a *continuity discrepancy*
     (possible causes: serialization, code drift, RNG/order, checkpoint
     timing), not machine nondeterminism.
5. **Budget guard** (codex 21133 / 21135; `memsub/sgm/p2d_launch_guard.py`,
   `modal-runners/modal-m4-sgm-p2d-diagnostics-grid.py`). Billing is
   reconciliation only, never the control.
   - **Cap scope:** all Modal compute for group `p2d-diagnostics-v1`,
     including image build, startup, idle and replays. Baseline
     re-evaluation and telemetry are local.
   - **Resources:** `cpu=(4, 4)` and `memory=(8192, 8192)`. CPU limits are
     soft (throttling) and memory is hard, so a CPU-overuse margin is
     reserved. `startup_timeout=300 s`, `scaledown_window=2`, `retries=0`,
     `max_containers=12`, and an 8 h backstop function timeout.
   - **Per-cell wall budget:** 1.4 × arm factor × that cell's OWN
     seed-specific v2 wall time. The arm factor is filler_off 1.0, long 3.0
     (the N32 s0 cell is ~7.3 h) and addr_supervised 1.1.
   - **Watchdogs** (codex 21139): an *independent sleeper process* SIGKILLs
     the cell process at its deadline, so it fires even while a C call holds
     the GIL (tested with a GIL-holding `usleep`). An early 120 s watchdog
     starts before any import or Dict RPC and bounds every attempt's claim
     phase. Both are cancelled in `finally` (process-group kill), and
     containers are `single_use_containers`. An expired cell is reported
     incomplete and not re-run.
   - **Attempts:** atomic claims via `Dict.put(..., skip_if_exists=True)`.
     Only `attempt1` of a cell may train. A replay claims the single reserved
     replay slot and exits within the early deadline. A further replay finds
     the slots exhausted: it sets a global HALT key, every later attempt of
     every cell refuses, and the launcher stops the app. A concurrent-claim
     test admits exactly one trainer. Any re-run is a new reviewed launch
     charged to the same cap.
   - **Admission ledger** (refuses launch if over the cap), at $0.252576 per
     container-hour (4 cores × $0.0000131/s + 8 GiB × $0.00000222/s), per
     dry run 2026-10-05:

     | component | USD |
     |---|---|
     | cell timeouts | 10.870 |
     | startup + teardown | 0.303 |
     | replay allowance (1 × (300 s + 120 s)) | 0.354 |
     | image build | 0.300 |
     | CPU-overuse margin (10%) | 0.812 |
     | fixed margin | 1.500 |
     | **reserved total** | **14.139 ≤ 15.00** |

     A configuration using rounded worst-seed durations (3,042 timeout-min)
     is rejected (test). Duplicate run IDs are rejected before the ledger is
     built (test).
   - **Shutdown verification:** app state `stopped` and 0 containers via the
     CLI, plus billing reconciliation.
