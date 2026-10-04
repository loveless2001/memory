# Addendum — recoding under the author's clarified criteria (2026-09-10)

The reference author answered the six unresolved questions in `REVIEW.md` after my review was saved.
Two answers change how criterion booleans should be assigned. **No verdict changes: 25 pass / 17 fail,
still 42/42 agreement with the author.** The blind first pass is preserved verbatim in `review.json`
and `reference-review.json`; the restated booleans live in the clearly-labelled copy
`review-recoded.json`. Where the two differ, `review.json` is the blind record and `review-recoded.json`
is the current-convention record.

## 1. Criterion definitions (author's reading adopted)

- `supported_in_visible_state` = **valid evidential support** — the claim follows from the actual
  reader messages with the correct person, chronology and qualification — not mere textual presence.
  An assistant acknowledgment mentioning paper books does not support a current paper-book preference.
- `task_complete` = a **correct and complete** answer, not merely one that addresses the question.
- The no-restatement rule lives in `withdrawal_compliant`, separately from `source_consistent`. "The
  earlier text mentioned X" can be visibly supported and still violate no-restatement.

Recoding the 17 failures under these definitions changed 18 boolean cells and closed 15 of the 18
differences with the author. **Residual: 3 cells**, all the same schema artifact — the author's
2026-09-10 schema had no `withdrawal_compliant` field, so restatement-only failures (C007-B, C016-B,
C020-B) were recorded as `source_consistent: false`. Under the clarified split those are
`withdrawal_compliant: false` with `source_consistent: true`. Same failure, different column; not a
disagreement.

## 2. Corrections to my saved `REVIEW.md`

Two, both in the failure taxonomy. Verdicts and per-case reasoning are unaffected.

- **C007-B was misfiled.** I read "You do not have a stated preference for any specific clothing
  fabrics" as asserting a known lack of preference. On re-reading, "stated" makes it a claim about the
  *record*, and the following sentence ("No current preference is established in the archival record")
  is unambiguously record-level. It belongs with C016-B and C020-B: correct uncertainty, forbidden
  restatement. The author's coding was right here and mine was not.
- **The pattern-1 count was wrong.** `REVIEW.md` says "(9 answers)" while listing 10 IDs, and omits
  C006-A, which asserts a withdrawn value as current and belongs in that class.

Corrected taxonomy of the 17 failures — reported separately, per the author's point that equal binary
scores do not imply equal severity:

| class | n | answers |
|---|---:|---|
| wrong current value, or a negative/opposite inferred from a withdrawal | 11 | C002-B, C003-A, C003-B, C006-A, C006-B, C008-B, C015-A, C017-B, C018-A, C019-A, C019-B |
| correct uncertainty, forbidden restatement of the withdrawn value | 3 | C007-B, C016-B, C020-B |
| ownership — supplied draft read as biography | 2 | C010-A, C010-B |
| over-abstention despite valid visible information | 1 | C004-A |

Any graded severity score needs its own prospective definition before it is used; this table is a
descriptive split of an already-frozen binary gate, not a new metric.

## 3. Statistical framing — correction to `REVIEW.md`

Generation was **greedy argmax, one decode per condition**, deliberately. `REVIEW.md` reports a
two-sided sign test (p ≈ 0.004) over the 9 discordant pairs. Withdraw that as an inferential claim.
With a deterministic decode and n=1 per condition, the discordant-pair count describes *this packet's*
paired pattern and nothing beyond it; there is no sampling distribution for it to be a p-value over.
**8/21 vs 17/21 stands as a descriptive count for this packet only.** A generalizable effect claim
needs a prospectively specified evaluation on new source families. Repeat greedy decoding would check
numerical reproducibility, not create independent examples; stochastic repetition would answer a
different question and would need a frozen decoding protocol first.

## 4. Points confirmed by the author, recorded here

- **Retained assistant acknowledgments were deliberate.** The intervention changed only annotated
  user-withdrawal rendering. It tests that narrow change amid retained echoes and does **not** test
  removal of withdrawn information; acknowledgment removal should be a separately controlled
  intervention. The author also confirms that supplying `UNKNOWN` bundles semantic preprocessing with
  a copyable answer, so the improvement cannot establish better memory reasoning. My REVIEW.md
  concerns 1 and 2 are accepted rather than disputed.
- **The verbatim-user-quotation rendering is a harness design defect.** Normalization was intentional;
  presenting its output as `[T150 user] reading format: UNKNOWN.` was not. The derived record should
  identify its origin, e.g. `[derived constraint from user T150]`. Existing captures stay unchanged;
  attribution is corrected in a prospective revision. User-role turns in the explicitly synthetic
  fixtures were intentional experimental inputs and are not part of this defect.
- **Mode labels were never scored.** C010 is better labelled `abstain` than `clarify`; `personalized`
  would not fit an answer establishing no personal preference. Recorded as a metadata issue; the
  frozen reference and the answer verdicts are unchanged.

## 5. Unchanged conclusions

C010/C011 byte-identical A/B prompts (effective paired n = 15, not 42); the acknowledgment leak that
C006-A demonstrably exploited; source contamination inside H015 and H016; and the absence of any case
testing a withdrawal followed by an explicit *different* value. Nothing here licenses training, and
the 120-question broader suite remains unauthored and unscored.
