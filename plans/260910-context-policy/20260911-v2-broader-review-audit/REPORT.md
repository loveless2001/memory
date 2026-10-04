# Saved answer review reconciled; correction pass needed

The independent model review covers all **262 captured answers** and passes
the packet/schema/exact-quote validator. Its recorded counts are **106 pass,
155 fail and one ambiguous**. The original review files are preserved and
hash-bound in `audit.json`. These are reproduced reviewer verdicts, not accepted
corrected scores. The collection remains 262/360, with 98 conditions missing.

The audit found criterion inconsistencies and a clear false chronology in a
parent pass. It prepared [a separate correction handoff](../../../CLAUDE-BROADER-CORRECTIONS.md)
covering 117 distinct answers. No original judgment was rewritten, no replacement
verdict applied, and no training label exported.

## Raw counts under the frozen classes

| Retrieval depth | Captured | Pass | Fail | Ambiguous |
| --- | ---: | ---: | ---: | ---: |
| Zero | 87 | 9 | 78 | 0 |
| One | 87 | 50 | 36 | 1 |
| Two | 88 | 47 | 41 | 0 |

| Frozen class | Zero: pass/n | One: pass/n | Two: pass/n |
| --- | ---: | ---: | ---: |
| Historical recall | 0/30 | 27/30 | 28/30 |
| Withdrawal/unknown current value | 1/15 | 0/15 | 0/15 |
| Attribution | 0/14 | 9/14 | 9/15 |
| Later different value | 6/14 | 11/14 | 10/14 |
| Later same value | 2/14 | 3/14 | 0/14 |

The one ambiguous answer is in historical recall at depth one; that cell also
has two failures. The review report's `historical_recall` aggregate combined
recall and attribution (133 captures); its `current_after_withdrawal` aggregate
combined different-value and same-value branches (84). Those totals reconcile,
but they hide the planned distinctions above. `audit.json` also records every
family's counts and each criterion's raw true/false/null totals.

On the **87 questions with all three views**, zero-to-one transitions are
43 fail-to-pass, two pass-to-fail, seven pass-to-pass, 34 fail-to-fail and one
fail-to-ambiguous. Zero-to-two transitions are 40 fail-to-pass, three pass-to-fail,
six pass-to-pass and 38 fail-to-fail. The common-set depth-two count is 46/87;
the additional single-view question supplies the extra pass in 47/88. These
are paired descriptions of the original judgments, not action labels or
independent observations.

## Why the criteria need reconciliation

- **85 answers** have `task_complete: true` while the reviewer's own reason
  describes an incorrect requested value, invented core content, ignored later
  assertion, wrong requested detail or reversed exchange. The frozen criterion
  requires correctness and completeness, not just a direct response. For example,
  C033-B says a later reinstatement is invalid and answers “No” despite the source
  establishing “Yes”; the reviewer rejects it but marks the task complete.
- **107 answers** have `source_consistent: false` and
  `supported_in_visible_state: true`. That combination is a request for inspection,
  not a logical contradiction in every possible case. The process note describes
  matching turn references to cited spans; related turn presence does not by
  itself support the answer's claims, source role or chronology. Assess actual
  text and character slices, not just availability of relevant evidence.
- **C079-B**, an original pass, says a T267 statement was *later* withdrawn at
  T172. The source has T172 withdrawal followed by T267 reinstatement. Its final
  preference is correct, but its chronology is false. Compare C069-A/B, both
  rejected for this same class of false explanation despite a correct value.
- **C026-A and C036-A**, also original passes, need a consistent reading of what
  “this preference/detail was withdrawn” refers to. Their later negative values
  are supported; their explanations may conflate that evidence with withdrawal
  of the earlier positive. These are proposed review concerns, not applied fails.
- **C073-B** remains ambiguous: it names the Real Estate degree and internship
  but omits Temple. The question's “which university degree” wording does not
  settle that scope simply because the reference includes the university name.
  No unilateral pass/fail ruling is imposed by this audit.

The two large flag sets overlap. Together with the three pass spot checks and
the existing ambiguity, they identify **117 distinct targets**, not 196 new
failures. Much of the work concerns per-criterion validity on answers already
rejected; correcting those booleans need not change their overall verdicts.
The author audit is unblinded and does not substitute for the requested
independent correction pass.

## Interpretation decisions and provenance limits

First-person echo is not automatically an ownership error when the referent
remains clearly the user. A lexical scan found 25 passing bodies beginning with
an explicit first-person echo; it does not establish 25 ownership failures or
justify the review report's approximate 30-pass sensitivity calculation.
Likewise, a correct final value does not excuse an unsupported explanation;
evaluate the relevant source and withdrawal criteria separately.

The reviewer self-identifies as Claude Opus 5 via the user-controlled Claude
Code session. The JSON `model_version` field instead discusses the unknown
answer-producing model; reviewer identity is available in `reviewer` and the
report, but the field is misused. The correction template explicitly requests
the correction reviewer's own model/version. No identity is independently
verified by the structural validator.

The reviewer discloses earlier exposure to the same sources and references from
the parent and delta reference reviews. Actual messages reveal retrieval depth.
The process note does not establish a fresh full-history semantic audit or
claim-level entailment check merely by matching turn identifiers. EOS is not
recoverable from decoded prose alone; token/EOS records were separately verified
in the run audit. Preserve these limits rather than treating a validator PASS
as semantic certification.

The severe withdrawal and same-value problems appear in this selected captured
prefix. They do not prove retrieval never helps in general, irreversible
forgetting, a general model capability, or a learned policy failure. Family and
shared-source dependence remain; no confidence interval or independent sample
size is inferred. The raw pattern does not justify spending on the 98 missing
conditions before resolving the review and deciding the next behavioral repair.

## Next step

Use the [Claude correction handoff](../../../CLAUDE-BROADER-CORRECTIONS.md).
It requests retain/replace decisions with source evidence, a scan of remaining
passes for the same defect class, and separate recording of additional findings.
The original review and this audit are frozen. The new validator checks parent
and audit hashes, complete target coverage, exact evidence and the candidate
merged review; it never certifies semantic truth. It can write a separate merged
review only after a complete correction is supplied, and refuses overwrites.

```bash
.venv/bin/python plans/260910-context-policy/20260911-v2-broader-review-audit/verify_corrections.py
```

No additional inference, GPU run, paid judging, training, source transfer,
commit or push was performed in this continuation. Training remains paused.
