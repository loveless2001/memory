# P2C — filler-length training curriculum (PREREG DRAFT v0.1)

Status: DRAFT for codex audit. User 21382 chose option (a) ("continue with a then") = draft + build this pilot.
Training (Modal or local) still needs the implementation audit + the user's scoped approval of the cap below.
Base: `e5a991a` (P2G closed). Evidence class: tiny-random-lm+taskhead, synthetic. No R3, scaling, pretrained or P3 claim.

## Motivation (from P2G, registered contrasts only)
P2G: training WITHOUT filler writes gave reproducible gains over v2 at N16/N32 at both eval settings, and the
filler-off-trained model kept 74–89% when filler writes were ON at eval; removing filler writes at eval did not
rescue v2 (N32: ≥5pp excluded). Hypothesis (unregistered in P2G, tested here): interference during TRAINING is
the obstacle, so an early phase without filler lets the model learn addresses that survive filler later.
P2G's filler-off training needs token labels (which tokens are filler). This pilot removes that: it changes only
the episode distribution (filler LENGTH), never tells the model which tokens are filler, and is evaluated with
standard 40-token filler and filler writes ON (E=on), i.e. no oracle at test or train.

## Question
Q-C. Does a two-phase filler-length curriculum (1000 steps with filler_len 0, then 500 steps with filler_len 40;
same 1500-step budget as v2) reproducibly beat v2 at N32 and N64, and recover ≥ half of the filler-off-training
reference (oracle-in-training model evaluated E=on)?

## Fixed protocol
- Recipe = P2 v2 `learned` (taskhead, batch 16, lr 3e-3, 4 queries, 1500 steps, seeds 0/1) except the new knob
  `PilotConfig.filler_len_schedule = ((0, 0), (1000, 40))`: training episodes at step t use the filler length of the
  last entry with start ≤ t. Default `()` = unchanged (bitwise; tested). `filler_len` stays 40, so dev evals during
  training, the run's own artifact eval and all registered evals use full 40-token filler. Fixed endpoint = step 1500.
- Schedule frozen by argument (not tuned): two thirds of the budget for address learning without interference, one
  third to adapt to full-length episodes before the fixed endpoint.
- Seeds: training-artifact eval on the published population **9_300_011+s**; registered readings population
  **9_500_011+s** reserved for one post-validation readings run (P2G consumed 9_400_011).
- Evaluation: common observer (P2G scripts `0726161` lineage, P2C source), heldout 16×16 = 256 episodes × 4 queries,
  interventions none / bank_derange / read_offset, **E=on for every corner** (no write mask anywhere).
  Episode-paired within seed; P2D rules `88dda56b` (`paired`, `memory_use`) and P2G rules (`classify` ordered
  gain → loss → excluded ≥5pp → neither, `linear_contrast`, `half_status`, interval/telemetry fail-closed checks)
  reused unchanged.

## Cells
New training (4): `curriculum-learned-n32-s0/s1`, `curriculum-learned-n64-s0/s1`, group `p2c-filler-curriculum-v1`.
Reused checkpoints (hash-bound in a new inputs index, never relabelled):

| role | N32 | N64 |
|---|---|---|
| v2 (baseline) | p2-load-sweep-v2 main-learned-n32-s* | p2-load-sweep-v2 main-learned-n64-s* |
| reference = filler-off-trained, evaluated E=on | p2g-selective-write-v1 filleroff-learned-n32-s* | p2d-diagnostics-v1 filleroff-n64-s0 + top-up filleroff-n64-s1 |

## Parity (before any reserved-seed use; STOP on failure)
P-on: v2 N32 and N64 s0/s1, E=on, seed 9_300_011+s, vs committed Step 2 frozen-observer baselines.
P-off: P2D filleroff N16 s0/s1 E=off vs their Modal rows (as P2G); plus P2G filleroff N32 s0/s1 E=off vs their own
Modal artifact rows at 9_300_011+s (validates the P2G-source observer on P2G-trained cells). Parsed + byte equal.

## Readings (per N)
- gain = classify(curriculum − v2), E=on. mem = memory_use passes both seeds.
- half ∈ {true, false, null}: defined iff classify(reference − v2) is a reproducible gain; then true iff lo > 0 both
  seeds for d_e = curriculum − 0.5·v2 − 0.5·reference; otherwise null (unavailable), never coerced.
- Ordered table (total):
  1. gain ∧ mem ∧ half=true → "SUPPORTS: the label-free filler-length curriculum reproducibly beats v2 and recovers ≥ half of the filler-off-training reference".
  2. gain ∧ mem ∧ half=false → "reproducible gain with memory use; ≥ half reference recovery not established".
  3. gain ∧ mem ∧ half=null → "reproducible gain with memory use; reference comparison unavailable (reference prerequisite not met)".
  4. gain ∧ ¬mem → "reproducible gain without registered memory-use evidence".
  5. ¬gain → "no reproducible gain; curriculum−v2 contrast is <label>".
- Descriptive only: accuracies, per-head gate telemetry (ρ, AUROC as P2G), and the full-filler dev-accuracy curve
  from each run's own telemetry (whether accuracy appears in phase 1 and survives phase 2).
- Limits carried: cohorts differ in source/host; seed-0 prefix discrepancy unresolved; a curriculum gain would show a
  training-distribution effect for this recipe, not a mechanism (no registered address-learning test); filler_len 0
  episodes also shorten sources, so "no filler" and "shorter episodes" are not separated.

## Ledger (exact numbers from a dry-run before launch)
Existing guard policy: timeout = 1.4 × own seed-specific v2 wall × factor 1.0 (curriculum steps are never longer than
v2's). v2 walls: N32 6267/4966 s, N64 8427/7721 s → timeouts 8773/6952/11797/10809 s. Non-preemptible 3× rate
$0.757728/container-h, existing overheads/margins → reservation ≈ **$11.1**; **cap request $12**. Expected ≈ $4
(P2G walls ran well under v2). New scoped runner/group/claims; P2G and older groups untouched. Local $0 alternative
needs the same authorization.

## Order
prereg audit → implement (knob + tests, inputs index, P2C runner + readings reusing P2G observer/rules) → CPU
preflights (tests, parity, schedule smoke) → implementation audit → user cap approval → launch → validate →
one readings run → codex results audit.

## Unresolved
- Two-phase 1000/500 schedule and the N64 inclusion are design choices (N64 reference failed in P2D, so its half is
  expected null); open to the auditor before registration.
