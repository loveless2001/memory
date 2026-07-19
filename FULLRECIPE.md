# FULLRECIPE.md — Full-Recipe Compactor: Does Scale Escape Position-Kernel Collapse?

Campaign brief for the full-scale Still-recipe compactor run and the
re-interrogation of every Regime-II finding under it. Authoritative
documents: spec v0.3.6 (semantics), COMPACTOR.md (architecture/training
constants — unchanged unless stated), paper v0.4 (the claims under test).
Precedence: this brief on scope, the spec on semantics. All prior
harnesses (certification, GT16 labeling, gate refresh, probe capture,
F1/F2) are reused unchanged; this brief adds instrumentation and re-runs,
not new machinery.

**Framing (write it into the report header):** this run does not exist to
produce a better compactor. It exists to answer five pre-registered
questions about whether the v0.4 paper's Regime-II findings — certified
against a subsampler — survive a real synthesizer. Each question has its
outcomes enumerated below; every outcome is reportable.

### Do-not-build list
- No backbone/LoRA training; compactor only, corrected KL objective
  (post-f214c0f), β = 0.
- No architecture changes vs COMPACTOR.md §2.1 (canonical Still config);
  scale changes ONLY data volume and steps.
- No serving work, no absorption-tier work, no new probe arms beyond
  re-running existing ones.

---

## P0 — Corpus completion + instrumentation (blocks training)

```text
C1  rationale audit: does the full 98,355-item corpus carry rationale-
    augmented answer traces (Still recipe: rationale + letter), or only
    the 25k M3.5 slice? If partial → teacher rationale-generation pass
    over the remainder (batched, greedy; est. $150–250). Verify a 200-
    item sample manually for trace quality before scaling.
C2  training mixture: match the Still recipe — domain-downsampled to the
    smallest (per B.3 counts → cap ≈ 23.5k/domain, ≈ 94k items,
    ~0.9B context tokens at 8k). Emit the mixture manifest + hash into
    compaction_policy_version material.
I1  entropy telemetry (the novel artifact): every 50 steps, on a fixed
    128-item probe batch, log per-layer block-1 cross-attention row
    entropy (mean + p10/p90) and argmax-kernel snapshot (kept-position
    sets). Cost ≈ one extra forward per 50 steps — negligible.
I2  online kernel-geometry probe: every 250 steps, compute F1's d_min
    univariate AUC on a fixed 1k labeled subsample against the CURRENT
    checkpoint's kept kernel (requires a cheap per-checkpoint relabel of
    the 1k subsample — ~$1.5/point; cap at ~20 points, ~$30).
GT26 (sanity, before scaling): GT11 identity pass-through green on the
    full-recipe config; GT12-class loss tripwire at 300 steps.
```

## WP1 — Training

```text
points     full recipe: T=8k, t=1024, effective batch 32, lr 4e-5,
           step budget 1500 (Still headline) with telemetry-based
           extension: if entropy is still rising at 1500, continue to
           3000 (decision logged, not improvised)
           mid-scale: 1/8 recipe (≈ 12k items) — same config, same
           telemetry; the third point on the collapse curve
           (existing 1/40 checkpoint A = the first point, $0)
hardware   8×H100/H200; save-then-exit watchdog (NCCL mitigation from
           M3.5); resume-safe every 250 steps
est. cost  full ≈ $400–550 · mid ≈ $60–90 · rationale pass per C1
```

## WP2 — The five questions (pre-registered outcomes)

```text
Q1  ESCAPE: does cross-attention entropy leave zero?
    report the entropy-vs-step curve for all three scale points +
    the step/data threshold if a transition exists.
    outcomes: (a) transition observed → paper #2's signature figure;
    (b) drift, no clean transition → report the curve as-is;
    (c) never leaves zero even at full recipe → position-kernel
    collapse is NOT a scale artifact on this corpus/config — a
    finding that directly qualifies the Still recipe's transfer.

Q2  GT13 RETRY: full certification (M1 harness, matched retained
    budget, per-axis, noise-floor row, depth {1, 4} + deployment
    depth): does full-recipe aggregation beat eviction?
    outcomes: ship / no-ship / axis-crossing-again — each with the
    same per-axis table format as ADDENDUM-M35 for direct comparison.

Q3  F1 RETRY: with the new kernel (content-routed or not per Q1),
    is write-time geometry loss-bearing? Rerun the kernel-distance
    features (exact per-item kernels from I1 snapshots at the final
    checkpoint). Branch rule identical to FOLLOWUP F1 (≥0.75 / 0.60–
    0.75 / <0.60). A flip to (i)/(ii) SOFTENS the v0.4 internality
    claim for synthesis — paper #2 states the correction explicitly.

Q4  PROBE SURVIVAL: relabel (GT16 protocol) under the full-recipe
    compactor; retrain c2/stack + the sink-head monitor; report
    evicted-only AUCs vs the subsampler's 0.85/0.76 and the F2
    context-only control (does the relational null hold under
    synthesis). Include GT22-style end-to-end row.
    outcomes: readable / degraded / unreadable — the last would mean
    divergence-prediction is compressor-difficulty-bounded, the most
    consequential possible result for the routability thesis.

Q5  SMUGGLING: pointwise lost-fact at matched budget vs eviction
    (the M3.5 0.271-vs-0.583 comparison rerun). Does the advantage
    persist under true blending, shrink, or invert?

Also emitted: fragility re-check (E1-style 2k relabel vs instance A —
does the nesting/κ structure survive a regime change), and the B ⊂ A
test against the full-recipe instance.
```

## Deliverables

FULLRECIPE-REPORT.md with Q1–Q5 verdicts in pre-registered vocabulary;
entropy/kernel telemetry curves + snapshots; certification reports
(per-axis, depth-aware, compaction_policy_version with weights hash +
max_certified_depth); refreshed labels, gate, probes + updated
arm-table rows; a "consequences for paper v0.4" section listing any
claim that needs a correction note, and a "paper #2 skeleton" section
mapping Q1–Q5 outcomes to sections.

## Budget

C1 rationale pass ≤ $250 (skip if audit says complete) · WP1 ≈
$460–640 · relabel + gate + probe re-runs ≈ $200–260 · telemetry ≈
$30. **Total ≈ $700–1,180.** Abort rules: GT26 red → stop; Q1 outcome
(c) confirmed at full recipe → Q2–Q5 still run (the subsampler-at-
scale result matters), but the 3000-step extension is cancelled.

## Stop condition

Q1–Q5 verdicts + deliverables → stop and report. No absorption work,
no Phase 4, no v0.4 edits (corrections, if any, go to paper #2 and an
arXiv v2 note — never silent).