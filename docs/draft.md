# Reading the Computation: How Compression Regime Determines Whether Lost Memory Is Routable

**Draft v0.5 — 2026-07-21.** Supersedes v0.4 with the certification-scope correction below; FOLLOWUP2 remains folded (F4: context-only null upgraded to full probe sweep; F5: sink-head monitor regime-general, added to §4.2/§6.3/Fig. 2).

> **Clean E1FULL follow-up (2026-07-21): NO-SHIP.** The leakage-free
> replacement run fails GT13 and certifies depth zero under checkpoint hash
> `c00b2437fdd813cc`. The frozen 1/40 arm in this paper was **not rerun** on
> that reserved holdout. Its original table is therefore a **historical 12-context**
> measurement of the trained artifact, **not clean held-out evidence** and not
> a basis for deployment or cross-generation ranking.
> The routing, probe, and position-kernel measurements remain within-protocol
> behavioral evidence.

---

## Abstract

Lossy compression of a language model's context memory produces silent
failures: facts the model once held are answered wrongly, with full
confidence, and no signal at generation time. We show that *which* signals
can predict — and therefore route around — this loss depends on the
compression regime, and we measure the full picture on one certification
protocol, one frozen 4B model, and a ~1B-token four-domain corpus of
98,355 counterfactually filtered probes. Under **contiguous eviction**,
loss is governed by observable mechanics: a $140 dual-encoder gate over
text shadows cuts silent loss 72% at a fifth of always-expand cost, ECE
≤ 0.023. Under a **trained compactor**, the same gate class collapses to
surface-statistics performance (AUC 0.55 ≈ a five-feature logistic at
0.56): the loss becomes invisible to write-side and corpus-side signals.
It does not become unpredictable — it becomes *internal and
query-conditioned*. A linear probe on the frozen model's residual stream
(layer 30), with the question present, predicts answer divergence at
0.819; a small stack reaches 0.854 and, deployed as a gate, matches the
shadow gate's correctness at one third of its expansion budget. A
context-only control shows the signal is *relational*: without the
question, no probe recovers it — linear or MLP, at any of six layers or
over their concatenation (max AUC 0.508 vs 0.813 with the question) —
consistent with sufficiency being a property of (query, memory) pairs
rather than of the memory state alone. We
further show (i) a deployment ladder of increasing cost — a prompted
self-check (0.638, one forward, no training), a two-hook attention-head
monitor (0.762; regime-general — it reaches 0.783 under eviction,
above the shadow gate's own discrimination, and transfers zero-shot
between regimes), and the trained probe stack (0.854); (ii) that probe
scores rank an instance-independent *fragility ordering* validated across
compactor reseeds (κ=0.745; Kendall τ 0.57); and (iii) a mechanistic
surprise: our 1/40-scale compactor's cross-attention consists of exact
positional delta kernels — it performs strided subsampling, not content
synthesis (**position-kernel collapse**; the learned kernel is a uniform stride-3
lattice, identical across heads and items, and its geometry is
loss-blind — needle-to-kept-position distance predicts survival at
0.509), which reframes both its historical protocol failure and its
unexpectedly *better* pointwise retention versus eviction at matched
budget (0.27 vs 0.58 silent loss). Total
marginal compute across all experiments: ≈ $1,100.

## 1. Introduction

[carries v0.1 §1's two-workload framing — pointwise vs. aggregative,
antagonistic under lossy compression — then pivots:] The antagonism makes
a *router* the critical component: a calibrated per-query estimate of
whether compressed memory suffices. This paper's question is what
information such a router can be built from, and the answer turns out to
be regime-dependent in a way we believe has not been measured before.

Contributions: **(i)** a two-axis certification protocol (aggregation /
pointwise, never blended) with counterfactually filtered probes;
**(ii)** its application to two compression regimes at matched retained
budget, showing the axes *trade* — eviction preserves aggregation and
destroys needles; our compactor degrades aggregation while halving
silent needle loss; **(iii)** the routability result: eviction loss is
mechanics-routable (0.72 reduction from shadow features), compactor loss
is routable only by reading the computation (0.85 AUC from the residual
stream; 0.56 from everything outside it); **(iv)** a three-rung
deployment ladder with measured cost/benefit at each rung; **(v)**
position-kernel collapse as a failure mode of small-scale learned
compaction, with cross-attention entropy as its certification-time
diagnostic; **(vi)** instance-independent fragility ordering; **(vii)**
multi-hop entry-gating beating per-block selection (1.98× vs 2.33×
oracle cost).

## 2. Related work
[v0.1 §2 carries over: KV reduction (selection / amortized selection /
synthesis / architecture-level), selective prediction & abstention,
memory-augmented agents. Add: probing & representation reading (linear
probes on residual streams; truthfulness/uncertainty probes) — our probe
is a *sufficiency* probe over an external memory tier, supervised by
counterfactual behavioral labels rather than truth labels. Add:
attention-sink literature — we repurpose sink-mass anomaly as an
insufficiency sensor (§6.3). verify-all-citations flag stands.]

## 3. Two axes and a certification protocol
[v0.1 §3 verbatim: definitions of counterfactual validity, aggregation
axis, pointwise axis (lost-fact incident rate), per-axis certification,
gate-mandatory rule, zero-compression noise floor (measured 0.000).]

## 4. Regime I — contiguous eviction: mechanics-routable loss

### 4.1 Setup and axis split
[v0.1 §4: corpus, filters, eq_policy, evict-oldest-nonsink 0.25/0.40,
sink pinning; canonical never-expand per protocol; KL ~0.03 while
evicted-span silent loss dominates.]

### 4.2 The shadow gate
[v0.1 §5.1/5.3: dual encoder, native calibration (ECE 0.023/0.017),
strict dominance over classify-and-expand, operating point 0.143 @
0.169 vs oracle 0.194; A2 decomposition: features-only ≈ full —
**the signal is eviction mechanics**, and that is enough here. §6.3's
head monitor later exceeds this gate's evicted-only discrimination even
in this regime (0.783 vs 0.622); the gate's end-to-end value — built on
calibration and free evicted/survived metadata — stands, but its
discrimination tier is dominated by two attention hooks.]

### 4.3 What travels and what doesn't
[v0.1 §5.5: LODO — discrimination transfers (AUC 0.78–0.87),
calibration does not (ECE 0.05–0.11); 200-item per-domain temperature
repair. Retained as the deployment procedure for every gate tier in
this paper.]

## 5. Regime II — a trained compactor: the axes cross, the gate goes blind

### 5.1 Compactor, historical protocol result, no-ship
Still-canonical per-layer Perceiver (50M params) trained at 1/40 the
published data scale against the frozen base; evaluated on the original
12-context protocol at matched retained budget. This frozen arm was not
rerun on the later reserved holdout, so the table is historical rather than
clean certification evidence. Aggregation axis: *worse* than
eviction (KL 0.263 vs 0.122; recurrence depth 4 collapses to 2.29 →
max_certified_depth = 0). Pointwise axis: *better* — silent needle loss
0.271 vs eviction's 0.583. The regimes trade axes at this scale.

### 5.2 Position-kernel collapse
Captured cross-attention is exactly positional: delta rows, entropy
0.000 across 1,000 items × 36 layers × 8 heads. The compactor never
left its position-dominated initialization — compaction here is strided
subsampling of [K;V] plus leakage smear, not content synthesis — the
kept set is exactly `round(k·(S−1)/1023)`, a uniform stride-≈3 lattice,
invariant across all heads and all items. This
(a) renames the regime honestly (subsampling, with true synthesis
untested at this scale); (b) explains the pointwise advantage
(subsampled latents smuggle partial content forward; deletion destroys
it); (c) explains the cross-reseed nesting of failure sets (§7);
(d) yields a certification diagnostic: **report compactor
cross-attention entropy; a near-zero value means the artifact is a
subsampler regardless of its loss curve** (ours hit KL 0.058 by step
300 while never routing content). We name the failure mode
position-kernel collapse, the compactor-side sibling of recurrent-gate
collapse.

### 5.3 The gate goes blind
Relabeling under the compactor and retraining the shadow gate: the A2
decomposition *flips* (embeddings 0.567 > features 0.537) but everything
lands at ~0.55 — statistically indistinguishable from a five-feature
surface logistic (0.564 [0.553, 0.575]). Engineered interference-
geometry features add nothing (0.568). The refreshed gate still
*calibrates* (ECE 0.0074) and rides the lower base rate to a nominal
operating point, but its marginal reduction is 22.5% at 86% of oracle's
budget: it is calibrated always-expand-lite, not a router. **The loss
did not become smaller-and-harder; it became internal.**

## 6. Reading the computation

### 6.1 Probes
All probes trained on GT16-protocol counterfactual labels, evicted-only
evaluation, doc-level splits, fixed capacity; fragility-ordering row
(Kendall τ vs the cross-reseed nesting) reported for every arm.

### 6.2 Results
| signal source | AUC [95% CI] | τ |
|---|---|---|
| surface features (floor) | 0.564 [0.553, 0.575] | — |
| + interference geometry | 0.568 [0.557, 0.579] | — |
| prompted self-check (1 fwd) | 0.638 [0.628, 0.649] | 0.20 |
| sink/retrieval-head monitor (2 hooks, 8 scalars) | 0.762 [0.753, 0.771] | — |
| per-head attention probe | 0.767 [0.758, 0.777] | 0.46 |
| residual linear, layer 30 | 0.819 [0.811, 0.827] | 0.45 |
| residual MLP (3 seeds) | 0.852 [0.844, 0.859] | 0.47 |
| stack | **0.854 [0.846, 0.862]** | **0.57** |

The layer curve is monotone through the last third of the stack (0.53
at L15 → 0.65 → 0.81 → peak L30): sufficiency estimation crystallizes
late. Aggregated attention statistics fail (best 0.536) while individual
late-layer heads reach 0.72 — including a cluster whose signal is
*anomalous sink mass*: under-attention to memory parks probability on
sink positions, turning the attention-sink phenomenon into a sensor.

### 6.3 The deployment ladder
Three rungs, each with its measured cost: the prompted self-check
(0.638; one extra forward, zero training — and already above every
corpus-side approach); the head monitor (0.762, end-to-end lost-fact 0.149 at expansion rate
0.060; two scalar hooks on one forward, no capture infrastructure —
and notably the prompted self-check adds nothing on top of it (0.763
combined): the model's verbalized self-report is subsumed by its own
attention behavior); the trained stack (0.854; capture + $3 of probe
training per capacity point).
The rung is regime-general: the same eight-scalar monitor, with the
memory region redefined as the surviving compacted span, predicts
eviction-regime loss at 0.783 [0.760, 0.808] — above the shadow gate's
own evicted-only discrimination (0.622) — and transfers zero-shot
between regimes (0.72–0.74 either direction), so
under-attention-to-memory is a cheap, compressor-independent
insufficiency sensor. End-to-end at natural prevalence, the stack-gated system reaches
lost-fact 0.146 at expansion rate **0.050** — the shadow gate's
correctness at one third of its budget — strictly inside its curve,
with oracle at 0/0.170. Per-capacity retraining is required (transfer
to t=512 drops 0.21, consistent with cross-capacity label κ 0.455);
per-domain temperature repair carries over from §4.3.

### 6.4 What the probe reads
A context-only control — the same compact context, no question, same
layer — drops to chance: a fresh probe reaches 0.502 [0.487, 0.518] and
the question-conditioned probe applied zero-shot reaches 0.508, against
0.813 with the question present. The probe is therefore a
**behavioral-divergence predictor** — it reads the model's answer-time
state, question included — and should not be interpreted as a readout
of memory contents. We regard this as confirmation rather than
deflation: our certification protocol *defines* sufficiency
counterfactually, as a relation over (query, memory) pairs, and the
control shows the model's internals agree — there is no
query-independent sufficiency signal to read, because sufficiency is
not a property the memory state has on its own. Scope: the null holds for linear *and* nonlinear (256-hidden MLP)
probes at every layer of a {10, 15, 20, 25, 30, 36} sweep and for a
concat-of-layers probe — max context-only AUC 0.508 vs 0.813 with the
question — so there is no query-free sufficiency signal to read at any
probed depth, not merely none linearly decodable at layer 30.

## 7. Fragility is a property of the fact, not the checkpoint
Cross-reseed relabeling: κ 0.745 with the weaker instance's failure set
nested inside the stronger's (P = 0.945) and protocol determinism
exactly 1.0 — loss follows an instance-independent fragility ordering
that better compactors peel from the top. Probe scores rank this
ordering (τ 0.57, CI excludes 0). Qualitatively, fragility concentrates
in key→value *binding* under confusable-sibling pressure — neighboring
table rows, near-identical identifiers, common-token values in crowded
neighborhoods — with token rarity mildly *inversely* predictive: what
dies is binding, not content.

## 8. Discussion

### 8.1 The routability ladder
One protocol, two regimes, three signal classes:

```text
eviction      loss follows visible mechanics   → shadow gate: −72% loss;
                                                   head monitor 0.78 too
subsampling   kernel geometry loss-blind        → shadows blind (0.55),
              (this work's "compactor")            kernel mechanics blind
                                                   (0.55); query-conditioned
                                                   computation-reading 0.85
                                                  → same loss at ⅓ budget
true synthesis                                  → untested at this scale
```

### 8.2 Is subsampling loss mechanics-routable after all?
No — and the test was as favorable as it could be made. The kernel is
fully known (the exact stride-3 lattice, item-invariant), yet
needle-to-nearest-kept-position distance predicts survival at 0.509
[0.499, 0.519], the mechanics-with-kernel gate adds +0.003 over the
surface floor (0.550 [0.537, 0.563]), and the residual-stream probe's
scores correlate with kernel distance at ρ = 0.045 — almost none of the
0.85 is kernel geometry. Because every span of three or more tokens
contains a lattice point, what varies is only the phase of the answer
tokens relative to the lattice, and phase carries no signal: survival
is decided by leakage smear and by how downstream layers use the
subsampled cache. The internality claim stands in full, with one
refinement from the context-only control: the loss is not merely
internal to the model — it is internal to the *query-conditioned*
computation. Write-side blind, question-free read-side blind; only the
encounter between the question and the memory carries the signal.

### 8.3 Consequences for memory-system design
Gate-mandatory is regime-independent; gate-*class* is regime-dependent.
Certification must include the probe: any retrained compactor gets its
divergence-predictability measured per instance and per capacity, its
cross-attention entropy reported, and — if the kernel is nontrivial —
the kernel-geometry test rerun (a full-recipe compactor that escapes
position-kernel collapse may make write-time geometry loss-bearing
again; ours did not). Multi-hop: content-aware *entry*
(per-query sufficiency score) beats per-block ranking (1.98× vs
2.15–2.33× oracle) — the binding constraint was never block scoring.

## 9. Limitations
Single 4B base; one tokenizer (fragility neighborhoods are partly
tokenizer artifacts); the compactor is 1/40-recipe and mechanistically
a subsampler — Regime II results characterize this artifact on its original
protocol, not clean held-out generalization or full-recipe synthesis;
extractive MCQ probes, letter-match equivalence,
greedy decoding, single-turn contexts; multi-hop k=2, one evicted
candidate per query; GT22 weighted at natural prevalence on the
captured sample; F1's needle features exclude the 22% of test items
without a locatable in-prefix answer; the context-only null covers linear and MLP probes across a six-layer
sweep and a concat-of-layers probe (max AUC 0.508); depths outside the
sweep and probe families beyond MLP are untested. F5's eviction-regime
monitor row is measured at f=0.40 only. Probe claims are per-capacity and
per-instance by measurement (§6.3, §7), and the probe predicts
behavioral divergence rather than certifying memory contents (§6.4).

## 10. Conclusion
Silent memory loss under compression is not one problem. Delete, and
the damage follows mechanics anyone can see; subsample-and-smear, and
the damage moves inside the model — and further in than that: it is not
stored in the memory state at all, but materializes in the encounter
between query and memory, where a linear probe on the residual stream
recovers what every external signal missed, for a third of the routing
budget. The practical statement
is a ladder — ask the model (free), watch two attention heads (cheap),
read the residual stream (small) — and the scientific one is that
*routability, not just fidelity, is a certifiable property of a
compression regime.* We think that is the property long-context memory
systems should be certifying next.

---

### Appendices
A. eval-protocol definitions & item partitions · B. baseline
reconciliations (A3-class, incl. 0.271-vs-0.189 protocol note) ·
C. decompositions + seeds/CIs · D. corpus construction · E. LODO &
recalibration · F. position-kernel collapse evidence (entropy tables,
loss-curve-vs-routing figure) · G. retrieval-head inventory ·
H. reproducibility & compute ledger (total ≈ $1,100 across
corpus/gate/compactor/probes) · I. FOLLOWUP results (F1–F3: kernel-lattice extraction, context-only control, sink-head monitor; verdicts and CIs).

### Figures
1. two-regime axis plot (aggregation × pointwise, both regimes +
control) · 2. routability bar chart (signal class × regime; incl. sink-head
monitor cells in BOTH regimes — 0.78 eviction / 0.76 subsampling — vs
mechanics 0.62 / 0.55) ·
3. deployment ladder cost/benefit · 4. layer curve · 5. end-to-end
cost/correctness plane (all gates + oracle) · 6. fragility nesting
diagram.

### Title alternatives
1. "Delete or Blur: Compression Regime Determines Where Memory Loss
   Can Be Predicted"
2. "The Loss Moved Inside: Routing Around Compressed-Memory Failure by
   Reading the Residual Stream"
3. "Routability Is a Certifiable Property of Memory Compression"
