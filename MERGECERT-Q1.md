# MERGECERT-Q1.md — Merge Placement Completion (moderate ratios)

Addendum to MERGECERT.md, correcting an over-fenced stop rule in the
parent brief: P0.3 gated the entire placement on the 90% direction
check, conflating "the source repo's headline fails" (now measured:
MERGECERT-REPORT, 2026-07-27) with "the method has no place on the
spectrum" (untested — the Q1 rows at moderate ratios were never run).
This brief completes the placement question only. Precedence: this
brief on scope, spec v0.3.7 on semantics. The P0 port is reused
unchanged (real accumulated attention, sink pinning, exact budget
matching); no re-porting, no tuning.

## Settled protocol amendment — 2026-07-29

The first Q1 smoke exposed that the exact archived M1 population contains
source windows shorter than 4,096 tokens. The settled choice is to preserve
the registered 20-document population and exact archived replay. This section
supersedes only the assumption that every document has one universal retained
KV length.

For each archived document, reconstruct the M1 context exactly as the original
harness did: tokenize the source, take up to 4,096 tokens from the registered
window, decode that source window, and re-encode the decoded text as the model
input. At requested ratio `r`, the contiguous comparator evicts exactly
`int(source_window_tokens * r)` physical KV entries. The merge arm must retain
exactly the comparator's measured physical count:
`model_input_tokens - evicted_tokens`. Sinks `0..3`, partitions, requested
ratios `(0.25, 0.40)`, real attention, control, model, and all other gates stay
unchanged.

The familiar retained counts 3,072 at 0.25 and 2,458 at 0.40 remain the
expected values for a 4,096-token source/model input. Short archived contexts
use their per-document matched physical budgets; they are not padded,
concatenated, dropped, or replaced. Evidence and the private report must record
the source-window token count, model-input token count, evicted token count,
eviction retained count, and matched merge target for every document and
ratio. Authorization, analysis, triggers, and downstream conditional work are
hash-bound to budget mode
`archived-m1-per-document-matched-physical-v1`.

**Registered framing:** the 90% verdict stands and is not re-litigated.
The open question is whether attention-weighted merging beats matched
eviction at the operating ratios anyone would actually deploy (0.25 /
0.40 evicted-equivalent), on either axis. Both answers are reportable;
a full negative closes the method's placement cleanly, a positive earns
it a scoped spectrum row despite the extreme-ratio collapse.

### Do-not-build list
- No 90% re-runs (settled), no hyperparameter or block-size sweep, no
  hybrid/anchor variants (that is a separate future brief if Kevin
  wants it), no cross-model work, no training, no public artifacts.
- Q2 (routability) and Q3 (fragility) run ONLY under the conditional
  below — do not launch them unconditionally.

---

## Q1 — Two-axis placement at 0.25 / 0.40 (the whole point)

M1 harness unchanged: per-axis, counterfactual probes, noise-floor row,
document-cluster bootstrap CIs, greedy, house fingerprint. Full
manifest, not the P0 200-item subsample.

```text
| arm (matched retained budget) | agg KL | agg accΔ | pointwise lost|prior |
| eviction 0.25 / 0.40          | (existing certified rows)             |
| MERGE 0.25 / 0.40             | ?      | ?        | ?                   |
| zero-compression control      | 0.0000 | 0.000    | 0.000               |

paired per-item deltas (merge − eviction) with 95% CIs on both axes,
per ratio; per-domain slices.

registered readings:
  R1  pointwise: merge CI-below eviction on lost|prior at either ratio
      → the preservation instinct holds at moderate ratios; scoped
      spectrum row earned ("blend-preserving at moderate ratios,
      collapsing at extreme"), §13.7 note upgraded accordingly
  R2  pointwise: CI-overlapping or worse (the E2 interference
      prediction — averaging manufactures confusable-sibling blending)
      → placement closes negative on the needle axis at all ratios;
      the theory's "merging is structurally worst-case for bindings"
      reading is confirmed at deployment-relevant compression
  R3  aggregation: independent of R1/R2, report where merge KL/accΔ
      lands relative to eviction — a merge that loses needles but
      wins aggregation is STILL a coherent scoped result (gist tier
      behind a gate), and the two-axis protocol exists precisely to
      say so without blending
```

## Conditional Q2/Q3 (launch only if R1 or the aggregation half of R3
lands positive with CI separation)

If merge earns any axis, its routability and fragility placement become
worth $30: run MERGECERT.md's Q2 arms (merge-mechanics features, shadow
gate, sink-head monitor fifth-regime row, residual probe) and Q3
nesting, unchanged from the parent brief. If Q1 is negative on both
axes, skip — routability of a loss nobody would deploy is not worth the
spend; record the skip and the rule that triggered it.

## Deliverables

MERGECERT-Q1-REPORT.md: the completed placement table with all
reference rows; R-verdicts verbatim; per-domain slices; conditional
Q2/Q3 results or the recorded skip; an updated **"For the KV-Merge
README"** section superseding the parent report's (the full-ratio
story, stated kindly: what holds, what doesn't, and — under R2 — the
hybrid merge-plus-anchor direction as the theoretically motivated next
design, one paragraph, offered not prescribed); an updated **"For the
spec"** §13.7 draft note matching the verdict. Private to Tyler +
Kevin, as before. Billing-ID compute provenance per the parent
report's format — keep it.

## Compute budget

Q1 full-manifest certification, 2 ratios ≈ $12–15 · conditional Q2/Q3
≈ $30 if triggered. **Ceiling $45; expected $15.**

## Stop condition

Q1 R-verdicts (+ conditional work or recorded skip) → stop and report.
No hybrid variants, no tuning, no 90% revisits, nothing public.
