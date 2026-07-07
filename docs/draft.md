# One Cache, Two Workloads: Certifying KV Compression Along Pointwise and Aggregative Axes, with a Calibrated Expansion Gate

**Draft v0.1 — 2026-07-07.** Working title; alternatives at end. Markdown master; convert to LaTeX after numbers freeze.

> **FILL-IN LEDGER (for Claude Code, from the ABLATION.md addendum artifacts):**
> every ⟨…⟩ token below maps to a field in the updated `eval-grid.json` /
> ADDENDUM.md. Numbers quoted without brackets are from the 2026-07-07 M3
> report and survive the addendum unchanged unless the ledger says otherwise.
> ⟨A1-AUC⟩ evicted-only test AUC · ⟨A1-PR⟩ evicted-only PR-AUC ·
> ⟨A2-verdict⟩ one of {content | mechanics | complementary} + the three-row
> table · ⟨A3-never⟩ canonical never-expand per fraction under the M3
> protocol · ⟨A4-CI⟩ 95% bootstrap CIs + seed SDs for every headline number ·
> §5.2 contains three pre-drafted mechanism paragraphs — keep exactly one
> per ⟨A2-verdict⟩ and delete the other two.

---

## Abstract

"Long context" conflates a serving problem — fitting the tokens — with two
capability problems that separate the moment full attention becomes
unaffordable: *pointwise* recall of exact, low-redundancy facts, and
*aggregative* understanding of distributed, redundant content. We argue these
are antagonistic optimization targets under any lossy cache compression, and
we introduce a certification protocol that scores the two axes separately and
forbids blending them. Applying the protocol to untrained KV eviction on
Qwen3-4B over a ~1B-token, four-domain corpus of 98,355 counterfactually
filtered questions, we find the axes split almost completely: next-token KL
against the full-context teacher stays near 3×10⁻² while
⟨A3-never⟩ of facts residing in evicted spans are silently lost (measurement
noise floor: 0.000). We then show the pointwise axis can be restored by a
*decoupled sufficiency gate*: a dual encoder over frozen sentence embeddings,
trained on counterfactual sufficiency labels produced by the frozen base
model, that decides per query whether compressed memory suffices or exact
re-expansion is required. The gate is natively calibrated (test ECE
0.017–0.023), strictly dominates a query-type-routing baseline at every
matched expansion rate, and at its chosen operating point cuts silent loss
from ⟨A3-never⟩ to 0.143 ⟨A4-CI⟩ while expanding on only 16.9% of queries
(oracle: 19.4%). Two further findings refine the picture: on multi-hop
questions the two-workload weakness appears on the *cost* axis rather than
the correctness axis — the gate protects correctness by over-expanding 2.3×
oracle — and gate *discrimination* transfers to held-out domains
(AUC 0.78–0.87) while *calibration* does not (ECE degrades to 0.05–0.11),
making per-domain recalibration part of the definition of a deployable gate.
Total marginal cost of the gate experiment was ≈ $140 of rented compute.

## 1. Introduction

Benchmarks, methods papers, and product claims routinely report a single
"long-context" score. This paper's starting point is that no such single
number can be coherent once the context no longer fits in exact form. A
needle-class query — an identifier, a figure, a verbatim clause — concentrates
its answer in exact bytes with near-zero redundancy against the surrounding
context; any lossy transform destroys it at a rate proportional to the
compression ratio, and the optimal mechanism for it is selection, indexing,
and exact lookup. An integration-class query — summarization, theme tracking,
most document reasoning — lives on distributed, redundant information; it is
compression-tolerant and often mildly compression-benefited. The two are not
merely different but antagonistic: compression bought for the aggregative
workload is paid for in pointwise fidelity, and exact retention kept for
needles is memory that compression was meant to free.

If the antagonism is real, three things follow. Evaluation must report the
two axes separately, because a blended score lets a method win the aggregate
while being needle-dead. Compressed-memory systems need a *routed two-path
architecture* — a lossy tier for aggregation and a lossless raw path for
pointwise traffic — rather than a single representation with a quality knob.
And the router itself becomes the critical learned component: a calibrated,
per-query estimate of whether the compressed representation suffices.

We contribute, in order: **(i)** a two-axis certification protocol for
compressed LLM memory, with counterfactually filtered probes such that a
correct answer proves the information flowed through the (compressed) cache;
**(ii)** a measurement at ~1B-token scale across four document domains
showing the axes split under untrained KV eviction — aggregative fidelity
essentially intact, pointwise fidelity collapsing, the gap widening with
eviction fraction; **(iii)** a decoupled sufficiency gate — trained entirely
outside the frozen base model for ≈ $140 — that restores the pointwise axis
at a fifth of the always-expand cost, with calibration good enough to expose
as a probability; **(iv)** two phenomena we believe are documented here for
the first time: the multi-hop *cost overhang*, where a well-calibrated
single-hop gate protects multi-hop correctness only by systematically
over-expanding, and *calibration non-transfer*, where discrimination
generalizes across domains but calibrated probabilities do not.

## 2. Related work

*KV-cache reduction.* Per-context selection scores tokens at inference and
evicts the rest (H2O, SnapKV, StreamingLLM); amortized selection learns the
scorer (KV-Distill); per-context and amortized synthesis write new compact
entries rather than keeping original rows (Attention Matching; Still), and
architecture-level lines bake reduction into the model (MLA, native sparse
attention). Our work is orthogonal to the choice of compressor: we certify
compressors along two axes and supply the decision layer their lossiness
requires. Notably, the strongest published synthesis results themselves show
the axis split we formalize — near-full aggregative utility with
needle-retrieval collapse — which we take as independent evidence for the
two-workload framing. *(verify all citations against primaries before
submission; drafted from working notes)*

*Selective prediction and abstention.* The gate is a selective-prediction
head over an external memory: it estimates, per query, whether the model's
conditioning state supports the answer. It is related to answerability and
abstention heads in retrieval-augmented settings, with two differences: the
label is *counterfactual* (answers under compressed vs. raw conditioning are
compared, rather than correctness being judged in isolation), and the head is
trained fully decoupled from the backbone, using the backbone only offline as
a teacher — an amortization move analogous to learned retrieval indexers in
sparse-attention serving systems.

*Memory-augmented agents.* OS-style memory hierarchies (MemGPT-class) page
text in and out of context but do not certify fidelity or route by workload;
our protocol and gate are directly applicable to such systems.

## 3. Two axes and a certification protocol

**Definitions.** Fix a base model f, a compression policy C, and a corpus of
(context, question, answer) items where each question is generated from a
specific source span. An item is *counterfactually valid* if f answers it
correctly with the context and incorrectly without it — so a correct answer
under compression proves the information traversed the compressed cache. The
**aggregation axis** is measured over integrative behavior: next-token KL
between f conditioned on the full cache and f conditioned on C(cache), plus
answer-accuracy deltas on items whose source spans survive compression. The
**pointwise axis** is the *lost-fact incident rate*: among counterfactually
valid items whose source span was compressed away, the fraction answered
incorrectly *without* any expansion mechanism — the silent-failure rate.

**Protocol.** A configuration is certified per axis, never as a blend; the
noise floor is established by running the identical probe battery at zero
compression; and a configuration certified only on the aggregation axis may
ship only behind an active, calibrated expansion gate for pointwise traffic.
The last clause converts the antagonism from an observation into a deployment
rule.

## 4. The axes split: measurement at 1B-token scale

**Setup.** Base model Qwen3-4B-Instruct-2507 (bf16, greedy, pinned runtime
fingerprint). Corpus: 40,000 long documents across financial filings (238M
tokens), literature (416M), case law (119M), and source code (154M);
98,355 extractive multiple-choice items generated by the base model from
random ~1k-token sub-chunks, teacher-verified answerable with context and
discarded if answerable without (98.4% of the 100k target; code has the
lowest filter survival). Equivalence is answer-letter exact match; a manual
audit of pointwise failures found 0% format noise. Compression policy:
evict-oldest-non-sink at fractions 0.25 and 0.40, with the first four
positions pinned as attention sinks. Contexts are 4096-token per-item
prefills with item placement randomized by hash, giving natural exposure to
eviction.

**Result.** The zero-eviction control gives a lost-fact noise floor of
0.000. Under eviction, the aggregation axis barely moves — mean KL 0.0303
(0.25) and 0.0339 (0.40) against the full-context teacher, answer deltas on
surviving-span items ≈ 0 — while the pointwise axis collapses: ⟨A3-never⟩
of facts in evicted spans are silently lost, worsening with fraction
⟨A4-CI⟩. The residual recoverable fraction is consistent with the summary
path carrying a minority of needles forward (surviving representations were
computed while the evicted span was still present). One artifact, two
workloads, opposite outcomes.

*(A3 note: an earlier certification pass under packed multi-item contexts
gave 0.708/0.808; the canonical numbers above are re-stated under the
per-item protocol used throughout this paper, with the reconciliation in
Appendix ⟨A3⟩.)*

## 5. A decoupled sufficiency gate

### 5.1 Labels, model, calibration

For each of the 98,355 items and each eviction fraction we produce a
counterfactual sufficiency label: y = 1 iff the answer under the compacted
cache differs from the answer under the raw span (196,710 rows; items whose
source span survived eviction enter as natural y = 0 rows). Splits are
grouped by source document, domain-stratified, with an additional
leave-one-domain-out rotation. The gate is a dual encoder over frozen
Qwen3-Embedding-0.6B — the same embedding model that produces the memory
blocks' retrieval shadows — with a 256-d normalized projection interaction,
a small feature head (eviction fraction, query–block overlap, evicted flag,
domain), and an auxiliary query-workload head. A frozen-embedder linear
probe sufficed. Per-fraction temperature search returned T = 1.0 for both
fractions: the probe is natively calibrated, with test ECE 0.023 (0.25) and
0.017 (0.40). Marginal cost of the entire gate experiment — labels,
training, evaluation, figures — was ≈ $140.

### 5.2 What the gate learned

⟨A2-verdict: keep exactly one of the following three paragraphs.⟩

⟨IF content⟩ Restricting evaluation to evicted-span rows — removing the
near-deterministic evicted-vs-survived separation from the task — the gate
retains AUC ⟨A1-AUC⟩ (PR-AUC ⟨A1-PR⟩), and the embeddings-only ablation
matches the full model within seed noise while the features-only ablation
falls to ⟨A2-feat-AUC⟩. The signal is content: the gate reads, from the
query and the block's shadow, whether this particular fact class survives
this compressor.

⟨IF mechanics⟩ Restricting evaluation to evicted-span rows, the full model
reaches AUC ⟨A1-AUC⟩ — but the features-only ablation reaches ⟨A2-feat-AUC⟩,
within seed noise of the full model, while embeddings-only falls to
⟨A2-emb-AUC⟩. The learned signal is predominantly eviction mechanics
(fraction, overlap, position), not content semantics; this also explains
the near-tie between document-level and item-level splits (there is little
content signal for item leakage to exploit). We therefore describe the gate
as a calibrated mechanics classifier and treat content-aware sufficiency as
open headroom.

⟨IF complementary⟩ Restricting evaluation to evicted-span rows, the full
model reaches AUC ⟨A1-AUC⟩, with features-only at ⟨A2-feat-AUC⟩ and
embeddings-only at ⟨A2-emb-AUC⟩ — both materially below the full model. The
signal decomposes: eviction mechanics carry the base rate, content
embeddings decide the hard cases, and the combination is what clears the
routing baseline in §5.3.

### 5.3 Operating point and baselines

At the operating threshold τ = 0.488 (chosen on the calibration split), the
gate reaches test lost-fact 0.143 ⟨A4-CI⟩ at expansion rate 0.169, against
never-expand ⟨A3-never⟩, always-expand at rate 1.0, and the oracle at 0.000
loss / 0.194 rate. Against the interpretable baseline — classify the query
as pointwise vs. aggregative and expand iff pointwise — the gate strictly
dominates at every matched expansion rate from 0.1 to 0.5 (lost-fact
0.277 / 0.092 / 0.000 / 0.000 / 0.000 vs. 0.470 / 0.416 / 0.368 / 0.308 /
0.248). The full cost–correctness plane is Figure 1; the gate's curve lies
inside the routing baseline everywhere and reaches ≈ 0 loss at ~0.30
expansion rate.

### 5.4 Multi-hop: the weakness moves to the cost axis

On a 500-item slice of teacher-filtered two-fact questions composed within
single documents, the gate at the single-hop threshold *holds correctness* —
lost-fact 0.036 vs. 0.376 never-expand — but does so by over-expanding:
recall 0.904 at precision 0.388, expansion rate 0.438 against an oracle of
0.188 (2.3×). The predicted mid-spectrum weakness of retrieval-then-
integration queries is real, but it lands on cost, not correctness: a
calibrated single-hop gate defends multi-hop questions by firing too often.
This cleanly scopes the next component — a selector that scores block *sets*
so a multi-hop query triggers one grouped expansion — and gives it a
quantitative target (recover ~2.3× → ~1× oracle cost at held recall).

### 5.5 Calibration does not transfer; discrimination does

Under leave-one-domain-out evaluation the gate's discrimination holds
(AUC 0.781–0.865, near-zero lost-fact at ~0.26 expansion), but calibration
degrades to ECE 0.05–0.11. Fitting a single scalar temperature on ~200
labeled items from the new domain restores ECE ≤ 0.05 in every rotation.
The practical statement: a "calibrated gate" is not a checkpoint but a
checkpoint plus a per-domain recalibration procedure, and deployment to a
new domain carries a small, explicit labeling cost.

## 6. Limitations

Single base model and scale (4B); one compression regime (untrained
eviction — trained synthesis compressors will shift the aggregation axis
but published results indicate they do not rescue the pointwise axis, which
is the case our protocol and gate address); extractive MCQ probes with a
letter-match equivalence function rather than open-ended generation; greedy
decoding; per-item single-turn contexts rather than multi-turn threads;
multi-hop limited to k = 2 within-document composition. The two-axis
protocol itself is compressor-agnostic and model-agnostic; the specific
numbers are not.

## 7. Conclusion

Single-number long-context evaluation is incoherent under compression: the
pointwise and aggregative axes are antagonistic, and at 1B-token scale they
split almost completely. The resolution is architectural — a lossy tier for
aggregation, a lossless path for needles, and a router between them — and
the router turns out to be cheap: a $140 decoupled probe over frozen
embeddings, natively calibrated, dominating query-type routing, and
recovering the pointwise axis at a fifth of always-expand cost. What does
not come for free is exactly what the measurements localize: multi-hop
queries expose a cost overhang that calls for set-level selection, and
calibration is a per-domain property requiring a recalibration procedure.
Both are precise targets rather than open mysteries, which is where we
think a memory system's decision layer ought to leave its next iteration.

---

### Appendices (to assemble from artifacts)
A. Eval-protocol appendix (V1): item partitions per axis, probing
   conditions, sampling parameters. B. Baseline reconciliation (A3).
C. Signal decomposition full table (A2) + seed SDs (A4). D. Corpus
   construction and filter-survival statistics. E. Recalibration procedure
   and LODO tables. F. Reproducibility: fingerprint record, pinned
   versions, compute ledger (corpus ≈ $500, labels ≈ $110, gate ≈ $30).

### Title alternatives
1. "Expand When It Matters: A Calibrated Sufficiency Gate for Compressed
   LLM Memory"
2. "Needles Don't Compress: Two-Axis Certification for Lossy LLM Memory"
3. "The Pointwise–Aggregative Split: Measuring and Routing Around the
   Antagonism in Compressed Long Context"