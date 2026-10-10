# M4-SGM — Sparse Growing Memory (research-only)

Status: **P0–P2 complete; P2D, P2G and P2C diagnostics CLOSED (2026-10-06); frozen-Qwen3-0.6B line (P2.5 → B3) CLOSED NEGATIVE (2026-10-10); P3 not authorized** (started 2026-10-05). Authorized in #gravity
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
   - **Launch and shutdown commands:**
     - Launch with the project interpreter's Modal CLI:
       `.venv/bin/python -m modal run --detach modal-runners/modal-m4-sgm-p2d-diagnostics-grid.py …`
       (SDK/CLI 1.5.1). The PATH CLI is 1.3.5.
     - Results are consumed in completion order. On allowance exhaustion the
       launcher runs `<launch python> -m modal app stop --yes <app>`
       (check=True, 120 s timeout).
     - Then, even if the stop errored (e.g. the app was already stopped), it
       verifies via `app list --json` / `container list --json`. The app is
       verified only if it is unlisted or listed with an explicit "stopped"
       state and 0 tasks, AND no container carries its app ID. The 1.5.1 CLI
       emits snake_case JSON keys (`app_id`, `state`, `tasks`), rather than
       the table headings; unknown row schemas fail verification. Tests
       generate responses through the installed CLI's JSON formatter.
     - Evidence goes to `shutdown.json`; any unverified state is
       `shutdown_unresolved` and the launcher exits non-zero.
     - Billing is reconciliation only.

### Step 2 run `p2d-diagnostics-v1` — INCOMPLETE (2026-10-05; #gravity 21168, codex 21169/21174)

- 6/12 cells done and validated: filleroff N16 s0/s1, N64 s0; addrsup N32
  s0/s1, N64 s1.
- Lost:
  - 3 cells preempted, then their restarts refused as registered: long N32
    s0, filleroff N64 s1, addrsup N64 s0.
  - 3 cells cancelled at 13:15:19 after the launch host died (last activity
    13:09:45): long N16 s0/s1, N32 s1. `--detach` did not protect in-flight
    starmap inputs. App stopped 13:16:42.
- Spend $5.12 (Modal billing, app-filtered).
- Readings: option (a) partial readings (codex) cover only the complete pairs.

#### Validated partial readings — option (a), 2026-10-05

Six completed v1 cells pass the registered config, launch/source, parameter
hash, fresh-seed and prediction-row checks. Only filler-off N16 and address
supervision N32 have both seeds. Frozen v2 baselines for these four cells
were re-evaluated locally on seed 9_300_011 + cell seed using code 1d62903.
Geometry and gate/bank diagnostics use dev 4242 (64 episodes). The runtime
is isolated at 31aa4c8 with memsub source d4effd0c…; the analysis script and
decision-rule hashes are recorded in the report. The report is **partial**
and contains no top-up data.

Accuracies and paired gains below are percentages / percentage points.
Each 95% interval uses the registered 256 episode differences, with four
queries per episode and matching treatment/baseline episode hashes.

| complete pair | seed | frozen v2 accuracy | treatment accuracy | paired gain [95% interval] |
|---|---|---|---|---|
| filler-off N16 | 0 | 6.25% | 94.92% | +88.67 [86.74, 90.60] |
| filler-off N16 | 1 | 59.08% | 95.41% | +36.33 [32.98, 39.68] |
| address supervision N32 | 0 | 2.44% | 2.93% | +0.49 [-0.85, 1.83] |
| address supervision N32 | 1 | 2.83% | 11.72% | +8.89 [6.73, 11.05] |

- **Filler-off N16 passes the registered reproducible-gain rule and
  memory-use checks in both seeds.** This supports harm from tail-filler
  writes for this recipe. The intervention changes training and evaluation
  together; it does not isolate those phases or establish filler as the
  sole cause. The address-alignment conjunction fails at layer 3 in both
  seeds; that conjunction is not a prerequisite for the filler-off reading.
  Projected filler beta remains positive, while effective filler beta is
  exactly zero, as registered.
- **Address supervision N32 fails the registered both-seed gain and
  non-collapsed alignment rules.** Preserve the seed-1 gain; seed 0 has no
  established paired gain. Read-address spread is 0.02–0.43 cells across
  all four heads and both seeds, below the 1-cell floor, and no head meets
  target coupling >= 2 times other-binding coupling. Small pair distances
  therefore do not establish selective addressing. Seed 0 also fails
  memory use; seed 1 passes. Registered reading: **probe did not establish
  the intended alignment; cause unresolved**.
- **N64 is descriptive only:** filler-off seed 0 accuracy 2.54%; address
  supervision seed 1 accuracy 1.86%. Their missing partners prevent paired
  arm readings. **All long-arm readings and continuity contrasts remain
  unevaluable.** Missing results are recorded as missing, rather than as
  failed scientific endpoints.
- No R3 pass, pretrained-model or scaling claim follows from this partial
  diagnostic. The top-up remains a separately identified execution group.

Artifacts: `plans/261005-0210-m4-sgm-p0-p2/p2d/step2-partial-v1/` contains
`step2-readings.json`, `readings-verification.json` (independent standard
library recomputation of paired intervals and rule decisions), four saved
fresh-baseline row files, raw geometry, dev occupancy/effective-cell and
projected/effective gate diagnostics. The sibling `step2-partial-v1.log`
records the local evaluation. Original v1 evidence and incomplete cells
are preserved; the status-audit directory holds the volume mirror and
artifact/billing checks. `scripts/sgm-p2d-step2-readings.py --partial`
implements the explicit incomplete-grid report; the full-grid default
still rejects missing cells. Twelve focused tests pass.

### Amendment T1 — Step 2 top-up `p2d-diagnostics-v1-topup` (user option b, #gravity 21178)

- **Scope:** exactly the 6 lost cells (`configs/m4_sgm_p2d_topup_grid.json`).
  - The launcher asserts each pilot config equals the v1 registered cell
    (v1 `expand`).
  - Same `final_seed_base` 9_300_011 and the same 1-attempt / no-retrain
    claim rule, using a fresh attempts Dict for the new group.
  - memsub unchanged (source `d4effd0c…`). The container checks the memsub
    and runner hashes BEFORE claiming, and exits as `identity_mismatch`
    without training on any mismatch.
  - The training wrapper is AST-identical to v1 (test).
- **Survival changes only** (none touch training):
  1. `nonpreemptible=True` (Modal: 3× CPU/memory list price).
  2. A deployed app plus `.spawn()` with call IDs saved after every spawn.
     - In-flight calls no longer depend on the local client.
     - `collect` is idempotent and writes cells exactly as v1 `consume` does
       (stop and verify on allowance exhaustion).
     - Once every cell is terminal, `collect` stops the app by its
       spawn-time ID and verifies zero containers (`collect_status.json`).
- **Audit fixes (codex 21196):**
  - **Early watchdog.** The 120 s early watchdog starts BEFORE the torch
    import, the source hashing and the claim RPCs. Only the guard module is
    imported before it, and that module is stdlib-only.
  - **Exact scope.** `plan_topup` and `collect` both require exactly the 6
    authorized IDs (`TOPUP_IDS`): nothing missing, nothing extra.
  - **Collector coverage.** Coverage is bound to the SAVED registered grid.
    - A registered cell with no saved call ID is `untracked`. This happens
      if spawn was interrupted, or if the host died between server
      acceptance and persistence.
    - The run is terminal, and the app is stopped, only when all 6 are
      tracked AND terminal. A `calls.json` with unregistered IDs is
      rejected.
  - **Untracked recovery.** An untracked cell is never respawned
    automatically.
    - The collector reports its attempts-Dict claim (`<id>#attempt1`).
      The volume dir is validated like any other cell.
    - A claimed cell is running or has run: wait for it.
    - An unclaimed cell after the startup window is reported to
      codex/user. Any respawn is a reviewed decision; a duplicate of an
      accepted call is refused by the claim rule.
  - **Atomic writes.** `grid.json`, `launch_provenance.json`, `calls.json`
    and `collect_status.json` are written atomically (tmp file + `os.replace`).
- **Ledger** (dry run): the 1× v1 formula on the 6 cells' own timeouts, with
  the rate-based parts ×3.

  | component | USD |
  |---|---|
  | cell timeouts (28.7 container-h) | 21.723 |
  | startup + teardown | 0.455 |
  | replay allowance | 0.530 |
  | CPU-overuse margin | 1.622 |
  | image build | 0.300 |
  | fixed margin | 1.500 |
  | **reserved total** | **26.130** |

  - Expected spend is about $13–17 (v1 cells finished at 0.47–0.78 of
    their timeouts).
  - **Cap: $27.00** (`TOPUP_CAP_USD = 27.0`). The user approved B1 at the
    proposed $27 (#gravity 21193, 14:25; codex 21194). It is admitted
    because $26.130 ≤ $27.00. The launcher still refuses a missing or
    insufficient cap (tests). The cap is separate from the spent v1 $15
    allowance.
- **Commands** (project interpreter, CLI 1.5.1):
  1. `.venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py`
  2. `.venv/bin/python modal-runners/modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py spawn` (refuses a dirty tree or an existing group dir)
  3. `… collect` (re-run until terminal)
- **Validation:** `scripts/sgm-recover-and-validate-grid-artifacts.py --group p2d-diagnostics-v1-topup --runner modal-runners/modal-m4-sgm-p2d-diagnostics-grid.py --source-sha d4effd0c…`.
  How the top-up is merged with v1 for the readings is decided in codex's
  readings work.
- **Claims:** none added. Same registered readings, with no R3 / scaling /
  pretrained claims.

### Validated full Step 2 readings — v1 + top-up (2026-10-05)

One resumed local run at `ac49538` completed at 23:47:46 Bangkok with exit 0.
The report indexes all 12 registered cells: six validated original-v1 cells
and six validated top-up cells, each bound to its own group, launch, manifest
and consumed input hashes. The original v1 group remains an incomplete
execution; the combined analysis is complete. No treatment was relabelled.

Six frozen-v2 learned checkpoints were evaluated on the registered fresh
final sets (seed 9_300_011 + cell seed, 256 episodes of four queries). All
four baseline row files overlapping the earlier partial analysis are
byte-identical. Geometry and gate/bank telemetry use dev 4242 (64 episodes).
The analysis memsub source is `d4effd0c…`; rules remain `88dda56b…`.

Accuracies are percentages; gains and their episode-paired 95% intervals
are percentage points. The registered gain rule requires at least +5 points
and a positive lower bound in both seeds.

| arm | N | seed | frozen v2 accuracy | final accuracy | gain vs v2 [95% interval] |
|---|---|---|---|---|---|
| filler-off | 16 | 0 | 6.25% | 94.92% | +88.67 [86.74, 90.60] |
| filler-off | 16 | 1 | 59.08% | 95.41% | +36.33 [32.98, 39.68] |
| filler-off | 64 | 0 | 2.05% | 2.54% | +0.49 [-0.58, 1.55] |
| filler-off | 64 | 1 | 1.66% | 1.27% | -0.39 [-1.40, 0.62] |
| long | 16 | 0 | 6.25% | 76.17% | +69.92 [66.99, 72.85] |
| long | 16 | 1 | 59.08% | 94.73% | +35.64 [32.42, 38.87] |
| long | 32 | 0 | 2.44% | 3.12% | +0.68 [-0.66, 2.02] |
| long | 32 | 1 | 2.83% | 31.93% | +29.10 [26.05, 32.15] |
| address supervision | 32 | 0 | 2.44% | 2.93% | +0.49 [-0.85, 1.83] |
| address supervision | 32 | 1 | 2.83% | 11.72% | +8.89 [6.73, 11.05] |
| address supervision | 64 | 0 | 2.05% | 1.66% | -0.39 [-1.44, 0.66] |
| address supervision | 64 | 1 | 1.66% | 1.86% | +0.20 [-0.96, 1.35] |

**Registered readings:**

- **Filler-off N16 reproduces the registered gain and passes memory use in
  both seeds.** This supports harm from tail-filler writes for this recipe.
  Training and evaluation were changed together, so their contributions
  remain unseparated and filler is not established as the sole cause.
  N64 has no registered reproducible gain and fails memory use in both seeds.
- **Long N16 passes both registered gain contrasts**, against its own
  1500-step checkpoint and against frozen v2, and passes memory use in both
  seeds. The registered reading is a budget effect for this recipe.
  The unresolved seed-0 prefix discrepancy below limits the v2 comparison.
  **Long N32 does not pass either both-seed gain rule.** Preserve seed 1's
  +29.10-point gain; seed 0 has no established paired gain. Memory use passes
  in both seeds, which does not substitute for the failed gain criterion.
- **Address supervision fails the intended non-collapsed alignment at
  both N32 and N64.** The registered reading remains: probe did not establish
  the intended alignment; cause unresolved. Preserve the N32 seed-1 gain of
  +8.89 points and its memory-use pass; seed 0 fails memory use and does not
  establish a gain. N64 has no reproducible gain or memory-use pass. Address
  spread is below one cell for every supervised head/seed at both loads.
- **Every arm fails the both-seed alignment conjunction.** Alignment is an
  additional diagnostic here; it is not a prerequisite for the registered
  filler-off or long-budget readings.
  Descriptively, layer 1 meets the head criteria in filler-off N16 (both
  seeds) and long N16 seed 1. Long N16 seed 0 has smaller layer-3 distances
  and target coupling above twice other-binding coupling, but its spread
  is 0.946–0.985 cells, below the registered floor. These partial layer
  observations remain visible; the both-layer/both-seed decision is unchanged.

**Gate telemetry (descriptive):** effective filler beta is exactly zero in
all four filler-off cells by the registered intervention; their projected
filler beta remains 0.269–0.551. In the eight long/address-supervised
cells, effective filler class means span 0.098–0.252, key means
0.051–0.332, and value means 0.055–0.556. These pooled class
means do not determine token/head-level selectivity or establish that
successful cells route filler elsewhere. Step 2 does not establish a
causal blocker for real-text P3. A selective-write experiment remains a
proposed hypothesis test, outside these completed registered readings.

**Long endpoints and continuity (descriptive):**

| N | seed | own 1500 accuracy | 4500 accuracy | 4500 − own 1500 [95% interval] | 1500 vs v2 checkpoint |
|---|---|---|---|---|---|
| 16 | 0 | 5.47% | 76.17% | +70.70 [67.83, 73.58] | continuity discrepancy (uninvestigated) |
| 16 | 1 | 59.08% | 94.73% | +35.64 [32.42, 38.87] | byte/tensor identical |
| 32 | 0 | 1.86% | 3.12% | +1.27 [-0.14, 2.68] | continuity discrepancy (uninvestigated) |
| 32 | 1 | 2.83% | 31.93% | +29.10 [26.05, 32.15] | byte/tensor identical |

Both seed-0 checkpoints differ in their tensors as well as file hashes;
serialization alone does not explain this. Both seed-1 checkpoints match
v2 exactly. These are the registered descriptive continuity labels, not
new pass/fail gates. The seed-0 `vs_own_1500` contrasts compare endpoints of
the same continuous run; `vs_v2` retains a baseline whose prefix was not
reproduced. The divergence cause has not been localized.

**Audit and evidence:** 63 focused tests passed before the single resumed
run. Separate standard-library recomputation checks all paired intervals,
accuracies, memory rules, alignment decisions and six paired arm readings;
checkpoint tensor equality and all consumed input hashes also pass.
Claude independently recomputed the results without importing the readings
script or rule module: **PASS, zero mismatches** (#gravity 21281). The archived
inputs also pass a separate replay of all 12 cells and six baselines. The
independent verifier, output and hashes are preserved with the full artifact.
The aborted `step2-full-v1/` remains empty, its original one-line log is
unchanged, and the v1-only partial artifacts remain byte-identical to the
committed copies. Resume provenance records the aborted attempt and command.

Artifacts are in `plans/261005-0210-m4-sgm-p0-p2/p2d/step2-full-v1-r2/`:
`step2-readings.json`, six fresh-baseline row files, `readings-verification.json`,
analysis source snapshots, and `input-evidence.tar.gz` with a hashed manifest.
The archive contains every consumed treatment input (including both long
checkpoint files), baseline parameters/manifests, and group grids/launches.
It supports a separate statistics/tensor replay without the volume mirrors.
The sibling `.log` and `.resume.json` preserve execution provenance.

Full report SHA256:
`a8ad11020a1c7c45a0ab4428614f61bfabb3b4aeb617084ab07797d7cc7fac16`.

Fresh read-only Modal checks at 23:31 confirm both experiment apps stopped
with zero running containers. App-filtered reported P2D Step 2 spend remains
**$15.31215567** (original v1 **$5.11993761**, top-up **$10.19221806**),
provisional pending billing backfill. This local analysis added no Modal
compute; these figures do not describe all-M4 spend.

This closes the registered Step 2 readings. The narrow N16 effects do not
establish a reproducible higher-load rescue, a unique causal blocker, an R3
pass, pretrained-model behavior or scaling. Further training, causal
localization and compute remain deferred.

## P2G — selective-write gate and filler train×eval 2×2 (2026-10-06, CLOSED)

**Registration and gates.** Prereg v0.2
`plans/261006-0010-m4-sgm-p2g-selective-write-gate/prereg.md` (`25fdbc5`,
SHA256 `c2fa7394…`), amended per codex audits of v0.1/v0.2 and cleared for
implementation (#gravity 21306). Drafting authorized by the user (21289).
Implementation `dc9e0bb` was held by codex (21309/21312/21315: the reserved
seed was reachable from training eval; NaN/partial-telemetry/interval inputs
did not fail closed; only memsub was end-checked), fixed at `e71784b`, then
the recovery CLI seed selection at `0726161` (21323). Code audit PASS (21329);
final implementation/preflight gate PASS (21340). User approval "ok go"
(21341), scoped by codex to exactly six cells, $13 cap, no retries (21342);
cap bound at `2613ced`; launch clearance (21346).

**Design.** Six new 1500-step cells (P2 v2 `learned` recipe), group
`p2g-selective-write-v1`: `gateclosed` N16/N32 s0/s1 (`beta_proj.bias`
shifted 0 → −3 at init only; `W_beta` and every other draw unchanged; memsub
source `5c3b5420…`) and `filleroff` N32 s0/s1. Reused checkpoints: v2
`learned` N16/N32 (1d62903 / a89284ea) and P2D `filleroff` N16 (31aa4c8 /
d4effd0c), hash-bound in `configs/m4_sgm_p2g_inputs.json`. Training-artifact
eval used the published population 9_300_011+s; the registered population
9_400_011+s was consumed only by the single readings run. One common observer
(P2G source; eval-write E=off = existing tail-filler write mask) evaluated
every corner after the parity gates passed: P-on (v2, E=on) and P-off (P2D
filler-off N16, E=off) reproduced the complete legacy files, parsed and
byte-equal, in preflights r1/r2/r3 and again at readings time (6/6 each;
30,720 rows; produced hashes identical across runs).

**Run.** App `ap-S6aKXZB9FPh9MBYkLsVdDN` (deploy + spawn, non-preemptible,
`2613ced`), spawned 01:24, all six `done` by 02:25, app stopped with zero
containers (`stopped_verified`). No failures, replays, untracked calls or
allowance exhaustion. Recovery/validation CLI: 6/6 `stream_ok` against the
group's grid, launch, source and artifact seed. App-filtered spend
**$3.44816365** (provisional pending backfill), under the approved $13 cap
(reservation $12.32978160). Codex training-artifact and billing audit PASS
(21364).

**Registered readings** (single run at `2613ced`; report
`plans/261006-0010-m4-sgm-p2g-selective-write-gate/readings-v1/p2g-readings.json`,
SHA256 `03d47be48fcfcc311fde34a0d25733bc085caa3259b89f8f0a7687debd125818`).
Heldout accuracy (intervention none), s0 / s1:

| N | X(on,on) v2 | X(on,off) | X(off,off) filler-off | X(off,on) | gate (E=on) |
|---|---|---|---|---|---|
| 16 | 5.6% / 56.1% | 5.8% / 64.6% | 94.8% / 96.2% | 87.3% / 89.2% | 80.9% / 81.0% |
| 32 | 2.3% / 2.1% | 2.3% / 2.2% | 84.5% / 80.8% | 77.4% / 73.7% | 3.8% / 1.9% |

Q2 contrasts (paired, percentage points, s0 / s1) and labels:

| contrast | N16 | N32 |
|---|---|---|
| C_T\|E=off | +89.06 / +31.64 — reproducible gain | +82.13 / +78.52 — reproducible gain |
| C_T\|E=on | +81.74 / +33.11 — reproducible gain | +75.10 / +71.68 — reproducible gain |
| C_E\|T=on | +0.20 / +8.50 — neither | +0.00 / +0.20 — positive gain ≥5pp excluded |
| C_E\|T=off | +7.52 / +7.03 — reproducible gain | +7.03 / +7.03 — reproducible gain |

- **Q2, both N:** "reproducible gain for the no-filler-write training recipe
  at both eval settings; eval-setting conjunction not met". The eval
  conjunction fails because C_E|T=on fails (N32 ≥5pp excluded; N16
  seed-specific +8.5). Eval-time filler-write damage is **not** absent:
  C_E|T=off is a reproducible ≈7-point gain at both N. Descriptive
  interaction (C_T|off − C_T|on): N16 +7.32 / −1.46, N32 +7.03 / +6.84.
- **Q1, N16:** "reproducible gain without registered pooled suppression;
  mechanism unresolved". Gate − v2 +75.29 / +24.90 (reproducible gain);
  memory use passes both seeds; half-oracle **true** (+30.66 / +4.83, oracle
  gain reproducible); pooled ρ 0.619 / 0.596 (> 0.20; v2 0.873 / 0.816);
  gate AUROC mean 0.612 / 0.560 (descriptive).
- **Q1, N32:** "no reproducible gain and no registered pooled suppression;
  gate−v2 contrast is positive gain ≥5pp excluded". Gate − v2 +1.46 / −0.20;
  ρ 1.057 / 0.843; half-oracle false (oracle gain reproducible). Memory use
  passes for seed 0 despite near-chance accuracy and fails for seed 1, so the
  both-seed memory conjunction fails; this does not turn the excluded
  contrast into a gain or establish a mechanism.

**Interpretation limits** (accepted #gravity 21370/21371/21378): the readings
are registered contrasts between training recipes and evaluation settings
across cohorts that differ in source and host (v2, P2D, P2G). Same episode
hashes make evaluations paired, not training histories identical, and the
Step 2 seed-0 prefix discrepancy remains unresolved. "Filler writes during
training prevent learning usable addresses" is a hypothesis: P2G registered
no address-learning mechanism test. The suppression headline is pooled class
means only; AUROCs are descriptive. Evidence class: tiny random backbone +
task head, synthetic. No R3, pretrained, scaling or P3 claim.

**Audit.** Codex numerical results audit PASS (#gravity 21379): an independent
standard-library recomputation agrees on every saved-row statistic,
interval, classifier and Q1/Q2 reading; a dev-4242 replay agrees on all 20
corners' four-head populations, means, skipped/applied counts, pooled ρ and
AUROCs; zero reserved-seed evaluations by the audit (audit JSON SHA256
`8dd87079…`). Source, input and parity bindings pass. Codex keeps the audited
`RESULTS.md` and consumed inputs with the readings bundle.

This closes the registered P2G study. Follow-up training, a curriculum
variant or a P3 run is not authorized by it; any of these needs its own
registration and user approval.

## P2C — filler-length training curriculum (2026-10-06, CLOSED)

**Registration and gates.** Prereg v0.2
`plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/prereg.md` (`0c8d358`,
SHA256 `b1bafbbd…`), amended per codex v0.1 audit and cleared (#gravity 21387).
User chose this pilot (21382). Implementation `e64266e` was held by codex
(21390: toy readings smokes evaluated on the reserved seed VALUES — toy
N4/16-episode tasks, not the registered N32/N64/256-episode population; the
P2C wrapper did not bind the prereg file) and fixed at `8c3161a` (smokes on
dev seeds with seed spies; prereg hash in the executed identity and inputs
validation). Preflight r1 was aborted before output; r2 at `8c3161a` passed
(8/8 parity, schedule smoke, start/end identity); full suite 206 passed with
an explicit exit status (21393/21395). Final technical gate (21397); user
approval (21398) scoped by codex to four cells, $12 cap, no retries (21400);
codex bound the cap at `d47fe17` and cleared launch (21403).

**Design.** Four 1500-update cells (P2 v2 `learned` recipe), group
`p2c-filler-curriculum-v1`, `curriculum` N32/N64 s0/s1:
`PilotConfig.filler_len_schedule = ((0, 0), (1000, 40))` changes only the
filler LENGTH of training episodes (updates 0–999 no filler, 1000–1499 filler
40); memsub source `09b05c16…`; the default empty schedule is bitwise the
pre-knob trainer. The curriculum cells use no filler-token identity labels
and no oracle write masks in training or evaluation; training still uses
the task's supervised answer targets. Every registered evaluation is E=on with
filler_len 40. Comparators: v2 at the same N, and the filler-off-trained
reference evaluated E=on (P2G filleroff N32; P2D filleroff N64 s0 and top-up
s1). Artifact eval on 9_300_011+s; reserved readings population 9_500_011+s.

**Run.** App `ap-WCxVagWdH2A0O7sEhZnofv` (deploy + spawn, non-preemptible,
`d47fe17`), spawned 10:10, all four `done`, app `stopped_verified` at 12:42;
no failures, replays, untracked calls or HALT. Validation 4/4 `stream_ok`.
App-filtered spend **$3.94734272** (provisional), under the $12 cap. Codex
spawn, training-artifact and lifecycle/billing audits PASS (21405, 21408).

**Registered readings** (single run at `d47fe17`; report
`plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/readings-v1/p2c-readings.json`,
SHA256 `2fe1ab12be204abfa17e12292d73506954fb708bcee4677537821497dd04904b`;
parity re-run 8/8 byte-equal; start/end identity equal). Heldout accuracy,
E=on, s0 / s1:

| N | v2 | reference (filler-off-trained) | curriculum |
|---|---|---|---|
| 32 | 2.8% / 2.8% | 76.9% / 72.7% | 60.5% / 64.9% |
| 64 | 2.0% / 1.7% | 2.1% / 2.0% | 2.0% / 1.7% |

- **N32: "SUPPORTS: the label-free filler-length curriculum reproducibly
  beats v2 at N and recovers ≥ half of the filler-off-training reference."**
  Curriculum − v2 +57.71 [54.31, 61.12] / +62.11 [59.10, 65.12]; reference −
  v2 +74.02 / +69.82 (prerequisite met); half +20.70 [17.36, 24.04] / +27.20
  [24.11, 30.29]; memory use passes both seeds. Descriptive gain fractions
  77.97% / 88.95% are not a separate registered claim.
- **N64: "no reproducible gain; curriculum−v2 contrast is positive gain ≥5pp
  excluded."** Reference − v2 is also ≥5pp excluded, so half is null
  (unavailable); memory use fails in every corner.
- **Joint:** both-N support is false; there is no claim at both loads.

**Descriptive only** (no registered suppression or mechanism test; no
authority for an extension): curriculum pooled ρ 0.916 / 0.849 (v2 1.164 /
1.088 at N32). P2C registered no pooled filler-suppression criterion, so
these ratios do not establish suppression or a mechanism. Full-filler dev
accuracy stays near chance through updates 0–900 and rises after filler is
introduced (N32:
9% / 34% at update 1200, 61% / 70% at 1500, with both seeds increasing
between the recorded updates 1400 and 1500). It measures transfer to
full-filler episodes, not what was learned on no-filler episodes, and
selects nothing.

**Interpretation limits** (codex 21410): a recipe/distribution contrast, not
a mechanism; filler_len 0 also shortens episodes, so "no filler" and "shorter
episodes" are not separated; equal updates are not equal token or compute
exposure. The N64 negative contrasts do not identify a different blocker and
do not show that every earlier intervention was ineffective there. Cohorts
differ in source and host; the Step 2 seed-0 prefix discrepancy remains
unresolved. Synthetic tiny random backbone + task head; no R3, pretrained,
scaling or P3 claim.

**Audit.** Codex results audit PASS (21411): all 36,864 saved reserved-population
rows, 12 corners, intervals, memory tests, half intervals, classifiers,
readings and the joint flag recomputed; a dev-4242 replay matches every
corner's four-head counts/means, ρ and AUROCs to 1e-12; zero reserved-seed
re-evaluations (audit JSON SHA256 `b0bfc99e…`). Closure bundle with
[RESULTS.md](plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/readings-v1/RESULTS.md),
replay archive and checksums: `1260538` (21412).

This closes the registered P2C study. No extension, follow-up training or P3
run is authorized by it.

## P2.5 → B3 — frozen Qwen3-0.6B sidecar line (2026-10-06 – 2026-10-10, CLOSED)

Closed by the user (#gravity 22357), reopened for the feature_shift lead, closed again (22606). Full write-up:
[plans/reports/claude-261010-0022-m4-sgm-qwen3-0p6b-sidecar-line-closing-writeup-r4.md](plans/reports/claude-261010-0022-m4-sgm-qwen3-0p6b-sidecar-line-closing-writeup-r4.md) (r1–r3 kept).

- P2.5 screen (18 cells, 2 seeds): NOT PASSED at N32/N16, memory_use FALSE. Learned N32 reserved accuracy 6.9/5.9% vs random-fixed 12.5/8.9% and oracle 100/97.9%. The reading is post-hoc amended for learned-n32-s1; the original reading "unavailable" is kept.
- Readout probe (taskhead): rescue not shown (12/1024, 16/1024 vs residual head 74/1024, 65/1024).
- Dead-start diagnosis + Stage A: reads escape to empty cells early (A0 99.6% absent at update 25). A lower address lr delays the escape but does not prevent it.
- Fill+anchor (branch `m4-sgm-occupied-fill-v1`): B1 ran all 100 updates; its routing band was PARTIAL. B2 (1,500 updates, seed 0) VALID_NEGATIVE, 5/256 normal = 5/256 deranged.
- CPU gradient-path diagnosis: no structural dead path at init. At the B2 endpoint the memory is suppressed (writes off at L6/L13, reads ~0, near-collinear projected k/v). Cause and timing are not established.
- Previous-key probe ($0, shift1 runtime, offline): CARRIED. The value-token input holds partial previous-key information (top-1 .24–.66 vs chance .03); appending key features offline makes it near-perfect.
- B3 (branch, shift2 bundle, 1,500 updates, training seed 0, dev seed 4242): VALID_NEGATIVE, 8/256 normal = 8/256 deranged.
- Scope: this design and these recipes on frozen Qwen3-0.6B, mostly single-seed. This does not show that a pretrained model cannot use a memory.
- Spend ≈ $169–171 provisional (sum of per-stage snapshots; B3 $6.65 snapshot, ≈ $8.29 by wall time).
- 2026-10-10 (user 22634/22660): branch `m4-sgm-occupied-fill-v1` MERGED into mvp (`244718e`); memsub now = the fill/shift variant (d86639b9). Closed P2.5 replays that bind the old memsub run at tag `m4-sgm-p2p5-replays-pre-sidecar-merge`; branch tip tag `m4-sgm-occupied-fill-v1-final`. Test cleanup `2a16280`/`45cf7d6` (reusable P2.5 guards re-bound to a private manifest; historical replays retired; pinned-Qwen tests opt-in via `M4_RUN_PINNED_QWEN_TESTS=1`).
