# ADDENDUM-M35 — Trained Compactor + Set-Scoring Selector (COMPACTOR.md)

Date: 2026-07-08 · Artifacts: `memsub-artifacts:/compactor-checkpoints/*`,
`/compactor-certification/summary.json`, `/gate-eval/wp2-set-selector-eval.json`,
`/gate-eval/gate-refresh-still.json` · Code: `memsub/compactor/`,
`memsub/gate/set_scoring_selector.py`.

## Ship/no-ship verdict (GT13): **NO-SHIP**

At matched retained budget (sinks + t latents + 1,024 recent raw slots of a
4,096-token context), the trained compactor's AGGREGATION axis is worse than
untrained evict-oldest-nonsink, at every sweep point (t=1024 shown; 12
contexts, 4 domains):

| arm | mean KL | acc delta | lost-fact \| prior-correct |
|---|---:|---:|---:|
| control (no compression) | 0.000 | 0.000 | 0.000 |
| eviction @ matched budget | 0.122 | −0.049 | **0.583** |
| compactor depth-1 | 0.263 | −0.090 | **0.271** |
| compactor depth-4 (recurrence) | 2.292 | −0.056 | 0.750 |

evict-oldest-nonsink remains the default L3 path. Honest scale caveat: this
checkpoint trained on ~25k rationale triplets / 1,500 steps (≈1/40 the Still
recipe's data volume, single 8×H100 run per point); the verdict certifies
OUR checkpoint, not the method's ceiling.

## The pointwise number (GT14) — and a surprise

Prediction confirmed directionally: pointwise stays far above the 0.000
floor under synthesis (0.271), so the §13.4 rule re-attaches — **the gate is
mandatory under every compaction regime**. The surprise: synthesis HALVES
silent needle loss vs matched-budget eviction (0.271 vs 0.583) — compact
latents smuggle needle content forward that eviction deletes outright. A
compactor that loses the aggregation contest still carries pointwise value;
worth revisiting if a full-recipe training run is ever funded.

## Certified depth (GT15)

Recurrence collapses on our workload exactly as the Still paper warns
(§3.4 "Iterative compaction": beyond the training horizon, repeated
compression collapses — verified against arXiv:2606.07878, 2026-07-09;
the working notes' "§M.2" pointer was wrong): depth-4 KL 2.29 (9× worse
than depth-1), lost-fact 0.75.
**max_certified_depth = 0** (no depth clears GT13's certification bar);
emitted into `compaction_policy_version`
(`still-compact-v1:t1024:depth…:sha256:b04b5bfd…`), and resume paths refuse
to stack beyond it (unit-tested, GT3-style).

## GT11/GT12 (sanity gates)

GT11 identity pass-through: green on tiny-config AND reference model before
any training (the §12 position-bug detector). GT12: loss 0.42 → 0.058 by
step 300 at t=512/T=4k (bar < 0.4).

## Gate refresh under the new policy (GT16): frontier — with its own baselines

Relabeled all 98,355 items under the compactor policy (deployment-shaped:
old prefix → t=1024 latents, recent 25% raw; y+ rate drops to 0.167 from
eviction's ~0.25 — consistent with GT14). All rows on the GT16 test
protocol, per-policy baselines included:

| decision rule (compactor policy) | lost-fact \| prior-correct | expand-rate |
|---|---:|---:|
| never-expand | 0.189 | 0.000 |
| refreshed gate @ τ | 0.146 | 0.147 |
| oracle | 0.000 | 0.170 |
| always-expand | 0.000 | 1.000 |

The system point (0.146 @ 0.147) numerically matches the M3
eviction-regime operating point (0.146 @ 0.168) — but the credit
assignment flips. Under eviction the gate cut silent loss 72%
(0.520 → 0.146); under synthesis the COMPRESSOR does most of the work
(never-expand is already 0.189 on this protocol) and the gate adds only a
**22.5% marginal reduction** while spending 86% of the oracle budget.
With evicted-only AUC 0.55, that residual is mostly calibration riding a
lower base rate, not discrimination. Formal GT16: 0.0001 miss on the
lost-fact target (frontier per escape clause); ECE 0.0074.

**The A2 decomposition FLIPS under synthesis** (the brief's anticipated
paper-relevant result): embeddings-only 0.567 ± 0.005 now beats
features-only 0.537 ± 0.002 (full 0.554 ± 0.003). Under a compactor,
eviction-mechanics features lose their signal and content becomes the
better predictor — but all evicted-only AUCs drop (~0.55 vs eviction's
0.62): synthesized loss is intrinsically harder to predict than deletion.

## WP2 — set-scoring selector (GT17/GT18): frontier documented

| selector | recall | expand/oracle | lost-fact |
|---|---:|---:|---:|
| M3 per-block gate (reference) | 0.904 | 2.33× | 0.036 |
| s1 top-k grouped (gap rule) | 0.882 | 2.24× | 0.118 |
| s2 joint head (margin features) | 0.835 | 2.15× | 0.165 |

**GT17 unreachable with the current gate** (target ≤1.3× oracle @ ≤0.05
lost, ≥0.85 recall). The cause is now diagnosed, not mysterious: the
overhang is bounded by the underlying gate's evicted-only discrimination
(AUC 0.62, mechanics-driven per the M3 A2 ablation) — set-level grouping
cannot separate needed from unneeded evicted blocks when the per-block
scores carry no content signal. The multi-hop cost overhang is therefore
downstream of the SAME open problem as A2: content-aware sufficiency.
GT18 (no single-hop regression): holds by construction — s1 degenerates to
the per-block threshold for single candidates (unit-tested), and the fitted
τ_entry (0.500) sits within 0.012 of the M3 operating threshold.

## Compute actuals
data prep ≈ $120 · GT12 + sweep + iterative ≈ $420 (incl. one NCCL-teardown
zombie, ~$60, root-caused and mitigated) · certification ≈ $35 · relabel +
refresh ≈ $115 · WP2 ≈ $25. **Total ≈ $715** (budget $850–1,400).

## Post-hoc code-review corrections (2026-07-08, external review 4d67a13..HEAD)

1. **Training objective multiset bug (fixed forward).** `forward_kl_on_answer`
   concatenated gold into the top-200 support unconditionally, duplicating the
   vocab id whenever gold was already top-k → KL over a multiset that
   overweights gold. The SHIPPED checkpoints (GT12 curve, all certified
   numbers above) were trained under this variant; the numbers certify those
   checkpoints as-is and remain valid, but any future training run uses the
   corrected set-support objective (`support[missing, -1] = gold`; unit
   tests: `tests/test_compactor_kl_gold_support_dedup.py`). One more reason
   the 1/40-scale caveat, not this checkpoint, bounds the method.
2. **GT15 depth predicate tightened.** Depth-4 was certified on mean-KL only
   while depth-1 used KL + acc-delta. Both depths now share the full GT13
   predicate (contiguous-prefix rule: depth 4 cannot certify past a failing
   depth 1). No verdict changes: depth-1 and depth-4 both fail the stricter
   bar too; max_certified_depth stays 0.
3. **Protocol label on compactor certification artifacts.** The harness
   stamped `pointwise_denominator: "source chunk in evicted window"` even on
   compaction_fn arms, where no eviction occurs. Numbers unaffected
   (label-only); harness now emits "compacted-away region (compaction_fn
   arm)" for those arms. Existing JSONs in
   `memsub-artifacts:/compactor-certification/` carry the old label — read
   `eval_protocol.eviction_mode = "trained_compactor"` as the authoritative
   arm marker there.

## Unresolved questions
- The compactor's aggregation gap vs eviction may be a data-scale artifact
  (1/40 recipe); a full-scale run is a funding decision, not an engineering
  one — the pipeline is ready.
- Content-aware gate signal is now the single blocker for BOTH the gate's
  discrimination headroom (A2) and the multi-hop overhang (GT17).
- NCCL teardown hang after final save (destroy_process_group) — mitigate
  with a save-then-exit watchdog if more training runs are funded.
