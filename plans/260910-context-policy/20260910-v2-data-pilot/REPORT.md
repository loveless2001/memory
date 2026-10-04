# ContextPolicy v2 development data pilot

**Verdict: data_pilot_failed; no training started.** Generation throughput
exceeds the preparation budget, and the generated dialogue does not reliably
meet the exact-sentence annotation contract. The FP32 cache gate remains passed.

| Measurement | Result |
|---|---:|
| Development histories | 10: seven training, three validation |
| Sessions | 80 |
| Generated tokens | 178,437 |
| Generation time | 460.97 seconds |
| Generation throughput | 387.09 tokens/second |
| Projected generation for 400 histories | 5.12 GPU-hours |
| Entire preparation allowance | 2 GPU-hours |
| Sessions passing exact-sentence/role checks | 6 / 80 |
| Histories satisfying every structural check | 0 / 10 |
| Function elapsed | 478.35 seconds |
| Modal reported app cost | $0.59335205 |

The projection linearly scales this small pilot, including its partial final
batch; it is an estimate, not a completed full-corpus measurement. Even using
only the full 64-session batch gives approximately 4.76 GPU-hours. Both exclude
notes, embeddings, retrieval selection, and counterfactual labels. The current
implementation cannot fit the authorized two-hour preparation allowance.

## What the structural failures mean

Seventy-three sessions failed because a required sentence did not appear
exactly once; one failed alternating-role structure; six passed. Spot checks
showed legitimate paraphrases and repetitions of supplied facts. Thus 6/80 is
**not factual-answer accuracy**, and this audit does not establish that the
other 74 sessions are factually incorrect. The verbatim matcher cannot certify
the intended grounding of this free-form generated data.

For example, a required statement that the Hazel Park review is Friday became
an explanation that the meeting is set for Friday. The dialogue additionally
invented calendar detail and operational procedures. Those additions require
semantic review against the event graph; relaxing string matching alone would
not establish that every future question has an unambiguous grounded answer.
No 50-question manual audit is claimed complete. No generated history was
promoted to approved training data.

## Execution and provenance

The controller requested an app stop after the first 64-session batch already
showed that the preparation budget would be exceeded. The first CLI stop
attempt required a noninteractive flag. The final batch completed before the
confirmed stop took effect, so the authoritative committed result contains all
80 sessions. The local waiting client received a stop-related error; the saved
remote `status.json` and `data-pilot-verdict.json` record `data_pilot_failed`.

- [Modal app](https://modal.com/apps/syntracts/main/ap-UrxhoWnALWP1LgS7lwdWGL).
- Function call: `fc-01M23T3BYKCSN5QNZ5NDGH00KF`.
- Source binding: `0c6ea1d9cd5d4976db7e5b231e7708a312d6e16ef283310566776794ec3c5fc5`.
- Six remote artifact hashes and eleven original source hashes verified.
- Raw dialogue and blueprint mirrors are retained locally and on the Modal volume.
- The original ContextGate v1 source still matches its completed-run manifest.
- Current local cache, training-loss, and corpus-contract suite: 21 passed.

## Additional external-test limitation

A separate structure-only audit of all 500 cleaned LongMemEval-S records found
18,464 unique normalized sessions, of which 4,375 are reused. Shared sessions
connect every record into one component. Under the registered source-component
bootstrap, the external confidence interval and advancement rule are
unassessable. This does not mean that descriptive benchmark scores are useless;
it means the specified uncertainty calculation cannot support an advancement
claim. No external question answers or predictions were scored.

The next data revision should avoid generating millions of new dialogue tokens,
separate semantic grounding from verbatim matching, and settle external inference
before claiming a successful experiment. See [the prospective data revision](../NEXT-DATA-PLAN.md).
