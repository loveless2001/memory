# Correction pass on the broader answer review

Correction reviewer: Claude Opus 5 (`claude-opus-5`), Claude Code, user-controlled session.
Explicitly **unblinded** correction over the **117 audit targets** — not a new review of 262 answers.
Original `claude-review/review.json` and `REVIEW.md` untouched; both hash bindings preserved.
`verify_corrections.py --corrections …` → **PASS**.

## Outcome

| | Original | Corrected (candidate merge) |
| --- | ---: | ---: |
| pass | 106 | **104** |
| fail | 155 | **157** |
| ambiguous | 1 | **1** |

Decisions: **115 replace, 2 retain** (plus 1 retained additional finding). Only **two verdicts
change** — C079-B and C026-A, both original passes. Every other replacement corrects
per-criterion booleans on answers that were already failed, exactly as the audit anticipated.

## What I accepted from the audit, and why

**1. `task_complete` requires the requested value to be correct — accepted.** My original rule
scored it as mere responsiveness and pushed correctness into `source_consistent`. Re-reading the
frozen criterion ("answers the current question and every necessary component", with abstention on
an answerable question counted incomplete), the audit's reading is better: it tracks task success,
not whether prose was emitted. Criterion effect: `task_complete` true **223 → 136**.

**2. `supported_in_visible_state` assesses the answer's claims, not evidence availability —
accepted.** I had been checking whether the cited turn was *present* in the view, which made the
criterion nearly vacuous (256/262 true). Effect: true **256 → 166**.

Applied **non-mechanically**, per the instruction. Three deliberate departures from flipping:

- **13 different-value answers** (C024-B, C036-C, C037-A/B/C, C045-A/B/C, C050-A/C, C076-A/B,
  C084-B) reach the value the later explicit user statement establishes, and that statement was
  visible in full. `supported_in_visible_state` and `task_complete` stay **true**; the failure sits
  in `source_consistent` + `withdrawal_compliant`, because the *explanation* infers the negative
  from the withdrawal alone.
- **10 name-inferred-gender answers** keep `task_complete` **true** — the attribution asked for is
  correct and complete, and the unsupported added attribute is scored under source consistency.
  This follows the audit's explicit warning not to conflate the two.
- **C020-B/C** keep `supported_in_visible_state` **true**: both the user's original post (T0) and
  the assistant's rewrite (T1) were visible, so the wording is traceable to visible text. The defect
  is that an assistant rewrite cannot establish the user's own passage — a source-consistency
  failure. This is an intentional, explained instance of the flagged false/true combination.
  I additionally set their `task_complete` false, which the audit had not flagged: the stated focus
  in the source is "safety-focused", and both answers recharacterise it.

## The four spot checks

- **C079-B — pass → fail.** Its final preference is right, but it states the T267 statement was
  "later" withdrawn at T172, while the source order is T172 withdrawal → T267 reinstatement. That is
  the same false chronology for which I failed C069-A/B, so consistency requires failing it:
  `source_consistent` and `withdrawal_compliant` false, `task_complete` and support true.
- **C069-A/B — corrected, verdict unchanged.** Same defect class; I have now also set
  `withdrawal_compliant` false so the three are scored identically.
- **C026-A — pass → fail.** The negative matches the later assertion, but the explanation rests
  only on the earlier positive being "withdrawn as a current detail" and never invokes the later
  negative. Withdrawal-only inference to a negative — the same defect I failed in C036-C.
- **C036-A — retained as pass.** Unlike C036-C it anchors on the later turn as well ("withdrawn by
  the user in [T260] and confirmed in [T262]"); T262 *is* the later explicit negative. Calling it
  "confirmed" is loose wording, not withdrawal-only inference.

## C073-B — ambiguity retained

Retained ambiguous, decided from the question and source rather than from the reference naming
Temple. "Which university degree and internship organization" supports both readings — the degree
that is a university degree, or which university's degree — and T24 supplies material for both. The
ambiguity is in the question, not the answer.

## First-person echo

Not treated as an ownership failure anywhere; I found no body where the referent stopped being the
user. `ownership_correct` is false on exactly one answer (C086-C, a reversed exchange). The audit's
lexical count of 25 passing bodies beginning with a first-person echo is recorded as a lexical
observation only, and my earlier "~30 answers" sensitivity remark should not be read as a score
change — I withdraw it as a quantitative claim.

## Corrected results in the five frozen classes

My earlier three classes were aggregations; these are the planned distinctions. Ambiguous shown
explicitly. Cells are pass/n.

| Frozen class | Depth 0 | Depth 1 | Depth 2 | Total pass | Ambiguous |
| --- | ---: | ---: | ---: | ---: | ---: |
| Historical recall | 0/30 | 27/30 | 28/30 | 55/90 | 1 (depth 1) |
| Attribution | 0/14 | 9/14 | 9/15 | 18/43 | 0 |
| Withdrawal / unknown current value | 1/15 | 0/15 | 0/15 | **1/45** | 0 |
| Later different value | 6/14 | 11/14 | 9/14 | 26/42 | 0 |
| Later same value | 2/14 | 2/14 | 0/14 | **4/42** | 0 |

| Depth | n | pass | fail | ambiguous |
| --- | ---: | ---: | ---: | ---: |
| 0 | 87 | 9 | 78 | 0 |
| 1 | 87 | 49 | 37 | 1 |
| 2 | 88 | 46 | 42 | 0 |

The two weakest classes are unchanged by the correction and remain the substantive finding:
**withdrawal/unknown 1/45** and **later same value 4/42**, both flat or worse across retrieval
depth, while historical recall and attribution improve sharply from depth 0 to depth 1.

## Scan of the original passes for the same defect class

I scanned all 106 original passes for withdrawal/chronology explanation defects. Four were sound
(C029-B, C031-C, C054-A, C076-C — each either cites the later assertion or correctly derives
*unknown* from the withdrawal). One is recorded in `additional_findings`:

- **C062-B — retained.** Correct "Yes" with the correct order (withdrawn earlier, re-established
  later), but says the re-establishment was "in the same user message" when T260 and T262 are
  different messages. The asserted order is right, unlike C069/C079, so verdict and criteria stand;
  recorded for transparency.

No further failures were found outside the 117 targets.

## Limitations

- Correction only. The 145 non-target answers keep their original judgments; this pass does not
  re-derive them.
- **Blinding is now spent.** This pass is unblinded by design: I read the audit, and I opened
  `sealed-map.json` here to obtain exact frozen-class labels (my rule-based reconstruction
  disagreed with the audit on 17 targets; the sealed map reproduces the audit's table exactly, 0
  mismatches). The sealed map was **not** opened before the original review was saved.
- Prior exposure unchanged and still disclosed: I performed the v1 reference review, the v2 delta
  review, and the original answer review of these same families.
- Two criterion re-readings are interpretive, not mechanical. If the audit's readings were rejected,
  `task_complete` and `supported_in_visible_state` would revert; verdict totals would move only by
  the two spot-check flips.
- Collection is still **262/360 captures, 88/120 questions**, a schedule prefix, with related
  questions per family and shared sources — not independent trials. A validator PASS is structural,
  never semantic certification. EOS was verified from token records in the run audit, not from
  decoded prose.
- No inference, training, paid API, upload or additional agent was run; writes are confined to this
  audit `review/` folder. No training labels follow from this pass.

## Unresolved questions

1. Should `supported_in_visible_state` stay true for the 13 different-value answers whose correct
   value was visible but whose explanation is withdrawal-only? I retained true; failing it would
   move 13 booleans without changing verdicts.
2. Is C020-B/C's `task_complete` false defensible given the audit did not flag it? I judged the
   stated focus mischaracterised; a lenient reading would call "safety" mentioned and pass it.
3. C073-B's scope ("which university degree") is still unsettled and remains the single ambiguous
   verdict.
