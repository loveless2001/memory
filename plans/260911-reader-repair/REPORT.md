# Paired reader repair — completed 2026-09-11

**Reject this prompt rewrite.** All 144 planned answers were collected and
reviewed. Strict passes fall from **17/24 to 14/24** on the existing development
cases and from **36/48 to 26/48** on fresh cases. Both predeclared repair gates
fail. Training remains paused, and no further prompt variant or broader run was
launched. These are unblinded author judgments, not independent validation.

## Paired results

Both arms use the same complete chronological JSON archive, question, frozen
reader and decoding. Only the system instruction changes. The candidate is a
single procedural rewrite covering scope, owner, chronological state, withdrawal,
reinstatement and final-answer constraints; it has no demonstrations or oracle
state annotations. The original instruction already contained most of these
rules. This experiment evaluates the bundled rewrite, not individual rules.

| Split | Original: required value/task correct | Rewrite: required value/task correct | Original: strict pass | Rewrite: strict pass | Rewrite gate |
| --- | ---: | ---: | ---: | ---: | --- |
| Existing development | 19/24 | 18/24 | 17/24 | 14/24 | FAIL: requires 24/24 |
| Fresh cases | 41/48 | 36/48 | 36/48 | 26/48 | FAIL: requires 48/48 |

The rewrite fixes two strict development failures but introduces five; on fresh
cases it fixes three and introduces thirteen. Considering required value/task
correctness alone, the corresponding corrections/regressions are 2/3 and 2/7.
The conclusion therefore does not depend only on the explanation restrictions.

Strict pass requires all seven criteria: task completeness, source consistency,
whole-answer visible support, withdrawal compliance, ownership, a valid answer
body and at most 90 words. [summary.json](summary.json) contains every comparison;
[review.json](review.json) records all judgments, reasons and exact evidence.

| Case type | Existing original | Existing rewrite | Fresh original | Fresh rewrite |
| --- | ---: | ---: | ---: | ---: |
| Positive baseline | 2/4 | 4/4 | 8/8 | 8/8 |
| Withdrawal to unknown | 0/4 | 0/4 | 0/8 | 0/8 |
| Later different value | 4/4 | 2/4 | 8/8 | 2/8 |
| Later same value | 4/4 | 4/4 | 6/8 | 8/8 |
| Historical original statement | 4/4 | 4/4 | 7/8 | 8/8 |
| Fictional-speaker ownership | 3/4 | 0/4 | 7/8 | 0/8 |

## Findings and concrete evidence

**The rewrite repairs unsupported staleness.** In `D01-baseline` and
`D02-baseline`, the original prompt asks for renewed confirmation despite an
unwithdrawn direct user assertion. The rewrite correctly retains that assertion.
All fresh baseline cases pass both prompts.

**Ownership gets substantially worse.** Across the twelve ownership questions,
the original prompt passes 10/12 and the rewrite passes 0/12. Several rewritten
answers correctly name the fictional speaker in their explanation, yet still
give that speaker's preference as the answer about the user. For example,
`F03-ownership-binary` answers “Yes, mango is your current preferred snack fruit”
and then acknowledges that the line was spoken by fictional Vale. Correctly
labeling the source does not support that affirmative user-biography claim.
Open-question answers also substitute the fictional preference for the required
unknown user preference. These are twelve related variants, not twelve independent
families.

**Withdrawal still becomes a definite negative in binary questions.** Fresh
cases cross binary and open questions on exactly the same four source histories.
In both arms, all four binary withdrawal questions receive unsupported No answers,
while all four open questions correctly say the value is unknown. This pattern
occurs for activities and food/drink topics. It supports a question-form effect
within these examples, without establishing a general effect size. Every open
withdrawal answer nevertheless repeats the removed old preference in its
explanation, so strict withdrawal passes remain zero in both arms.

**Reinstatement improves, but chronology alone was insufficient.** The original
prompt incorrectly rejects later same-value assertions in the fresh origami and
mango binary cases, even though the source is chronological. Both rewritten
answers correctly use T4 after the T2 withdrawal. Other same-value cases pass
both prompts. The earlier presentation diagnostic's ordering result therefore
does not establish universal reinstatement reliability.

**Additional explanations create output violations.** Every different-value
answer gives the correct required value or binary response. However, the rewrite
restates the withdrawn old assignment in two development and six fresh answers.
For example, `F03-different-open` correctly answers kiwi, then explains the update
by repeating the withdrawn mango preference. The original prompt passes all
twelve different-value cases under the strict criteria.

One fresh original historical answer (`F04-historical-binary`, capture 129)
correctly recalls lemonade but places acknowledgment of the withdrawal at T2.
T2 is the user request; the assistant acknowledgment is T3. This explicit
explanatory attribution accounts for its strict failure despite a correct
requested answer. The rewritten historical answers pass.

Across both arms and splits, 114/144 required answers are correct and 93/144
strictly pass. The 51 strict failures comprise 30 wrong/incomplete required
answers, twenty additional withdrawn-value restatements and one additional
incorrect acknowledgment-turn attribution. These selected aggregate counts are
descriptive; the two split-specific gates above are the primary decision.

## Fresh source/question crossing and review boundaries

The unchanged 24 development cases come from the prior diagnostic. Fresh sources
cover bouldering/kayaking, origami/chess, mango/kiwi and lemonade/iced coffee. Each
family has six case types, each asked in binary and open form: 48 questions.
This crosses topic and question form, which the previous diagnostic did not.
Both prompts receive all source turns, original speaker/turn/character labels
and the same question; only their system messages differ. Maximum input length
is 531 tokens. References remain local and were not mounted for inference.

| Fresh question form | Original strict pass | Rewrite strict pass |
| --- | ---: | ---: |
| Binary | 16/24 | 14/24 |
| Open | 20/24 | 12/24 |

The [plan](preflight/PLAN.md), [author reference review](preflight/REFERENCE-REVIEW.md),
cases, prompts and gates were frozen before generation. Four synthetic families
and repeated source/question variants do not support population confidence
intervals, independent sample-size claims or transfer to long-history retrieval.
The candidate was written from the prior observed failures, and the fresh cases
share templates with development cases. This is a bounded development experiment.

Codex inspected all 144 answers against their complete sources and actual reader
messages. [record_author_review.py](record_author_review.py) encodes explicit
inspected decisions, not a keyword classifier. Correct required values are
separated from forbidden explanations. A direct current-state binary denial is
allowed when a different value is established; stating the old positive
assignment while explaining withdrawal is not. Captures 52 and 100 pass this
distinction, while capture 77 restates the old assignment through its explicit
pronoun antecedent. Historical questions may quote original withdrawn values.
Missing citations are not penalized; incorrect asserted turn labels are.
No hidden reasoning or physical erasure is inferred from answer wording.

## Execution amendment and verification

The original one-H100 run passed forty cache fixtures but reached its internal
time ceiling after **35/144 captures**, at **1,152.107 seconds**. Generation itself
was fast in the inspected captures; per-step artifact checkpointing dominated
wall time. Its failed status, error, outputs and billing remain preserved in
[run](run/). The original twenty-minute execution plan was insufficient.

An explicit [execution amendment](continuation-preflight/AMENDMENT.md) permitted
one sequential continuation to finish only the missing 109 conditions, with
remote commits batched every twenty checkpoint requests. The amendment was made
after throughput and a few early answers were inspected, so execution scheduling
was not wholly prospective. It did not change either prompt, any source/question,
reference, semantic criterion, gate or decoding setting. The missing suffix was
frozen after terminal retrieval; no saved answer was regenerated for collection.
The runtime AST differs only by skipping that saved prefix. Forty actual-prompt
cache fixtures were repeated in the new process before collecting the suffix.

The continuation completed **109/109 captures in 216.341 seconds** (3m36s).
It made seven batched commits before its final commit; those seven consumed
12.945 seconds. Each run retained a twenty-minute hard cap, with zero automatic
retries. Total recorded execution time was **1,368.449 seconds** (22m48s), excluding
some launch/final-commit overhead. This completes the original 144-condition
semantic comparison with a disclosed two-run execution deviation.

| Run | App | Captures | Recorded execution | Observed cost |
| --- | --- | ---: | ---: | ---: |
| Initial, time-capped | `ap-0cv9BR8318FTbJGRofD4uc` | 35 | 1,152.107 s | $1.25263187 |
| Continuation, complete | `ap-MoX2gb3EZeLphuck7Mnq0n` | 109 | 216.341 s | $0.25882956 |
| Total | Two sequential apps | 144 | 1,368.449 s | **$1.51146143** |

Billing was observed at 04:38:50 and 04:44:50 UTC on 2026-09-11; reported charges
may lag terminal execution. See [initial billing](run/billing.json) and
[continuation billing](continuation-run/billing.json). Both apps are confirmed
stopped with zero tasks. The reader remains Qwen/Qwen3-4B-Instruct-2507 at revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, with Torch 2.7.1, Transformers 4.55.2,
FP32 math attention, TF32 off, seed zero, greedy decoding, fresh prefill, supplied
ANSWER prefix and 192-token generation cap. Each app used one H100, four CPUs and
32 GiB RAM. No parameter was trained.

[Artifact verification](combined/artifact-verification.json) passes for the
complete prefix/suffix union: **80/80 cache fixtures**, all 144 token/format/EOS/
budget/forward-count replays, and all 144 answers within 90 words (maximum 63).
All **24 previous baseline inputs and output token sequences match exactly**.
All 978 initially protected files and all 1,020 continuation-protected files
remain unchanged. Source snapshots, input hashes and separate run manifests bind
the [combined captures](combined/captures.json) to both original artifacts.

`python plans/260911-reader-repair/verify_results.py` checks the final
[result manifest](result-manifest.json), protected files and a read-only replay of
the evidence-backed review summary. The prior diagnostic and broader suite are
preserved, including the broader run's 98 uncaptured conditions.

The stopping rule is reached: this rewrite fails both gates and should not replace
the development baseline. The next research question is whether explicit,
source-backed ownership and state tracking can enforce the distinctions that
this reader still violates. That architecture has not been implemented or
validated here. No training labels or training admission were produced.
