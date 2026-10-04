# Repaired-reference diagnostic: no usable action targets

The source-only reference repair is complete for this bounded development sample.
The frozen-base reader diagnostic is complete, but **0/30 answers satisfy the
registered action protocol**, so all **20 nonterminal action targets are masked**.
No corpus-trained adapter or external evaluation exists. Do not launch full
label collection or training from this batch.

## What was run

Ten new PersonaMem-v2 training personas, one unchanged question per persona,
were selected from the 50 newly authored references. Seven questions have
source-supported personal context; three exercise general advice or withdrawal.
This deliberately enriched sample is neither random nor held out. The same
Codex agent authored the references and reviewed the outputs; there was no
independent human review or paid judge.

The pinned Qwen3-4B reader stayed frozen. Query-blind notes used a single full
history pass (768-token cap, BF16); answers used the previously certified FP32
math SDPA runtime, TF32 disabled. BM25 supplied up to two 1,024-token evidence
rounds; recent dialogue was capped at 512 tokens. All three forced-answer states
used real captured contexts. The reader received no reference answers, private
rubrics, or profile-bearing system messages. These temporary choices were
recorded in the [prelaunch plan](../20260910-v2-label-repair/DIAGNOSTIC-PLAN.md).
This run does not certify adaptive tool appends or trained-policy behavior.

References and inputs were frozen before launch. The judgment rubric was frozen
during note generation, before inspecting any reader answer. Raw artifacts and
all 14 source-snapshot hashes were verified. The remote status remains the
unaltered collection-time `awaiting_manual_judgments`; the local
[judgment summary](judgment-summary.json) records the completed review.

## Results

| Measurement | Notes + recent | +1 retrieval | +2 retrievals |
|---|---:|---:|---:|
| Strict acceptable answers | 0/10 | 0/10 | 0/10 |
| Exploratory content-only acceptable | 9/10 | 6/10 | 5/10 |
| Mean input tokens | 1,189.7 | 2,087.6 | 2,988.8 |
| Mean capture seconds | 2.249 | 2.465 | 2.999 |

All 30 generations ended at EOS. Twenty-nine omitted `ANSWER`; one emitted
`ANSWER  \n` with two spaces, which the exact parser rejects. The original
format score remains unchanged. Format failure is not evidence of an adapter
failure: no corpus-trained adapter exists.

Content-only judgments explicitly disregard the action marker and accept useful
general advice where the question permits it. They are a diagnostic, not revised
primary labels or an accuracy claim. See [all 30 judgments](judgments.json),
including reasons and borderline cases. No confidence intervals are warranted
for this selected ten-question engineering sample. Timing is one serial capture
per state, including forced-answer prefill, not a paired adaptive latency test.

Five retrieved outputs answer a different question: the city-networking query
gets background-sound advice after round two; the hobbies query gets knee
intervention advice after both retrieval rounds; the road-trip query gets a
history of soda counters after round two; the gala query gets an outdoor
itinerary after round one. Two aerial-photography outputs emphasize low angles;
one also treats forgotten drone ownership as a reason to avoid drones. Two
absence-support outputs reuse the withdrawn inspiring-person/legacy framing.
These are output-level observations; the experiment does not isolate whether
ranking, context placement, or model conditioning caused them.

For the local-April query, retrieval changes a generic season assumption into a
request for the user's current location. This is the sole notes-fail to retrieved-
pass change in the exploratory judgments. The archive contains a past Santa
Monica hike, but not a confirmed current starting location.

The notes stage also needs repair: **5/10 notes hit the 768-token cap without
EOS**, two others only claimed that summarization was complete, and one capped
summary repeated the same few sentences. Persona 945 renumbered source turns
and turned withdrawals into claims such as “no longer visits antique fairs.”
The notes are not reliable evidence just because they claim to preserve facts.
Relevant personal evidence was retrieved for several questions, but the answers
mostly remained generic or drifted to an older question. This does not establish
a useful memory-dependent training distribution.

## Accounting and provenance

- App: `ap-fsL2D6hYclHYgj4tJ6Aq8o` (completed).
- Function call: `fc-01M24RSS7KX5GMKRGX1VD8YNE2`.
- Total function elapsed: 270.878 seconds; notes: 117.026 seconds; captures: 77.124 seconds.
- Reported app charge: **$0.30522266** (H100 $0.27430595, CPU $0.01313891, memory $0.01777780).
- Cumulative ContextPolicy v2 app charges observed: **$1.38398351**.
- No additional judge charge; zero trainable parameters; no automatic paid retry.

[Billing](billing.json), [launch](launch.json), and [hash verification](verification.json)
bind this report to the saved evidence. Original ContextGate v1 sources remain
unchanged. Local cache, training-loss, corpus, intake, reference, and pilot tests:
34 passed.

## Required changes before further paid work

1. Separate answer-body collection from learning the action syntax. Prospectively
   freeze whether counterfactual collection supplies an `ANSWER\n` prefix or uses
   independently grounded answer demonstrations with explicit markers. Continue
   evaluating free-running actions with the existing strict parser. Do not relabel
   these malformed captures as generated protocol successes.
2. Restore bounded session-wise note updates and audit actual retained user facts,
   withdrawal constraints, and original turn identifiers. Reject empty/meta-only
   notes and track truncation explicitly. Time a small batch before scaling.
3. Make retrieved dialogue clearly archival, retain the current question after
   evidence in an append-only-compatible transcript, and check whether this fixes
   question drift. Freeze this as a new prompt/runtime identity and rerun the real
   cache-equivalence gate before relying on its latency. Retrieval ranking also
   needs evidence-recall checks; BM25 here was only a temporary diagnostic.
4. Admit a development distribution with demonstrable memory need. Most selected
   requests allow correct generic advice; extra personal detail alone is not an
   accuracy benefit. Preserve these results, retain unsupported-answer masks,
   and perform independent semantic review before full-corpus admission.

These are prospective requirements, not completed fixes or authorization for an
automatic rerun. The external one-connected-source-component inference issue and
independent judge configuration also remain unresolved.
