# P2.5 Amendment PK — packed A100-80GB execution with durable checkpoint/resume (DRAFT v0.3)

Amends prereg v0.2 (`3bf8737`, sha 0ce61a09…; file unchanged). User 21549 chose "A: plan a packed P2.5".
History: v0.1 `5c7f74f`; v0.2 `2c99725` (codex 21551); **v0.3 = codex 21553 items 1–6** (cell state machine,
durable generations/ownership, terminal TRAINED/eval-only state, cross-container proof, frozen proof acceptance and
budget, restart lifetime) + one disclosed ledger correction (PK5: artifact-eval batch counts).
Basis (dev evidence, audited; not a price or correctness claim): stage-1 GPU parity (`c17cfcc`), registered L40S
re-timing v2 (`4e22bae`), packing test (`6686215`: A100-80GB fixed-work P2 k=2 1.928×, P1 k=3 2.118×).

**Unchanged:** question, arms, 18 cells, model/readout/SGM settings, training recipe (1500 updates, batch 16, lr 3e-3,
P2C curriculum, seeds 0/1, full-gradient FP32 token-serial contract), populations, single readings run, readings
table, limits. Only execution topology, SKU, preemption handling and the ledger basis change.

## PK0 — Bound universe and preserved bytes
Cells = exactly the 18 run ids `{tag}-n{N}-s{seed}` from `configs/m4_sgm_p2p5_grid.json` (sha256 d1c045ea…).
Prereg v0.2, profile evidence v1 (`2fda0d4`) and v2 (`4e22bae`), dev/packing evidence and every ledger file keep
their bytes. New outputs go only to new paths.

## PK1 — SKU, slots, schedule, isolation
- Modal **A100-80GB**, preemptible (no non-preemptible GPU functions exist), hard tuples 8 cores / 64 GiB, the pinned
  P2.5 image (torch 2.7.1+cu126, transformers 4.55.2, weights @da87bfb6), TF32 off, `torch.set_num_threads(2)` per
  worker.
- 9 fixed slots, each = 2 cells as 2 independent OS processes (same arm, same N, seeds 0+1): learned N16 · learned
  N32 · single_cell N16 · single_cell N32 · random_fixed N16 · random_fixed N32 · oracle N32 · memory_off N16 ·
  memory_off N32. Pairing is fixed now and never changed. k = 3 is not used.
- Schedule across P1→P2: the slot is sized for both workers in phase 2 at once (worst case; ≈ 57 GB summed in the
  packing test); phase alignment is not required, so post-resume misalignment is allowed.
- Isolation is a POLICY, not an immunity: each worker has its own process, output and checkpoint paths; a worker that
  exits nonzero becomes FAILED (PK2) while its co-tenant continues. A shared fault (GPU error, host loss, a co-tenant-
  induced OOM) can still end both; a container loss follows PK2's restart rule, a worker exit does not.

## PK2 — Durable cell state machine (volume `memsub-artifacts`, `m4-sgm/<group>/cells/<cell>/`)
States (in `state.json`, the cell's single durable pointer): **NEW** (no state file) → **STARTED** → **TRAINED** →
**COMPLETE**; terminal side states **FAILED** and **LOST**. Precedence on every start: COMPLETE, FAILED and LOST are
terminal and never re-run, whatever later container losses happen; TRAINED → eval-only consumer; STARTED → resume
from the acked generation, or (no acked generation yet) a declared from-scratch replay of ≤ C updates (the fresh
build is deterministic from the cell seed; the replay is recorded); NEW → fresh start.
- **Attempt directories:** every start of a cell uses a fresh `attempt-<a>/` (run_pilot's out_dir must not exist).
  Interrupted attempt directories are never deleted; they are marked `interrupted` in the pointer history.
- **Immutable checkpoint generations:** `ckpt/gen-<g>-step<s>.pt` (format `m4-sgm-train-resume-v1`), written once,
  sha256 recorded. Generation g is DURABLE only after the slot supervisor (the container's main process) has (i)
  verified the file hash, (ii) atomically replaced `state.json` to point at it, (iii) called `Volume.commit()` and
  (iv) written the worker's ack. The worker BLOCKS after each checkpoint until its ack, so no update runs past a
  non-durable checkpoint: lost work on any container loss is ≤ C updates (+ the in-flight update).
- **Cadence:** C = 50 updates for campaign cells (checkpoints at 50, 100, …, 1450) plus the **terminal generation
  at step = steps (1500)**, taken at the start of the final loop iteration (before the step-1500 dev eval), which
  moves the cell to TRAINED. Commit/serialization overhead is measured in PK3 and charged in PK5.
- **Eval-only consumer (TRAINED):** resumes from the terminal generation into a fresh attempt dir; the loop runs only
  the final iteration (dev eval at 1500; no optimizer update), then the run_pilot artifact eval and output writing.
  An interruption during the dev/artifact eval repeats only the evaluation (deterministic, no_grad, fixed seeds);
  the partial eval attempt is preserved and labelled. No optimizer update is ever repeated after TRAINED.
- **COMPLETE** is published only after the outputs (manifest, metrics, per-example rows, trained parameters) are
  hashed, validated (v0.2 per-cell validation + PK4), committed, and the pointer is updated and committed again.
- **FAILED:** a worker nonzero exit, a continuity refusal, or a validation failure. Never resumed.
- **LOST:** a cell not terminal when its slot has no admitted start left or its lifetime deadline passed (set by the
  next admission check, the collector or the reaper; never resumed).
- **Continuity checks before any resume / eval-only start** (refuse → FAILED "continuity"): checkpoint PilotConfig ==
  the cell's grid expansion; memsub source sha, slot-runner sha, pinned environment (python/torch/CUDA/transformers,
  TF32 off) and model-file hashes == the slot's first-start identity (stored in the pointer); format string; step ∈
  {C, 2C, …, steps}; checkpoint file sha == pointer sha. RNG/optimizer/data state come from the checkpoint.
- **Ownership:** one owner per cell = the current admitted attempt of its slot. Each admitted start atomically claims
  `slot-<k>-start-<n>` in a Modal Dict and writes it as `owner` into the pointers it touches; before every commit the
  supervisor re-reads the slot's current-attempt key and refuses (stops its workers, writes nothing) if it is no
  longer the owner (stale-writer refusal). Every start calls `Volume.reload()` before reading pointers.

## PK3 — Restart lifetime (R)
- R = 3 restarts ⇒ **at most 4 admitted starts per slot**. Admission = atomic Dict claim (survives host loss) +
  per-slot lifetime deadline set once at spawn. No admitted start is left past the deadline (admission refuses;
  the call completes). Function `retries` set so the platform restarts crashed containers into the admission check.
- A scheduled in-app reaper stops the WHOLE app past the global deadline (stop-first, app-id bound, as the accepted
  v1/v2 profile reaper); local collection stops + verifies by app id; both fail closed.
- No worker-level retry; no operator retry, rescue, reseeding, recipe/precision/batch change or re-pairing.

## PK4 — Per-cell validation additions
Pointer history consistent (generations strictly increasing, every resume's from-step == an acked generation step,
TRAINED only after the terminal generation, COMPLETE only after validated outputs); telemetry rows continuous with no
duplicated or missing update ids; co-tenant recorded and == PK1; exactly 1500 optimizer updates in total per cell
(update-id ledger across attempts). Everything else exactly as v0.2.

## PK5 — Proof before any campaign spend (needs its own user approval; budget = a computed reservation)
Runs the REAL slot runner + supervisor + resume consumer in proof mode on A100-80GB. Proof mode = a separate grid
`configs/m4_sgm_p2p5_packed_proof_grid.json` (new): steps 8, C = 2, curriculum ((0,0),(4,40)) (crosses phase at
step 4), eval_every 4, eval_batches 1, batch 16, N32 unless stated, seeds 99/100, proof populations dev 8_800_000,
artifact 8_800_011+s, train-split 8_800_021+s (never 4242 / 555_001 / 9_100_003 / 9_300_011 / 9_400_011 /
9_500_011 / 9_600_011 families), run_pilot artifact eval cut to 1 batch per intervention.
1. **Reference A, A′:** learned pair, uninterrupted, twice (separate containers) → run-to-run determinism control.
2. **Training interruption B:** same pair; fault injected after the step-4 ack (supervisor kills workers and exits
   the container nonzero) → a fresh container is admitted and consumes generation step 4 through the real runner →
   COMPLETE. Both container ids and generation hashes retained.
3. **Terminal/eval interruption C:** fault injected during the artifact eval after TRAINED → fresh container →
   eval-only consumer → COMPLETE; the update ledger shows exactly 8 updates; the partial eval attempt preserved.
4. **FAILED persistence D:** worker rank 1 injected to exit 3 at step 2 (FAILED), then a container fault after rank
   0's step-4 ack → fresh container: rank 1 stays FAILED (not started), rank 0 resumes → COMPLETE.
5. **Packed vs alone E:** seed-99 learned alone (k = 1 slot) vs its packed run in A.
6. **Packed timing T (all 9 slot types × phases 1, 2 = 18 configs):** k = 2, 2 warmup + 4 measured updates, one
   dev-shaped and one artifact-shaped eval batch per config, one repeat, threads 2; plus checkpoint+commit time.
   Any OOM/error/incomplete config ⇒ no ledger.
**Acceptance (frozen):** comparisons over per-update loss, name-bound gradients (full expected parameter name list
and shapes), final weights, dev/artifact predictions and accuracies; all values finite; bitwise status reported.
If A ≡ A′ bitwise, then B, C, D-rank-0 and E must be bitwise ≡ A on that scope; otherwise each value must satisfy
|x − x_A| ≤ max(1e-5 · max|x_A|, 1e-8) per tensor, with identical predictions. Training-telemetry numeric fields are
compared too (finite, |Δ| ≤ same rule). Any failure in 1–5 stops the packed plan (report + options); any T failure
blocks the ledger. No automatic scope reduction or retry. Budget: a complete charged reservation (every container
start, model loads, timing configs, commits, teardown, image build, margin, 2× CPU/RAM basis) is computed and
posted before the approval request; ≲ $2 is a target only.

## PK6 — Priced estimate / reservation (only after PK5 PASS; not a price guarantee)
Per slot: life = max(paired cell walls) at the PK5 k = 2 timings (+ measured checkpoint/commit overhead) × 1.4 +
startup + 3 restarts × (startup + ≤ C updates + checkpoint reload); artifact eval at the run_pilot batches **as
implemented: 5 interventions × 16 + 4 train-split = 84 batches (learned/random_fixed/oracle), 68 (single_cell,
coord_shuffle not applicable), 20 (memory_off)** — correcting the earlier 52/20 basis, which assumed 3 interventions;
all 9 slots (parallel), readings run, parity, image build, reaper, teardown, fixed margin; A100-80GB + 8 cores +
64 GiB list prices on the audited 2× CPU/RAM basis. Assumptions stated (preemption rate, restart count, queueing).
The user cap is requested on the planning reserve.

## Gates
1. Amendment PK clearance → implementation (slot runner, supervisor commit/ack protocol, state machine, eval-only
   consumer, train() terminal checkpoint, run_pilot proof-population parameters, proof grid, fault injection limited
   to proof mode) + meaningful CPU tests ($0) → implementation audit.
2. PK5 reservation posted → **separate user approval** → proof → proof/artifact audit.
3. PK5 PASS → PK6 schedule-bound estimate/reservation → **explicit user execution cap** → launch audit → 9 slots.
4. Readings exactly once after all cells validate (unchanged), on one A100-80GB (stated SKU).
