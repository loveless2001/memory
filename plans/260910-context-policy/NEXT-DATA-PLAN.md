# Prospective data revision after the failed preparation pilot

Status: **candidate inspected and rejected unchanged at the grounding gate**.

The continuation completed pinned-source acquisition and a 50-case screening.
Four confirmed reference problems fail the 48-sound threshold. System messages
also exposed full persona profiles and were excluded from reader input. See
the [completed intake report](20260910-v2-personamem-intake/REPORT.md).
The proposal below records the original intake criteria; it is not an adopted
replacement corpus or an authorization to bypass the failed gate.

The current fresh-dialogue implementation projects to 5.12 GPU-hours before
notes, indexing, or labels. Its verbatim-anchor checker rejects many legitimate
paraphrases and does not establish semantic fidelity. Increasing the budget
alone would leave that annotation problem unresolved. Keep the completed
preflight and preparation results intact.

## Candidate that avoids fresh dialogue generation

Inspect **PersonaMem-v2 text training data**, pinned to revision
`ed956dea41521fc4499acbc63f966e0fd3c053ba`, before committing to it. Its official
card describes about 18.5k training queries with persona-disjoint benchmark and
validation splits, existing text histories, and source snippets. The 32k
history schema declares zero irrelevant-padding tokens. The release is
LLM-generated and is not wholly manually verified. It is CC-BY-4.0.
[Dataset card](https://huggingface.co/datasets/bowen-upenn/PersonaMem-v2),
[field definitions](https://huggingface.co/datasets/bowen-upenn/PersonaMem-v2/blob/main/column_descriptions.md).

This would change the development domain from authored workplace facts to
implicit personal preferences. It is not a drop-in implementation of the
original corpus. Its free-form response rubric also cannot be replaced by
the current exact factual-answer matcher.

Concrete intake and admission steps:

1. Acquire only the text training CSV and referenced 32k histories at the pinned
   revision. Keep `persona_id` groups intact. Audit actual history lengths,
   enough questions per persona, and cross-split source overlap before fixing
   sample counts; do not invent 400 independent groups by splitting histories.
2. Give the reader only the chronological raw history and `user_query`.
   Keep `correct_answer`, `incorrect_answers`, `preference`, `prev_pref`,
   `updated`, `expanded_persona`, and `related_conversation_snippet` in private
   scoring/grounding metadata. In particular, never turn the task back into
   multiple-choice selection or hand the reader a complete persona profile.
3. Match each private supporting snippet to actual raw turns. Review 50
   development questions for supported current preferences, updates, ownership,
   and possible ambiguities. Require at least 48 sound cases. An existing
   benchmark's labels do not replace this audit.
4. Freeze an independent free-form judge and budget before collecting useful-
   action labels. A private correct-answer string is not permission to mark any
   paraphrase incorrect or to use the answering 4B as its own judge.
5. Time a small notes/index/label batch with the selected FP32 reader. Project
   all remaining preparation, both training arms, and all evaluation arms
   against their existing ceilings, including generated answer lengths.
   Existing histories eliminate dialogue generation, not those later costs.

Keep LoRA targets, answer-versus-retrieve protocol, cache ownership, matched
answer exposure, and the same-reader forced-RAG control. Apply FP32 math SDPA
to every reader arm. Do not spend more on the failed dialogue generator.

## External inference must be settled prospectively

The original LongMemEval-S 500-question set remains entirely held out.
Its all-source connected-component bootstrap has one group. Two defensible
routes are available before any test scoring:

- Continue as an **exploratory pilot**, report all external scores descriptively,
  retain independent internal-family uncertainty estimates, and mark the
  original external advancement rule unassessable. Do not call this a registered
  success or substitute question-level confidence bounds silently.
- Revise the external test first. The candidate's persona-held-out benchmark
  and 32k histories may offer usable source groups, but actual overlap must be
  audited. Freeze the new test, judge, and grouping rule before fitting or
  selecting checkpoints, and label the result as a new protocol revision.

No replacement benchmark has been adopted, and no replacement corpus has been
used for training. The candidate failed admission before a new external test
was needed. Source acquisition and the ten-history audit are recorded in
`inputs/personamem-v2-candidate.json`; full-corpus overlap certification and a
usable independently judged target set remain pending.
