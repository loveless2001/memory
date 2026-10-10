# Independent review of Amendment PK v0.3 (392b6bb)

Reviewed 2026-10-06. This is a source/protocol review and pure CPU arithmetic, not a GPU proof or campaign authorization.

Reviewed amendment SHA256: `3265c78e64bdb7f6cd042153705d210a9726d6154c5d0822e87b22bb878a8e9d`.
Original prereg SHA256 remains `0ce61a096b0c7150e00f0a604ed85cb8f9694584cb70790d43d5fb3d010c2002`;
registered grid remains `d1c045eadfb562829cab72f58ba6b293f573f2e853629d3a3dd324b740a13073`.
The grid still expands to 18 cells in nine fixed arm/N seed pairs.

Most of review 21553 is incorporated: explicit terminal-state precedence, fresh attempts, checkpoint/commit acknowledgements,
terminal TRAINED/eval-only recovery, proof through a fresh-container consumer, all nine timing pairs, bounded admission counts,
and separate paid-proof/campaign gates. The two-worker topology remains a reasonable direction.
The current text needs the following focused corrections before amendment clearance.

1. **Fence writes and distinguish admission from missing files (lines 33–44, 61–64).** Re-reading an owner key before
   writing a shared mutable `state.json` is a check-then-write race. Counterexample: owner A checks the key; B is admitted
   and publishes its pointer; A then commits its already-prepared replacement. A's stale pointer can win. This is a
   logical interleaving, not an observed remote failure. Modal documents last-write-wins file conflicts and no distributed
   file locks on Volumes: [official Volume guide](https://modal.com/docs/guide/volumes).
   Use an actually fenced authority, immutable epoch-scoped state selected through durable admission authority, or a
   documented serialized handoff that confirms the previous writer cannot continue. Add a CPU test that changes owners
   between validation and publication, not just before validation. A previous durable admission with a missing state file
   must not silently classify as NEW. Acknowledge initial STARTED/identity before training, and declare the missing-state
   recovery/refusal policy. In proof D, persist and acknowledge FAILED before deliberately destroying the container.

2. **Separate logical updates from replayed physical work (lines 36–44, 75–78).** Exactly 1500 physical optimizer
   updates across all attempts conflicts with permitted rollback/replay. If step 50 is durable and the container is lost
   after physically executing 51–75, a successful resume has 1500 authoritative logical updates but 1525 physical
   executions. Validate a canonical checkpoint chain with logical update ids 0…1499 exactly once. Keep attempt-local
   physical/replayed update records, mark discarded work explicitly, and charge it. Terminal eval-only recovery adds
   zero optimizer updates. Apply the same distinction to the eight-step proof.

3. **Freeze a usable numerical comparison scope (lines 98–103).** Training telemetry includes `sec_per_step`
   (`memsub/sgm/synthetic_pilot.py:223`); output metrics/manifests also contain `wall_seconds`
   (`memsub/sgm/synthetic_pilot_run.py:140`). These vary with scheduling and cannot be required to match numerically
   or bitwise with model values. Declare an explicit schema separating numerical model/training/evaluation fields from
   clocks/provenance. Retain clocks with finite/nonnegative and budget checks. Match full key/name sets, shapes and
   expected rows; explicitly preserve legitimate N/A fields such as `aux_address_mse=None` and
   `single_cell/coord_shuffle=None` (evaluation returns before running that intervention). No missing-key or NaN pass.
   A′ must itself pass the declared tolerance against A before the non-bitwise branch is available; instability of the
   control must stop the proof. Then freeze bitwise or declared tolerance for B/C/D/E on that scientific scope.

4. **Price interruption during evaluation as well as training (lines 108–114).** The restart term currently contains
   startup + C updates + checkpoint reload. TRAINED can instead be interrupted near the end of dev/artifact evaluation,
   so a restart can repeat that evaluation. Include its worst allowed repeat, checkpoint serialization/commit/reload and
   the C-plus-in-flight allowance where applicable, within the four-start/per-slot deadline and whole-app stop allowance.
   Choose and state a conservative maximum or sum for training versus evaluation restart overhead before producing a cap.
   Freeze the exact T/proof configurations and evaluation multiplicities in the implementation package before paid approval;
   one final batch per intervention still has the current two-batch train-split minimum unless explicitly overridden.

## Evaluation-count correction

The disclosure in PK6 is correct. `INTERVENTIONS` has five entries; `run_pilot` uses all five for memory arms and `none`
for memory_off. `single_cell/coord_shuffle` returns immediately. With final_batches=16, the train-split minimum is four.
Thus actual final artifact evaluation is 84 batches for learned/random_fixed/oracle, 68 for single_cell, and 20 for
memory_off. The separate registered readings remain three interventions. My earlier acceptance of 52/20 as the actual
default was incorrect. The saved 52/20 ledger remains a historical assumption-specific arithmetic result.

The new independent supplement reproduces every unrounded historical L40S aggregate before changing those counts:

| Historical L40S v2 model | Old 52/20 assumption | Corrected 84/68/20 | Increase |
| --- | ---: | ---: | ---: |
| Estimate | $158.37643063514034 | $160.4333670856408 | $2.056936450500473 |
| Planning reserve (historical JSON key `bound`) | $270.5192411888874 | $273.7883005134665 | $3.269059324579075 |

See `codex-261006-p2p5-pk-392b6bb-ledger-correction.py` and `.json` beside this report. The script verifies profile,
grid and prereg hashes, reproduces both saved bases within floating-point tolerance, leaves readings arithmetic unchanged,
and checks that every consumed input hash remains unchanged. It creates its supplement exclusively at a new path.
The numbers retain the old L40S learned-arm proxy and N16 scaling assumptions; they do not price packed A100 execution
or establish a measured/enforced campaign bound. No historical ledger/evidence/source bytes were edited.

Free planning/preparation is already authorized by user 21549. Requested action is a focused protocol revision followed
by free implementation/CPU audit; there is no new user-permission request. No paid proof or campaign launch is authorized.
