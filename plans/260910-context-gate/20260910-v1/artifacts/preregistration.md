# ContextGate v1 — retrieval control for a frozen 4B model

Status: designed 2026-09-10; execution status and artifact hashes are recorded
under `plans/260910-context-gate/`. This is an isolated research campaign,
authorized by the user's request to design the experiment and train on Modal.
It does not change memsub's compaction certification or production defaults.

## Question and scope

Can a small controller reading a frozen Qwen3-4B's pre-answer state decide
when retrieving original conversation turns improves its answer, beyond
ordinary confidence and visible note-coverage features?

Codex's experimental context feature motivates notes plus recoverable history.
Its public description does not demonstrate reliable retrieval control in a
4B model. The local evidence motivating this experiment is clean E1FULL's
pointwise/aggregation tradeoff and MergeCert Q2's residual-versus-surface
routability gap. Those are KV-policy results; this new text-memory experiment
must establish its own labels, calibration, and behavioral outcomes.

This first stage is a **controlled, single-decision diagnostic** using
synthetic conversation histories, deterministic notes, constrained MCQ
answers, and constrained R/S retrieval decisions. It neither reproduces
Codex nor establishes natural agent performance, free-form tool adherence,
learned note writing, or repeated-reset reliability.

The backbone stays frozen, bf16, without adapters. Training means training
small retrieval-utility controllers on freshly collected 4B states and
counterfactual outcomes. Existing KV compactors, gates, probes, and historical
corpora are not trained on or overwritten.

## Data and pre-registered splits

The seeded generator builds independent fictional project conversations.
Each has six projects, initial configurations, service-owner registries,
later amendments, and unrelated administrative turns. Three task families:

1. Exact current artifact identifier.
2. A numeric requirement after a superseding amendment.
3. Current project-to-service-to-owner binding, requiring multiple turns.

Every episode has complete, randomly omitted, and stale working-note views.
Note coverage is generated across every project/field, independently of which
fact the query requests. Policy and task-family labels are withheld from
prompts and controller features. Notes retain source-turn references, which
are legitimate observable freshness cues. The surface baseline gets those
cues too; synthetic shortcuts are a reason to reject a claimed probe gain.

| Split | Episodes | Rows | Purpose |
|---|---:|---:|---|
| Train | 300 | 900 | Fit controllers and feature standardization |
| Validation | 60 | 180 | Early stopping only |
| Calibration | 60 | 180 | Thresholds and baseline comparator selection |
| Test | 120 | 360 | Locked primary evaluation |
| OOD | 60 | 180 | Locked paraphrased-history/question diagnostic |

All note views of an episode stay together. Each split has disjoint
conversation identities, opaque project/service names, and archive hashes.
OOD varies wording, not task semantics; it is not a new-domain test. No
test/ood filtering on correctness, new hyperparameter selection, or seed
selection is allowed. A separate 12-episode/36-row smoke population never
enters training or test. Immutable configuration is
`experiments/context_gate/config.json`; dataset and source hashes are bound
to each run's manifest before capture starts.

## Retrieval and answer collection

All ordinary retrieval arms share deterministic two-round BM25, at most four
exact turns: two query hits, then two hits using project/service references
from those first hits. Ranking uses query and archive text only. Answer
options, gold answers, notes, and oracle annotations cannot affect ranking.
The budget is 768 retrieved tokens and 8,192 total prompt tokens. Overflow is
a failed input audit, never silent truncation. Retrieved turns are presented
chronologically and override stale notes.

For every row collect the frozen model's four-choice answer probabilities
under notes only, ordinary retrieved evidence, and oracle evidence. Oracle
evidence includes the relevant original/update turns and service registry
when needed; it supplies evidence, not an answer label. Oracle accuracy is a
diagnostic reference and need not mathematically bound every arm.

The primary answer rule is argmax over A/B/C/D logits. Capture full-vocabulary
first-token validity as a format diagnostic; forced choices do not measure
free-form generation. The explicit model controller similarly chooses R/S
from its two logits. Record its extra prompt/token/time overhead.

Capture the notes-only last-prompt hidden vector at fixed hidden-state index
27 (no layer search), answer probabilities, input lengths, and eight visible
features: note length, line count, query overlap, maximum/mean source-turn
coverage, answer confidence, margin, and entropy. No retrieved/oracle
activation can enter a controller feature.

## Labels and training

Let `c0` be correctness with notes and `c1` correctness after the *actual*
retriever. Label `u = c1 - c0` in {-1, 0, +1}. The positive class means
retrieval repairs an error; the negative class means retrieval harms a
previously correct answer. This explicitly differs from uncertainty or
divergence prediction. Oracle correctness does not define training labels.

Train three-class classifiers to estimate expected gain `P(u=+1)-P(u=-1)`:

- Surface MLP, eight observable features.
- Hidden linear controller, hidden vector plus the same surface features.
- **Primary hidden MLP**, hidden vector plus the same surface features.

MLPs have one 64-unit GELU layer. Train three fixed seeds (0,1,2) and use
their equally weighted probability ensemble; no best-seed picking. AdamW,
learning rate 0.001, weight decay 0.01, batch 128, at most 80 epochs, early
stopping after 10 validation-loss non-improvements. Fit scaling on train
only, with a variance floor. Save every seed's selected checkpoint, scaler,
history, initial/final loss, gradient norms, and weights' change magnitude.
Backbone parameter gradients must remain disabled.

Training requires at least 20 positive-gain and 20 nonpositive training rows;
otherwise save a label-starvation result and stop, without redesigning the
generator on test outcomes. Calibration requires at least 5 positive and 5
nonpositive rows. Report class counts without discarding neutral/harmful rows.

## Arms and locked decision rules

Notes-only, always ordinary retrieval, explicit R/S at 0.5, calibrated R/S,
calibrated answer-confidence, calibrated surface MLP, hidden linear, primary
hidden MLP, oracle evidence, and an unattainable oracle-action diagnostic
(`retrieve iff u>0`) are reported separately.

For calibrated controllers choose the threshold on calibration maximizing
`accuracy - 0.05 * retrieval_rate`; ties prefer fewer retrievals. Always/never
thresholds are eligible. The coefficient is a fixed retrieval penalty, **not
a dollar cost or equal-compute claim**. Choose the strongest non-hidden
comparator on the same calibration objective from notes-only, always-retrieve,
confidence, surface MLP, raw R/S, and calibrated R/S. Freeze it before test.

Report task accuracy, exact-fact and binding slices, benefit AUC (tie-correct,
undefined if one class), Brier score for benefit, harmful retrieval, missed
recoverable errors, retrieval frequency, and actual retrieved/input tokens.
Keep all-error rate, error-without-retrieval, and loss conditioned on
oracle-evidence correctness distinct. Report paired episode-cluster bootstrap
95% intervals (2,000 draws), keeping the three note views together.

Offline counterfactual arm accounting includes the notes prefill for hidden
and confidence gates, decision prefill for R/S, plus the full second prompt
after retrieval. Always-retrieve pays for one retrieved prompt only. No KV
reuse is assumed. Batch-amortized capture times are estimates, not deployed
latency. A preselected 12 test episodes (36 rows) also get sequential online
replay, invoking trained controllers and executing only their chosen branch;
record wall time and token counts for notes, always, raw R/S, confidence,
surface MLP, and hidden MLP, with randomized arm order per row and a warmup.
This replay is descriptive; it does not change thresholds or verdicts.

**Advance** by either of two pre-registered routes: (A) primary test accuracy
and utility both beat the frozen strongest baseline with paired CIs wholly
above zero, with no increase in accounted input tokens; or (B) accuracy is
noninferior (paired lower bound >= -0.02) while accounted input tokens fall
at least 10%, with the paired token-difference CI wholly below zero.
Otherwise report negative or inconclusive. OOD and sequential
latency remain mandatory descriptive results. AUC improvement alone cannot
advance the experiment. A stronger result than these criteria is welcome but
cannot relax them after outcomes are seen.

## Compute, artifacts, and stop rules

One Modal H100, pinned torch 2.7.1 / transformers 4.55.2 / safetensors 0.5.3,
with the cached immutable Qwen revision resolved before launch. Existing
`memsub-hf-cache` is reused. New outputs live exclusively under
`memsub-artifacts/context-gate-v1/<run-id>/` and local
`plans/260910-context-gate/`.

One combined smoke/capture/train/evaluate/replay call has a 7,200-second
timeout, zero configured retries, and a 6,600-second internal cutoff that
saves partial status. At current listed H100 pricing, two GPU-hours are
approximately $7.90, plus CPU/memory/build/storage charges; this is an
estimate, not billed spend. Source: https://modal.com/pricing (2026-09-10).
Capture commits every batch. A failure or timeout does not authorize an
unbounded new campaign; inspect completed artifacts before any bounded repair.

Smoke gates: valid single-token action letters, finite probabilities/states,
no prompt/retrieval overflow, frozen backbone, all three task families,
oracle-evidence accuracy >=0.60, at least three retrieval repairs, and a
projected total runtime below the remaining internal budget. Failure saves
the diagnostic and stops before full capture/training.

Required outputs: frozen manifest/config/source hashes, split audit,
fingerprint/revision and parameter count, smoke report, per-row captures,
per-seed controller checkpoints, frozen thresholds/comparator, test/ood
metrics with CIs, sequential replay, elapsed compute and status, and local
report with exact Modal app/function IDs. Checkpoint/replay reload equivalence
is checked before reporting a completed trained controller.

## Conditional next stage (not this launch)

Only an advancing result warrants natural histories, learned note writing,
free-form answers/tools, repeated resets, and longer evidence dependencies.
If oracle evidence works but retrieval does not, investigate selection.
If oracle evidence fails, investigate the task/reader. If surface or ordinary
retrieval matches the hidden controller, retain that simpler result. No
additional backbone/adapter training or serving integration is part of v1.
