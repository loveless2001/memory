# Proposal v0.2 — does Qwen's value-token adapter input carry the preceding key? ($0 CPU information probe)

Status: DRAFT for codex review. Supersedes v0.1 (`proposal.md`, f634d1a, kept unchanged). Applies codex 22390
(`plans/reports/codex-261010-gravity-22386-information-probe-proposal-review/review.md`, sha 05e492fe…).
Authorizes nothing. Implementation audit and user go come before any numerical run.
Exploratory diagnostic. The closed Qwen-line negatives stay closed.

## Question
In the binding task the value token writes the binding. With `feature_shift=1`, its write projections see only its own adapter input x = z_value: the normalized PRE-attention hidden state passed to `project()`.
- Q1: on episodes and keys unseen by the probe fit, can z_value recover the preceding key at layers 6/13/20/27?
- Q2: does appending z_prevkey (the value token's half of the `feature_shift=2` input) improve recovery?

This probe tests information availability only. It does not test the shift2 bundle: shift2 also changes the query input, init draws and scaling (codex 22385 §2).

## Frozen condition (one arm; no MLP or memory-disabled arm)
- Runtime: P2.5 learned arm, seed-0 init. `pilot_config` is taken from `plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json` (sha256 4e89b95a…0bb0).
- Construction overrides, all frozen and recorded: `device="cpu"`; no optimizer is constructed; every forward runs under `torch.no_grad()`; nothing is trained; `feature_shift=1`. The model is frozen Qwen3-0.6B-Base rev da87bfb6, sha-checked by `pinned_pretrained_qwen3_backbone.py`.
- SGM is enabled at init, matching what the adapter sees at step 0. L13+ inputs include the earlier layers' init memory output. Its size is NOT measured or claimed small (alpha ≈ .018 alone does not show that).
- Tap: a wrapper on each adapter's `project(x)` records x for every ingest step. z_value = x at value-token positions; z_prevkey = x at the key position just before it.

## Data (existing generator, unchanged)
- `BindingTaskSpec(N=32, Q=4, filler=40)`. Source = 4 sinks + 32 (key, value) pairs + 40 filler = 108 tokens.
- Fit: split `train` (keys 10000–10800), data seed 9_700_011, 96 episodes = 3,072 value tokens.
- Final evaluation: split `heldout` (keys 10800–11000, disjoint ids; heldout filler), seed 9_700_021, 64 episodes = 2,048 value tokens.
- Episode CV inside the fit split reuses train key ids, so it calibrates generalization to NEW EPISODES. Only the final evaluation tests NEW KEYS.

## Probe (fixed)
- Target: the L2-normalized pinned input embedding of the preceding key, `embed_tokens[key_id]` (d=1024).
- Ridge: minimize Σ‖y − (W x̃ + b)‖² + λ‖W‖²_F. The sum-of-squares loss is not divided by n. The intercept b is unpenalized, so Y is centered. x̃ is X standardized with mean/std computed on the TRAIN rows of the current fit (std floor 1e-6). λ grid: {1e-2, 1e-1, 1, 10, 100, 1000}. Solved in closed form via SVD of x̃, float64.
- CV: fit episodes go into 4 folds by a fixed permutation (generator seed 9_700_041). Standardization and the solve are refitted inside each CV train fold. The CV metric is the mean over held-out folds of episode-retrieval top-1. Ties go to the larger λ. The final probe uses the chosen λ, with standardization and the solve refitted on all 96 fit episodes.
- Retrieval: score = cosine(prediction, each of the episode's 32 key embeddings). rank = #{other candidates with score ≥ true score}, so ties count against. top-1 ⇔ rank = 0. A zero-norm prediction counts as rank 31. Chance top-1 = 1/32.

## Feature sets per layer L ∈ {6, 13, 20, 27}
| Set | Features | Role |
|---|---|---|
| V | z_value | Q1 |
| V+K | [z_value, z_prevkey] | Q2 |
| K | z_prevkey | per-layer calibration (positive control) |
| E_v | value-token input embedding | context-free baseline |
| V-shuf | z_value with shuffled targets | null |

V-shuf semantics: each value token's target is replaced by the key of another binding in the same episode, using a fixed per-episode derangement (no fixed points). Fit episodes use generator seed 9_700_031; held-out episodes use 9_700_032. The probe is fit and evaluated on deranged targets.

## Intervals
Episode-level percentile bootstrap: 4,000 resamples of held-out episodes, generator seed 9_700_051. Every per-layer interval below is Bonferroni-adjusted over the 4 layers (two-sided 98.75%). The null/baseline family below uses its own adjustment.

## Readings (operational labels, fixed before running; precedence top to bottom)
1. **INVALID**: in the null/baseline family (E_v and V-shuf × 4 layers = 8 intervals, each two-sided 1 − .05/8 = 99.375%), any interval lies entirely above 1/32.
2. **NO CALIBRATED LAYER**: no layer is calibrated. A layer is calibrated iff K top-1 ≥ .50 and K's interval lower bound > .25. An uncalibrated layer gets no V reading. A failed K decoder is NOT taken as proof of broken capture.
3. **CARRIED**: at some calibrated layer, V top-1 ≥ .50 and V's interval lower bound > .10.
4. **PARTIAL**: at some calibrated layer, V's interval lower bound > .10, but not CARRIED.
5. **WEAK LINEAR RECOVERY UNDER THIS PROBE**: at every calibrated layer, V's interval upper bound ≤ .10. This does not exclude nonlinear information.
6. **INCONCLUSIVE**: otherwise (wide intervals).

Q2 is read per calibrated layer from the paired episode bootstrap Δ = top1(V+K) − top1(V), with the same resamples:
- APPEND HELPS: Δ interval lower bound > .10.
- NO MEASURABLE HELP: Δ interval within [−.05, .05].
- Otherwise inconclusive.
Secondary, descriptive only: Δ' = top1(V+K) − top1(K).

## Execution bounds
- Local CPU only, $0. `torch.set_num_threads(8)` on the 16-core box.
- Each invocation runs under `systemd-run --user --scope -p MemoryMax=4400M -p MemorySwapMax=1200M` and `timeout --signal=KILL <wall>`.
- No retry. Any exception, nonfinite feature or cap kill stops the run. Partial evidence is kept with its exit status.
- Work estimate: capture = 160 episodes × 108 steps = 17,280 token-serial steps. CV fits = 6 λ × 4 folds × 5 sets × 4 layers = 480 candidate evaluations, plus 20 final fits. The SVD is reused across λ per (set, layer, fold), so there are 80 CV SVDs and 20 final SVDs.
- Wall bound: profiled in smoke S1. The full-run wall = 2 × the profiled estimate (capture + fit), capped at 4 h. Above 4 h, stop and report instead of running.

## Smokes and checks (separate labels and seeds; not evidence for the readings)
- **C0 algorithm checks** (CPU unit tests, no model):
  - ridge recovers a planted linear map;
  - standardization is fit inside folds only (a leak mutant fails);
  - folds are assigned by episode;
  - the derangement has no fixed points;
  - retrieval tie and zero-norm rules;
  - Bonferroni levels;
  - label precedence on constructed metric tables.
- **S1 capture/fixed-λ smoke:** 2 fit + 2 eval episodes, seeds 9_799_011 / 9_799_021, λ = 1, no CV. It measures peak RSS, seconds per episode and fit seconds, and checks finiteness and the tap positions (the value/key indices match the generator's layout).
- **S2 full-path smoke:** 4 fit + 2 eval episodes, seeds 9_799_012 / 9_799_022, with the full 4-fold CV path. It exercises the code end to end; its numbers are not read.
- Then ONE full run, `probe-run-v1/`. It holds the features hash index, per-layer/per-set metrics JSON with the chosen λ and CV table, intervals, the label, the run log and the exit status. Feature tensors are not committed; their hashes are.

## Follow-ups (NOT authorized; each needs its own proposal, review and user go)
- WEAK or PARTIAL: a registered variant, either the full shift2 bundle or codex's role-separated address through ONE shared f (the query uses the current key embedding, the value write uses the preceding key embedding). It is gated first by a small fixed-set memory-dependent overfit.
- CARRIED: the shift lead is weakened, so look at extraction/optimization (a versioned contrastive address diagnostic, or the spec's answer-NLL + KL objective at registered targets).

## Unresolved questions
- None blocking. A nonlinear probe and a memory-disabled arm are deliberately excluded (codex 22390).
