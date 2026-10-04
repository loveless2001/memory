# Qwen3-8B reader comparison — completed 2026-09-11

**The larger reader improves modestly but still fails both acceptance gates.**
With the original prompt, strict passes increase from **17/24 to 20/24** on
development cases and **36/48 to 39/48** on the reused fresh cases. The procedural
rewrite remains worse than the original prompt on 8B. All 144 answers were
collected and reviewed; no training or further model run followed.

The requested “qwen7B same class” was implemented with **Qwen/Qwen3-8B**, the
nearest dense Qwen3 size, with thinking disabled. The
[official Qwen3 repository](https://github.com/QwenLM/Qwen3) lists 8B rather than
7B; its 2507 refresh does not provide an 8B counterpart to the previous
Qwen3-4B-Instruct-2507. This choice was disclosed before inference. Parameter
count, checkpoint release/post-training and native chat template differ, so this
comparison cannot isolate model size as the cause of any change. See the
[8B model card](https://huggingface.co/Qwen/Qwen3-8B) and
[frozen plan](preflight/PLAN.md).

## Matched results

| Prompt | Split | 4B strict pass | 8B strict pass | 4B required answer correct | 8B required answer correct |
| --- | --- | ---: | ---: | ---: | ---: |
| Original, primary | Development | 17/24 | **20/24** | 19/24 | 21/24 |
| Original, primary | Reused fresh | 36/48 | **39/48** | 41/48 | 42/48 |
| Rewrite, secondary | Development | 14/24 | 15/24 | 18/24 | 17/24 |
| Rewrite, secondary | Reused fresh | 26/48 | 28/48 | 36/48 | 38/48 |

Strict pass requires all seven frozen criteria: required answer/task correctness,
source consistency, whole-answer visible support, withdrawal compliance,
ownership, valid body and at most 90 words. Required-answer correctness separates
the requested value from errors in the explanation. Both prompts fail the
predeclared **24/24 development AND 48/48 fresh** gate. The original prompt was
selected as the primary model comparison before any 8B answers were generated.

Under the original prompt, changing from 4B to 8B fixes four development strict
failures and introduces one; on fresh cases it fixes six and introduces three.
Required-answer corrections/regressions are 3/1 and 4/3 respectively. Thus the
net gain includes regressions and is smaller when considering only the required
answer. Under the rewrite, strict corrections/regressions are 1/0 and 4/2;
required-answer corrections/regressions are 0/1 and 2/0.

On 8B itself, the rewrite fixes three development strict failures but introduces
eight, and fixes one fresh failure but introduces twelve. Required-answer
correctness also falls, from 21 to 17 and from 42 to 38. The adverse prompt result
therefore persists beyond explanation-only penalties.

| Case type | 8B original development | 8B rewrite development | 8B original fresh | 8B rewrite fresh |
| --- | ---: | ---: | ---: | ---: |
| Positive baseline | 1/4 | 4/4 | 8/8 | 8/8 |
| Withdrawal to unknown | 3/4 | 0/4 | 2/8 | 0/8 |
| Later different value | 4/4 | 3/4 | 8/8 | 2/8 |
| Later same value | 4/4 | 4/4 | 8/8 | 8/8 |
| Historical original statement | 4/4 | 4/4 | 8/8 | 8/8 |
| Fictional-speaker ownership | 4/4 | 0/4 | 5/8 | 2/8 |

Fresh strict scores by question form are 20/24 binary and 19/24 open for the
original prompt, versus 13/24 and 15/24 for the rewrite. Full comparisons,
criterion counts and topic/form cells are in [summary.json](summary.json).

## What changed and what remains

The original prompt now passes three development withdrawal cases. For example,
`D03-withdrawal` answers that the breakfast-fruit preference is unknown, without
repeating the withdrawn assignment. Fresh mango and lemonade open withdrawal
answers likewise become clean unknown responses. Same-value reinstatement also
improves: the original prompt now correctly accepts the later origami and mango
assertions, making all eight fresh reinstatement answers pass.

Unknown still often becomes a definite negative. Original-prompt binary
withdrawal answers for origami, mango and lemonade say No. The mango answer even
continues by saying the preference is unknown; that explanation does not make
the initial negative correct. The rewrite gives unsupported negatives on all
four fresh binary withdrawal questions. Its ownership answers often identify
Vale correctly but still say No or assert that the user has no preference.
These are failures of unknown-versus-negative handling; correct attribution in
those explanations is retained as a separate passing criterion.

Ownership also regresses in a different way. Under the original prompt, the
origami, mango and lemonade open ownership answers now supply the fictional
character's preference as the user's current preference. All three were strict
passes on 4B. For example, `F03-ownership-open` answers “The current preferred
snack fruit is mango” even though the only source is a fictional line attributed
to Vale. A larger reader did not consistently preserve owner scope.

Unsupported staleness remains on development activity cases and newly affects
the original-prompt rooibos baseline: the model asks for recent information even
though the latest direct preference has not been withdrawn or changed. The
rewrite fixes these three baselines but creates more errors elsewhere.

Extra explanations continue to restate withdrawn preferences. Across both arms,
118/144 required answers are correct and 102/144 strictly pass. The 42 strict
failures consist of 26 wrong/incomplete required answers, fifteen additional
old-value restatements, and one unsupported generalization: `D04-withdrawal`
under the rewrite correctly leaves the tea type unknown but asserts a current
preference for tea after the sole preference record was withdrawn.

These results support a modest reader/checkpoint effect on this suite. They do
not establish that the previous failures were simply due to using 4B, that
capacity is irrelevant, or that targeted training cannot help. State tracking
remains a possible research direction, without implementation or validation here.

## Protocol, review and execution

All 72 cases, references, both prompts, source/user messages, condition order and
forty cache-fixture indices match the completed 4B experiment. Verification
confirms identical actual message text for all 144 matched conditions. Both
models see complete short sources; references and derived state labels remain
local. This is a reader comparison without learned retrieval or compaction.

The 8B revision is `b968826d9c46dd6066d109eabc6255188de91218`, with 8,190,735,360
parameters and zero trainable parameters. Torch 2.7.1, Transformers 4.55.2, FP32
math attention, TF32 off, seed zero, greedy decoding, fresh prefill, ANSWER prefix,
192 output tokens, 90 words and an 8,192-token context cap match the protocol.
The native template uses `enable_thinking=False`; its empty closed thinking
block adds four input tokens, raising the maximum from 531 to 535. No generated
answer contains a thinking marker. Greedy decoding is retained for comparability
despite the model card's sampling recommendation; this is not a search for the
model's best achievable score.

Codex performed unblinded author review of every saved answer against the frozen
references, full source histories and actual reader messages. Exact quotes and
individual reasons are in [review.json](review.json);
[record_author_review.py](record_author_review.py) records explicit inspected
decisions. This is not independent validation. Unknown is distinct from No;
historical questions may quote original values; a current-state denial is allowed
when a different value is established. Restating an old positive assignment in
an explanation fails withdrawal compliance. Missing citations are allowed;
incorrect asserted source labels are not. No hidden reasoning is inferred.

The four fresh synthetic families were already used in the 4B experiment and
share templates with development cases. “Fresh” retains that earlier split name,
not a new holdout for 8B. Binary/open variants and shared histories are related;
no population confidence intervals or independent sample-size claims are made.
Results do not establish transfer to the broader long-history suite, whose 98
uncaptured conditions remain uncaptured.

Weights were staged on a CPU worker and all five shards (approximately 16.4 GB)
verified against upstream sizes and SHA-256 hashes before GPU use. An initial
CPU startup failed because a local metadata path was read during remote module
import. The failure and original source are preserved; the corrected CPU-only
acquisition completed in 50.031 seconds. Existing model caches were preserved.

| App | Purpose | Observed cost |
| --- | --- | ---: |
| `ap-M8XkUoXTzLT4ceWmCOhh4l` | Failed CPU startup | $0.00001152 |
| `ap-5XKMwz5cuglatWwtBQ5y4R` | Verified CPU acquisition | $0.00355970 |
| `ap-5vjhoy7uundd9vUtp7XihE` | Complete H100 inference | $0.33940695 |
| Total | | **$0.34297817** |

The single H100 run completed all 144 conditions in **270.863 seconds** (4m31s),
with zero retries. All **40/40 cache fixtures** pass initial-argmax and
sixteen-token-or-EOS trajectory equality. Artifact verification checks captured
tokens, formats, EOS, budgets and forward counts; all 144 answers fit 90 words
(maximum 58). All **1,074 protected prior files remain unchanged**. See
[artifact verification](run/artifact-verification.json),
[billing](billing.json) observed at 05:10:19 UTC, and [terminal app states](app-status.json).
All three apps are stopped with zero tasks. Billing may lag execution.

The [result manifest](result-manifest.json) binds the saved comparison. Run
`python plans/260911-reader-qwen3-8b/verify_results.py` for a read-only verification
of final hashes, protected files, review/summary consistency and stopped apps.
No training labels or training admission were produced.
