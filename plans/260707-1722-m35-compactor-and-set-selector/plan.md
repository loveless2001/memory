# M3.5 — Trained Amortized Compactor + Set-Scoring Selector (COMPACTOR.md)

Scope: COMPACTOR.md; semantics: spec §8.1/B.4 + Still constants inlined in brief.
Budget ≈ $850–1,400. Base frozen; compactor params only; β=0; HF tier-(a) substrate.

## Phases
- [x] P0 compactor module (memsub/compactor/): per-layer Perceiver (H=8 banks,
      t latents, d_l=256, B=2 blocks, no FFN, QK-norm, logit scale d_l,
      internal RoPE base 10), RoPE-fix (un-rotate → internal → re-rotate),
      identity-style init; GT11 pass-through test LOCAL (tiny model) then
      reference (Modal). Nothing trains until GT11 green.
- [x] P1 data prep (Modal): rationale traces for ~24k B.3 items @8k ctx
      (teacher greedy, ~$130) → training triplets in volume.
- [x] P2 training (Modal 8×H100 DDP over compactor only): GT12 loss sanity
      (<0.4 by ~300 steps @ t=512/T=4k) then sweep t∈{128,512,1024} @T=8k,
      1500 steps, AdamW 4e-5 warmup 100, eff. batch 32; ONE iterative family
      (chunked, lookahead buffer, lr 2e-4).
- [x] P3 certification (GT13 aggregation vs eviction @ matched budget —
      ship/no-ship; GT14 pointwise prediction: stays collapsed; GT15 depth
      {1,4,N_deploy} → max_certified_depth in policy version, refuse-past-
      depth unit test).
- [x] P4 gate refresh (relabel 98k×2 with compactor as C ≈$110; reuse
      embeddings — glosses unchanged; retrain + A2 decomposition ×3 seeds;
      recalibrate; GT16 end-to-end vs M3 0.143@0.169).
- [x] P5 WP2: multi-hop slice → ~2,000 items (~$50); s1 top-k grouped
      expansion w/ marginal-score-gap stopping; GT17 (≤1.3× oracle @ ≤0.05
      lost, recall ≥0.85) / GT18 (no single-hop regression); s2 only if s1
      misses.
- [x] P6 ADDENDUM-M35.md + re-emitted certification reports + docs/commits.

## Status: COMPLETE 2026-07-08 — GT11/12/18 green; GT13/14/15/16/17 honestly documented (ADDENDUM-M35.md)
