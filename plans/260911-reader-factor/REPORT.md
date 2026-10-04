# Fact identification versus answer selection: frozen 4B diagnostic

The original pronunciation and dessert errors are repaired by independently extracting a fact record and then answering from it. This is useful evidence for a staged reader, but not a complete fix: extraction loses negative-preference state, and selection still turns unknown into a categorical No even with correct facts and an explicit question interpretation. No additional training occurred.

This is a descriptive, unblinded author-reviewed challenge set: sixteen short histories, four related questions each, four answer arms. Four histories are reused (twelve exact prior questions plus four added controls); twelve histories and 48 questions are new. The 64 correlated questions are not 64 independent trials or a random benchmark.

## Matched answer results

Strict correctness requires all seven frozen criteria: task completion, source consistency, visible support, withdrawal compliance, ownership, valid body and <=90 words. Required-answer correctness checks the requested answer separately from explanation support.

| Condition | Strict, all 64 | Required, all 64 | Strict, 16 reused-history questions | Strict, 48 new questions |
|---|---:|---:|---:|---:|
| direct | 56/64 | 57/64 | 13/16 | 43/48 |
| extracted_fact | 59/64 | 59/64 | 13/16 | 46/48 |
| oracle_fact | 62/64 | 62/64 | 16/16 | 46/48 |
| oracle_query | 60/64 | 60/64 | 16/16 | 44/48 |

Direct uses the original complete archive and answer prompt. Extracted fact uses a model-produced record and a different, fixed selection prompt. Oracle fact replaces that record with a reviewed correct record under the same selection prompt. Oracle query additionally supplies a reviewed operation/candidate interpretation. These oracle inputs are intentional privileges; no final answer reference or prior output was mounted.

## What the interventions reveal

- **N09-1, pronunciation:** direct says `Yes. You supplied MAH-ree.` when asked about MAY-ree. The independent extraction correctly records MAH-ree; all three record arms correctly answer No. N09-2 and both added question controls stay correct.
- **N12-2, dessert:** direct says only `You have not specified a preferred dessert.` Extraction correctly records explicit none, and all record arms say the user has no preferred dessert. The other three forms stay correct.
- **Candidate comparison:** the same direct wrong-Yes/right-value error occurs for Ravn/Raven, Soren/Sorren, and Vesta/Pallas. All record arms fix them. Vesta/Pallas are distant strings and the archive contains no assistant value substitution, so this is not confined to near spellings or conflicting assistant values. nah-LO/nah-RO and silver/orange work even directly.
- **Known none:** besides dessert, direct omits explicit none for the open soup and bath-towel questions. The pen-cap binary answer has the correct No but falsely calls the preference unknown. All record arms fix these. Other question forms on those same histories work directly.
- **Fact extraction:** all three negative-preference histories become status none. For velvet, the extracted quote also drops the explicit negative; three downstream answers regress. For laces and Marble, the quote retains the negative, and generated answers recover all eight requested answers from that quote despite the wrong status. Successful downstream prose therefore does not certify the typed record.
- **Selection with correct facts:** both new withdrawal histories have correct unknown records. Extracted-fact and oracle-fact answers still give categorical No on the alternative-candidate questions X11-2 and X12-2. Oracle query fixes none of these and introduces No on X11-1 and X12-1 as well. More explicit question information is not sufficient.

Changing to record prompts also changes formatting, instructions and available evidence, so these behavioral interventions do not prove that the direct model internally implements separate extraction and selection stages. The experiment localizes failures in this constructed pipeline. It does not admit deployment or retrieval-policy training.

## Extraction and record faithfulness

| Check | Histories passing |
|---|---:|
| Schema and exact user-span checks | 16/16 |
| Source-reviewed semantic meaning | 13/16 |
| Usable semantically correct record | 13/16 |
| Literal status/value match to gold | 12/16 |
| Quote sufficient for the true state | 15/16 |
| Correct user ownership | 16/16 |

The semantic score accepts `silver` as a sufficient contextual value for the parcel pickup counter, since the property and exact quote say silver counter. The frozen literal selector does not equate those strings. This is one representation mismatch, separate from the three negative-to-none semantic errors. No alias mapping was added after inference.

With semantically correct records, generated selection passes 50/52 questions and fails the two withdrawal binaries. With incorrect records, it passes 9/12: one velvet candidate answer is correct despite lost state, and eight laces/Marble answers recover from the retained negative quotes. There are no invalid-record fallbacks to credit. Record-prompt faithfulness is 62/64 for extracted fact, 62/64 for oracle fact and 60/64 for oracle query; correctness relative to the original source is a separate criterion. In extracted fact, only 54/64 answers follow the typed status: eight source-correct answers instead use quotes contradicting that status.

| Stream | Gold state/value | Generated state/value | Semantic correctness | Literal match |
|---|---|---|---|
| R01 | value: MAH-ree | value: MAH-ree | True | True |
| R02 | none: None | none: None | True | True |
| R03 | value: Ravn | value: Ravn | True | True |
| R04 | negative: Velvet | none: None | False | False |
| X01 | value: Soren | value: Soren | True | True |
| X02 | value: nah-LO | value: nah-LO | True | True |
| X03 | value: silver counter | value: silver | True | False |
| X04 | value: Vesta | value: Vesta | True | True |
| X05 | none: None | none: None | True | True |
| X06 | none: None | none: None | True | True |
| X07 | none: None | none: None | True | True |
| X08 | none: None | none: None | True | True |
| X09 | negative: laces | none: None | False | False |
| X10 | negative: Marble | none: None | False | False |
| X11 | unknown: None | unknown: None | True | True |
| X12 | unknown: None | unknown: None | True | True |

## Deterministic selector with oracle query parsing

Gold record plus reviewed query interpretation gives 64/64 by construction. Model record plus the same oracle query interpretation gives **52/64**. This is not a learned or autonomous query parser. It uses only case-folded literal comparisons and does not reason over the quote.

The twelve failures comprise three per negative history (the stated-negative question and two lookups) and three on the silver abbreviation (positive candidate plus two lookups). Generated prose recovers from context/quotes where the literal selector cannot, but the literal selector preserves unknown correctly. This exposes a tradeoff between robust representations and flexible interpretation; neither component is solved by this result.

## Matched corrections and regressions

- direct->extracted_fact, strict: corrected N09-1, N12-2, H02-1, X01-1, X04-1, X05-3, X06-1, X07-3; regressed H11-2, H11-3, H11-4, X11-2, X12-2.
- direct->extracted_fact, required: corrected N09-1, N12-2, H02-1, X01-1, X04-1, X05-3, X07-3; regressed H11-2, H11-3, H11-4, X11-2, X12-2.
- direct->oracle_fact, strict: corrected N09-1, N12-2, H02-1, X01-1, X04-1, X05-3, X06-1, X07-3; regressed X11-2, X12-2.
- direct->oracle_fact, required: corrected N09-1, N12-2, H02-1, X01-1, X04-1, X05-3, X07-3; regressed X11-2, X12-2.
- oracle_fact->oracle_query, strict: corrected none; regressed X11-1, X12-1.
- oracle_fact->oracle_query, required: corrected none; regressed X11-1, X12-1.
- extracted_fact->oracle_fact, strict: corrected H11-2, H11-3, H11-4; regressed none.
- extracted_fact->oracle_fact, required: corrected H11-2, H11-3, H11-4; regressed none.

## Breakdown by fact type and question form

| Group | Questions | Direct strict | Extracted strict | Oracle fact strict | Oracle query strict |
|---|---:|---:|---:|---:|---:|
| kind:assertion | 24 | 20 | 24 | 24 | 24 |
| kind:negative | 12 | 12 | 9 | 12 | 12 |
| kind:none | 20 | 16 | 20 | 20 | 20 |
| kind:unknown | 8 | 8 | 6 | 6 | 4 |
| question_form:binary | 32 | 27 | 29 | 30 | 28 |
| question_form:open | 32 | 29 | 30 | 32 | 32 |

For each history, all four related answers are strictly correct on direct: 8/16, extracted_fact: 13/16, oracle_fact: 14/16, oracle_query: 14/16. These counts describe consistency across question forms, not independent replicated trials.

## Wording sensitivity and review limits

The frozen primary rule counts a categorical `No.` after withdrawal as a negative assignment, even when followed by an unknown clause. `No evidence supports ...` is instead an epistemic statement and passes. If every categorical-No failure were read generously as refusal to assert a candidate, strict scores would be direct 56/64, extracted 61/64, oracle fact 64/64 and oracle query 64/64. Primary scores remain unchanged. X12-1 in oracle query also says no preference was explicitly stated, which can be read historically and is unsupported on that reading; the generous score assumes a current-evidence reading.

Candidate-scoped “no preference for laces” is accepted as denying preference for laces when the source quote states that negative; it is not accepted as evidence of global none. “Not specified a preference” alone on an explicit-none lookup is incomplete, following the retained N12-2 rule. Full source, actual prompt, response and decision are recorded for every answer. Review was unblinded and performed by the experiment author, not an independent judge.

## Execution, provenance and accounting

App [ap-qKXz6IWvLWSaE8OEoxobsy](https://modal.com/apps/syntracts/main/ap-qKXz6IWvLWSaE8OEoxobsy) completed in 192.945 function seconds; stopped with zero tasks. One H100, zero retries, hard timeout 1,200 seconds. Observed billing: **$0.23685322**, snapshot 2026-09-11T07:33:50.671919+00:00 (billing may lag).

All 256 answers and 16 extractions completed. All answers satisfy body and word limits. All 25 cached/fresh checks pass, including initial argmax and up to sixteen generated tokens. All twelve prior direct prompts, token sequences and texts reproduce exactly. Complete base and adapter tensor hashes are identical before/after, all parameters frozen, zero optimizer steps/labels, and all 1,390 protected files unchanged.

| Calls | Count | Input tokens | Generated tokens | Forwarded tokens | Generation seconds |
|---|---:|---:|---:|---:|---:|
| extract | 16 | 5067 | 528 | 5579 | 11.555 |
| direct | 64 | 24299 | 832 | 25067 | 21.368 |
| oracle_fact | 64 | 18071 | 720 | 18727 | 17.797 |
| extracted_fact | 64 | 18003 | 735 | 18674 | 18.116 |
| oracle_query | 64 | 19256 | 747 | 19939 | 18.390 |

Including the sixteen one-time extractions amortized across four queries each, extracted-fact input tokens total 23070, generated tokens 1263, forwarded tokens 24253, and summed generation time 29.671s. This is not an end-to-end latency benchmark or a serving cost result. Gates, loading, commits and verification add overhead; gate accounting is separately retained in summary.json. Oracle authoring costs are not included.

Artifacts: [frozen plan](preflight/PLAN.md), [all failures](ALL-FAILURES.md), [complete review](review.json), [explicit author decisions](review-decisions.json), [summary](summary.json), [artifact verification](run/artifact-verification.json). Reproduce local verification with `.venv/bin/python plans/260911-reader-factor/verify_results.py`. No follow-up run was launched.
