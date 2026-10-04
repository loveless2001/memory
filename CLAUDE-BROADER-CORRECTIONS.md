# Claude Code: reconcile the broader answer review

Preserve your original `claude-review/review.json` and `REVIEW.md` under
`plans/260910-context-policy/20260911-v2-broader-answer-review/`. They have been
validated and hash-bound. This is an explicitly unblinded correction pass, not
a new independent review of 262 answers. Do not alter frozen inputs, references,
the original review, or the reader implementation.

Read the new `plans/260910-context-policy/20260911-v2-broader-review-audit/REPORT.md`
and `audit.json`. Verify integrity first:

```bash
.venv/bin/python plans/260910-context-policy/20260911-v2-broader-review-audit/verify_corrections.py
```

The original counts remain 106 pass / 155 fail / one ambiguous. They are not
accepted corrected scores. There are **117 distinct targeted answers**, with
overlapping concerns: 85 task-completeness flags, 107 visible-support flags,
three potentially inconsistent parent passes, and the existing ambiguity.
Flags request inspection; do not flip booleans mechanically or assume the Codex
audit is right. Use each target's original packet case, full source history,
exact `actual_messages`, generated answer and original reason.

## Apply the existing criteria consistently

1. `task_complete` requires the requested answer to be correct and complete.
   Merely producing a direct response is insufficient. In 85 cases, your reason
   describes a wrong requested value, invented core content, reversed exchange,
   or similar core task error while this flag is true. Reinspect those cases.
   An otherwise complete answer with an unsupported added attribute can still
   fail source consistency separately; do not conflate those situations.
2. `supported_in_visible_state` assesses the claims made by the answer, not
   merely the presence of a related source turn. In 107 cases, source consistency
   is false while visible support is true. That combination is not automatically
   impossible, but requires a defensible explanation. Compare actual role, text,
   character slices, assertion, ownership and chronology. A related turn number
   alone cannot support a false current value or invented gender. Do not require
   a whole long reference span when a smaller visible excerpt establishes the
   fact, and do not confuse source absence with appropriate uncertainty.
3. Reconcile **C079-B** with rejected **C069-A/B**: C079-B says a T267 statement
   was *later* withdrawn at T172. The full source has the withdrawal first and
   reinstatement later. The correct final preference does not erase a false
   chronology asserted in its explanation.
4. Reinspect **C026-A** and **C036-A** without presuming rejection. Their final
   negative values are source-supported, but their explanations may conflate
   withdrawal of the old positive value with establishment of the later negative.
   Distinguish a valid later assertion from withdrawal-only inference. Compare
   C036-C and apply the same rule to any analogous answer you find.
5. **C073-B** remains ambiguous. The question says “which university degree and
   internship organization”; the answer gives the degree subject and internship
   but omits Temple. Decide from the existing question and source, not solely
   the fact that the reference names Temple. Retaining the ambiguity is valid.

The first-person echo is not an automatic ownership failure when context clearly
preserves the user as referent. Identify an actual attribution error before
changing that criterion. Record this interpretation and any uncertain examples.
Similarly, the correct final value reached through a false withdrawal inference
can fail source/withdrawal criteria; assess task correctness and explanation
support separately rather than using one blanket rule for every answer.

Scan the original pass answers for the same explanation/chronology defect class.
Record findings outside the 117 targets separately. Do not turn the approximate
“30” first-person sensitivity note into an exact score change: the author audit
found 25 passing bodies beginning with an explicit first-person echo, which is
a lexical count, not an ownership adjudication.

## Save corrections separately

Copy `correction-template.json` into a new `review/` folder within the audit
directory as `corrections.json`. Fill the correction reviewer's own model/version,
time, process and exposure notes. Preserve both hash bindings and target order.
For every target use:

- `retain`: explain why the original full judgment stands; replacement is null.
- `replace`: provide a complete replacement answer-judgment object in the same
  schema as the original, with the same answer ID, all seven criteria, verdict,
  reason and exact evidence.
- null only while unfinished, with status `partial` and no replacement.

Every completed decision needs exact evidence using `history`, `reader_message`
or `answer`, with `index` and `quote`, as in the original rubric. Use source and
visible excerpts to establish the relevant claim rather than quoting only a
related turn label. `additional_findings` uses the same decision schema for
non-target answer IDs; never repeat an ID already in the target list.

Validate without merging:

```bash
.venv/bin/python plans/260910-context-policy/20260911-v2-broader-review-audit/verify_corrections.py --corrections plans/260910-context-policy/20260911-v2-broader-review-audit/review/corrections.json
```

Also write `review/REVIEW.md` describing retained versus corrected criteria,
changes to verdicts, remaining ambiguity and process limitations. Report the
ambiguous count explicitly in breakdown tables. The frozen classes distinguish
historical recall from attribution and different-value from same-value updates;
your prior combined classes were aggregations, not the planned five-class view.
The author audit already records raw counts in those frozen classes.

Write only within the new audit `review/` folder. Do not run inference, training,
paid APIs, uploads, messages or additional agents without user authorization.
The 98 uncaptured conditions remain missing. This correction does not authorize
training labels or complete the original 360-condition evaluation.
