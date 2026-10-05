# P2G — audited registered results (closed)

The registered training-recipe conjunction passes at N16 and N32. The gate
recipe has a reproducible N16 gain without registered pooled suppression;
its mechanism remains unresolved. At N32, a positive gate gain of at least
five points is excluded under the registered rule. These findings concern
the tiny random backbone synthetic binding task and historical recipe
contrasts; they do not establish an address-learning mechanism, pretrained
behavior, scaling, or a P3 result.

Prereg v0.2: `25fdbc5`, SHA256
`c2fa7394e9e621766af705743d46715b9584c83e161a90bdfd45d928908925c3`.
Execution and analysis source: `2613ced`; memsub SHA256
`5c3b5420152de933a04264604fdc1fb6312a24609b631ad9fd0c614755bde6a2`.
Report: [p2g-readings.json](p2g-readings.json), SHA256
`03d47be48fcfcc311fde34a0d25733bc085caa3259b89f8f0a7687debd125818`.

Six new cells trained for exactly 1,500 steps in
`p2g-selective-write-v1`, approved in #gravity 21341 with a $13 cap.
Training-artifact evaluation used published seed `9_300_011+s`.
The single registered readings run used reserved seed `9_400_011+s`, with
256 episodes of four queries per corner and the none, bank-derange, and
read-offset interventions. Comparisons are paired by episode within seed.

## Q2: training recipes and evaluation settings

Heldout accuracy, percent, seed 0 / seed 1. T indicates training filler
writes; E indicates evaluation filler writes.

| N | T=on, E=on (v2) | T=on, E=off | T=off, E=off | T=off, E=on | gate, E=on |
|---|---|---|---|---|---|
| 16 | 5.57 / 56.05 | 5.76 / 64.55 | 94.82 / 96.19 | 87.30 / 89.16 | 80.86 / 80.96 |
| 32 | 2.34 / 2.05 | 2.34 / 2.25 | 84.47 / 80.76 | 77.44 / 73.73 | 3.81 / 1.86 |

Contrasts in percentage points, seed 0 / seed 1. A reproducible gain requires
at least +5 points and a positive paired 95% lower bound in both seeds.
Every interval is retained in the report.

| contrast | N16 difference | N16 label | N32 difference | N32 label |
|---|---|---|---|---|
| training off minus on, E=off | +89.06 / +31.64 | reproducible gain | +82.13 / +78.52 | reproducible gain |
| training off minus on, E=on | +81.74 / +33.11 | reproducible gain | +75.10 / +71.68 | reproducible gain |
| evaluation off minus on, T=on | +0.20 / +8.50 | neither | +0.00 / +0.20 | positive gain >=5pp excluded |
| evaluation off minus on, T=off | +7.52 / +7.03 | reproducible gain | +7.03 / +7.03 | reproducible gain |

At both N, the registered reading is: **reproducible gain for the
no-filler-write training recipe at both eval settings; eval-setting
conjunction not met**.

Evaluation-time filler-write damage is present in the T=off models:
omitting those writes improves both seeds by about seven points. The
evaluation conjunction fails because T=on does not pass both seeds. Preserve
the N16 seed-1 gain of +8.50 points; the N32 upper bounds exclude a positive
gain of at least five points in both seeds. These are recipe/setting
contrasts, not proof that training filler prevents learning usable addresses.

The interaction is descriptive and does not change labels: N16
+7.32 / -1.46 points, N32 +7.03 / +6.84 points.

## Q1: closed gate initialization

Gate minus v2 paired differences and 95% intervals, in percentage points:

| N | seed | gate accuracy | difference [interval] | pooled rho | memory-use pass |
|---|---|---|---|---|---|
| 16 | 0 | 80.86% | +75.29 [72.57, 78.01] | 0.619191 | true |
| 16 | 1 | 80.96% | +24.90 [21.44, 28.36] | 0.595544 | true |
| 32 | 0 | 3.81% | +1.46 [-0.02, 2.95] | 1.056951 | true |
| 32 | 1 | 1.86% | -0.20 [-1.31, 0.92] | 0.842717 | false |

- **N16:** reproducible gain without registered pooled suppression;
  mechanism unresolved. Memory use passes in both seeds. The oracle
  prerequisite is a reproducible gain; half-oracle is true, with margins
  +30.66 [28.13, 33.20] and +4.83 [2.12, 7.55] points. The registered
  suppression threshold is rho <=0.20 in both seeds, and both fail.
- **N32:** no reproducible gain and no registered pooled suppression;
  gate-v2 contrast is positive gain >=5pp excluded. Half-oracle is false
  although the oracle prerequisite passes. Retain seed 0's memory-use pass
  despite near-chance accuracy; seed 1 and the both-seed conjunction fail.

Gate AUROC means are descriptive: N16 0.611866 / 0.559731;
N32 0.445944 / 0.520719. The headline suppression criterion pools filler
and binding event means across all four heads. Neither these ratios nor
descriptive AUROCs establish a causal explanation for the accuracy gain.

## Audit, preserved evidence, and execution

Independent audit **PASS**, with zero reserved-seed evaluations. A separate
stdlib implementation recomputes all 61,440 saved fresh rows' accuracies,
episode-paired intervals, interactions, half-oracle contrasts, memory-use
tests, classifier labels, flags, and registered readings. Development-seed
4242 replay checks all 20 corners' four-head event populations, projected
and effective means, applied/skipped events, pooled rho, and AUROCs using an
independent CDF/tie computation. All match within 1e-12.

- [Independent audit output](audit/independent-results-check.json), SHA256
  `8dd8707933d92e0007ca630b2c67ed2e9b2184a853ac384fc9ce6b88448f29d3`.
- [Verifier source snapshot](audit/independent-results-check.py). Its canonical
  `plans/reports/` path is preserved in the replay archive.
- [Training artifact audit](audit/training-artifacts-check.json): six cells
  match their own grid, launch, parameters, source, attempt, deadlines, and
  published evaluation seed; local/volume copies agree.
- [Lifecycle and billing audit](audit/lifecycle-billing-check.json): app
  `ap-S6aKXZB9FPh9MBYkLsVdDN` is stopped with zero containers; reported
  app-filtered cost **$3.44816365**, provisional pending billing backfill,
  against approved cap $13 and reservation $12.32978160.
- [Replay evidence](replay-evidence.tar.gz), SHA256
  `56f98f0b3d6b2397531bed235ac6c850eaa8e6f1f0736c2140c5815576b98fb1`:
  222 files, 4,059,356 compressed bytes, including all 12 consumed checkpoint
  cells, saved output rows, bound code/index/grid/prereg, launch/validation
  evidence, and auditor source/output at original repository paths.
- [Archive manifest](replay-evidence-manifest.json),
  [byte verification](audit/archive-verification.json), and
  [archived statistics replay](audit/archive-statistics-replay.json). All
  archived members match; originals are unchanged; replayed saved-row
  statistics and flags pass without volume access or fresh evaluation.

To replay the full audit, use an isolated checkout containing commit
`2613ced`, extract the archive at its repository root, and run
`python plans/reports/codex-261006-p2g-results-independent-audit.py` from that
root with the analysis dependencies installed. The verifier expects this
canonical path and access to the producer's Git history. It reads the saved
reserved-seed rows and replays only development-seed 4242 gate telemetry.

Readings-time parity passed all six complete legacy fixtures, parsed and
byte-equal. Start/end observer identities are equal, every consumed
parameter/input hash matches, and output source hashes match producer commit
2613ced. Preflight r1/r2/r3 parity agrees as well. SHA256SUMS covers the
closed bundle.

Historical cohorts differ in source and host; shared evaluation episodes
do not make training histories identical. The earlier seed-0 long-run
1500-step continuity discrepancy remains uninvestigated. This experiment
did not register an address-learning test. Initialization telemetry is not
a training result. No curriculum, follow-up training, P3, pretrained-model,
or scaling claim is authorized or established by closing P2G.
