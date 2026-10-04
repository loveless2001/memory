# Review of the broader reader's captured answers

Reviewer: Claude Opus 5 (`claude-opus-5`), via Claude Code, user-controlled session.
Model that produced the answers: **not stated in the packet; unknown to this reviewer.**
Validator: `validate.py` PASS on the packet and PASS on this review (`review_status: complete`).

## Coverage — actual denominators

Collection is **partial**. This is **not** a completed 120-question evaluation.

| | Actual | Planned |
| --- | --- | --- |
| Answers reviewed | **262** | 360 |
| Cases (questions) with any capture | **88** | 120 |
| Questions with a complete three-view set | **87** | 120 |
| Missing captures | **98** | — |

One case (C013) has a single answer; 87 cases have all three views. 32 questions are
absent entirely. Per the manifest, what exists is a **prefix of the fixed family/question
schedule, not a random subset**, so these results cannot be read as an unbiased estimate of
the full suite. Every included answer was reviewed; none was omitted.

## Verdicts

| Verdict | Count |
| --- | --- |
| pass | 106 |
| fail | 155 |
| ambiguous | 1 |
| insufficient_source | 0 |

All 262 answers passed the two structural criteria. I recomputed these independently from
each answer's text rather than trusting the stored flags — word counts, EOS, empty bodies,
stray standalone `ANSWER`/`RETRIEVE` markers — and all 262 agree with the stored metadata.
No malformed answer was found. Every failure is substantive.

## Breakdown by retrieval depth and case class

Both breakdowns below were derived **without opening `sealed-map.json`**: retrieval depth is
visible from each answer's own `actual_messages` (count of `tool` messages), and case class
follows from the reference's constraint kinds. The sealed map was therefore never needed and
was not opened at any point.

| Retrieval | n | pass | fail | pass rate |
| --- | --- | --- | --- | --- |
| 0 | 87 | 9 | 78 | 10% |
| 1 | 87 | 50 | 36 | 57% |
| 2 | 88 | 47 | 41 | 53% |

| Case class | n | pass | fail | pass rate |
| --- | --- | --- | --- | --- |
| historical_recall | 133 | 73 | 59 | 55% |
| current_after_withdrawal | 84 | 32 | 52 | 38% |
| abstain_unknown (correct answer is "unknown") | 45 | 1 | 44 | **2%** |

Class × retrieval, the sharpest contrast in the packet:

- historical_recall: 0/44 pass at zero retrieval, 36/44 at one, 37/45 at two.
- abstain_unknown: 1/15, 0/15, 0/15 — **retrieval does not help, and never did.**

## Failure patterns (whole-packet scan, after individual judgments)

1. **Withdrawal treated as establishing the opposite — 52 answers, the single largest defect.**
   On "unknown" questions the reader repeatedly answers a confident "No, you do not
   currently…" and cites the withdrawal as its reason. A withdrawal makes the value unknown;
   it establishes neither the old value nor its opposite. This is retrieval-insensitive: it
   occurs at 0, 1 and 2 retrievals alike, which is why the abstain class sits at 2%.
2. **Later re-establishment ignored or inverted — 39 answers** (`chrono` variants). Where the
   user re-asserts a value after the withdrawal, the reader reports the withdrawn state as
   current, often stating the inversion explicitly: C033-B — "the reassertion is not valid
   because it contradicts a prior withdrawal without explicit override"; C067-C treats T222 as
   "the most recent instruction" over the later T224; C061-A has the T259 statement "withdrawn
   in [T202]" though T202 precedes it. C072-A states the correct value and then reverses itself
   within the same answer.
3. **Abstention on answerable recall — 37 answers**, almost all at zero retrieval. Scored as
   `task_complete: false` only, with support left true, per the frozen rubric's instruction to
   keep that task failure separate. These are the "reasonable given its evidence, still
   incomplete" cases.
4. **Confabulation when evidence is absent — 6 answers.** At zero retrieval a few answers
   invent content instead of abstaining: C005-B ("comfort and intentional design" for a passage
   that says storybook charm and eco-friendly design), C066-B, C083-A (which fabricates
   quotations), C070-A, C078-A, C086-A.
5. **Gender inferred from a name — 10 answers**, the same sparse cross-family defect the
   parent reference review missed on its first pass, now recurring in the *answers*: "her
   brother" for Aisyah (C006-B/C), "she" for Lena (C016-A/B), "She suggests" for Emily
   (C018-A/C), "he is asking" for Kwame (C038-A/B), "He is asking" for Sebastián (C065-B),
   "She is addressing" for Izzy (C070-C). None of these passages states the person's gender.
   Notably the v2 references for several of these were corrected to neutral wording, so the
   reader is now *less* neutral than its own reference. Correctly **not** counted: source-supported
   pronouns for Ruth (T197 "what she's trying to convey"), Karen (T126 same pattern) and
   Margaret (T12 "She showed"), which the rubric expressly permits.
6. **Sourcing from the assistant's rewrite — 2 answers.** C020-B/C describe the campaign's focus
   with "feel embraced … from the moment they step inside", wording that appears only in the
   assistant's T1 rewrite, not the user's original T0 post ("a safety-focused promo campaign").
   The rubric is explicit that assistant rewrites cannot establish user facts.
7. **Smaller distinct defects:** wrong detail despite visible evidence (C066-A/C substitute
   "creative vision" for "engagement"); a hallucinated citation (C058-C cites "[T90]", which is
   not the withdrawal turn); a reversed exchange direction (C086-C makes Daniel the recipient of
   his own explanation); one passage misidentification while abstaining (C048-B).

**Recurring style defect, deliberately not scored:** 30+ answers reply in the first person
about the user's own preference ("No, I do not currently enjoy…" to "Do I currently enjoy…?").
The referent is still the user, so I did not fail `ownership_correct` on it; it is recorded here
because it is systematic and a stricter reviewer could score it. This is my main
rubric-interpretation call — see below.

## Cases are not independent

60 distinct question texts across 88 cases: 14 question texts recur in three cases each
(e.g. "Do I currently enjoy board games with friends?" as C015/C025/C054), and 43 histories
back 88 cases, up to 4 cases per history. The three views of one question share everything but
retrieval depth. Failures therefore cluster: the 52 withdrawal-inversions are not 52
independent observations but a single behaviour repeated across related items and views.
No per-answer verdict should be treated as an independent trial.

## Reference concerns

`reference_issue_if_any` is null for all 88 cases. I judged each answer against the source,
not by matching the reference, and found no case where the frozen reference was wrong or
ambiguous enough to change a verdict. The one place the reference's own wording came up was
C073-B, recorded as **ambiguous**: the answer gives "a Real Estate degree" and the internship
organisation but omits Temple, and whether "which university degree" requires the university is
genuinely unsettled. That is a question-wording ambiguity, not a reference defect. Frozen
references were not modified.

## Limitations

- **Partial collection.** 262/360 captures, 88/120 questions, and a schedule prefix rather than
  a random subset. Rates above describe what was collected, nothing more.
- **Blinding is real but incomplete**, exactly as the packet warns: ids are opaque, but
  retrieval depth is legible from the messages, so conditions are distinguishable.
- **Prior exposure, disclosed:** I performed the v1 120-reference review and the v2 delta review
  of these same families. The source passages, withdrawal turns and corrected references were
  already familiar to me. That is exposure to references and sources — not to these answers, any
  score, or the sealed map. It plausibly made me faster and more confident on source questions,
  and it is a reason to treat my agreement with the references as less than fully independent.
- **Rubric-interpretation calls** are mine and change counts if reversed: (a) first-person echo
  not scored as an ownership failure; (b) an answer that reaches the right value *via* the
  withdrawal still fails `withdrawal_compliant`, because the rubric names that inference as the
  violation; (c) repeating the withdrawn value while abstaining fails, which is what separates
  C031-C (the one passing abstain_unknown answer) from the other 44.
- A model audit, not human validation, not a performance score, and not permission to train.
  No inference, training, uploads or additional agents were run; writes are confined to
  `claude-review/`.

## Unresolved questions

1. Is the first-person echo ("No, I do not currently enjoy…") intended to be an
   `ownership_correct` failure? Scoring it would move roughly 30 answers from pass to fail.
2. Should an answer that lands on the correct current value but derives it from the withdrawal
   count as a withdrawal failure? I scored it as one; this drives a substantial share of the 52.
3. C073-B: does "which university degree" require naming Temple? Left `ambiguous` pending a
   ruling.
