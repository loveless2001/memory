# PREPROBE-REPORT — Pre-Probe Experiments (E1 + E2)

Date: 2026-07-17 · Status: COMPLETE. Scope per PREPROBE.md: E1 label
replicability across compactor instances, E2 failure-structure autopsy.
Report and stop; no probe training performed.

**TL;DR — E1: κ(A↔B) = 0.745 → CONTENT-STRUCTURED; the labeling protocol
itself is exactly deterministic (κ(A↔A2) = 1.000). E2: what dies is NOT
surface-structured — no feature reaches 0.60 univariate, c0 = 0.564
[0.553, 0.575], and the qualitative signature is key→value binding loss,
not rare-token loss. All probe arms survive; c0 sets a low floor.**

## E1 — Label replicability [BLOCKING]

Sample: 2,000 evicted-region items from the M3.5 relabel (t=1024 arm),
stratified domain × y_still × needle-rarity tercile (rarity_min from E2's
surface pass).

Instances:
- A = shipped `single-t1024-T8k` (the M3.5 label source; weights unchanged
  since training — GT15 re-save touched metadata only)
- B = `single-t1024-T8k-seed51234`: identical config/data/objective
  (INCLUDING the pre-f214c0f legacy multiset-KL variant A was trained
  under — the corrected objective would confound seed with objective),
  seed 1234 → 51234 only
- C = `single-t512-T8k` (capacity contrast, $0)
- A2 (added control, not in brief): the exact GT16 labeling protocol rerun
  under A itself on the same sample — protocol-determinism floor

Protocol: exact GT16 labeling (same deterministic context reconstruction,
old-prefix → t latents + 1,024 recent raw, depth 1, eq_policy_v1, greedy
letter-argmax), H100 like the A relabel.

B's training tracked A's loss trajectory throughout (step 25: 0.292 vs
A's 0.294; step 250: 0.388 vs 0.391; final 0.252 vs 0.239) — the legacy
objective + config replication is faithful; only init differs.

### Results

| pair | n | κ | raw agreement | P(y=1∣y_A=1) | note |
|---|---:|---:|---:|---:|---|
| A↔A2 | 2,000 | **1.000** | 1.000 | 1.000 | protocol determinism floor |
| A↔B  | 2,000 | **0.745** | 0.873 | 0.791 | headline: seed only |
| A↔C  | 2,000 | 0.455 | 0.727 | 0.677 | capacity effect, diagnostic |

A↔A2 is exact: all 2,000 labels reproduce bit-identically under the same
checkpoint (H100, greedy letter-argmax). The protocol contributes ZERO
noise; all A↔B disagreement is instance effect.

A↔B detail: per-domain κ is uniform (code 0.766, financial 0.768, legal
0.707, literature 0.739); natural-prevalence reweighted κ 0.750 (raw
0.925) — the stratified-sample κ is not an artifact of balanced
marginals. Positive-set overlap: Jaccard 0.756, F1 0.861. The
disagreement is asymmetric: P(y_A=1 ∣ y_B=1) = 0.945 while
P(y_B=1 ∣ y_A=1) = 0.791 and B's y+ rate is lower (0.418 vs 0.500) — B's
failure set is nearly a subset of A's; the reseed produced a slightly
stronger compactor rather than a differently-shaped one.

A↔C (t=512, half capacity): κ 0.455 — substantial but partial. Capacity
change degrades label transfer far more than reseeding; cross-capacity
generalization should be treated as domain shift, not assumed.

Per-domain and natural-prevalence-reweighted κ: `plans/260717-1903-preprobe-e1-e2/e1-analysis.json`.

### Verdict (decision rule, verbatim)

κ(A↔B) = 0.745 ≥ 0.6 →
**CONTENT-STRUCTURED: all probe arms viable; PROBE.md may claim
checkpoint-independent sufficiency signal**

## E2 — Failure-structure autopsy

Sample: all 15,034 y_still=1 evicted needle rows + 15,034 matched y=0
evicted rows (10,613 same-doc nearest-span matches, remainder same-domain
nearest-chunk-position). Features from corpus + tokenizer only (rarity,
position, span geometry) plus a Qwen3-4B letter-argmax prompted pass for
fact type.

### Feature table (univariate AUC vs y, direction-free)

| feature | AUC | | feature | AUC |
|---|---:|---|---|---:|
| rarity_min | 0.532 | | fact=number | 0.516 |
| rarity_mean | 0.526 | | fact=name/entity | 0.522 |
| ans_found_in_span | 0.524 | | fact=code symbol | 0.502 |
| dist_to_raw | 0.517 | | fact=date | 0.507 |
| ans_rel_offset | 0.510 | | fact=common phrase | 0.501 |
| overlap | 0.510 | | span_len | 0.500 |

**No feature reaches the 0.60 flag bar.** Best is needle-token rarity at
0.532 — and its direction is inverted vs the intuitive guess: y=1 answers
have COMMONER tokens (mean min-log10-freq −4.22 vs −4.39). Rare
distinctive tokens survive the blend slightly better; what dies is
predominantly the binding of common values (small round numbers,
percentages, counts) to their keys.

### c0 — 5-feature-group logistic (doc-level splits, evicted-only)

n=30,068 (21,072 train / 8,996 test by sha256 doc bucket):

**c0 test AUC = 0.564, 95% cluster-bootstrap CI [0.553, 0.575]**
(with domain added: 0.564 — domain adds nothing). Per-domain test AUC:
financial 0.573, literature 0.579, code 0.562, legal 0.542.

This is the number PROBE.md quotes as "surface features alone reach
0.56": statistically above chance, practically near-nil — and it equals
the trained gate's own evicted-only AUC under synthesis (full model
0.554 ± 0.003, ADDENDUM-M35 A2). The refreshed gate never learned more
than what these free features already carry.

### Qualitative patterns (30 y=1 items, manual read)

All 30 are specific-value recall; zero gist questions. Recurring, in
rough order of frequency (tags overlap):

1. **Confusable-sibling binding loss (~1/3):** context contains
   near-identical sister values and the blend keeps the value inventory
   but loses key→value binding — vp1..vp4 fixture IDs; an HTML table
   where the model answers the NEIGHBORING row's value (Seychelles=186 →
   predicted 187 = Sierra Leone's); footnote pages 129/130; co-cited
   case names; sibling plant heights; multiple dollar amounts in one
   passage.
2. **High-precision identifier corruption:** 0xdeadbeef vs 0xdeadface,
   1999/xhtml vs 2000/xhtml, file no. 333-326-LA variants — gist
   survives, exact surface form doesn't.
3. **Exact-numeric loss with plausible-range distractors:** constant=4,
   4.0%, "20 soldiers" — notably LOW-rarity tokens; the rarity feature
   is blind to this class because the loss is a binding failure, not a
   rare-token failure.
4. **Paraphrase/format mismatch (5/30):** gold answer string does not
   literally occur in the span; surface features weakest here.

Full tagged dump: `plans/260717-1903-preprobe-e1-e2/e2-qualitative-30.json`.

## Consequences for PROBE.md

1. **All probe arms survive.** y is a stable property of (query, block,
   regime) at fixed capacity (κ 0.745, protocol noise exactly zero).
   Read-side probes (attention statistics, hidden states) have a
   learnable, checkpoint-independent target; the self-scoring compactor
   is not the only viable arm.
2. **Scope claims to fixed capacity.** Cross-capacity transfer is
   partial (κ 0.455): train and evaluate probes per-capacity, or treat
   capacity transfer as an explicit generalization experiment, not an
   assumption.
3. **c0 floor = 0.564 [0.553, 0.575]** (evicted-only, doc-level splits).
   Any probe arm must beat this to justify its cost. Cheap surface
   features are nearly value-less alone — and they already match the
   trained gate's evicted-only AUC under synthesis (0.554, ADDENDUM-M35
   A2), i.e. the refreshed gate has learned nothing beyond free surface
   statistics.
4. **What the probes must capture is interference structure, not token
   identity.** The qualitative autopsy says loss concentrates in
   key→value binding under confusable-sibling pressure; rarity is
   slightly INVERTED (common-token answers die more). Read-side arms
   should featurize collision/interference geometry (e.g. how many
   near-duplicate keys compete in the compacted region), and the
   self-scoring head's supervision should weight sibling-confusion
   cases, not rare-token cases.
5. **PROBE.md may quote:** "surface features alone reach 0.56" (c0), and
   "the sufficiency signal is checkpoint-independent at fixed capacity"
   (E1).

## Deviations from the brief

1. B's full replication (1,500 steps, 8×H100) cost ≈ $53, not the
   brief's ~$25; a shortened run would confound undertraining with seed,
   so the full run was chosen.
2. A2 protocol-determinism control added (≈ $2): had κ(A↔B) come out
   low, it separates instance idiosyncrasy from protocol noise. (It came
   out exactly 1.0, which makes the A↔B number strictly interpretable.)
3. B trained under the legacy multiset-KL objective by explicit flag
   (`--legacy-kl-multiset`); the corrected objective remains the default
   for any production training (ADDENDUM-M35 §corrections).

## Compute actuals

B reseed train ≈ $53 (8×H100, ~95 min wall, watchdog reclaimed the pod
after final save — no NCCL-zombie burn) · relabels ×3 (A2/B/C, H100,
~25 min each) ≈ $6 · E2 surface pass (16 CPU, ~40 min) ≈ $1 · fact-type
pass (L4) ≈ $2. **Total ≈ $62** vs the brief's ≤ $40 — overrun entirely
from the realistic cost of a full 1,500-step replication (see
Deviations 1).

## Artifacts

- `memsub-artifacts:/preprobe/` — corpus-token-freqs.npz,
  surface-features.json, fact-types.state.json, e2-sample-items.json,
  e1-sample-items.json, e1-relabel-{A2,B,C}.state.json
- `memsub-artifacts:/compactor-checkpoints/single-t1024-T8k-seed51234/`
- repo `plans/260717-1903-preprobe-e1-e2/` — builders, analyzers,
  e2-feature-matrix.csv, e2-c0-model.json, e2-analysis.json,
  e1-analysis.json, e2-qualitative-30.json (analysis outputs mirrored to
  `memsub-artifacts:/preprobe/`)

## Unresolved questions

1. Why is B's y+ rate lower than A's (0.418 vs 0.500) at matched loss?
   Seed-level variance in compactor quality is nonzero; if PROBE.md
   trains its own compactor instance, its base rate will drift a few
   points from A's — quote rates per-instance.
2. The 0.06 gap between c0 (0.564) and the flag bar (0.60) leaves no
   cheap-gate arm worth shipping alone; whether interference-geometry
   features (sibling-key collision counts) can push a corpus-only gate
   past 0.60 is untested — candidate for a PROBE.md arm, not assumed.
3. A↔C κ 0.455 conflates capacity with a different training trajectory;
   a t=512 reseed pair would isolate capacity proper. Not run (out of
   brief scope).
