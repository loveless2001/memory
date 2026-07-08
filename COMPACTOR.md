# COMPACTOR.md — M3.5: Trained Amortized Compactor + Set-Scoring Selector

Handoff brief for spec Phase 3.5 (§8.1, Appendix B.4) plus the multi-hop
selector target quantified by M3. Authoritative documents:
`unified_memory_substrate_spec_v0.3.6.md` (semantics) and the Still paper
(arXiv:2606.07878) for the compactor recipe — the constants needed are
inlined below so the paper is reference, not required reading. Precedence:
this brief on scope, the spec on semantics. M0–M3 (incl. ABLATION.md
addendum) assumed complete; artifacts on `memsub-artifacts`.

---

## 1. Mission

Two work packages, ordered:

```text
WP1  train and certify a Still-class amortized KV compactor against the
     frozen Qwen3-4B base; replace evict-oldest-nonsink as the default L3
     path IF it clears certification (§13.4, two-axis, depth-aware);
     refresh the sufficiency-gate labels/calibration under the new policy
WP2  set-scoring selector: grouped expansion for multi-hop queries,
     targeting the M3 cost overhang (2.3× oracle → ≈1×)
```

The scientific questions, stated so the runs answer them: does trained
synthesis move the **aggregation axis** materially past untrained eviction
at matched retained budget? Does the **pointwise axis** remain collapsed
(predicted yes — synthesis does not rescue needles), re-confirming that the
gate is mandatory under every compaction regime? And what is the compactor's
**certified recurrence depth** on our workload?

### Do-not-build list
- No backbone/LoRA training; compactor parameters only, base frozen.
- β = 0 everywhere: no bias channel, no custom attention kernels.
- No vLLM tier; HF tier-(a) CompactedPrefixCache is the substrate.
- No soft slots, channels, recurrent absorption (§15, §16.4).
- No serving/latency optimization; batch harness only.

---

## 2. WP1 — Compactor

### 2.1 Architecture (Still canonical; constants inlined from the paper)

```text
one Perceiver-style compactor per transformer layer (36 for Qwen3-4B)
per layer: per-KV-head bank of t learned latent queries (H=8 banks),
  linear projections SHARED across heads
input  X = [K; V] per head (T × 2d), keys UN-ROTATED first (RoPE-fix)
blocks B = 2, pre-norm, cross-attention in EVERY block; latent
  self-attention; NO FFN; RMSNorm; QK-norm (L2 after projection);
  logit scale = d_l (not 1/√d_l); nc = ns = 1 heads
compactor-internal RoPE, base 10; latent query positions evenly spaced
  over the compacted range; compact keys RE-ROTATED at output positions
output heads (shared across heads within a layer):
  C_k = Z W_key, C_v = Z W_val; β head absent/zeroed
d_l = 256 (= 2d, REQUIRED by identity-style init)
init: identity-style (block-diagonal identity on value/output path,
  zeroed refinement output projections, position-dominated Q/K pathway)
size ≈ 50M params at t = 128 (~1% of base)
```

### 2.2 Training

```text
data       reuse the B.3 corpus triplets (ctx_ids, prompt_ids, answer_ids)
           — already teacher-verified + no-context filtered; 8k-context
           split; answer side includes the rationale trace + answer letter
loss       forward KL, full-context teacher → compact-cache student,
           answer-side tokens only, top-200 teacher support with the gold
           token forced into support; prompt/pad masked
optimizer  AdamW lr 4e-5 (β1 .9, β2 .95), warmup 100 linear, constant
           after; weight decay 0.01 matrices / 0 elsewhere; clip 1.0;
           effective batch 32; checkpoint at step 1500
tiers      full: 8×H100/H200, one working day, ≈ $400–700 per checkpoint
           reduced (fallback only): 1×H100 + grad accum, T=4k, t=512
sweep      single-pass checkpoints at t ∈ {128, 512, 1024} on T=8k
           (200×/16×/8× nominal); pick the certification winner
iterative  ONE iterative family at the deployment chunking (c tied to
           horizon), trained under the recurrence with the one-chunk raw
           lookahead buffer; reduced lr 2e-4; Lookahead optimizer for
           stability (aux-KV loss variant only as fallback)
```

### 2.3 Sanity gates before any long run

```text
GT11  near-pass-through at init: with identity init and t = T, compact-
      cache logits ≈ full-cache logits (top-k set match) BEFORE training.
      This is the cheap detector for RoPE-fix / re-rotation / offset bugs
      — the §12 failure class. Nothing trains until GT11 is green.
GT12  loss sanity: train loss falls below 0.4 within ~300 steps at t=512
      /T=4k (paper-consistent regime); if not, stop and debug rather
      than extend the run.
```

### 2.4 Certification (the actual experiment)

Run the M1 harness unchanged — same probes, same per-axis reporting, same
V2 noise-floor row — with the compactor as the compression policy:

```text
GT13  aggregation axis, matched retained budget vs evict-oldest-nonsink:
      compactor KL and surviving-span deltas must beat the untrained rows
      at the SAME physical cache size. This is the ship/no-ship gate for
      replacing the default L3 path.
GT14  pointwise axis: lost-fact incident over compacted-away spans,
      reported per fraction — prediction: remains high (needle collapse
      is intrinsic to synthesis). Whatever the number, the §13.4 rule
      re-attaches: aggregation-only certification ⇒ gate mandatory.
GT15  depth certification: certify at recurrence depths {1, 4, N_deploy};
      emit max_certified_depth into compaction_policy_version (compactor
      weights hash included); resume paths refuse to stack past it
      (unit-tested, mirrors GT3's parameterized style).
```

### 2.5 Gate refresh (policy change ⇒ label change)

The M3 gate is bound to the eviction policy it was labeled under; a new
compaction policy is a new label distribution (spec §4.6 / §13.4).

```text
relabel     rerun the §17.5 counterfactual labeling with the compactor as
            C (reuse the M3 labeling scaffolding; ~same $110-class cost)
gate        retrain the same dual-encoder config (all three A2 ablation
            rows again — the mechanics/content decomposition may CHANGE
            under synthesis, which is itself a paper-relevant result);
            recalibrate per fraction and per domain (recalibrate.py)
GT16  end-to-end: compactor + refreshed gate at its operating point
      achieves lost-fact ≤ the M3 end-to-end number (0.143-class) at
      expand-rate ≤ the M3 rate, on the same test protocol. If the
      frontier is better (plausible: better aggregation tier ⇒ fewer
      borderline losses), report the improvement; if worse, report
      honestly per the GT9 escape clause.
```

---

## 3. WP2 — Set-scoring selector (multi-hop cost overhang)

M3 finding: at the single-hop threshold the gate holds multi-hop
correctness (0.036 lost) only by over-expanding — recall 0.904, precision
0.388, expand 0.438 vs oracle 0.188 (2.3×). Cause hypothesis: per-block
independent scoring cannot represent "this query needs blocks {i, j}
jointly", so every plausibly-relevant block crosses τ independently.

```text
approach    score block SETS, cheapest first:
            (s1) top-k grouped expansion: rank blocks by gate score,
                 expand the top-k as ONE decision with k chosen by a
                 budget-aware stopping rule (marginal-score gap)
            (s2) query-conditioned joint head: small MLP over the
                 concatenated top-m block interactions predicting the
                 REQUIRED SET SIZE; expand exactly that many
            implement s1 first; s2 only if s1 misses GT17
labels      the 500-item multi-hop slice already carries per-fact source
            blocks → set-level ground truth exists; expand the slice to
            ~2,000 items (same k=2 construction, ~$50) for train/test
GT17  on the multi-hop test slice: expand-rate ≤ 1.3× oracle at
      lost-fact ≤ 0.05 and recall ≥ 0.85. Escape clause: if unreachable,
      report the achieved frontier against the M3 2.3× point — halving
      the overhang is still the paper delta.
GT18  no single-hop regression: the set-scoring path, applied to the
      single-hop test split, stays within CI of the M3 operating point.
```

---

## 4. Deliverables

```text
compactor checkpoints (sweep + iterative) + training curves
updated compaction_policy_version records (weights hash,
  max_certified_depth) and re-emitted certification reports (per-axis,
  vs untrained-eviction rows at matched budget, noise-floor row)
refreshed gate checkpoint + per-domain calibration + A2-style
  decomposition under the new policy
set-selector module + multi-hop eval JSON + updated cost/correctness
  plane with the s1/s2 curves added
ADDENDUM-M35.md: one page — ship/no-ship verdict on GT13, the GT14
  pointwise number, certified depth, GT16/GT17 frontiers
```

## 5. Compute budget

```text
compactor sweep (3 single-pass + 1 iterative)   ≈ $600–1,000
certification + relabel + gate retrain          ≈ $150–250
multi-hop slice expansion + WP2                 ≈ $80–120
total                                            ≈ $850–1,400
```

## 6. Stop condition

When GT11–GT18 are green or honestly documented as frontier findings,
stop and report. Do not begin absorption-tier work (§16.4), soft slots,
or any serving integration. The absorption measurement study is the next
brief, not this one.