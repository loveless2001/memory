# PROBE-REPORT — Content-Aware Sufficiency Probes

Date: 2026-07-18 · Brief: /PROBE.md (post-PREPROBE) · Reference instance
A = `single-t1024-T8k`, target = GT16-protocol y_A, fixed capacity
t=1024. Eval: evicted-only AUC, doc-level splits (sha256 bucket
<0.6/0.6–0.7/≥0.7), cluster-bootstrap 95% CIs, n=30,847 captured items
(E2 ∪ E1), test n=8,996-class.

**TL;DR — The mission is met. A linear probe on the residual stream
already reads sufficiency at 0.819; the best stack reaches 0.854
[0.846, 0.862] vs the c0 floor 0.564 and the p2 self-check floor 0.638.
End-to-end (GT22) the stack-gated system sits STRICTLY INSIDE the
refreshed gate's cost/correctness curve: lost-fact 0.146 at ~1/3 of the
gate's expansion budget (0.050 vs 0.147). Two arms died for a newly
mechanistic reason: the trained compactor's cross-attention is a delta
position kernel — routing is content-blind, so write-time signals (c3a)
and corpus-side interference geometry (c0.5) carry ~nothing. Sufficiency
under synthesis IS predictable — but only by reading the computation.**

## P0 pilots (1,000 items, stratified y × domain) — GT19

- **p1 (attention-signal existence): FAILED the bar.** Best single
  aggregated statistic 0.536 (recent-window mass at last prompt token);
  all < 0.55 → c1 demoted to per-head analysis per the decision rule.
  Post-hoc nuance: aggregation was the killer, not absence of signal —
  individual heads reach 0.72 (see head inventory), and the learned
  per-head probe (c1d) reaches 0.767.
- **p2 (prompted self-check): 0.659 on the pilot, 0.638 [0.628, 0.649]
  on the full test split.** Above the 0.62 bar → the near-zero-cost
  option alone already beats every corpus-side feature approach and
  must be the deployment baseline any trained probe justifies against.
- **p3 harness** built on the E1 A/B relabels: fragility classes
  survived (955) / A-only-lost (209) / both-lost (790), 46 non-nested
  rows excluded.

## The mechanistic finding: content-blind routing

Captured block-1 cross-attention of the compactor on all pilot items:
**attention rows are delta functions on single source positions —
lstar purity exactly 1.0, row entropy exactly 0.0, zero variance across
1,000 items × 36 layers × 8 KV-heads.** The Perceiver never left its
position-dominated init: compaction ≈ strided position subsampling of
[K;V] pairs plus leakage smearing. Consequences:

1. **c3a is infeasible as designed** — the routing carries zero content
   information, so collision features computed from it cannot predict
   loss. c3b's gate (c3a ≥ 0.60) fails ⇒ c3b not run ($70 saved).
2. **Explains E2's confusable-sibling signature** — whether a fact
   survives depends on which positions the fixed kernel samples and how
   neighbors smear, hence "answered the adjacent table row."
3. **Explains PREPROBE's B ⊂ A nesting** — reseeds share the position
   kernel and differ in leakage, so one instance's failure set nests.
4. Bounds interpretation of GT13/GT14: the 1/40-scale compactor is a
   subsampler, not a synthesizer; full-recipe training may change this
   regime entirely.

## Arm comparison table (test split; floors as rows)

| arm | AUC | 95% CI | p3 τ (CI) | code | fin | legal | lit |
|---|---:|---|---|---:|---:|---:|---:|
| c0 surface floor | 0.564 | [0.553, 0.575] | — | 0.56 | 0.57 | 0.54 | 0.58 |
| c0.5 +interference | 0.568 | [0.557, 0.579] | — | — | — | — | — |
| p2 self-check floor | 0.638 | [0.628, 0.649] | 0.20 [0.16, 0.23] | 0.604 | 0.662 | 0.651 | 0.668 |
| c1-demoted per-head | 0.767 | [0.758, 0.777] | 0.46 [0.44, 0.49] | 0.727 | 0.793 | 0.788 | 0.781 |
| c2 linear (layer 30) | 0.819 | [0.811, 0.827] | 0.45 [0.43, 0.48] | 0.785 | 0.849 | 0.848 | 0.823 |
| c2 MLP (3 seeds, sd 0.002) | 0.852 | [0.844, 0.859] | 0.47 [0.45, 0.50] | 0.817 | 0.875 | 0.874 | 0.851 |
| **stack (c2+p2+c1d+c0/c0.5)** | **0.854** | [0.846, 0.862] | **0.57** [0.56, 0.60] | 0.817 | 0.879 | 0.875 | 0.855 |

c0.5 detail: interference-geometry features alone 0.535; stacked on c0
0.568 [0.557, 0.579] — fails its 0.575 bar. The anticipated null: with a
position-kernel compactor, collision is decided inside the computation,
not in corpus-visible sibling geometry.

**Layer curve (c2 linear, test AUC):** 0.50 (embed) → 0.53 (L15) → 0.65
(L20) → 0.81 (L25) → **0.819 (L30 peak)** → 0.81 (L36). Sufficiency
estimation crystallizes in the last third of the stack; full curve in
`readside-metrics.json`.

**Retrieval-head inventory (demoted-c1 deliverable):** top pilot heads —
L25/H14 latent-mass 0.72; a late-layer sink-mass cluster (L26/H26 0.72,
L28/H19 0.71, L35/H15 0.70): under-attention to memory shows up as
anomalous sink mass. `retrieval-head-inventory.json`.

## Golden-test verdicts

- **GT19 ✓** P0 ran first; c1 demoted, c3a declared infeasible (with
  mechanism), c3b gated off, p2 elevated — all before scaling capture.
- **GT20 ✓** Every arm's lower CI clears 0.575 (even p2: 0.628).
- **GT21 ✓** Best arm 0.854 ≥ 0.65 target. Deltas: +0.290 over c0,
  +0.216 over p2.
- **GT22 ✓ (win condition met)** Stack as gate, τ chosen on val
  (weighted): test lost-fact|prior-correct **0.146 at expand_all ≈
  0.050** vs refreshed gate 0.146 @ 0.147, oracle 0 @ 0.170,
  never-expand 0.184 @ 0. Strictly inside the gate's curve — same
  correctness at ~1/3 the expansion budget. (Weighted estimate on the
  captured sample at natural prevalence; assumes non-evicted rows are
  never expanded — stated in gt22-gt24.json.)
- **GT23 ✗ → frontier documented.** Entry-gated retry on the 2k
  multi-hop slice: recall 0.831, **1.98× oracle** at lost 0.169
  (targets: ≥0.85 / ≤1.5× / ≤0.08). Better than the M3 gate (2.33×) and
  s2 (2.15×), and achieved WITHOUT per-block content scores (per-query
  arm score gates entry; evicted block expanded on entry). The residual
  gap is regime shift: the probe was trained on GT16 synthesis rows,
  the slice's needed-flags come from the eviction counterfactual.
- **GT24 (labeled capacity transfer)** Held-out E1 rows: 0.949 vs y_A
  → **0.735 vs y_C (t=512), drop 0.214.** Consistent with PREPROBE's
  κ(A↔C)=0.455: per-capacity retraining of the probe is required;
  budget one capture+train per capacity point (~$85 + $3).
- **GT25 ✓** Stack τ = 0.575 [0.559, 0.590] on the A/B fragility
  ordering — CI excludes 0 decisively; the arm reads the underlying
  fragility scalar, not one checkpoint's noise.

## End-to-end cost/correctness plane

At natural prevalence (weighted): never-expand 0.184 @ 0 · stack-gate
0.146 @ 0.050 · refreshed gate 0.146 @ 0.147 · oracle 0 @ 0.170. The
stack dominates the refreshed gate; remaining distance to oracle is the
0.146 silent-loss floor at this budget — full frontier in
`gt22-gt24.json: test_frontier`.

## Consequences for the paper (§8 material)

1. The routability asymmetry resolves: synthesized loss IS routable —
   at 0.85 AUC — but only from READ-SIDE signals (residual stream at
   the decision point). The two-regime story gains its third clause:
   eviction loss routes via mechanics (0.72 reduction), synthesis loss
   does not route via mechanics or content-surface (0.56) but routes
   via computation-reading (0.85 → 2/3 budget cut at equal loss).
2. The trained compactor is mechanistically a position subsampler
   (delta cross-attention kernels). This reframes GT13's NO-SHIP and
   the 1/40-scale caveat: the certified artifact never entered the
   content-synthesis regime.
3. The cheap tier matters: a single prompted self-check (one forward,
   no training) reaches 0.638 — already above every corpus-side
   approach. Deployment story: p2 for free, +capture-trained stack
   where the 0.85 tier pays for itself.
4. Multi-hop: entry gating with a per-query sufficiency score beats all
   prior per-block selectors (1.98× vs 2.15–2.33×) — content-aware
   ENTRY, not content-aware block ranking, was the binding constraint.

## Deviations & assumptions

1. Capture cost ran ≈ $78 vs the $60–80 estimate (3.5 s/item pilot led
   to a light-mode trim: decode-step attentions and c3a hooks dropped
   post-GT19 for the scaled run).
2. GT22 is a natural-prevalence weighted estimate on the captured
   sample (capturing all 82k evicted rows would have tripled cost);
   non-evicted rows assumed never-expanded.
3. GT23 uses entry-gating (per-query score + expand-evicted-on-entry)
   rather than per-block scoring; evicted-vs-survived is system
   metadata, so this is deployment-legal. Documented in gt23.json.
4. p1/p2 pilot ran on 1k items inside the same capture protocol used
   for scaling (GT19 sequencing respected; no capture was scaled before
   the bars were read).
5. mh (multi-hop) capture rows are score-only (split=3), never trained
   on — their y is the eviction-counterfactual regime.

## Compute actuals

Pilot ≈ $3 · scaled capture (8×H100 ≈ 18 H100-h, incl. one preemption
redo) ≈ $73 · multihop capture ≈ $5 · c0.5 (4×L4) ≈ $5 · probe training
(3 L4 runs, one killed for an npz-quadratic-load bug) ≈ $3.
**Total ≈ $89** (brief envelope $150–250 with c3b excluded; c3b not
triggered).

## Artifacts

- `memsub-artifacts:/probe/` — capture-manifest.json, capture shards
  (attn stats + hidden states + c3a, ~5.9 GB), multihop capture,
  c05 feature slices, readside-scores.npz, readside-metrics.json
- repo `plans/260717-2319-probe-sufficiency-arms/` — all runners'
  analysis scripts, p0-analysis.json, c05-analysis.json,
  arm-table.json, arm-scores-all.npz, gt22-gt24.json, gt23.json,
  retrieval-head-inventory.json, plan.md
- Modal runners: `modal-probe-unified-capture-attention-hidden-crossattn.py`,
  `modal-probe-c05-interference-geometry-features.py`,
  `modal-probe-train-readside-probes-and-scores.py`

## Unresolved questions

1. The c2 probe reads "the model won't answer as it would have with
   full context" — how much of the 0.85 is answer-confidence proxy vs
   genuine memory-content readout? A probe on a no-question forward
   (context-only) would separate these; not run (out of brief scope).
2. GT23's residual gap: would fine-tuning the probe on multi-hop-shaped
   supervision close 1.98× → 1.5×, or is per-block content scoring
   still required for many-candidate settings (this slice has one
   evicted candidate per query)?
3. Whether a full-recipe compactor (past the position-kernel regime)
   keeps sufficiency readable at 0.85 — the read-side probe should be
   re-run as a certification step on any retrained compactor
   (per-capacity AND per-instance, per GT24 + PREPROBE #1).
4. The late-layer sink-mass anomaly heads (L26–L35) as a cheap online
   monitor: single-head statistics at 0.70–0.72 could gate WITHOUT any
   capture infra — untested as a standalone deployment arm.

Stop condition met: GT19–GT25 resolved (green or frontier-documented).
No absorption work, no Phase 4, no serving.
