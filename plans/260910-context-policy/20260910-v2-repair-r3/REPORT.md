# Repair revision 3: budget passed, source-ID selection failed

Revision 3 passed **40/40 real frozen-4B cache fixtures** and the first three
note updates. Their rendered notes used **741, 759 and 738 tokens**, all within
the unchanged 768-token cap. The fourth update returned an unavailable source ID
and the run stopped under the frozen rule. No complete history notes, answer
captures, routing labels, training, or external evaluation were produced.

## What changed and what happened

The [prelaunch plan](../20260910-v2-repair-r3-plan/PLAN.md) replaced model-estimated
note budgets with deterministic whole-quote admission. The model ranked up to
eight candidate IDs; code validated the complete list, then admitted whole
quotations in rank order while keeping every seen withdrawal verbatim. The
same ten development histories/questions, reference version, reader transcript,
FP32 runtime and token budgets were retained. All 18 source files and the input
and reference hashes were frozen before launch.

The model completed four selections at EOS, requesting eight IDs each time.
The first three passed validation and budget enforcement. The fourth included
`T158:0-124`, which was not in the candidate list. The actual candidates included
`T158:0-457`, `T158:457-567`, and `T160:0-124`. The generated address appears to
combine the turn number of one candidate with another's character endpoint;
this is an inference from the strings, not a measured internal mechanism. No
ID was duplicated. See [exact failure analysis](id-failure-analysis.json) and
[all selection events](artifacts/note-events.json).

The budget mechanism therefore worked on the three observed accepted updates;
it did not make free-form address generation reliable. The invalid ID was not
silently dropped. There are no answer-quality or retrieval-drift results from
this run, and no claim that these partial notes preserve the needed context.
Revision 1's 0/30 strict score and exploratory 9/6/5 counts remain unchanged.

## Completed local follow-up

Added a finite-choice source-ID grammar in
`experiments/context_policy/source_choice.py`, integrated as explicit
`--repair-revision 4`. The tokenizer callback permits only token paths for
currently supplied source IDs, each at most once. EOS is permitted after a
complete choice and required at the eight-choice limit. It cannot complete the
unavailable address observed above. The model emits newline-separated choices;
code serializes their validated IDs for the existing exact budget renderer.
The raw generated text/tokens and the fact that syntax was enforced are logged.

This controls note-selection syntax; it is not evidence of learned action-format
compliance, semantic retention, or answer quality. The ordinary reader action
parser remains unchanged. Quotes still undergo source validation and budget
admission, and withdrawals remain inside the shared note cap. Empty/truncated
output, invalid source bindings, or inability to fit any quotation still stop
collection. Revision 3's original failure is preserved.

Local tests cover the observed mixed-address error, duplicate prevention,
truncation, EOS boundaries, and actual Transformers `generate` integration with
a tiny random CPU Qwen model. All **42 local tests passed**. Across the ten source
histories, the grammar's conservative maximum for eight choices plus EOS fits
within the existing 192-token cap; see [token feasibility](choice-feasibility.json).
Revision 4 has not been GPU-tested. A new prospective freeze and bounded run are
required before claiming the selector works on the real 4B or starting any
semantic/answer-quality review.

## Run and cost

- Run: `20260910-v2-repair-r3`.
- App: `ap-54O722166kHGIzRqhS1A0e`, completed.
- Function: `fc-01M24TVXTVTF6QH82D2ZM0NEXB`.
- Function elapsed: **141.076 seconds**; four note-generation calls totaled **8.296 seconds**.
- Reported app charge: **$0.18801698**, summed across the two hourly billing rows.
- Cumulative ContextPolicy v2 app charges observed: **$1.76734196**.
- No judge charge, automatic paid retry, corpus training or external scoring.

[Launch](launch.json), [billing](billing.json), [cache verdict](artifacts/transcript-verdict.json),
[source audit](source-audit.json), and [verification](verification.json) preserve
the evidence. All 40 cache comparisons, 18 source snapshots and four hashed
remote artifacts were verified. The cache check covers tested base-reader
appends and 16 greedy continuation tokens or earlier EOS; future trained
adapters still require their own certification.

The next step is the bounded revision-4 selector probe, followed by source and
content review if collection completes. Full-corpus admission, an independently
reviewed memory-dependent question distribution, and external inference/judge
configuration remain unresolved. Training stays paused.
