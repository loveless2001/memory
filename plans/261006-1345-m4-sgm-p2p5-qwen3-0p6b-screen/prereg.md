# P2.5 — frozen Qwen3-0.6B synthetic screen (PREREG DRAFT v0.1)

Status: DRAFT for codex audit. User 21420 ("go P2.5 then") = draft + build. Registered follow-up from the spec review
(M4-SGM.md "Agreed amendments" 1: Qwen3-0.6B pilot). Base: `a6afc29` (P2C closed).
Spec anchors: §13 (P0–P2 local work → reference pilot), §15 baselines, §16 exploratory synthetic screen, §8 causal checks.
Evidence class: **frozen-qwen3-0.6b-base + taskhead, synthetic** — first pretrained-backbone result; still no P3,
recovery, pretrained-LM-readout, scaling or real-text claim.

## Gates
1. Prereg clearance → implementation + CPU tests + a **local GPU profile** (RTX 3060 laptop, $0; ≤ 50 updates per
   profiled config, no registered cell, no reserved-seed use; timing/memory only, accuracy not read).
2. The priced Modal GPU ledger + cap come from that profile; the registered cells need the implementation audit AND
   a fresh scoped user cap approval (local training needs the same approval).
3. One reserved-seed readings run only after every cell validates and parity passes. No early stop, selection,
   tuning, automatic retry, missing-seed headline or expansion; any failure stops the readings.

## Question
S(N), N ∈ {16, 32}: on a frozen pretrained backbone, does learned SGM (trained with the P2C curriculum) pass the spec
§16 screening rule — ≥ 5 pp exact-answer gain over the stronger of the local-only and fixed/random-address controls,
paired interval excluding 0, both seeds — with memory use? Read per N.

## Fixed protocol
- Backbone: `Qwen/Qwen3-0.6B-Base` revision `da87bfb608c14b7cf20ba1ce41287e8de496c0cd` (28 layers, hidden 1024),
  frozen, fp32 compute, weights hash-bound. Same synthetic binding task and token-id ranges as P2 (all inside the
  151,936 vocab), filler 40, 4 queries, task-head readout over memory reads.
- SGM (spec-proportional to the 4B default [8,17,26,35]/36): layers (6, 13, 20, 27), 4 heads, d_k = d_v = 32,
  address_hidden 64, address_scale 8, local window 32 + 4 sinks (every binding is outside local KV at query time),
  max_cells 2048, **feature_shift 1** (spec default; the tiny-backbone shift deviation is not carried over).
- Training (every trained arm identical): 1500 updates, batch 16, lr 3e-3, P2C curriculum
  `filler_len_schedule ((0,0),(1000,40))`, seeds 0/1, fixed endpoint, filler writes ON, evals at filler 40, E=on.
- Seeds: artifact eval 9_300_011+s; reserved readings population **9_600_011+s** (P2G/P2C consumed 9_400/9_500).
- Rules reused unchanged: P2D `paired`/`memory_use`, P2G `classify` (ordered), interval/telemetry fail-closed checks.

## Cells (14 trained + eval-only)
- Trained, N16 and N32 × s0/s1: `learned`, `single_cell` (fixed single bank), `random_fixed` (fixed/random address).
- Diagnostic, N32 × s0/s1: `oracle` (interface check; never a headline).
- Eval-only: `memory_off` (local-only; with the task-head readout it is chance by construction — reported, and kept in
  the "stronger control" set so the rule is applied as written).

## Readings (per N)
- Prerequisite I (interface): oracle N32 heldout ≥ 0.5 both seeds. If it fails → "interface not established on the
  pretrained backbone; screen not read" (stop condition).
- Stronger control per seed = the control with the higher reserved-population accuracy among {memory_off, single_cell,
  random_fixed}; contrast = paired(learned − that control), per seed (choosing the stronger control only makes the rule harder).
- screen = classify(contrast); mem = memory_use(learned) both seeds; dead routing = read_offset contrast lo ≤ 0 for a seed.
- Table (total): screen gain ∧ mem → "SCREEN PASS at N"; gain ∧ ¬mem → "gain without registered memory use";
  ¬gain → "screen not passed; learned−control is <label>". Dead routing / unused memory are reported as the spec's P3
  stop conditions.
- Descriptive: all arm accuracies, gate telemetry, address telemetry, dev curves; no paired comparison with tiny-backbone cohorts.
- Limits: synthetic task over real token embeddings, task-head readout (not LM answer NLL/KL); 2 seeds (spec wants
  ≥3 for the reference pilot); recipe/backbone contrast, no mechanism.

## Engineering (implementation scope)
1. Device plumbing: adapters, banks, head and batches follow the backbone device; CPU behaviour bitwise unchanged
   (P2G/P2C parity fixtures + default-trainer fingerprints re-run).
2. Pinned pretrained backbone builder (local HF cache / image-baked weights, revision + file hashes bound).
3. GPU Modal runner (non-preemptible, deploy + spawn, same claims/watchdog/collector/stop-verify contract), GPU pricing
   in the ledger, weights baked into the image (no network at run time).
4. P2.5 readings reusing the common observer and rules.

## Ledger (provisional; replaced by the profile-based dry-run)
Rough: 14 trained cells × ~1.5–3 h on a 24 GB GPU (A10G/L4 class) → **≈ $25–50** expected; cap proposal after the
local profile. Guard policy: per-cell watchdog from profiled wall × 1.4, existing startup/replay/margin structure.

## Unresolved (for the auditor)
- 2 seeds vs the spec's 3 (screen, not the reference pilot); N8 omitted (works on tiny); oracle only at N32.
- fp32 vs bf16 backbone compute; GPU type (A10G vs L4) pending the profile.
