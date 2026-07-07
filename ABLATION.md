# ABLATION.md — M3 Addendum (blocking for the paper, non-blocking for M3 closure)

Scope: re-analysis + small reruns over existing `memsub-artifacts` artifacts.
No new corpus, no new labeling passes, no architecture changes. Precedence:
this brief on scope, GATE.md/spec v0.3.6 on semantics. Everything below is
re-analysis of stored predictions or ~$20-class training reruns.

---

## A1 — Conditional (evicted-only) metrics  [BLOCKING]

The pooled AUC 0.83 mixes two tasks: separating evicted from survived rows
(near-deterministic given the `evicted` feature) and the question that
matters — among evicted spans, which lost their fact.

```text
recompute, on the test split, restricted to rows with evicted = 1:
  AUC, PR-AUC, precision/recall at τ=0.488, ECE (re-fit temperature on
  the evicted-only cal subset), per fraction and per domain
report both pooled and evicted-only in eval-grid.json; the paper's
headline discrimination number is the EVICTED-ONLY one.
```

## A2 — Signal decomposition  [BLOCKING]

Three retrains, identical config and splits, single seed each (seeds
handled in A4):

```text
(a) full model            (exists — baseline row)
(b) features-only         zero out both encoders; feature head only
                          (fraction, overlap, evicted, domain)
(c) embeddings-only       drop the feature head entirely
report evicted-only AUC/PR for each. Claims mapping:
  (c) ≈ (a)  → content-driven gate; dual-encoder story stands
  (b) ≈ (a)  → mechanics classifier; paper must retitle the mechanism
               and GT6's near-tie is explained
  both well below (a) → complementary signal; report the decomposition
Also resolves GT6's open reading either way — fold the answer into the
GT6 row of the report.
```

## A3 — Baseline reconciliation (0.520 vs 0.708/0.808)  [BLOCKING]

Never-expand appears at 0.520 in M3 and 0.708/0.808 in M1. Write the
one-paragraph reconciliation with numbers, covering at minimum:

```text
context construction   M1 packed multi-item contexts vs M3 per-item
                       4096-token randomized-placement prefills
conditioning           which item population enters each denominator
                       (per V1 appendix definitions)
fraction pooling       M3 number pooled vs M1 per-fraction
```

Then re-state ONE canonical never-expand row under the M3 protocol per
fraction, and use only that protocol's numbers in the paper. The M1
numbers remain in the certification reports with an explicit
"different protocol, see appendix" pointer.

## A4 — Uncertainty  [BLOCKING]

```text
gate training: 3 seeds for rows A2(a,b,c); report mean ± seed SD for
  every headline metric (GT9's 0.143 vs 0.15 especially)
per-cell: bootstrap over test items (1k resamples) → 95% CIs on
  lost-fact, expand-rate, AUC in eval-grid.json
GT9 verdict restated as: pass iff the upper CI bound ≤ 0.15 OR the
  frontier is reported honestly per GATE.md GT9's escape clause.
```

## A5 — Per-domain recalibration procedure  [non-blocking, small]

LODO showed discrimination transfers, calibration does not. Ship the
procedure as an artifact, not a remark:

```text
recalibrate.py: given ~200 labeled items from a new domain, fit a
domain temperature on frozen gate scores; emit (domain, T, ECE before/
after) into the checkpoint's calibration record. Unit-test on the LODO
splits: post-recalibration ECE ≤ 0.05 for every held-out domain.
```

## Deliverables

Updated `eval-grid.json` (+ evicted-only and CI fields), A2 decomposition
table, A3 reconciliation paragraph + canonical baseline row, seed-SD
table, `recalibrate.py` + test, and a one-page ADDENDUM.md summarizing
what changed relative to the 2026-07-07 report. Stop and report; do not
begin M3.5.