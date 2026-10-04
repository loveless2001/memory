# Reader presentation diagnostic — completed 2026-09-11

All **96/96 conditions completed**, and all **40/40 cache checks passed**.
The primary JSON chronological configuration passes **17/24**, failing the
predeclared 24/24 gate. Chronological display resolves the same-value
reinstatement failures in this diagnostic, but substantial reader errors remain.
Training stays paused. These are unblinded Codex author judgments, with every
answer, reason and exact source quote preserved in [review.json](review.json).

## Results

Strict pass requires every frozen criterion: required answer completeness,
source consistency, whole-answer visible support, withdrawal compliance,
correct ownership, valid answer body and at most 90 words.

| Configuration | Required value/task correct | Strict pass | Strict fail |
| --- | ---: | ---: | ---: |
| Plain, chronological | 20/24 | 17/24 | 7/24 |
| Plain, withdrawals last | 16/24 | 13/24 | 11/24 |
| JSON, chronological — primary | 19/24 | 17/24 | 7/24 |
| JSON, withdrawals last | 15/24 | 11/24 | 13/24 |
| Total | 70/96 | 58/96 | 38/96 |

The following table reports strict passes. Each cell contains four cases, one
per synthetic family; repeated conditions are not independent samples.

| Case type | Plain chronological | Plain withdrawals last | JSON chronological | JSON withdrawals last |
| --- | ---: | ---: | ---: | ---: |
| Positive baseline | 2/4 | 2/4 | 2/4 | 2/4 |
| Withdrawal to unknown | 0/4 | 1/4 | 0/4 | 0/4 |
| Later different value | 3/4 | 2/4 | 4/4 | 2/4 |
| Later same value | 4/4 | 0/4 | 4/4 | 0/4 |
| Historical original statement | 4/4 | 4/4 | 4/4 | 4/4 |
| Fictional-speaker ownership | 4/4 | 4/4 | 3/4 | 3/4 |

For JSON, changing withdrawals-last display to chronological fixes six strict
failures and introduces none, satisfying the predeclared order-help criterion.
For plain text, it fixes six but introduces two strict failures, a mixed result.
Both plain regressions involve restating a withdrawn preference in an explanation,
not a wrong final value. The primary JSON chronological gate still fails.

## What the answers establish

**Displayed order affects same-value reinstatement.** All four families pass
under both chronological wrappers (8/8), while all fail when the earlier withdrawal
is displayed last (0/8). Original turn numbers, role labels and complete source
text are preserved. For `D02-same`, T2 withdraws the activity preference and T4
explicitly reinstates it. The JSON chronological answer recognizes T4. The JSON
withdrawals-last answer instead says “no subsequent statement reinstates it.”
This is a matched short-source presentation result; it does not identify the
model's internal mechanism or establish an effect in the broader runtime.

**Withdrawal is still confused with a negative.** All eight activity withdrawal
conditions answer definite No when the required current value is unknown. For
example, `D02-withdrawal` with JSON chronological answers: “No, you do not
currently enjoy amateur astronomy. You explicitly requested that this personal
detail be forgotten.” The source establishes no later dislike. The eight named
fruit/tea withdrawal conditions correctly answer unknown, but seven repeat the
withdrawn old preference, violating the output rule. Thus withdrawal has 8/16
correct required values but only 1/16 strict passes.

**Some baselines invent staleness.** All eight activity baseline conditions
abstain despite a direct positive assertion with no withdrawal, update or supplied
time gap. `D01-baseline` with plain chronological says there is “no subsequent
information confirming or denying your current feelings.” The frozen reference
treats the latest assertion as valid. All eight named fruit/tea baselines pass.
Question form and subject matter vary together here; this cannot isolate a
causal effect of binary questions.

**Fictional ownership can be lost under JSON.** `D03-ownership` provides a
copy-editing request containing fictional Rowan's first-person line. Both JSON
conditions answer “I currently prefer pears for breakfast.” Both plain conditions
correctly treat the user's preference as unknown. The two JSON conditions are
identical-input duplicates, so this is one affected source case, not two
independent replications. The other ownership cases pass.

**Different-value and historical tasks are stronger.** All 16 different-value
conditions give the correct final value; five nevertheless repeat a withdrawn
old value in their explanation. All 16 historical questions correctly report the
original statement at the explicitly requested historical scope.

The 38 strict failures consist of 26 wrong or incomplete required answers and
12 additional answers with correct values but forbidden old-value restatements.
Source consistency and visible support pass 70/96, withdrawal compliance 68/96,
and ownership 94/96. All 96 bodies are structurally valid and within 90 words
(maximum 50). These criterion counts overlap and must not be summed as cases.

## Design and review boundaries

The [prospective plan](preflight/PLAN.md) and references were frozen before
generation. Four fresh synthetic families cover urban sketching, amateur
astronomy, breakfast fruit and tea. Each has six cases crossed with two wrappers
and two displayed orders, producing 24 cases and 96 conditions. Every condition
contains the same complete source turns for its case, including role labels,
original turn numbers and character coordinates. The input is at most 449 tokens.
The system instruction and decoding are fixed. No oracle UNKNOWN annotations,
reference answers, query-specific source selection or generated notes are given
to the reader; references remained local and were not mounted for inference.

The review is an unblinded author model review against author-written references,
not independent validation. [The recorded decisions](record_author_review.py)
encode inspected answers, not a keyword classifier. Exact evidence is checked
against the complete sources, actual reader messages and captured text by
[summarize.py](summarize.py). Current-value answers that restate a withdrawn old
positive preference fail withdrawal compliance even if historically supported;
topic-only mentions do not. Historical questions explicitly allow the original
statement. “Forgotten” wording is treated as record status, not proof of physical
erasure. Missing citations are not penalized, and correct answers do not establish
hidden reasoning. These interpretive rules explain the difference between the
value/task column and strict pass column.

Four simple families, repeated controls and related question forms do not support
population-level accuracy estimates or confidence intervals. The experiment does
not reproduce long-history distraction, lossy note selection, the entire previous
withdrawal ledger or retrieval. It establishes neither learned policy quality nor
transfer to the frozen broader suite. No winning prompt was selected after seeing
outputs. The primary candidate and success gate were declared in advance.

## Execution and artifact verification

The frozen Qwen/Qwen3-4B-Instruct-2507 reader at revision
`cdbee75f17c01a7cc42f958dc650907174af0554` ran on one H100 with FP32 math attention,
TF32 off, seed zero, greedy decoding, fresh prefill, a supplied `ANSWER` prefix
and a maximum of 192 output tokens. Torch 2.7.1 and Transformers 4.55.2 were pinned.
The run used four CPUs and 32 GiB RAM, a 1,200-second hard ceiling and zero retries.
Measured execution elapsed time was **437.259 seconds** (7 minutes 17 seconds).

- App: `ap-ZAxAy2NZR5y3qIQZucV0q0`;
  [Modal run](https://modal.com/apps/syntracts/main/ap-ZAxAy2NZR5y3qIQZucV0q0).
- Terminal state: collection complete; subsequent live status is **stopped,
  zero tasks**, preserved in [app-status.json](run/app-status.json).
- Observed billing: **$0.53963343**, including H100 $0.48497271, CPU $0.02322958
  and memory $0.03143114. [Billing evidence](run/billing.json) was observed at
  2026-09-10 20:44:14 UTC; billing may lag terminal execution. Recorded cumulative
  v2 cost becomes $6.77787052 when added to the prior $6.23823709 snapshot.
- All forty actual-prompt cache fixtures pass initial-argmax and
  sixteen-token-or-EOS cached/fresh trajectory equality, ten fixtures per arm.
- All sixteen identical-input control pairs have identical output token IDs.
- [Offline artifact verification](run/artifact-verification.json) validates
  all 96 captures, source/input/runtime hashes, token IDs, EOS, context budgets,
  forward counts and all **928 protected prior files unchanged**.
- [summary.json](summary.json) records every count and declared comparison.
  [result-manifest.json](result-manifest.json) binds the completed report,
  review, summary, scripts, frozen inputs, source snapshots and run artifacts.
  `python plans/260911-reader-diagnostic/verify_results.py` checks that manifest,
  the protected files and a read-only replay of the review summary.

This authorized diagnostic is complete. The prior broader run and its adjudication
are preserved; its 98 missing conditions remain uncaptured. No training, action
labels, additional GPU run or external judge was performed. The reader has not
passed the declared readiness gate.
