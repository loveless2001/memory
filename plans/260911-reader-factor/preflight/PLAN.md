# Inference-only factorization of fact identification and answer selection

The user approved the proposed separation diagnostic with “ok cont”. Run one
bounded inference-only experiment with the frozen v2 adapter. No model training,
adapter changes, prompt sweep or automatic retry is part of this experiment.
Earlier result manifests and judgments remain unchanged.

Use 64 questions on sixteen histories: four reused histories (N09 pronunciation,
N12 explicit no-preference, H02 surname conflict, H11 negative preference), and
twelve new histories with new properties/wording. Each history has four related
questions. Twelve reused questions retain exact original histories, queries and
references; four additional questions on those histories are diagnostic controls.
The 48 questions on twelve new histories test nearby spellings/transcriptions,
distant value comparisons, explicit none, negative preferences and withdrawal.
This selected challenge set is not a random benchmark or independent sample.

## Fixed conditions

1. Direct: original complete chronological archive and original answer prompt.
2. Extracted fact: independently extract a compact record from the complete
   history using only the named property; then answer the original question
   from that generated record, with no archive in the answer prompt.
3. Oracle fact: use a source-reviewed correct record with the same answer prompt
   and original question as condition 2.
4. Oracle query: use the same correct record and answer prompt, additionally
   supplying a reviewed operation/candidate interpretation of the question.

Records contain status value/none/negative/unknown, value, supporting user-turn
number and an exact source quote. An exact quote establishes anchoring, not the
correct state/ownership; review semantics separately. A schema/span/body failure
gets an explicitly recorded unknown fallback for downstream generation, without
silently rewriting the model's output. Review raw extraction meaning even when
formatting fails, and distinguish semantic correctness from usable schema.

The extraction prompt is independent of question candidates. Target property
selection is supplied metadata, not a learned retrieval or routing operation.
Oracle records and oracle question interpretations are intentional privileges;
they are not deployable capabilities or evidence that extraction/query parsing
has been solved. Final answer references, prior outputs and review code remain
local. A dedicated output volume avoids mounting prior captured answers.

Also compute a deterministic reference selector from the extracted record and
the reviewed query interpretation. It case-folds literal string comparisons,
without fuzzy matching or semantic alias resolution, and preserves none,
negative and unknown as different states. Invalid records are unusable, not
credited as correct via a convenient fallback. Gold record plus gold query must
pass this selector on all 64 questions before inference. It is a diagnostic
with oracle question parsing, not an autonomous system baseline.

## Prospective analysis

Use the same seven strict answer criteria and separate required-answer scores.
Report source correctness and supplied-record faithfulness separately: a model
can faithfully answer a wrong extracted record, and a correct answer can contain
an unsupported explanation. Review every extraction and answer against the full
source and actual prompt. Retain exact prior direct-answer judgments only after
message/token/text reproduction. No independent-review claim is made.

Report by reused/new split and fact type:

- Usable extraction syntax/spans, raw semantic meaning, correct usable record,
  and ownership/evidence sufficiency; count failures of each separately.
- Direct versus extracted-fact versus oracle-fact versus oracle-query strict and
  required-answer scores, every correction/regression, and complete failure cases.
- Correct usable record followed by wrong answer, versus wrong/invalid record
  followed by wrong answer; disclose coincidentally correct fallback answers.
- Failures remaining with oracle facts; failures fixed by adding oracle query
  interpretation; failures still present despite both.
- The deterministic selector with gold and model records, explicitly retaining
  its oracle-query privilege and limited literal comparison domain.

For N09-1 and N12-2, describe exactly which interventions help and which do not.
The same applies to the fresh near-string and none contrasts. Behavioral changes
across prompts localize difficulty in this constructed pipeline; they do not
prove the same internal stages caused the direct model's mistakes. No aggregate
score or perfect small-suite result admits deployment, retrieval training or a
claim of general reasoning improvement. This experiment is descriptive, not
another adapter acceptance test.

## Frozen implementation and bound

Same Qwen3-4B-Instruct-2507 revision and v2 adapter, Torch 2.7.1/Transformers 4.55.2/
PEFT 0.17.0; FP32 math attention, TF32 off, greedy decoding, forced ANSWER prefix,
192 generated tokens and 90 words for final answers. Sixteen extraction calls
and 256 final-answer calls. The same generated record feeds all four questions
on its history. Rotate answer-arm order by question, with fresh prefill each time.
Five actual prompts per each of four answer arms and extraction must pass
cached/fresh argmax and up-to-sixteen-token trajectory equality (25 fixtures).
Verify complete base and adapter tensor hashes before/after; all parameters frozen.

One H100, four CPUs, 32 GiB RAM, hard limit 1,200 seconds and internal deadline
1,100 seconds, zero retries. Use `memsub-reader-factor-artifacts`, prefix
`reader-factor/20260911-v1`. Review references and test the parser/projector,
freeze inputs/source/configuration/this plan, then launch once. Download and
hash-verify final artifacts, confirm stopped app and zero tasks, read observed
billing, finish source-based review and freeze the final report. No automatic
follow-up run, including after an invalid extraction or a failed numerical gate.
