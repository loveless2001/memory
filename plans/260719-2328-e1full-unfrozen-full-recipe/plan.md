# E1FULL Campaign — Full-Recipe Unfrozen Compactor (Third GT13 Attempt)

> **CLEAN CERTIFICATION COMPLETE (2026-07-21): NO-SHIP.** The replacement
> run has zero document/item overlap. GT13 fails and the certified policy is
> `still-compact-v1:t1024:depth0:sha256:c00b2437fdd813cc`.

Brief: /E1FULL.md. Selected config (ESCAPE P0.2): E1 fixed logit scale √d_l = 16,
otherwise canonical. Framing: every question is "does X survive kernel mobility."

## Status

Clean-rerun remediation (2026-07-21): holdout `64043bca…8882d` (60 docs,
15/domain, 193 probes); balanced manifest `16e3ef0e…066aff` (94,056 unique
items, 23,514/domain); training triplets 75,834 with zero document/item
overlap. Two-step smoke passed. Training completed at 3,000 steps in Modal app
`ap-29tVezzeS6JTfh9bAvbzCT`; clean n=60 certification completed as
`ap-R7H9SiqDVAnmI1JwMoI61a`. Both apps are stopped with zero tasks.

| Item | Status |
|---|---|
| P0.1 ESCAPE closeout (E2, 3-seed, R3/R4, R6/R7) | ✅ committed (feat(escape)) |
| P0.2 arm selection | ✅ E1 fixed √d_l (tie with E2 → simplest lever) |
| P0.3 GT27 (init<1.5, tripwire<0.45@300, NaN watchdog) | ✅ wired (--tripwire-loss, isfinite abort) |
| WP1 clean retrain `e1full-clean-v1-t1024-T8k` (75,834 triplets) | ✅ 3000/3000; loss 0.1348; entropy 1.8122; checkpoint sha `c00b2437…a46099` |
| WP1 extension decision (slope>0.01 nats over last 250) | ✅ FIRED: 1.6064→1.6680, +0.0616 > 0.01; resumed step 1500 to 3000 |
| Q1' trajectories (historical R6/R7/d_min; clean entropy) | ✅ historical item-adaptive result retained; clean telemetry entropy 0.815→1.8122 |
| Q2' GT13 clean replacement | ❌ NO-SHIP: d1 KL 0.1281 vs eviction 0.0787; paired +0.0495 [0.0272,0.0715]; depth 0 |
| Q5' clean pointwise result | ✅ d1 vs eviction: lost 0.106 vs 0.683; lost\|prior 0.050 vs 0.631; both paired CIs exclude zero, but KL worsens |
| Q3' F1 under per-item kernels | ✅ branch (iii): d_min 0.5003 [0.495,0.505] flat at chance; kept sets rich (mean 2,779) yet loss-blind — internality survives strongest test |
| Q4' gate refresh | ✅ y+ 0.083; A2 weak-flat (.570/.568/.564); GT16 0.089 @ 0.000 expand; MARGINAL VALUE 0.0% — trend 72→22.5→9.0→0% |
| Q4' probes+GT22'+F5 | ✅ ladder RECOVERS: stack .857 [.847,.865], sinkheads .764, c2 L33 .856; F2 null .507; F5 .759/.727; GT22' stack routes below never-expand (.049@9.1%) |
| Q5' historical downstream analysis | ⚠ retained as mechanistic history; no clean cross-generation ranking claimed |
| Q6' fragility vs A and FR (κ, nesting) | ✅ base rates A .499/B .418/FR .321/E1F .172; κ(E1F↔A) .283, ↔B .312, ↔FR .417; nesting 91.0% ⊂ A, 78.5% ⊂ FR — mostly-nested shrinkage + 21.5% novel-vs-FR reshuffle; κ drop largely marginal-driven |
| Clean result propagation | ✅ artifact tracked; report/spec/paper/model-card updated; full verification green |

## Pre-registered anchors (from briefs; fixed before results)
- Q2' primary: KL < 0.1218 AND accΔ ≥ eviction's − 0.02 (ship/no-ship).
- Q2' secondary: accΔ ≥ eviction's AND pointwise lost ≤ eviction's.
- Extension rule: entropy slope over last 250 steps > 0.01 nats → extend to 3000.
- Q1' item-adaptive threshold: R6 < ~0.9.
- Comparators: eviction {KL 0.1218, accΔ −0.0486, lost|prior 0.583}; frozen FR
  {KL 0.2566, accΔ +0.0625, lost|prior 0.188}; gate marginal trend 72→22.5→9.0%.

## Historical campaign cost ledger
- The original E1FULL campaign recorded ≈ $435 total (incl. ≈$45 for the contaminated n=60 re-certification of all four generations): WP1+extension $200, I2 $22, certification $8, F1 $8, relabel $95, 2k relabel $4, capture $45, probes/gate $8.
- The clean retraining and recertification spend was not exported in the signed artifact and is not estimated here.
