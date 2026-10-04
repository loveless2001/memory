# Prospective repair revision 2 diagnostic

Frozen before the new paid run, after observing revision 1. This is development
engineering, not an independent accuracy evaluation or full-corpus admission.
User continuation authorizes implementing the reported repairs and one bounded
revised diagnostic. Ceiling: one H100 function, 900 seconds, internal stop at
850 seconds, zero retries. No training or external data access.

Use exactly the prior ten reader questions and sanitized histories and the same
50 source-bound reference version. Preserve all prior artifacts and strict 0/30
format verdict. New sources and this plan are frozen separately.

## Changes

- Replace single-pass abstractive summaries with query-blind, chronological
  selection of exact user quotations. Split user text into approximately 96-token
  pieces with original character coordinates and source hashes. Assistant text
  cannot become a selected quote. These windows are artificial token batches,
  not real session boundaries. This is an explicit extractive-note amendment;
  it does not claim equivalent quality to the originally proposed summaries.
- Retain every dataset-style `Please forget ...` user instruction verbatim in a
  separate ledger within the shared 768-token note cap. Selection sees only
  previous retained quotes and the current batch. The ledger advances with the
  batch. Never infer an opposite preference, omit a withdrawal to fit the cap,
  accept invented IDs, truncate note output, or turn a quote into a personal-fact
  assertion. This narrow detector does not handle arbitrary natural-language
  deletion/correction requests; the reader and semantic review still must.
- The pinned 4B selects IDs in BF16, at most 192 output tokens per update. Reject
  malformed, empty, duplicate, unavailable, truncated or over-budget selections.
  Stop on the first failure and save it; do not retry, clip, or substitute notes.
  Local tokenization found 63 updates, with 269–581 tokens for selected quotes
  after final withdrawal overhead. Audit quality separately after collection.
- Wrap retrieval as archival data and repeat the unchanged current question at
  the end of each tool message. Keep ranking, query, evidence caps, recent cap,
  and counterfactual round counts unchanged. JSON quoting is contextual guidance,
  not a security guarantee. It cannot prove the reader ignores old instructions.
- Supply the exact `ANSWER\n` prefix only for forced-answer body collection.
  Record generated-action validity as null, not success. EOS, nonempty body,
  no repeated action marker, task completion, source consistency and support in
  the actual visible state are required before producing a demonstration.
  Source/content judgments must bind the entire capture and reference version.
  Free-running policy evaluation retains the original strict parser.

## Gates and interpretation

First run all 40 existing synthetic cache fixtures under the new transcript on
the actual frozen 4B, FP32 math SDPA, TF32 off. Compare fresh and append-only
argmax at each of two retrieval appends and at the supplied answer prefix, then
compare 16 greedy continuation tokens or earlier EOS. Require 40/40; retain all
mismatches and stop if any fail. This is a base-reader check, not certification
of a future trained adapter. CPU token-prefix tests alone are not sufficient.

Only then perform note updates and capture ten questions at zero/one/two
retrievals. The unchanged 768/512/1024/192-token budgets apply. Forced-answer
arms do a single prefill, not an artificial retrieval-decision pass. All notes,
selection events, actual reader messages, generated tokens, timings and hashes
are retained. Compare content with the previous 9/6/5 counts only descriptively:
notes, prompt and forced prefix all changed, so no cause is isolated.

Manual review uses the prior source/content definitions without requiring
personalization for general requests. For this prospective collection mode,
body validity replaces free-generated marker validity when deriving development
counterfactual labels; those are labels for proposed actions, not observed
successful generated actions. References stay unchanged. Reviewer independence,
full-corpus admission, genuine memory-dependent distribution, future-adapter
cache certification and external uncertainty/judge issues remain unresolved.

Stop before training. Record actual app billing and report any failed gate.
