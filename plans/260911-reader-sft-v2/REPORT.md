# Revised-supervision 4B reader pilot: FAIL

The single revised-data pilot completed all 64 optimizer steps and 416 answer captures. The predeclared follow-up rule is **FAIL** under unblinded author review. Scores below compare the frozen v1 adapter with the newly trained and reloaded v2 adapter on identical messages. The original v1 experiment remains frozen with its original failed verdict.

| Split | v1 strict | v2 strict | v1 required answer | v2 required answer |
|---|---:|---:|---:|---:|
| regression | 141/144 | 141/144 | 141/144 | 141/144 |
| test | 59/64 | 62/64 | 59/64 | 63/64 |
| all | 200/208 | 203/208 | 200/208 | 204/208 |

The regression set contains all 144 previously evaluated questions, including the former 48-question test. It is reused evaluation after those results informed the revision. Only the new 64 questions are a fresh test for this follow-up; they comprise four related questions per sixteen separately authored histories.

## Predeclared acceptance rule

- Fix N09-1 and N12-2: **FAIL**; individual strict results: N09-1=fail, N12-2=fail.
- Preserve all 141 v1 regression strict passes: **PASS**. Lost cases: none.
- Preserve all earlier raw-base-correct required answers and all v1-correct required answers on the new test: **FAIL**. Earlier raw-base losses: N09-1, N12-2; new-test losses: none.
- New-test floor 60/64: **PASS** (62/64).
- New-test strict score at least v1: **PASS**.

Separate perfect-suite gates: prior: regression=FAIL, test=FAIL; adapted: regression=FAIL, test=FAIL.

The pilot threshold is not a production-readiness standard. No result here admits retrieval-policy training, routing action generation, long-history reliability or deployment.

## Known failure pairs and remaining errors

**N01-1** — Would it be accurate to say swimming is my preferred exercise now?

Reference: My current exercise preference is unknown.

v1: No. Your current exercise preference is unknown.

v2: No. Your current preference for exercise is unknown.

v2 strict: fail. The leading No remains wrong under the frozen UNKNOWN-versus-negative convention, even with a following unknown clause. The current exercise preference was withdrawn. The same question also permits an epistemic refusal-to-assert reading; report that generous sensitivity separately without changing the primary judgment.

**N09-1** — Is MAY-ree the pronunciation I supplied for my name?

Reference: No. You supplied MAH-ree.

v1: Yes. You supplied the pronunciation MAH-ree.

v2: Yes. You supplied MAH-ree.

v2 strict: fail. The question asks whether MAY-ree was supplied by the user; the source instead supplies MAH-ree, while MAY-ree belongs to the assistant reply. The leading Yes is wrong and conflicts with the answer's correct MAH-ree value. A correct value in the explanation cannot rescue the wrong requested binary answer. The factual attribution within the explanatory clause remains correct.

**N09-2** — How should you pronounce my name based on what I told you?

Reference: MAH-ree.

v1: MAH-ree.

v2: MAH-ree.

v2 strict: pass. Correctly answers the requested fact or preference from the complete supplied user history. It preserves speaker attribution, matching candidate polarity, chronology and withdrawal scope, and distinguishes negative, explicit none and unknown. The answer adds no unsupported factual claim.

**N12-1** — Have I explicitly said that I have no preferred dessert?

Reference: Yes. You explicitly said you have no preferred dessert.

v1: Yes. You explicitly said: "I do not have a preferred dessert."

v2: Yes. You explicitly said: "I do not have a preferred dessert."

v2 strict: pass. Correctly answers the requested fact or preference from the complete supplied user history. It preserves speaker attribution, matching candidate polarity, chronology and withdrawal scope, and distinguishes negative, explicit none and unknown. The answer adds no unsupported factual claim.

**N12-2** — What is my dessert preference?

Reference: You explicitly have no preferred dessert.

v1: Your current dessert preference is unknown.

v2: You have not specified a preferred dessert.

v2 strict: fail. The source explicitly establishes no preferred dessert. Saying only that a preferred dessert has not been specified omits this known-none state and presents the absence of a positive named value. That narrow literal claim is source-supported, so support and consistency remain true; it does not fulfill the requested preference answer. This is still a failure of the targeted distinction, though the explanation differs from v1's categorical unknown claim.

The new test improves by four required-answer corrections, all in explicit-none or known-negative coverage. H02-1 still shows the same binary contradiction on a new surname, while code, numeric-suffix and entrance comparisons pass. This supports a narrow improvement rather than a general repair of assertion comparison.

H09-4 is a new strict-only failure: it turns not preferred into an explicit rejection. The required negative and unknown-alternative answer remains correct. Generously interpreting reject as reject-as-the-preferred-option yields 63/64 v2 strict test passes instead of 62/64, with no new strict test regression. The two required target failures still leave the prospective rule failed. E18 negative-preference paraphrases retain the earlier interpretation and introduce no categorical refusal or duration claim.

For N12-2, the v2 claim that no particular preferred dessert was specified can be literally true; support stays true, but the answer omits the explicitly known no-preference state. Likewise, H11-4 in v1 supplies only the unknown alternative and omits the known negative. Required-answer completeness and source consistency are scored separately.

All four new-test questions pass within 11/16 families for v1 and 14/16 for v2 under primary strict scoring. These are related question groups, not independent reliability estimates.

All remaining v2 strict failures: `N01-1`, `N09-1`, `N12-2`, `H02-1`, `H09-4`.

Every v1 and v2 strict failure is reproduced with its question, reference, answer and judgment in [ALL-FAILURES.md](ALL-FAILURES.md). The [complete review](review.json) retains exact full-history and actual-message evidence for every answer. Binary/open answers sharing a history are scored individually; conflicting paired answers cannot be rescued by selecting the better form.

## Supervision, isolation and interpretation

The revision retains all 384 original training cases unchanged and adds 128 new cases: 64 user-assertion comparisons across eight factual families, with and without assistant conflicts, and 64 positive/none/negative/withdrawn preference contrasts across eight additional families. There are 512 examples, 32 families and 240 distinct histories. Prior evaluation histories, questions and model answers are excluded from training. The test uses sixteen new properties absent from all training and prior evaluation; exact train/eval history and query overlaps are zero.

The author reviewed the two new training constructors, all sixteen new training family definitions, every new test history and all 64 test references before freezing. All-case evidence-role/bounds, polarity, scope, target-length and overlap checks passed, as did the five answer-mask/precision CPU tests. This is author review plus mechanical checks, not independent validation.

The coverage gaps motivate this experiment but are not proven causes of the earlier failures. V2 is trained from the original base, using two epochs of the expanded mixture. Compared with v1 it also has more optimizer steps, different shuffled orders and a longer LR schedule. The result compares these complete recipes; it does not isolate the causal effect of the added examples. The synthetic families and four related questions per test history do not justify population or real-world reliability claims.

All 144 v1 regression message/token/text sequences reproduce exactly and retain their source-checked prior judgments. All 64 new v1 answers and all 208 v2 answers receive new unblinded author review against complete histories, questions, references and reconstructed actual prompts. Semantic evaluation review began after the fixed training finished. The N01 wording ambiguity retains its frozen primary judgment; the separate generous sensitivity is shown below and does not alter the primary rule.

| N01 sensitivity | Regression strict | Regression required answer |
|---|---:|---:|
| prior | 142/144 | 142/144 |
| adapted | 142/144 | 142/144 |

## Fixed runtime and integrity

Qwen/Qwen3-4B-Instruct-2507 revision `cdbee75f17c01a7cc42f958dc650907174af0554`; Torch 2.7.1, Transformers 4.55.2 and PEFT 0.17.0. LoRA rank 16/alpha 32/dropout .05 on q_proj and v_proj in all 36 layers, 5,898,240 trainable parameters. Seed zero, AdamW peak LR 1e-4/weight decay .01, microbatch one, accumulation sixteen and clipping 1. Three-step warmup and linear decay end at LR zero on step 64; 63 steps have nonzero LR. No checkpoint selection or early stopping. Epoch mean answer losses: 0.948758, 0.095448. These are training-fit measures.

All 1,024 example exposures completed. Answer/EOS target exposures: 11,988; masked prefix exposures: 409,548. No routing or supplied ANSWER-prefix loss is trained. BF16 frozen base parameters, FP32 adapter parameters and original FP32 buffers are used for training, with non-reentrant gradient checkpointing. Evaluation uses FP32 math attention, TF32 disabled, original answer-only prompt, full chronological history, fresh prefill, greedy decoding and a 192-token/90-word cap.

The comparator reads only the two hash-pinned prior adapter files. A dedicated output volume keeps old model captures and evaluation references outside the runtime mounts. Training references are intentionally mounted as supervision; evaluation references and review code are not. All base parameter and buffer hashes are unchanged across training/reload, adapter weights changed, and saved/reloaded adapter tensors are exactly equal. All 40 cached/fresh checks pass. All 1321 protected files remain unchanged.

The single app `ap-xQP6Ifd4mWBB0t8mKYk5VB` is stopped with zero tasks. Function time: 632.967 s; training phase through save: 255.964 s. Hard limit 2,400 seconds, internal limit 2,300 seconds, no retries. Observed cost: **$0.79357782**, a billing snapshot that can lag execution. No automatic follow-up run occurred.

## Accounting

| Arm | Answers | Input tokens | Generated tokens incl. EOS | Forwarded tokens | Generation seconds |
|---|---:|---:|---:|---:|---:|
| prior | 208 | 83,151 | 2,381 | 85,324 | 76.577 |
| adapted | 208 | 83,151 | 2,524 | 85,467 | 79.511 |

All 416 answers ended at EOS: True. Valid bodies: 416; within 90 words: 416; maximum words: 32. Maximum input is 464 tokens. Training prefix/target exposures exclude backward and gradient-checkpoint recomputation; generation seconds exclude training, hash/reload checks, numerical fixtures and commits. This is not a serving benchmark.

| Fixture arm | Count | Cached generated | Cached forwarded | Fresh generated | Fresh forwarded |
|---|---:|---:|---:|---:|---:|
| prior | 20 | 233 | 8179 | 233 | 94044 |
| adapted | 20 | 249 | 8196 | 249 | 100971 |

Fixture forwarded-token counts are reconstructed from the frozen runtime loop and captured trajectories, including the last non-EOS forward. They are separate from evaluation and training counts.

## Question form

| Split/category | n | v1 strict | v2 strict | v1 task | v2 task |
|---|---:|---:|---:|---:|---:|
| regression/original | 24 | 24 | 24 | 24 | 24 |
| regression/binary | 60 | 58 | 58 | 58 | 58 |
| regression/open | 60 | 59 | 59 | 59 | 59 |
| test/binary | 32 | 30 | 31 | 30 | 31 |
| test/open | 32 | 29 | 31 | 29 | 32 |

## Case type

| Split/category | n | v1 strict | v2 strict | v1 task | v2 task |
|---|---:|---:|---:|---:|---:|
| regression/baseline | 16 | 16 | 16 | 16 | 16 |
| regression/withdrawal | 14 | 14 | 14 | 14 | 14 |
| regression/different | 14 | 14 | 14 | 14 | 14 |
| regression/same | 16 | 16 | 16 | 16 | 16 |
| regression/historical | 16 | 16 | 16 | 16 | 16 |
| regression/ownership | 16 | 16 | 16 | 16 | 16 |
| regression/withdrawal_assistant_echo | 2 | 1 | 1 | 1 | 1 |
| regression/explicit_negative | 2 | 2 | 2 | 2 | 2 |
| regression/selective_withdrawal | 2 | 2 | 2 | 2 | 2 |
| regression/unrelated_withdrawal | 6 | 6 | 6 | 6 | 6 |
| regression/quoted_then_personal | 2 | 2 | 2 | 2 | 2 |
| regression/quote_after_withdrawal | 6 | 6 | 6 | 6 | 6 |
| regression/same_reinstatement | 2 | 2 | 2 | 2 | 2 |
| regression/multiple_updates | 4 | 4 | 4 | 4 | 4 |
| regression/assistant_conflict | 4 | 3 | 3 | 3 | 3 |
| regression/historical_scope | 2 | 2 | 2 | 2 | 2 |
| regression/other_person_distractor | 2 | 2 | 2 | 2 | 2 |
| regression/explicit_no_preference | 2 | 1 | 1 | 1 | 1 |
| regression/assistant_echo | 2 | 2 | 2 | 2 | 2 |
| regression/different_without_withdrawal | 2 | 2 | 2 | 2 | 2 |
| regression/other_then_user | 4 | 4 | 4 | 4 | 4 |
| regression/negative | 4 | 4 | 4 | 4 | 4 |
| regression/no_preference | 4 | 4 | 4 | 4 | 4 |
| test/assertion_conflict | 16 | 15 | 15 | 15 | 15 |
| test/explicit_none | 16 | 13 | 16 | 13 | 16 |
| test/explicit_negative | 16 | 15 | 15 | 15 | 16 |
| test/withdrawal_scope | 16 | 16 | 16 | 16 | 16 |

## Every correction and regression

**regression strict corrections (0)**: none.

**regression strict regressions (0)**: none.

**regression task corrections (0)**: none.

**regression task regressions (0)**: none.

**test strict corrections (4)**: `H05-3`, `H06-4`, `H07-1`, `H11-4`.

**test strict regressions (1)**: `H09-4`.

**test task corrections (4)**: `H05-3`, `H06-4`, `H07-1`, `H11-4`.

**test task regressions (0)**: none.

## Saved artifacts

The final [adapter weights](run/adapter/adapter_model.safetensors) have SHA-256 `87e605f14123dc51a98fcc0a025b80776c98bb20be50aca2843b63171e5880d1`. The [plan](preflight/PLAN.md), [reference review](preflight/REFERENCE-REVIEW.md), [step log](run/training-steps.json), [reload proof](run/reload-verification.json), [artifact verification](run/artifact-verification.json), [summary](summary.json), [billing](billing.json) and [app state](app-status.json) are retained. Use `preflight/verify.py`, `verify_artifacts.py` and `verify_results.py` with the repository virtual environment for local verification.
