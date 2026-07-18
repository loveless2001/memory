# FOLLOWUP2.md — Pre-Submission Micro-Batch (F4/F5)

Scope: two analyses closing scope caveats in gate_paper_draft_v0.3 before
arXiv. Existing artifacts only (`memsub-artifacts:/probe/` F2 shards, M3
eviction-regime labels + captures where present); one small capture run if
F5 requires it. ≈ $15 ceiling. Precedence: this brief on scope, spec
v0.3.6 on semantics. No new arms beyond these two; stop and report.

---

## F4 — Nonlinear / multi-layer context-only probe  [strengthens or narrows §6.4]

The F2 null ("no query-independent sufficiency signal") is currently
scoped to *linear decodability at layer 30*. The relational-sufficiency
claim is load-bearing in the abstract; test the null harder.

```text
inputs      f2-context-only-states shard (layer 30) PLUS a multi-layer
            re-extract from the same F2 forward passes if layer dumps
            beyond 30 were not retained — if a re-forward is needed,
            reuse the F2 runner in light mode over the same 5,090-item
            subsample, capturing layers {10, 15, 20, 25, 30, 36}
            (~$8; skip if shards suffice)
probes      (a) per-layer linear sweep on context-only states
            (b) MLP (c2's architecture, 3 seeds) on the best layer
            (c) concat-of-layers linear + MLP
eval        evicted-only AUC vs y_A, same doc-level test split and
            bootstrap protocol as F2; report every cell
decision    all probes ≤ 0.55 → the null UPGRADES: "no decodable
              signal (linear or nonlinear, any probed layer)" — edit
              §6.4's scope sentence and the limitations line accordingly
            any probe ≥ 0.60 → the null NARROWS: report the value,
              rewrite §6.4's scope sentence to state exactly what is
              question-free-decodable and how far below the
              question-conditioned 0.85 it sits; the relational claim
              softens from "no signal to read" to "the dominant signal
              is query-conditioned"
            0.55–0.60 → report as marginal; scope sentence keeps the
              layer-30-linear framing plus the measured band
```

## F5 — Sink-head monitor across regimes  [ladder generality]

Is the middle deployment rung compactor-specific, or general?

```text
question    does the 8-scalar monitor (L25/H14, L26/H26, L28/H19,
            L35/H15 × {latent/memory-mass, sink-mass}) predict y under
            the EVICTION regime — where "memory region" = the surviving
            compacted-summary span rather than latents?
inputs      M3 eviction labels (evicted-span rows). If no attention
            captures exist for eviction-regime contexts (likely — M3
            predates the capture infra), run a light capture on a
            5,000-item stratified subsample of eviction-protocol
            contexts, hooks on the 4 heads only (~$6)
probe       refit the same logistic (8 scalars) on eviction labels,
            doc-level splits; ALSO apply the compactor-regime monitor
            zero-shot (both directions of transfer reported)
eval        evicted-only AUC + CI; compare against the eviction shadow
            gate's evicted-only discrimination (the mechanics-driven
            0.62-class number from the M3 A2 row) — the interesting
            outcome in either direction:
              ≥ shadow gate → the ladder's middle rung is
                regime-general; add one sentence + one row to §6.3 and
                a cell to Fig. 2
              < shadow gate → footnote in §6.3: the monitor is a
                synthesis/subsampling-regime instrument; under
                eviction, mechanics features remain the cheap tier
```

## Deliverables

FOLLOWUP2-REPORT.md: F4 layer×probe table + decision-rule verdict
verbatim + the exact replacement sentence(s) for §6.4/limitations;
F5 AUC table (refit + both zero-shot directions) + the §6.3
sentence/footnote as applicable; updated arm-table.json rows
(`f4_context_only_nonlinear`, `f5_sinkheads_eviction`). Stop and
report; no further arms, no compactor work, no FULLRECIPE tasks.

## Compute

F4 ≈ $0–8 (re-forward only if multi-layer shards absent) ·
F5 ≈ $0–6 (capture only if eviction-context attentions absent) ·
probe fits ≈ $1. Ceiling $15.