# P2.5 — frozen Qwen3-0.6B residual-readout screen (PREREG DRAFT v0.2)

v0.2 amends v0.1 (`59ca18d`) per codex audit `plans/reports/codex-261006-p2p5-prereg-v01-audit.md` (R1–R5).
User 21420 ("go P2.5 then") = draft + build. Registered follow-up from the spec review (Qwen3-0.6B pilot).
Spec anchors: §13, §15 baselines, §16 exploratory synthetic screen, §8 causal checks.
Evidence class: **frozen-qwen3-0.6b-base + residual-head, synthetic** — a synthetic classifier interface screen on a
pretrained residual stream. Not LM-answer, teacher-KL, P3, recovery, scaling, matched-storage or real-text evidence.

## Gates
1. Prereg clearance → implementation + CPU tests + the bounded profile (§Profile). No registered cell, no artifact or
   reserved seed, accuracy never read in the profile.
2. Profile outcome → frozen GPU SKU, environment, deadlines and a complete charged ledger. If the local GPU cannot fit
   the shape-faithful step (OOM), that is reported for review; a paid Modal profile needs its own user approval.
3. Registered cells (Modal or local) need the implementation audit AND a fresh scoped user cap approval.
4. Exactly one reserved-population readings run, after every cell validates and parity passes. No early stop,
   selection, tuning, automatic training retry, missing-seed headline or expansion. Stop conditions are reading
   gates after the fixed runs, never adaptive.

## Question
S(N), N ∈ {16, 32}, exploratory (two seeds): with every arm read through the same trained head on the final normalized
query residual of the frozen pretrained model, does learned SGM (P2C curriculum) beat **every** control — local-only,
fixed single bank and fixed/random addresses — by the screening margin, with memory use, at a load where the oracle
interface is established? Read per N.

## Model, memory and readout (R1, R5)
- Backbone `Qwen/Qwen3-0.6B-Base` revision `da87bfb608c14b7cf20ba1ce41287e8de496c0cd`; config and every weight-file
  hash bound; frozen (never in the optimizer); FP32 compute; TF32 disabled (CUDA matmul and cuDNN).
- SGM: layers (6, 13, 20, 27), 4 heads, d_k = d_v = 32, address_hidden 64, address_scale 8, local window 32 + 4 sinks,
  max_cells 2048 (realized deviation from the spec's 1024 default; resident bytes/access and trained parameters
  reported; no matched-storage claim), feature_shift 1. FP32, feature_shift 1, layers and the schedule are fixed
  settings, never rescue knobs.
- **Readout (R1):** every arm has the same 64-class linear head (identical init seed, objective, updates, data) on
  `final_norm(h)` at the query's last position — after the last selected layer's injection, its MLP and the final norm.
  Each query is answered from an independent snapshot of the post-source state.
- Arms: `learned`; `single_cell` (fixed single bank); `random_fixed` (fixed/random addresses); `memory_off` = genuine
  local-only: source re-ingested with SGM disabled (local window + sinks only), the same trained head; `oracle`
  (diagnostic; oracle addresses only in this arm).

## Training (R4: gradient contract)
Every trained arm: 1500 updates, batch 16, lr 3e-3, P2C curriculum `((0,0),(1000,40))`, seeds 0/1, filler writes ON,
evals at filler 40. Full-gradient token-serial ingestion; fresh episode state after every update; no `no_grad` on the
student path; no detached-source substitute; no activation checkpointing; no bf16, quantization, offload, chunking
or reduced global batch. An OOM never authorizes any of these; an alternative needs its own protocol.

## Cells
- Trained (16): `learned`, `single_cell`, `random_fixed`, `memory_off` × N16, N32 × s0, s1.
- Diagnostic (2): `oracle` N32 × s0, s1. Its N16 interface check is an explicitly labeled **transfer diagnostic**: the
  same two N32-trained oracle checkpoints evaluated on the N16 population (bound checkpoint + population; no inferred pass).

## Populations and evaluation (R3)
- Training stream seed = cell seed. Dev population 4242 (4 × 16 = 64 episodes) for in-run evals and telemetry.
  Artifact eval (in-run, Modal) 9_300_011+s. **Reserved readings population 9_600_011+s**: 16 batches × 16 = 256
  episodes × 4 queries; interventions none / bank_derange / read_offset for memory arms (3,072 rows), none only for
  `memory_off` (1,024 rows). Episode hashes must match across every paired corner (abort otherwise); full schema/
  completeness/finite checks; CPU sampling and canonical row hashing before any device movement.
- Order inside the one readings run: bindings + parity → **oracle interface at N32, then N16 (transfer)** →
  only for an N whose interface passed: the remaining arms on that N's reserved population. An N whose interface
  fails keeps its other reserved corners unevaluated (population untouched).

## Readings (per N; R2, R3)
- Interface(N): oracle accuracy ≥ 0.50 on both seeds (N32: trained load; N16: transfer diagnostic).
- For each control c ∈ {memory_off, single_cell, random_fixed}: label_c = `classify(learned − c)` (P2G ordered
  classifier; normal paired intervals as in P2 — an explicit screening deviation from the spec's proposed episode bootstrap).
- all_gain = every label_c is "reproducible gain" (conjunction; no selected control). The largest control mean is descriptive only.
- mem = P2D `memory_use(learned)` both seeds. Read-offset lo ≤ 0 → "read-address use not established" (not proof of dead routing).
- Ordered, total table:
  1. a bound input is missing/invalid/non-finite, or parity failed → "unavailable: <reason>" (no headline at any N).
  2. Interface(N) fails → "interface not established at N; screen not read".
  3. all_gain ∧ mem → "SCREEN PASS at N".
  4. all_gain ∧ ¬mem → "gain over every control without registered memory use".
  5. ¬all_gain → "screen not passed at N; per-control labels: {…}".
- Null/unavailable values are preserved, never coerced.
- Descriptive only: accuracies, 16-head gate telemetry (layers {6,13,20,27} × heads 0–3; telemetry undefined for
  `memory_off` is "unavailable", not a zero population), address telemetry, dev curves, resident bytes/access.
- Limits: exploratory 2 seeds (the reference pilot needs ≥3); N8 omitted by scope; synthetic classifier screen; recipe
  contrast, no mechanism; P2C's success does not validate this backbone/readout/geometry.

## Profile (R4; bounded, $0 local)
- Environment: a separate pinned CUDA venv (`.venv-gpu`: torch 2.7.1 CUDA build, transformers 4.55.2,
  safetensors 0.5.3); the CPU `.venv` and its pins stay untouched.
- Matrix (4 configs): {learned, memory_off} × N32 × {phase 1 (filler 0), phase 2 (filler 40)}; batch 16, the
  registered gradient contract; seed 99 training stream (never 0/1, never artifact/reserved populations); per config 2
  warmup + 8 measured complete forward/backward/optimizer updates (40 total ≤ 50), one dev-eval batch timing;
  wall bound 30 min total; first OOM or error stops the profile and is reported.
- Output: s/update per config, peak memory, eval s/batch; no accuracy. A 6 GB laptop result is not a 24 GB Modal
  measurement: any transfer assumption is stated in the ledger.

## Implementation checks (R5)
Bound P2.5 builder/readout/observer (no tiny defaults), 16-head telemetry set, arm-aware ingest. Tests: legacy
P2G/P2C parity fixtures and default-trainer fingerprints unchanged; disabled-SGM equivalence (pretrained, window ≥
length: runtime final hidden = HF forward within FP32 tolerance); backbone excluded from the optimizer;
output-path gradients reach every adapter incl. layer 27's output/mix; causal leakage rejection; CPU-vs-CUDA tolerance
on a tiny config (not bitwise); snapshot and replay checks. Start/end binding of model files, resolved
SGM/readout/compute config, analysis/runner/source/prereg/grid/index bytes, environment and checkpoints.

## Ledger
Provisional ≈ $30–60 for 18 GPU cells (memory_off cheaper). Frozen SKU, preemption policy, deadlines (profiled wall ×
1.4) and every charge (GPU + CPU/RAM, both phases, dev/artifact evals, builds/startup/shutdown, readings/parity,
fixed margin) come from the profile; the cap is requested only then.
