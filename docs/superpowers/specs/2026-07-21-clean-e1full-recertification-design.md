# Clean E1FULL Recertification Design

## Objective

Replace the contaminated E1FULL certification with a reproducible experiment in
which certification documents are reserved before training, provenance is
recorded in the result artifact, every reported comparison has a paired
confidence interval, and runtime deployment depth agrees with the certified
predicate.

## Scope

This change repairs the full-recipe manifest, E1FULL training and certification
workflow, result schema, model-card generator, campaign report, specification,
and the one non-standard JSON artifact found by the audit. It also launches one
clean E1FULL retrain and n=60 certification. It does not rerun unrelated gate,
probe, or paper experiments.

## Holdout Contract

A new deterministic holdout builder selects 15 eligible documents per domain
from the four-domain MCQ corpus. Eligibility uses the same tokenizer, context
window, compacted-region bounds, and probe-count requirements as certification.
The builder writes `/artifacts/corpus-fullrecipe/certification-holdout.json`
with sorted document IDs, selected item IDs, selection parameters, corpus hash,
and its own canonical hash.

The full-recipe mixture builder requires this artifact and excludes every item
whose document is reserved. It records the holdout hash and verifies both
document-level and item-level overlap are zero. Previously traced holdout items
are classified as deliberately excluded rather than orphaned.

Certification requires the same holdout artifact and the exact training
manifest used by the checkpoint. It refuses to run unless:

- the requested number of documents is present in every domain;
- selected certification documents exactly match the reserved set;
- document and item overlap with training are both zero; and
- the checkpoint records the training-manifest and holdout hashes expected by
  the run.

## Result And Predicate Contract

Every arm records probes. The top-level artifact records selected document IDs,
aggregation and needle item IDs, corpus, holdout, training-manifest, and
checkpoint hashes, plus the run parameters.

Paired per-document bootstrap intervals are emitted for `mean_kl`,
`accuracy_delta`, `lost_fact_incident_rate`, and
`lost_fact_rate_given_prior_correct`. Comparisons include every candidate
against matched eviction and the unfrozen E1FULL arm directly against the
frozen full-recipe arm when both artifacts are supplied to the analysis path.
Labels and tables must use the metric whose values they display.

The runtime keeps one conservative `max_certified_depth`. Depth 1 is written
only when the primary distributional GT13 predicate passes; a secondary
task-anchored result remains analysis metadata and cannot enable runtime use.
The current contaminated E1FULL result and deployment claim are marked invalid
until the clean rerun finishes.

## Rerun

The rerun uses new artifact names so contaminated checkpoints and reports remain
available for audit but cannot be mistaken for clean results. The sequence is:

1. Build and validate the holdout.
2. Rebuild the full-recipe manifest and derived triplets/token arrays.
3. Train an unfrozen E1 compactor under a new clean tag.
4. Run n=60 certification against matched eviction and required comparison
   arms, saving full probe provenance.
5. Copy the result into the repository, validate hashes and confidence
   intervals, then update the report/spec/model-card text from that artifact.

The job is stopped on any overlap, non-finite training value, missing hash,
insufficient per-domain document count, or checkpoint/manifest mismatch.

## Testing

Pure helpers cover deterministic holdout selection, document-level exclusion,
fail-closed overlap checks, canonical hashes, paired confidence intervals, and
depth metadata. Existing certification tests verify probe provenance. The full
suite, compilation, strict JSON parsing, and a dry-run audit of the remote
artifacts gate the paid jobs.

## Cost Boundary

Authorization covers the clean E1FULL training and n=60 recertification needed
to replace the invalid result. It does not cover additional hyperparameter
sweeps, recurrence training, gate relabeling, or publication pushes.
