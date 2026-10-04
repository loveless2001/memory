# Structured-decision supervision: matched four-condition experiment

**Prospective result: FAIL.**

The structured-decision recipe fails its prospective rule. Its new strict score is 145/160 (90.625%), below the required 152/160 and below the matched prose continuation at 155/160 (96.875%). It also loses 45 of the 259 protected previously correct cases. These are failures of the tested recipe, despite successful numerical and artifact verification.

The ordinary-answer continuation produces the stronger result on this packet: 130 to 155 new strict passes, with 26 corrections and one new failure. On the 260 regression questions it moves from 250 to 252, with nine corrections and seven new failures relative to current v2. Eight failures fall in the broader union of previously correct cases, so it also does not establish regression-free progress.

The structured disadvantage remains when only final answers are scored: 147/160 new and 222/260 regression, versus 155/160 and 252/260 for the prose continuation. The conclusion therefore does not depend solely on the extra record criteria. Training teaches much of the format (new schema validity rises from 98/160 to 155/160), but does not make the state, source selection and decision jointly reliable.

All scores below use the frozen source references and unblinded author review. This is a selected synthetic pilot with forty new histories, not independent external validation. Both new continuations started from the same frozen v2 checkpoint; ordinary prose and structured targets used the same 512 source/question pairs and 64 updates.

## Main results

| Condition | New strict /160 | New rendered-only strict /160 | New required answer /160 | Regression strict /260 | Protected regression losses /259 |
|---|---:|---:|---:|---:|---:|
| current_direct | 130 | 130 | 131 | 250 | 9 |
| current_decision | 20 | 47 | 63 | 29 | 230 |
| trained_direct | 155 | 155 | 156 | 252 | 8 |
| trained_decision | 145 | 147 | 149 | 215 | 45 |

Strict scores require the prior seven final-answer criteria. Decision arms additionally require usable schema, correct state/scope/relation, query interpretation, decision, evidence and ownership. Rendered-only correctness omits those additional record criteria; it cannot rescue a wrong record for the primary decision. Invalid records fail even if the correct response would have been unknown.

The four conditions are: current v2 with its original answer prompt; current v2 with the structured prompt and deterministic renderer; v2 continued on ordinary answers; and v2 independently continued on structured decisions. Each condition receives only the complete archive and question. Prose/decision user messages are identical; system instructions and output targets differ. No oracle property, candidate, scope, state or query interpretation is supplied at inference.

## Frozen pass rule

| Requirement | Result |
|---|---|
| new_strict_at_least_152 | FAIL |
| beats_current_direct | PASS |
| beats_trained_direct | FAIL |
| zero_protected_regression_losses | FAIL |
| numerical_training_and_artifact_verification | PASS |

The 95% threshold is 152/160. The trained decision model must strictly exceed both current-direct and trained-direct new-test scores and lose none of the 259 protected regression cases. The protection mask is the union of previously strict-correct non-oracle answers on exact matching histories/questions across the prior seven experiments. It includes previous model sizes, prompts and extracted pipelines. N01-1 is the only regression without such a prior pass; it is still evaluated. No score threshold was changed after inference.

Protected regression losses for trained_decision: D01-withdrawal, D01-ownership, D02-withdrawal, D02-ownership, D03-ownership, D04-same, D04-ownership, F01-ownership-binary, F01-ownership-open, F02-ownership-binary, F03-ownership-binary, F03-ownership-open, F04-ownership-binary, F04-ownership-open, N04-1, N07-1, N07-2, N09-1, E01-binary, E04-binary, E04-open, E08-binary, E09-binary, E16-binary, E18-binary, E18-open, H01-1, H02-1, H04-2, H07-1, H09-1, H09-2, H09-3, H09-4, H11-1, H11-2, H11-3, H11-4, H12-2, H15-4, R02-extra-2, X03-2, X09-4, X10-1, X10-3.

## Matched changes on the new questions

| Comparison | Strict corrections / regressions | Rendered corrections / regressions | Required-answer corrections / regressions |
|---|---:|---:|---:|
| current_direct->current_decision | 0 / 110 | 10 / 93 | 10 / 78 |
| current_direct->trained_direct | 26 / 1 | 26 / 1 | 27 / 2 |
| current_direct->trained_decision | 24 / 9 | 25 / 8 | 24 / 6 |
| current_decision->trained_decision | 125 / 0 | 100 / 0 | 87 / 1 |
| trained_direct->trained_decision | 5 / 15 | 5 / 13 | 4 / 11 |

All new-test and regression transitions, including every corrected and regressed ID, are retained in summary.json. [ALL-FAILURES.md](ALL-FAILURES.md) contains every strict failure with raw output, rendered answer, source, original reference and the author judgment.

## Structured record accuracy

| Condition / split | Schema valid | State correct | Query interpretation correct | Decision correct | Evidence sufficient | Ownership correct | Full semantic record correct |
|---|---:|---:|---:|---:|---:|---:|---:|
| current_decision / test | 98 | 61 | 66 | 61 | 140 | 140 | 20 |
| trained_decision / test | 155 | 146 | 159 | 154 | 158 | 160 | 145 |
| current_decision / regression | 121 | 120 | 107 | 116 | 210 | 242 | 30 |
| trained_decision / regression | 238 | 240 | 253 | 240 | 245 | 248 | 228 |

On the new questions, exact full canonical record agreement (all nine fields, ignoring JSON key order/whitespace) is current_decision: 17/160, trained_decision: 140/160. Exact agreement on the seven semantic fields excluding turn/quote is current_decision: 20/160, trained_decision: 143/160. These literal diagnostics do not replace context-sensitive author review; sufficient alternative quotes and semantically equivalent value phrases can still be correct.

A schema/span check only establishes that fields and copied strings have valid locations. It does not establish whose fact is expressed, whether a withdrawal controls, whether an alternative candidate remains unknown, or whether the binary decision is correct. Source-grounded semantic equivalence is judged separately from exact canonical text. Internal candidate fields and current-source quotes are not displayed as final answers. Given correctly scoped records, the renderer preserves unknown and historical scope without repeating withdrawn values in current answers; it cannot correct wrongly encoded current facts.

## New-test breakdown

| History type | Questions | Current direct | Current decision | Trained direct | Trained decision |
|---|---:|---:|---:|---:|---:|
| different | 20 | 19 | 5 | 20 | 13 |
| historical | 20 | 19 | 4 | 19 | 20 |
| negative | 20 | 11 | 0 | 18 | 16 |
| none | 20 | 13 | 0 | 19 | 20 |
| ownership | 20 | 14 | 0 | 20 | 20 |
| positive | 20 | 17 | 5 | 19 | 19 |
| same | 20 | 19 | 6 | 20 | 18 |
| withdrawal | 20 | 18 | 0 | 20 | 19 |

All four questions on a new history are strictly correct for current_direct: 19/40, current_decision: 0/40, trained_direct: 35/40, trained_decision: 30/40.

| Trained-decision comparison | Mean strict accuracy difference | Descriptive 95% history-bootstrap interval |
|---|---:|---|
| versus current_direct | 9.38 pp | [0.00, 18.12] pp |
| versus current_decision | 78.12 pp | [70.62, 85.00] pp |
| versus trained_direct | -6.25 pp | [-13.75, 0.00] pp |

Descriptive bootstrap over forty synthetic histories. It is not a random external sample, not independent question-level inference, and intervals do not modify the frozen pilot gate.

## Training and inference accounting

Each continuation sees the same 512 examples twice, in the same two frozen shuffled orders. Each uses 64 optimizer steps, including the same final zero-LR step of the existing linear schedule. Starting adapter files/tensors are identical; no checkpoint from one continuation initializes the other. The LoRA shape, optimizer, seed and update count are matched. Target lengths, system prompt lengths, dropout draw shapes, computation and elapsed times differ. This tests the complete supervision recipe; it is not a matched-FLOP or isolated-format causal estimate.

| Continuation | Exposures | Updates | Supervised target tokens | Masked prefix tokens | Training seconds | Adapter SHA-256 |
|---|---:|---:|---:|---:|---:|---|
| trained_decision | 1024 | 64 | 57438 | 658248 | 274.797 | 27fb229a448f2a5909ed9fb1a7b1d771fa74e23e23f8b9800f1122de6d6dd3da |
| trained_direct | 1024 | 64 | 13330 | 412488 | 263.644 | ddbe312e0eef9e265662165f9dc81e1c592f5d9aea6bd4c27ab3fcb6fbfa41e5 |

| Evaluation condition | Calls | Input tokens | Generated tokens | Forwarded tokens | Generation seconds |
|---|---:|---:|---:|---:|---:|
| current_direct | 420 | 168697 | 5227 | 173504 | 174.338 |
| current_decision | 420 | 269497 | 23108 | 292185 | 677.092 |
| trained_direct | 420 | 168697 | 5165 | 173442 | 177.326 |
| trained_decision | 420 | 269497 | 23822 | 292899 | 734.251 |

Prose has a 192-token generation cap; structured output has a 256-token cap for its nine fields and source quote. Both final answer formats have a 90-word limit. All calls use fresh prefill, greedy decoding, FP32 math attention and TF32 off. Gate token accounting is separately retained in summary.json. Generation seconds exclude loading, training, commits, local rendering/review and other overhead, so this is not a serving latency benchmark.

App [ap-BwyTowAv8QgAAEKJr6Tuw8](https://modal.com/apps/syntracts/main/ap-BwyTowAv8QgAAEKJr6Tuw8) completed in 2740.093 function seconds. One H100, four CPUs, 32 GiB RAM; 3,600-second hard ceiling and zero retries. Observed billing is **$3.35500240** at 2026-09-11T08:51:22.204239+00:00; billing can lag. The app is stopped with zero tasks.

## Verification and limits

All 1680 captures and 80/80 cached/fresh fixtures completed. All 260 prior direct prompts, token sequences and texts reproduce exactly. Both trainings have finite loss/gradients, exact exposure order, target-only supervision and adapter-only updates. Complete base parameters/buffers stayed unchanged; both saved adapters reload exactly and their tensors remain unchanged after inference. All 1460 protected prior files are unchanged.

Training has sixteen novel properties across eight history types (120 distinct histories); the forty test properties and their exact histories/questions are disjoint from this training, prior training and regression. Four related questions share each new history. The synthetic templates and author review limit generalization. Correct enum output and correct rendering do not prove an internal reasoning mechanism or reliable long-context retrieval.

The categorical-No versus unknown rule from prior evaluations remains primary. Alternative epistemic readings, if applicable, are disclosed in review decisions without changing primary verdicts. Scope, polarity and factual support are evaluated against full source, not a keyword-based Yes/No score.

## What this changes

Paired extra supervision improves ordinary prose accuracy on the new synthetic packet. The tested structured-decision recipe does not beat that control and produces more regression failures. This supports retaining the prose continuation as an experimental checkpoint, while rejecting the structured recipe under the frozen rule. Neither result clears the prior-correctness preservation requirement for a production reader.

The new structured failures span several mechanisms visible in the outputs: positive facts are encoded as negative (J03-1, J22-2); a negative preference is confused with having no preference (J07-4, J10-3/4); unknown alternatives receive categorical No (J06-3); current state after withdrawal or reinstatement is wrong (J18-3, J24-2, J29-1, J30-1/4); and the restored Arllen string is misspelled Arlen in all four J26 answers. J18-3 and J24-2 illustrate why a correct rendered unknown cannot validate the underlying record.

Regression failures add quoted-person ownership errors, missed reinstatements, incorrect query operations and evidence selection failures. Some schema failures are purely case or span conformity errors, such as ferries/Ferries, spiral/Spiral, velvet/Velvet, marble/Marble and Roman numerals versus Roman-numeral. They remain failures of the frozen exact-span protocol even where semantic review accepts the meaning. Other records choose a follow-up instruction that omits the needed value, or an assistant echo after withdrawal. The full inventory distinguishes these causes; no parser repair or alternate scoring was applied after seeing outputs.

The prose continuation fixes every one of its predecessor's new failures except J01-1, J07-3, J09-3 and J11-1, but adds J39-2 (a historical binary mismatch). Its retained failures include near-spelling confusion, unsupported No for an unspecified alternative, strengthening non-preference into dislike, and replacing explicit none with unknown. Those remain concrete reliability gaps despite the higher aggregate score.

The two continuations match examples, source histories, initial adapter, shuffled order and 64 optimizer updates. Structured supervision uses 57,438 target tokens versus 13,330 for prose, and 658,248 masked prefix tokens versus 412,488. For 420 evaluation calls, trained structured output forwards 292,899 tokens versus 173,442 and takes 734.251 versus 177.326 measured generation seconds. These are recipe-level accounting differences on this runtime, not an isolated format effect or a serving benchmark.

The four questions per new history are correlated: 30/40 complete histories pass for trained decisions and 35/40 for trained prose. The descriptive history-bootstrap interval for their strict difference is [-13.75, 0.00] percentage points. One selected synthetic packet, one training seed and unblinded author judgments cannot establish generalization or statistical superiority. Frozen thresholds, references, all outputs and all per-answer judgments remain available for independent review.

N01-1 now receives unknown from both continuations and passes the same prior primary convention; the original current-direct answer is retained as a failure. Source ownership is evaluated using the entire passage, including fiction or other-person framing. Bare or historical quotations can answer what-did-I-say questions without asserting a current preference; explicitly current assertions after withdrawal fail. These distinctions explain individual judgments rather than changing the prospective rule.

Artifacts: [frozen plan](preflight/PLAN.md), [reference review](preflight/REFERENCE-REVIEW.md), [review](review.json), [explicit decisions](review-decisions.json), [rendered decisions](rendered-decisions.json), [summary](summary.json), [verification](run/artifact-verification.json). Reproduce the final checks with `.venv/bin/python plans/260911-reader-decision/verify_results.py`. No follow-up run was launched.
