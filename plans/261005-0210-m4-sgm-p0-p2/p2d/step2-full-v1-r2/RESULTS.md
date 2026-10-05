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
