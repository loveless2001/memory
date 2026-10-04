# Repair revision 2: cache passed, note selection exceeded budget

The revised archive/question transcript passed **40/40 real frozen-4B cache
fixtures**. Note selection then failed on the second update of the first
persona: 14 valid source IDs rendered to **1,359 tokens**, exceeding the unchanged
768-token cap. The run stopped as registered. No complete notes, answer-body
captures, routing labels, corpus training, or external evaluation were produced.

## Implemented and exercised

The reader envelope marks retrieved dialogue as archival data and repeats the
unchanged current question at the end of each tool message. The new forced-body
collector supplies `ANSWER\n` and records generated-action protocol validity as
null. Source/content review remains mandatory before constructing demonstrations;
free-running policy evaluation retains the original strict parser.

The notes implementation processes chronological user-quote batches, retains
original character coordinates and source hashes, and carries dataset-style
`Please forget ...` requests verbatim. It rejects invented IDs, changed quotations,
missing withdrawals, malformed/truncated selections and excess rendered tokens.
This extractive representation is an explicit development amendment, not proof
of equivalent quality to the original summary design. User quotations can still
be drafts, questions or third-party material, so provenance does not prove
personal ownership. The narrow withdrawal detector is not a general deletion
classifier.

The paid run used the same ten histories/questions and the same repaired
reference version as revision 1. References were not mounted. The
[prospective plan](../20260910-v2-repair-revision/PLAN.md) and input/source hashes
were frozen before launch. The plan required a 40-case cache gate before note
selection and a stop on the first selection failure, with no retry or clipping.

## Observed results

- All 40 fixtures matched fresh versus append-only next-token choices across
  retrieval appends and the supplied answer prefix, plus 16 greedy continuation
  tokens or earlier EOS. FP32 math SDPA, TF32 off, base model frozen. This does
  not certify a future trained adapter or all possible transcript lengths.
- Persona `150`, update 1: 5 selected quotations, 636 rendered tokens, accepted.
- Persona `150`, update 2: 14 source IDs, 1,359 rendered tokens, rejected. The
  generated array was complete at EOS (160 output tokens). It was neither an
  invented-ID failure nor output truncation.
- Total function elapsed: **161.813 seconds**. Note generation took 1.173 and
  3.011 seconds for the two attempted updates. These observations do not establish
  the cost of the full 63-update workload because it was stopped early.
- No answer-quality or question-drift result is available from this revision.
  Revision 1's 0/30 strict score and exploratory 9/6/5 counts remain unchanged.

## Local follow-up: deterministic quote admission

After the failed run, added `experiments/context_policy/note_budget.py`. The next
selector prompt asks for ranked source IDs; code admits whole quotations in rank
order using exact rendered token counts. It keeps the complete withdrawal ledger,
validates the entire ranking before dropping anything for budget, logs every
omission, and rejects a ledger that leaves no room for a quotation. It never
clips source text or treats invalid IDs as ignorable budget excess.

A CPU replay of the captured second selection, treating its existing order as
proposed rank, admitted 6 of the 14 quotes at **743 tokens**, preserving all
8 withdrawals seen at that update. See [replay](local-budget-replay.json).
This only demonstrates mechanical feasibility. The old prompt did not ask for
ranked priorities, and no memory-quality improvement is claimed. Revision 2's
recorded gate remains failed. The new helper is wired to the explicit `--repair-revision 3` path in the
current runner; revision 2 retains strict rejection. Revision 3 has not been
run on GPU and requires a new prospective source/plan freeze before testing.

## Evidence and cost

- App: `ap-YKTEIVc7oQckjYgmEyFjDm`, completed.
- Function: `fc-01M24T14N3P9SP0NGFPGBSWAWQ`.
- App charge observed: **$0.19534147** (H100 $0.17555488, CPU $0.00840886, memory $0.01137773).
- Cumulative ContextPolicy v2 app charges observed: **$1.57932498**.
- No judge charges and no automatic paid retry.

[Launch](launch.json), [billing](billing.json), [cache verdict](artifacts/transcript-verdict.json),
[note events](artifacts/note-events.json), and [verification](verification.json)
provide the exact evidence. All 17 launch source snapshots and all remote
artifact hashes were verified. Thirty-eight local tests passed before launch;
the additional deterministic-budget test also passes (39 tests total).

Next work is to freeze and test revision 3, then measure semantic retention
and answer quality under the revised collector. Passing a token cap
is not corpus admission: genuine memory-dependent questions, independent source
review, future-adapter certification, and the external uncertainty/judge issues
remain unresolved. Training stays paused.
