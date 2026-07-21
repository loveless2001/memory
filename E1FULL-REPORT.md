# E1FULL-REPORT.md — Full-Recipe Unfrozen Compactor: Third GT13 Attempt Under a Mobile Kernel

> **CLEAN RECERTIFICATION (2026-07-21): NO-SHIP.** The replacement n=60
> artifact uses 15 documents/domain reserved before training: 60 documents and
> 193 certification probes, with zero document and item overlap against the
> 94,056-item training manifest. Depth-1 fails GT13 and
> `max_certified_depth = 0`. Policy:
> `still-compact-v1:t1024:depth0:sha256:c00b2437fdd813cc`.

**Framing (per the brief):** FULLRECIPE established a law under a frozen
kernel — aggregation kernel-bound, pointwise smear-bound, routability
falling as compressors improve. This run dissolves the law's premise:
every question below is "does X survive kernel mobility," with both
survival and collapse pre-registered as reportable.

Status: **CLEAN RERUN COMPLETE; GT13 NO-SHIP** (2026-07-21). Config: E1
fixed logit scale √d_l = 16 (ESCAPE P0.2 selection), otherwise canonical;
fixed harness; 75,834 triplets from a balanced 94,056-item manifest. The
historical contaminated run is retained below only where it supports
training/mechanistic observations; its certification table is superseded.

Verdict line: Q1' routing keeps learning and becomes item-adaptive ·
Q2' **CLEAN HELD-OUT NO-SHIP; KL SIGNIFICANTLY WORSE THAN EVICTION** ·
Q3' branch (iii) — geometry loss-blind even content-routed ·
Q4' probe ladder RECOVERS (stack 0.857); gate marginal value reaches **0%**;
F2 null holds; F5 transfer regime-general · Q5' clean pointwise loss improves
strongly despite the distributional failure · Q6' mostly-nested shrinkage,
minority reshuffle.

---

## WP1 — Training

The clean checkpoint reached 1,500 steps without a tripwire. Its entropy rose
1.6064 → 1.6680 over the last 250 steps (+0.0616 > 0.01), so the registered
extension rule fired. It resumed from step 1,500 and completed 3,000 steps at
loss 0.1348 and entropy 1.8122. Step-tagged checkpoints and the final weights
are bound to holdout sha `64043bca…8882d` and manifest sha
`16e3ef0e…066aff`.

## Q1' — Routing at full scale

| step | 0 | 250 | 1000 | 1500 | 2000 | 3000 |
|---|---|---|---|---|---|---|
| entropy (nats) | 0.815 | 1.06 | 1.54 | 1.62 | 1.70 | **1.78** |
| R6 cross-item J | 1.000 | 0.789 | 0.737 | 0.641 | 0.567 | **0.550** |
| R7 cross-head J | 1.000 | 0.128 | 0.168 | 0.193 | 0.271 | **0.287** |
| d_min AUC (per-item kernels) | — | 0.500 | 0.503 | 0.509 | 0.500 | **0.504** |
| y+ (I2 1k) | — | 0.234 | 0.204 | 0.160 | 0.159 | **0.159** |

The historical routing run established the R6/R7 observations in this table;
the clean rerun did not repeat those separate sweeps. Its directly comparable
training telemetry confirms entropy 0.815 → 1.812. In the historical run,
routing keeps learning with 8× the data: entropy climbs to 1.78 before
plateauing; the kernel is **item-adaptive** (R6 0.550, far past the
registered <0.9 threshold, deepening monotonically); heads despecialize
immediately (R7 → 0.13) then partially re-organize (→ 0.29). The final
kernel touches essentially every source position across the probe batch
(kept-l0 8,186/8,188). Not one mobile lattice — per-item, per-head,
content-conditioned routing.

## Q2' — GT13 clean held-out replacement

The artifact of record is
`plans/260719-2328-e1full-unfrozen-full-recipe/summary-e1full-clean-v1-n60.json`
(remote source `compactor-certification/summary-e1full-clean-v1-n60.json`).
It records holdout sha `64043bca…8882d`, manifest sha
`16e3ef0e…066aff`, checkpoint weights sha `c00b2437…a46099`, all selected
document and probe IDs, and an explicit empty overlap audit.

| arm | agg KL | agg accΔ | pointwise lost | lost \| prior |
|---|---|---|---|---|
| eviction-matched | **0.0787** | +0.0014 | 0.683 | 0.631 |
| **clean unfrozen d1** | 0.1281 | **+0.0536** | **0.106** | **0.050** |
| clean unfrozen d4 (untrained-for) | 13.6640 | −0.1556 | 0.800 | 0.783 |
| control-0 (noise floor) | 0.0000 | +0.0000 | 0.072 | 0.000 |

Paired candidate-minus-eviction differences (95% bootstrap CI, n=60):

| arm | KL | accΔ | pointwise lost | lost \| prior |
|---|---|---|---|---|
| d1 | +0.0495 [0.0272, 0.0715] | +0.0522 [−0.0395, 0.1461] | −0.5778 [−0.7000, −0.4500] | −0.5806 [−0.7028, −0.4528] |
| d4 | +13.5854 [13.0532, 14.1428] | −0.1569 [−0.2958, −0.0167] | +0.1167 [−0.0278, 0.2611] | +0.1528 [0.0167, 0.2889] |

- **Primary GT13: NO-SHIP.** Depth-1's KL is worse than eviction and the
  paired interval lies wholly above zero. Its accuracy point estimate is
  higher, but that interval crosses both zero and the registered −0.02
  non-inferiority bound. The full point predicate and CI predicate both fail.
- **Pointwise result:** depth-1 sharply reduces both pointwise denominators;
  both paired intervals exclude zero. This benefit is real on the clean
  holdout, but it cannot override the distributional gate or enable runtime
  depth.
- **Depth result:** untrained depth-4 recurrence collapses on both
  distributional metrics. The longest contiguous certified prefix is empty,
  so `max_certified_depth = 0`.
- **Policy:**
  `still-compact-v1:t1024:depth0:sha256:c00b2437fdd813cc`. The historical
  contaminated policy `…8238173715edc8f1` and its task-anchored SHIP/ranking
  interpretation remain withdrawn.

### Consequences for the spec (v0.3.7 change note — no silent flip)

Keep evict-oldest-nonsink as the default L3 path. The clean checkpoint is a
research artifact, not an opt-in deployment policy. Its checkpoint metadata
and the clean result agree on `max_certified_depth = 0`.

## Q3' — F1 under per-item kernels: branch (iii), geometry stays loss-blind

Full 5,090-item protocol, kernel-distance features from PER-ITEM kept
sets (mean kept-set size 2,779 vs the frozen 1,024-lattice), new labels
(y+ 0.153 on needle-locatable):

| feature | AUC | 95% CI |
|---|---|---|
| d_min | **0.5003** | [0.4949, 0.5050] |
| d_mean | 0.5189 | [0.4977, 0.5404] |
| frac_needle_kept | 0.5190 | [0.4978, 0.5409] |

Branch rule (≥0.75 / 0.60–0.75 / <0.60): **(iii)**. The anticipated
"geometry becomes loss-bearing when routing reads content" flip did NOT
occur — at any of 12 checkpoints (I2) or on the full protocol. The
companion paper's internality claim survives its strongest test:
**write-time geometry is loss-blind even for a content-routed,
item-adaptive kernel.**

## Q4' — Probe survival: the ladder RECOVERS; the gate reaches its floor

GT16 relabel of all 30,847 manifest items (y+ 0.487 → 0.325 → **0.173**
across A/FR/E1F; 11,051 flips vs A), re-capture, probes retrained
(`e1f-readside-*`, arm-table `e1full_*` rows):

| arm (evicted-only test AUC) | A (subsampler) | FR (frozen) | **E1F (unfrozen)** |
|---|---|---|---|
| p2 self-check | 0.638 | 0.602 | 0.612 |
| f3 sink-heads | 0.762 | 0.730 | **0.764** [0.751, 0.776] |
| c2 linear (best layer) | 0.819 (L30) | 0.763 (L25) | **0.836 (L33)** |
| c2 MLP | 0.852 | 0.797 | **0.856 ± 0.003** |
| stack | 0.854 | 0.802 | **0.857 [0.847, 0.865]** |

- The frozen-FR degradation was policy-specific, not a trend: divergence
  readability fully recovers under the unfrozen compressor even though it
  loses half as many facts. Best layer moves again (30 → 25 → 33):
  probes are per-policy artifacts (re-certification rule re-confirmed).
- **F2 context-only control: 0.507 (chance)** — the relational null
  holds under content routing; the 0.86 remains behavioral-divergence
  prediction, not memory-content readout.
- **F5-style regime transfer** of the sink-head monitor across the
  frozen↔unfrozen divide: FR→E1F **0.759**, E1F→FR **0.727** zero-shot —
  the two-hook middle rung is regime-general across compressor classes
  (matches the original eviction↔compactor transfers 0.744/0.717).
- **Gate refresh** (98,355 rows, y+ 0.083): A2 weak-flat
  (0.570/0.568/0.564); GT16 operating point = never-expand (lost 0.089
  @ expand 0.000). **Gate marginal value: 0.0%** — the trend completes:
  **72% → 22.5% → 9.0% → 0%**. The question-blind gate's routable
  fraction reaches the floor under a good-enough compressor.
- **GT22'-style row:** the computation-reading stack still routes where
  the gate cannot: lost 0.086 @ 0.5% expansion (vs never-expand
  0.089 @ 0), and pushes BELOW never-expand — 0.049 lost @ 9.1%
  expansion. Reading the computation retains routing power at exactly
  the point where text-shadow gating has none.

## Q5' — Clean pointwise benefit does not buy certification

On the clean holdout, lost-given-prior-correct falls from 0.631 under matched
eviction to 0.050 under depth-1 compaction (paired difference −0.5806,
95% CI [−0.7028, −0.4528]). Raw lost-fact incidence falls from 0.683 to
0.106 (−0.5778 [−0.7000, −0.4500]). This is strong clean evidence that the
compactor preserves locatable facts better than eviction. It is not a trade
that earns certification: aggregation KL simultaneously worsens by +0.0495
[0.0272, 0.0715], so GT13 remains NO-SHIP. Historical cross-generation
monotonicity and ranking claims remain withdrawn because those arms were not
rerun on this reserved holdout.

## Q6' — Fragility: mostly-nested shrinkage, minority reshuffle

E1-protocol 2k relabel (`preprobe/e1-relabel-E1F.state.json`),
per-instance base rates per PREPROBE practice:

- Base rates: A 0.499 · B 0.418 · FR 0.321 · **E1F 0.172**.
- κ(E1F↔A) = 0.283 · κ(E1F↔B) = 0.312 · κ(E1F↔FR) = 0.417 — vs the
  frozen lineage's cross-scale 0.567–0.588 and reseed 0.745.
- **Nesting survives the regime change: 91.0% of E1F-lost ⊂ A-lost;
  78.5% ⊂ FR-lost.** Novel losses are the minority (9% vs A, 21.5% vs
  FR). Much of the κ drop is marginal-driven (base rates 0.172 vs
  0.499 cap κ even under perfect containment).
- Registered vocabulary: fragility is **largely content-intrinsic**
  (nesting survives a kernel-class change), with a real but minority
  regime-relative component. NOT the clean "reshuffle" outcome —
  and specifically NOT the "nesting 0.44" that the anticipatory
  draft of the arXiv v2 note assumed (that note needs rewording;
  see consequences).

## Trajectory figures

`plans/260719-2328-e1full-unfrozen-full-recipe/e1full-trajectories.png`
(entropy frozen-vs-unfrozen; R6/R7/d_min overlay — paper #2's closing
figure) and the ESCAPE overlay (all arms).

## Consequences for paper #2

- §2 (mechanism): unchanged; add the full-scale confirmation that escape
  persists and deepens for 3,000 steps.
- §5 (constructive): all pendings resolve positively EXCEPT the
  geometry flip: Q3' selects the branch where **internality holds even
  under content routing** — geometry never becomes the loss signal;
  reading the computation stays the only read-out. This is a stronger,
  simpler claim than the anticipated flip.
- §6 (certification): replace the contaminated two-verdict table with the
  clean held-out NO-SHIP result and its four paired intervals; retain depth 0.
- §7/§8 (downstream): gate-trend endpoint 0% (not asymptotic-above-zero);
  ladder recovery (0.857); F5 regime-generality; fragility =
  mostly-nested shrinkage (correct the draft's reshuffle framing).
- Companion arXiv v2 note (docs/revise.md): point 2's quantitative
  narrowing must be rewritten to the measured values (κ 0.28–0.42 with
  nesting 0.78–0.91 — stability is largely fact-intrinsic; the shared
  kernel accounts for the difference between 0.94 and ~0.8 nesting, not
  for nesting itself).

## Historical campaign cost ledger (actuals ≈)

These figures cover the original E1FULL campaign and contaminated certification.
The clean retraining and recertification spend was not exported in the signed
artifact and is therefore not estimated here.

WP1 1500 + extension ≈ $200 · I2 sweeps (12) ≈ $22 · certification ≈ $8
· F1/F2 sweep ≈ $8 · relabel fleet ≈ $95 · 2k relabel ≈ $4 · capture
fleet ≈ $45 · gate/probes/F3/CPU ≈ $8 · invalid n=60 reruns ≈ $45.
**Total ≈ $435** (budget
$285–450; extension fired, as budgeted).

## Unresolved questions

- Single-seed at full recipe (mid-scale escape is 3-seed); a full-recipe
  reseed would also enable a within-regime κ for the unfrozen class
  (currently only cross-regime κ exists for it).
- Depth>1 certification requires recurrence training (iterative family)
  — excluded by the do-not-build list; the depth-4 collapse is expected,
  not diagnostic.
- Whether a compressor class can close the remaining clean pointwise gap to
  the control floor (0.106 vs 0.072) without worsening aggregation KL.
