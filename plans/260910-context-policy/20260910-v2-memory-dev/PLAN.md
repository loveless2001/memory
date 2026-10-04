# Memory-dependent development questions, version 1

This is a new, local CPU data/evidence diagnostic on the ten already-seen
PersonaMem training histories. Existing questions, references, captures and
scores remain frozen. No GPU collection, paid judge, training or label export
is part of this step.

Author 50 questions: three historical fact-recall questions and one withdrawal
case per history, plus five missing-information and five generic controls.
Use only sanitized user/assistant dialogue to author source-bound references.
Prefer concrete quantities, names, schedules and details from supplied drafts;
explicitly scope draft recall to the text rather than asserting autobiography.
Exclude target facts withdrawn later. Withdrawal cases must respect the latest
instruction without inferring the opposite preference or restating the detail.
Missing-information controls need a whole-history absence audit. References must
fit 90 whitespace-delimited words. Freeze questions and references before
running the new evidence-availability audit; never modify them to improve it.

Selection is manual and purposive, emphasizing early concrete user turns.
The author has already seen these histories and the earlier notes. This is
neither blind nor held out; there are ten source groups, not 50 independent
examples. Source coordinates and hashes certify provenance, not entailment.
Record author review separately from still-pending independent semantic review.

Replay the unchanged pinned tokenizer, 512-token recent window, 384-token
chunks with 64-token overlap, and two 1024-token BM25 retrieval rounds against
the revision-4 notes. Report required evidence in notes alone, notes + recent,
and after each retrieval, with exact spans and manual semantic inspection of
alternate evidence. Exact source-span overlap is a conservative diagnostic,
not answer accuracy. Full semantic coverage requires all answer components,
their relation, role/ownership and applicable withdrawal context. Report
withdrawal and control cases separately. No routing targets may be inferred
from availability alone: actual answers are required for useful-action labels.

Save a reader-only bundle, private references and audit packet, source/freeze
hashes, per-case availability, and a report. Check new source bindings and
confirm the prior reader bundle, references and revision-4 artifacts are
unchanged. Full-corpus admission and external evaluation remain pending.
