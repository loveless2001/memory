# memsub — Unified Memory Substrate for Long-Context LLM Threads

> **CLEAN E1FULL RESULT (2026-07-21): NO-SHIP.** The replacement n=60
> certification reserves 15 documents/domain before training and records zero
> document/item overlap. Depth-1 improves silent fact loss but has worse
> aggregation KL than matched eviction (+0.0495, 95% CI [0.0272, 0.0715]);
> `max_certified_depth = 0`. Clean policy:
> `still-compact-v1:t1024:depth0:sha256:c00b2437fdd813cc`.

A runtime for long-lived LLM conversation threads that keeps recent context
exact, compresses older context, persists it to disk, and expands it back
when the compressed form turns out to be insufficient — plus the
certification machinery to say *when* that expansion is necessary.

Everything here runs against a **frozen** Qwen3-4B base: no backbone
training, ever. What gets trained is the compaction policy and the decision
layer that routes around its losses.

- Design of record: `unified_memory_substrate_spec_v0.3.7.md`
- Build scope for the MVP: `BUILD.md`
- Architecture and module map: `docs/system-architecture.md`
- Dated history: `docs/project-changelog.md`

---

## The story so far

The project started as an engineering build and turned into a research
program when a compressor everyone assumed was working turned out not to be.

### 1. The substrate (M0–M2)

A three-layer memory: durable text + provenance (the only tier that
survives a model or tokenizer change), a compressed KV tier, and an exact
raw archive to expand from. The load-bearing trick is that compaction
decouples a token's **logical** position (what RoPE sees) from its
**physical** slot (what the attention mask sees), so a compacted cache can
be continued, checkpointed, and resumed without the model noticing the
holes. Golden tests GT1–GT5 cover identity round-trips, sink pinning,
fingerprint gating, certification, and redaction propagation.

### 2. Measuring the damage (M1 + B.3 corpus)

To certify a compressor you need to know what it silently breaks. We built
a 98,355-item counterfactually filtered MCQ corpus over four domains
(finance, law, code, literature; ~1B tokens) and a certification protocol
with a rule that turned out to matter enormously: **the two axes are never
blended.** *Aggregation* (does the model still reason well over what
survived) and *pointwise* (did a specific fact silently die) behave
oppositely under every compressor we tested. Contiguous eviction leaves
aggregation nearly untouched while silently losing 55–65% of previously
known facts.

### 3. Routing around the loss (M3 gate, M3.5 compactor)

If loss is unavoidable, predict it and expand exactly those blocks. A
~$140 dual-encoder gate over text shadows cuts silent loss **72%** under
eviction — it works because eviction loss is *mechanical* (did the span get
deleted). We then trained a Still-class amortized compactor to replace
eviction. It failed certification (GT13 no-ship) but halved needle loss,
and under it the gate's value collapsed to 22.5%: synthesis loss is
content-bound, not mechanical. That asymmetry became paper #1,
*Reading the Computation*.

### 4. Reading the computation (PREPROBE → PROBE → FOLLOWUP)

If the text shadow can't predict synthesis loss, can the model's own
activations? Yes: a hidden-state probe reads behavioral divergence at
**0.854 AUC** where surface features sit at 0.564. Two controls kept the
claim honest — strip the question and the signal vanishes (so it predicts
*divergence*, not memory contents), and a 2-hook, 8-scalar "sink-head
monitor" recovers most of it at almost no cost.

That work also surfaced something odd: the trained compactor's
cross-attention was a **delta position kernel** — attention entropy exactly
zero, one source position per latent. It wasn't synthesizing. It was
keeping every third token.

### 5. Is it just scale? (FULLRECIPE — no)

The obvious explanation was undertraining. So we completed the training
corpus (76k rationale-traced items) and trained at full recipe. The kernel
did not move — **bitwise identical to its initialization**, at every
checkpoint, at every data scale, while the loss fell normally from 0.58 to
0.36. Certified aggregation KL was 0.2529 at 1/40 scale and 0.2820 at full
recipe (60-document protocol): an 8× data increase did not improve the
certified number at all.

The same campaign found a real bug: the multi-GPU trainer had been calling
the model inside the DDP wrapper's `.module`, so **gradients were never
synchronized** across the 8 workers. Every earlier checkpoint was a
single-replica, batch-4 artifact. Behavioral measurements were unaffected
(they measure the artifacts as they exist); the training-scale attribution
in paper #1 needed a correction note.

### 6. Why it was frozen, and the one-constant cure (ESCAPE)

Gradient forensics at initialization, one forward/backward: under the
canonical attention logit scale (×256), the routing projections receive
gradients of **1.1e-11 and 1.6e-10** while the value pathway sits at 17–22.
Eleven to twelve orders of magnitude, exactly along the routing/value cut.
The identity initialization makes attention rows near-one-hot; multiplied
by 256, the softmax saturates and passes ~zero gradient to its own logits.
The compactor could only ever learn *what to write into fixed slots*, never
*where to look*.

Changing that one constant to √256 = 16 wakes the dead groups by ~10¹⁰. The
kernel then moves, all eight KV-heads specialize differently, and the
unfrozen compactor **beats the frozen one on the objective that froze it**
(loss 0.219 vs 0.365) while losing 35% fewer facts. Controls rule out the
alternatives: init-time noise doesn't escape (not a tie-breaking problem),
and content-seeded initialization stays flat (content can't substitute for
gradient).

### 7. The full-scale rematch (E1FULL)

The original n=60 certification was invalid: 52 of 60 evaluation documents
and 207 of 241 probes appeared in full-recipe training. The replacement run
reserved 60 documents before constructing a balanced 94,056-item manifest,
trained a new 3,000-step checkpoint, and certified 193 held-out probes with
zero document or item overlap.

The clean result is **GT13 NO-SHIP**. Depth-1 reduces lost-fact incidence from
0.683 to 0.106 and lost-given-prior-correct from 0.631 to 0.050 versus matched
eviction, but worsens aggregation KL from 0.0787 to 0.1281. The paired KL gap
is +0.0495 [0.0272, 0.0715], so the primary distributional predicate fails;
the accuracy advantage is uncertain (+0.0522 [-0.0395, 0.1461]). Untrained
depth-4 recurrence collapses. Runtime depth therefore remains zero.

### The transferable lesson

A loss curve fell for 1,500 steps at every data scale while the one thing
compaction is *for* was frozen from step zero. Two checks, minutes each,
catch it: **per-group gradient norms at init**, and **cross-attention
entropy telemetry during training**. Both are now mandatory in the
certification protocol (spec v0.3.7 §13.4), and they're worth running on
any Perceiver-style compressor, any resampler with sharpened attention, and
any architecture combining identity-style init with a large logit scale.

---

## Repository layout

```
memsub/                 the substrate: store, archive, runtime, compaction,
                        certification, checkpoints, gate/, compactor/
tests/                  golden tests (GT1–GT5, GT11) + unit suites
modal-runners/          GPU campaign harnesses (training, capture, probes,
                        certification) — research code, not runtime
paper/                  paper #1 "Reading the Computation" (LaTeX, tectonic)
paper2/                 paper #2 "The Compactor That Couldn't Learn Where to Look"
docs/                   architecture, changelog, paper drafts, arXiv v2 note
plans/                  per-campaign plans + reports
*.md (root)             campaign briefs and their reports (see below)
```

**Campaign briefs → reports** (each brief is the pre-registered scope; each
report carries verdicts in the brief's own vocabulary):

| brief | report | verdict in one line |
|---|---|---|
| `GATE.md` | `plans/reports/gate-*` + `ABLATION.md` | gate works under eviction; it's a mechanics classifier |
| `COMPACTOR.md` | `ADDENDUM-M35.md` | GT13 no-ship; synthesis halves needle loss |
| `PREPROBE.md` | `PREPROBE-REPORT.md` | fragility is content-structured |
| `PROBE.md` | `PROBE-REPORT.md` | sufficiency readable from the computation (0.854) |
| `FOLLOWUP.md` / `FOLLOWUP2.md` | matching `*-REPORT.md` | geometry loss-blind; context-only null; sink-heads regime-general |
| `FULLRECIPE.md` | `FULLRECIPE-REPORT.md` | collapse is not a scale artifact |
| `ESCAPE.md` | `ESCAPE-REPORT.md` | saturation confirmed; √d_l escapes |
| `E1FULL.md` | `E1FULL-REPORT.md` | clean held-out GT13 no-ship; depth 0 |

## Running things

```bash
# local suite (tiny random Qwen3-config model on CPU — exercises all logic)
uv run pytest tests/ -q

# reference suite on an H100 (the laptop cannot hold a 4B model)
modal run modal-runners/modal-reference-golden-test-runner.py::run_golden_tests

# papers
cd paper2 && tectonic main.tex        # tectonic, not pdflatex
```

Artifacts (corpora, checkpoints, labels, probe captures, telemetry) live in
the `memsub-artifacts` Modal volume; `memsub-hf-cache` holds model weights.

**Two gotchas worth knowing before you touch a checkpoint:**

1. **E1-class checkpoints deploy at logit scale √d_l = 16.** Every harness
   takes `--lever e1_sqrt_scale`. Load one at the canonical scale and its
   routing silently changes.
2. **Labels, gates, and probes are compaction-policy-scoped.** A new policy
   invalidates them along with the caches — the best probe layer alone
   drifted 30 → 25 → 33 across three policies.

## Cost

Before the clean remediation run, roughly $2,100 of rented H100 time had been
recorded end to end: corpus construction ≈ $500,
gate + labels ≈ $110, M3.5 compactor ≈ $715, probe campaigns ≈ $175,
FULLRECIPE ≈ $440, ESCAPE ≈ $95, E1FULL ≈ $435.

## Status

M0–M3.5 built and measured (n=60 documents, paired CIs); two papers
drafted. The clean unfrozen compactor is a research artifact, not an L3 policy:
GT13 fails and the default remains evict-oldest-nonsink. Not started: the absorption
measurement study (spec §16.4), recurrence-depth training beyond depth 1,
serving/vLLM integration, and any HTTP surface.
