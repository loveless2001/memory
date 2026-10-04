# Independent reference review — 120-case broader-eval candidate

Reviewer: Claude Opus 5 (`claude-opus-5`), via Claude Code. Independent of the
source-only author, not independent data and not human review.
Candidate freeze: `1465222774e1714bfc4d8e42d60974dd6a8af97db44fa05a02cde181ab716c40`.
Candidate files unchanged; review written only to `review/`.

## Counts

| Status | Count |
| --- | --- |
| accept | 114 |
| reject | 6 |
| ambiguous | 0 |
| insufficient_source | 0 |

All 20 complete base histories read in full, plus all 40 synthetic continuations
and all 120 questions/references.

## What was checked

- **Passage identification.** For every historical question, the whole history was
  searched for other passages matching the descriptive cue. Several families
  contain near-miss passages — F003 has five bios (only T12/T28 match the cues, and
  they genuinely disagree: "fintech clients" vs "growth-focused investors");
  F004 has other convention passages (T130 names an All Might *pin*, T156 an All
  Might *figure*, neither is a "diary entry"); F007 has five distinct summits;
  F018 has four self-written passages sent to four different target languages.
  In every case the cue resolves to exactly one passage. No ambiguity found.
- **Withdrawals / abstain cases (20).** Every user turn after each withdrawal was
  read for re-establishment in any wording, not just keyword matches. None found.
  Assistant restatements (e.g. F001 T157, F014 T71) were correctly not treated as
  establishing user facts. Several withdrawals sit at or near the last user turn
  (F002 T189/191, F013 T222/224, F018 T234/236), leaving no room for re-establishment.
  Near-misses judged and rejected as merely topical: F011 T221 (tolerance for
  spicier dishes), F010 T288 (brutalist web design), F016 T182 (fictional draft).
- **Synthetic continuations (40).** Each declaration post-dates its withdrawal, is
  absent from the base and from the sibling variant, and the answers rest on the
  declaration rather than on the withdrawal. 15 explicit negatives, 5 alternate
  values, as documented.
- **Mechanical pre-pass.** All 120 proposed evidence spans re-hashed against the
  parsed histories: all valid. All references ≤ 90 words.

## The six rejects — one defect class

Every reject is the same issue, and no reject concerns *which* passage or *which
person* the answer identifies — those are correct in all six.

| Case | Reference asserts | Source status |
| --- | --- | --- |
| F001-Q4 | Kwame Mensah … **his** final semester | first-person email, signed with a name only |
| F006-Q4 | Aisyah … **her** brother | gender never stated; only assistant text uses the name |
| F014-Q4 | Lena describes **her** own ritual | user's framing says "what **they**'re really saying"; only assistant T71 says "her" |
| F016-Q4 | Lars Henriksen reports **his** results | sender's gender unstated ("Ms. Johansen" is source wording for the *addressee*) |
| F018-Q4 | May had taken **her** around the riverside | user only asks which grammatical form the assistant chose (T4–T5) |
| F020-Q4 | Karen … **her** own container; Jon … **he** need not | unstated; the question itself uses "their"/"they" |

Each is unsupported specificity: an attribute inferred from a first name and
asserted in a reference whose own `task_scope` rule is to attribute *within the
identified passage*. The packet asks reviewers to flag unsupported specificity,
and instructs that a correction belongs in `reject`, not in an `accept` record —
hence reject rather than accept-with-note. Each carries a pronoun-free or
neutral `suggested_answer`; the repair is a one-line rewording, not re-authoring.

**Not rejected, for contrast** (pronouns that *are* grounded): F008-Q2 (source says
"**She** showed particular skill"), F008-Q4 and F009-Q4 (the user's own framing turn
says "she"), F019-Q4 (the writer's gender comes from the user's own wording at T60,
though not from the cited span — noted in that record). F004-Q2's "her version 2 hero
costume" attributes a costume to a named public fictional character rather than
inventing an attribute of a person in the source, so it was accepted; a stricter
reviewer could treat it as the same class.

## Other observations (not defects)

- F010-Q5 and F011-Q5: the synthetic declaration drops a qualifier the question
  keeps ("interesting" architecture; "regularly"). Accepted — negating the broader
  category entails the narrower case — but the wording mismatch is worth knowing.
- F018-Q2 renders the source's "unmistakable fiery kick" as "a fiery spicy kick";
  a gloss, not an added source detail.
- F019 Q2 and Q4 cite the same passage (T48); both are independently answerable
  and neither leaks the other.
- Several histories contain consecutive user turns with no assistant reply
  (F002 T104/T105, F005 T190, F008 T196/T197, F009 T140, F015 T200/T201,
  F017 T226/T227, F020 T212/T213). Irrelevant to these cases, but it means some
  variants append a second consecutive user turn.
- F013: T2 and T138 are near-duplicate "PhD reflection" cues with unrelated content —
  no actual ambiguity, but a template-similarity signal consistent with the packet's
  own warning that near-duplicate independence is not established.

## Limitations of this review

- Model review, not human review, and not a benchmark performance score. It judges
  the questions and reference answers only; no reader answers exist for this candidate.
- Independence is limited: a separate reviewer from the author, on the same data,
  not blinded to the proposed answers.
- Most of the review was performed by delegated per-family reviewers reading one
  complete history each, with the coordinating reviewer doing the mechanical
  span/word-count pass, reading every question, answer and cited passage, reading
  F010, F015, F018 and F019 end-to-end directly, and adjudicating all cross-family
  consistency. The six rejects were decided centrally after one delegated reviewer
  raised the pattern on F020 — the other five had been accepted by their reviewers
  and were downgraded on re-review, which is itself evidence that single-pass
  per-family review under-detects a defect class spread thinly across families.
- Verdicts rest on the packet's stated conventions (`quoted_text_only` ownership,
  historical textual scope, withdrawal semantics). A reviewer reading "unsupported
  specificity" more leniently would return 120 accepts; one reading it more strictly
  would also flag F004-Q2.
- Overlap caveats carry forward unchanged: 19 connected components of exact-turn
  sharing within the new families (17 including prior families), near-duplicate
  independence not established, retrieval cues present in question wording.

## Unresolved questions

1. Should the six pronoun cases be repaired in place and re-frozen, or recorded as
   known-minor and left as-is? They do not change which passage or person is correct.
2. Is F004-Q2's "her version 2 hero costume" (a named public fictional character)
   in or out of the same defect class? This review put it out.
3. Should question wording be normalised to the neutral "they/their" style that
   F020-Q4's question already uses, to keep references from inheriting the issue?
