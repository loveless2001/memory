# Independent Claude Code judge handoff

You are reviewing a memory-reader experiment independently of its Codex author.
The user will run you in this repository. Your task is to audit the sources,
proposed references and captured answers, record your own judgments, and flag
anything that prevents a defensible result. Do not assume the author's labels
are correct. This is an independent-model review, not independent human review.

## Start here; preserve the first-pass blind review

Use only this note and the files under:

`plans/260910-context-policy/20260910-v2-judge-handoff/`

Initially **do not read** `sealed-map.json`, any `REPORT.md`, `CONTEXT-POLICY.md`,
`manual-judgments.json`, `judgments.json`, `judgment-summary.json`, or the
`author_judgments.py` scripts. They reveal the author's decisions and aggregate
results. Do not search the repository for prior verdicts before saving yours.
The packet hides original case IDs, arm labels, author verdicts and scores.
The actual prompts necessarily reveal their text; this is label/score blinding,
not a claim that the two representations are impossible to distinguish.
If you have already seen prior results, disclose that in `blinding_notes`.

Recommended model: Claude Opus 5 if available in the user's Claude Code setup.
Record the actual model/version; do not claim a particular model if unknown.
Use the current user-controlled Claude Code session. Do not launch separate
paid API calls, other agents, GPU jobs, training, uploads, or messages to others.
Do not change frozen experiment code, data, prompts, references or captures.
Write your review only under the handoff directory's new `claude-review/` folder.

## Material ready for review

There are **21 questions, 42 captured answers and 18 sanitized source histories**.
Each question has two answers collected with different withdrawal renderings.
The source data includes existing synthetic PersonaMem histories and short
hand-authored controls. These are selected development cases, not a representative
benchmark. There is no learned retrieval policy in this run.

- `packet/index.json`: ordered opaque case IDs and file paths.
- `packet/histories/H*.json`: complete original user/assistant histories with
  source turn numbers. Hidden persona/system profiles have been removed.
- `packet/references/C*.json`: current question and a **proposed**, fallible
  reference answer, source spans and constraints. No prior review verdict.
- `packet/answers/C*.json`: two anonymous answers, each with the exact messages
  the reader saw, EOS status and collection mode.
- `review-template.json`: output skeleton; copy it rather than editing it.
- `packet-manifest.json`: byte hashes and provenance bindings. It contains no
  semantic verdict or score.

From repository root, check packet integrity first:

```bash
PYTHONPATH=. .venv/bin/python plans/260910-context-policy/20260910-v2-judge-handoff/validate.py
```

## Review in two passes

1. Review all 21 proposed references using the full original sanitized histories
   and questions **before opening any answer files**. Record `accept`, `reject`,
   `ambiguous`, or `insufficient_source`, with reasons and source evidence. Check
   later turns, ownership, withdrawals and all requested answer components.
   Save these first-pass decisions as `claude-review/reference-review.json`.
2. Read each answer and its **actual reader messages**. Judge against the source
   and frozen rules below, not merely string similarity to the proposed answer.
   An answer may match a bad reference and still fail. A correct fact absent
   from the reader's actual visible state fails visible-support even if it
   appears in the full source. Preserve uncertainty rather than guessing a label.

Do not cherry-pick cases or stop after finding one error. Review all references
and all answers. If a case is ambiguous, record why and keep it unresolved.
If the review cannot finish, mark it partial and list the unreviewed IDs; never
report an aggregate as though it covers the complete packet.

## Frozen answer rules

An answer passes only if all applicable requirements hold:

- **Task completeness:** answers the actual current question and all necessary
  components. Safe abstention is appropriate when the requested value is unknown;
  it is incomplete when valid, visible information answers the question.
- **Source consistency and current validity:** facts follow from user evidence
  with the relevant chronology. Old assistant suggestions are not new user facts.
- **Withdrawal:** at the withdrawal turn, the affected topic becomes unknown.
  This does not establish its opposite, a dislike, or a known lack of preference.
  Do not repeat the withdrawn value, even while explaining that it was forgotten.
  A later explicit user statement may establish the same or a different value.
  A later question, assistant acknowledgment or quoted suggestion does not do so.
- **Ownership and task scope:** a supplied draft or fictional first-person text
  does not by itself establish user biography. A question explicitly asking about
  a passage should be answered from that passage. Respect the stated person and
  topic; do not let an unrelated withdrawal erase a named character or other fact.
- **Visible support:** use the exact `actual_messages` for that anonymous answer.
  The complete source history is for source truth, not a substitute for what the
  reader actually received. Bare `UNKNOWN` is acceptable when the current value
  is unknown. A question mentioning a topic does not re-establish its value.
- **Format:** nonempty body, generation ended at EOS, no standalone uppercase
  `ANSWER` or `RETRIEVE` anywhere in the generated body, at most 90 whitespace-
  separated words. The runner supplied `ANSWER\n`; do not count that supplied
  prefix as generated format compliance. No retrieval decisions were generated.

Apply the frozen rules even if you would choose different product wording.
You may separately criticize a rule, but do not silently relax it to alter scores.
Unknown validity and missing evidence are different from a definitive negative.
Avoid treating a refusal or cautious answer as correct merely because it is safe.

## Output and evidence format

Copy `review-template.json` to `claude-review/review.json` and fill every case.
Record reviewer identity, model/version if known, date, whether earlier verdicts
were seen, and any blinding limitations. For each anonymous answer give separate
booleans for the seven criteria in the template and a verdict of `pass`, `fail`,
`ambiguous`, or `insufficient_source`. Use `null` only when a criterion cannot be
resolved; a `pass` requires every criterion true. `withdrawal_compliant` is true
when no applicable withdrawal is violated; `ownership_correct` is true when no
ownership error occurs. A rejected reference does not automatically fail its
answers; assess them against the source and explain the discrepancy.

Evidence entries have this form:

```json
{"where":"history","index":4,"quote":"exact source text"}
```

Use `where: "history"` with the original turn index, or `where:
"reader_message"` with the zero-based index in that answer's `actual_messages`.
Quote exactly; include enough to locate support or contradiction. Reference
reviews use history evidence only. For absence claims, explain the inspected
scope and why no later statement establishes the value; a failed keyword match
alone is not proof. If you propose a reference correction, place it in
`reference_revision_if_needed`, leaving the frozen reference untouched.

Validate your completed output:

```bash
PYTHONPATH=. .venv/bin/python plans/260910-context-policy/20260910-v2-judge-handoff/validate.py --review plans/260910-context-policy/20260910-v2-judge-handoff/claude-review/review.json
```

This validates structure, identity and exact quotations, not semantic correctness.
Also write `claude-review/REVIEW.md` covering reference problems, answer failure
patterns, rubric concerns, uncertainty and limitations. Save `review.json` before
unblinding. After saving, you may inspect the sealed map and original judgments
to write a separate `claude-review/DISAGREEMENTS.md`; preserve your first pass.
Explicitly distinguish your model audit from human review and from held-out
benchmark evidence. Do not approve training or rewrite the historical result.

## Broader evaluation handoff — separate, not yet ready to score

After saving the review, you may inspect:

- `plans/260910-context-policy/20260910-v2-broader-eval-plan/PLAN.md`
- `plans/260910-context-policy/20260910-v2-broader-eval-plan/selection.json`
- `plans/260910-context-policy/20260910-v2-broader-eval-data/source-overlap-audit.json`

Twenty new families were selected before inspecting their dialogue, excluding
all 21 previously acquired personas and the prior 400-family reservation.
Their pinned raw bytes were acquired and verified, then system profiles removed.
Selection by persona does not eliminate shared dialogue turns: consult the
explicit overlap audit before claiming independent source groups.

The proposed 120-question broader suite has **not been authored or frozen**, and
no reader answers or independent scores exist for it. Do not report it as ready
or use the old 42 answers as its evaluation. Your review of the current packet
is the immediate handoff; the new-source suite is the next preparation task.
The earlier external benchmark and its inference limitations remain unchanged.
