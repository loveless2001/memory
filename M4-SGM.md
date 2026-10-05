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
- **R4 memory use:** bank_derange drops every memory arm above 4× chance to
  0.011–0.020, i.e. chance.

Mechanism notes (descriptive, not registered):

- Learned write gating emerges where routing works. At N = 4, mean β is 0.83–0.85
  on value tokens and 0.25–0.37 on filler. At N ≥ 32, β on value tokens is at or
  below β on filler. Learned banks spread to 30–48 occupied cells and 16–25
  effective cells at N ≤ 8: well beyond one 3×3 neighbourhood, and no
  single-cell collapse.
- The failure at large N is in **learning**, not capacity. The oracle stores 64
  bindings at d_k = 8 per cell perfectly, while learned, single_cell and
  random_fixed all sit at chance from N = 32. random_fixed (a frozen coordinate
  map over learned q/k) is worse than single_cell at N ≤ 8.
- Ablations at N = 16. `noshift`: learned 0.065 / 0.061 and oracle 0.990 / 0.995;
  with oracle addresses the key shift is unnecessary, and the learned
  comparison is inconclusive given the seed spread of the main N = 16 learned
  cells. `lmread` (frozen random LM head): oracle 0.898, learned 0.047.

Scope: mechanism evidence on a frozen RANDOM tiny backbone with a task head
and `feature_shift = 2`. It says nothing about frozen pretrained Qwen,
recovery, or long-history scaling. The headline is that learned sparse
routing works and is used at small loads, but stops learning beyond about
16 bindings per episode within 1500 steps.

Spend (Modal billing, hourly): v2 **$12.72**. M4 total: smoke $0.008, sanity
$0.190, stopped v1 $1.153, v2 $12.722, for **$14.07**.
