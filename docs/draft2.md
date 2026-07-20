# The Compactor That Couldn't Learn Where to Look: Gradient Saturation, Position-Kernel Collapse, and the First Certified KV Compressor

**Draft v0.1 — 2026-07-20.** All experimental branches resolved (ESCAPE +
E1FULL reports); no placeholders. Markdown master. Companion to paper #1
("Reading the Computation"), whose arXiv v2 carries the two corrections
this work motivated.

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
gradients to the routing pathway (latent queries, W_Q, W_K) **ten orders
of magnitude** smaller than to the value pathway. The compactor's
apparent learning is entirely value-side: it learns what to do with
positions it can never change. Controls isolate the mechanism —
init-time noise does not escape (not a tie-breaking problem), and
content-seeded initialization stays frozen while paying a large loss
penalty (content without gradient does not help). The cure is one
constant: at √d_l scale, routing gradients wake by 10⁹–10¹⁰, kernel
entropy leaves the numerical floor within 50 steps, all eight KV-heads
despecialize from the shared lattice, the kept sets become item-adaptive,
and the unfrozen compactor overtakes the frozen one on the very objective
that froze it. At full recipe, the unfrozen compactor becomes — to our
knowledge — the first learned compactor to pass a pre-registered two-axis
certification against an eviction baseline at matched retained budget, on
both a distributional predicate (teacher KL 0.108 vs 0.122, CI-separated)
and a task-anchored one, at recurrence depths 1 and 4. Downstream, kernel
mobility reorganizes the routing landscape measured in our companion
work: write-time geometry becomes loss-predictive exactly when routing
becomes content-dependent (AUC 0.51 → 0.71); the expansion gate's
marginal value continues its monotone decline across compressor
generations (72% → 22.5% → 9.0% → 4.1% silent-loss reduction) without
reaching zero; the hidden-state probe ladder survives (0.87 / 0.79); and
fact fragility — nested and stable across frozen instances — reshuffles
across the regime change (κ 0.31), showing it is a property of the
(fact, compression regime) pair. Total marginal compute: ≈ $560.
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
the consequence: a full-recipe unfrozen compactor that passes a
pre-registered two-axis certification against eviction at matched
budget, on two independent predicates, including at recurrence depth 4
where the frozen lineage collapsed; **(v)** the downstream
reorganization: with routing content-dependent, write-time geometry
becomes a usable loss signal, gate value continues to shrink but not
vanish, and fragility proves regime-relative — motivating a scope
correction to our companion paper, which we state explicitly (§8);
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
loss drops from 0.271 (1/40) to 0.188 (full recipe), with the later
instance's failure set nested inside the earlier's (94.1%). Every
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
group: under the canonical ×256 logit scale, the routing pathway is
numerically dead — latent queries ~1.1 × 10⁻¹¹, W_Q ~2.9 × 10⁻¹²,
W_K ~3.1 × 10⁻¹² — while W_V (0.021), W_O (0.017), and the output heads
(0.038–0.041) are healthy: **ten orders of magnitude of separation,
exactly along the routing/value cut.** Swapping the scale to √d_l = 16,
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

At √d_l, the escape is immediate and complete: entropy departs the floor
by step 50 and rises smoothly through 188 mid-scale steps (0 → 0.84
nats, all three seeds, tight); the kernel moves (Jaccard vs init 0.31 by
step 188) and — measured at full recipe — becomes **item-adaptive**
(mean cross-item Jaccard of kept sets 0.42, against 1.000 by
construction when frozen) with all eight KV-heads despecializing from
the single shared lattice (per-head divergence trajectories in Appendix).
Training dynamics show the honest trade: the soft scale leaks the
identity passthrough, so E1 *starts* worse (loss 0.61 vs 0.44) — the
×256 scale was protecting the passthrough — then crosses over near step
120 and finishes ahead (0.219 vs 0.365 mid-scale; the gap persists at
full recipe). The frozen configuration is not a bad optimum being
escaped; it is a gradient-dead region the canonical constant walls in.
A learned per-layer temperature initialized soft (E2) also escapes and
recovers sharpness where useful; we ship the fixed √d_l for simplicity
per our pre-registered selection rule. We note the published recipe may
differ from our reproduction in unexplored details; our claim is scoped
to the canonical configuration as specified, and the diagnostic (§9)
resolves the question for any implementation in minutes.

## 6. Certification: the first ship

Full two-axis certification at matched retained budget against the
eviction baseline, both pre-registered predicates:

| axis / predicate | eviction | frozen full-recipe | **unfrozen full-recipe** |
|---|---:|---:|---:|
| aggregation KL (↓) | 0.1218 | 0.257 | **0.108 [0.101, 0.116]** |
| aggregation accΔ vs teacher | −0.031 | +0.063 | **+0.041** |
| pointwise silent loss (↓) | 0.583 | 0.188 | **0.204** |
| depth-4 KL | (n/a) | 2.29 (collapse) | **0.131 (certifies)** |
| verdict (distributional) | baseline | NO-SHIP | **SHIP** |
| verdict (task-anchored) | baseline | NO-SHIP (KL) | **SHIP** |

The two predicates — whose dissociation the frozen lineage exposed
(distributionally unfaithful yet task-better) — agree for the first
time. The pointwise row shows the pre-registered trade: content routing
spends a sliver of the frozen subsampler's needle-smuggling advantage
(0.188 → 0.204, both far below eviction's 0.583) to buy the aggregation
win — the companion paper's two-workload antagonism operating *inside*
one compressor's training dynamics. max_certified_depth = 4;
compaction_policy_version `still-e1-fullrecipe-t1024` with weights hash
and diagnostics attached.

## 7. Downstream: routing under a mobile kernel

**Write-time geometry becomes loss-bearing.** Against the frozen
lattice, needle-to-kept-position distance predicted nothing (AUC 0.509)
— every ≥3-token span contained a lattice point. Against the unfrozen,
item-adaptive kernel, the same feature family computed from per-item
kept sets reaches **0.71**: geometry regains predictive power exactly
when routing reads content. The companion paper's internality claim
refines accordingly: loss is internal to whichever pathway makes the
routing decisions, and becomes externally legible precisely when that
pathway's decisions become inspectable at write time.

**The gate's value shrinks; the ladder survives.** Refreshed on
unfrozen-compactor labels, the hidden-state probe reads divergence at
0.87 and the two-hook sink-head monitor at 0.79 (zero-shot transfer
both directions with prior regimes intact); end-to-end, the gated
system reaches silent loss 0.101 at expansion rate 0.041. The gate's
marginal silent-loss reduction across four compressor generations:
72% → 22.5% → 9.0% → **4.1%** — monotone, and plausibly asymptotic
above zero. Routing value falls as compressors improve; it does not
vanish, and the query-conditioned null (context-only probes at chance)
holds under content routing.

## 8. Fragility is regime-relative — and a correction to our companion paper

Across the frozen→unfrozen regime change, which facts die reshuffles:
cross-regime κ = 0.31 with nesting 0.44, against within-regime κ = 0.68
(unfrozen reseeds) and 0.745/0.94 (frozen instances). This resolves a
confound in the companion paper's §7: its cross-instance nesting
evidence came from two instances sharing an *identical frozen kernel*,
so part of the observed stability was the shared lattice. The corrected
claim — filed as an arXiv v2 note there and stated here — is that
**fragility is stable within a compression regime and substantially
regime-relative across regimes.** Practically: gate labels and
calibration are compaction-policy-scoped artifacts; a policy change
invalidates the decision layer's training data along with the caches.

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
(mid-scale escape is 3-seed); certification on extractive-MCQ probes
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
immediately. One constant later, routing learns, heads specialize, the
kernel reads content, and the result is the first learned compactor to
pass a two-axis certification against eviction — while the downstream
measurements reorganize on cue: geometry becomes predictive when
routing becomes contentful, the safety gate's value shrinks toward a
floor it never reaches, and fragility reveals itself as a property of
the (fact, regime) pair. The generalizable lesson is the method:
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
H. reproducibility: fingerprints, policy versions, ~$560 compute ledger
(cumulative project ≈ $2,100).

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
3. "One Constant Away: From a Compactor That Cannot Route to the First
   Certified KV Compressor"