# FOLLOWUP2-REPORT — Pre-Submission Micro-Batch (F4/F5)

Date: 2026-07-19 · Brief: /FOLLOWUP2.md · Reference instance A =
`single-t1024-T8k`. Two analyses closing scope caveats in the v0.3 paper
before arXiv. Existing artifacts + two small captures (F4 multi-layer
context-only re-forward on the same 5,090-item F2 subsample; F5 eviction-regime
sink-head capture, 5,022 evicted rows at f=0.40). **Actual cost ≈ $14.**

**TL;DR.** (F4) The F2 null **UPGRADES**: no query-free sufficiency signal is
decodable — linear or nonlinear, at any probed layer (max AUC 0.508 vs the
question-conditioned 0.813). (F5) The middle deployment rung is
**regime-GENERAL**: the 8-scalar sink-head monitor predicts eviction loss at
**0.783** [0.760, 0.808] — above the $140 mechanics shadow gate (0.622) — and
transfers zero-shot across regimes (compactor→eviction 0.744,
eviction→compactor 0.717).

---

## F4 — Nonlinear / multi-layer context-only probe

Same 5,090-item test subsample and context-only readout as F2 (compact
context, no question, newline sentinel), re-forwarded to capture the residual
at layers {10, 15, 20, 25, 30, 36}. All probes: doc-level 5-fold OOF,
cluster-bootstrap CIs, evicted-only AUC vs y_A.

| probe | AUC | 95% CI |
|---|---:|---|
| linear, layer 10 | 0.499 | [0.484, 0.515] |
| linear, layer 15 | 0.503 | [0.487, 0.519] |
| linear, layer 20 | 0.496 | [0.481, 0.512] |
| linear, layer 25 | 0.504 | [0.489, 0.520] |
| linear, layer 30 | 0.506 | [0.490, 0.522] |
| linear, layer 36 | 0.504 | [0.488, 0.519] |
| MLP (256-h, 3 seeds), layer 30 | 0.508 | sd 0.004 |
| concat-of-layers, linear | 0.501 | [0.485, 0.517] |
| concat-of-layers, MLP | 0.502 | — |
| — question-conditioned reference | 0.813 | — |

**Decision rule (verbatim):**
> **all probes ≤ 0.55 → the null UPGRADES: "no decodable signal (linear or
> nonlinear, any probed layer)."**

Max context-only AUC 0.508; every cell's CI includes 0.5. The relational-
sufficiency claim is not a linear-probe or layer-30 artifact.

**Exact replacement sentences.**

*§6.4 scope sentence* (replaces "Scope: the null is for linear decodability at
the probed layer; nonlinear or multi-layer context-only readouts are
untested."):
> Scope: the null holds for linear *and* nonlinear (256-hidden MLP) probes at
> every layer of a {10, 15, 20, 25, 30, 36} sweep and for a concat-of-layers
> probe — max context-only AUC 0.508 vs 0.813 with the question — so there is
> no query-free sufficiency signal to read at any probed depth, not merely
> none linearly decodable at layer 30.

*Limitations line* (replaces "the F2 null is scoped to linear decodability at
layer 30."):
> the context-only null covers linear and MLP probes across a six-layer sweep
> and a concat-of-layers probe (max AUC 0.508); depths outside the sweep and
> probe families beyond MLP are untested.

## F5 — Sink-head monitor across regimes

Does the 8-scalar monitor (L25/H14, L26/H26, L28/H19, L35/H15 ×
{memory-mass, sink-mass}) predict loss under **eviction**, where the memory
region is the surviving compacted span rather than latents? Captured the four
heads' mass on {surviving-KV span, sinks} at the last prompt token over 5,022
evicted rows (f=0.40), question-conditioned; refit the same logistic on
eviction labels (doc-level bucket split).

| arm | AUC | 95% CI |
|---|---:|---|
| **F5 eviction monitor (refit)** | **0.783** | [0.760, 0.808] |
| per-domain | code 0.729 · fin 0.755 · legal 0.812 · lit 0.813 | |
| compactor monitor → eviction (zero-shot) | 0.744 | — |
| eviction monitor → compactor (zero-shot) | 0.717 | — |
| compactor monitor (in-regime refit, ref) | 0.762 | — |
| — eviction shadow gate, evicted-only (mechanics) | 0.622 | — |

**Decision rule (verbatim):**
> **≥ shadow gate → the ladder's middle rung is regime-general; add one
> sentence + one row to §6.3 and a cell to Fig. 2.**

0.783 ≥ 0.622: the head monitor beats the $140 mechanics shadow gate's
evicted-only discrimination *in the eviction regime*, and both transfer
directions clear 0.71 — the monitor reads a regime-agnostic
under-attention-to-memory signal, not a compactor artifact.

**Exact addition sentence (§6.3, after the head-monitor rung):**
> The rung is regime-general: the same eight-scalar monitor, with the memory
> region redefined as the surviving compacted span, predicts eviction-regime
> loss at 0.783 [0.760, 0.808] — above the shadow gate's own evicted-only
> discrimination (0.622) — and transfers zero-shot between regimes (0.72–0.74
> either direction), so under-attention-to-memory is a cheap, compressor-
> independent insufficiency sensor.

**Fig. 2 cell:** add a "sink-head monitor" row under the *eviction* regime
column at AUC 0.78 (vs the shadow-gate mechanics 0.62 already plotted).

## Consequences for the paper

1. **F4 hardens the abstract's relational claim.** "without the question, the
   same layer carries no linearly decodable trace (AUC 0.502)" → the null now
   covers nonlinear and multi-layer probes; the relational-sufficiency
   statement is load-bearing and now stress-tested.
2. **F5 promotes the middle rung from compactor-specific to general.** The
   two-hook monitor is the cheap tier under *both* regimes and beats the
   mechanics shadow gate even where mechanics were supposed to win — a
   stronger deployment-ladder claim than v0.3 stated.

## Artifacts

- repo `plans/260719-0105-followup2-f4f5/`: `analyze-followup2-f4-f5.py`,
  `f4-verdict.json`, `f5-verdict.json`, `followup2-all-verdicts.json`,
  per-slice captures (F5 head-feats kept in git; F4 residual shards on volume).
- Modal runners: `modal-followup2-f4-multilayer-context-only.py`,
  `modal-followup2-f5-eviction-sinkhead-capture.py`.
- `memsub-artifacts:/probe/`: `followup2-f4-slice-{00..03}.npz`,
  `followup2-f5-eviction-slice-{00..03}.npz`. Updated `arm-table.json` rows
  `f4_context_only_nonlinear`, `f5_sinkheads_eviction`, `_followup2_verdicts`.

## Deviations & assumptions

1. F4 probes use doc-level 5-fold OOF within the re-forwarded test subsample
   (mirrors F2-refit); MLP approximates c2's 256-hidden arch via
   sklearn `MLPClassifier` (ReLU, early stopping) rather than the exact torch
   probe — immaterial given every cell sits at chance.
2. F5 uses fraction f=0.40 evicted rows only (single-fraction capture); the
   shadow-gate 0.622 comparison is its pooled evicted-only mechanics AUC across
   fractions. Region split under eviction: sinks [0,4), memory =
   surviving-KV [4, ctx_len−evict_n); prompt tokens excluded (as in F3).
3. Cross-regime zero-shot normalizes with the *source* regime's feature
   mean/SD; AUC is rank-based and robust to the residual affine mismatch.

## Unresolved questions

1. F5 at f=0.25 (milder eviction) — expected similar but unmeasured.
2. Whether a probe family beyond MLP (e.g. attention over all 37 layers)
   could recover any query-free signal; the sweep + concat + MLP say no, but
   the space is not exhausted.

Stop condition met: F4 (upgrades) and F5 (regime-general) resolved, arm-table
updated, replacement sentences supplied. No further arms.
