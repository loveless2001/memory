# Broader source-disjoint evaluation candidate

Prepare a new source-bound evaluation before further model changes or policy
label collection. This step authorizes CPU preparation and acquisition of
approximately 4 MB of pinned public source histories. It does not launch a GPU,
paid judge, training job, or publish/send a review packet.

## Source selection before inspection

Use the already acquired PersonaMem-v2 text training CSV at revision
ed956dea41521fc4499acbc63f966e0fd3c053ba. Read only persona IDs and 32k history
paths for selection. Exclude every locally acquired persona and the prospective
400 training/validation/internal-test personas from the prior intake. Rank the
remaining personas by SHA256('context-policy-broader-eval-v1:' + persona_id)
and select the first 20 before downloading or reading their dialogue. Freeze
the selection, exclusion list and selector code first. Fetch pinned object
metadata separately and verify every downloaded history against it.
Never replace a difficult selected history on the basis of reader performance.

These are newly selected local evaluation histories from the same synthetic
source release, not natural user conversations or the official external test.
Once inspected for authoring they are not blind to the reference author. Keep
all selected families out of future training; do not describe author review as
independent review. The official PersonaMem benchmark/validation and existing
LongMemEval-S external boundary remain unchanged.

## Candidate coverage

Target six questions per selected family: two source-scoped historical recall
questions, one withdrawal question, one ownership/current-fact control, and two
explicitly labeled synthetic continuation controls for later different/same
values. Continuation controls append user statements to a copy of the source;
they never overwrite the original archive. Keep variants grouped with their
parent family. If a natural case cannot be grounded unambiguously, retain the
selection and record the coverage gap instead of manufacturing a fact.

Author queries and references from sanitized user/assistant dialogue only.
Do not expose hidden persona/system messages, released answers/preferences,
or source answer snippets to the authoring or reader bundles. Cite exact source
turns with character offsets and hashes. Inspect later turns for applicable
corrections, withdrawals and ownership. Keep references separate from reader
inputs. Record source facts, task-scoped quotations and synthetic additions
separately. Freeze candidates before any reader inference.

Audit exact raw-history and normalized turn overlaps against all previously
acquired histories and among selected families. Report all-source connected
components rather than assuming persona IDs imply independence. Report source
provenance and synthetic origin explicitly. No case-level confidence interval
may silently replace family/source-component uncertainty.

## Review before labels

Prepare review packets that include complete sanitized histories, current
questions and proposed references with source coordinates. Hide the author's
accept/reject decisions from an independent model review. A reviewer must check
task completeness, source entailment, current validity, ownership, withdrawal
scope and ambiguity; hashes certify binding rather than semantic truth.

Proposed initial judge: Claude Opus 5, pending user selection and a frozen
calibration request/budget. Use a fixed 20-case calibration subset plus a small
separate challenge set with known structural/semantic defects. Do not tune the
judge on the new evaluation results or treat model agreement as human review.
Disagreements and ambiguous references remain unresolved until adjudication.
No source transfer or paid inference is authorized merely by naming a judge.

Deliver the source selection/provenance audit, candidate records/references,
review instructions/schema and packets, CPU validation and a status report.
Stop at independent-review readiness. Useful-action labels and policy training
remain gated on a prospectively approved and verified review protocol.
