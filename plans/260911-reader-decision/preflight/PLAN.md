# Matched structured-decision supervision experiment

The user authorized the preceding four-condition proposal with “ok go ahead”.
Complete one bounded experiment, preserve prior results, and report the frozen
pass/fail rule. No automatic retry, extra checkpoint selection, prompt sweep,
external evaluation or deployment is part of this authorization.

## Hypothesis and conditions

Explicit supervision of a source-grounded state and question decision, followed
by deterministic answer rendering, may reduce the observed polarity and state
errors without losing previously correct answers. Syntax alone is not success.

1. `current_direct`: frozen v2 adapter, original archive/answer prompt.
2. `current_decision`: same v2 adapter, new structured-decision prompt and renderer.
3. `trained_direct`: one continuation of v2 trained on ordinary source-authored answers.
4. `trained_decision`: independent continuation of exactly the same v2 weights,
   trained on decisions for exactly the same source histories and questions.

For each example the prose and decision formats share the identical user
message: only the full chronological archive and current question. No target
property, scope, candidate, oracle state, question interpretation or reference
is supplied at inference. The system instructions and target format differ.
No learned retrieval or routing is tested. The archive is fully supplied.

The structured model generates nine fields: scope, relation, status, value,
operation, candidate, decision, turn and quote. Status distinguishes value,
negative, explicit none and unknown. Operation distinguishes candidate matching,
explicit-none statements, explicit-negative statements and open lookup. The
model must infer all fields. Exact source/candidate anchoring and the schema are
checked after generation; they do not establish semantic correctness. No grammar
repair, second attempt or reference-based output correction is performed.

Code renders the predicted decision: supported -> Yes, contradicted -> No,
unknown -> uncertainty, answer -> known open answer. The renderer never decides
polarity by consulting the gold answer. An inconsistent predicted decision can
therefore remain wrong. Invalid records render a clear processing failure and
fail evaluation, even when the reference is unknown. Unknown answers never
repeat withdrawn values; a known negative or separate known enjoyment fact may
be included while answering an unknown candidate question. Internal source
quotes/candidate fields can cite the archive/question; only rendered text is the
user-facing answer. Historical answers retain passage scope and source wording.

## Matched data and training

512 new paired examples from sixteen new properties and eight history types:
positive, negative, explicit none, withdrawal, same-value restoration,
different-value restoration, fictional ownership and historical scope. Four
questions per typed history; some withdrawal/historical sources coincide, giving
120 distinct histories. The same questions receive independently source-authored
ordinary targets and typed targets. Neither arm trains on evaluation sources,
questions, references or captured model outputs.

Negative histories include a second candidate whose truth remains unknown.
Enjoying A does not imply not enjoying B: other-activity questions are unknown
unless an explicit source establishes them. Historical comparisons ask what a
particular passage said, so absence of the questioned alternative there can
support No. Current scope is explicit on removal/replacement questions. These
semantic distinctions were reviewed before inference rather than inferred from
model answers.

Both continuations use the same starting v2 files, seed zero, same exact two
shuffled example orders, two epochs, microbatch one, accumulation sixteen,
64 optimizer steps, AdamW peak 1e-4, weight decay .01, three-step warmup, linear
decay, clipping 1, existing rank-16 q/v LoRA, alpha 32/dropout .05. Base weights
and buffers are frozen. The final checkpoint is fixed; no validation selection.
This matches examples and update counts, not supervised tokens, FLOPs or elapsed
time. Record actual costs. Different prompt lengths also change dropout draws;
this is a comparison of training recipes, not an isolated token-budget effect.

## Evaluation and pass rule

160 new questions from forty new histories/properties, five per history type,
with four questions per history. Source wording is separately authored, but
these are related synthetic constructions rather than a natural/random external
benchmark. New properties, exact histories and queries are disjoint from new
training, prior 512-example training and all 260 regression questions.

The regression set is the union of the previous 208 reader cases and 52 added
factorization questions. Twelve duplicated factorization cases are retained once.
All original histories, questions and references remain unchanged. Exact
current-direct messages/tokens/text must reproduce on all 260 cases. Reuse old
judgments only after that check. Freeze the protection mask before launch: 259
cases have a strict-correct non-oracle answer in one of the seven previous reader
experiments, matched by exact history and question. Protect that union, including
previous sizes/prompts/extracted pipelines; oracle answers do not count. The one
unprotected N01-1 remains evaluated and reported under its frozen convention.

The `trained_decision` condition passes only if ALL hold:

- At least 152/160 strict passes on the new questions (95%).
- Strict new-test score exceeds both current_direct and trained_direct.
- Zero losses among the 259 protected regression questions.
- Numerical, training, artifact and saved-checkpoint verification all pass.

Also report whether it improves over current_decision, every correction and
regression, current-direct-correct preservation on the new set, and scores by
history type/form/relation. Correlated questions are grouped by source history
for descriptive paired differences and any bootstrap intervals; forty groups
are not 160 independent samples. No single pilot is deployment certification.

Use the prior seven strict final-answer criteria and separate required-answer
correctness. Decision arms additionally require a usable schema and correct
source-grounded state, question interpretation, decision and evidence/ownership.
A wrong structured record fails even if its rendered answer happens to be right;
report rendered-answer-only scores separately. Review semantic equivalence in
context, not exact text matching; report literal target agreement separately.
In particular, a source-anchored quote does not prove ownership, scope or state.
No credit is awarded merely for a JSON parse or an unknown fallback.

The old categorical-No versus unknown convention stays fixed. Disclose wording
sensitivity without changing primary scores. Review all new outputs after both
fixed trainings complete, against source, actual prompt, reference and rendered
text. It is unblinded author review, not independent evaluation.

## Bound, numerics and provenance

One H100, four CPUs, 32 GiB RAM, hard limit 3,600 seconds and internal deadline
3,500 seconds, retries zero. Two trainings and 1,680 captures in one app. No
second launch if the bound is exceeded; save partial artifacts and report.
Dedicated volume `memsub-reader-decision-artifacts`, prefix
`reader-decision/20260911-v1`. Mount only frozen runtime, training targets,
unlabeled evaluation prompts, order/gate/configuration and the two v2 adapter
files. No prior evaluation outputs or evaluation references are mounted.

Pinned Qwen3-4B-Instruct-2507 revision cdbee75f17c01a7cc42f958dc650907174af0554,
Torch 2.7.1 / Transformers 4.55.2 / PEFT 0.17.0. FP32 math attention and TF32 off
for evaluation; BF16 frozen base parameters, FP32 trainable adapter/buffers for
training, preserving base tensor contents on return to FP32. Fresh prefill,
greedy output, forced ANSWER prefix. Prose cap 192 generated tokens; structured
cap 256 to accommodate evidence fields; all final rendered answers <=90 words.
Disclose this token-cap difference and raw accounting.

Twenty identical selected question IDs per arm (ten regression, ten new) must
pass initial cached/fresh argmax and up-to-sixteen-token trajectory equality:
80 fixtures total. Run baseline formats in alternating order per question;
then train/evaluate prose continuation and structured continuation sequentially.
Verify complete base and adapter tensors initially, after baseline, before each
training, after each training, after saved-adapter reload and after evaluation.
Check loss, finite gradients, exact exposure order, target-only masking and
adapter-only updates. Download/hash-verify artifacts, confirm stopped app and
zero tasks, read observed billing, finish semantic review and freeze the report.
