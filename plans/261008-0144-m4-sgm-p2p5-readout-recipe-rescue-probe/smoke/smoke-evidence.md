# Readout probe: bounded local smoke evidence (codex 21803 clearance: ONE local $0 smoke, no retry)

**Result: COMPLETE, EXIT_STATUS=0.** It was the single attempt; there was no retry and nothing was re-run. Cost $0: a
local RTX 3060 Laptop, with no Modal involved.

## Launch identity (`run-20261008T0511Z.launch-identity.json`)
- **argv (exact):** `timeout --signal=KILL 3600 .venv-gpu/bin/python scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py --out plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe/smoke/run-20261008T0511Z`
- **Source:**
  - cwd = repo root
  - git HEAD 30e2b3e (r2 PASS), with no tracked file dirty
  - memsub tree 2eee4228…
  - shas of the smoke script, validator, slot logic, grid, registry, schema, supervisor, worker and launch guard are
    recorded in the identity file
- **Environment:**
  - GNU timeout 9.4
  - .venv-gpu: Python 3.12.13, torch 2.7.1+cu126 (CUDA 12.6), transformers 4.55.2
  - GPU: NVIDIA GeForce RTX 3060 Laptop, driver 610.88, 6144 MiB, 0 MiB used before the launch
  - M4_SGM_QWEN3_0P6B_DIR / HF_HOME / CUDA_VISIBLE_DEVICES unset, so the default HF cache snapshot `da87bfb6…` is used
- **Preflight:** `verify_files` on that snapshot passed: config, generation_config and model.safetensors shas equal
  the pins. The smoke pilot has `device: cuda`.
- **Timestamps (`run-20261008T0511Z.exit.txt`):** identity written 05:11:47Z; start_utc 05:11:53Z; end_utc
  05:22:20Z; EXIT_STATUS=0. The script's wall_s was 620.5 and its metrics wall_seconds 612.2.
- **Process group:** observed 4 s after launch, timeout (pgid 2396473), the smoke python and the packed_slot_worker
  were all in pgid 2396473. The outer-bound check passed. After the exit no smoke, worker or watchdog process
  remained, and GPU memory was back to 0 MiB.

## Outcome (`run-20261008T0511Z/smoke-summary.json`, cell record `…/epoch-1/state.json`)
- **Cell:** `smoke-taskhead-learned-n32-s7`.
- **State:** state COMPLETE, recovery fresh, reason null, unacknowledged_epochs [].
- **Validation:** the COMPLETE transition passed the path-exact probe validator, run with the frozen registry and
  schema.
- **Updates:** 20 updates exactly. physical-updates.jsonl has 20 rows (updates 0–19); observed_updates 20; record
  steps 20.
- **Checkpoint chain:** g1 at step 10 (`gen-1-step10.pt`, ced82264…) and g2 at step 20 (`gen-2-step20.pt`, a908b525…).
  Both carry a `cuda_rng` state (1 device), i.e. `runtime.device.type == "cuda"`, so the training really ran on the
  GPU.
- **Output files** match the record's sha map, which the supervisor bound at COMPLETE: metrics 4a2282a9…, per-example
  results 9a7bb44d…, report 0e6454df…, telemetry 47eb6cfa…, run_manifest e5650364…, split_manifest bef28229…,
  trained_parameters e20b617e….
- **Logs:** worker.log is 0 bytes (the worker writes files, not stdout). console.txt holds the script's one-line JSON.
- **Final accuracies** are 0.0 on all six evaluation sets (4 smoke episodes each, after 20 updates at batch 2). This
  is NOT interpretable and is not a probe result. The smoke checks the contract, not learning.

## Observed None-vs-zero paths (real Qwen graph, GPU)
- **Logged training rows:** routing_telemetry has 2 training rows (steps 0 and 10) and 3 eval rows. metrics.train_last
  is step 10.
  - grad_norm null keys are exactly {L27/alpha, L27/out_proj}: contract (a), required null.
  - update_norm has no nulls. L27/out_proj and L27/alpha update_norm are 0.0.
  - L27 k_proj/value/beta grad_norm is numeric in both rows: step 0 ≈ 8.99 / 7.56 / 3.50, step 10 ≈ 9.7e-06 /
    3.4e-05 / 3.5e-06 (exact values in the telemetry file).
- **Optimizer step coverage** (`run-20261008T0511Z.optimizer-step-coverage.json`). AdamW skips a parameter whose grad
  is None, so the step count in its state shows on how many updates that parameter had a gradient. Parameters are
  named by the REAL CPU build order of the smoke pilot (adapters then head; construction only, no forward); all 44
  stepped slot shapes match that order in both checkpoints.
  - **Never stepped (0/20):** adapters.27.alpha_logit and adapters.27.out_proj.weight. This is contract (a).
  - **Step 10 checkpoint:** every other parameter stepped 10/10.
  - **Step 20 checkpoint:**
    - adapters.6.{k_proj.weight, v_proj.weight, beta_proj.weight, beta_proj.bias} stepped 12/20;
    - adapters.20.{same four} stepped 15/20;
    - all others stepped 20/20.
  - So during updates 11–20 the contract (b) None case (k_proj/value/beta on a read miss) really occurred on the real
    graph: 8 updates at L6 and 5 at L20. q_proj and address_mlp were never None.
  - The logged rows (steps 0 and 10) did not catch it, so the schema's `num_or_null` on those paths is exercised by
    real training, not only by the tiny-CPU forced read miss.
- **No schema change** follows from this observation. Contract (c), everything else numeric, held on every logged row.

## Files and hashes
- `SHA256SUMS-smoke.txt` covers every committed smoke file: the run dir minus binaries, the 4 sidecars, this file and
  the binaries list.
- **Binaries are NOT committed** (`SHA256SUMS-smoke-excluded-binaries-not-in-git.txt`): gen-1-step10.pt (24,878,805 B),
  gen-2-step20.pt (24,880,917 B), trained_parameters.safetensors (8,625,720 B). They are kept locally under the run
  dir.

## Next gates
1. Codex smoke-evidence clearance.
2. chat_read immediately before the paid step.
3. Deploy, then spawn (≤ 20 min after the first reaper tick), then collect until stopped_verified.
4. Reading.
5. Codex audit and billing.
Scope is unchanged: user 21755 conditional go, cap $40.75 (ledger $40.7401166468), 4 TOTAL admitted starts, immutable
31,946.2 s deadline.

## Unresolved questions
- None for the smoke itself.
- Note: the paid probe's pairing and reading do not depend on the smoke. The smoke's populations (777_xxx) are its own
  and are never reused.
