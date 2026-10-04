# Source-only repair and bounded base-reader diagnostic

Frozen before the diagnostic launch. This is a small manually judged development
pilot, not full-corpus admission, LoRA training, or the original external test.

The four confirmed failures have new source-bound answers. A fresh deterministic
sample contains 50 unchanged questions from the next ten training personas in
the existing hash order. Authoring used sanitized history and current query;
old answers, private preferences, profiles, and source-label flags were excluded.
Fifty targets were drafted and then reviewed by Codex, with explicit source
coordinates for twelve answers using personal context. This is author review,
not an independent human review. Draft and reviewed versions remain separate.

The user was asked about a full-scale independent judge. No response has been
received at this point. The default for this bounded pass is manual Codex
judgment of base-reader outputs; no external judge account or new judge model
is used. Full-scale admission and independent evaluator configuration remain
pending. Do not infer action targets from the repaired reference strings.

## Ten-question diagnostic

Use sample indices `3,6,10,17,23,26,31,35,40,49`: one question per persona,
seven with supported personal context and three general/withdrawal cases.
This is deliberately enriched for debugging, not a representative evaluation.
None is an internal or external held-out test question.

- One query-blind BF16 summary per complete sanitized history, at most 768
  output tokens; preserve generated notes even when incomplete or mistaken.
  Single-pass summary of the supplied history is a diagnostic amendment to
  the original session-by-session summarizer and is not a streaming result.
- Keep the latest 512 raw tokens, 384-token original-turn chunks with 64-token
  overlap, and at most 1,024 retrieved tokens per round. BM25 is provisional
  for this diagnostic; the planned BM25-versus-hybrid comparison is pending.
- Use the pinned base Qwen3-4B, all weights frozen. Reader arithmetic is FP32
  math SDPA, TF32 off. Produce forced-answer counterfactuals with zero, one,
  and two retrieval rounds: 30 captures total. No learned/adaptive routing.
- Forced retrieval is supplied before the answer prefill. Do not add artificial
  decision passes to the forced-RAG cost. Decode uses the existing cache helper.
  These captures do not themselves recertify exact tool-append equivalence.
- Greedy generation, at most 192 output tokens. Incomplete EOS/protocol outputs
  remain failures; no repair or gold-informed answer fallback.
- One H100, 15-minute function timeout, internal stop at 850 seconds before
  the next decode step. No automatic paid retry. Partial artifacts are retained.

The model receives only a bundle of ten sanitized histories and ten queries.
Repaired references and rubrics stay local and are not mounted into its image.
Bind source code, configuration, and reader-input hashes before execution.

## Manual output assessment

Freeze the reference version before capture. Afterward, review complete answer
text with its actual visible notes/tool evidence and the private repaired rubric.
Record task completion, unsupported personal claims, misuse of withdrawn details,
and malformed/truncated output separately. A recommendation need not match the
reference wording. General advice is valid when it satisfies the current request
without pretending to remember a personal fact. A withdrawn preference does not
establish its opposite, and a current explicit request can revisit that topic.

Use paired outcomes to see whether retrieval repairs an answer. Report observed
costs and failures, not statistical advancement or a trained-policy result.
Do not select a checkpoint or score LongMemEval from these development captures.
