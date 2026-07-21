# Clean Experimental Trace Gallery Design

**Date:** 2026-07-21
**Status:** Approved for planning

## Goal

Produce a compact, paper-ready gallery of real held-out E1FULL certification
traces. The gallery must be reproducible from the signed clean artifact and
must not mix toy runtime output, contaminated historical measurements, or
manually transcribed metrics into the evidence.

## Source Of Truth

The sole experimental input is:

`plans/260719-2328-e1full-unfrozen-full-recipe/summary-e1full-clean-v1-n60.json`

The generator verifies the artifact's holdout hash, training-manifest hash,
checkpoint hash, zero-overlap audit, document count, and GT13 NO-SHIP verdict
before selecting any trace. A mismatch stops generation rather than producing
an updated-looking gallery from an unknown artifact.

## Outputs

- `examples/experimental-traces/clean-e1full-traces.json`: structured,
  machine-readable trace records with provenance.
- `examples/experimental-traces/README.md`: human-readable trace cards for
  paper and README reuse.
- A concise trace summary and link in the root `README.md`.
- A compact trace table and artifact pointer in paper #2's appendix, followed
  by a rebuilt `paper2/main.pdf`.

These are certification traces: selected questions, choices, gold labels,
per-arm predictions, and document-level metrics. They are explicitly not
token-by-token generation logs or attention tensor dumps.

## Trace Selection

Select exactly three documents from the 60-document clean holdout:

1. **Pointwise recovery:** matched eviction loses at least one prior-correct
   fact while depth-1 preserves it.
2. **Axis disagreement:** depth-1 improves pointwise retention relative to
   eviction while its document-level aggregation KL is worse.
3. **Depth-4 collapse:** depth-4 loses a prior-correct fact that depth-1
   preserves and has materially worse aggregation KL.

Selection is deterministic and runs in the listed category order. Pointwise
recovery candidates sort by recovered-item count, then the eviction-minus-d1
lost-fact-rate gap. Axis-disagreement candidates sort by that rate gap, then
the d1-minus-eviction KL gap. Depth-4 candidates sort by the count of items d1
preserves and d4 loses, then the d4-minus-d1 KL gap. Every numeric sort is
descending and document ID is the final ascending tie-breaker. Already chosen
documents are excluded from later categories. If fewer than three distinct
eligible documents exist, generation fails with a descriptive error.

## Trace Schema

The JSON output contains:

- Artifact, holdout, manifest, and checkpoint hashes.
- Policy ID, clean verdict, and certified depth copied from the source record.
- For each trace: category, document ID, domain, selection reason,
  document-level metrics for eviction, depth 1, depth 4, and control.
- A question-level comparison keyed by item ID, including question, options,
  gold answer, full-context prediction, and the available per-arm compacted
  predictions.
- Explicit evidence-scope text stating that aggregate-axis metrics are
  document-level and probe records are pointwise items.

No source context passages are fabricated. The gallery uses only fields
present in the signed artifact.

## Generator

A small repository script reads the signed artifact, validates provenance,
aligns reports by `eval_protocol.doc_id`, aligns probe records by `item_id`,
selects the three cases, and writes stable JSON and Markdown. Stable ordering
and serialization make regeneration diffable.

The checked-in outputs are generated artifacts. Manual edits belong in the
generator or its templates, not directly in the JSON gallery.

## Failure Handling

Generation fails closed when:

- Provenance hashes or the zero-overlap audit differ from the registered clean
  values.
- An arm is missing a held-out document or required item record.
- Gold labels or full-context predictions disagree across aligned arms.
- The three trace predicates cannot be satisfied by distinct documents.
- Regeneration differs from checked-in output during tests.

## Verification

Tests cover provenance validation, arm/item alignment, deterministic distinct
selection, predicate satisfaction, and byte-for-byte regeneration of both
gallery files. Existing publication-hygiene tests will require the README and
paper #2 to link the clean gallery and retain NO-SHIP/depth-zero wording.

Final verification runs the focused trace tests, the complete test suite,
strict JSON parsing, `git diff --check`, and a warning-free Tectonic rebuild of
paper #2.

## Non-Goals

- No toy or synthetic examples in the gallery.
- No historical contaminated trace rows.
- No frozen-versus-unfrozen ranking claim.
- No token-level generation, attention, or hidden-state dump.
- No web UI, notebook, or remote publication step.
