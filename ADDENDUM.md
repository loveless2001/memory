# ADDENDUM — M3 Ablation Results (changes vs the 2026-07-07 gate report)

Artifacts: `memsub-artifacts:/gate-eval/{ablation-results.json, eval-grid.json}`
(eval-grid now carries `evicted_only`, `bootstrap_ci`, `canonical_never_expand`).
Full context: `plans/reports/gate-260707-1319-m3-expansion-gate-final-report.md`.

## A2 — The mechanism is not what the 07-07 report implied  [headline change]

| Variant (3 seeds) | evicted-only AUC | pooled AUC |
|---|---:|---:|
| full model | 0.624 ± 0.004 | 0.831 |
| features-only (no encoders) | **0.621 ± 0.006** | 0.837 |
| embeddings-only (no features) | 0.536 ± 0.004 | 0.557 |

Features-only matches the full model within seed noise: **the gate is a
calibrated eviction-mechanics classifier** (overlap × fraction), not a
content-driven dual encoder. shadow-v1 embeddings add ~nothing to
evicted-only discrimination. The paper must present the mechanism as
mechanics-based; the dual-encoder architecture remains as scaffolding whose
content pathway is a negative result. This also fully explains GT6's
near-tie (no content signal → nothing for item-level leakage to exploit).

## A1 — Headline discrimination number  [changed]

Pooled AUC 0.83 conflated evicted/survived separation with the real task.
**Evicted-only test AUC = 0.622 [bootstrap 95% CI 0.608–0.636]**, PR-AUC
0.621; per domain 0.585 (legal) – 0.640 (financial); ECE evicted-only 0.017
after refitting temperature on the evicted-only cal subset. 0.62 is the
paper's discrimination number.

## A4 — GT9 restated with uncertainty  [verdict changed to frontier]

Seed variance (3 seeds): lost-fact 0.126 ± 0.014, expand-rate 0.177 ± 0.007.
Bootstrap over test items: lost-fact 0.146 [0.136, **0.156**] at expand-rate
0.168 [0.163, 0.173]. The upper CI bound exceeds 0.15 → GT9 is **not a clean
CI-pass**; per GATE.md's escape clause the frontier is reported as-is: the
gate sits at ≈0.13–0.15 silent loss at ≈0.17 expand-rate, vs never-expand
0.45–0.55 and oracle 0 at 0.19. Operationally unchanged; the claim wording
changes from "meets ≤0.15" to "statistically indistinguishable from 0.15".

## A3 — Baseline reconciliation (0.520 vs 0.708/0.808)  [one paragraph]

The M1 numbers (0.708/0.808 raw; 0.550/0.650 conditioned) and the M3
never-expand 0.520 measure different protocols. (1) Context construction:
M1 certified 20 packed contexts whose eviction window was ANCHORED ON the
needle chunk (adversarial placement, whole chunk always evicted); M3 labels
use per-item 4096-token contexts with hash-randomized placement, so
"evicted" rows include boundary items with partial (>0.5) overlap. (2)
Denominators: M1 raw rates include never-knew items (V2 floor 0.167); M3
rows have raw_correct ≈ 1 by construction (filter (a) + greedy determinism),
so no never-knew inflation. (3) Pooling: 0.520 pooled both fractions.
**Canonical never-expand rows under the M3 protocol: 0.453 (evict 0.25,
n=1,606) and 0.551 (evict 0.40, n=3,493)** — the paper uses only these; the
M1 certification numbers remain in the certification reports flagged
"different protocol, see eval-protocol appendix".

## A5 — Recalibration procedure shipped  [artifact]

`memsub/gate/domain_recalibration.py` (+ unit tests): fit on ~200 labeled
items from a new domain, frozen scores; escalates from temperature to Platt
(T + bias) when the fit-sample ECE misses 0.05 — cross-domain miscalibration
proved to have a location component T alone cannot repair (temperature-only
left 3/4 domains at 0.071–0.073). Verified on real LODO splits:

| held-out | method | ECE before → after |
|---|---|---|
| financial | platt | 0.130 → 0.014 |
| legal | platt | 0.106 → 0.029 |
| code | temperature | 0.064 → 0.035 |
| literature | platt | 0.116 → 0.023 |

All ≤ 0.05. Records are emitted into the checkpoint's `domain_calibration`
block.

## Unresolved questions

- The content pathway being dead may be a gloss problem (extractive chunk
  prefix + question-only queries) rather than a fundamental one; a
  summary-based gloss or answer-aware query encoding is the natural probe —
  out of ABLATION.md scope, do not start without a new brief.
- Per GATE.md/ABLATION.md: M3.5 is not begun.
