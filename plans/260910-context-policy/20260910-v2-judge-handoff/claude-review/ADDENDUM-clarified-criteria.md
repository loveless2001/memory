# Addendum — recoding under the author's clarified criteria (2026-09-10)

Editorial correction by Codex at the user's request on 2026-09-10. The changes
below correct reporting and metadata; they do not constitute a new independent
review or alter any per-case judgment in the recoded file. The prior addendum and
recoded file are retained under `editorial-history/20260910-clarification-corrections/`.

The reference author answered the six unresolved questions in `REVIEW.md` after my review was saved.
Two answers change how criterion booleans should be assigned. **No verdict changes: 25 pass / 17 fail,
still 42/42 agreement with the author.** The blind first-pass records remain in `review.json`
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

Comparing the recoded and blind answer records shows **17 boolean changes and one
reason change**: 13 `task_complete`, three `supported_in_visible_state`, one
`source_consistent`, and the explanation for C007-B. Sixteen of the original
18 boolean differences with the author close; the C007-B source-consistency
recoding introduces one additional convention difference, leaving **three residual
cells** (a net reduction of 15). All three reflect the same schema distinction — the author's
2026-09-10 schema had no `withdrawal_compliant` field, so restatement-only failures (C007-B, C016-B,
C020-B) were recorded as `source_consistent: false`. Under the clarified split those are
`withdrawal_compliant: false` with `source_consistent: true`. Same failure, different column; not a
disagreement.

## 2. Corrections to my saved `REVIEW.md`

Two corrections concern the failure taxonomy. Verdicts are unaffected; the recoded
explanation for C007-B is also corrected as described below.

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
Deterministic decoding does not itself preclude inference across sampled cases.
Here, however, the cases were selected for development, some share source
histories, and no sampling or randomization design justifies treating discordant
pairs as independent draws from a target population. The nominal sign-test
calculation therefore does not establish a generalizable rendering effect.
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
  attributing its output as `[T150 user] reading format: UNKNOWN.` misleadingly presents
  derived text as the user's words. The derived record should
  identify its origin, e.g. `[derived constraint from user T150]`. Existing captures stay unchanged;
  attribution is corrected in a prospective revision. User-role turns in the explicitly synthetic
  fixtures were intentional experimental inputs and are not part of this defect.
- **Mode labels were never scored.** C010 is better labelled `abstain` than `clarify`; `personalized`
  would not fit an answer establishing no personal preference. Recorded as a metadata issue; the
  frozen reference and the answer verdicts are unchanged.

## 5. Corrected coverage and remaining limits

There are **19 pairs with different actual input messages and two identical-input
controls, C010 and C011**. These are input-contrast counts, not a certified number
of independent observations. The earlier "effective paired n = 15" claim is
withdrawn; neither 42 answers nor 19 changed-input pairs establishes an independent
sample size.

Different-value restatements are present. In **C001**, user T0 prefers coffee to
tea, T2 withdraws that preference, and T4 explicitly establishes tea. In **C009**,
user T0 gives Tuesday as the meeting day, T2 withdraws it, and T4 establishes
Thursday. C004 separately tests re-establishing the same reading-format value.
These are short synthetic controls, not evidence of broad chronology competence.

C006-A asserts a withdrawn reading preference while an assistant acknowledgment
restating that preference remains visible. This is consistent with copying that
acknowledgment, but the experiment does not isolate which fragment caused the
answer. The causal claim "demonstrably exploited" is withdrawn. The misleading
assistant statements in H015 and H016 remain relevant archive-quality limitations.

Nothing here licenses training, and the proposed 120-question broader suite
remains unauthored and unscored.

## 6. Preservation and recoding provenance

The independent blind artifacts are `review.json` and `reference-review.json`.
Their hashes match the preceding Codex check and remain unchanged during this
editorial correction. There is no earlier recorded baseline proving byte-for-byte
preservation before that check. The preservation manifest states that boundary.

`review-recoded.json` is a post-unblinding interpretation under clarified criteria.
Its `prior_verdicts_seen` field is true for this stage; the original blind record's
field remains false. Its metadata distinguishes the original Claude judgments,
Claude's recoding, and Codex's subsequent editorial metadata correction. No
answer verdict, criterion boolean, evidence quotation or reference decision is
changed by the editorial correction.
