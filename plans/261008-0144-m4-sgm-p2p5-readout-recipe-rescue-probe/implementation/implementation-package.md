# Readout probe: frozen implementation package (for the codex implementation review, BEFORE any model smoke)

Authority:
- user 21748 asked for the probe
- proposal v0.2, 14e2b43 then gate-order fix at fbfebe0 (sha in SHA256SUMS)
- codex 21750 cleared local implementation
- codex 21752 set the reaper checks

**Implementation commit: fbfebe0.** No Modal build, deploy or spawn was done. No Qwen forward pass. Nothing charged.
Only a CPU construction of the model was done, for the registry check below.

## Files (all NEW; memsub tree 2eee4228… and every campaign file unchanged)
| file | role |
|---|---|
| configs/m4_sgm_p2p5_readout_probe_grid.json | P2.5 base with `readout = "taskhead"`; 2 cells: taskhead-learned-n32-s0/s1 |
| configs/m4_sgm_p2p5_readout_probe_registry.json | derived from the campaign learned registry; ONLY head.weight → [64, 512] |
| configs/m4_sgm_p2p5_readout_probe_output_schema.json | path-exact campaign learned schema + the None-vs-zero contract |
| scripts/sgm-p2p5-readout-probe-registry-and-schema-freeze.py | write-once derivation of the two files above |
| scripts/sgm-p2p5-readout-probe-output-validation.py | contract, path-exact schema check, `validate_probe_outputs`, `ProbeSlotSupervisor` |
| modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-logic.py | ALL probe bindings + pure lifecycle: admit, probe reaper decision, spawn guard, cell report, collect |
| modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py | NEW Modal entry point: GPU run_slot + in-app reaper; local plan/spawn/collect |
| scripts/sgm-p2p5-readout-probe-priced-ledger.py → ../probe-priced-ledger.json | full-envelope ledger |
| scripts/sgm-p2p5-readout-probe-reading.py | local CPU reading, write-once |
| scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py | bounded local Qwen smoke. NOT RUN; it waits for this review |
| tests/test_sgm_p2p5_readout_probe_validation_contract.py, …_runner_reaper_reading.py | 65 tests |

## Contract (codex 21750 #1/#2)
- Only `grad_norm` leaves may be null.
  - (a) REQUIRED null: L27/out_proj and L27/alpha.
  - (b) number-or-null: k_proj/value/beta at every layer.
  - (c) everything else is numeric.
  - `update_norm` is always numeric.
- Tiny-CPU evidence, from the tests:
  - (a) holds on every logged row and in train_last, with update_norm 0.0.
  - A FORCED read miss (every read offset by 1000) makes all k_proj/value/beta grads None, while q_proj and
    address_mlp stay numeric. The hit control is not None.
  - A residual-head control has no nulls.
  - The campaign extractor raises `inconsistent schemas` on a taskhead run; the probe schema accepts it and rejects
    the residual control.
  - The validator enforces the contract on every training row: 7 parametrised edits.
- **End to end:** the real ProbeSlotSupervisor with subprocess workers takes a taskhead cell to COMPLETE. A residual
  cell, given a matching registry, is FAILED with `output validation: probe schema: …`. A sentinel test confirms that
  COMPLETE never calls the campaign validator directly.
- **Registry:** the derived registry equals a REAL CPU build (`parameter_registry`) of both probe cells: 46 tensors,
  head [64, 512] (`registry-real-cpu-build-check.{py,json,exit.txt}`, EXIT 0). This was construction only: the
  frozen weights were loaded on CPU, with no forward pass.
- **Drift tests:** the frozen registry and schema equal their re-derivation. Their recorded grid, memsub, validator
  and campaign-schema hashes equal the current files.

## Runner and reaper (codex 21750 #3, 21752)
- **No import of the campaign module.** The bindings load first: app `memsub-m4-sgm-p2p5-readout-probe`, its own
  guard and admission Dicts, and volume subpath `m4-sgm/p2p5-readout-probe-v1/taskhead-learned-n32`.
- **Image inputs** (AST-tested): memsub, configs, the ledger, the validator, the slot logic and the lifetime logic.
- **Specs** (introspected): GPU A100-80GB, cpu (8, 8), memory 64 GiB, /artifacts volume; the reaper has 0.125 CPU and
  256 MB. Decorator arguments are AST-tested: max_containers 1, single_use_containers, retries MAX_STARTS−1, timeout
  86400; the reaper has a Period(120), timeout 110 (< period, so a hung stop is bounded), and retries 0.
- **Admission** refuses guards with an empty or missing app id, and deadlines that are NaN, inf, True, ≤ 0, missing
  or passed. At most 4 starts are claimed.
- **Probe reaper decision.** The shared `reap_decision` and `reap_and_stop` are NOT used; the shared helper is
  unchanged and its sha is pinned in a test.
  - The own id comes from a read-only lookup and is bound write-once. A later mismatch never stops.
  - A guard app id that is not this app never stops.
  - A valid deadline stops once it has passed.
  - Unspawned, interrupted or malformed bindings (NaN, inf, True, −1, a string, None) fall back to bounded
    abandonment ABANDON_S after the first tick, stopping with the bound self id.
  - A malformed first_tick never stops.
  - `stopper` is NEVER called with None. A stop error is recorded, `reaper_fired` is written, and the next tick
    retries.
- **Spawn guard:** before spawn, only first_tick and self_app_id (equal to the deployed id) may exist, and the spawn
  must happen at least 600 s before the abandonment stop.
- **Collect** follows the campaign order: provenance first, then a bound-id stop, verification and a durable status
  BEFORE any evidence. A failed fetch or export leaves every cell UNAVAILABLE. All of this is tested with fakes.

## Recovery and deadline (codex 21750 #4)
- Pre-checkpoint from-scratch replay is ALLOWED and declared (inherited supervisor). At most 4 admitted starts; a lost
  prefix is at most C+1 = 51 updates.
- One immutable deadline: the v6 learned-n32 reserve, 31,946.2 s. A cell that is not COMPLETE and valid makes the probe
  unavailable.
- **Ledger** (`probe-priced-ledger.json`):
  - (31,946.2 + 240) s × rate(2.0) = $38.23
  - reaper ticks ≈ $0.2, 2 images $0.34, margin $2
  - **cap request $40.75**
  - The 120 s period and 240 s stop tail are DECLARED assumptions.
  - Expected cost reference: $20.10, the actual P2.5 learned-n32 slot (prelim).

## Reading (proposal §6)
- Comparator rows are sha-bound. The seed-1 comparator is the post-hoc amended cell's output, and its sha equals the
  amendment spec's bound output (tested).
- Pairing is by (batch, episode, episode_hash, query); any mismatch means unavailable, never re-paired.
- C uses P2G.classify; B is the reused P2D.memory_use criterion on both seeds. Fixture tests cover gain+B, gain
  without B, not shown, a hash mismatch, FAILED, and an invalid COMPLETE.

## Smoke (§8.6, after this review)
- The script exists but has NOT been run.
- One cell: seed 7, batch 2 (the local RTX 3060 Laptop has 6 GB, and the batch-16 N32 profile ran out of memory),
  20 updates, C = 10.
- Its own namespace and populations: dev 777_001, final 777_100+7, train-split 777_200+7.
- A SIGKILL Watchdog of 3,600 s is armed before any model load, plus an outer `timeout`. No retry.
- A test checks the bounds and the order of those steps.

## Evidence
- `sgm-suite.txt` / `sgm-suite.exit.txt`: tests/test_sgm_*.py + hygiene, **557 passed, 2 skipped, EXIT 0** (at fbfebe0).
- `mutation-checks-readout-probe.{py,json,stdout.txt,exit.txt}`: 26 mutations + baseline, each in a private copy. The
  registry, schema and ledger are re-frozen inside the copy when the mutated file feeds them, and the AIMED test must
  fail. Result: **baseline 65 passed; 26/26 mutations caught by their aimed test; all_ok, EXIT 0.**
- `registry-real-cpu-build-check.*`, `SHA256SUMS-implementation-package.txt`.

## Next gates
1. Codex implementation review.
2. Bounded local smoke ($0) and its evidence.
3. The user's explicit cap ($40.75 requested).
4. chat_read, deploy, then spawn within 30 minutes of deploy (spawn is refused after 20 minutes), and collect.
5. Reading, then codex audit.

## Unresolved questions
- The slot-logic module (237 lines) and the runner (224 lines) exceed the 200-line guideline. They were kept
  whole so that all bindings live in one module.
