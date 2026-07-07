# M3 Expansion Gate — Final Report (GATE.md fulfilled)

> **2026-07-07 late addendum (ABLATION.md)**: headline discrimination is the
> EVICTED-ONLY AUC 0.622 (pooled 0.83 conflated tasks); the mechanism is a
> calibrated eviction-mechanics classifier (features-only ≈ full model);
> GT9 restated as frontier (bootstrap upper CI 0.156 > 0.15); canonical
> never-expand baselines 0.453/0.551 per fraction. See `ADDENDUM.md`.

Date: 2026-07-07 · Artifacts: Modal volume `memsub-artifacts` under
`corpus-gate-labels/` and `gate-eval/` · Figures: `plans/reports/gate-figures/`

## P0 verification gate
- V1 protocol appendix, V2 control rows, V3 audit: done 2026-07-07 morning
  (`certification-260707-0907-eval-protocol-appendix.md`). Format noise = 0%
  (< 15% bar) → labels trainable as-is.
- V4 = no (per-item records covered only certification needles) → labeling
  passes run per §3.

## Labels (spec §17.5 counterfactual)
- 98,355 items × 2 fractions = **196,710 rows**; per item: one 4096-token
  context prefill (placement randomized by item hash → natural eviction
  exposure under evict-oldest-nonsink), clone+evict per fraction; y = compact
  answer ≢ raw-span answer (eq_policy_v1). Survived-span rows kept as natural
  y=0 (GATE.md §3). 12 H100 workers, ~3.5h, ~$110.
- raw_correct ≈ 1 by construction (filter (a) at corpus build + greedy
  determinism) → raw and prior-correct-conditioned rates coincide here.

## Gate
- Dual encoder over frozen Qwen3-Embedding-0.6B (shadow-v1, same model as
  block shadows): normalized projection interaction (256d) + feature head
  (fraction, overlap, evicted, domain) + aux workload head. Linear-probe
  tier sufficed (GT8 green → no unfreezing). Config hash + temperatures in
  `gate-eval/gate-checkpoint.pt`.
- Calibration: per-fraction temperature search returned T=1.0 for both —
  the probe is natively calibrated; ECE (GT7) 0.023 / 0.017.

## Golden tests

| GT | Status | Evidence |
|---|---|---|
| GT6 no leakage | **resolved by A2 ablation** | doc-split AUC 0.8283 vs item-split 0.8259 near-tie. ABLATION.md A2 settled the open reading: features-only retrains match the full model on evicted-only AUC (0.621 vs 0.624), embeddings-only collapses to 0.536 — the signal is eviction MECHANICS, not document content, so item-level leakage had nothing to exploit. See ADDENDUM.md; the mechanism claim in this report is superseded accordingly. |
| GT7 ECE ≤ 0.05 | **green** | 0.0229 (evict 0.25), 0.0168 (evict 0.40) on test |
| GT8 dominates classify-and-expand | **green** | at every matched expand-rate 0.1–0.5: gate lost 0.277/0.092/0.0/0.0/0.0 vs classify 0.470/0.416/0.368/0.308/0.248 |
| GT9 end-to-end | **green (feasible)** | τ=0.488 chosen on cal: test lost-fact 0.143 ≤ 0.15 (V2 floor = 0.000) at expand-rate 0.169 ≤ 0.5×always. vs baselines: never 0.520, oracle 0.000 @ 0.194 expand |
| GT10 budget trace | **green** | BudgetedExpansionHarness: grants by score until budget; remainder traced `budget_exhausted`, never dropped (unit-tested) |

## Evaluation grid highlights (test split, τ=0.488)

- **Cost/correctness plane** (`gate-figures/cost-correctness-plane.png`):
  gate curve strictly inside classify-and-expand everywhere; reaches
  lost≈0 at ~0.3 expand-rate vs oracle's 0.194.
- Per domain (lost|prior @ expand): financial 0.069@0.12 / 0.047@0.30,
  code 0.129@0.12 / 0.105@0.28, literature 0.186@0.08 / 0.162@0.21,
  legal 0.219@0.07 / 0.233@0.18 — legal weakest (recall 0.28–0.43),
  consistent with its OCR-corrupted source text (known corpus issue).
- **LODO generalization row**: held-out-domain AUC 0.781–0.865 with
  near-zero lost-fact at ~0.26 expand — but ECE degrades to 0.05–0.11
  (calibration does not transfer across domains; per-domain recalibration
  required before deploying to a new domain).
- **Multi-hop slice** (500 teacher-filtered k=2 questions, evicted+survived
  block rows): AUC 0.832; at the single-hop τ the gate holds correctness
  (lost 0.036 vs never-expand 0.376) by over-expanding — recall 0.904,
  precision 0.388, expand 0.438 = 2.3× oracle (0.188). The spec §4.7
  middle-of-spectrum weakness appears on the COST axis, not correctness.

## Deliverables checklist (GATE.md §7)
- gate checkpoint + calibration + config hash: `gate-eval/gate-checkpoint.pt` ✓
- re-emitted M1 reports with V1 appendix + V2 controls: done (07-07 am) ✓
- eval grid JSON: `gate-eval/eval-grid.json`, `gate-eval/multihop-eval.json` ✓
- figures: plane + reliability curves (volume + `plans/reports/gate-figures/`) ✓

## Compute actuals
labels ~$110 (12×H100, 3.5h) · embeddings ~$8 · multi-hop ~$15 ·
training+eval ~$5 (CPU/L4). Total ≈ $140 — under the §8 estimate.

## Unresolved questions
- GT6's near-tie invites a follow-up ablation: train WITHOUT the eviction
  features (embeddings only) to separate mechanics-driven from
  content-driven signal. Non-blocking for M3.
- LODO calibration drift → per-domain temperature as deployment procedure.
- Multi-hop cost overhang is the natural M3.5/selector-scoring target.
