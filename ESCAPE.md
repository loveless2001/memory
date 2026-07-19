# ESCAPE.md — Unfreezing the Position Pathway (blocking for paper #2 freeze)

Pilot testing the mechanism hypothesis for the frozen kernel, and whether
cheap levers escape the fixed point. Authoritative context:
FULLRECIPE-REPORT (Q1 outcome (c): argmax kernel bitwise frozen at init,
entropy at the 1.16e-10 floor, at every scale; value path trains and
rescues). Precedence: this brief on scope, spec v0.3.6 on semantics.
All runs use the FIXED harness (true batch 32, synced grads) and the
existing I1/I2 telemetry unchanged — the telemetry IS the readout.

**Hypothesis (pre-registered):** the frozen kernel is
**logit-scale-induced gradient saturation**. The canonical config
multiplies QK-normed cosine logits by d_l = 256; at identity init the
position-dominated pathway already yields near-one-hot rows, and a
saturated softmax passes ~zero gradient to its logits — the routing
pathway (latents, W_Q, W_K, compactor RoPE phase) is gradient-dead from
step 0, while the value/output path (downstream of the weights) trains
normally. Prediction: reducing effective logit scale (or breaking exact
saturation at init) restores routing gradient and entropy leaves the
floor; if entropy stays at floor even at √d_l scale, the fixed point is
not (only) saturation.

### Do-not-build list
- No full-recipe runs; mid-scale (1/8, 9,498 items, 188 steps) only.
- No architecture changes beyond the four registered levers below.
- No downstream re-certification in this brief (that is paper-#2 work,
  conditioned on this pilot); Q-style relabels limited to the I2 1k
  subsample.
- No backbone anything, β = 0, corrected KL, as always.

---

## P0 — Gradient forensics (~$5, before any training; can settle the
hypothesis on its own)

```text
G1  at init, on the fixed 128-item probe batch, one forward+backward:
    log grad-norm per parameter group — latent banks, W_Q, W_K,
    W_V, W_O, output heads — per layer.
    prediction under the hypothesis: ‖∂L/∂{latents, W_Q, W_K}‖ ≈ 0
    (numerically dead) while ‖∂L/∂{W_V, W_O, heads}‖ is healthy.
G2  same measurement with logit scale swapped to √d_l = 16, weights
    untouched: routing grads should wake by orders of magnitude if
    saturation is the mechanism.
    G1+G2 together are near-dispositive BEFORE spending on training;
    run them first and record the ratio table.
```

## Arms (each = mid-scale run, 188 steps, true batch 32, full I1 every
25 steps + I2 at {47, 94, 141, 188}; canonical config except the one
lever; 3 seeds ONLY for whichever arm is selected as the escape
candidate, single seed for the sweep)

```text
E0  baseline replication (canonical, d_l scale) — the frozen reference
    under the fixed harness; $0 marginal (exists: FULLRECIPE mid run —
    reuse, do not retrain)
E1  logit scale = √d_l (16)          the direct saturation test
E2  learned temperature, init √d_l   scale as a trainable scalar per
                                     layer (clamped [1, d_l]) — lets
                                     the model choose sharpness AFTER
                                     routing learns
E3  position-logit noise at init     Gaussian σ=0.02 on Q/K biases
                                     (breaks exact one-hot ties;
                                     scale stays d_l) — separates
                                     "saturation" from "symmetric
                                     tie-breaking failure"
E4  content-seeded init              latent bank initialized from
                                     mean-pooled corpus [K;V] cluster
                                     centroids instead of zeroed
                                     content pathway; scale d_l —
                                     the non-identity-init arm
                                     (FULLRECIPE unresolved #1)
```

## Readouts (per arm, all from I1/I2 — no new instrumentation)

```text
R1  entropy-vs-step curve (the signature readout): floor / drift /
    transition, with step of first departure > 10× floor
R2  kernel mobility: argmax-set Jaccard vs init at each checkpoint
    (bitwise-frozen = 1.000 throughout)
R3  d_min AUC at each I2 point: does write-time geometry become
    loss-bearing once (if) routing moves — the F1-flip question,
    finally testable
R4  y+ on the I2 1k subsample at step 188 vs E0's 0.370-class: does
    unfreezing HELP or HURT short-horizon quality (an escaped kernel
    that loses more facts at 188 steps is not yet a better compactor —
    report, don't conclude; 188 steps is not a training claim)
R5  final loss + loss@300-equivalent tripwire per arm
```

## Decision rules (pre-registered, verbatim in the report)

```text
D1  G1 shows dead routing grads AND G2 wakes them
      → hypothesis CONFIRMED at the gradient level regardless of
        training outcomes; report the ratio table as the mechanism
        evidence.
D2  any arm's entropy departs floor (R1) with Jaccard < 1.0 (R2)
      → ESCAPE DEMONSTRATED; that arm is the paper-#2 constructive
        result; run its 3-seed replication; R3 on it answers the
        F1-flip question and selects paper #2's §5 branch.
D3  E1–E4 all stay at floor with Jaccard 1.000
      → the fixed point is ROBUST to the cheap levers; paper #2's
        claim hardens to "position-kernel fixation under the Still
        recipe is not rescued by logit scale, temperature, noise, or
        content-seeded init at mid scale" — with G1/G2 either
        localizing the deadness elsewhere or (if G2 woke grads but
        training still froze) pointing at optimization dynamics
        beyond init-time saturation.
D4  R4 quality regression in an escaped arm does NOT veto D2 —
      escape and quality are separate claims at 188 steps; whether an
      escaped kernel eventually WINS is full-recipe work, explicitly
      out of this brief.
```

## Deliverables

ESCAPE-REPORT.md: G1/G2 gradient table; per-arm R1–R5 with the D-rule
verdicts verbatim; entropy overlay figure (all arms, one plot — the
candidate signature figure for paper #2 §2 or §5); if D2: the escaped
arm's 3-seed replication + its R3 branch selection; a "consequences for
paper #2" section mapping D-outcomes to the skeleton's §2/§5 and stating
whether the full-recipe escaped run (next brief, ~$110) is warranted.

## Budget

G1/G2 ≈ $5 · E1–E4 ≈ $20–25 each (mid run class) · I2 relabels ≈ $6/arm
· 3-seed replication of one arm ≈ $50 · misc ≈ $10.
**Total ≈ $130–185.**

## Stop condition

D-verdicts + deliverables → stop and report. No full-recipe retrain, no
downstream re-certification, no paper edits (branch-drafting waits for
the report, per standing practice).