# P2.5 Amendment PK — packed A100-80GB execution with checkpoint/resume (DRAFT v0.2)

Amends prereg v0.2 (`3bf8737`, sha 0ce61a09…; file unchanged). User 21549 chose "A: plan a packed P2.5".
Basis (dev evidence only, audited): option-A speed-up stage 1 (GPU parity 6/6 bitwise in checked scope, run 2
`c17cfcc`), registered L40S re-timing v2 (`4e22bae`: learned 9.44 / 14.88 s/update), packing test (`6686215`:
A100-80GB fixed-work speed-up P2 k=2 1.928×, P1 k=3 2.118×). None of these is a campaign price or a correctness
claim under packing; this amendment registers how the unchanged 18-cell experiment would be EXECUTED.

v0.2 adds codex 21551: universe binding, the P1→P2 two-worker schedule, worker failure isolation, exact
continuity checks, the resume consumer, the retry/stop policy, the proof through the real campaign consumer, and
"priced estimate / reservation" wording (no firm price).

## PK0 — Bound universe and preserved bytes
- Cells = exactly the 18 run ids `{tag}-n{N}-s{seed}` expanded from `configs/m4_sgm_p2p5_grid.json`
  (sha256 d1c045ea…; group p2p5-qwen3-0p6b-screen-v1); prereg v0.2 (sha 0ce61a09…), both profile evidence trees
  (v1 `2fda0d4`, v2 `4e22bae`), the dev/packing evidence and every ledger file keep their bytes. New outputs go
  only to new paths.

**Unchanged:** question, arms, 18 cells, model/readout/SGM settings, training recipe (1500 updates, batch 16, lr 3e-3,
P2C curriculum, seeds 0/1, full-gradient FP32 token-serial contract), populations, single readings run, readings
table, limits. Only execution topology, SKU, preemption handling and the ledger basis change.

## PK1 — SKU and packing topology
- SKU: Modal **A100-80GB**, preemptible (Modal offers no non-preemptible GPU functions), hard tuples 8 cores / 64 GiB,
  pinned image = the P2.5 dev/profile image (torch 2.7.1+cu126, transformers 4.55.2, weights @da87bfb6), TF32 off.
- One container ("slot") = **2 cells as 2 independent OS processes** (k = 2), each the unchanged `run_pilot` cell
  with its own seed, data stream, optimizer, artifact eval and output dir; no shared tensors, streams or state.
  Workers arm a checked parent-death signal (as in the packing test).
- 9 slots, fixed pairing (same arm, same N, seeds 0+1 — matched expected duration):
  learned N16 · learned N32 · single_cell N16 · single_cell N32 · random_fixed N16 · random_fixed N32 ·
  oracle N32 · memory_off N16 · memory_off N32. Pairing is fixed before any cell runs and never changed after.
- k = 3 is NOT used (three P2 learned-like processes exceed 80 GB by the summed peaks; untested).
- **Schedule across P1→P2:** both workers of a slot start together (same recipe, matched N), so they normally switch
  from phase 1 (filler 0, ~17 GB peak each) to phase 2 (filler 40, ~26.8 GB peak each, ≈ 57 GB summed observed in the
  packing test) at update 1000 at similar times; the slot is sized for both workers in phase 2 simultaneously (the
  worst case), so no phase alignment is required for memory. After a resume the two workers may be at different
  updates; that is allowed (memory bound unchanged).
- **Worker failure isolation:** each worker is its own process with its own output dir and checkpoint path. A worker
  that exits nonzero (error, OOM, non-finite) is NOT restarted and is reported "failed" with its log; its co-tenant
  continues to completion unaffected. Only a whole-container loss (preemption, host loss, container crash) triggers
  a restart (PK2), which resumes every not-yet-finished worker of that slot.

## PK2 — Checkpoint / resume (preemption)
- Each cell runs `run_pilot(..., train_checkpoint=<volume path>, checkpoint_every=C)` with **C = 50 updates**
  (implemented at `f676699`: atomic, PilotConfig-bound snapshot of adapters, head, AdamW, episode generator,
  CPU/CUDA RNG, logged telemetry and fixed-endpoint checkpoints; resumes at the start of the saved iteration).
- A preempted/crashed slot is rescheduled by the platform; each restart resumes BOTH cells from their own last
  checkpoint. Bounded: at most **R = 3 restarts per slot** (Modal Dict attempt ledger, atomic claims); a slot past R
  or past its lifetime deadline stops, and its cells are reported "lost" (no operator rescue, no reseeding).
- **Resume consumer = the campaign slot runner itself** (no separate tool): on container start it lists each
  assigned cell's state on the volume: `complete` (validated outputs present) → skip; `checkpoint present` →
  `run_pilot(..., train_checkpoint=…)` resumes; `nothing` → fresh start.
- **Exact continuity checks before any resume** (refuse and mark the cell "failed: continuity" otherwise): the
  checkpoint's PilotConfig equals the cell's grid-expanded config; the running memsub source sha, runner sha,
  pinned environment (python/torch/CUDA/transformers, TF32 off) and model-file hashes equal the slot's launch
  identity recorded at first start; checkpoint format `m4-sgm-train-resume-v1`; step < 1500 and a multiple of C.
  RNG/optimizer/data continuity is carried by the checkpoint itself (restored states, not reseeded).
- **Retry/stop policy:** container restarts only (≤ R = 3 per slot, atomic attempt claims; lifetime deadline per
  slot); no worker-level retry; no operator retry, rescue, reseeding, recipe/precision/batch change or re-pairing.
- Every resume is recorded (from-step, attempt, container id) in the cell manifest. A resumed cell is the SAME cell
  (same seed and recipe); it is excluded from headlines only if its resume validation fails (PK4).
- Final artifact eval runs after training completes in the same process; if a restart happens after training
  finished but before the artifact eval was saved, training is NOT repeated (final weights are checkpointed first).

## PK3 — Pre-campaign paid proof ("packed profile + GPU resume", needs its own small user approval, ≲ $2)
Seed 99 streams only; no accuracy; no registered/artifact/reserved populations. Runs THROUGH the real campaign slot
runner and resume consumer (proof-mode slot: a dev grid with the same code path, shortened step counts, seeds
99/100), on one A100-80GB:
1. **Packed timing for every slot type**: for each pairing shape {learned-like N16, learned-like N32 for learned /
   single_cell / random_fixed / oracle, memory_off N16, N32} × {phase 1, phase 2}: 2 warmup + 4 measured updates at
   k = 2 (closes the untested P1 k=2 and the unprofiled arms / N16 timings), plus one dev and one artifact-shaped eval
   batch per shape.
2. **GPU resume equivalence**: learned N32, 8 updates uninterrupted vs 4 + simulated container loss (the slot's
   worker processes killed after the step-4 checkpoint) + the slot runner's restart path resuming to 8 in fresh
   processes. Compare per-update loss, name-bound gradients and final
   weights; report bitwise status; PASS = within the run-2 checker tolerance (rtol 1e-5) and identical dev
   predictions. A second uninterrupted run measures run-to-run GPU determinism.
3. **Packed-vs-alone numerical equivalence**: the uninterrupted learned run alone vs the same run at k = 2 (paired
   with another seed-99+1 process): same checked-scope comparison.
Outcome: any FAIL in 2 or 3 stops the packed plan (report; options to the user). Otherwise 1 → ledger (PK5).

## PK4 — Validation additions per cell
- Resume records complete and consistent (each resume's from-step equals a saved checkpoint step; telemetry rows
  continuous; no duplicated or missing update ids).
- The slot co-tenant is recorded; pairing must equal PK1.
- Everything else exactly as the v0.2 per-cell validation (manifests, hashes, finite metrics, artifact seeds).

## PK5 — Priced estimate / reservation (computed only after PK3, before any cap request; not a price guarantee)
Per slot: life = max(cell walls) at the measured k = 2 timings × 1.4 + startup + R × (startup + lost work ≤ C
updates) allowance; charged at A100-80GB + 8 cores + 64 GiB list prices (2× CPU/RAM conservative basis as audited);
plus readings run, parity, image build, reaper/teardown, fixed margin. Two bases (estimate / planning reserve) as
before; topology, concurrency (9 slots in parallel) and queueing stated; assumptions explicit (preemption rate,
restart count, platform scheduling). The user cap is requested on the planning reserve. The packing-test numbers
and the $75–85 illustration are not a bound.

## Gates
1. Amendment PK clearance (codex) → implementation: packed slot runner + resume integration + CPU tests ($0).
2. Implementation audit (meaningful CPU tests: slot runner, resume consumer, continuity refusals, failure
   isolation, restart bound) → **separate user approval** for the PK3 proof (≲ $2) → run → proof/artifact audit.
3. PK3 PASS → schedule-bound priced estimate/reservation → **explicit user execution cap** → launch audit → 9 slots.
4. Readings exactly once after all cells validate (unchanged), on a single A100-80GB or the profile L40S (stated).
