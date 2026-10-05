# P2C — filler-length training curriculum (PREREG DRAFT v0.2)

v0.2 amends v0.1 (`5271a50`) per codex audit `plans/reports/codex-261006-p2c-prereg-v01-audit.md` (items 1–4;
accepted choices: frozen 1000/500 schedule, N32 and N64 × s0/s1 retained).
Base: `e5a991a` (P2G closed). Evidence class: tiny-random-lm+taskhead, synthetic. No R3, scaling, pretrained or P3 claim.

## Gates and stop conditions (item 2)
1. Prereg clearance (codex) → implementation + bounded CPU preflights only: unit/regression tests, schedule smoke
   (few steps, tiny N, no registered cell), parity fixtures at 9_300_011+s, ledger dry-run.
2. The four 1500-step cells — on Modal OR locally — require the implementation audit AND a fresh scoped user approval
   of the exact cap/ledger. User 21382 ("continue with a then") authorized drafting and building only.
3. Exactly one reserved-seed (9_500_011+s) readings run, only after all four cells validate and every parity gate passes.
4. No early stop, checkpoint selection, schedule tuning, automatic training retry, missing-seed headline or expansion.
   A failed cell, artifact validation or parity gate stops the planned readings; any repair/resume is its own reviewed scope.

## Motivation and scope (item 1)
P2G registered recipe contrasts: training without filler writes gave reproducible gains over v2 at N16 and N32 at
both eval settings; the filler-off-trained model kept 74–89% with filler writes ON at eval. Removing filler writes
at eval did not reproducibly rescue v2: N32 ≥5pp excluded, but **N16 seed 1 gained +8.50pp** (seed-specific).
P2G's filler-off training uses token labels. This pilot tests a **label-free recipe contrast**: curriculum vs v2,
changing only the training episode distribution (filler length). Interference during training and address learning
are possible explanations, not mechanisms this pilot confirms or excludes. A positive result is also compatible
with changed episode length, token exposure, positions and training-stream draws; equal optimizer updates (1500) do
not mean equal token or compute exposure.

## Question (read per N)
Q-C(N), N ∈ {32, 64}: does the two-phase filler-length curriculum reproducibly beat v2 at N (E=on), with memory use,
and recover ≥ half of the filler-off-training reference? Any claim of support at both loads requires both per-N
SUPPORTS readings; no scaling inference from either.

## Fixed protocol
- Recipe = P2 v2 `learned` (taskhead, batch 16, lr 3e-3, 4 queries, 1500 optimizer updates, seeds 0/1) plus
  `PilotConfig.filler_len_schedule = ((0, 0), (1000, 40))`: update index t ∈ [0, 999] trains on filler_len 0 episodes,
  t ∈ [1000, 1499] on filler_len 40. Same model, head, optimizer state and continuous training generator across the
  boundary; only the final state after update 1500 is evaluated.
- Default `filler_len_schedule = ()` preserves initialization, training-stream draws, updates and every evaluation
  bitwise (regression-tested against the pre-knob trainer). `filler_len` stays 40: every dev eval during training,
  the run's own artifact eval and every registered eval use filler_len 40 with filler writes ON (E=on).
- Seeds: artifact eval on the published population 9_300_011+s; registered readings on reserved **9_500_011+s**.
- Evaluation: common observer on the P2C source; heldout 16×16 = 256 episodes × 4 queries; interventions
  none / bank_derange / read_offset (3,072 rows per corner); every registered corner E=on; episode-paired within
  seed (abort on unmatched hashes). Rules reused unchanged: P2D `paired`/`memory_use` (`88dda56b`) and P2G
  `classify` (gain → loss → excluded ≥5pp → neither), `linear_contrast`, `half_status`, interval/telemetry
  fail-closed checks.

## Cells and bindings (item 3)
New training (4): `curriculum-learned-n32-s0/s1`, `curriculum-learned-n64-s0/s1`, group `p2c-filler-curriculum-v1`.
Reused checkpoints (exact manifests, configs, parameter hashes committed in a new inputs index, checked before any
evaluation; never relabelled):

| role | N32 | N64 |
|---|---|---|
| v2 baseline | p2-load-sweep-v2 main-learned-n32-s0/s1 | p2-load-sweep-v2 main-learned-n64-s0/s1 |
| reference = filler-off-trained, evaluated E=on | p2g-selective-write-v1 filleroff-learned-n32-s0/s1 | p2d-diagnostics-v1 filleroff-learned-n64-s0; p2d-diagnostics-v1-topup filleroff-learned-n64-s1 |

Grid, prereg, inputs index, observer, rules, runner and memsub source are bound at start and end of preflight and
readings (as P2G `finish_identity`); any change aborts.

## Parity (STOP on failure)
Complete legacy five-intervention files (5,120 rows each), parsed + byte equal, at 9_300_011+s:
- P-on: v2 N32 and N64 s0/s1, E=on, vs the committed Step 2 frozen-observer baselines.
- P-off: P2D filleroff N16 s0/s1, E=off, vs their Modal rows; P2G filleroff N32 s0/s1, E=off, vs their Modal artifact
  rows. P-off fixtures intentionally exercise the legacy E=off path; registered readings and curriculum training never use it.

## Readings (per N; item 4)
- gain = `classify(curriculum − v2)`. mem = `memory_use` passes both seeds.
- half ∈ {true, false, null}: computed from the measured prerequisite on the reserved population — defined iff
  `classify(reference − v2)` is a reproducible gain (E=on, fresh population; nothing preset from P2D's E=off history);
  then true iff lo > 0 both seeds for d_e = curriculum − 0.5·v2 − 0.5·reference; otherwise null (unavailable), never coerced.
- Ordered table (total), per N:
  1. gain ∧ mem ∧ half=true → "SUPPORTS: the label-free filler-length curriculum reproducibly beats v2 at N and recovers ≥ half of the filler-off-training reference".
  2. gain ∧ mem ∧ half=false → "reproducible gain with memory use; ≥ half reference recovery not established".
  3. gain ∧ mem ∧ half=null → "reproducible gain with memory use; reference comparison unavailable (reference prerequisite not met)".
  4. gain ∧ ¬mem → "reproducible gain without registered memory-use evidence".
  5. ¬gain → "no reproducible gain; curriculum−v2 contrast is <label>".
- All per-seed intervals, labels, memory tests and half intervals are kept even when a conjunction fails.
- Descriptive only: accuracies; gate telemetry (ρ, AUROC as P2G); the full-filler dev-accuracy curve from each run's
  telemetry, which measures transfer to full-filler episodes during each phase — its absence cannot establish failure
  to learn the no-filler distribution, and it cannot select the boundary, endpoint or schedule.
- Limits: cohorts differ in source/host; seed-0 prefix discrepancy unresolved; filler_len 0 also shortens sources
  ("no filler" vs "shorter episodes" not separated); recipe/distribution effect only, no mechanism.

## Ledger
Frozen guard policy; timeouts = 1.4 × own seed-specific v2 wall × 1.0: 8773 / 6952 / 11797 / 10809 s. Non-preemptible
3× rate $0.757728/container-h. Reservation **$11.12716980** (codex-verified: training $8.06790888, startup/teardown
$0.30309120, refused-replay allowance $0.35360640, CPU-overuse $0.60256332, image $0.30, fixed $1.50) under a
**requested $12 cap** — to be approved by the user only after the implementation audit and exact dry-run. The replay
allowance bounds refused duplicate invocations; it never authorizes another training attempt. Expected ≈ $4 is an
estimate, not a bound. New scoped runner/group/claims; P2G and older groups untouched.

## Order
prereg clearance → implement → CPU preflights → implementation audit → user cap approval → launch → validate all four
→ parity → one readings run → codex results audit.
