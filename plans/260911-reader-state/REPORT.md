# Structured-state reader diagnostic — completed 2026-09-11

**The tested extracted-state pipeline should not replace the baseline.**
Reviewed state improves some answers, but model extraction loses that benefit
and the answer generator still mishandles unknown and explicit no-preference
states. All 288 answers and 52 extractions were collected and reviewed. Every
arm fails both clean-suite gates. No training or further inference followed.

| Input to the answer generator | Regression strict | New strict | Regression required answer correct | New required answer correct |
| --- | ---: | ---: | ---: | ---: |
| Full history, original prompt | 53/72 | **17/24** | 60/72 | 18/24 |
| Reviewed state, oracle diagnostic | 60/72 | **18/24** | 64/72 | 18/24 |
| Model-extracted events → resolver → state | 52/72 | **14/24** | 56/72 | 15/24 |

Strict pass requires all seven frozen criteria: requested answer correctness,
source consistency, whole-answer support, withdrawal compliance, ownership,
valid body and at most 90 words. These are **unblinded author judgments**, not
independent acceptance. The unchanged 72 regression baselines reproduce all
previous input messages and output token sequences exactly. Their reviewed
scores remain 17/24 on the former development split and 36/48 on the former
fresh split; those earlier labels do not describe a new holdout here.

Against raw history, reviewed state fixes fourteen regression strict failures
and introduces seven; on new questions it fixes three and introduces two. The
extracted pipeline fixes thirteen and introduces fourteen on regression, and
fixes three and introduces six on new questions. Compared directly with reviewed
state, extracted state introduces eight regression and four new strict failures,
with no corrections. Required-answer comparisons also favor the baseline over
the extracted pipeline. See [summary.json](summary.json) for all matched counts.

## What the separation reveals

Current-scope answers isolate the main state-tracking question. The remaining
thirteen questions are historical controls that directly receive their selected
original source passage in both structured arms; they do not test extraction.

| Current-scope questions | Raw history | Reviewed state | Extracted state |
| --- | ---: | ---: | ---: |
| Regression strict | 42/60 | 52/60 | 44/60 |
| New strict | 16/23 | 17/23 | 13/23 |
| Combined strict | 58/83 | **69/83** | **57/83** |
| Combined required answer correct | 65/83 | 69/83 | 58/83 |

Correct supplied state is still insufficient for this answer generator. For
example, the reviewed record for `F01-withdrawal-binary` explicitly says unknown,
yet the answer says bouldering is not the preferred activity “because your
preferred weekend activity is unknown.” Some other binary answers begin with
No and then correctly explain that the value is unknown. The frozen scoring
convention rejects that leading negative; it does not establish that the model
internally believes the opposite preference. All four regression ownership
binary questions also receive unsupported negatives from the reviewed unknown
record. Open questions on those same states correctly return unknown.

The new dessert case tests a different state. The source explicitly says the
user has no preferred dessert. Its reviewed record is `status: known`,
`polarity: none`, and the prompt defines none as an explicit no-preference
assertion. Nevertheless, the reader denies that the user explicitly said this
in the binary question and answers unknown in the open question. Both raw-history
answers pass. This is a failure even with the correct state and interpretation
rule supplied, rather than a failure to retrieve the source.

Extraction adds errors that deterministic resolution cannot correct. All eight
regression fictional-speaker streams are labeled user-owned, including cases
where the exact quote itself says fictional Rowan or Vale. The resolver then
establishes those values as user preferences. The extracted-arm answers follow
those wrong records, producing twelve wrong ownership answers across the repeated
question forms. Exact source matching establishes where text came from; it
does not validate its claimed owner.

In new `N04`, the user withdraws breakfast preference while explicitly retaining
the fountain-pen preference. The extractor emits a withdrawal for the target
writing-tool property anyway. Both resulting answers fail; the raw and reviewed
state answers pass. This identifies property relevance as a separate extraction
target from chronology.

## Extraction audit

Extraction runs once per unique history/property pair, shared across questions.
The 52 streams comprise forty regression and twelve new histories. Gold event
references were reviewed and frozen before any model call.

| Extraction measure | Regression | New | Total |
| --- | ---: | ---: | ---: |
| Valid schema and exact source spans | 40/40 | 10/12 | 50/52 |
| Semantically correct complete event sequence | 30/40 | 5/12 | 35/52 |
| Semantically correct resolved state | 30/40 | 8/12 | 38/52 |

Exact categorical event matching is **29/52**, and exact complete state-record
matching is **34/52**. Semantic scores are higher because six positive-extraction
streams copy an entire “I enjoy …” phrase instead of the required minimal activity
value. These violate the minimal-value convention but preserve the positive
meaning; four affect the final state's value surface. They are disclosed as
surface/schema deviations, not silently repaired outputs.

The seventeen semantic sequence failures comprise eight wrong owners, three
polarity/value construction failures, one wrong-property withdrawal, three
omitted other-owner assertions, and two rejected schemas/source bindings.
The three omissions leave the final user state correct, illustrating why final
state correctness alone cannot validate complete extraction.

The polarity/value failures encode negative enjoyment in the whole value phrase
instead of consistently using `deny` with the activity name; one places negation
in both operator and value. These violate the signed-value contract, although
the original negative text remains visible. The reader recovers the correct
negative answers for all four questions using those three streams. This is
answer recovery from a malformed state representation, not successful extraction.

Two complete extractions were rejected without repair. The pronunciation stream
adds a T2 denial whose value, MAY-ree, does not occur in its quoted T2 substring;
the source refers to the assistant's version anaphorically. This is a limitation
of the frozen copying/source-binding contract and does not prove the model failed
to understand the correction. The otherwise correct MAH-ree event is discarded
under the predeclared whole-parse rejection rule. The dessert stream emits a
dictionary instead of a five-field array and a sentence instead of null. Its
intended no-preference operation is visible, but the format is invalid. Both
rejections produce unknown fallback states, and all four resulting answers fail
strict scoring.

One pronunciation binary answer happens to begin with the correct No, while its
explanation falsely says the supplied pronunciation is unknown. Required-answer
correctness credits that leading response, but source support and strict scoring
fail. It is the sole coincidentally correct required response after rejected
extraction, and is not counted as state-tracking success.

Across the 83 current extracted-arm questions, the decomposition is:

| State judgment | Required answer correct | Required answer wrong |
| --- | ---: | ---: |
| Correct | 53 | 8 |
| Wrong / state-contract failure | 5 | 17 |

The five correct answers from wrong states comprise four negative-text recoveries
and the accidental pronunciation No. The eight wrong answers from correct states
are the four regression and four new withdrawal binary questions. No hidden
reasoning is inferred from these observable input/output relationships.

## Historical controls and scoring sensitivity

All thirteen historical required answers are correct in every arm. Strict scores
are 12/13 for raw history and 9/13 for each structured arm. Four structured answers
correctly recall the original detail but additionally assert that it was not
withdrawn. The full source has a T2 withdrawal and the question presupposes it.
The selected original-passage record alone cannot justify denying a later
withdrawal. This is an answer-stage overclaim under restricted evidence.

Other historical answers say there is no indication of withdrawal **in the
provided original-passage record**. Those statements are scoped to a record that
contains only T0, so they are not equated with an unqualified denial that a
withdrawal occurred. The original-passage value “remaining as stated” is read at
the requested historical scope. The review records this distinction explicitly;
the current-scope table above does not depend on these historical judgments.

New `N01` asks whether saying swimming is the current preference would be
accurate. Its wording permits an epistemic refusal-to-assert reading of No,
in addition to the frozen literal UNKNOWN-versus-negative convention. A generous
post-review sensitivity credits all three N01 binary answers: new strict scores
become **18/24 raw, 19/24 reviewed state, and 15/24 extracted state**. The relative
ranking and failed gates are unchanged. These sensitivity counts do not replace
the frozen primary judgments or make N01 a clean question-form contrast.

[Answer review](review.json) and [extraction review](extraction-review.json)
contain individual reasons and exact source/actual-message evidence. Their
recording scripts encode inspected decisions, not a keyword judge. The retained
baseline judgments are bound to verified identical captures. Correctness against
the full source is separate from fidelity to the supplied state: a reader can
faithfully answer from an incorrectly extracted state and still be wrong.

## Protocol, cost and verification

The [frozen plan](preflight/PLAN.md) and
[pre-inference reference review](preflight/REFERENCE-REVIEW.md) cover 72 unchanged
regression cases and 24 new questions on twelve varied synthetic histories.
The reviewed-state arm intentionally receives privileged state derived from gold
events. The extracted arm receives only model-produced state. Both share the
same record schema and answer prompt. Current records omit withdrawn values and
old source quotations, so the oracle-versus-raw comparison changes accessible
content as well as representation; it does not isolate JSON formatting.

The property and historical target-turn routing are supplied by the author.
The extractor sees history and property, not the question or gold events. This
tests conditional extraction for a supplied property, not automatic discovery
of properties or general query routing. Raw gold events and final-answer
references were excluded from inference inputs; oracle state is present only
in the oracle answer messages. The complete actual prompts are retained.

The reader is unchanged Qwen3-4B-Instruct-2507 at revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, Torch 2.7.1 and Transformers 4.55.2,
FP32 math attention, TF32 off, seed zero, greedy decoding and fresh prefill.
Answers have 192-token/90-word caps; extraction has a separate 768-token cap.
No parameters were trained. The one-H100 job completed in **421.865 seconds**
(7m02s), within its 1,800-second hard cap, with no retries.

| Generated workload | Calls | Input tokens | Output tokens | Generation time |
| --- | ---: | ---: | ---: | ---: |
| Raw-history answers | 96 | 39,132 | 2,817 | 84.178 s |
| Reviewed-state answers | 96 | 28,934 | 1,569 | 47.762 s |
| Event extraction | 52 | 25,066 | 3,136 | 90.833 s |
| Extracted-state answers | 96 | 28,990 | 1,524 | 46.942 s |

The extracted pipeline therefore uses **54,056 input tokens** and **4,660 output
tokens**, with extraction shared across related questions, versus 39,132 and
2,817 for raw history. That is about **38% more input tokens** and **40% more total
input/output tokens**, with lower strict accuracy in this batch. These counts
exclude numerical-fixture calls; observed billing includes them and all execution
overhead. Oracle authoring is privileged and unpriced here, so its lower inference
token count is not an end-to-end efficiency result. Generation times are measured
inside the shared job, not separate deployment latency measurements.

All **40/40 numerical fixtures** pass cached/fresh initial-argmax and up to
sixteen-token trajectory checks. All **288 answers** pass body checks and fit 90
words (maximum 56). Offline reconstruction verifies source spans, parsed events,
computed records, actual prompt text, tokens, EOS, forward counts and accounting.
All **1,185 protected prior files remain unchanged**. Five focused resolver/parser
tests passed before the freeze. The live extraction copy inspected during answer
collection matches the final saved artifact byte-for-byte.

App `ap-tNLXTV3B55HmyFf0nBFstQ` is stopped with zero tasks. Observed cost is
**$0.52742384**, recorded at 05:39:35 UTC; billing may lag terminal execution.
See [billing](billing.json), [app state](app-status.json) and
[artifact verification](run/artifact-verification.json). Run
`python plans/260911-reader-state/verify_results.py` to verify the final
[result manifest](result-manifest.json), evidence summaries and protected files.

This bounded development test identifies two separate targets for later work:
owner/property/polarity extraction, and faithful answers for unknown versus known
negative/no-preference states. A representation change alone has not solved
either. The new examples remain author-written, related question pairs, and are
not an independent long-history benchmark. Broader evaluation and training-label
review remain necessary before retrieval-policy training; no training admission,
new model comparison or additional inference was performed.
