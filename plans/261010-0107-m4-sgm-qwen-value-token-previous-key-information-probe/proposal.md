# Proposal v0.1 — does Qwen's value-token adapter input carry the preceding key? ($0 CPU information probe)

Status: DRAFT for codex review. Authorizes nothing; execution needs codex clearance + user go.
Origin: user 22381 ("see if we got some other ideas"); claude 22382 lead #1; codex review 22385
(`plans/reports/codex-261010-gravity-22382-feature-shift-spec-review/review.md`, sha 6f06f166…).
Exploratory diagnostic. The closed Qwen-line negatives stay closed. This is not a rescue claim.

## Question
In the binding task the value token writes the binding. With `feature_shift=1`, its write projections see only its own normalized PRE-attention adapter input z_value. Two questions:
- Q1: on episodes and keys the probe never saw, can z_value recover the identity of the preceding key at each SGM layer (6/13/20/27)?
- Q2: does appending z_prevkey (the value token's half of the `feature_shift=2` input) improve recovery?

This probe tests information availability only. It does not test the full shift2 bundle: shift2 also changes the query input to [z_key, z_last-source-token], plus init draws and scaling (codex 22385 §2).

## Data (existing generator, no changes)
- `BindingTaskSpec(N=32, Q=4, filler=40)`; source = 4 sinks + 32 (key, value) pairs + 40 filler = 108 tokens.
- Fit split: `train` keys 10000–10800, data seed 9_700_011, 96 episodes = 3,072 value tokens.
- Evaluation split: `heldout` keys 10800–11000 (disjoint key ids) and heldout filler, seed 9_700_021, 64 episodes = 2,048 value tokens.
- Features come from the exact adapter input x passed to `project()` during `ingest`. The runtime is the P2.5 learned-arm config at seed-0 init: pilot_config from `plans/261009-0030-…/inputs/probe-taskhead-learned-n32-s0-run_manifest.json`, `feature_shift=1`, frozen Qwen3-0.6B-Base rev da87bfb6, run on `mvp` (no fill code needed). Captured under `torch.no_grad()`, with no optimizer and no training. L6 z is unaffected by any memory output. L13+ z includes the tiny init memory output of earlier layers (alpha ≈ .018), which is recorded.

## Targets and metric
- Common target: the pinned input embedding of the preceding key token (`embed_tokens[key_id]`, L2-normalized).
- The probe is ridge regression X → target. λ is picked by 4-fold CV over fit EPISODES from the grid {1e-2, 1e-1, 1, 10, 100, 1000}. X is standardized with fit-split statistics.
- Readout = candidate retrieval within the episode: the rank of the true key's embedding among that episode's 32 key embeddings by cosine to the prediction. Report top-1 (chance 1/32) and mean rank (chance 15.5), with 95% bootstrap CIs over held-out episodes (2,000 resamples).

## Feature sets per layer L ∈ {6, 13, 20, 27}
| Set | Features | Role |
|---|---|---|
| V | z_value | Q1 (the shift=1 write input) |
| V+K | [z_value, z_prevkey] | Q2 (the value token's shift=2 input) |
| K | z_prevkey | positive control (the key token's own state) |
| E_v | value-token input embedding | context-free value-only baseline (should be chance) |
| V-shuf | z_value with targets permuted among the episode's keys | shuffled-pair null (pipeline check; should be chance) |

## Descriptive readings (operational labels, not significance tests; fixed before running)
- **carried**: some layer has V held-out top-1 ≥ .50 with CI lower bound > .10. The information is linearly present, so shift=1 is not starved by this probe and the lead is weakened.
- **not linearly carried**: V's CI includes 1/32 at every layer while K ≥ .50 at the same layers. This is consistent with lead #1. Caveat: weak linear decoding does not prove there is no nonlinear information (codex §3).
- **partial**: anything else.
- **invalid**: E_v or V-shuf CI excludes chance, or K < .50 at every layer (the pipeline or positive control failed).

## Compute and safety
- Local CPU only, $0.
- One process per run under `systemd-run --user --scope -p MemoryMax=4400M -p MemorySwapMax=1200M` (lesson from the r1 OOM). Smoke first with 2 fit + 2 eval episodes; measure peak RSS and seconds per episode.
- Expected cost: forward only, no graph, ~108 token-serial steps per episode. This is an estimate to be measured in the smoke, not a bound.
- Outputs: `probe-run-v1/` (features hash index, per-layer/per-set metrics JSON, run log, exit status). Large feature tensors are not committed.

## Follow-ups (NOT authorized; each needs its own proposal, review and user go)
- If "not linearly carried" or "partial": a registered variant, either the full shift2 bundle, or codex's role-separated address through ONE shared f (the query uses the current key embedding, the value write uses the preceding key embedding). It is gated first by a small fixed-set memory-dependent overfit, then a capped screen.
- If "carried": the shift lead is weakened, so look elsewhere: extraction/optimization (contrastive address diagnostic, versioned), or the spec's answer-NLL + KL objective at registered targets.

## Unresolved questions
- Should a small nonlinear probe (1-hidden-layer MLP) be added as a secondary readout? It costs more and has more choices.
- Is the init runtime right, or should features come from a memory-disabled forward (`enabled=False`), so that L13+ z is the pure backbone? Default: init runtime, i.e. what the adapter actually sees at step 0.
