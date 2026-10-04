# Withdrawal regression: neutral records help, but four cases still fail

The paired probe passes **8/21 with raw withdrawals and 17/21 with neutral
UNKNOWN records**. Nine cases improve, eight pass in both arms, and four fail
in both. No previously passing case becomes a failure. The prospective clean
regression requirement was 21/21 in the neutral arm, so **the gate fails and
training remains paused**. This is a selected development result, reviewed by
the reference author; independent review remains pending.

## Controlled comparison

The [prelaunch plan](../20260910-v2-withdrawal-regression-plan/PLAN.md) and
[data freeze](../20260910-v2-withdrawal-regression-data/freeze.json) fix 21
questions, 42 captures and their order before inference. Thirteen questions
and references come unchanged from the preceding development set; eight new
synthetic histories test chronology, topic scope, ownership and attribution.

Both arms use the same revised answer-only prompt, runner-supplied archive
message, supplied `ANSWER` prefix, FP32 math-SDPA base model with TF32 disabled,
768-token notes, 512-token recent window and 192-token output cap. Twenty
questions receive one retrieval capped at 1,024 tokens; the missing-price
format control receives none. Each answer starts with a fresh cache. Arm order
alternates by frozen question index. BM25 ranking and source chunk IDs are
identical within each pair.

The sole paired intervention replaces 16 manually annotated user withdrawal
turns with source-bound topic labels and `UNKNOWN`, after evidence selection.
Ten annotations cover the selected real-history questions and six cover
synthetic histories. They are fixed per history, independent of the current
query. All 79 selected quotations and the other 137 withdrawal ledger entries
remain unchanged. Assistant acknowledgments may still repeat old values. This
is a representation experiment, not a general parser, raw-data deletion or
learned forgetting. Private references are excluded from the reader image.

## Results under every frozen criterion

A passing answer must complete the task, respect source and withdrawal
constraints, have support in the actual visible state, contain a valid body
and fit 90 whitespace-delimited words. For an unknown preference, saying
`UNKNOWN` is acceptable; repeating the old value or asserting its opposite
fails. A later explicit user statement may establish a value again.

| Case group | Raw | Neutral |
|---|---:|---:|
| Existing withdrawal questions | 0/10 | 7/10 |
| Retained rehearsal fact | 1/1 | 1/1 |
| Previously incorrect passage attribution | 1/1 | 1/1 |
| Missing-price format control | 1/1 | 1/1 |
| Eight synthetic controls | 5/8 | 7/8 |
| **Total** | **8/21** | **17/21** |

The seven recovered real-history cases concern pens, fabrics, snowboarding,
Nordic vacations, AR games, drinks and aquarium visits. The other two paired
improvements are the synthetic same-value restatement and assistant-repetition
cases. The neutral arm correctly uses a later user restatement of the same
paper-book preference and does not repeat the withdrawn spiciness preference.
Both arms preserve the later different drink preference, later meeting update,
unrelated pen preference, named fictional character and specified passage.

All **42/42 bodies** end at EOS, contain no reserved action marker and fit the
word limit; the maximum is 59 words. The corrected validator now rejects
standalone `ANSWER` or `RETRIEVE` anywhere in the body. This collection supplies
the action prefix and archive lookup; it does not measure generated action
compliance or learned retrieval decisions.

## Remaining neutral-arm failures

| Question | Observed failure |
|---|---|
| `memory-dev-v1-642-4` | Says learning blockchain/cryptocurrency would **not** suit the user even while citing UNKNOWN interest. |
| `memory-dev-v1-651-4` | Says jigsaw puzzles are **not** a usual pastime, and repeats an assistant acknowledgment of the withdrawn liking. |
| `memory-dev-v1-990-4` | Says “I prefer paper books” despite the T150 UNKNOWN record; retrieved assistant text still mentions paper books. |
| `withdrawal-regression-v1-s06` | Answers “Tea” to a personal-preference question when the only source is a fictional first-person monologue. Both arms have identical inputs for this case. |

The first two still turn unknown into a negative. The third asserts a withdrawn
value. The fourth violates ownership even in a short, fully visible example.
The captured text establishes these failures; it does not establish which
individual context fragment causally produced them.

Raw additionally repeats withdrawn pen, fabric and spicy-food details; infers
other negative/opposite preferences; and ignores a visible later paper-book
restatement. Every failure and passing decision is recorded in the
[42 source-bound judgments](judgments.json), with separate semantic criteria
and exact capture/reference hashes. The [paired summary](judgment-summary.json)
retains all case types and transitions.

## Verification, cost and decision

The one bounded H100 run completed in **284.916 seconds**, with zero retries
and no training. Its 40 actual-reader cache fixtures matched fresh recomputation
exactly through all checked appends and up to 16 greedy continuation tokens.
All 18 note histories, 79 quotations and 153 withdrawal ledger entries passed
source validation. The [artifact audit](source-capture-verification.json)
verified 23 launch source snapshots, 48 frozen file bindings, five remote
artifact hashes and all 42 actual prompts, retrievals, token counts and decoded
bodies against their frozen CPU replay. The 31 targeted CPU tests passed.
The earlier dataset verifier also passed with its 236 prior artifacts unchanged.

App `ap-96zoNp4skgTFahFp89bE4P` is stopped with zero tasks.
[Measured billing](billing.json), observed at 08:19:19 UTC on 2026-09-10, is
**$0.35649983**: H100 $0.32038914, CPU $0.01534623 and memory $0.02076446.
Recorded cumulative ContextPolicy v2 cost is **$3.38624093**.

The earlier wrong-passage and missing-price failures now pass in both arms.
That comparison also changes the shared prompt and transcript, so it cannot
be attributed specifically to neutral withdrawal records. Only the paired
8-to-17 comparison isolates this manually annotated representation change.
The selected seen histories, synthetic controls and same-author review do not
establish generalization or full-corpus admission.

Stop after this report, as planned. Preserve these failures before a separate
revision. A next intervention should address current-value validity and
ownership while retaining later-statement positive controls; it should be
frozen before another bounded comparison. Broader data and independent review
remain necessary before any training or learned-policy claim.
