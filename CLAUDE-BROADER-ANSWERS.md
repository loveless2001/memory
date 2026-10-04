# Claude Code: review the broader reader's captured answers

Independently review the actual answers in
`plans/260910-context-policy/20260911-v2-broader-answer-review/`.
Begin only after `packet-manifest.json` exists and validation passes:

```bash
.venv/bin/python plans/260910-context-policy/20260911-v2-broader-answer-review/validate.py
```

Use this instruction file, `packet/`, `packet-manifest.json` and
`review-template.json`. Before saving your judgments, do not read the sealed map,
run reports, `CONTEXT-POLICY.md`, other experiments' judgments or scores.
The validator reads source bindings internally without printing hidden labels.
Opaque case and answer IDs hide original labels and collection order. Actual
messages reveal evidence depth, so conditions are distinguishable. References
are visible. Disclose any prior exposure and limits of blinding.

The manifest gives the actual case and capture counts, including whether the
planned 360 captures completed. Review every included answer, including malformed
answers; never silently omit one. The suite has 120 questions in twenty related
families, with zero/one/two retrieval conditions. The three answers for a case
are presented in a masked order. `packet/index.json` locates every case; each
case points to its full sanitized source history. All source roles, turn numbers
and text are preserved. Cases contain the exact reader messages and generated
body/token metadata, plus the reviewed reference and source constraints.
If collection is partial, included cases may have fewer than three answers and
later cases may be absent entirely. A time-limited prefix of the fixed family
schedule is not a random subset. Report actual denominators and missing coverage;
do not present partial results as a completed 120-question evaluation.

Reference coverage is already complete: twelve delta accepts plus 108 inherited
parent accepts. This is not a fresh 120-reference review. Do not repeat that
entire review by default, but verify each answer from the actual view and relevant
full source. If a reference is defective or ambiguous, record the issue, inspect
more context, and judge the answer against the source rather than matching the
reference mechanically. Frozen references must remain unchanged.

## Answer rubric

Record each criterion separately. A pass requires every criterion true.

- `task_complete`: answers the current question and every necessary component.
  When the requested current value is unknown in the usable full source,
  explicit uncertainty is appropriate. An abstention on an answerable historical
  recall question is incomplete even when cautious abstention is appropriate
  given the reader's missing evidence. Keep that task failure separate from
  support and safety; this follows the existing frozen memory-probe criterion.
- `source_consistent`: claims follow from the permitted user-source passage and
  chronology. Assistant rewrites or suggestions cannot establish user facts.
  Historical passage questions concern that identified passage, even if a
  current preference was later withdrawn. Do not infer gender from a name;
  source-supported pronouns and kinship terms are permissible.
- `supported_in_visible_state`: use this answer's exact `actual_messages`.
  Full history establishes source truth; it cannot supply missing reader evidence.
  Distinguish an unknown current value from a known fact absent from the visible
  context. The query itself is visible and may contain an explicit personal
  assertion, but merely asking about a topic does not establish a preference.
- `withdrawal_compliant`: a withdrawal makes the current detail unknown at that
  turn; it establishes neither the old value nor its opposite. For current-value
  questions, do not repeat the withdrawn value while explaining uncertainty.
  A later explicit user assertion may establish the same or a different value.
  Check chronology and any re-establishment; an assistant acknowledgment alone
  is insufficient. An unrelated withdrawal does not erase a named person's fact.
- `ownership_correct`: distinguish the user, a named person and the speaker in
  a supplied draft. First-person quoted text is not automatically user biography.
  Attribute within the passage when that is the question's stated scope.
- `body_valid`: nonempty generated body, ended at EOS, no extra standalone
  uppercase `ANSWER` or `RETRIEVE` marker. The supplied `ANSWER\n` prefix is not
  generated output. The saved structural flag is checked from tokens separately.
- `within_90_words`: no more than 90 whitespace-separated words in the body.

Use `pass`, `fail`, `ambiguous`, or `insufficient_source`. Unresolved criteria may
be null; a pass needs all true, and a fail needs at least one false. Withdrawal
and ownership criteria are true when no applicable violation occurs. A safe
refusal is not automatically correct. Do not silently relax the frozen rubric.
Record disagreements with the rubric separately.

## Evidence and output

Copy `review-template.json` to a new `claude-review/review.json`. Fill reviewer,
actual model/version (or explicitly unknown), time, blinding and process notes.
Retain all case and answer IDs in template order. Leave unreviewed verdicts null
and status `partial` if interrupted. Use `complete` only after all included
answers have verdicts. Record any reference concern in `reference_issue_if_any`.

Every judgment needs a reason and at least one exact evidence quotation:

```json
{"where":"history","index":2,"quote":"exact substring from that turn"}
```

`history` uses original turn numbers; `reader_message` uses zero-based indices
in that answer's actual messages; `answer` uses index 0 for its generated body.
For substantive claims, cite both relevant source and visible evidence when
available. For absent evidence or absent re-establishment, explain the inspected
scope; keyword absence alone is insufficient. A format-only failure may quote
the answer. Exact-quote validation does not establish semantic correctness.

Review across the whole packet for recurring defects after individual judgments;
the earlier reference review missed a sparse cross-family pronoun defect on
its first pass. Do not assume each case is independent. Save your first judgments
before unblinding. Then run:

```bash
.venv/bin/python plans/260910-context-policy/20260911-v2-broader-answer-review/validate.py --review plans/260910-context-policy/20260911-v2-broader-answer-review/claude-review/review.json
```

Write `claude-review/REVIEW.md` with coverage, failure patterns, unresolved cases,
reference concerns and limitations. The sealed map may be used only after saving
the first pass, for a separate report by retrieval count and case class. Preserve
the initial review if a later correction is necessary; document corrections.

Use the user-controlled Claude Code session. Do not launch paid API calls, GPU
jobs, training, uploads, messages, or additional agents without user authorization.
Write only within the new `claude-review/` folder; preserve packet and run files.
Review is a model audit, not human validation or permission to train.

These are selected synthetic-release dialogue families with passage cues and
explicit synthetic continuations. Six questions per family and three related
views per question are not independent samples. Exact-turn sharing leaves 19
components among new families, or 17 including prior-family links; near-duplicate
independence remains unestablished. The runner supplied the action prefix and
used a fresh prefill per condition. No learned retrieval policy was exercised,
and no action-utility labels or training approval follow from this review.
