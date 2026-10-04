# Delta review — v2 neutral-wording correction

Reviewer: Claude Opus 5 (`claude-opus-5`), via Claude Code.
Candidate freeze (v2): `3a161e9ef2a28dc83e432f6b878957181181aa40a17da2e77b9c9969d01d7f05`.
Parent review: `550f5b5cc5633bff8243a90a9f5f417775b73a92ce7c4ed764a8acea76b12f43` (114 accept, 6 reject) — unchanged.

## Scope and counts

This is a **bounded twelve-case delta review**, not a fresh 120-case review.

| | Count |
| --- | --- |
| Delta cases reviewed here: accept | 12 |
| Delta cases: reject / ambiguous / insufficient_source | 0 |
| Additional findings among unchanged cases | 0 |
| Unchanged cases carrying the **parent** review's accept | 108 |

The 108 are inherited, not re-judged. This review does **not** assert 120 independently
re-reviewed accepts.

## Provenance checks (independent of the supplied scripts)

- `verify.py` PASS; `revision.py` PASS.
- All 20 histories and `variants.json` are **byte-identical** to v1 (`cmp` on each file),
  so the parent review's source and chronology work transfers intact.
- Re-diffed v1 vs v2 `cases.jsonl` directly: exactly 11 answer changes and 2 question
  changes across 12 cases, **zero undeclared edits**, zero evidence-span changes, and the
  manifest's 108 unchanged IDs match the actual unchanged set.
- All 12 cited evidence spans re-hashed against the histories: valid.
- The manifest's parent hashes match v1's freeze and my v1 review file on disk.

## The twelve changes

All twelve preserve the right person, passage, direction and requested detail.

- **Six required repairs applied verbatim** from the parent review's `suggested_answer`
  (F001-Q4, F006-Q4, F014-Q4, F016-Q4, F018-Q4, F020-Q4). Each was checked back against
  its source passage, not just against the suggestion text.
- **F004-Q2** drops "her" before "version 2 hero costume". This resolves the borderline case
  the parent review explicitly left open: the answer now needs only T18's own wording
  ("I cosplayed as Uraraka (version 2 hero costume)"), with no external character knowledge.
- **F008-Q2, F008-Q4, F009-Q4, F019-Q4** were accepted in the parent review and their
  pronouns *were* source-grounded — F008-Q2's source says "**She** showed", and for F008-Q4
  and F009-Q4 the user's own framing turns say "she". These edits are stylistic consistency,
  correctly described as such in the report rather than as error corrections.
- **Two question edits** (F009-Q4, F013-Q2) are stylistic; neither leaks its answer, and
  F013-Q2's "the uncle" merely reuses a term already present in the question's first clause.

Two non-blocking wording observations, both accepted:

- **F008-Q4** is the weakest of the twelve. "Ruth describes a personal experience" conveys
  *whose* experience only by implication, where the sibling repairs kept an explicit
  "their own" (F014-Q4) / "their own" (F016-Q4). Parity wording would be an improvement,
  not a correction.
- **F008-Q2** now reads "…; skill in mediation helped colleagues…" with no possessive —
  grammatically clipped, though the attribution stays clear from the sentence.

## Cross-family defect scan (all 120 authored queries and references)

The parent review's failure mode was a defect class spread thinly across families that a
per-family pass missed, so the scan was run packet-wide and mechanically, not family by family.

1. **Lexical pronoun scan** over all 120 queries, answers *and* claim strings:
   **zero** occurrences of he/she/his/her/him/hers/himself/herself. The report's claim holds.
2. **Unsupported-specificity sweep**: for every case, answer content words were checked
   against the cited evidence spans plus the question text. 81 cases raised tokens, all
   resolved on inspection as stemming artifacts ("ate"/"eat", "mediation"/"mediating"),
   template boilerplate (the abstain and "You explicitly said" forms), or benign glosses.
   No new invented entity, attribute, number or relationship was found.
3. **Gendered kinship/honorific check**: every such term in an answer is source-supplied —
   "brother" (F006-Q4, T38), "uncle" (F013-Q2, T4), "mother" (F019-Q4, from the source's
   "my mom"), "Ms. Johansen" (F016-Q4, T0). Consistent with the stated convention of keeping
   quotations, names, honorifics and kinship terms as supplied.

Carried over from the parent review, still present and still not defects: F018-Q2 glosses
"unmistakable fiery kick" as "a fiery spicy kick"; F014-Q1 renders "the sands"/"the shore"
as "the beach sands". Both were noted and accepted in v1; neither is a new issue, so
`additional_findings` is empty and no inherited accept is blocked.

## Limitations

- Delta review only. For the 108 unchanged cases I relied on the parent review's source and
  chronology work; I did **not** re-read all twenty full histories for this pass.
- The parent review's process caveat is preserved and still applies to those inherited
  accepts: it used **delegated per-family readers with central adjudication**, not one reader
  independently reading every full history. Five of its six rejects surfaced only when a
  pattern found in one family was checked across the packet — which is why the scan above is
  packet-wide and lexical rather than another per-family pass.
- The pronoun scan is lexical. It certifies the absence of this specific accidental addition,
  not the absence of every possible unsupported attribute or inference.
- Model review, not human review, and not a performance score. No reader answers exist for
  this candidate; no inference or training was run.
- Data limitations carry forward unchanged: same synthetic release, six related cases per
  family, 19 exact-turn components within the new families (17 including links through prior
  families), near-duplicate independence not established, retrieval cues in question wording,
  deliberately explicit synthetic updates.

## Unresolved questions

1. Adopt parity wording for F008-Q4 ("their own experience") and restore a possessive in
   F008-Q2? Both are readability fixes; neither changes what the answers identify.
2. The neutralisation was applied to four cases whose pronouns were source-grounded. Is the
   convention meant to override source-grounded gender in authored prose, or only to bar
   name-inferred gender? The current mix is defensible but leaves the rule under-specified.
