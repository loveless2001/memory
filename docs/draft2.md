# The Compactor That Couldn't Learn Where to Look: Gradient Saturation, Position-Kernel Collapse, and the Anchor Problem in Compression Certification

> **CLEAN E1FULL RESULT (2026-07-21): NO-SHIP.** The replacement n=60
> artifact reserves 15 documents/domain before training and reports zero
> document/item overlap. Depth-1 worsens aggregation KL versus matched eviction
> by +0.0495 (95% CI [0.0272, 0.0715]); runtime depth remains zero. Policy:
> `still-compact-v1:t1024:depth0:sha256:c00b2437fdd813cc`.

**Draft v0.4 — 2026-07-21.** Replaced the contaminated E1FULL table with
the signed clean-holdout result and all four paired intervals.

**Draft v0.3 — 2026-07-20.** Certification re-measured at n=60 documents
with paired CIs (n=12 left both aggregation verdicts unresolved), and the
task-anchored predicate applied to the frozen arm as well — it passes too,
which retires the "first certified" framing.

**Draft v0.2 — 2026-07-20.** Corrected against the E1FULL report of
record (v0.1 was drafted from a preliminary result set that the
completed report superseded in six places; every number below now
matches `E1FULL-REPORT.md`). Markdown master. Companion to paper #1,
whose arXiv v2 note carries the corrections this work motivated.

---

## Abstract

We report a failure mode of learned KV-cache compaction in which a
published compactor architecture cannot learn to route: trained under its
canonical configuration, the per-layer Perceiver's cross-attention kernel
is a uniform positional lattice that remains **bitwise identical to its
initialization** for the entire training run — at 1/40, 1/8, and full
recipe data scale — while the training loss falls normally. We name this
*position-kernel collapse* and identify the mechanism by gradient
forensics: the canonical attention logit scale (×d_l = 256) saturates the
softmax at the position-dominated identity initialization, delivering
gradients to the routing projections (W_Q, W_K) **eleven to twelve
orders of magnitude** smaller than to the value pathway (the latent
banks stay partially alive through their residual value-path role). The compactor's
apparent learning is entirely value-side: it learns what to do with
positions it can never change. Controls isolate the mechanism —
init-time noise does not escape (not a tie-breaking problem), and
content-seeded initialization stays frozen while paying a large loss
penalty (content without gradient does not help). The cure is one
constant: at √d_l scale, routing gradients wake by 10⁹–10¹⁰, the
softmax is de-saturated from step 0 (entropy starts at 0.82 nats
instead of the floor) and training then *raises* it, all eight KV-heads
despecialize from the shared lattice, the kept sets become item-adaptive,
and the unfrozen compactor overtakes the frozen one on the very objective
that froze it. The historical full-recipe certification cannot support a
held-out comparison because its evaluation documents overlap training. The
clean replacement confirms **GT13 NO-SHIP**: depth-1 greatly reduces silent
fact loss but worsens aggregation KL by +0.0495 [0.0272, 0.0715], and its
accuracy advantage remains uncertain. No frozen-versus-unfrozen ranking is
restored.
Downstream, kernel mobility *sharpens* the routing landscape of our
companion work rather than reorganizing it: write-time geometry stays
loss-blind even for a content-routed, item-adaptive kernel (AUC 0.5003)
— the internality claim's strongest test, passed; the text-shadow
expansion gate's marginal value completes a monotone decline to
**zero** (72% → 22.5% → 9.0% → 0%) while computation-reading probes
fully recover (stack 0.857) and retain routing power exactly where
shadow gating has none (silent loss pushed below never-expand at 9%
expansion); the clean checkpoint sharply improves pointwise preservation
against eviction but remains distributionally worse; and fact
fragility proves largely content-intrinsic — 78–91% of the unfrozen
compressor's losses nest inside the frozen lineage's — with a real but
minority regime-relative component. Total marginal compute: ≈ $925 across the three campaigns.
Diagnostics — a one-pass gradient-norm check and cross-attention entropy
telemetry — cost minutes and would have caught the collapse at step zero.

## 1. Introduction

Learned compaction promises what heuristic cache eviction cannot: a
compressor optimized end-to-end to preserve a frozen model's behavior.
The recipe we study — a per-layer Perceiver trained once against the
frozen base with a behavioral KL objective — reports strong results at
scale. We began by reproducing it at reduced scale for a certification
study and found something stranger than underperformance: the compactor
was not compressing at all in the intended sense. It was keeping every
third token.

This paper is the anatomy of that observation. Our contributions:
**(i)** *position-kernel collapse*, a failure mode in which a compactor's
routing freezes at initialization while its loss improves — undetectable
from the loss curve, invariant to data scale, and (we show) not a scale
artifact; **(ii)** the mechanism, established by direct gradient
measurement: logit-scale-induced softmax saturation at identity
initialization kills the routing pathway's gradient specifically, with
init-noise and content-seeded-init controls ruling out the alternative
explanations; **(iii)** the cure — reduce the logit scale — validated
from gradient wake-up through kernel mobility, head despecialization,
item-adaptivity, and training-loss crossover, at three seeds; **(iv)**
the consequence: a leakage-free full-recipe recertification that returns
GT13 NO-SHIP — silent loss improves sharply, but aggregation KL is
significantly worse than eviction and certified depth remains zero; **(v)** the
downstream sharpening: write-time geometry remains loss-blind even
under content routing (internality confirmed at its strongest test),
the text-shadow gate's routable fraction reaches zero while
computation-reading retains routing power, smuggling grows with
compressor quality, and fragility is largely fact-intrinsic —
motivating a *narrower-than-anticipated* refinement to our companion
paper, stated explicitly (§8);
**(vi)** two mandatory-cheap diagnostics for anyone training compactors.

## 2. Background and setup

[One paragraph each: the compactor recipe (per-layer Perceiver, identity
init, QK-norm with logit scale d_l, behavioral KL vs full-context
teacher, β = 0 throughout); the two-axis certification protocol from the
companion paper (counterfactually filtered probes, aggregation vs
pointwise axes never blended, matched retained budget, noise-floor row,
recurrence-depth certification); the corpus (98,355 items, four domains,
~1B tokens; 76.0k rationale-traced training items after domain
balancing); the harness-provenance note (a gradient-sync omission in the
earliest runs, found and fixed before this paper's experiments; the
frozen-kernel result reproduces identically under the corrected harness,
and the accidental small-batch run becomes a free control in §3).]

## 3. Position-kernel collapse

At every data scale — 9.5k, 76k items; batch 4 and true batch 32 — the
trained compactor's block-1 cross-attention rows are exact delta
functions: mean row entropy at the numerical floor (1.16 × 10⁻¹⁰ nats),
and the argmax kernel — `round(k·(S−1)/1023)`, a uniform stride-≈3
lattice shared by all eight KV-heads and all items — **bitwise identical
to initialization at every logged checkpoint of every run.** Meanwhile
the loss falls (0.58 → 0.36 over 1,500 full-recipe steps) and the
compactor's *behavior* improves monotonically: certified silent needle
loss drops from 0.196 (1/40) to 0.171 (full recipe) on the 60-document
protocol, with the later instance's failure set nested inside the
earlier's (94.1%). Every
improvement is value-side learning over a frozen routing skeleton — the
compactor learns what to write into fixed slots, never where to look.
The loss curve is not merely uninformative about this; it is actively
misleading, which is the operational point of §9's diagnostics.

Two published-recipe implications follow. First, evaluation suites that
aggregate over tasks would not distinguish this subsampler from a
synthesizer; our two-axis protocol did (the subsampler's profile —
aggregation-poor, needle-smuggling — is characteristic). Second, the
recipe's own ablation showing learned keys are load-bearing at full
scale implies full-recipe published checkpoints route content; we could
not reproduce escape by scale alone, which localizes the difference to
configuration, not data (§5 note on unexplored recipe deltas).

## 4. Mechanism: logit-scale-induced gradient saturation

One forward/backward at initialization, gradient norms by parameter
group: under the canonical ×256 logit scale, the routing projections
are numerically dead — W_Q ~1.1 × 10⁻¹¹, W_K ~1.6 × 10⁻¹⁰ — while
W_V, W_O, the block-2/self-attention groups, and the output heads sit
at 17–22: **eleven to twelve orders of magnitude of separation, exactly
along the routing/value cut** (the latent banks show a small nonzero
gradient, 6.1 × 10⁻², because they also feed the residual stream and
output heads — the clean routing-only weights are W_Q and W_K). Swapping the scale to √d_l = 16,
weights untouched, wakes precisely the dead groups by 10⁹–10¹⁰ while
value-path norms move a generic ~3.5×. The identity initialization
produces near-one-hot attention rows; multiplied by 256, the softmax is
saturated and passes ~zero gradient to its logits; everything upstream
of the attention weights starves, everything downstream trains.

Two controls sharpen the claim. Gaussian noise on the position logits at
canonical scale (E3) perturbs the kernel at step 0 and then freezes it
in its perturbed state — degenerate tie-breaking is not the mechanism;
saturation re-freezes whatever configuration it is handed. Content-seeded
latent initialization at canonical scale (E4) starts off-floor and stays
exactly flat while paying a large loss penalty for breaking the identity
passthrough — content in the pathway cannot substitute for gradient
through it.

## 5. The cure and its dynamics

At √d_l, the escape is immediate and complete: the softer scale
de-saturates the softmax at initialization (entropy starts at 0.815
nats rather than the floor), stays flat through warmup, then rises
smoothly from ~step 75 to 1.11 nats by step 188 at mid scale (1.01–1.11
across three seeds); the kernel moves (Jaccard vs init 0.18 by step
188) and — measured at full recipe — becomes **item-adaptive** (mean
cross-item Jaccard of kept sets 0.550, against 1.000 by construction
when frozen) with all eight KV-heads despecializing from the single
shared lattice (cross-head Jaccard 1.000 → 0.199 at mid scale; per-head
trajectories in Appendix).
Training dynamics show the honest trade: the soft scale leaks the
identity passthrough, so E1 *starts* worse (loss 0.737 vs 0.576) — the
×256 scale was protecting the passthrough — then crosses over before
step 60 (15-step smoothed) and finishes ahead (0.219 vs 0.365 mid-scale).
At full recipe, the historical mechanistic run established item-adaptivity
(cross-item Jaccard 1.000 → 0.550) and head reorganization. The leakage-free
replacement independently fired its registered extension at step 1,500
(entropy +0.0616 over 250 steps) and completed step 3,000 at entropy 1.8122
and loss 0.1348. The frozen configuration is not a bad optimum being
escaped; it is a gradient-dead region the canonical constant walls in.
A learned per-layer temperature initialized soft (E2) also escapes and
recovers sharpness where useful; we ship the fixed √d_l for simplicity
per our pre-registered selection rule. We note the published recipe may
differ from our reproduction in unexplored details; our claim is scoped
to the canonical configuration as specified, and the diagnostic (§9)
resolves the question for any implementation in minutes.

## 6. Certification: clean held-out no-ship

The signed replacement artifact reserves 15 documents per domain before
training and certifies 60 documents / 193 probes with zero document or item
overlap. Against matched eviction, depth-1 changes aggregation KL
0.0787 → 0.1281 and accuracy delta +0.0014 → +0.0536; pointwise lost-fact
incidence changes 0.683 → 0.106 and lost-given-prior-correct 0.631 → 0.050.
Paired candidate-minus-eviction intervals are:

| metric | difference | 95% CI |
|---|---:|---:|
| aggregation KL | +0.0495 | [0.0272, 0.0715] |
| accuracy delta | +0.0522 | [−0.0395, 0.1461] |
| lost-fact incidence | −0.5778 | [−0.7000, −0.4500] |
| lost given prior correct | −0.5806 | [−0.7028, −0.4528] |

The result is **GT13 NO-SHIP**: KL is significantly worse, and the accuracy
interval does not clear the registered −0.02 CI bound despite its positive
point estimate. Untrained depth-4 recurrence collapses (KL 13.664,
accuracy delta −0.156). The certified prefix is empty and runtime remains
`max_certified_depth = 0`. Policy
`still-compact-v1:t1024:depth0:sha256:c00b2437fdd813cc`. Because the clean
artifact did not rerun the historical frozen arm, no clean
frozen-versus-unfrozen ranking is claimed.

## 7. Downstream: routing under a mobile kernel

**Write-time geometry stays loss-blind — internality's strongest test,
passed.** Against the frozen lattice, kernel distance predicted nothing
(0.509) because every ≥3-token span contained a lattice point. The
anticipated flip under content routing did not occur: against the
unfrozen, item-adaptive kernel, the same features computed from
per-item kept sets still predict nothing — d_min 0.5003 [0.495, 0.505],
d_mean 0.519, fraction-of-needle-kept 0.519 — at every one of twelve
training checkpoints. Even when the kernel reads content, *which*
routed content survives is decided downstream of the geometry. The
companion paper's claim that compression loss is legible only inside
the query-conditioned computation survives with no qualification.

**The shadow gate reaches its floor; the ladder fully recovers.** The
text-shadow gate's marginal silent-loss reduction completes a monotone
decline to zero across four compressor generations: 72% → 22.5% →
9.0% → **0%** — its optimal operating point under the unfrozen
compressor *is* never-expand (0.089 lost at 0 expansion; A2
decomposition weak-flat at ~0.57). Computation-reading is a different
story: probes recover fully from the frozen-regime dip (stack 0.857
[0.847, 0.865]; best layer drifting 30 → 25 → 33, re-confirming probes
as per-policy artifacts), the two-hook sink-head monitor holds at
0.764 with zero-shot transfer across the frozen↔unfrozen divide
(0.759 / 0.727), and end-to-end the stack routes where the shadow gate
cannot — matching never-expand's loss at 0.5% expansion and pushing
*below* it, 0.049 lost at 9.1% expansion. The query-conditioned null
holds (context-only 0.507). The refined ladder statement: as
compressors improve, externally-visible routing signal is exhausted
first; the computation-reading tier is the last to retain routing
power, and at this generation it is the only one that does.

**Pointwise preservation improves, but the distributional trade remains.**
The clean depth-1 checkpoint cuts lost-given-prior-correct from 0.631 to
0.050 versus matched eviction, with a paired interval wholly below zero.
That gain accompanies significantly worse aggregation KL, not a clean win on
both axes. The clean control floor is 0.072 raw lost-fact incidence (the
conditioned control denominator is zero), versus 0.106 for depth-1, so the
gate remains formally mandatory even as its historical text-shadow tier hits
zero — precisely why the ladder's computation tier matters.

## 8. Fragility is largely fact-intrinsic — and a refinement to our companion paper

Across the frozen→unfrozen regime change, silent loss shrinks
(per-instance base rates 0.499 → 0.321 → 0.172) in a **mostly-nested**
pattern: 91.0% of the unfrozen compressor's losses lie inside the
original subsampler's failure set, and 78.5% inside the frozen
full-recipe's. Raw κ falls (0.28–0.42 cross-regime vs 0.745 within the
frozen lineage), but much of the drop is marginal-driven: base rates of
0.172 vs 0.499 cap κ even under perfect containment. The registered
verdict: fragility is **largely content-intrinsic**, with a real but
minority regime-relative component (9–21.5% novel losses). This
resolves a confound in the companion paper's §7 — its two frozen
instances shared an identical kernel, so their 0.94 nesting was partly
lattice-shared — but the refinement is *narrower than we ourselves
anticipated while drafting*: the shared kernel accounts for the
elevation from ~0.8 to 0.94, not for the nesting phenomenon itself,
which survives a kernel-class change largely intact. The companion
paper's arXiv v2 note is worded to the measured values. The per-policy
rules stand regardless: gate labels, calibration, and probes are
compaction-policy-scoped artifacts (best-layer drift alone guarantees
this); a policy change invalidates the decision layer's training data
along with the caches.

## 9. Diagnostics (the transferable deliverable)

Two checks, minutes each, that catch the collapse at step zero:
(1) **init gradient forensics** — one forward/backward, per-group norms;
routing groups orders of magnitude below value groups means saturation;
(2) **entropy telemetry** — cross-attention row entropy and argmax-set
identity logged during training; floor-pinned entropy with a static
kernel means the artifact is a subsampler regardless of its loss. Both
are now mandatory steps in our certification protocol, and we recommend
them for any Perceiver-style compactor, any resampler with sharpened
attention, and any architecture combining identity-style initialization
with large logit scales.

## 10. Limitations

One base model (4B), one compactor architecture and recipe family;
escape levers swept at mid scale (188 steps) with the selected lever
alone run to full recipe; full-recipe unfrozen run is single-seed
(mid-scale escape is 3-seed; no within-regime κ exists yet for the
unfrozen class); depth > 1 requires recurrence training, excluded here
(the depth-4 collapse is expected, not diagnostic); certification on extractive-MCQ probes
with letter-match equivalence, single-turn contexts, depths ≤ 4;
published-recipe deltas beyond logit scale unexplored — our collapse
claim is scoped to the canonical configuration as we implement it, and
the §9 diagnostics are the portable test; cost figures are marginal
rented-compute only.

## 11. Conclusion

A compactor whose loss falls for fifteen hundred steps at every data
scale never learned the one thing compaction is for — where to look —
because a single configuration constant walled its routing pathway
behind a saturated softmax from the first gradient step. The loss curve
could not see it; a one-pass gradient check and an entropy log see it
immediately. One constant later, routing learns, heads specialize, and the
kernel reads content. The clean certification then draws a hard boundary:
silent fact loss improves sharply, but aggregation KL is significantly worse
than eviction, so GT13 remains NO-SHIP and certified depth remains zero. The
downstream measurements sharpen rather than reorganize: write-time
geometry stays blind even to a content-routed kernel, the
externally-visible routing signal is exhausted entirely while the
computation-reading tier keeps routing, and fragility proves to belong mostly to the facts
themselves. The generalizable lesson is the method:
certify per axis, instrument the pathway you care about — not the loss
— and treat every improvement in the compressor as a fresh question
about what still fails, and whether you can still see it.

---

### Appendices
A. gradient-forensics tables (all groups × layers, both scales) ·
B. entropy/Jaccard/d_min trajectories, all arms and scales; per-head
despecialization · C. controls (E3/E4) full curves · D. certification
tables incl. noise-floor and depth rows; predicate definitions ·
E. downstream re-runs (labels, gate, probes, F1'/F2'/F5' analogs) ·
F. fragility matrices (within/cross regime) · G. harness-provenance
forensics (DDP omission; frozen-kernel invariance across the fix) ·
H. reproducibility: fingerprints, policy versions, compute ledger for
this paper's three campaigns ≈ $925 (frozen-lineage collapse study
≈ $440 + ESCAPE ≈ $95 + E1FULL ≈ $390; cumulative project ≈ $2,100).

### Figures
1. the two-panel signature: entropy-vs-step and loss-vs-step, frozen vs
unfrozen, crossover marked · 2. gradient-norm bars by group × scale
(log axis) · 3. kernel snapshots: frozen lattice vs unfrozen per-item
kept sets · 4. certification per-axis table as grouped bars ·
5. gate-marginal-value trend across four generations · 6. cross- vs
within-regime fragility agreement.

### Title alternatives
1. "Frozen at Birth: How a Logit Scale Kept a KV Compactor from
   Learning to Route"
2. "The Loss Curve Lies: Detecting and Curing Position-Kernel Collapse
   in Learned KV Compaction"
3. "Certified Against What? Anchor Choice Decides Which KV Compressor
   Wins"
