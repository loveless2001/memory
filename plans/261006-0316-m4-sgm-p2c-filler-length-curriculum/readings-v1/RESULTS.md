# P2C — audited registered results (closed)

The fixed filler-length curriculum passes the registered support rule at
N32 in both seeds: it beats v2, passes the memory-use tests, and recovers
at least half of the filler-off-training reference gain. At N64, positive
curriculum and reference gains of at least five percentage points are
excluded under the registered rule; memory use fails and the half-reference
comparison is unavailable. Support at both loads is therefore **false**.
These are results for the tiny random backbone synthetic binding task.

Prereg v0.2: `0c8d358`, SHA256
`b1bafbbdeca4668d8bd9270f54a970576332a6612c1bc81a55a5d705ab031413`.
Execution and analysis source: `d47fe17`; memsub SHA256
`09b05c16459c2caba55cddee651bd232e9de4ac5a87ce5ad11f3f18a8ab6d966`.
Report: [p2c-readings.json](p2c-readings.json), SHA256
`2fe1ab12be204abfa17e12292d73506954fb708bcee4677537821497dd04904b`.

Four new cells trained in `p2c-filler-curriculum-v1`, approved in #gravity
21398/21400 with a $12 cap. All ran exactly 1,500 optimizer updates:
updates 0–999 used filler length 0, and 1000–1499 used length 40, with
continuous model, head, optimizer and generator state. Filler writes were
enabled throughout. Evaluation always used length 40 with filler writes
enabled. “Label-free” in the registered reading means no filler-token
identity labels or oracle write mask; training still used supervised targets.

Training-artifact evaluation used seed `9_300_011+s`. The single registered
readings run used reserved seed `9_500_011+s`: 256 episodes of four queries
per corner, with none, bank-derange and read-offset interventions. Comparisons
are paired by evaluation episode within seed, not by training history.

## Registered readings

Heldout accuracy, percent, seed 0 / seed 1. All corners use E=on.
The reference retains the historical filler-off-training recipe and group.

| N | v2 | filler-off-training reference | curriculum |
|---|---|---|---|
| 32 | 2.83 / 2.83 | 76.86 / 72.66 | 60.55 / 64.94 |
| 64 | 1.95 / 1.66 | 2.15 / 1.95 | 1.95 / 1.66 |

Episode-paired differences and normal 95% intervals, percentage points:

| N | seed | curriculum − v2 | reference − v2 | half-reference margin |
|---|---|---|---|---|
| 32 | 0 | +57.71 [54.31, 61.12] | +74.02 [71.18, 76.87] | +20.70 [17.36, 24.04] |
| 32 | 1 | +62.11 [59.10, 65.12] | +69.82 [67.04, 72.60] | +27.20 [24.11, 30.29] |
| 64 | 0 | +0.00 [−1.27, 1.27] | +0.20 [−0.92, 1.31] | −0.10 [−1.26, 1.06] |
| 64 | 1 | +0.00 [−1.08, 1.08] | +0.29 [−0.84, 1.43] | −0.15 [−1.16, 0.86] |

A reproducible gain requires a difference of at least +5 points and a
positive paired lower bound in both seeds. The half-reference margin is
`curriculum − 0.5*v2 − 0.5*reference`; its status is evaluated only when
the reference itself has a reproducible gain.

- **N32:** curriculum and reference both have reproducible gains.
  Curriculum memory use passes in both seeds: bank-derange accuracy is
  1.86% / 1.46%, and both none-minus-derange and none-minus-read-offset
  lower bounds are positive. Reference memory use also passes; v2 fails
  in both seeds. Both half-reference lower bounds are positive. The exact
  registered reading is **“SUPPORTS: the label-free filler-length curriculum
  reproducibly beats v2 at N and recovers >= half of the filler-off-training
  reference.”** Descriptive gain fractions are 77.97% / 88.95%; these do
  not replace the registered half-reference criterion.
- **N64:** curriculum and reference contrasts are both **positive gain
  >=5pp excluded**. Every corner fails the registered memory-use test.
  Half-reference is **null**, because the measured E=on reference
  prerequisite fails. Its intervals remain computed and preserved.
  The exact reading is **“no reproducible gain; curriculum-v2 contrast is
  positive gain >=5pp excluded.”** This does not establish zero effect,
  an alternative blocker, or that all earlier interventions were ineffective.

## Descriptive telemetry and limits

N32 curriculum pooled effective rho is 0.916097 / 0.848537, compared with
v2 1.163600 / 1.088129. Mean applied-event AUROC is 0.495438 / 0.500666.
P2C registered no suppression criterion; neither these descriptive summaries
nor their differences establish a mechanism for the accuracy gains.

Full-filler development accuracy at updates 1000, 1200 and 1500 is
1.56% / 5.08%, 9.38% / 34.38%, and 61.33% / 69.53%, respectively, at N32.
The development curves measure transfer to full-filler episodes. Low
early transfer does not establish that the first phase learned nothing,
and the curves authorize no training extension or checkpoint selection.

Filler length 0 changes episode length, token exposure, positions, generator
progression and compute. Equal optimizer updates do not equalize these.
This is a recipe/distribution contrast; filler interference and address
learning remain possible explanations, not identified or excluded causes.
Historical v2/P2D/P2G/P2C cohorts differ in source and host. The earlier
seed-0 prefix continuity discrepancy remains unresolved. There is no R3,
pretrained-model, scaling or P3 claim, and no follow-up run is authorized
by this closure.

## Audit, preserved evidence and execution

Independent audit **PASS**, with zero reserved-seed re-evaluations. Separate
stdlib arithmetic recomputes all 36,864 saved rows' accuracies, episode-paired
intervals, memory-use tests, half-reference contrasts, ordered classifiers,
flags, readings and joint status. Development-seed 4242 replay checks all
12 corners' four-head event populations, projected/effective/applied means,
pooled rho and AUROCs with independent tie-aware CDF arithmetic. All match
within 1e-12. Development curves match the actual training telemetry.

- [Independent audit output](audit/independent-results-check.json), SHA256
  `b0bfc99e3e877f527328b8b9380eb4e6342a1f800e8ddc6855ca78f0cdf178a0`;
  [verifier snapshot](audit/independent-results-check.py).
- [Training artifact audit](audit/training-artifacts-check.json): four cells
  match their grid, launch, parameters, source, attempt, deadlines and
  published seed; all 20,480 artifact rows independently agree. Streamed
  metrics add only the verified manifest hash to the volume metrics.
- [Lifecycle and billing audit](audit/lifecycle-billing-check.json): app
  `ap-WCxVagWdH2A0O7sEhZnofv` is stopped with zero containers, verified
  at 06:31 UTC on 2026-10-06. App-filtered cost is **$3.94734272**, provisional
  pending billing backfill, against cap $12 and reservation $11.12716980.
  All four first attempts completed within their registered deadlines;
  no replay or HALT was consumed.
- [Replay archive](replay-evidence.tar.gz), SHA256
  `04df258eccea710e1d7d0649d4a8c62436e37a937e02c59caccb13a757b5254a`:
  252 files, 4,633,789 compressed bytes. It preserves all 14 bound checkpoint
  cells (12 registered corners plus two N16 parity-only cells), saved rows,
  source/index/grid/prereg, preflight and launch/validation records, and
  reviewer evidence at original repository paths.
- [Archive manifest](replay-evidence-manifest.json),
  [byte verification](audit/archive-verification.json), and
  [isolated saved-statistics replay](audit/archive-statistics-replay.json).
  All members match; originals are unchanged. The isolated replay passes
  provenance, parity, saved-row statistics and decisions without remote
  volume access, network access or further model evaluation.

Readings-time parity passed all eight complete legacy fixtures, parsed and
byte-equal. Start/end observer identities agree and all consumed hashes
match. The original toy smoke used reserved seed *values* before the fix,
on untrained N4 models rather than the registered population; that incident
is retained in the implementation audit. `8c3161a` moved the toy to separate
seeds and bound the actual prereg bytes. Full-suite evidence records 206
passed with explicit exit status 0; preflight r2 passed on that source.

To replay, use an isolated checkout containing producer commit `d47fe17`,
extract the archive at the repository root and run the canonical
`plans/reports/codex-261006-p2c-results-independent-audit.py`. Use
`--saved-only --out /tmp/p2c-audit.json` for the stdlib saved-statistics audit.
The full audit needs the pinned analysis environment and replays only
development-seed gate telemetry. The copied verifier under `audit/` is a
snapshot; run its canonical archived path so repository-root resolution
is correct. Historical preflight evidence belongs to `8c3161a`, before
the approved-cap change. SHA256SUMS covers the closed bundle.
