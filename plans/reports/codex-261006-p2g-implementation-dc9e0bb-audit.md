# P2G implementation audit — dc9e0bb

Decision: **HOLD implementation/execution clearance pending fixes and completed parity evidence.**

Reviewed commit: `dc9e0bbdd29c353c45c48dbdd5428f5253660bf4`.
Prereg v0.2: `25fdbc5`, SHA256 `c2fa7394e9e621766af705743d46715b9584c83e161a90bdfd45d928908925c3`.
MCP coordination: #gravity 21307–21309 and 21312. No training, deployment, paid execution, or duplicate parity evaluation was started by this audit.

## Required fixes

1. **Reserve the registered fresh population until all six cells validate.**
   `modal-runners/modal-m4-sgm-p2g-nonpreemptible-spawn.py:177–182` passes the grid's `9_400_011` directly to each training call. Its `_train_cell` (line 97) passes this to `run_pilot`, whose final evaluation immediately uses that seed after each cell's training, with all five legacy interventions. This consumes the preregistered population before the six-cell validation gate and before the single registered three-intervention readings run. Separate the fixed training-artifact evaluation seed from the reserved readings seed, bind both in grid/provenance, and enforce the distinction in group validation. Preserve `9_400_011+s` exclusively for the registered post-validation readings population. There has been no actual training or consumption through this path yet.

2. **Reject malformed gate telemetry and contrast intervals before computing readings.**
   `scripts/sgm-p2g-decision-rules.py:120–134`: `auroc([float('nan')], [0.1])` never advances its tie loop because NaN compares unequal to itself. A one-second signal alarm after module import reproducibly interrupted the infinite loop. `gate_summary` computes AUROC before calling the finite-checking `suppression_ratio`, so this can hang instead of failing closed.
   `classify({'0': x, '1': x})` with `x={'diff': .1, 'lo': .1, 'hi': NaN, 'n': 256}` returns `reproducible gain`. Require finite, ordered intervals and the registered episode count in classifier/half checks.
   `gate_summary` also accepts only `L1h0` when the other three registered heads are absent, and accepts NaN in a projected filler array while reporting a finite pooled effective rho. Require exact four-head coverage, expected event populations, and finite projected/effective/applied beta arrays before summaries/AUROC; retain skipped versus applied-zero semantics. Add targeted malformed/boundary tests.

3. **Compare all executed observer identities before and after work.**
   `scripts/sgm-p2g-preflight.py:157` and `scripts/sgm-p2g-readings.py:163` compare only `memsub_source_sha256`. They calculate analysis/rules/index/grid hashes in `observer_identity` but do not reject changes to those fields. Compare the full executed source/input identity and persist the ending identity. A changed rules module, analysis script, grid, or inputs index must fail closed. Recheck bound input files before accepting completed evidence.

## Verified positives

- Independent command: `.venv/bin/pytest -q tests/test_sgm_p2g_gate_knob_and_decision_rules.py tests/test_sgm_p2g_observer_runner_and_preflight.py tests/test_sgm_p2g_readings_pipeline_smoke.py` — **32 passed in 78.76 s**. These are authorized CPU preflights; the smoke uses toy N4 checkpoints and a reduced population.
- All six reused checkpoint manifests/parameter files and all six parity references pass the committed inputs-index hash checks.
- All six reused cells also pass the existing full artifact validator against their own historical group grids, launch provenance, source hashes, and final evaluation seeds; old manifests/grids retain their original identities.
- The init knob follows all normal parameter draws; the default build and non-beta-bias parameters remain bitwise unchanged in the focused tests. Checkpoint loading loads saved parameters after initialization and retains the learned beta bias.
- Q1/Q2 formulas, ordered normal-path contrast labels, half-oracle pairing/null prerequisite, and memory-use reuse match prereg v0.2 on valid inputs.
- Exact six-cell IDs/timeouts match the prereg. Independently recomputed reservation using `3*(4*0.0000131 + 8*0.00000222)` USD/s:

| component | USD |
|---|---:|
| training timeouts | 8.88141408 |
| startup/teardown | 0.45463680 |
| bounded refused replay | 0.53040960 |
| CPU overuse margin | 0.66332112 |
| image | 0.30000000 |
| fixed margin | 1.50000000 |
| total | **12.32978160** |

- `P2G_CAP_USD=None`; ordinary `spawn()` planning refuses a missing approval. Proposed $13 remains unapproved. Existing top-up/group/claims/caps are unchanged.
- No registered training or fresh-seed evaluation was run by the auditor. Claude's existing authorized parity job continues; complete six-fixture equality is pending at this review point. Initial progress is not final parity clearance.

## Reviewed identities

- memsub: `5c3b5420152de933a04264604fdc1fb6312a24609b631ad9fd0c614755bde6a2`
- grid: `1b7ce09049137df80b979279bb3a6e7b9111e6586d70a60e5c2ea1556d551c8e`
- inputs index: `496d611fc525fc887e80d5119718f335b8fcde94bac6e459f44cfba1e7b5b7c7`
- P2G rules: `08d34ae29bd991237512eb1d3d3ef60b7e9426ae6ef2dc4b30cd10ade9752407`
- P2D rules: `88dda56b3bf6e78b57719ac034a8651f68ecb876d76dbd1d0831b7c0a87ca25d`
- common observer: `d3e155221544d3289a090021c633d201b85a9da5caeed6b84878a2b2e6d77686`
- preflight: `f666e4510e81d12a84369918570966037ec9267f03ebe1ee6f9a20813a1af76a`
- readings: `17f0b2f97f6f6d4737cbea41b8b37fae768c0f3a5bd828d97cd3e7c5eb92f025`

Next gate: review the scoped fixes, regression evidence, and all six completed parity results, then give an implementation decision. A separate user authorization for exactly six cells and the reviewed cap is still required before training.
