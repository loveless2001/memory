# MergeCert Q1 Completion Design

**Date:** 2026-07-28

**Status:** Design approved; written-spec review pending

**Authoritative scope:** `MERGECERT-Q1.md`, with `MERGECERT.md` and spec
v0.3.7 retained for unchanged semantics

## Objective

Complete the missing moderate-ratio placement experiment for
attention-weighted KV merging. The settled 0.90 P0 result remains negative and
is not rerun or reinterpreted. Q1 measures merge against matched contiguous
eviction at 0.25 and 0.40 on aggregation and pointwise preservation axes. Q2
and Q3 run only if Q1 earns at least one axis with a directionally favorable
95% confidence interval that excludes zero.

## Chosen approach

Surgically adapt the existing MergeCert runner and analyzers. This preserves
the verified real-attention port, sink handling, M1 reconstruction, exact
budget logic, and conditional Q2/Q3 implementations while removing assumptions
superseded by the addendum.

Rejected alternatives:

- A separate Q1-only runner would duplicate the most sensitive cache and M1
  replay logic.
- A generic campaign-configuration framework would add scope and new failure
  modes without improving this fixed experiment.

## Registered protocol

### Scope and provenance

- Model: `Qwen/Qwen3-4B-Instruct-2507`.
- Ratios: exactly 0.25 and 0.40.
- Retained physical KV lengths: 3,072 and 2,458.
- Exact sinks: logical positions 0 through 3.
- Recent KV remains exact.
- Merge uses the existing real accumulated attention implementation.
- The 0.90 result is imported from the immutable P0 verdict and raw artifact;
  it is never recomputed by Q1.
- Every Q1 artifact records SHA-256 hashes of `MERGECERT-Q1.md`, the settled
  P0 verdict, source corpus manifest, all-items manifest, archived M1 reports,
  and the compatibility fingerprint.

The old boolean requirement that P0 pass is replaced only for this addendum.
The new gate requires the exact settled P0 negative state:

- P0.3 is false.
- P0.4 and real-attention validity are true.
- `stop_q1_q3` is true under the parent brief.
- The addendum hash is present and authorizes moderate-ratio Q1.

Any other P0 state or hash drift fails closed.

### M1 population and arms

Q1 uses the complete archived M1 protocol of record: four domains, five
contexts per domain, for 20 unique documents. It does not use the P0 200-item
subsample.

For each context, the runner prefills once and evaluates:

- zero-compression control;
- contiguous eviction at 0.25 and 0.40;
- attention-weighted merge at 0.25 and 0.40.

All arms must share the identical context, aggregation probes, needle probes,
and full-context predictions. Before accepting merge evidence, the control and
eviction rows are replayed against all archived M1 reports. The control must
have exactly zero KL, accuracy delta, and lost-prior rate.

### Statistics and verdicts

The analyzer computes arm summaries, per-domain slices, and paired
document-cluster bootstrap intervals for `merge - eviction` at each ratio:

- aggregation mean KL;
- aggregation accuracy delta, defined as compacted accuracy minus
  full-context accuracy;
- pointwise lost-fact rate given prior correctness.

The registered readings are decided mechanically:

- **R1:** earned when the upper endpoint of the lost-prior interval is below
  zero at either ratio.
- **R2:** selected when R1 is not earned. The report distinguishes overlap
  from directionally worse intervals per ratio without changing the registered
  wording.
- **R3:** reported independently for both aggregation metrics at both ratios.
  Aggregation earns an axis when either the mean-KL interval is wholly below
  zero or the accuracy-delta interval is wholly above zero.

Q2/Q3 trigger if and only if R1 is earned or aggregation earns an axis under
R3. The trigger decision is written to a small hash-bound
`q1-trigger.json`. A full negative records the conditional skip in the same
artifact.

## Execution flow

1. Add contract and analyzer tests that fail against the parent-brief behavior.
2. Adapt Q1 constants, provenance gate, arms, analyzer, and smoke audits.
3. Run all local focused and full tests.
4. Copy the addendum and settled P0 verdict to the private Modal volume.
5. Obtain explicit approval for the bounded Q1 H100 spend, then launch a
   two-document smoke.
6. Independently validate the retrieved smoke before full spend.
7. If the smoke passes, launch the 20-document Q1 certification detached under
   the same approved Q1 spending bound and monitor it to completion.
8. Retrieve the immutable artifact, calculate verdicts locally, and write
   `q1-trigger.json`.
9. If the trigger is false, record the Q2/Q3 skip. If true, adapt Q2 gate
   checks to require the positive Q1 trigger hash, run the registered Q2 pilot,
   eight-slice capture fleet, probe analysis, and local Q3 nesting analysis.
10. Retrieve exact billing records, stop all apps, and produce the final
    evidence bundle and private report.

## Conditional Q2/Q3 authorization

Q2 capture and probe runners currently require a passing parent P0 flag. Under
this addendum they instead require:

- a valid settled-P0 hash;
- a valid addendum hash;
- a validated `q1-trigger.json`;
- `run_q2_q3: true`;
- at least one named favorable Q1 interval satisfying the registered rule.

The local Q2 analyzer independently verifies the same authorization. Q3 uses
the Q2 score artifact at ratio 0.40 and the fixed 2,000-item E1 membership; it
does not launch a separate capture job.

## Artifacts and report

Local evidence lives under a new `plans/260728-mergecert-q1/` directory so the
parent campaign's evidence and report remain immutable. The existing runner
may gain addendum-specific entry points, but it must retain the parent P0
entry points and behavior. Expected files are:

- `source-provenance.json`
- `q1-smoke.json`
- `q1-certification.json`
- `q1-verdict.json`
- `q1-trigger.json`
- `q1-table.md`
- `compute-actuals.json`
- `artifact-manifest.json`
- conditional Q2/Q3 evidence, tables, and explicit skip record

The final `MERGECERT-Q1-REPORT.md` contains:

- the completed table with all required reference and control rows;
- verbatim R1, R2, and R3 registered readings followed by measured verdicts;
- paired confidence intervals and per-domain slices;
- the conditional Q2/Q3 evidence or exact skip rule;
- billing-ID compute provenance;
- “For the KV-Merge README” full-ratio wording;
- “For the spec” §13.7 draft wording;
- limitations and no-publication statement.

The parent `MERGECERT-REPORT.md` is not rewritten by this campaign. The new
report remains local/private. Prior delivery waiver is not represented as a
new confirmed transmission.

## Failure handling and resumability

- Existing remote artifacts are accepted only when their registered sample,
  provenance hashes, gate record, and completed counts match exactly.
- Smoke and full artifacts use distinct paths.
- Per-document Q1 checkpoints commit after each document.
- Q2 slices use existing independent resumable state.
- Any M1 replay mismatch, partition drift, non-finite tensor, nonzero control,
  budget mismatch, source drift, malformed confidence interval, or billing
  ambiguity stops the campaign before later spend.
- Every launched app is inspected and stopped before the campaign is reported
  complete.

## Verification

Tests must cover:

- ratios contain only 0.25 and 0.40;
- no Q1 code path evaluates 0.90;
- exact retained budgets and pinned sinks;
- settled-negative P0 plus addendum authorization;
- rejection of missing or altered hashes;
- all five Q1 arms and identical partitions;
- all archived M1 replay checks;
- exact zero control;
- paired intervals and per-domain slices;
- R1/R2/R3 and conditional trigger boundaries;
- Q2 rejection without a positive Q1 trigger;
- negative-report and conditional-positive report schemas;
- artifact hash completeness and billing provenance.

Completion requires the final report validator, complete local test suite,
`git diff --check`, clean campaign job state, exact Modal billing evidence,
and a requirement-by-requirement audit against `MERGECERT-Q1.md`.

## Budget and stop rule

The total ceiling remains $45. Q1 is expected to cost $12–15. Conditional
Q2/Q3 may spend the remaining budget only after the registered Q1 trigger.
No 0.90 rerun, tuning, hybrid implementation, training, cross-model work,
public artifact, or deployment claim is permitted.

After Q1 plus conditional work or recorded skip, generate the report and stop.
