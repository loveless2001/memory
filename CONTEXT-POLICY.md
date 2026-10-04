# ContextPolicy v2 — train a 4B model to answer or retrieve

Status: **PAUSED AT USER REQUEST** (2026-09-11). The structured-decision
experiment is complete and fails its prospective acceptance rule.

The current stopping decision is to discontinue iteration on this structured
recipe and pause the broader reader/retrieval research campaign. Ordinary prose
supervision improves accuracy on the selected synthetic test, but neither new
checkpoint preserves all previously correct answers. The results do not
establish a reliable reader or disprove the broader memory/retrieval approach.
Further targeted synthetic patches are deferred; no further training,
inference, external evaluation, or serving work is scheduled or authorized by
the earlier campaign plans while this pause is in effect.

If the user later reopens this work, the proposed decision point is a frozen,
independently reviewed sample of the actual target workload, comparing the best
prose checkpoint against a simple baseline on accuracy, cost, and previously
correct answers. This is a deferred proposal, not a queued experiment. Preserve
the checkpoints, complete source references, judgments, failures, and frozen
reports for that decision. The experiment history and original design below
remain as provenance; their prospective wording does not override this pause.

The [completed four-condition supervision experiment](plans/260911-reader-decision/REPORT.md)
compares current v2, a structured prompt, and two independent v2 continuations
on the same 512 new source/question pairs with 64 updates each. Under unblinded
author review, new strict scores are 130/160 current prose, 20/160 current
structured, 155/160 trained prose and 145/160 trained structured. Their regression
scores are 250/260, 29/260, 252/260 and 215/260. Trained structured output also
trails on rendered answers alone: 147/160 new and 222/260 regression. It misses
the frozen 152/160 threshold, loses to the trained prose control, and loses 45
of 259 cases previously answered correctly by at least one non-oracle condition.
Trained prose improves aggregate accuracy but still loses eight protected cases
(seven regressions relative to current v2), so it does not establish reliable
preservation either. The complete report distinguishes wrong state, polarity,
ownership and evidence from exact-span formatting failures. Both continuations
are retained as experimental checkpoints; this result does not clear the reader
for serving or retrieval-policy training. All 1,680 captures and 80 numerical
fixtures completed, all 260 previous direct outputs reproduced exactly, both
adapters reload correctly, base tensors stayed unchanged, and all 1,460 protected
files were preserved. Structured targets use more tokens and computation, so
this is a comparison of complete recipes. Observed cost is $3.35500240; the app
is stopped with zero tasks. No automatic follow-up was launched.

The [completed inference-only factorization diagnostic](plans/260911-reader-factor/REPORT.md)
uses the unchanged v2 adapter on sixteen histories and 64 matched questions.
Unblinded author strict scores are 56/64 direct, 59/64 with model-extracted
records, 62/64 with reviewed oracle records and 60/64 with oracle records plus
reviewed question interpretations. Required-answer scores are 57/64, 59/64,
62/64 and 60/64 respectively. The original pronunciation and explicit-none
errors are fixed by the record prompt, but three negative preferences are
extracted as global none, and correct unknown records still produce unsupported
categorical No answers. All sixteen extractions pass syntax/span checks;
thirteen are semantically correct and twelve match the frozen literal values.
Quotes preserve enough information to recover some answers despite wrong
statuses; this does not validate the typed state. Oracle question interpretation
fixes no remaining failure and adds two withdrawal errors. The report discloses
wording sensitivity and oracle privileges; the selected, correlated challenge
set does not establish internal causal stages or deployment readiness. All 272
captures and 25 numerical fixtures completed, all twelve exact prior direct
answers reproduced, base/adapter tensors stayed unchanged, and all 1,390
protected files were preserved. Observed cost is $0.23685322; the one H100 app
is stopped with zero tasks. That diagnostic used no training.


The [completed revised-supervision reader pilot](plans/260911-reader-sft-v2/REPORT.md)
trained one fresh adapter on the original 384 examples plus 128 source-authored
assertion and preference contrasts. All 144 previously evaluated questions are
now regression cases; 64 questions on sixteen new histories form the fresh test.
Under unblinded author review, strict scores are 141/144 for both v1 and v2 on
regression, and 59/64 to 62/64 on the new test; new required-answer correctness
rises from 59/64 to 63/64. Four new-test answers improve, with one new strict-only
failure from overstating non-preference as explicit rejection. N09-1 still gives
a contradictory Yes with the correct pronunciation; N12-2 omits the explicitly
known no-preference position. Both required target fixes fail, so the prospective
follow-up rule fails. N01 wording and the new rejection-phrasing sensitivities
are disclosed without changing that verdict. All 64 optimizer steps, 416 answers
and 40 cache fixtures completed. All 144 prior adapter token sequences reproduce
exactly; base parameters/buffers and all 1,321 protected files are unchanged,
and saved/reloaded adapter tensors match. Observed cost is $0.79357782; the app
is stopped with zero tasks. The recipe also changes update count and shuffle,
so this does not isolate a data-only causal effect. The checkpoint, complete
review and failure inventory are preserved; no automatic follow-up was launched.

The [completed supervised 4B reader pilot](plans/260911-reader-sft/REPORT.md)
trained one answer-only LoRA adapter on 384 separately authored examples and
compared it with the pinned base reader on 48 new questions and all 96 prior
regression questions. Under unblinded author review, strict passes rise from
35/48 to 48/48 on the new test and 70/96 to 93/96 on regression. Required-answer
scores rise from 38/48 to 48/48 and 78/96 to 93/96. Despite 38 strict corrections,
two previously correct regression answers become wrong: N09-1 gives the wrong
binary polarity while naming the right pronunciation, and N12-2 replaces an
explicit no-preference position with unknown. The predeclared zero-regression
and known-control-preservation requirements therefore fail. N01-1 remains a
failure under the primary convention; its disclosed wording sensitivity does
not change the rejection. All 48 training steps, 288 answer captures and 40
cache checks completed. All 96 base regression token sequences reproduce
exactly; base parameters/buffers are unchanged and the saved adapter reloads
exactly. All 1,249 protected files remain unchanged. Observed cost is $0.76916083;
the single H100 app is stopped. The checkpoint and full failure evidence are
retained. No follow-up run or retrieval-policy training was launched.

The [completed structured-state diagnostic](plans/260911-reader-state/REPORT.md)
collected 288 answers and 52 event extractions with the original 4B reader.
Unblinded author strict scores are 53/72 regression and 17/24 new for raw history,
60/72 and 18/24 for reviewed oracle state, and 52/72 and 14/24 for extracted state.
All clean-suite gates fail. On current-scope questions alone, strict scores are
58/83 raw, 69/83 oracle and 57/83 extracted. Extraction passes schema/span checks
on 50/52 streams, complete semantic event review on 35/52, and semantic resolved
state review on 38/52. Wrong ownership and property scope remain; even reviewed
unknown/no-preference states can produce wrong answers. All 72 prior baseline
token sequences reproduce exactly. All 40 cache checks pass and all 1,185
protected files remain unchanged. Observed cost is $0.52742384; the single app
is stopped. That diagnostic used no training. The report discloses
historical controls, oracle/routing privileges and one question-wording sensitivity.

The [completed Qwen3-8B comparison](plans/260911-reader-qwen3-8b/REPORT.md) collected
all 144 matched conditions with thinking disabled. Under unblinded author review,
the original prompt improves from 17/24 to 20/24 development strict passes and
from 36/48 to 39/48 on the reused fresh cases. Required-answer correctness rises
from 19/24 to 21/24 and from 41/48 to 42/48. The rewrite remains worse, at 15/24
and 28/48 strict passes. Both perfect-suite gates fail. Qwen3-8B is the nearest
dense Qwen3 size to the requested 7B; it differs from 4B-Instruct-2507 in release,
post-training and native template, so this does not isolate parameter count.
All 40 cache checks pass and all 1,074 protected prior files remain unchanged.
Observed total cost, including CPU acquisition and its failed startup, is
$0.34297817. All three apps are stopped; no training or further inference followed.

The [completed paired reader repair](plans/260911-reader-repair/REPORT.md) collected
all 144 answers. Under unblinded author review, the procedural rewrite reduces
strict passes from 17/24 to 14/24 on existing cases and from 36/48 to 26/48 on
fresh cases. It fixes unsupported staleness and two fresh reinstatements but
worsens ownership handling and adds withdrawn-value restatements. Both the
24/24 development and 48/48 fresh gates fail. All 80 cache checks pass, and all
24 previous baseline token sequences reproduce exactly. The first run hit its
checkpointing-related time cap after 35 answers; a disclosed execution amendment
batched commits and collected the remaining 109 in a sequential continuation.
Observed total cost is $1.51146143. Both apps are stopped; no training or broader
run followed. The candidate is rejected, and source-backed state tracking remains
an untested next research direction.

The [completed presentation diagnostic](plans/260911-reader-diagnostic/REPORT.md)
collected all 96 conditions across 24 fresh synthetic cases, with 40/40 cache
checks passing. Under unblinded author review, JSON chronological passes 17/24,
versus 11/24 when withdrawal turns are displayed last; six failures are fixed
with no new failures. Same-value reinstatement passes 8/8 across chronological
wrappers versus 0/8 with withdrawals last. Withdrawal-to-unknown, fictional
ownership and unsupported staleness errors remain, so the primary 24/24 gate
fails. Across all arms, 70/96 answers give the required value or task response,
while only 58/96 satisfy every output criterion. The one-H100 diagnostic finished
in 437.3 seconds, reports $0.53963343 observed cost, and is stopped with zero
tasks. All 928 protected prior files remain unchanged. These short-source
results do not establish transfer to the broader suite, whose 98 uncaptured
conditions remain uncaptured. No training or action labels were produced.

The [broader adjudication](plans/260910-context-policy/20260911-v2-broader-adjudication/REPORT.md)
records 104 pass / 157 fail / one ambiguous across the 262 captured answers.
Claude's correction changed two original passes to fails. The subsequent
user-approved Codex author overlay changes nineteen whole-answer support flags,
restores C020-B/C task completeness, and retains C073-B ambiguity, without further
verdict changes. Both Claude passes remain preserved. This author overlay is
explicitly unblinded and retains the correction reviewer's interpretation of
the withdrawal explanations; it is not another independent review.
Historical-recall passes are 0/30, 27/30 and 28/30 by retrieval depth; withdrawal
passes are 1/15, 0/15 and 0/15. Different-value updates pass 26/42 versus 4/42
for same-value reinstatements. The earlier [117-entry audit](plans/260910-context-policy/20260911-v2-broader-review-audit/REPORT.md)
is preserved as the correction handoff. No action labels or additional inference
were produced by review or adjudication.

The [broader reader run](plans/260910-context-policy/20260911-v2-broader-reader/REPORT.md)
stopped at its internal time deadline after 262 of 360 planned captures. All
forty cache fixtures, sixty notes, 171 note updates and 262 captured transcripts
pass offline verification. Every captured answer passes structural checks and
fits within 90 words. There are 87 complete three-view questions and one partial
question; 98 conditions remain uncaptured. This is a fixed-schedule prefix,
not a random sample or a completed broader evaluation. All 394 protected prior
files remain unchanged. The approved one-H100 run used no retries and reports
an observed cost of $2.85199616 ($6.23823709 cumulative recorded v2 cost).
The [original Claude answer-review handoff](CLAUDE-BROADER-ANSWERS.md) supplied
actual messages, full sources and reviewed references. Its review and correction
are now incorporated through the separate adjudication above; no training or
learned action-policy result is established.

The broader candidate has 120 references across twenty reserved source families:
40 historical recall, 20 withdrawal, 20 attribution and 40 synthetic continuation
cases. The independent v1 reference review accepted 114 and rejected six for
unsupported gender pronouns. V2 applies those six suggested repairs and neutral
wording consistently: twelve cases changed, with 108 accepted cases unchanged.
The delta review accepted all twelve edited cases, with no additional findings.
Together with 108 unchanged parent accepts, this completes reference-review
coverage; it is not a fresh 120-case independent review. Both validators pass.
Reference acceptance is separate from answer-quality reconciliation. See the
[acceptance record and wording decisions](plans/260910-context-policy/20260911-v2-broader-eval-acceptance/STATUS.md)
and [saved delta review](plans/260910-context-policy/20260910-v2-broader-eval-v2/review/REVIEW.md).
V1 and its review remain unchanged. Full-history review used per-family delegates
with central adjudication; the follow-up includes a packet-wide defect scan.
Exact-turn overlap leaves 19 new-family components, or 17 with links through
prior families; these counts do not establish an independent sample size.

The earlier [Claude judge review](plans/260910-context-policy/20260910-v2-judge-handoff/claude-review/REVIEW.md)
is complete: 21 references accepted and 25/42 answers passing. Blind review files
and the separately attributed editorial corrections are preserved. That review
does not validate the new candidate references. Earlier preparation documents
below remain historical snapshots.

A paired 21-question regression passes 8/21 with raw withdrawals and 17/21 with
manually annotated neutral UNKNOWN records. Existing withdrawal cases improve
from 0/10 to 7/10. Four neutral cases still fail: two infer negatives from
unknown values, one asserts a withdrawn reading preference, and one treats a
fictional monologue as user biography. All 40 cache checks and 42 body-format
checks pass; all answers fit 90 words. The 21/21 clean-regression gate fails.
No training or corpus admission occurred. This selected same-author comparison
cost $0.35649983, bringing recorded v2 cost to $3.38624093. See the
[paired regression report](plans/260910-context-policy/20260910-v2-withdrawal-regression/REPORT.md).


The frozen 50-question reader probe completed 40/40 cache checks and 150 answer
captures with reused notes. Historical fact recall passes 3/30, 29/30 and 29/30
at zero/one/two retrievals, but withdrawal compliance is only 1/10, 0/10 and 0/10.
Requiring every frozen criterion yields 11/50, 39/50 and 39/50. All answers fit
90 words; 25 zero-retrieval bodies append an extra action marker that the legacy
runtime helper missed. No training traces were exported. This selected, same-author
development review is not an independent benchmark or learned-policy result.
See the [memory reader report](plans/260910-context-policy/20260910-v2-memory-probe/REPORT.md).

A separate 50-question development version now includes 30 historical fact
questions, ten withdrawal checks and ten controls on the same ten seen training
histories. CPU replay finds complete required user-source fragments for 3/30
fact questions in notes plus recent dialogue and 30/30 after one retrieval.
Relaxed content review finds one additional pre-retrieval match from a different
passage. These are evidence-availability counts, not reader accuracy or action
labels. No new model inference or training ran; earlier artifacts are unchanged.
See the [new data/evidence report](plans/260910-context-policy/20260910-v2-memory-dev/REPORT.md).

Revision 4 passed 40/40 real base-reader cache fixtures, all 63 note updates,
and collected 30 valid answer bodies across ten histories. Manual source/content
counts are 8/10, 8/10 and 10/10 at zero/one/two retrievals. Eleven answers exceed
the 90-word instruction; including that check yields 6/10, 6/10 and 4/10.
The action prefix was supplied, so no generated-action compliance is claimed.
No training occurred. Note provenance now checks out, but selection utility and
memory-dependent question coverage still need work. See the
[revision 4 report](plans/260910-context-policy/20260910-v2-repair-r4/REPORT.md).

Revision 3 passed 40/40 base-reader cache checks and three note updates under
768 tokens. Update four requested an unavailable source ID, so it stopped before
any complete notes or answers. A constrained source-choice decoder is now
integrated as revision 4 and CPU-tested, but has not run on the real 4B. See the
[revision 3 report](plans/260910-context-policy/20260910-v2-repair-r3/REPORT.md).
Training remains paused; source syntax does not establish memory quality.

The next repair passed all 40 real base-reader cache fixtures under the revised
archive/question transcript. Its second note selection rendered to 1,359 tokens
against the 768-token cap, so collection stopped before any complete note or
answer. A subsequent CPU-tested helper admits whole quotes under an exact token
budget (743 tokens in a replay); it is integrated as prospective revision 3,
not GPU-tested or evidence of semantic improvement. Training remains paused. See the
[revision 2 report](plans/260910-context-policy/20260910-v2-repair-r2/REPORT.md).

Four known reference failures and 50 fresh source-only targets were repaired,
with Codex author review and source-bound evidence. A frozen-base ten-question
probe then produced 0/30 protocol-valid answers, masking all 20 routing-label
states. Exploratory content-only counts were 9/10 with notes, 6/10 after one
retrieval, and 5/10 after two. These are selected development cases, not benchmark
scores. Notes truncation, ineffective summaries and retrieval-induced question
drift must be addressed before full label collection. No corpus training has
started. Full-corpus admission and independent evaluation remain pending.
See the [completed diagnostic](plans/260910-context-policy/20260910-v2-repair-probe/REPORT.md)
and its prospective next requirements. Preserve the failed captures and strict
format criterion; do not launch an automatic paid retry.

The subsequent PersonaMem-v2 intake acquired existing training histories and
removed their profile-bearing system messages. Four confirmed grounding or
withdrawal conflicts in a fixed 50-question sample fail the required 48-sound
admission threshold. That intake launched no GPU work or corpus training. The
candidate was not adopted as a replacement training corpus or external test.
See the [intake report](plans/260910-context-policy/20260910-v2-personamem-intake/REPORT.md).

The development dialogue pilot generated 80 sessions in ten histories. Its
measured generation time projects to 5.12 GPU-hours for the full corpus,
exceeding the two-hour allowance for all preparation before notes or labels.
Only six sessions passed the exact-sentence/role contract; most failures were
missing or repeated verbatim anchors, not established factual errors. Corpus
training has not started. See the
[data pilot report](plans/260910-context-policy/20260910-v2-data-pilot/REPORT.md).

Runtime amendment before corpus realization or training: the fixed-adapter
diagnostic reproduced BF16 drift (39/40 exact matches with automatic SDPA,
38/40 with math SDPA). FP32 math SDPA passed all 40 comparisons. Use that
reader execution mode with TF32 disabled for every primary reader arm and
for useful-action label collection. The original BF16 failure remains a
failed result; this is a changed runtime identity, not a relaxed gate.
The shared, query-blind dialogue/notes generator and adapter optimization may
still use the specified BF16 setup. Evaluation uses FP32 for base and adapted
readers alike and charges its real latency and memory cost.

The first real 4B/LoRA preflight passed 39 of 40 exact greedy comparisons.
One continuation differed in wording before EOS, so the registered cache gate
failed and corpus training did not start in that run. Gradient flow, chat-prefix equality,
and rejection of disabled adapters passed. See the
[verified preflight report](plans/260910-context-policy/20260910-v2-preflight/REPORT.md).
The exact prelaunch design and source bytes are preserved with that run.

This is the next experiment after ContextGate v1. The user authorized
implementation and the bounded campaign after reviewing this design. Execute
the correctness and preparation gates before corpus training; do not bypass
a failed gate or automatically retry a paid stage.
The model's original weights remain frozen, but LoRA adapters will change its
attention computation and output behavior. That is a new experimental model
identity outside memsub's existing frozen-reader certification.

The next continuation implements an extractive-note and transcript revision.
Its [prospective plan](plans/260910-context-policy/20260910-v2-repair-revision/PLAN.md)
requires a fresh actual-4B transcript gate before note/body collection and retains
a 15-minute ceiling with zero retries. Forced body collection supplies `ANSWER`;
this cannot count as generated action-format compliance. Full training stays gated.

## Decision and hypothesis

Bank v1 as negative for its external hidden-state controller. On its 360 test
rows, always-retrieve and the surface MLP both reached 90.0% accuracy; the
hidden MLP reached 88.89% and used 47.7% more input tokens than always-retrieve.
The run is preserved in [the v1 report](plans/260910-context-gate/20260910-v1/REPORT.md).

The new hypothesis is narrower than “small models can manage memory”:

> A LoRA-adapted Qwen3-4B can learn to emit a retrieval action only when useful,
> then answer using the appended evidence, with better accuracy/latency than
> strong retrieval baselines under the same memory and execution rules.

Two changes are tested independently: learned action selection and reuse of
the existing KV cache. Cached execution is available to every compatible arm.
A system improvement caused solely by cache reuse is not a policy-learning win.

## Model and training configuration

Use the same immutable `Qwen/Qwen3-4B-Instruct-2507` revision as v1:
`cdbee75f17c01a7cc42f958dc650907174af0554`. Keep torch 2.7.1, transformers
4.55.2 and safetensors 0.5.3. The reader uses FP32 math SDPA after the runtime
amendment above; adapter optimization uses BF16. Proposed added dependency:
`peft==0.17.0`, isolated to this campaign's image rather than the core runtime.
Compatibility with the pinned reader must pass the future GPU preflight.

LoRA: rank 16, alpha 32, dropout 0.05, `q_proj` and `v_proj` in all decoder
layers; no bias, embedding, or LM-head training. Log the actual trainable
module list and parameter count and assert that all original parameters are
frozen. Save separate adapter, tokenizer/template, and runtime hashes.
[PEFT's versioned LoRA API](https://huggingface.co/docs/peft/v0.17.0/package_reference/lora)
supports specifying these target modules and initialization parameters.

Pilot seed 0; one answer-only adapter and one policy adapter. Both start from
the same base and initialization and see the same source conversations.
AdamW, learning rate 1e-4, weight decay 0.01, warmup 5%, gradient clip 1.0,
microbatch 1, accumulation 16, maximum 2 epochs, maximum 500 optimizer steps,
maximum training sequence 8,192 tokens. No cross-conversation packing. Use
gradient checkpointing and `use_cache=False` during training. Check validation
after each quarter epoch and select checkpoints without opening test scores.

Training-token totals, updates, and selected epochs must be reported for both
adapters. Action loss is the intentional difference between them; match answer
targets and answer-token exposure rather than fabricating extra answer data to
hide the policy adapter's additional action tokens. The answer-only adapter
masks routing-marker loss. It is a control for improved reading after SFT,
not an exact equal-FLOP training comparison.

## Data: realistic language without borrowing the test set

### Independent development corpus

Create 400 independent scenario families: 280 train, 60 validation, 60 internal
test, with five questions per family (1,400 / 300 / 300 question states).
Split scenario graphs, authorship/template families, entity namespaces, and
all paraphrases together before realizing the conversations. Share no v1
project-ID fixtures, notes, labels, or captures with this corpus.

Each history contains 8–16 timestamped sessions, targeting 16k–48k model tokens
in total, with natural dialogue and intervening work rather than a table of
latest fields. Cover software changes, scheduling, research decisions,
organizational procedures, and personal preferences. Required mechanisms:

- A proposal is discussed, then rejected; it must not become a current fact.
- A correction changes one requirement but preserves another.
- Different entities have similar names and nearby dates.
- An answer needs evidence from multiple sessions.
- An old instruction still applies despite a later unrelated conversation.
- Some questions have no supported answer and require abstention.

Represent the underlying event graph, accepted/rejected status, temporal
relations, answer aliases/rubric, and supporting turn IDs in a private label
sidecar. Dialogue realization must preserve the graph and never see the final
evaluation questions while choosing prose or distractors. Generated dialogue
is still synthetic; do not call it a collection of real user conversations.

Before training, inspect 50 stratified development questions and all their
evidence manually. Require at least 48 unambiguous, correctly supported cases;
otherwise repair the generation process before freezing any internal/external
test inputs. Log all repairs and regenerate only development data. Reserve
internal test realization templates before that review; no test-driven repair.
The full corpus remains unbuilt. The completed development pilot failed its
throughput and annotation contracts; the 50-question manual audit was not
claimed complete, and none of its generated histories is approved training data.

### External evaluation

Use all 500 questions in **LongMemEval-S cleaned**, without using any of its
questions, answers, oracle sessions, filler sessions, or paraphrases for
training, checkpoint selection, prompt tuning, or retrieval tuning. Its
questions cover extraction, multi-session reasoning, updates, temporal
reasoning, and abstention. The benchmark's histories are partly simulated,
so this is external natural-language evaluation, not proof on organic agent
traffic. [Official benchmark](https://github.com/xiaowu0162/LongMemEval),
[cleaned release](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned).

Pin the cleaned dataset revision and the SHA-256 of
`longmemeval_s_cleaned.json` at acquisition. Pin the evaluator source revision
as well; these are deliberately unresolved artifact identifiers in the design
config, not implicit `main` defaults for a runnable job. Do not load the oracle
JSON as training data: it contains the same evaluation questions.

The acquired file is 277,383,467 bytes with SHA-256
`d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`.
A structure-only audit found 18,464 unique normalized source sessions; 4,375
occur in more than one history. Under the registered all-shared-session
connected-component rule, all 500 questions form **one component**. Therefore
the registered external confidence bounds and advancement rule are currently
unassessable. No external predictions or scores were generated. Do not silently
replace the grouping rule with independent-question resampling.

Run an audit of normalized session hashes, source graph IDs, and word-13-gram
overlap across development splits and against the external corpus. Hash exact
duplicates into connected components; report near duplicates and adjudicate
them before checkpoint selection. Shared boilerplate alone is not grounds to
drop a test item. Unknown pretraining contamination remains a limitation.

LongMemEval-V2 was also reviewed. Its multimodal web/enterprise trajectories
and separate memory-backend/reader interface would introduce extra changes
for this text-only 4B action-policy study. Defer it to a later agentic test;
do not present a text-only adaptation as its official leaderboard result.
[Official V2 harness](https://github.com/xiaowu0162/LongMemEval-V2).

## Memory construction, shared by all arms

Archive every original turn with session ID and timestamp. Chunk at turn
boundaries, splitting overlong turns into at most 384-token pieces with
64-token overlap. Index original text using BM25 and the existing pinned
Qwen3-Embedding-0.6B shadow model. Fuse the two rank lists with reciprocal-rank
fusion (`k=60`); no reranker. The embedding revision must be recorded before
use. Audit embedding and chunking cost separately from reader cost.

Construct one query-blind chronological notes stream with the **unadapted**
4B, before revealing each question: retain at most 768 note tokens and the
latest 512 raw tokens, with source pointers. The summarizer receives earlier
notes plus the next session and a fixed instruction to retain decisions,
corrections, dates, and unresolved uncertainties. It receives no gold labels,
question, `has_answer` field, or answer-session IDs. All arms consume the same
notes, archive, index, and recent window. Summarization failures are measured;
do not replace bad summaries with oracle-written notes.

Use BM25-only and hybrid retrieval on **development validation** with the base
always-retrieve reader. Select the stronger by answer accuracy; within one
percentage point prefer the cheaper query latency. Freeze that retriever for
every primary arm. Record both validation results. This permits a bounded
choice between two specified baselines, not a retrieval sweep on external test.

At each retrieval, return the next ranked unseen chunks in chronological order,
up to 1,024 newly supplied tokens. Stop after two retrievals and 2,048 total
evidence tokens. Same fixed original question and frozen ranking for every
arm; query rewriting and learned block selection are future questions.
Missing matches and exhausted budgets are explicit tool results.

## Action and answer protocol

The model generates complete assistant messages, greedily, with no answer
choices or gold-answer candidates:

```text
RETRIEVE
```

or

```text
ANSWER
The deployment uses port 8443; the later discussion only changed the timeout.
```

`RETRIEVE` must be the entire stripped message. `ANSWER` must be its own first
line followed by nonempty answer text. An unsupported question is answered
with an explicit statement that the history does not establish the fact.
Unknown markers, malformed messages, token-limit exits, and retrieval after
budget exhaustion are traced and counted as failures. Do not silently map an
invalid action to retrieval or use a gold-informed fallback. Primary results
use real generated messages; constrained action-logit scores are diagnostic.

Allow at most 192 new tokens per assistant message and at most 384 generated
tokens per query across all actions and answers. The model must still fit the
8,192-token active context cap. Retrieval text is appended as a tool message;
the original notes and question are never re-rendered into a new prefill just
because retrieval occurred. Original history can exceed the active window.

## Training examples and loss

Create counterfactual notes-only, one-retrieval, and two-retrieval answer
traces using the same unadapted reader, actual retriever, and execution
contract. Private fact graphs/rubrics score them. Keep failed, neutral, and
harmful retrieval outcomes in the trace archive.

For action supervision, choose the least expensive **supported, correct**
continuation among those observed traces. Prefer answering now when it is
already supported and correct; prefer retrieval when it actually repairs the
answer. Compare one and two retrievals only when both are allowed by budget.
Correct guesses unsupported by visible evidence do not become answer-now
demonstrations. Gold text is never added to a model-visible prompt.

If none of the continuations is supported and correct, mask the action target
for that state. It can still contribute a grounded answer/abstention target
when the visible evidence and sidecar rubric justify one. Do not teach a gold
answer from an insufficient note state. Retain all such cases in evaluation;
this mask is a training-label decision only. Report the masked fraction by
family and whether at least 200 answer-now and 200 retrieve states remain.

Policy adapter objective: assistant answer-token cross-entropy plus an
equal-weight, per-action normalized routing-message cross-entropy. Mask all
system/user/tool evidence tokens and padding; avoid letting a long answer
drown out the short action target. The answer-only control masks action loss
on exactly the same demonstrations. Do not train on prior system/private
metadata or test outputs.

This is supervised imitation of observed useful actions, not optimal-control
or reinforcement-learning evidence. Labels are collected with the base
reader; adaptation can change which actions are useful. Measure this by
evaluating the same policy adapter under forced retrieval and free actions.
Do not relabel and retrain after inspecting external results.

## KV reuse contract and correctness gates

For an immutable `(base revision, adapter hash, tokenizer/template hash,
precision, attention implementation)` identity, cached token IDs must be an
exact prefix of the next transcript's token IDs. Append only the unseen
suffix, including consumed action tokens and the actual tool-result tokens.
Never rebuild a cache under one adapter and continue it under another, even
if the base weights match. A changed note, timestamp, template, or tokenization
prefix invalidates the cache; a real reset starts a new prefill and is charged.

Use standard `DynamicCache`, correct total attention-mask length, logical
positions, and `cache_position`. Avoid editing old messages to insert evidence
ahead of the question. Verify chat-template prefix equality before model use,
including assistant endings, tool wrappers, and generation headers. Cache
reuse does not make suffix attention or output generation free.
[Transformers cache explanation](https://huggingface.co/docs/transformers/v4.55.4/cache_explanation)
is supporting documentation; the implementation is tested against the repo's
installed 4.55.2, not silently upgraded to the documentation version.

The local prototype is `experiments/context_policy/cache_session.py`.
It validates the caller-supplied identity; it does not hash live parameters or
detect an adapter switched behind its back. The future model owner must bind
that identity to the loaded weights and prevent in-place adapter switching.
Required checks: prefix/suffix logits against a fresh forward, multiple tool
append operations, exact token accounting, unchanged prefix retention,
rejection of a changed prefix or model/adapter identity, empty append rejection,
length limits, and failure poisoning of partially updated caches.

Before real training, additionally verify on the pinned 4B + actual adapter:
full versus reused-cache greedy sequences agree on a fixed 40 development
prompts, no silent adapter switch, and actual Qwen chat-template tool appends
preserve the prefix. Record bf16 numerical deltas and any argmax changes. A
cache correctness failure stops the campaign before collecting useful-action
labels. Tiny CPU tests alone cannot pass that GPU gate.

## Comparison arms

| Arm | Reader | Routing | Purpose |
|---|---|---|---|
| Base notes | Base 4B | Answer now | Memory-loss reference |
| Base RAG | Base 4B | Always retrieve | Strong untrained baseline |
| Base adaptive | Base 4B | Generated actions | Prompt-only control |
| Answer-SFT RAG | Answer-only adapter | Always retrieve | Reading improvement control |
| Policy-SFT RAG | Policy adapter | Always retrieve | Same-reader policy attribution |
| Policy-SFT adaptive | Policy adapter | Generated actions | Primary candidate |
| Policy-SFT adaptive, fresh | Same policy adapter | Same generated actions | Cache attribution ablation |
| Oracle evidence | Base and policy reader | Gold evidence | Reader/retriever diagnostic |

Choose always-retrieve's one- versus two-batch evidence budget on development
validation using accuracy, with latency as tie-breaker within one percentage
point, then freeze it. Every compatible arm uses cache reuse. Forced RAG
retrieves before its first answer prefill; it is not charged an artificial
model decision call. The fresh-cache ablation replays the *same realized
token transcript* to isolate numerical/compute effects, and also runs a
separate fresh generation to report any behavioral drift.

Each adapter has its own independent cache and fingerprint. Report the
primary against both strongest development-selected RAG baseline and
Policy-SFT RAG. An improvement over the base model alone is not evidence
that learned routing is responsible.
Select the strongest RAG arm from Base, Answer-SFT, and Policy-SFT RAG by
validation accuracy, breaking ties within one percentage point by query
latency. Freeze this selection before internal/external scoring. If it is
Policy-SFT RAG, report the duplicate comparator transparently and retain the
prespecified conservative significance threshold.

## Evaluation, cost, and success rule

Internal test: deterministic graph/rubric scoring with declared aliases and
numeric/date normalization. External test: free-form answer scoring using the
official benchmark rubric, with a separately frozen judge configuration.
Prefer its official evaluator; the specific judge snapshot, paid API budget,
and source revision must be recorded before external evaluation. A local
4B self-judge is not a substitute for independent evaluation. Until that
configuration is frozen, external launch readiness remains false.

Blindly human-review 50 external answer pairs selected by an ID hash (no arm
names), plus disagreements between two fixed judge repetitions. Include every
external abstention item in answer accuracy; retrieval-recall metrics exclude
only items with no evidence locations and report that denominator. Private
benchmark metadata never reaches a retriever or policy prompt.

Measure correctness, unsupported confident answers, appropriate abstention,
actual action validity, retrieval rounds, evidence recall, fresh input tokens,
attention context lengths, generated tokens, peak memory, warm/cold query
latency, and p95 latency. Time retrieval search and archive access, tokenizer,
model calls, and actions—not just GPU forward calls. Show raw per-arm totals.
Record one-time note/index construction and training costs separately, plus
amortized totals for 1, 10, and 100 queries per history. A token reduction alone
is not a latency or total-cost result.

Run arms sequentially on the same H100 with randomized per-query arm order
and one unscored warmup. Bootstrap paired differences by source conversation;
for external histories sharing source sessions, construct connected components
before seeing results and bootstrap those components. Report effective group
count; insufficient independent groups means inconclusive, not a question-level
CI masquerading as independent evidence.

**Primary advancement rule (external 500, one frozen checkpoint):**

1. Against both Policy-SFT RAG and the strongest frozen RAG baseline, paired
   accuracy lower bounds must be at least -0.02.
2. Mean warm end-to-end query latency must fall at least 15% against both,
   with paired latency-difference upper bounds below zero.
3. p95 query latency cannot increase more than 10%; invalid action rate must
   be <=1%; unsupported-answer rate cannot worsen by more than two points.
4. The conclusion must survive the blind scoring audit and exclude savings
   attributable solely to different preprocessing or missing evidence costs.

Use simultaneous one-sided bounds (Bonferroni over the four accuracy/mean-
latency comparisons, alpha 0.0125 each) rather than claiming four independent
95% tests establish one result. Secondary accuracy gains and cache savings
are reported but cannot replace this rule. Report inconclusive intervals as
such; do not loosen margins or tune checkpoints using external test results.

## Historical compute plan and preparation readiness

The earlier campaign design specified these ceilings. They are retained for
provenance and do not authorize resuming work during the current pause:

| Stage | Ceiling | Exit condition |
|---|---|---|
| Data preparation/review | Local or separately budgeted | Frozen corpus, sources, audits, rubrics |
| GPU cache + adapter preflight | 15 minutes, one H100 | Exact protocol/caching and gradient checks pass |
| Notes, embeddings, and counterfactual labels | 120 minutes total, one H100 | Complete frozen caches and label archive; no partial-data training |
| Train two seed-0 adapters | 90 minutes total, one H100 | Checkpoints and finite loss/gradient telemetry |
| Internal paired pilot | 30 minutes, one H100 | >=98% valid actions; no >5 pp accuracy loss versus same-reader RAG |
| External evaluation | 90 minutes, one H100 | Only after internal gate; frozen judge/budget ready |

Total planned GPU ceiling: 345 minutes, zero automatic retries. These are
abort ceilings, not estimates that the workload will finish. Time a small
development preparation batch first; if projected work exceeds its ceiling,
stop and revise the design before training rather than silently shrinking
the corpus or omitting preprocessing costs. If a stage
times out, retain the partial artifacts and stop; no implicit GPU upgrade or
unbounded resume. Price at launch, and include CPU/memory, preprocessing and
judge charges separately. A positive seed-0 result earns a separately planned
replication; it does not automatically authorize a seed sweep.

The original full-corpus preparation state is recorded in
`experiments/context_policy/design.json`:
the full development corpus and judge configuration remain pending. The
external file hash is pinned and the 4B FP32 cache gate has passed. Full
dataset realization and trainer integration remain behind the failed data
preparation gate. The external inference rule also needs a prospective design
decision. At that preparation checkpoint, GPU work consisted of the original preflight, its explicitly
authorized numerical diagnostic, the stopped development data pilot, and the
completed ten-question repaired-reference diagnostic. The later bounded
reader-training pilots are documented above; full-corpus policy training and
external scoring have not occurred. All remaining stages are paused.
