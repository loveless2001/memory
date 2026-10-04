# Broader evaluation v2: neutral wording corrections

V2 corrects the six references rejected by the independent Claude review and
applies a consistent neutral-pronoun convention to authored prose. **Twelve cases
changed; 108 accepted cases are byte-identical at the record/reference level.**
The changes need independent delta review. No reader answers exist and training
remains paused.

The original candidate, its freeze, and both saved review files remain unchanged.
The parent review has 114 accepts and six rejects. We did not convert those six
rejects into accepts ourselves. The new
[review entrypoint](../../../CLAUDE-BROADER-EVAL-V2.md) supports a bounded delta
review and a cross-family scan for the same defect class.

| Change | Cases |
| --- | --- |
| Apply reviewer-suggested neutral answer verbatim | F001-Q4, F006-Q4, F014-Q4, F016-Q4, F018-Q4, F020-Q4 |
| Remove unneeded fictional-character pronoun under the source-only rule | F004-Q2 |
| Neutral answer wording for consistency, without reclassifying accepted v1 answers as errors | F008-Q2, F008-Q4, F009-Q4, F019-Q4 |
| Neutral question wording | F009-Q4, F013-Q2 |

There are eleven answer changes and two question changes across twelve cases.
The two question edits were stylistic; the review found no question defects.
The source-grounded pronouns in the accepted cases were not errors. F004-Q2's
public fictional character is a different setting from a private speaker, but
external character knowledge is unnecessary: removing the pronoun preserves
everything requested using only the passage. No web lookup was needed.

The authoring convention is to prefer names, role nouns, or they/their unless
gender is task-relevant and explicitly supported by user-provided evidence.
Keep source quotations, names, honorifics and kinship terms as supplied. All
120 authored queries and answers were scanned; no he/she/his/her/him/hers
pronouns remain. This lexical check does not certify every possible attribute
or inference. It reduces this specific accidental addition without changing
the task's meaning.

All sixty reader histories, forty synthetic continuations, source bindings and
evidence spans are unchanged. The two question hashes were recomputed, and
eleven answer claims were synchronized with the new wording. All references
remain within 90 words. `revision.py` compares every record/reference against
the parent and permits only those declared edits. `verify.py` checks the full
candidate, the 228 earlier protected files and 80 parent-candidate/review files.
The actual verification result and new freeze hash are in `verification.json`.

`revision-manifest.json` records the exact old/new wording, six required repairs,
other editorial changes, parent review hash, and 108 unchanged accepted case
IDs. Those accepts come from the parent review, not a new model judgment. The
original full-review template remains available; `delta-review-template.json`
contains the twelve decisions needed for the narrower follow-up.

The review process caveat matters: most full histories were read by delegated
per-family reviewers. The coordinator inspected every query, answer and cited
passage, personally read four full histories, and adjudicated the packet. Five
of the six rejects were caught only when a pattern found in another family was
checked across the whole packet. This supports an explicit cross-family defect
scan; it does not quantify review reliability or establish exhaustive correctness.

Data limitations carry forward: the same synthetic release, related cases per
family, 19 exact-turn components within new families and 17 with links through
prior families, no established near-duplicate independence, passage cues in
questions and deliberately explicit synthetic updates. This is reference
review, not a performance score, human review, or evidence of learned memory.
