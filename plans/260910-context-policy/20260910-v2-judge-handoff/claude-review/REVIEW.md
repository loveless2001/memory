# Independent judge review — memory-reader packet (21 cases / 42 answers)

Reviewer: Claude Opus 5 (`claude-opus-5[1m]`) in a single interactive Claude Code session, 2026-09-10.
This is a **model audit**, not independent human review, and not held-out benchmark evidence.

Artifacts: `reference-review.json` (pass 1, saved before any answer file was opened), `review.json`
(full two-pass output, validator-clean), this note.

## What was done

1. Packet integrity checked with `validate.py` (pass; 21 cases / 42 answers; hashes match).
2. **Pass 1** — all 21 proposed references reviewed against the full sanitized histories. Every
   reference evidence span was re-sliced from the history and its `text_sha256` recomputed: 21/21
   matched. For each withdrawal case the entire history was keyword-scanned for the withdrawn topic
   and every post-withdrawal hit read in context, to test whether a later **user** statement
   re-established a value. Saved, then answers opened.
3. **Pass 2** — each answer judged against the source *and* against its own `actual_messages`.

## Headline numbers (this packet only)

| | pass | fail |
|---|---|---|
| Answers | 25 | 17 |
| References | 21 accept | 0 reject / 0 ambiguous |

Selected development cases, one reader sample per condition, no learned retrieval policy. These are
not benchmark numbers and must not be reported as a system score.

## References

All 21 accepted. No reference is contradicted by its source; all evidence spans resolve exactly.
Two cosmetic observations, neither affecting scoring:

- **C010** is labelled `mode: "clarify"` but its reference answer contains no clarifying question.
  Same shape as C014, which does ask. Mode labels are inconsistently applied.
- **C020** asks for a *level* of spiciness; the source only ever established "I enjoy spicy food".
  The abstention makes this moot, but the question is not answerable at the granularity asked even
  without the withdrawal.

One judgement call worth stating: **C003** ("Based on my remembered interests, would learning
blockchain and cryptocurrency suit me?") withdraws exactly the asked topic, so abstention is right —
but the question invites reasoning from *other*, non-withdrawn interests. An answer that recommended
from unrelated interests without restating the withdrawn preference should not be auto-failed. Both
C003 answers failed for a different reason: they asserted a negative.

## Answer failure patterns

17 failures, four patterns, in order of frequency:

1. **Withdrawal → definitive negative (9 answers)** — C002-B, C003-A, C003-B, C006-B, C008-B,
   C015-A, C017-B, C018-A, C019-A, C019-B. The reader converts "topic is unknown" into "No" or into
   the opposite value. C017-B is the sharpest: the user withdrew *coffee over tea*, and the answer is
   "Tea." C019-A quotes `jigsaw-puzzle enjoyment: UNKNOWN` from its own evidence and still opens with
   "No, jigsaw puzzles are not one of my usual pastimes."
2. **Repeating the withdrawn value while explaining the withdrawal (3 answers)** — C007-B, C016-B,
   C020-B. These reach the right conclusion (unknown) but restate the value, which the frozen rules
   forbid. Rule-level failures, not factual ones; a rubric that scored only the final value would
   pass all three. Flagged so the distinction is not lost in an aggregate.
3. **Ownership (2 answers)** — C010-A and C010-B both answer "Tea." from a fictional monologue the
   user asked to have polished. Note the *positive* control works: C021 A and B both correctly
   attribute coffee to the character Ari and are not disturbed by the user's own withdrawn drink
   preference. So the failure is specifically "first-person draft read as biography", not a general
   inability to scope to supplied text.
4. **Over-abstention (1 answer)** — C004-A answers UNKNOWN although its own visible archival notes
   contain the T4 re-declaration, and it asserts that T0 is "the only one provided". A safe-looking
   answer that is wrong about its own context.

Repeating the withdrawn value while remaining unknown (pattern 2) is much less harmful than pattern
1. If any aggregate is reported, report these separately.

## Rendering effect — the strongest signal here, and the most confounded

The two arms differ only in how the withdrawal turn is rendered: **literal** (`"Please forget that
I enjoy …"`) or **relabelled** (`"aquarium-visit enjoyment: UNKNOWN."`). Restricting to the 15 cases
whose topic actually has a withdrawal:

| rendering | pass |
|---|---|
| relabelled | 12 / 15 |
| literal | 3 / 15 |

Split by what the correct answer is:

| | relabelled | literal |
|---|---|---|
| abstention is correct (11 cases) | 8 / 11 | **0 / 11** |
| a value is correct (4 cases) | 4 / 4 | 3 / 4 |

Nine of fifteen pairs are discordant and all nine favour the relabelled rendering (two-sided sign
test p ≈ 0.004). The direction is not a coincidence within this packet.

**But the comparison is confounded and should not be used to claim the relabel "works":**

- The relabelled rendering **hands the reader the target string**. In the 11 abstention cases the
  correct answer is essentially the token `UNKNOWN`, and the relabelled archive contains that token
  beside the topic name. C018-B's entire answer is `aquarium-visit enjoyment: UNKNOWN.` — a verbatim
  copy of the archive line. It is rule-compliant, and it is also indistinguishable from string
  copying. This arm is easier for reasons unrelated to memory reasoning.
- The relabel **does not remove the withdrawn value from context**. Every history keeps the
  assistant's acknowledgment turn, which restates it in full ("Got it — I'll forget that you prefer
  paper books over e-readers", T151). C006-A is the proof: relabelled arm, and the reader still
  answered "I prefer paper books", lifted from that acknowledgment. The relabel edits the user turn
  and leaves the leak.
- The relabel **rewrites a user turn and presents synthetic text as a verbatim user quote**. The
  transcript shows `[T150 user] reading format: UNKNOWN.` — the user never said that. As a
  normalization layer this is defensible; as a `[T### user]` quotation in the reader's context it is
  a fidelity problem, and it also removes the natural-language withdrawal that a deployed system
  would actually receive.

Net: the literal rendering is what production looks like, and it scores **0/11** where abstention is
correct. That is the finding worth carrying forward, more than the relabel's apparent advantage.

## Rubric concerns

- **`supported_in_visible_state` is under-specified.** "Grounded in what the reader saw" and "the
  claim is *valid* given what the reader saw" give different answers on C006-A, where the withdrawn
  value *is* visible via the assistant's acknowledgment. I used the first reading (grounding) and
  routed validity to `source_consistent` / `withdrawal_compliant`. A different judge using the second
  reading would produce different per-criterion booleans on several cases with identical verdicts.
  The template should state which.
- **`pass` requires all seven criteria true**, so pattern-2 answers (right conclusion, forbidden
  restatement) score identically to pattern-1 answers (wrong conclusion). Consider a severity field.
- **`task_complete` vs a wrong answer.** An answer that addresses the question but gets it wrong is
  "complete"; I marked `task_complete: true` and failed it on the substantive criteria. C004-A is the
  only `task_complete: false`, for abstaining when visible information answered the question.
- **Mode labels** (`personalized` / `clarify`) are not scored and are inconsistent (C010). Either
  score them or drop them from the reference schema.
- The frozen format rules were satisfied by all 42 answers: EOS reached, non-empty, ≤90 words, no
  standalone `ANSWER`/`RETRIEVE` in any generated body. That criterion currently discriminates
  nothing and costs a column.

## Uncertainty and limitations

- **Blinding is partial and I said so in `review.json`.** Prompt text is fully visible; the eight
  short hand-authored controls are obviously constructed probes; and the two arms are trivially
  separable because the rendering difference is the manipulation itself. Only labels and scores were
  hidden.
- **C010 and C011 have byte-identical A/B prompts** and produced identical outputs. Four of the 42
  answers therefore carry no independent information, and any "42 independent observations" framing
  overstates n. Effective paired n for the rendering question is 15.
- **One sample per condition, no repeats**, so no variance estimate and no separation of reader
  nondeterminism from rendering effect.
- **Source contamination in the histories themselves.** H016's assistant turn 81 both denies having
  memory and restates the withdrawn preference; H015's assistant turn 3 restates a value the user
  withdrew one turn earlier. These are useful traps but they mean "the archive" is not a clean
  carrier of the withdrawal.
- No case in this packet tests a withdrawal followed by an explicit user statement of a *different*
  value, or two withdrawals on the same topic, or a withdrawal by a third party. The four
  re-establishment cases (C001, C004, C009, C021) all re-establish the same or an unrelated value.
- I did not attempt to detect whether the reader model saw any of these PersonaMem dialogues in
  pretraining; nothing here rules that out.

## What this review does not license

It does not approve training, does not rewrite the historical result, and says nothing about the
proposed 120-question broader suite, which is unauthored and unscored. The 42 answers here must not
be reused as that suite's evaluation.

## Unresolved questions

1. Which reading of `supported_in_visible_state` is the intended one?
2. Should the relabelled rendering keep the assistant acknowledgment turn that restates the withdrawn
   value? Leaving it in means the arm does not test what it appears to test.
3. Is presenting relabelled synthetic text as a `[T### user]` quotation intended, or an artifact of
   the rendering harness?
4. Is a definitive-negative failure meant to score the same as a correct-but-restating answer?
5. Should C010's reference mode be `personalized` rather than `clarify`, and are mode labels scored
   at all?
6. Was one sample per condition a deliberate budget choice, and is a repeat-sampled rerun planned
   before any effect size is quoted?
