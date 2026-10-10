# Independent Gate-3 audit — f8d8592

**NOT CLEARED.** Review target: `f8d85929e0c3fee166671a7f96be74c3134ff00d`, submitted in gravity 21614. The local tests and tiny parity pass, but the submitted package has reproducible reading-order, analysis-binding and collector defects. Resolve the findings below and submit a newly indexed package for focused re-audit before requesting the campaign cap.

This audit used local CPU execution, synthetic rows, private source variants and mocked Modal calls. It did not deploy, spawn, stop a remote app, run a registered population, edit shared implementation or proof artifacts, commit, or push. Reviewer artifacts are confined to this directory. Claude held the reviewed paths unchanged during the audit (21616); the tracked implementation diff against HEAD was empty at completion.

User 21613 authorizes continued preparation, not campaign execution. The completed $8.57 proof authorization is separate; its full hold remains pending settled app/build billing reconciliation. The approximately $2.924 app-only snapshot was not a settled total. No additional paid proof is needed to exercise the local fixes identified here.

## Verified evidence

| Check | Independent result |
|---|---|
| Package index | SHA256 `f7edc8ad48e9bf7582896bef9f17c2a7ff9ea7fa1070795a12922d79e82dfdef`; all 16 listed file hashes and the memsub tree hash match |
| SGM suite | `tests/test_sgm*.py`: **431 passed, 2 skipped**, 485.47 s |
| Artifact hygiene | `tests/test_experiment_artifact_hygiene.py`: **6 passed**, 1.40 s; this accounts for the difference from the submitted 437 total |
| Tiny CPU parity | Fresh run against exported reference `2fda0d4`: **11/11 cases bitwise**, maximum relative difference 0, reference import isolation passed, deliberate perturbation detected |
| Source bridge | `git diff d62602c f8d8592 -- memsub` changes only the manifest backbone description and its helper; tiny label preserved, numerical path unchanged |
| Preserved proof manifests | All 10 current manifest hashes still match the frozen proof index |
| Per-N interface gating | Both mixed outcomes tested with real decision rules and synthetic schema-valid rows; only the passing N's non-oracle populations are evaluated |
| v5 arithmetic | Fresh pure-arithmetic execution reproduces estimate **$114.46737111775417** and planning reserve **$256.37788715412125**; output differs from the published file only in the current git-head provenance |

Evidence: [probe program](probe-package.py), [probe results](independent-package-probes.json), [SGM log](independent-sgm-suite.log), [hygiene log](independent-hygiene-tests.log), [parity result](independent-tiny-parity/parity.json), [parity log](independent-tiny-parity.log), [recomputed ledger](independent-priced-estimate-v5.json).

The submitted slow tiny readings log is indexed and reports 2 passing tests in 1027.82 s. I did **not** independently rerun those two opt-in slow tests. Synthetic ordering probes are evidence about orchestration and decision-rule wiring, not Qwen results. The previously audited 8b2d9c1 process-group cleanup, structured evidence-before-stop and immutable candidate-deadline fixes remain closed; this review does not reopen the accepted GPU resume proof.

## Findings requiring changes

### R1 — Both oracle interfaces must precede other reserved readings

[Readings script lines 132–157](../../../scripts/sgm-p2p5-pk-campaign-readings.py#L132) evaluates oracle N32, then all N32 controls if it passes, and only then oracle N16. The independent call trace begins `oracle32/s0, oracle32/s1, learned32/s0, learned32/s1`. This contradicts the script's own documented order and [prereg lines 56–58](../../261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/prereg.md#L56): bindings/parity, oracle N32 then oracle N16 transfer, then remaining arms.

Split orchestration into two phases: evaluate and record both oracle interfaces in N32→N16 order; afterward evaluate other arms only at each passing N. Keep the same N32-trained oracle checkpoints for N16 transfer. **Independent per-N gating is correct:** a failure at one N does not suppress the other N's passing screen. Preserve that behavior, with call-order and both mixed-outcome checks.

### R2 — Decision semantics can change without changing the readings identity

[current_identity lines 113–115](../../../scripts/sgm-p2p5-pk-campaign-readings.py#L113) and the readings runner's identity check bind memsub, grid, registry, schema and the entry script only. The script dynamically imports the pretrained observer and P2.5/P2G/P2D decision/evaluation scripts; those bytes are outside the memsub hash and absent from both the runtime identity and package index.

In a private copy, changing `INTERFACE_MIN` from 0.50 to 0.99 changes the freshly imported decision rule while leaving `current_identity()` exactly unchanged. The start/end comparison therefore cannot detect a substantive analysis change. The source variant is confined to `frozen/scripts/sgm-p2p5-decision-rules.py`; the original is retained alongside it as `sgm-p2p5-decision-rules.original.py`. The shared dependency is unchanged.

Freeze and verify the complete consumed analysis dependency set and relevant runner bytes, and carry the prereg/grid/index binding through launch and final report as required by prereg R5. Preserve existing model/config/checkpoint checks. Bind a non-circular input/source manifest rather than making a file hash itself. Exercise dependency mutation before population access, plus a start/end mismatch. A clean checkout alone does not connect the deployed image to the reviewed dependency hashes.

### R3 — Null launch IDs reach a name-only stop in both collectors

[Slot collect lines 267–286](../../../modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py#L267) and [readings collect lines 199–218](../../../modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py#L199) check only that launch provenance parses. With `deployed_app_id: null`, both pass `None` to the real shared `stop_bound_app`. That helper intentionally skips its lookup/ID check for `None`, then stops by name.

The CPU probe exercised this actual helper with mocked Modal: both collectors called `stop_app(name)` with **zero identity lookups**. This violates their explicit promise to refuse any name-only stop and could target a later deployment using the same name.

Validate provenance before polling or side effects: a nonempty bound app ID, finite positive deadline and matching slot/group/expected identity. Fail closed on malformed or missing fields. Keep legacy abandonment behavior isolated from these collectors, or introduce a strict stop wrapper. Probe null/empty/missing IDs and a replaced live app; no name-only stop is acceptable on these collector paths.

### R4 — `stopped_verified` currently ignores tasks and containers

The actual verifier closures in [slot runner lines 320–321](../../../modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py#L320) and [readings runner line 246](../../../modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py#L246) accept `app_state in {stopped, none}`. Both returned true for a mocked real CLI row with `state: stopped, tasks: "7"`; neither queried containers. The result feeds the readings spawn precondition as `stopped_verified`.

Verify the bound app's stopped/unlisted state **and zero tasks/containers**, retaining raw query results and errors. Incomplete or failed verification stays `shutdown_unresolved`. A stop exception can be retained alongside a successful independent verification if the app is already fully shut down. A shared verifier can align controller and collectors; do not weaken the controller's existing zero-task check. Test nonzero tasks, remaining containers, CLI errors and replaced IDs.

### R5 — Malformed cell evidence aborts collection before its durable report

[cell_report lines 241–255](../../../modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py#L241) parses epoch names and acknowledged records outside its exception boundary. A malformed `state.json` raises `JSONDecodeError` rather than returning `INVALID`. Since the final collect report is written after the cell comprehension, one bad cell prevents the shutdown evidence and co-tenant report from being written.

Contain expected record/epoch/schema/I/O validation failures per cell, report `INVALID` with the cause, and retain the other cell and shutdown evidence. Do not rewrite authoritative state or turn an invalid record into a valid completion. Also make collection failures explicit: the fetched command return code is currently recorded but not used to prevent validation of pre-existing local evidence after a failed fetch. A failed fetch must remain unavailable or be explicitly identified as an older retained snapshot.

### R6 — Reconcile the final readings work with the priced envelope

The v5 totals are arithmetically reproducible, but its workload and assumptions predate the completed reader:

- Prereg populations specify three interventions for memory arms (lines 52–54); pricing charges three for oracle, while the reader evaluates oracle with `("none",)` only. Reconcile the intended frozen oracle matrix explicitly with the protocol and index. Do not silently change the frozen protocol or expand paid readings.
- With both interfaces passing, the reader builds/loads a checkpoint **38 times**: 18 parity cells plus 20 reserved populations. The explicit `READ_LOAD_S` line charges 20 populations; parity is a blanket 10% of reserved evaluation time. Show that this allowance covers all parity builds/loads/evaluations, or itemize those operations.
- `reserved_rows` calls four-dev-batch gate telemetry for each of 16 memory-arm populations, adding **64 dev batches**. Account for this explicitly or demonstrate coverage by a stated allowance. Avoid asserting that the excess oracle batch allowance automatically cancels unrelated costs.
- State the controller build/setup and CPU/RAM billing assumptions. The image line covers 10 GPU apps and the controller line uses one requested 0.125 CPU/0.25 GiB basis. Clarify any shared/cached build or billing-floor assumptions rather than presenting the scalar as an unconditional maximum.
- Correct the stale envelope description claiming an in-app reaper, a pending campaign runner and up to four starts for every app. The submitted architecture uses one control-plane reaper and one admitted readings start.

This is a workload reconciliation finding, **not evidence that the existing total necessarily underprices the run**. Preserve v5 bytes and issue a newly versioned, hash-bound model if revised. Retain explicit conditionality: 50 MB/s checkpoint I/O, 30 s load allowances, 1.4 factor, three slot restarts, 2× CPU/RAM basis and nominal shutdown latency are planning assumptions. **$256.38 is a conditional reserve, not a hard platform cash ceiling or unconditional worst case.**

Modal's current [pricing](https://modal.com/pricing) agrees with the GPU/CPU/RAM list rates used; billing can exceed requested CPU/RAM when actual usage is larger. Its [timeouts documentation](https://modal.com/docs/guide/timeouts) also distinguishes startup from execution and allows some execution overrun. These facts support conditional wording; they do not supply missing workload bounds. Its [volume documentation](https://modal.com/docs/guide/volumes) describes background and exit commits, so files written before interruption should be preserved when available, without claiming every uncommitted partial row is guaranteed durable.

## Re-audit boundary

Claude can implement the free preparation fixes and re-index the concrete package under existing authorization. Use focused regression checks for the findings and relevant existing tests; no new paid experiment is required to fix or demonstrate these issues. Keep registered grid/prereg/amendment and the accepted proof artifacts immutable. Submit the final source/analysis binding, execution supplement, collector evidence and reconciled price model together. Campaign cap approval and any paid deployment/spawn remain later gates.
