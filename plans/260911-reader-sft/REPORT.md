# Supervised 4B reader pilot: large gain, preservation rule fails

The single frozen answer-only LoRA pilot completed. Under unblinded author review, the trained reader passes all 48 new test questions and 93/96 regression questions, versus 35/48 and 70/96 for the base reader. The predeclared pilot rule **fails** because two previously correct regression answers become wrong. The saved adapter is an experimental artifact; this result does not admit retrieval-policy training or establish general reader readiness.

| Split | Base strict | Adapted strict | Base required answer | Adapted required answer |
|---|---:|---:|---:|---:|
| regression | 70/96 | 93/96 | 78/96 | 93/96 |
| test | 35/48 | 48/48 | 38/48 | 48/48 |
| all | 105/144 | 141/144 | 116/144 | 141/144 |

Strict passing requires all seven frozen criteria: required-answer correctness, source consistency, visible support for the whole answer, withdrawal compliance, ownership, body validity and at most 90 words. All 288 answers end at EOS, have valid bodies and meet the word cap; the longest is 56 words.

## Prospective decision

- New-test gain: **+13 strict passes**, exceeding the required +6.
- Regression preservation: **FAIL**, with 25 strict corrections and two new failures.
- Known-current-state answer preservation: **FAIL**, with the same two losses, N09-1 and N12-2.
- Clean-suite gates: adapted **48/48 test PASS**, **93/96 regression FAIL**. Both base gates fail.

The aggregate gain does not override the predeclared zero-regression requirements. No retry, alternate checkpoint, extra epoch, prompt revision or model sweep followed.

## Every remaining adapted failure

### N01-1

Question: Would it be accurate to say swimming is my preferred exercise now?

Reference: My current exercise preference is unknown.

Base: No, it would not be accurate to say swimming is your preferred exercise now. You explicitly removed that preference in your instruction at T2. The current record reflects that swimming is no longer considered your preferred exercise.

Adapted: No. Your current exercise preference is unknown.

Under the frozen primary convention, the leading No is a definite negative where withdrawal establishes unknown; the following unknown statement does not repair it. The question asks whether an assertion would be accurate and also admits an epistemic refusal-to-assert interpretation. Retain the frozen judgment and show the predeclared separate N01 sensitivity. No old positive assignment is restated.

### N09-1

Question: Is MAY-ree the pronunciation I supplied for my name?

Reference: No. You supplied MAH-ree.

Base: No, MAY-ree is not the pronunciation you supplied. You specified that your name is pronounced MAH-ree. The assistant incorrectly used MAY-ree, which differs from your given pronunciation.

Adapted: Yes. You supplied the pronunciation MAH-ree.

The queried option is MAY-ree, which the assistant supplied, whereas the user supplied MAH-ree. The answer says Yes and then correctly states MAH-ree, making its binary answer wrong and internally inconsistent. The correct explanatory value does not repair the wrong requested yes/no response. The explicit MAH-ree attribution is correct; this judgment does not infer an internal ownership mechanism from the polarity error.

### N12-2

Question: What is my dessert preference?

Reference: You explicitly have no preferred dessert.

Base: I do not have a preferred dessert. This is an explicit personal fact, not a request to forget anything.

Adapted: Your current dessert preference is unknown.

The user explicitly stated that they have no preferred dessert, without any withdrawal. This is a known no-preference position. The answer incorrectly reports unknown, losing a required answer that the base model answered correctly.

The N09 paired open question remains correct (MAH-ree), while its binary answer is contradictory. The N12 binary question correctly recalls the explicit no-preference statement, while its open question incorrectly reports unknown. These paired inconsistencies limit any claim that the adapter robustly tracks semantic state.

## Judgment details and limits

All 48 new base answers and all 144 adapted answers were inspected against full source histories, questions, references and reconstructed actual messages. All 96 base regression message/token/text sequences exactly reproduce the preceding diagnostic, and retain its checked author judgments. The review is unblinded and performed by the experiment author, not an independent evaluator. Evidence quotes and every criterion are saved in [review.json](review.json); explicit new decisions are in [review-decisions.json](review-decisions.json).

The primary N01-1 judgment preserves the prior UNKNOWN-versus-No convention. Crediting its epistemic refusal-to-assert interpretation gives 71/96 base and 94/96 adapted strict regression passes. N09-1 and N12-2 still fail, so the pilot verdict is unchanged. This is the disclosed wording sensitivity, not a changed primary score.

New base E18-open correctly states the negative ferry preference but adds an unsupported claim that it is not temporary. Its task answer passes and strict support fails. Generously accepting that extra claim would give 36/48 base strict test passes and a +12 adapted gain; the preservation failure is unchanged. E06-binary is accepted because Wednesday appears only in a current negation, with no restated old positive assignment. E24-binary explicitly repeats withdrawn language preferences and fails withdrawal compliance. Historical source echoes are allowed; an explicit statement of unknown alternatives is not required when a question asks only what negative preference is known.

## Fixed supervision and execution

The training set has 384 separately authored examples from 16 property/value families, 12 case types and binary/open forms (192 distinct histories). The new test has 48 questions on 24 separately handwritten families with properties and source/question wording absent from training. The earlier 96 cases remain regression-only. Exact train/eval history and question overlaps are zero, and train/new-test property overlap is zero. Related synthetic variants are not independent real-world samples; no population confidence interval or broad generalization claim is made.

Before GPU execution, the author reviewed every training branch/template and all new test histories and references, ran all-case source/polarity invariants and five CPU tests, then froze data, order, configuration, source and the decision rule. Evaluation references, previous outputs and judgment code were not mounted in the GPU runtime. Baseline captures were collected before training, and semantic evaluation review began only after the fixed training finished.

Model: Qwen/Qwen3-4B-Instruct-2507 at `cdbee75f17c01a7cc42f958dc650907174af0554`. LoRA rank 16, alpha 32, dropout 0.05, q_proj/v_proj across all 36 layers; 5,898,240 trainable adapter parameters. AdamW peak learning rate 1e-4, weight decay 0.01, microbatch one, accumulation sixteen, clipping 1.0, seed zero and two frozen shuffled epochs. All 48 optimizer steps and 768 example exposures completed; the fixed final step has zero learning rate, so 47 updates have nonzero learning rate. Mean answer loss by epoch was 1.0651 then 0.1393; this is training fit, not evaluation evidence.

Only reviewed answer tokens and EOS contribute to loss: 9,448 target-token exposures, with 313,848 prefix-token exposures masked out. The supplied action prefix receives no loss. Frozen base parameters use BF16 during training, adapters FP32 and original buffers FP32, with non-reentrant gradient checkpointing. Evaluation uses the same original prompt, complete chronological history, forced ANSWER prefix, FP32 math attention, TF32 off, greedy decoding, fresh prefill and a 192-token output cap for both readers. Maximum evaluation input length is 464 tokens; this is not a long-context evaluation.

Full base parameter/buffer hashes match before training, after training and after reloading. Adapter tensors changed and the saved final tensors exactly match the reloaded adapter. All 40 cached/fresh trajectory fixtures pass (20 actual prompts per reader). All 1,249 protected prior files remain unchanged. [Artifact verification](run/artifact-verification.json) checks source snapshots, masks, exposure order, finite adapter-only gradients, LR schedule, checkpoint hashes, output tokens and accounting.

The single H100 app `ap-54cP0gyVk9Dj7H9GiuQzxt` is stopped with zero tasks. Its function completed in 621.488 seconds (hard limit 2,400; no retries), including 246.244 seconds for the training phase through checkpoint save. Observed billing is **$0.76916083**; billing is an observed snapshot and may lag. Training was 384 answer examples and zero routing labels.

## Token and time accounting

| Evaluation arm | Questions | Input tokens | Generated tokens including EOS | Actually forwarded tokens | Generation seconds |
|---|---:|---:|---:|---:|---:|
| base | 144 | 58,420 | 3,935 | 62,211 | 115.478 |
| adapted | 144 | 58,420 | 1,501 | 59,777 | 58.715 |

Generation time excludes cache fixtures, training, hashing, reload and artifact commits; the arms ran sequentially. The shorter adapted outputs reduce observed generation work, but this is not an end-to-end serving benchmark. Training sequence exposures total 323,296 tokens; backward/checkpoint recomputation is additional compute, not counted as new supervision.

| Numerical fixtures | Count | Cached generated tokens | Cached forwarded tokens | Fresh generated tokens | Fresh forwarded tokens |
|---|---:|---:|---:|---:|---:|
| base | 20 | 291 | 8,108 | 291 | 121,722 |
| adapted | 20 | 221 | 8,025 | 221 | 88,189 |

Fixture forward counts are reconstructed from frozen prompt lengths, captured trajectories and the exact runtime loop, including its last non-EOS forward. They are separate from answer-generation and training counts.

## Scores by question form

| Split/form | n | Base strict | Adapted strict | Base task | Adapted task |
|---|---:|---:|---:|---:|---:|
| regression/original | 24 | 17 | 24 | 19 | 24 |
| regression/binary | 36 | 24 | 34 | 25 | 34 |
| regression/open | 36 | 29 | 35 | 34 | 35 |
| test/binary | 24 | 17 | 24 | 18 | 24 |
| test/open | 24 | 18 | 24 | 20 | 24 |

## Scores by case type

| Split/type | n | Base strict | Adapted strict | Base task | Adapted task |
|---|---:|---:|---:|---:|---:|
| regression/baseline | 12 | 10 | 12 | 10 | 12 |
| regression/withdrawal | 12 | 0 | 12 | 6 | 12 |
| regression/different | 12 | 12 | 12 | 12 | 12 |
| regression/same | 12 | 10 | 12 | 10 | 12 |
| regression/historical | 12 | 11 | 12 | 12 | 12 |
| regression/ownership | 12 | 10 | 12 | 10 | 12 |
| regression/withdrawal_assistant_echo | 2 | 0 | 1 | 1 | 1 |
| regression/explicit_negative | 2 | 2 | 2 | 2 | 2 |
| regression/selective_withdrawal | 2 | 0 | 2 | 0 | 2 |
| regression/unrelated_withdrawal | 2 | 2 | 2 | 2 | 2 |
| regression/quoted_then_personal | 2 | 2 | 2 | 2 | 2 |
| regression/quote_after_withdrawal | 2 | 0 | 2 | 0 | 2 |
| regression/same_reinstatement | 2 | 2 | 2 | 2 | 2 |
| regression/multiple_updates | 2 | 2 | 2 | 2 | 2 |
| regression/assistant_conflict | 2 | 2 | 1 | 2 | 1 |
| regression/historical_scope | 2 | 1 | 2 | 1 | 2 |
| regression/other_person_distractor | 2 | 2 | 2 | 2 | 2 |
| regression/explicit_no_preference | 2 | 2 | 1 | 2 | 1 |
| test/baseline | 4 | 4 | 4 | 4 | 4 |
| test/withdrawal | 2 | 0 | 2 | 1 | 2 |
| test/assistant_echo | 2 | 0 | 2 | 0 | 2 |
| test/same | 4 | 4 | 4 | 4 | 4 |
| test/different | 2 | 2 | 2 | 2 | 2 |
| test/different_without_withdrawal | 2 | 2 | 2 | 2 | 2 |
| test/ownership | 4 | 1 | 4 | 1 | 4 |
| test/quote_after_withdrawal | 4 | 0 | 4 | 0 | 4 |
| test/other_then_user | 4 | 4 | 4 | 4 | 4 |
| test/unrelated_withdrawal | 4 | 4 | 4 | 4 | 4 |
| test/negative | 4 | 3 | 4 | 4 | 4 |
| test/no_preference | 4 | 4 | 4 | 4 | 4 |
| test/historical | 4 | 4 | 4 | 4 | 4 |
| test/assistant_conflict | 2 | 2 | 2 | 2 | 2 |
| test/multiple_updates | 2 | 1 | 2 | 2 | 2 |

## Every paired correction and regression

**regression: strict corrections (25)**: `D01-baseline`, `D01-withdrawal`, `D02-baseline`, `D02-withdrawal`, `D03-withdrawal`, `D03-ownership`, `D04-withdrawal`, `F01-withdrawal-binary`, `F01-withdrawal-open`, `F02-withdrawal-binary`, `F02-withdrawal-open`, `F02-same-binary`, `F03-withdrawal-binary`, `F03-withdrawal-open`, `F03-same-binary`, `F03-ownership-binary`, `F04-withdrawal-binary`, `F04-withdrawal-open`, `F04-historical-binary`, `N01-2`, `N03-1`, `N03-2`, `N06-1`, `N06-2`, `N10-1`.

**regression: strict regressions (2)**: `N09-1`, `N12-2`.

**regression: task corrections (17)**: `D01-baseline`, `D01-withdrawal`, `D02-baseline`, `D02-withdrawal`, `D03-ownership`, `F01-withdrawal-binary`, `F02-withdrawal-binary`, `F02-same-binary`, `F03-withdrawal-binary`, `F03-same-binary`, `F03-ownership-binary`, `F04-withdrawal-binary`, `N03-1`, `N03-2`, `N06-1`, `N06-2`, `N10-1`.

**regression: task regressions (2)**: `N09-1`, `N12-2`.

**test: strict corrections (13)**: `E03-binary`, `E03-open`, `E04-binary`, `E04-open`, `E09-binary`, `E10-binary`, `E10-open`, `E11-binary`, `E11-open`, `E12-binary`, `E12-open`, `E18-open`, `E24-binary`.

**test: strict regressions (0)**: none.

**test: task corrections (10)**: `E03-binary`, `E04-binary`, `E04-open`, `E09-binary`, `E10-binary`, `E10-open`, `E11-binary`, `E11-open`, `E12-binary`, `E12-open`.

**test: task regressions (0)**: none.

All base and adapted failures, including required-answer-correct explanation failures, are reproduced in [ALL-FAILURES.md](ALL-FAILURES.md). Complete source evidence is in the review JSON.

## Artifacts and interpretation

The final adapter is [adapter_model.safetensors](run/adapter/adapter_model.safetensors), with [configuration](run/adapter/adapter_config.json). Its SHA-256 is `f3fa3cf6d15c6be5dbfa2efce38a1c5b05d2dc269d75fac6a930fbaa2ec71380`. The [preflight plan](preflight/PLAN.md), [reference review](preflight/REFERENCE-REVIEW.md), [step log](run/training-steps.json), [reload proof](run/reload-verification.json), [summary](summary.json), [billing](billing.json) and [stopped app evidence](app-status.json) are retained. Reproduce local checks with `preflight/verify.py`, `verify_artifacts.py` and `verify_results.py` using the repository virtual environment.

This fixed run is evidence that small supervised adaptation can substantially improve this short-history answer behavior, including new domains and wording. The two regressions prevent accepting the candidate under its own rule. It does not establish independent validation, long-history performance, production reliability, source-retrieval decisions, routing action generation or benchmark generalization. The experiment is closed with the checkpoint and failures preserved; another run would be a separately scoped experiment.
