# E1FULL Campaign — Full-Recipe Unfrozen Compactor (Third GT13 Attempt)

> **INVALIDATED CERTIFICATION (2026-07-21):** 52/60 evaluation documents
> overlapped training. The clean holdout retrain/rerun is in progress; prior
> certification and deployment conclusions are withdrawn.

Brief: /E1FULL.md. Selected config (ESCAPE P0.2): E1 fixed logit scale √d_l = 16,
otherwise canonical. Framing: every question is "does X survive kernel mobility."

## Status

| Item | Status |
|---|---|
| P0.1 ESCAPE closeout (E2, 3-seed, R3/R4, R6/R7) | ✅ committed (feat(escape)) |
| P0.2 arm selection | ✅ E1 fixed √d_l (tie with E2 → simplest lever) |
| P0.3 GT27 (init<1.5, tripwire<0.45@300, NaN watchdog) | ✅ wired (--tripwire-loss, isfinite abort) |
| WP1 train e1full-t1024-T8k (75,998 items, 1500 steps) | ✅ 00:13–02:1x; loss 0.165 (vs frozen 0.357); GT27 pass (0.217@300); entropy 0.815→1.62 still rising; kept-l0 8159/8188 |
| WP1 extension decision (slope>0.01 nats over last 250) | ✅ FIRED: +0.0696 > 0.01 → extended to 3000 (launched ~02:2x, decision logged) |
| Q1' trajectories (entropy, R6, R7, d_min) | ✅ entropy 0.815→1.78 (plateau at 3000); R6 1.000→0.550 ITEM-ADAPTIVE (<0.9 threshold); R7 →0.13 then re-organizes →0.29; d_min ~0.50 at all 12 ckpts; y+ →0.159 |
| Q2' GT13 third attempt | ❌ INVALIDATED by train/eval overlap; clean-v1 retrain and n=60 rerun pending |
| Q5' smuggling | ✅ monotone across 4 generations on one protocol (n=60): 0.617 → 0.196 → 0.171 → 0.108; no trade |
| Q3' F1 under per-item kernels | ✅ branch (iii): d_min 0.5003 [0.495,0.505] flat at chance; kept sets rich (mean 2,779) yet loss-blind — internality survives strongest test |
| Q4' gate refresh | ✅ y+ 0.083; A2 weak-flat (.570/.568/.564); GT16 0.089 @ 0.000 expand; MARGINAL VALUE 0.0% — trend 72→22.5→9.0→0% |
| Q4' probes+GT22'+F5 | ✅ ladder RECOVERS: stack .857 [.847,.865], sinkheads .764, c2 L33 .856; F2 null .507; F5 .759/.727; GT22' stack routes below never-expand (.049@9.1%) |
| Q5' smuggling | ✅ (see above — 0.083, advantage grows) |
| Q6' fragility vs A and FR (κ, nesting) | ✅ base rates A .499/B .418/FR .321/E1F .172; κ(E1F↔A) .283, ↔B .312, ↔FR .417; nesting 91.0% ⊂ A, 78.5% ⊂ FR — mostly-nested shrinkage + 21.5% novel-vs-FR reshuffle; κ drop largely marginal-driven |
| E1FULL-REPORT.md + trajectory figures + arm-table rows | ✅ complete; paper2 pendings filled + rebuilt; revise.md corrected to measured values |

## Pre-registered anchors (from briefs; fixed before results)
- Q2' primary: KL < 0.1218 AND accΔ ≥ eviction's − 0.02 (ship/no-ship).
- Q2' secondary: accΔ ≥ eviction's AND pointwise lost ≤ eviction's.
- Extension rule: entropy slope over last 250 steps > 0.01 nats → extend to 3000.
- Q1' item-adaptive threshold: R6 < ~0.9.
- Comparators: eviction {KL 0.1218, accΔ −0.0486, lost|prior 0.583}; frozen FR
  {KL 0.2566, accΔ +0.0625, lost|prior 0.188}; gate marginal trend 72→22.5→9.0%.

## Cost ledger (running)
- Actual ≈ $435 total (incl. ≈$45 n=60 re-certification of all four generations) (WP1+ext $200, I2 $22, cert $8, F1 $8, relabel $95, 2k $4, capture $45, probes/gate $8).
