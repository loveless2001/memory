# Memory reader probe: retrieval works; withdrawal handling fails

The frozen 50-question probe completed **40/40 cache checks and 150 answer
captures**. Historical fact recall passes **3/30 with notes and recent dialogue,
29/30 after one retrieval, and 29/30 after two**. Withdrawal compliance passes
only **1/10, 0/10 and 0/10**. Repeating a withdrawn detail or inferring its
opposite fails the frozen rule. No training was performed or admitted.

## Scope and frozen criteria

This run uses the [new development question version](../20260910-v2-memory-dev/REPORT.md)
and [prelaunch plan](../20260910-v2-memory-probe-plan/PLAN.md). Its 30 fact
questions, ten withdrawal questions, five missing-information questions and
five generic controls remain unchanged. The same author wrote references and
reviewed outputs; independent semantic review remains pending.

The revision-4 notes were reused byte-for-byte. All ten history bindings,
65 source quotations and 147 detected withdrawal instructions passed validation.
No note generation ran. The original FP32 math-SDPA reader, TF32-off setting,
archival transcript, 512-token recent window, 384/64-token chunks/overlap,
two 1,024-token evidence rounds and 192-token output cap were preserved.
Private references were not mounted into the reader image.

The primary development criterion is the conjunction of task completeness,
source consistency, support in the actual visible state, valid answer-body
structure and at most 90 whitespace-delimited words. Safe abstention without
the requested historical facts is incomplete; unsupported correct guesses
would also fail. Draft recall does not establish autobiography. Merely finding
reference fragments in retrieval is not counted as answer correctness.

## Results

| Passes under every frozen criterion | Notes + recent | +1 retrieval | +2 retrievals |
|---|---:|---:|---:|
| Historical facts | 3/30 | 29/30 | 29/30 |
| Withdrawal handling | 1/10 | 0/10 | 0/10 |
| Missing information | 2/5 | 5/5 | 5/5 |
| Generic controls | 5/5 | 5/5 | 5/5 |
| **All questions** | **11/50** | **39/50** | **39/50** |

The 26 recovered fact answers are the main retrieval benefit in this selected
sample. The three facts already retained in notes are answered correctly in
every state. Most other zero-retrieval fact responses are cautious: 23 acknowledge
missing information. Two instead conflate unrelated notes into specific wrong
answers; two overclaim that an unseen original passage lacks the requested
information. The [150 judgments](judgments.json) bind each decision to its
capture and frozen reference, with reasons and separate criteria.

One fact question remains wrong despite complete source evidence. For
`memory-dev-v1-746-2`, user T8 names **carrying props and adjusting lights**.
After one retrieval the answer substitutes running lines and setting up chairs
from an unrelated assistant passage, T57. After two retrievals it combines
running lines with adjusting lights. This is wrong passage attribution, not
failure to retrieve the required original user source. It is one development
case, not a general causal claim about assistant-text retrieval.

## Withdrawal failures and protocol discrepancy

Of the 30 withdrawal answers, one passes. The other 29 have these primary
failure classifications:

- **21 infer the opposite preference.** Forgetting enjoyment of jigsaw puzzles,
  snowboarding or aquarium visits becomes a claim that the user does not enjoy
  them. The coffee/tea case asserts a tea preference after withdrawal of a coffee
  preference, adding archival assistant suggestions as supposed personal evidence.
- **Six acknowledge that the current preference is unknown but repeat its
  withdrawn value.** These are repeat-only failures; some opposite-inference
  responses also repeat old details.
- **Two assert a known absence of preference**, rather than acknowledging that
  the preference is unknown.

Every tested withdrawal instruction is present in the compact notes. More
retrieval therefore does not fix missing constraints. The sole passing case,
the pen question without retrieval, deteriorates when later answers repeat the
hotel-ballpoint detail. This does not establish a general forgetting capability,
and successful generic clarification alone would not prove one either.

All **150 answers meet the 90-word limit**; the longest is 79 words. The runtime
helper also marks all 150 structurally valid, but its implementation checks only
for a **leading** repeated action marker. Manual audit finds **25 extra trailing
`RETRIEVE` markers**, all in zero-retrieval bodies: 22 fact questions and three
missing-information controls. The prelaunch rule excluded repeated action
markers anywhere, so the corresponding frozen body-rule counts are **25/50,
50/50 and 50/50**. The original runtime flags are preserved; neither the helper
nor old scores were rewritten after observing this mismatch.

Source/content criteria alone give 13/50, 39/50 and 39/50. Adding the frozen
body rule produces the primary 11/50, 39/50 and 39/50 totals. All five
missing-information answers recognize the absent requested value, but three
zero-retrieval answers append an action marker; one also makes an unsupported
claim about the unseen email. Their improvement is not recovered memory.

`ANSWER\n` was supplied for every capture. **Generated action-format validity
remains null**. A trailing `RETRIEVE` is not an observed policy decision, and
forced collection is not an adaptive agent rollout.

## Routing diagnostics and limits

The 100 nonterminal states yield **50 ANSWER, 29 RETRIEVE and 21 masked**
counterfactual proposals under the frozen conjunction. Of the 29 retrieval
proposals, 26 concern fact recovery and three concern missing-information
responses whose body formatting improves after retrieval. No second-round
retrieval proposal is supported by this sample. These
[diagnostics](routing-diagnostics.json) are not generated actions or an admitted
training dataset. **No training traces were exported.**

There are ten already-seen source histories, not 50 independent examples.
Twenty-nine fact questions concern supplied drafts or translation passages;
explicit lexical cues make all 30 source answers available after one retrieval.
The author knew the prior histories and notes. The reader results are useful
development evidence, not a held-out benchmark or policy advancement result.
The shorter answers on this new question distribution do not demonstrate a
length-control improvement over revision 4's different questions.

## Verification, time and cost

- Run: `20260910-v2-memory-probe`.
- App: [`ap-UtIXt4LhjVawrEUXrCkDkZ`](https://modal.com/apps/syntracts/main/ap-UtIXt4LhjVawrEUXrCkDkZ), completed.
- Function: `fc-01M24Z40SDDW7Q67BVF465XXDS`.
- Function elapsed: **591.667 seconds** within the 900-second timeout.
- Measured answer-capture time: **205.948 seconds** in total.
- Observed app charge: **$0.71299876**; cumulative ContextPolicy v2 charges:
  **$3.02974110**. No judge or training charge.
- Local verification before launch: **17 tests passed**, including reused-note
  tampering checks and the existing transcript/body tests.

| Per-capture mean | Notes + recent | +1 retrieval | +2 retrievals |
|---|---:|---:|---:|
| Input tokens | 1,468.42 | 2,499.82 | 3,513.46 |
| Capture seconds | 1.315 | 1.168 | 1.636 |

These are serial forced-answer timings with different generated lengths, not
paired adaptive latency estimates or an end-to-end speedup. Function elapsed
also includes model/cache work, retrieval, serialization and volume commits.

The original client recovered from two heartbeat timeouts before dispatch;
there was no resubmission. See [connection record](client-connection-note.json),
[launch](launch.json), [completed app status](completed-app-status.json) and
[billing](billing.json).
[Source/capture verification](source-capture-verification.json) checks all five
remote artifact hashes, 21 launch snapshots, 34 frozen inputs/source bindings,
40 cache fixtures, reused notes and all 150 actual input views/token records
against the earlier CPU replay. Prior frozen data and artifacts remain intact.

## Next decision

The reader can recover most of these specific facts with ordinary retrieval.
Keep training paused while repairing withdrawal semantics and answer-body
validation, before collecting a larger training corpus. Keep the present
captures and scores as a failed withdrawal diagnostic, and version any new
instruction/parser change prospectively. Independent review, broader source
coverage, trained-adapter certification and external evaluation remain pending.
No further GPU run, corpus training, commit, push or publication occurred.
