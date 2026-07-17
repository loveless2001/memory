# PROBE.md — Content-Aware Sufficiency Probes (post-PREPROBE)

Handoff brief for the §17.3 escalation beyond the shadow gate. Conditioned
on PREPROBE-REPORT (2026-07-17): κ(A↔B)=0.745 → all arms viable, claims
scoped to fixed capacity; c0 floor = 0.564 [0.553, 0.575]; failure
mechanism = key→value binding loss under confusable-sibling interference;
fragility is (near-)ordered across instances (B ⊂ A). Precedence: this
brief on scope, spec v0.3.6 on semantics. Fixed capacity throughout:
`single-t1024-T8k` (A) is the reference instance; its GT16-protocol labels
are the training target.

**The one-line mission:** beat 0.564 evicted-only AUC with a signal that
reads the computation instead of the surface, and convert the winner into
end-to-end gate improvement (GT16-style operating point, GT17 multi-hop
retry).

### Do-not-build list
- No backbone/LoRA training. c3b retrains the COMPACTOR only (aux head).
- No serving integration; batch harness only.
- No new corpus; labels, contexts, checkpoints all exist.
- No cross-capacity claims: t=512 appears only in the GT24 transfer
  experiment, clearly labeled as such.

---

## P0 — Pilots (gate which arms proceed; ~$25 total)

```text
p1  attention-signal existence, 1,000 labeled evicted-only items
    (stratified y, domain): trial forward pass over the compact context
    with attentions captured; per item compute RAW statistics over the
    memory (latent) region at the last prompt token and first 3 decode
    steps: attention entropy, max single-latent mass, sink-position
    mass, memory-vs-recent mass ratio (lookback), top-head max.
    BAR: any single statistic ≥ 0.60 AUC → c1 proceeds as designed;
    all < 0.55 → c1 demoted to per-head analysis inside c2's sweep.
p2  prompted self-check floor (§17.3 option b): ask the base model, with
    the compact context, "does the context contain the information to
    answer this?" (letter-argmax yes/no), 1,000 items.
    This number is the floor ANY trained arm must beat to exist; it is
    also near-zero marginal cost in deployment, so report it honestly —
    if it lands ≥ 0.62 the cheap option changes the whole cost story.
p3  fragility-ordering harness: freeze the eval that scores any arm's
    output against the A/B 2k overlap — does the score rank B-lost <
    A-only-lost < survived? (ordinal AUC / Kendall τ). Built once in P0,
    applied to every arm.
```

## Arms (all evaluated: evicted-only AUC vs y_A, doc-level splits,
fixed capacity, 3 seeds for trained arms, cluster-bootstrap CIs,
per-domain table, p3 ordering row)

```text
c0.5  interference-geometry features (corpus-only, ~$10)
      the E2 autopsy says collision geometry is the mechanism; test
      whether it is visible WITHOUT the model: per item, over the
      compacted region — count of confusable siblings (same fact-type
      values within the region; near-duplicate key patterns by n-gram
      and by shadow-embedding similarity of candidate spans), sibling
      density around the needle, needle's key-distinctiveness (embedding
      distance to nearest sibling key). Logistic on top of c0's five.
      BAR: beat 0.564 upper CI; stretch 0.60. Even a null is
      publishable: "interference is real but only measurable inside the
      computation."

c1    attention-statistics probe (~$60 for ~30k-item capture)
      p1's statistics plus per-head features: identify the model's
      retrieval heads once (standard needle protocol on RAW contexts,
      per-head lock-on scoring), then featurize those heads'
      lock-vs-diffuse behavior over the latent region, sibling-split
      mass (attention divided among confusable latents = the collision
      signature), and sink-anomaly. Gradient-boosted/logistic head.
      Deployment shape: generate-then-verify (one trial pass), score at
      last-prompt + first decode steps.

c2    hidden-state probe (~$40; shares c1's capture run — hook residual
      stream in the same forward passes)
      linear probe per layer on the residual stream at the last prompt
      token (layer sweep), best-layer MLP variant second. This is the
      information ceiling for read-side signals; report the layer curve.

c3a   compactor cross-attention probe (frozen compactor, ~$15)
      the compactor SEES the destruction: at compaction time, capture
      its cross-attention (source positions → latents) and featurize
      collision directly — how many source positions share the needle's
      dominant latent, needle's write-mass concentration, sibling
      co-assignment. Probe on top. Write-time signal: zero
      inference-time cost, becomes loss_estimate metadata (§6.1, §8.2).

c3b   self-scoring compactor (retrain, ~$70, run ONLY if c3a ≥ 0.60)
      aux head on the compactor predicting per-source-span loss
      probability; multi-task KL + BCE (aux weight sweep {0.1, 0.3});
      supervision = A's span-aggregated labels, upweight
      confusable-sibling cases per the E2 tags. Corrected KL objective
      (post-f214c0f), NOT legacy. Verify the aux head does not degrade
      the primary KL (report both). New instance ⇒ new base rate ⇒
      relabel a 2k eval sample under it (PREPROBE unresolved #1).
```

## Golden tests

```text
GT19  P0 executed first; arm plan updated per p1/p2 bars before any
      capture run is scaled.
GT20  at least one arm beats the c0 floor's upper CI (0.575) with its
      lower CI — otherwise the honest verdict is "sufficiency under
      synthesis is not predictable from read/write-side signals at this
      scale," reported as such (escape-clause discipline).
GT21  best arm target 0.65 evicted-only AUC; escape clause: report the
      achieved frontier — the delta over 0.564 and over p2 is the
      result, not the round number.
GT22  end-to-end: plug the best arm (or best stack: c3a write-time +
      c1/c2 read-time — they are independent ends of the pipeline;
      test the stack if both pass GT20) into the gate; recalibrate;
      report the GT16-protocol operating point vs the refreshed gate's
      0.146 @ 0.147 and vs oracle 0.170. Win condition: strictly inside
      the refreshed gate's cost/correctness curve.
GT23  multi-hop retry (GT17's diagnosis was content-blind scores):
      rerun the s1 set-selector with the new arm's scores on the 2k
      multi-hop slice; target expand ≤ 1.5× oracle at lost ≤ 0.08;
      escape clause as ever — the delta vs 2.33× is the claim.
GT24  capacity transfer, labeled as such: best arm trained at t=1024,
      evaluated against the C (t=512) 2k relabels; report the drop.
      This bounds the per-capacity retraining cost story.
GT25  fragility ordering (p3): best arm's scores rank the A/B nesting
      above chance (Kendall τ CI excludes 0) — evidence the arm reads
      the underlying fragility scalar, not one checkpoint's noise.
```

## Deliverables

Arm comparison table (AUC + CI + p3 τ + per-domain, floors c0/p2 as rows);
layer curve (c2); retrieval-head inventory artifact (c1, reusable);
compactor collision-feature spec + populated loss_estimate fields (c3a);
end-to-end updated cost/correctness plane with the new operating point;
PROBE-REPORT.md with a verdict per GT and a "consequences for the paper"
section (the two-regime paper gains §8: what it takes to route around
synthesized loss).

## Compute budget

P0 ≈ $25 · captures (shared c1/c2) ≈ $60–80 · c0.5 ≈ $10 · c3a ≈ $15 ·
c3b (conditional) ≈ $70 · end-to-end + multi-hop ≈ $40.
Total ≈ $150–250 (c3b excluded) / ≈ $220–320 (included).

## Stop condition

GT19–GT25 resolved (green or frontier-documented) → stop and report.
No absorption work, no Phase 4, no serving. The paper restructure
proceeds in parallel and does not wait for this brief.