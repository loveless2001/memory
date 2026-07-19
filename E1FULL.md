# E1FULL.md — Full-Recipe Unfrozen Compactor: Third GT13 Attempt Under a Mobile Kernel

Campaign brief for the full-recipe run of the escaped configuration and
the re-interrogation of every finding that was established under a frozen
kernel. Authoritative context: ESCAPE-REPORT (D1 confirmed: logit-scale
saturation; E1 √d_l escapes — entropy rises, kernel moves, mid-scale loss
beats frozen baseline), FULLRECIPE-REPORT (the frozen-kernel Q1–Q5
verdicts this brief re-tests). Precedence: this brief on scope, spec
v0.3.6 on semantics. Fixed harness (true batch 32, synced grads)
throughout; I1/I2 telemetry unchanged.

**Framing (into the report header):** FULLRECIPE established a law under
a frozen kernel — aggregation kernel-bound, pointwise smear-bound,
routability falling as compressors improve. This run dissolves the
law's premise. Every question below is "does X survive kernel
mobility," and the pre-registered outcomes make both survival and
collapse reportable.

### Do-not-build list
- No iterative-family training (single-pass only; depth cert for the
  record).
- No backbone anything; corrected KL; β = 0.
- No serving work; no spec edits (a ship verdict routes to a spec
  v0.3.7 change note, never silent).
- No new probe arms; re-runs of existing harnesses only.

---

## P0 — ESCAPE closeout + arm selection (blocks training)

```text
P0.1  ESCAPE final report complete: E2 rerun landed, D2 3-seed
      replication of the escaped arm, R3/R4 sweeps, AND:
        R6 item-invariance — mean pairwise cross-item Jaccard of kept
        sets per checkpoint (from existing I1 per-item argmax
        snapshots, $0). Frozen ⇒ 1.000; report the E1 trajectory.
        R7 head divergence — define the kept-set union metric
        precisely (per-head sets, union across 8 KV-heads) and report
        per-head pairwise Jaccard vs step: despecialization from the
        shared lattice, or one moving lattice?
P0.2  arm selection rule (pre-registered): among ESCAPE arms with
      D2-class escape (entropy departure + Jaccard < 1.0, 3-seed
      stable), select by final mid-scale loss; ties → simplest lever
      (E1 fixed √d_l over E2 learned temperature). Record the
      selection and its numbers; the chosen config is frozen into
      compaction_policy_version material.
P0.3  sanity gates, adapted: GT11 identity passthrough DOES NOT APPLY
      (the soft scale intentionally leaks it — ESCAPE R5 init loss).
      Replacement GT27: init loss finite and < 1.5; loss@300 tripwire
      re-anchored to the ESCAPE mid-scale curve (< 0.45); NaN/inf
      watchdog.
```

## WP1 — Training

```text
run        selected config, full mixture (75,998 traced items,
           manifest hash unchanged), T=8k, t=1024, 1500 steps, true
           batch 32, 8×H100; step-tagged checkpoints every 250;
           I1 every 50, I2 at every checkpoint (1k relabels)
extension  REINSTATED (FULLRECIPE's Q1(c) abort no longer applies):
           if mean entropy is still rising at step 1500 (slope over
           last 250 steps > 0.01 nats), continue to 3000; decision
           logged. Budget both cases.
Q1'        report entropy, cross-item Jaccard (R6), head divergence
           (R7), and d_min AUC trajectories at full scale — does
           routing keep learning with 8× the data, and does the
           kernel become item-adaptive (R6 < ~0.9) or remain one
           mobile lattice?
```

## WP2 — Re-interrogation battery (all existing harnesses)

```text
Q2'  GT13, THIRD ATTEMPT — the headline. Full certification, M1
     harness, matched retained budget, per-axis, noise-floor row,
     depths {1, 4}. TWO registered verdicts, both reported:
       primary (comparability): the original GT13 predicate — beat
         eviction KL (0.1218) within 0.02 accΔ. Ship/no-ship on this.
       secondary (task-anchored, registered NOW because FULLRECIPE
         exposed the KL/accΔ dissociation): aggregation accΔ ≥
         eviction's AND pointwise lost ≤ eviction's at matched
         budget. Report its verdict beside the primary; if the two
         disagree, paper #2's certification-anchors section (the
         resmse dissociation) carries the discussion — the predicate
         tension is a finding, not a footnote.
     If EITHER verdict ships: emit the policy version, and route the
     L3-default question to a spec v0.3.7 change note with the full
     table (never a silent flip).
Q3'  F1 under (possibly) per-item kernels: if R6 shows item-adaptive
     routing, compute kernel-distance features from PER-ITEM kept
     sets (capture pipeline handles this); branch rule unchanged
     (≥0.75 / 0.60–0.75 / <0.60). A flip to (i)/(ii) here would mean
     write-time geometry becomes loss-bearing exactly when routing
     reads content — the cleanest possible refinement of the
     internality claim, and paper #2 §5's branch selector.
Q4'  probe survival under content-routed compression: GT16 relabel
     (full manifest), c2/stack/sink-heads retrained, F2 context-only
     control, GT22-style end-to-end row, gate refresh with its
     marginal-value number — the fourth point on the 72% → 22.5% →
     9.0% → ? trend, now with the compressor class changed. Also
     rerun F5-style regime transfer of the sink-head monitor to the
     new instance (zero-shot both directions).
Q5'  smuggling at matched budget vs eviction (0.583) and vs the
     frozen full-recipe (0.188): does content routing keep, grow, or
     spend the pointwise advantage? (A content-adaptive kernel might
     trade needle smuggling for aggregation — registered as a
     legitimate outcome, not a regression.)
Q6'  fragility structure: E1-style 2k relabel vs instances A and FR.
     Frozen-regime nesting was 94.1% ⊂ A; a content-routed kernel
     plausibly RESHUFFLES rather than nests — either outcome is
     informative (nesting survives ⇒ fragility is content-intrinsic;
     reshuffle ⇒ fragility was lattice-relative). κ and nesting
     fractions, per-instance base rates quoted per PREPROBE practice.
```

## Deliverables

E1FULL-REPORT.md: Q1'–Q6' verdicts in registered vocabulary; the
two-verdict Q2' certification table; trajectory figures (entropy +
R6 + R7 + d_min overlay — paper #2's closing figure); updated
arm-table rows and compaction_policy_version records; "consequences
for paper #2" mapping outcomes to the skeleton's §2/§5/§6 and a new
closing section; "consequences for the spec" (v0.3.7 change note if
any verdict ships); explicit statement of the gate-marginal-value
trend point.

## Budget

WP1 train ≈ $110 (+$110 if extension fires) · Q2'/Q5' cert ≈ $10 ·
Q4' relabel fleet ≈ $95 · Q4' capture ≈ $45 · probes/gate/F2/F5 ≈ $10 ·
Q3' ≈ $10 · Q6' ≈ $5 · P0 closeout (R6/R7 analysis, 3-seed if not yet
run) ≈ $0–55. **Total ≈ $285–450.**

## Stop condition

Q1'–Q6' + deliverables → stop and report. No iterative retrain, no
absorption work, no paper edits (paper #2 v0.1 branch-drafts against
this report; paper #1 remains untouched beyond the already-planned
arXiv v2 note).