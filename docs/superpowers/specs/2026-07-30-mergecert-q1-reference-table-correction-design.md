# MergeCert Q1 Reference Table Correction Design

## Problem

`MERGECERT-Q1-REPORT.md` currently mixes Q1's matched 0.25/0.40 arms with
historical reference rows under one “matched retained budget” heading. The
historical rows are neither population-matched nor ratio-matched to Q1, and
their values are stale n=12 or contaminated-run anchors.

## Approved presentation

The Q1 section will contain two explicitly different views:

1. A matched Q1 table containing, in order, eviction 0.25, MERGE 0.25,
   eviction 0.40, MERGE 0.40, and the zero-compression control.
2. A “Historical context — not directly budget/population matched” table
   containing the latest n=60 frozen and clean-unfrozen depth-1 rows.

The historical table will state that its rows use different populations and
approximately 50% compression, so they are context rather than matched Q1
comparators.

## Evidence architecture

No campaign verdict or trigger artifact will be rewritten. In particular,
`q1-verdict.json` and `q1-trigger.json` remain byte-for-byte unchanged because
the trigger hash is embedded in downstream Q2/Q3 evidence.

The renderer will load and hash-bind two existing authoritative sources:

- `FULLRECIPE-REPORT.md` for the superseding frozen n=60 row:
  KL 0.2820, accuracy delta +0.1019, lost given prior 0.210.
- `plans/260719-2328-e1full-unfrozen-full-recipe/summary-e1full-clean-v1-n60.json`
  for the clean unfrozen depth-1 row:
  KL 0.1281380667, accuracy delta +0.0536133333, lost given prior 0.050.

The renderer will extract these values from their sources rather than copying
them into a new result file. Validation will require the expected source
hashes, the frozen supersession statement, and the clean artifact's empty
overlap audit with 60 certification documents.

The old `q1-verdict.json` reference fields remain registered historical
anchors. They are not displayed as current evidence and remain validated as
part of the immutable Q1 artifact.

## Validation

Regression tests will first establish that the current renderer fails the new
presentation contract. The implementation will then:

- require paired matched-arm ordering;
- exclude historical rows from the matched table;
- render a separately labelled current n=60 context table;
- reject source hash, extraction, or clean-overlap drift;
- include both reference sources in the artifact manifest;
- reproduce the report deterministically;
- leave Q1 verdict and trigger hashes unchanged.

The report-specific tests, validator, deterministic regeneration, full offline
test suite, and immutable-artifact hashes will be checked before handoff.

## Scope

This correction is local only. It does not push, publish, transmit, rerun GPU
work, modify Q1/Q2/Q3 scientific verdicts, or overwrite the user's modified
files in the primary checkout.
