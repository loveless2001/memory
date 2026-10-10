# Independent revision-3 review: e1632cb

**Status: not cleared for the paid proof approval request.** Two validation areas remain incomplete. All work in this review was CPU/read-only except for newly created reviewer-owned reports and scratch copies. No GPU, deployment, launch, stop, commit, or push action was performed.

## Verified evidence and resolved findings

- Independently reran the six affected test modules: **78 passed in 232.67 seconds**. Exact invocation and exit status are in `focused-pytest-status.json`; the real-worker proof fixture is retained under `pytest-tmp/proof0/`.
- Independently rebuilt the pinned Qwen proof parameter registry on CPU: **46 gradient names/shapes and 46 saved tensor names/shapes match**. Grid/source bindings match. See `registry-reconstruction.json`.
- Independently reconstructed the frozen normalized output schema from the real CPU fixture: it matches. This verifies reconstruction, not the completeness properties discussed below.
- Independent negative probes confirm the earlier jointly gutted metric dictionaries now fail, zeroed predecessor digests fail, and an empty timing eval/checkpoint worker list fails. The affected tests also cover consumed-input hashes, whole telemetry gutting, supervisor refusal of gutted final dictionaries, timing source/spec/SKU/missing-worker/commit-size errors, and mutated predecessor snapshots.
- Actual comparator/registry/schema/grid inputs pass `check_consumed_inputs()` using a separately reconstructed runner identity. Source is `99f0ea978c3c54c276c0b4cf568c40af95f78b1d01ac4eef656e5b1b579bfa47` at `e1632cbaa9625db5e99c2df8b2bde8b639d23e2b`, with a clean scoped tracked tree. Bindings are retained in `audit-bindings-and-checks.json`.
- Original preregistration, the accepted amendment and registered 18-cell grid hashes remain unchanged. Training math sources `synthetic_pilot.py` and `synthetic_pilot_run.py` are unchanged from de656de.
- Independent arithmetic still reproduces the **$8.560027** reservation under the existing serial lifetime/reaper/billing assumptions. It is not an unconditional platform cash ceiling. No paid approval is inferred.
- Read the retained **385-test** full-suite log and **11-case bitwise tiny-parity** log; these were not independently rerun for this revision. The independent current test count is 78.

## 1. Scientific output validation still loses required coverage

The complete independent reproducer and results are `independent-rejection-probes.py` and `.json`, with untouched baseline artifacts plus new mutation copies under `rejection-probes/`. The unmodified baseline passes. Running the script again requires a new scratch/report destination, since it refuses to reuse its directory.

**One layer's missing field is collapsed into another layer's field.** Remove `L1/q_proj` from every completed run's telemetry `grad_norm`, and from `metrics.train_last.grad_norm`, then rebind output hashes. Full acceptance still **PASSES**; the real supervisor also publishes **COMPLETE**. Normalization maps both `L1/q_proj` and `L3/q_proj` to `L{L}/q_proj`. Keeping the L3 field preserves the normalized key; the global `seen` set still contains L1 from its other fields. The same normalization logic is used for Qwen's four selected layers. A global union of layer IDs does not require each expected layer at each metric path.

Fix: expand the frozen layer-template keys at each dictionary/path to the actual selected layer IDs and compare the exact required keys there, or otherwise enforce complete layer coverage separately for each normalized suffix and parent dictionary. Do not collapse missing multiplicity into a surviving entry for another layer. Add joint partial-layer omission cases through both acceptance and supervisor publication.

**A row count and types do not prove prediction coverage.** Replace each completed run's prediction file with its first valid row repeated to the original row count, then rebind hashes. Full acceptance still **PASSES**, and the supervisor publishes **COMPLETE**. The checker compares equally incomplete row lists. The revision claims full row coverage, but the implementation checks only total length, key names and scalar types.

Fix: require exactly one row for each frozen `(intervention, batch, episode, query)` combination, with the declared domains; reject duplicates and missing/extra combinations. Validate row correctness and associated count/population consistency against the declared task/config. Add a joint-duplicate regression before pairwise comparison and before COMPLETE.

**Non-finite overflow is only caught downstream.** A JSON numeric literal `1e999` in an artifact accuracy field bypasses `parse_constant` and is classified as a number by the frozen schema. The supervisor publishes **COMPLETE**. Whole equivalence subsequently fails with a non-finite metric error; this is not a false acceptance of the whole proof. Fix recursive finiteness checking during shared output validation so invalid scientific output cannot become COMPLETE, and add a publication-level regression.

## 2. Timing validation still accepts invalid worker coverage and derived rate

These are explicitly **synthetic validator fixtures**, with synthetic A100/source labels and exit/commit stubs. They are not GPU or real Volume commit evidence. Both the full reproducer above and separately retained `timing-validator-probes/results.json` show the real `validate_timing()` accepting:

- duplicate rank 0 for both workers;
- a worker claiming `k=1` in a frozen k=2 config;
- six update rows whose IDs are all 0;
- `fixed_work_updates_per_s=1e9` despite unchanged worker timings/span.

The current loop checks worker-list length, seed set, arm/N/phase and update-list length. It does not validate rank-to-seed/k binding, exact update IDs, or recompute the derived timing/rate from raw records. This leaves the ledger gate able to accept internally inconsistent timing data.

Fix: reuse the already audited packing helper's `validate_workers()`/`summarize()` with the frozen T warmup=2/measured=4/seed99 settings, or implement equally complete checks. Require ranks `0..k-1`, seed-to-rank and k consistency, updates exactly `0..5`, finite positive chronological update durations/endpoints/barrier/means, and summary span/rate/means consistent with the raw records. Add negative cases through whole-proof acceptance as well as the validator.

The fixes are still free CPU preparation. Once these checks fail closed, independently review the resulting frozen revision before the separate proof reservation approval gate. Campaign launch remains subject to the GPU proof/artifact audit and a later campaign ledger/cap approval.
