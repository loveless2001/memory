# M4-SGM P0–P2 implementation & validation report

Scope: P0–P2 only (M4-SGM.md). Research-only; no deployment default,
`HFModelRuntime`, certification harness or historical report was changed.

## Environment (resolved)

- Local: WSL2, Python 3.12.13, torch 2.7.1+cpu, transformers 4.55.2,
  safetensors 0.5.3 (`uv.lock` unchanged).
- Modal: CPU-only containers (4 vCPU, 8 GiB), `debian_slim` py3.12, torch
  2.7.1 CPU wheel, transformers 4.55.2. Artifacts on volume
  `memsub-artifacts` under `m4-sgm/<group>/<run-id>/`.
- No GPU was used. No pretrained-model (Qwen) run was made.

## Files

| File | Role |
|---|---|
| `memsub/sgm/config.py` | `SGMConfig`, versioned algorithm ids, `policy_id` hash |
| `memsub/sgm/interpolation.py` | quadratic B-spline 3×3 stencil; single-cell control |
| `memsub/sgm/sparse_cell_bank.py` | sparse banks; alias-free fork; fail-closed capacity; counters |
| `memsub/sgm/delta_memory.py` | functional read / delta update (FP32, non-finite fails closed) |
| `memsub/sgm/layer_adapter.py` | q/k/v/β projections, AddressMLP, output path, param groups |
| `memsub/sgm/session_state.py` | `SGMSessionState`, fork / detached snapshot, validity check |
| `memsub/sgm/backend.py` | transactional `ingest_source`, read-only `evaluate_query` |
| `memsub/runtime/sgm_model_runtime.py` | explicit Qwen3 layer loop, token-serial, full gradient |
| `memsub/sgm/synthetic_binding_task.py` | episodes, disjoint split families, overlap audit |
| `memsub/sgm/synthetic_pilot.py` | arms, tiny frozen backbone, training loop, telemetry |
| `memsub/sgm/synthetic_pilot_evaluation.py` | evaluation, interventions, bank/β telemetry |
| `memsub/sgm/synthetic_pilot_run.py` | one run → §21 artifact set |
| `scripts/sgm-synthetic-pilot.py` | local CLI |
| `memsub/sgm/p2_grid_readings.py` | fail-closed R1–R4 decision logic |
| `scripts/sgm-p2-grid-summary.py` | grid table + readings (registered N/steps from grid.json) |
| `modal-runners/modal-m4-sgm-synthetic-pilot-grid.py` | Modal CPU grid |
| `configs/m4_sgm_{tiny,reference,p2_grid}.json` | configs (reference = design only) |
| `memsub/errors.py` | + `CapacityError`, `NonFiniteStateError` |
| `tests/test_sgm_{core,runtime,pilot,grid_readings}.py` | 39 SGM tests |

## Design decisions worth auditing

- **Fork = shallow copy.** Cell and KV tensors are never mutated in place
  (writes replace dict entries; DynamicLayer concatenates; eviction
  index-selects), so a dict/cache shallow copy is an alias-free branch that
  keeps the autograd graph. `detached()` is the evaluation snapshot.
- **Transaction = one `ingest_source` call.** It runs on a fork and returns the
  new committed state; the caller's state is never touched. Capacity is
  checked per (layer, head) bank before any cell of that write changes.
- **Eviction boundary.** After each token step, keep the 4 sinks + the last
  `local_recent_tokens` non-sink positions; the current token additionally
  attends to itself during its step. Logical positions are never renumbered.
- **Write path.** Every source token writes (β = sigmoid > 0); zero-weight
  stencil slots never allocate. No decay or clipping.
- **AddressMLP** is shared by the read/write paths and by the heads of a
  layer. Its final layer is calibrated so that the initial address std equals
  `address_init_spread` cells. `random_fixed` detaches the AddressMLP input,
  so routing receives no gradient.
- **Registered deviation:** `feature_shift = 2` in the tiny grid (see M4-SGM.md).
- **Live-state identity:** `runtime_uuid:Σ param._version`. It is ephemeral (P2);
  durable fingerprinting of persisted state is P4.
- **Known limits:** in task-head arms the last selected layer's out_proj/α
  receives no gradient (reads feed the head directly). Multi-token queries
  transiently hold the whole prompt in KV before eviction (the pilot uses
  1-token queries).

## Tests actually executed

`pytest tests/test_sgm_core.py tests/test_sgm_runtime.py tests/test_sgm_pilot.py`
→ **39 passed** (local CPU; `tests/test_sgm_grid_readings.py` included). Full suite: 601 passed, 53 failed, 2 skipped.
The 53 failures are the pre-existing MergeCert hash drift (see M4-SGM.md P0);
no new failures.

Audit regressions (A2): identical episodes across all interventions;
`bank_derange` effective for `single_cell`; `coord_shuffle` N/A there; live
state rejected under a different-seed runtime and after an optimizer step;
the artifact set includes trained parameters and source hash.

Gradient evidence (SGM-03/15): with the loss on layer-3 reads only, all
q/k, value, β and AddressMLP groups of the layer-1 adapter receive nonzero
gradient through frozen layers 2–3; backbone grads stay `None`.
SGM-01: with the adapter disabled, the SGM loop matches HF prefill logits
(max |Δ| ≈ 2.5e-7, serial and block).

## Measured synthetic results

`p2-load-sweep-v2` is complete: 49 of 49 cells, all `stream_ok` after the
validation pass. Readings and the full table are in M4-SGM.md (§ "P2 result").
Summary:
- R1: oracle ≥ 0.999 at every N.
- R2: N* = 4.
- R3: MET at N = 4 and N = 8 (both seeds). NOT MET at N = 16 (seed-unstable), 32 and 64.
- R4: bank_derange gives chance for every memory arm.
- Spend: v2 $12.72; M4 total $14.07.

Development and stopped runs: `sanity-v1` (development; oracle 0.991, learned
and single_cell at chance after 300 steps) and `p2-load-sweep-v1` (stopped,
not evidence).

## Not implemented (by phase)

- P3: SGM-18 (teacher/student continuation alignment), any pretrained
  frozen-LM run, chunked ingest, detached-source-feature training, write
  gate, Qwen3-0.6B pilot, retrieval reference.
- P4: SGM-10/11 (persistence, redaction of live state), SGM-12/13/14
  (recovery), SGM-20 (certificates), provenance postings, safetensors
  manifests. P2 state is ephemeral and must not be used with real archive
  threads.
