# FULLRECIPE-REPORT.md — Full-Recipe Compactor: Does Scale Escape Position-Kernel Collapse?

**Framing (per the brief):** this run does not exist to produce a better
compactor. It exists to answer five pre-registered questions about whether
the v0.4 paper's Regime-II findings — certified against a subsampler —
survive a real synthesizer. Each question had its outcomes enumerated in
FULLRECIPE.md before any run started; every outcome below is reported in
that pre-registered vocabulary.

Status: **COMPLETE** (2026-07-19). Verdicts: Q1 outcome (c) — collapse is
not a scale artifact, kernel bitwise frozen at init · Q2 NO-SHIP
(0.2566 vs 0.1218, scale-invariant) · Q3 branch (iii) — geometry
loss-blind, internality claim stands · Q4 DEGRADED-but-readable
(stack 0.802 vs 0.854; F2 null holds; GT22 win transfers) · Q5 advantage
persists and grows (0.188 vs 0.583). Total spend ≈ $440.

---

## P0 — Corpus completion + instrumentation

### C1 rationale audit — verdict: PARTIAL
Only 19,619 / 98,355 items carried rationale-augmented traces (the M3.5
6k-per-domain prep after short-context drops: fin 5,474 / lit 5,878 /
code 4,519 / legal 3,748). Teacher rationale pass over the remainder was
required.

- 200-item stride sample (50/domain): format rate 86.5%, gold accuracy
  67.3% — statistically identical to the existing traces (86.5% / 66.0% on
  a 400-item audit), same `<|endoftext|>`-continuation artifact (present in
  the originals at 24%; eos is `<|im_end|>` in both protocols).
- Batched-vs-unbatched equivalence on 24 already-traced items: 23/24
  letter agreement, identical gold accuracy (18/24 both), 9/24 bitwise
  trace matches with median 52-token shared greedy prefix (expected bf16
  divergence under left-padded batching; distributionally equivalent).
- Legal yield lowest (52% on sample), consistent with the known OCR/short
  -doc weakness of that domain.

### C2 training mixture — DONE
Domain-downsampled to the smallest B.3 domain (code = 23,563):
94,252 nominal items (23,563 × 4), manifest sha256
`8e0bb280b75d87d8382586027ecb69242c4ebe510bdfeae18de5941be5afe564`
(compaction_policy_version material). All 19,619 existing traces fall
inside the mixture (0 orphans); remainder = 74,633 items.
Final traced mixture (post short-ctx drops): TBD after merge.

### I1 / I2 instrumentation — BUILT
- I1: every 50 steps, fixed 128-item probe batch (first 128 rows of the
  shuffled full mixture — same probe batch for every scale point), per-layer
  block-1 cross-attention row entropy (mean/p10/p90, nats) + argmax-kernel
  position histograms (kept-position sets) + exact per-item layer-0 argmax
  at checkpoint steps.
- I2: per step-tagged checkpoint (every 250 steps; every 47 on mid), GT16-
  protocol relabel of the fixed 1k subsample (first 1,000 of the E1 2k
  sample) fused with the F1 kept-kernel capture → d_min univariate AUC per
  checkpoint.

### GT26 sanity — GREEN
GT11 identity pass-through: PASS (reference config, 2 tests green,
2026-07-19). GT12-class loss tripwire armed at step 300 of the full run
(mean of last 25 steps < 0.4; checkpoint A's batch-4 curve had 0.323 at
that point).

### Harness finding (unplanned, load-bearing): M3.5 DDP trainer never synced gradients
The M3.5 inner script called `compactor.module.compact(...)`, bypassing the
DDP wrapper's forward. DDP only arms its gradient hooks in `DDP.forward`,
so **gradients were never all-reduced**: verified empirically (2-rank test:
bypass → per-rank grads differ; wrapper → identical). Consequences:

- Every shipped checkpoint (A `single-t1024-T8k`, reseed B, the t∈{128,512,
  1024} sweep, the iterative family) is a **single-replica model trained at
  effective batch 4** with per-rank init (`seed + rank`); rank 0's replica
  was saved. The "effective batch 32" in COMPACTOR.md §2.2 was never
  realized by that harness.
- Behavioral findings about those artifacts (position kernel, probe AUCs,
  GT13–GT25 numbers) are unaffected — they measure the artifact as it is.
- Provenance statements in the v0.4 paper need a correction note (paper #2
  + arXiv v2 note; never silent, per the brief's stop conditions).
- E1's A↔B seed comparison remains valid (both instances trained under the
  same buggy regime, seed the only difference).
- The FULLRECIPE trainer fixes this for the new runs: identical init on all
  ranks + explicit gradient all-reduce (true effective batch 32) + rank-0
  parameter broadcast at every checkpoint. The scale points therefore
  differ from A in batch semantics as well as data volume; this is the
  recipe-compliant choice (the brief pre-registers "effective batch 32")
  and is flagged wherever A sits on the collapse curve.

## WP1 — Training

Final traced mixture: **75,998 items** (80.6% of the 94,252 nominal after
short-context drops; lit 23,075 / fin 21,502 / code 17,696 / legal 13,725
— nominal selection was balanced at 23,563/domain, drops skew realized
counts, legal worst per its known OCR/short-doc profile). ≈0.62B context
tokens at 8k. Deterministic shuffle seed 1234; train-ids sha256 in
`corpus-fullrecipe/train-mixture-stats.json`.

| run | items | steps | batch | loss@300 (mean last 25) | final loss | wall |
|---|---|---|---|---|---|---|
| mid (1/8) | 9,498 | 188 | 32 (true) | n/a | 0.365 | ~35 min |
| full | 75,998 | 1500 | 32 (true) | **0.394** (GT12 pass, narrowly) | 0.357 | ~2.6 h |

Both on 8×H100, corrected KL objective, β=0, T=8k, t=1024, lr 4e-5,
warmup 100. Step-tagged checkpoints every 250 (mid: 47). No tripwire.
**Extension to 3000 cancelled** by the pre-registered rule
(entropy delta 0.000000 < 0.01; Q1 outcome (c) abort rule also applies).

## WP2 — The five questions

### Q1 ESCAPE — outcome (c): entropy NEVER leaves zero; the kernel never moves at all

Entropy-vs-step (mean over 36 layers, block-1 cross-attn rows, nats,
fixed 128-item probe batch, identical measurement at every point):

| scale point | items × steps × batch | entropy (max over run) | kept-l0 |
|---|---|---|---|
| init (step 0) | — | 1.16e-10 | 1024 |
| mid 1/8 | 9,498 × 188 × 32 | 1.16e-10 (flat, 5 pts) | 1024 |
| A (prior, 1/40-class) | 19,619 × 1500 × 4* | 1.16e-10 (snapshot) | 1024 |
| B (reseed of A) | 19,619 × 1500 × 4* | 1.16e-10 (snapshot) | 1024 |
| full recipe | 75,998 × 1500 × 32 | 1.16e-10 (flat, 31 pts) | 1024 |

*batch-4 single-replica per the DDP finding above.

There is no transition and no drift: every telemetry point of every run
sits at the numerical floor (1.16e-10 nats ≈ the bf16/softmax precision
limit of a d_l=256-scaled QK-normed logit). Stronger still, the
**argmax kernel is bitwise frozen at its initialization**: kept-position
sets at step 0, full-recipe step 1500, and instance A are identical
(Jaccard 1.000 on every layer probed; 1024 positions/layer; stride-8
lattice on the 8k train shape — 1020 gaps of 8, 3 of 9 — consistent with
F1's stride-2.998 on the 4k deployment shape, 3068/1024 ≈ 3.0).

**Verdict (pre-registered vocabulary): position-kernel collapse is NOT a
scale artifact on this corpus/config.** The position-dominated identity
init is a fixed point of the Still training objective here: the value/
output pathway trains (loss 0.58 → 0.36, min 0.21) while the position pathway never
budges, at any data scale from 9.5k to 76k items and true batch 32. This
directly qualifies the Still recipe's transfer to this corpus/config and
is the signature finding for paper #2.
### I2 — online kernel-geometry probe (d_min AUC vs step)

GT16-protocol relabel of the fixed 1k subsample at every step-tagged
checkpoint, d_min against the (frozen) kept kernel
(`fullrecipe-telemetry/i2-*`, curve in the campaign plan dir):

| ckpt | mid-47 | mid-94 | mid-141 | mid-188 | full-250 | full-500 | full-750 | full-1000 | full-1250 | full-1500 |
|---|---|---|---|---|---|---|---|---|---|---|
| y+ (1k) | .409 | .379 | .375 | .370 | .354 | .357 | .331 | .328 | .331 | **.318** |
| d_min AUC | .514 | .526 | .512 | .524 | .526 | .527 | .514 | .522 | .521 | **.521** |

Write-time geometry is **loss-blind at every point of training** (AUC
pinned at ~0.52, F1's 0.509 class), while the y+ rate falls monotonically
— the value path rescues facts without the geometry ever becoming
predictive. There is no phase anywhere on the trajectory where kernel
distance carries loss signal.

### Q2 GT13 RETRY — verdict: NO-SHIP (again), numbers nearly unchanged from M3.5

Full certification, M1 harness unchanged, matched retained budget
(keep = 4 + 1024 + 1024 of 4096), per-axis, noise-floor row, depths {1, 4}
(deployment depth = 1 for the single-pass family). ADDENDUM-M35 table
format (`compactor-certification/summary-fullrecipe.json`):

| arm | agg mean KL | agg accΔ | pointwise lost | lost \| prior-correct |
|---|---|---|---|---|
| eviction-matched | 0.1218 | −0.0486 | 0.597 | 0.583 |
| compactor-d1 (full recipe) | **0.2566** | **+0.0625** | 0.229 | **0.188** |
| compactor-d4 (recurrence, untrained-for) | 15.82 | −0.236 | 0.944 | 0.917 |
| control-0 (noise floor) | 0.0000 | +0.0000 | 0.069 | 0.000 |

> **Superseded (2026-07-20):** these are n = 12-document measurements.
> All arms were re-certified at n = 60 with paired CIs; the frozen
> full-recipe row becomes KL 0.2820 / accΔ +0.1019 / pointwise 0.210
> against eviction 0.0842 / −0.0650 / 0.644, all CI-separated. The
> verdict below is unchanged in direction. See E1FULL-REPORT Q2'.

GT13 predicate (beat eviction KL AND stay within 0.02 accΔ): **fails on
KL** (0.257 vs 0.122, ~2.1×) despite the accuracy delta flipping positive.
M3.5's 1/40-scale caveat is now resolved: at full recipe the aggregation
KL is 0.2566 vs M3.5's 0.263 — **scale changed nothing on the aggregation
axis**, exactly what a bitwise-frozen position kernel predicts (the
certified object is still a strided subsampler with a trained smear).
`max_certified_depth = 0`; depth-4 recurrence without recurrence training
collapses (KL 15.8). Policy version emitted:
`still-compact-v1:t1024:depth0:sha256:41e72e65a15b245d` (weights hash +
depth in `compaction_policy_version`, per deliverables).

evict-oldest-nonsink **stays the default L3 path**.
### Q3 F1 RETRY — branch (iii) again: geometry loss-blind, internality claim STANDS

The kept kernel under the full-recipe checkpoint is bitwise identical to
instance A's at the deployment shape too (keepcount equal on all 1,260
overlapping F1 test items; residual30 differs — max |Δ| 6.0 — so the value
path really did retrain). Kernel-distance features on the full F1 protocol
(5,090-item test subsample, 3,963 needle-locatable, NEW labels y+ 0.332):

| feature | AUC | 95% CI (doc-cluster bootstrap) |
|---|---|---|
| d_min | **0.5165** | [0.5052, 0.5275] |
| d_mean | 0.5004 | [0.4811, 0.5197] |
| frac_needle_kept | 0.5004 | [0.4807, 0.5208] |

Branch rule (≥0.75 / 0.60–0.75 / <0.60): **(iii)** — smear dominates. No
flip to (i)/(ii), so the v0.4 internality claim for synthesis is NOT
softened; write-time geometry remains loss-blind under a real synthesizer
at full recipe (and, per I2, at every intermediate checkpoint).

### Gate refresh under the full-recipe policy (Q4 prerequisite)

Full §17.5 relabel (98,355 rows, 12 workers) + gate retrain
(`gate-eval/gate-refresh-fullrecipe.json`):

- Label base y+ falls to **0.135** (A-policy relabel: higher) — the
  full-recipe compactor loses fewer facts overall; 6,539/30,847 manifest
  labels flip (21%), manifest y+ 0.487 → 0.325.
- A2 decomposition (evicted-only AUC, 3 seeds): full 0.579 ± .003,
  features-only 0.567 ± .002, embeddings-only 0.577 ± .007 — the M3.5
  "content > mechanics, both weak" shape persists with the content edge
  now marginal. The trained-gate ceiling stays in the 0.58 class.
- GT16 end-to-end: lost 0.139 @ expand 0.055 (τ 0.197, ECE 0.008),
  passes the M3 operating point — but the gate's marginal reduction vs
  its OWN policy's never-expand (0.153) is **9.0%**, down from 22.5%
  (M3.5) and 72% (eviction). Monotone pattern across regimes: the better
  the compressor, the less routable the residual loss is to a
  question-blind gate.
### Q4 PROBE SURVIVAL — verdict: DEGRADED (readable); relational null HOLDS

Full pipeline rerun under the full-recipe compactor: GT16 relabel of all
30,847 manifest items (y+ 0.487 → 0.325, 21% flips), re-capture (8 slices,
light protocol), probes retrained from scratch on the new labels
(`fr-readside-*`, arm-table gained `fullrecipe_*` rows):

| arm (evicted-only test AUC) | subsampler (A) | full recipe | Δ |
|---|---|---|---|
| p2 prompted self-check (free) | 0.638 | 0.602 | −0.036 |
| f3 sink-heads (8 scalars, middle rung) | 0.762 | 0.730 [0.720, 0.740] | −0.032 |
| c2 linear (best layer) | 0.819 (L30) | 0.763 (L25) | −0.056 |
| c2 MLP | 0.852 | 0.797 ± 0.001 | −0.055 |
| stack | 0.854 [0.846, 0.862] | **0.802 [0.793, 0.811]** | −0.052 |
| c0 surface floor (reference) | 0.564 | — | |
| trained gate ceiling (this policy) | — | 0.579 | |

- **Degraded, not unreadable**: the whole ladder shifts down ~0.03–0.06
  under true blending but keeps its ordering and stays far above both
  floors. Divergence-prediction is compressor-difficulty-SENSITIVE but not
  compressor-difficulty-bounded in the fatal sense.
- Best read-out layer moves 30 → 25 — the value-path retrain relocates
  where divergence is most linearly visible; probes must be retrained
  per-instance (re-confirming the PROBE.md per-policy certification rule).
- **F2 context-only control: 0.512 (chance, OOF GroupKFold refit on the
  5,090-item context-only re-forward)** — strip the question and nothing
  is decodable from the full-recipe compactor's states either. The
  relational null holds under synthesis at scale; the 0.80 stack remains a
  behavioral-divergence predictor, not a memory-content readout.
- **GT22-style end-to-end row**: stack-gated operating point
  **lost|prior-correct 0.146 @ expand_all 0.0095** vs the refreshed gate's
  0.139 @ 0.055 and never-expand 0.153 @ 0 — the computation-reading
  stack matches the gate's lost-rate class at ~1/6 of its expansion
  budget. The GT22 win transfers to the real synthesizer.
### Q5 SMUGGLING — advantage PERSISTS and grows under true blending

The M3.5 pointwise comparison (0.271 vs 0.583 lost-fact at matched budget)
rerun under the full-recipe compactor: **0.188 vs 0.583**
(lost-given-prior-correct; raw incident 0.229 vs 0.597). Synthesis
smuggles MORE needle content through at full recipe than at 1/40 scale —
the value-path smear, not the kernel, is what improved with data. The
§13.4 rule still re-attaches: pointwise loss remains far above the noise
floor (0.000), so aggregation-only certification ⇒ gate mandatory under
every compaction regime.
### Fragility re-check + B⊂A — nesting SURVIVES the regime change

E1-style relabel of the fixed 2k sample under the full-recipe instance
(FR), exact GT16 protocol (`preprobe/e1-relabel-FR.state.json`):

- y+ base rate: FR **0.321** vs A 0.500 (B was 0.418) — per-instance
  base-rate drift is large under the regime change; quote rates
  per-instance, as established in PREPROBE.
- κ(A↔FR) = **0.567**, κ(B↔FR) = **0.588** — vs the seed-only
  κ(A↔B) = 0.745. A regime change moves the lost-set more than a reseed,
  but agreement stays far above chance: content structure persists.
- **B⊂A-style nesting vs the full-recipe instance: 94.1%** of FR-lost
  items (604/642) are also A-lost; only 38 novel losses. The full-recipe
  lost-set is nearly a subset of A's — scaling the recipe RESCUES items
  from the fixed lattice's loss set rather than reshuffling it. Combined
  with the frozen kernel (Q1), this is the cleanest evidence yet that
  which facts die is decided by content interacting with a FIXED
  position lattice, and more value-path training monotonically shrinks
  (not permutes) that set.

## Consequences for paper v0.4

Per the brief: no v0.4 edits; corrections go to paper #2 and an arXiv v2
note — never silent.

1. **Training-provenance correction (required):** all Regime-II
   checkpoints in v0.4 were trained WITHOUT gradient sync (effective batch
   4, single replica, per-rank init) due to the DDP-bypass harness bug.
   Every statement citing "effective batch 32 / Still recipe constants"
   for those artifacts needs the correction note. No behavioral number
   changes.
2. **"1/40-scale training caveat" resolved — in the unexpected
   direction:** at full recipe (76k rationale-traced items, true batch 32)
   the aggregation KL is 0.2566 vs M3.5's 0.263. The GT13 no-ship was not
   a scale artifact. v0.4's caveat can be replaced by a definitive
   statement (correction note strengthens the paper).
3. **Delta-position-kernel finding upgraded:** v0.4 reports the shipped
   compactor's kernel as a collapsed delta lattice; this campaign shows
   the lattice is the INIT kernel, bitwise frozen through training at
   every scale — a stronger and cleaner mechanism claim (init fixed
   point, not training collapse). Fold into paper #2; v2 note may cite.
4. **Numbers that transfer unchanged:** routability asymmetry direction
   (gate marginal value 72% eviction → 22.5% M3.5 → 9.0% full recipe —
   monotone), pointwise smuggling advantage (0.583 → 0.271 → 0.188),
   probe readability (0.854 → 0.802, degraded not broken), F2 null
   (holds at chance in both regimes). No v0.4 claim is overturned; two
   get sharper.

## Paper #2 skeleton (Q1–Q5 → sections)

1. **Intro/claim:** a Still-class compactor's position pathway is a fixed
   point of the distillation objective on this corpus/config — compaction
   IS strided subsampling plus a trained smear, at every scale we can
   afford.
2. **§ The frozen kernel (Q1 + I1/I2):** entropy flat at 1.16e-10 across
   init/9.5k/19.6k/76k; kept sets bitwise identical (J=1.000); stride-8
   (train shape) / stride-3 (deploy shape) lattice; d_min AUC ~0.52 at
   every checkpoint. Signature figure: entropy-vs-step overlay + kernel
   Jaccard matrix.
3. **§ Certification at scale (Q2 + Q5):** per-axis table (0.2566 vs
   0.1218 KL; accΔ flips positive; 0.188 vs 0.583 pointwise) — the
   aggregation axis is kernel-bound (scale-invariant), the pointwise axis
   is smear-bound (improves with data). Depth-4 recurrence collapse
   (KL 15.8) without recurrence training.
4. **§ What the gate can and cannot route (gate refresh):** marginal
   value 72% → 22.5% → 9.0% as the compressor improves; A2 decomposition
   stays weak-flat under synthesis.
5. **§ Reading the computation still works (Q3 + Q4):** geometry
   loss-blind (branch iii, d_min 0.517); probes degrade ~0.05 but ladder
   and GT22-class deployment win survive; best layer moves 30→25 (retrain
   per policy); F2/F4-class context-only null holds.
6. **§ Fragility structure (E1 recheck):** lost-sets nest across regime
   change (94.1% ⊂ A); scaling rescues, never reshuffles — content ×
   fixed-lattice determines who dies.
7. **§ Harness forensics appendix:** the DDP-bypass bug, its detection,
   and why single-replica batch-4 training left every behavioral
   conclusion intact (A↔FR κ 0.567 despite the regime change).
8. **Limitations:** one backbone, one corpus family, t=1024 single-pass;
   entropy floor is measurement-limited at d_l=256 logit scale; no
   iterative-family retrain at full recipe (do-not-build).

## Cost ledger (actuals, ≈)

| item | cost |
|---|---|
| C1 batched rationale pass (8×H100, 3.9 h) | ~$130 |
| C1 sample + equivalence + GT11 + C2 + pack | ~$12 |
| WP1 full run (8×H100 ~2.6 h) + mid (~35 min) + smoke | ~$110 |
| A/B I1 snapshots | ~$3 |
| Q2/Q5 certification | ~$8 |
| Q3 F1/F2 sweep (4×H100) | ~$8 |
| E1 FR relabel + I2 sweep (10 ckpts) | ~$23 |
| Q4 relabel fleet (12×H100 ~1.8 h) | ~$95 |
| Q4 capture fleet (8×H100 ~1.4 h) | ~$45 |
| gate refresh + probe train + F3 (L4) + CPU misc | ~$6 |
| **Total** | **≈ $440** (envelope $700–1,180) |

## Unresolved questions

- Whether a NON-identity (e.g. content-seeded) init escapes the fixed
  point at this scale — out of scope (architecture change), but paper #2's
  natural next experiment.
- Whether the entropy floor (1.16e-10) hides sub-argmax content routing:
  argmax sets are frozen, but second-order attention mass was not
  telemetered. The frozen keepcount + loss-blind d_min make this unlikely
  to matter for loss routing.
- Iterative-family behavior at full recipe (depth>0 certification)
  remains open — excluded by the do-not-build list.
