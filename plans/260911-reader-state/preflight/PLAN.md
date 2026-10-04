# Frozen structured-state diagnostic

The user approved continuing the proposed three-way comparison after the 8B
report: history to answer; reviewed state to answer; extracted events through a
deterministic resolver to answer. This authorizes this bounded inference test,
not training, a model sweep or a further retrieval run.

Use Qwen/Qwen3-4B-Instruct-2507 revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, the unchanged base reader, with no adapter.
Keep Torch 2.7.1, Transformers 4.55.2, FP32 math attention, TF32 off, seed zero,
greedy decoding, fresh prefill, supplied ANSWER prefix, 192-token/90-word answer
limits and an 8,192-token context cap. Extraction has a separate 768-token cap
and no prose word limit. This additional extraction work is charged and reported;
the pipeline is not an equal-compute comparison to one-pass answering.

## Cases and arms

Retain all 72 existing cases and references as regression cases, including the
previous development/fresh labels as secondary metadata. Add 24 new questions on
twelve separately authored synthetic histories. These cover assistant repetition
after forgetting, explicit negative preference, selective and unrelated
withdrawal, quoted versus personal assertions, quoted reappearance after
withdrawal, same-value reinstatement, several sequential updates, assistant
contradiction, historical scope, another person's preference, and explicit
absence of a preference. They vary wording and include distractors; they remain
small authored examples rather than a representative benchmark. Two questions
per new history are related and must not count as independent histories.

Author event references and review all new sources before freezing; no reader
or extractor inference may precede the freeze. Review is by the experiment
author, not independent. Prior reference bytes remain preserved; added fields
are in a new artifact only. Cases are reused for diagnostic evaluation, never
admitted as training examples by this experiment.

Each of 96 questions receives three answers, in cyclically rotated arm order:

1. `baseline`: exactly the existing original prompt and complete chronological
   archive. All 72 old message sequences must match their prior 4B originals.
2. `oracle`: answer from the author-reviewed state record, built from gold events.
   This intentionally supplies privileged correct state. It tests answer
   generation conditional on correct state, not learned state tracking.
3. `extracted`: answer with the same state prompt after 4B extracts source-bound
   events and deterministic code computes their current state. No gold event or
   state enters an extraction or extracted-arm answer prompt.

The oracle and extracted arms receive identical record schemas and prompts.
Current records show owner, property, status, polarity, value and supporting
turn IDs. They omit old values and old quotations. Therefore oracle versus raw
changes both representation and accessible content; it does not isolate syntax.
For historical questions, both structured arms return the explicitly selected
original source passage, with source labels. These are scope/answer controls:
they bypass event extraction and must not be counted as evidence of extraction
success. Report current-scope comparisons separately.

Properties and historical target-turn metadata are author-specified task routing
for every arm's case. The extractor sees only the target property and complete
history, not the question, reference, gold events or oracle state. This is
conditional extraction for one supplied property, not an end-to-end property
discovery or query-routing system. Identical history/property pairs share one
extraction, regardless of their question wording or scope. No extraction retry,
JSON repair, best-of-N selection or fallback to gold is allowed.

## Extraction and resolver contract

The extraction schema is exactly `{"events": [[turn, owner, op, value, quote], ...]}`.
Owner is user or other; op is set, deny, withdraw or no_preference. Values for set
and deny must be copied from the exact quoted user source; the other operations
use null. Quotes must identify unique exact substrings of the cited USER turn.
Nonexistent turns, assistant citations, malformed schemas, duplicated events,
out-of-order turns, incomplete output and unanchored quotes invalidate the whole
extraction. There is no silent partial salvage. The resulting state is unknown
and the extraction remains a recorded failure. A safe unknown can coincidentally
answer an unknown case correctly; do not count that as successful extraction.

For each property, source-bound user events apply in source order. A positive
assertion sets the value; a negative asserts only the stated value's negative;
withdrawal makes state unknown; explicit no-preference is known with polarity
none. Later user assertions override earlier events, including same-value
reinstatement. Other-owner events are retained for audit but never establish user
state. Assistant turns cannot establish it. Selective topic relevance is the
extractor's job; the resolver cannot infer that a semantically wrong but
well-anchored event concerns another property. This limitation is scored.

Gold and extracted events undergo the same source validation and resolver. Quote
anchoring proves location, not owner, relevance, operation, value interpretation
or completeness. Report exact categorical event matching against gold (turn,
owner, op and value), then author-review semantic event correctness and quote
sufficiency. Gold quote boundaries need not match when a different exact span
supports the same event. Report harmless value-surface differences separately
from semantic errors; do not repair the executed state after viewing outputs.

## Scoring and decision

Use the previous seven final-answer criteria: task correctness, source
consistency, whole-answer support, withdrawal compliance, ownership, body validity
and 90 words. Source consistency/support are scored against the full underlying
source, while unsupported additions absent from the state prompt are also
flagged separately for structured answers. Historical source quoting is allowed.
UNKNOWN differs from No and from an explicit lack of a preference. A direct
binary denial is allowed when another current value or an explicit negative
establishes it; explanations must not restate withdrawn old positive assignments.

Report required-answer and strict scores by regression/new split, arm, current
versus historical scope, question form and case type; matched corrections and
regressions; extraction schema/span validity; semantic event correctness; and
resolved-state correctness. Separate wrong state with plausible answer, correct
state with wrong answer, and invalid extraction with coincidentally correct
unknown. All judgments are unblinded author judgments with exact source and
actual-message evidence. No independent acceptance or population confidence
intervals are claimed.

Keep clean-suite gates of 72/72 regression and 24/24 new strict answers per arm;
also disclose partial gains. Perfect answers do not imply perfect extraction.
If the oracle arm fails current answers, correct state is insufficient for this
answer generator. If oracle works but the extracted arm loses accuracy, event
extraction/state construction is a candidate target for later supervised work.
If both work, broader held-out history evaluation is the next gate. These are
diagnostic implications, not automatic authorization for training or another run.

## Execution and accounting

One H100, four CPUs, 32 GiB RAM; 1,800-second hard timeout and 1,750-second internal
deadline, zero retries. Existing cached 4B weights are reused. Keep all earlier
experiments unchanged. Batch remote commits every twenty requests and always
save terminal status. Forty numerical fixtures compare initial argmax and up to
sixteen cached/fresh greedy tokens: ten baseline, ten oracle and ten extraction
prompts before extraction, then ten actual derived-state prompts before answer
collection. Selected request IDs are frozen before inference. Failed fixtures
stop collection and preserve artifacts.

Mount only allowlisted runtime sources and inference inputs. Oracle records are
intentionally present in oracle messages; raw gold events, final-answer
references, authoring and review code are excluded. Record actual prompts for
every model call to audit this separation. Preserve extraction outputs, parsed
events, computed states, derived prompts, answer tokens, source snapshots and
hashes. Verify all counts, message/token reconstruction, original baseline
reproduction, protected files, billing and terminal app state before reporting.
Include extraction tokens/time in end-to-end cost, with shared-history accounting
explicit. Report observed billing rather than multiplying nominal model prices.
