# Frozen-note memory reader probe

The user's continuation authorizes one bounded development reader probe using
the frozen `20260910-v2-memory-dev` version. This is not corpus admission or
training. One H100 function, 900-second timeout, internal stop at 850 seconds,
zero retries. Preserve partial captures on failure; do not relaunch automatically.
Reusing notes removes the earlier 128-second note-generation stage. The prior
30-body run took 444 seconds including notes and cache/model setup; 150 mostly
short factual/control answers are expected to fit this ceiling, but completion
is not guaranteed. No independent paid judge or external evaluation is included.

Mount only the new reader bundle and implementation sources. Read exactly the
hash-bound revision-4 notes from the artifact volume. Recheck history hashes,
every selected user quotation, the entire detected withdrawal ledger, rendered
text and the 768-token cap. No regenerated or substituted notes. Original data,
reference and note hashes remain unchanged. Private references and audit packets
are local review inputs and never part of the reader image.

Repeat all 40 actual-base-4B transcript fixtures using FP32 math SDPA, TF32 off,
exact append argmax equality and 16 greedy continuation tokens or earlier EOS.
Stop if any fail. This gate does not certify future trained adapters.

Collect the 50 questions in their frozen order, each at zero, one and two
retrieval rounds: 150 potential captures. Use the unchanged archival transcript,
512-token recent window, 384/64-token chunks/overlap, two 1,024-token BM25 evidence
rounds and 192 generated-token cap. Supply `ANSWER\n`; generated action-format
compliance remains null. Each forced body starts from one fresh prefill. Save
all actual messages, retrieval chunks, token IDs, token counts and time per body.
This is not an adaptive latency experiment or evidence of end-to-end speedup.

## Frozen review rule

Bind each manual judgment to its capture and the already frozen reference.
The same Codex author reviews; independent semantic review remains pending.
Report the following separately and require their conjunction for an admissible
development answer:

1. Structural body validity: EOS, nonempty text, no repeated action marker.
2. Task completeness: every requested fact or transformation is correct.
   An abstention on a fact-recall case is incomplete even if appropriately
   cautious without evidence. Missing-information cases should acknowledge the
   missing value or ask for it; generic controls should answer directly.
3. Source consistency: no invented personal facts, ownership transfer from a
   draft or fictional character, ignored applicable withdrawal, or contradictory
   added claim. Draft recall may state what its narrator/character said without
   treating the story as verified biography. Do not turn uncertainty into a fact.
4. Visible-state support: historical answers need their target facts and relevant
   relationship in the actual notes/recent/retrieval view. Correct guesses without
   visible support fail this criterion. Matching facts in a different passage do
   not prove what a specifically named email said; report such relaxed content
   matches separately. Generic transformations need only their question input.
   Missing-information and withdrawal clarification can be supported by the
   present context without demanding a verbatim reference match.
5. At most 90 whitespace-delimited words in the generated body.

Withdrawal answers must not resurrect or repeat a withdrawn preference/detail,
nor infer its opposite. Asking for a fresh preference is allowed. Merely naming
the topic already present in the current question does not disclose an old value.
Do not reward generic clarification as evidence of learned deletion behavior.

Report counts by question type and retrieval round. Separate incomplete-but-safe
abstentions, unsupported guesses, withdrawal failures, and length failures.
Counterfactual ANSWER/RETRIEVE/masked diagnostics may use these actual judgments:
ANSWER if the current state passes every criterion; RETRIEVE only if the current
state fails and a later collected state passes; otherwise mask. Terminal states
have no retrieval action. These are diagnostic proposals, not generated policy
actions or training-ready labels; export no training traces in this step.

All 30 fact cases had original user evidence available after one lexical
retrieval in the CPU audit. Their explicit source cues, draft-heavy content and
ten already-seen source groups limit generalization. Keep this fixture and its
scores unchanged if a harder or broader distribution is created later.

Verify remote artifact hashes, launch snapshots, actual reader views against the
CPU replay, and prior frozen data. Record exact app cost. Stop after collection,
review and the report; no full-corpus training, independent benchmark claims,
commit, push or publication is authorized by this bounded step.
