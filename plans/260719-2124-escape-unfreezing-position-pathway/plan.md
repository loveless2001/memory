# ESCAPE Campaign — Unfreezing the Position Pathway

Brief: /ESCAPE.md. Hypothesis (pre-registered): frozen kernel = logit-scale-induced
gradient saturation (d_l=256 on cosine logits → one-hot softmax → zero routing grads
from step 0; value path downstream trains normally).

## Status

| Item | Status |
|---|---|
| P0 G1 grad forensics @ init (canonical d_l=256) | ✅ W_Q 1.1e-11 / W_K 1.6e-10 DEAD; W_V/W_O/heads 21.6 healthy; latents 0.061 (residual value-path role) |
| P0 G2 same @ scale √d_l=16 | ✅ W_Q ×5.0e9 → 5.5e-2, W_K ×3.4e9 → 5.4e-1; value path only ×3.5. **D1 CONFIRMED.** init loss 0.705→0.862 (passthrough cost) |
| E0 baseline | ✅ exists (FULLRECIPE mid run — reuse, $0) |
| E1 logit scale √d_l | ✅ ESCAPED: entropy 0.82→1.11, J→0.18, loss 0.219, y+ 0.239; 3-seed stable |
| E2 learned temperature (init √d_l, clamp [1,256], per layer) | ✅ ESCAPED (0.2104, J 0.172) after OOM + shared-tensor fixes |
| E3 anchor noise σ=0.02 at init (scale d_l) | ✅ frozen (floor, J 1.000) — rules out tie-breaking |
| E4 content-seeded init (centroid latents + unzeroed content proj) | ✅ off-floor flat, mean J 0.99, quality-catastrophic (y+ 0.614) |
| I2 relabels {47,94,141,188} × arms | ✅ R3 d_min ~0.50 all arms; R4 table in report |
| R1–R5 readouts + D verdicts | ✅ D1 confirmed, D2 (E1+E2), D3 moot, D4 not triggered; +R6 0.821/R7 0.199 |
| 3-seed replication (iff D2) | ✅ E1 seeds 1234/51234/91234 all escape |
| ESCAPE-REPORT.md + entropy overlay figure | ✅ complete; arm selection: E1 fixed √d_l |

## Implementation decisions (logged)
- Lever plumbing: `--lever` arg in the fullrecipe inner trainer (fixed harness reused;
  telemetry unchanged; telemetry_every=25 per brief).
- E1/G2 scale swap: set `d_l` attr on every _QKNormCrossAttention (scale-only use) — no
  architecture change.
- E2: one trainable scalar per compactor layer, init 16, clamped [1, 256], applied in all
  4 attention modules of that layer; joins the no-decay param group.
- E3: N(0, 0.02) added to q_anchor/k_anchor of every attention module at init.
- E4: per (layer, head) torch k-means (k=1024, 10 iters, 8k sampled [K_unrot;V] vectors
  from 16 probe items) → latent bank; content projections q_proj/k_proj unzeroed with
  N(0, 0.02) (else zeroed q_proj makes centroid latents routing-inert — "instead of
  zeroed content pathway" per brief); anchors kept; rank0 computes, broadcasts.
- E0 baseline: FULLRECIPE mid run reused (its telemetry is every 50 + step 188; arms use
  every 25 — E0 curve compared at shared steps).

## Cost ledger (running)
- Total ≈ $95 (G1G2 $3, arms ~$54, I2 $20, seeds $20; budget $130–185)
