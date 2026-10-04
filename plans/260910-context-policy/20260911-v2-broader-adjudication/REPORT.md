# Broader review: approved rulings applied separately

The current adjudicated review records **104 pass, 157 fail and one ambiguous**
across 262 captured answers. Applying the user's approved rulings changes
criteria, not these verdict totals. The original Claude review and its unblinded
correction pass remain unchanged. This final layer is an explicitly attributed
**Codex author adjudication**, not another independent model review.

## Applied rulings

1. **Whole-answer support:** the thirteen correct-negative/withdrawal-explanation
   answers now have `supported_in_visible_state: false`. Each was inspected
   individually, and both the withdrawal and later negative statement were found
   verbatim in its actual visible messages. The final negative is supported;
   the overlay retains Claude's interpretation of the withdrawal sentence as an
   invalid explanation of it. Under that interpretation the whole answer fails
   support. `adjudication.json` records the individual wording and exact source,
   visible-message and answer quotations.
2. **C020-B/C:** restore `task_complete: true`. T0 itself says autumn menu,
   safety-focused campaign and warm, comforting atmosphere. Both answers supply
   the requested season and focus. The retained source failure is narrowed to
   the added assurance about guests from the moment they enter, rather than
   incorrectly treating warmth/comfort as assistant-only concepts. Whole-answer
   support is false because visible assistant wording cannot establish that
   assurance as part of the original user passage.
3. **C073-B:** retain ambiguous. The existing question does not unambiguously
   request the university name. The reference's inclusion of Temple cannot add
   a retrospective requirement. A future question may explicitly ask for degree
   subject, university and internship organization; the frozen question is unchanged.

The same support rule also applies to C026-A's retained explanation failure and
the false chronologies in C069-A/B and C079-B. With C020-B/C, these are six related
consistency cases beyond the original thirteen. In total, **19 support flags
change true → false and two task-completeness flags change false → true**.
There are nineteen replacement entries and one retained ambiguity; every other
judgment is byte-equivalent at the parsed-object level to the Claude-corrected
review. No verdict changes in this author overlay.

## Interpretive boundary

Missing a citation to a later statement is not itself a failure. A response
that independently states two supported facts need not reveal how it reached
its conclusion. This overlay does **not** prove that the reader internally
inferred a negative from withdrawal, or that its memory was actually erased.

For these thirteen answers, the prior correction review's reading of the
withdrawal sentence as an operative explanation is explicitly retained. That
reading is interpretive, especially for short adjacent sentences such as
C024-B, C037-B and C045-C. An alternative reading as independent supported facts
would require a separately recorded change to their underlying source/withdrawal
judgments and might change verdict totals. The current support flags are
conditional on the retained explanation findings, not a new rule requiring
explicit citations. No such alternative verdict change is applied here.

## Current results and provenance

| Review stage | Pass | Fail | Ambiguous |
| --- | ---: | ---: | ---: |
| Original Claude review | 106 | 155 | 1 |
| Claude correction | 104 | 157 | 1 |
| User-approved author adjudication | 104 | 157 | 1 |

The two changes to overall verdicts occurred in the Claude correction: C026-A
and C079-B changed from pass to fail. They were not introduced by this overlay.

| Criterion | True | False | Unresolved |
| --- | ---: | ---: | ---: |
| Task complete | 138 | 123 | 1 |
| Source consistent | 147 | 115 | 0 |
| Supported in visible state | 147 | 115 | 0 |
| Withdrawal compliant | 164 | 98 | 0 |
| Ownership correct | 261 | 1 | 0 |
| Body valid | 262 | 0 | 0 |
| Within 90 words | 262 | 0 | 0 |

The matching source/support totals are an outcome of this review, not a general
requirement that those criteria be equivalent.

| Frozen class | Zero: pass/n | One: pass/n | Two: pass/n |
| --- | ---: | ---: | ---: |
| Historical recall | 0/30 | 27/30 | 28/30 |
| Withdrawal/unknown | 1/15 | 0/15 | 0/15 |
| Attribution | 0/14 | 9/14 | 9/15 |
| Later different value | 6/14 | 11/14 | 9/14 |
| Later same value | 2/14 | 2/14 | 0/14 |

Depth totals are 9/87, 49/87 and 46/88 passes; the one ambiguity is at depth one.
`summary.json` preserves criterion counts, frozen-class breakdowns and paired
transitions for the 87 complete three-view questions. The single-view question
is retained separately through the actual denominators.

Files form an explicit provenance chain: the original review plus
`review/corrections.json` produce `claude-corrected-review.json`; the user-approved
`adjudication.json` then produces `adjudicated-review.json`. `freeze.json` binds
both external review passes, the packet identity, scripts and output artifacts.
The verifier checks this overlay's exact projection and unchanged unrelated
judgments, in addition to the existing coverage and exact-evidence validator.
Structural validation does not certify semantic judgments.

```bash
.venv/bin/python plans/260910-context-policy/20260911-v2-broader-adjudication/verify.py
```

Collection remains **262/360**, a fixed-schedule prefix with 98 missing conditions,
88 represented questions and 87 complete three-view sets. Prior source exposure,
unblinded corrections, author adjudication, synthetic controls and shared-family
dependence limit interpretation. Training remains paused; no labels, inference,
GPU runs, paid judging, commits or pushes were added by this adjudication.
