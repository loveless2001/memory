# Certification Eval-Protocol Appendix (makes the B.3 numbers citable)

Date: 2026-07-07 · Applies to: `corpus-certification-full/*` (regenerated with
protocol-bearing report objects) · Supersedes the denominator-ambiguous table
in corpus-260707-0907-full-scale-b3-run-final-report.md.

## Protocol (now embedded verbatim in every report object as `eval_protocol`)

- **Pointwise denominator**: needle items whose SOURCE CHUNK start lies inside
  a fixed reference window (the 0.25-fraction contiguous window anchored at
  the first item's chunk). Max 8/context. The SAME partition is used across
  every arm (control, 0.25, 0.40, random) — `prior_correct = 21/25` needles
  in all four arms confirms it.
- **Aggregation denominator**: a disjoint set of up to 8 same-document items.
  Caveat now counted per report (`n_agg_items_chunk_outside_context`): some
  aggregation items' chunks lie outside the 4,096-token certification
  context; they score ~chance under BOTH conditions, so `accuracy_delta`
  remains a valid paired comparison but its magnitude is diluted. The two
  axes share no items; a 70% pointwise failure rate cannot leak into the
  aggregation delta.
- **Compacted context contents**: surviving KV only. No summary text, no
  auxiliary representation — the harness certifies pure eviction mechanics,
  not the full substrate resume path.
- **EXPAND**: disabled (`expand_enabled: false` in every report;
  `expand_calls = 0`).
- **Scoring**: argmax over option-letter logits, greedy (eq_policy_v1).
  Letter-format failures are impossible by construction — scoring never
  parses generated text.
- **KL window**: fixed short continuation (~5 tokens) — a smoothness probe,
  not a long-horizon divergence measure.

## Results with control and random arms (4 domains × 5 contexts each)

| Arm | mean KL (agg) | raw lost-fact | lost-fact given prior-correct |
|---|---:|---:|---:|
| evict 0.00 (control) | 0.0000 | 0.167 | **0.000** |
| evict 0.25 contiguous | 0.0303 | 0.708 | **0.550** |
| evict 0.40 contiguous | 0.0339 | 0.808 | **0.650** |
| evict 0.25 matched-random | 0.1028 | 0.292 | **0.125** |

- **Noise floor**: the control arm's raw rate (0.167) is entirely never-knew
  items (model wrong even with full context); conditioned on prior-correct
  the floor is exactly 0.000 with KL exactly 0 (deterministic greedy
  scoring). The conditioned column is therefore the citable metric; the
  raw column carries a ~0.17 never-knew floor.
- **Headline restated**: at 25% contiguous eviction, 55% of facts the model
  demonstrably knew from context are silently lost; 65% at 40%.
- **Recency structure matters a lot** (random arm): evicting the same token
  count uniformly instead of contiguously CUTS pointwise loss ~4× (0.125 vs
  0.550) while TRIPLING aggregation-axis damage (KL 0.103 vs 0.030) —
  spreading damage thin preserves needles (~75% of each chunk survives) but
  perturbs the whole distribution. Contiguous-span policies concentrate
  pointwise damage and hide it from aggregate metrics; this is the sharpest
  quantitative form of the spec 4.7 antagonism we have measured.

## Manual failure audit (complete population, not a sample)

26 prior-correct failures across the 0.25/0.40 arms deduplicate to **14
unique items** (12/14 fail at both fractions — deterministic and coherent).
All 14 reviewed by hand from `probe_records` (question, options, gold, both
predictions, source-chunk excerpt):

- **11/14 genuine forgetting** — exact needles (GTM container ID, pinch
  constant 750, $202,500 advance, 9.5% CPUC rate, signing date, case name,
  const prefix, employee count, pill count, residency years, skill count),
  typically with near-miss distractors; the model flips to a plausible
  alternative once the source span's KV is gone.
- **2/14 malformed items** — duplicate answer options (A ≡ D verbatim, e.g.
  the $3,500 Rhino-X item). The model's compacted answer was content-wrong
  anyway, but these items are low-quality; a dedup-options filter in the MCQ
  pipeline would remove them.
- **1/14 question–gold mismatch** — asks for a "statute," gold is a case
  name (State v. Tavares); the compacted model's statute answer is arguably
  the more faithful reading. Counts toward noise.
- **0/14 letter-format failures** — impossible under logit-argmax scoring.
- Corpus-quality note: legal-domain chunks show OCR corruption (case-law
  scans); items still function as needles but corpus cleaning would help.

Audit verdict: ≈79–86% of measured prior-correct loss is genuine forgetting;
the conditioned headline (0.550/0.650) overstates true loss by at most ~2-3
percentage points from flawed items — well inside the qualitative claim.

## Unresolved questions

- MCQ pipeline should gain two cheap filters for future runs: reject items
  with duplicate options; reject question/gold type mismatches (case vs
  statute). Not rerun-blocking; items affected ≈ 2-3/14 of the failure set.
