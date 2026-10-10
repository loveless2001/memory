PK6 audit: v1 curriculum error corrected; v2 arithmetic reproduces, execution-cap package not cleared

Audited a4ce83b and its same-task correction 1cd0469ba5199fd8c0084a1fd67ae23b9f184852. The free arithmetic reproduction and source/charge-path review are complete. Claude remains implementation owner. No GPU work, campaign execution, reserved readings, deployment, spawn, stop, shared-artifact edit, commit or push was performed by this reviewer.

The $149.73 expected / $313.34 planning reserve / $435.96 lifecycle figures in v1 are wrong for the registered curriculum. The source unpacked `(_, switch)` from `[1000,40]`, so it used forty P1 and 1460 P2 updates. I reproduced the committed v1 result exactly and independently reconstructed its wrong arithmetic. Claude fixed this at 1cd0469, preserved v1, added a fail-closed 1000/500 check, and withdrew the old quote/comparison in gravity21592/21593.

The v2 CLI independently reproduces its committed JSON exactly. Independently rebuilt schedule arithmetic agrees within $1.5e-14, from floating-point summation order. Script SHAb993d434e0cb9dac87146481b162a152fa48a29ef5db373e3020218eb92c6f63; v2 output SHA3a53d78258bf09ba62026128a46ce4b949c99387261eb563c93b5a5cecd45cc4.

| Model, retaining other v1/v2 assumptions | Expected USD | Planning reserve USD | Conditional global lifecycle USD | End-to-end wall hours |
|---|---:|---:|---:|---:|
| Original v1, wrong phase split | 149.729954 | 313.343015 | 435.956710 | 8.646140 |
| v2, correct 1000/500 split | 112.791946 | 248.045459 | 358.386955 | 7.206390 |
| Correct split, primary fixed-work rates | 112.799097 | 248.060192 | 358.409404 | 7.206724 |
| Above, conservative sixty checkpoint commits per slot | 113.497136 | 249.294031 | 359.643011 | 7.229612 |

The sensitivity rows are diagnostic calculations, not corrected executable quotes or approval. They retain unvalidated startup, full-readings and lifetime assumptions. v2 training slots take 5.174861h in parallel, followed by its 2.031529h single-container readings allowance. Queueing, model/parameter loads, validation and settlement can add time; this is a host-derived estimate. The old 6.6h v1 figure omitted sequential readings and therefore was not the full completion time.

Verified scope and inputs

- Registered grid SHAd1c045eadfb562829cab72f58ba6b293f573f2e853629d3a3dd324b740a13073; exactly nine fixed two-seed slots and all eighteen original cells.
- Consumed audited T SHA6381c986972af93ddb712171b0bbe2e1fc1465dc524a549d0e9650a3e514f537 and timing.exit SHAd92cf667c73d63a92e6f7afb10fb70a42c14e7da405f852e3e00e22d8020df17 match the independently accepted GPU proof. No old packing/L40S timing is consumed by this script.
- Source remains memsub2e422cea223ab8fb27dad1ca796ff9a1f1f7f03ebd98dfa5ed541e208b75ffc5. All post-proof committed changes are the new pricing script and v1/v2 outputs; frozen proof evidence is unchanged.
- Actual train loop evaluates at 0,100,...,1500: sixteen evaluations, each four batches. Durable generations are 50,100,...,1500: thirty per cell. Current run_pilot multiplicities are correctly 84 learned/random/oracle, 68 single-cell, 20 memory-off. The readings model preserves both oracle populations, all cells, three memory-arm interventions and none-only memory-off; its complete traversal is an upper workload scenario, since registered interface failure must leave the corresponding remaining readings untouched.
- Rechecked official [Modal pricing](https://modal.com/pricing) on Oct7: A100-80GB $0.000694/s, physical CPU $0.0000131/core/s, RAM $0.00000222/GiB/s. CPU/RAM are charged on the larger of requested and used resources. The script's hard-tuple and 2x CPU/RAM basis reproduce from these rates; they are planning assumptions, not a platform cash guarantee.

Remaining blocking items for a user-cap package

1. Bind the reserve to the actual executable lifetime and retry envelope. v2 prices the sum of per-slot reserve lives at $248.05, but its own all-nine-slots-through-global-deadline scenario costs $358.39 under the same billing assumptions. A longest-slot whole-app reaper does not itself justify the smaller sum as an execution cap. Four admitted starts also do not count charged containers that crash before admission. The campaign runner does not exist yet, so no per-slot remaining-time enforcement, termination, startup/crash handling or charge envelope has been verified. Either implement and independently demonstrate controls that support the chosen smaller envelope, with charged startup/unadmitted/stop allowances, or base the cap request on the disclosed larger lifecycle reservation. Preserve an explicit distinction between estimated cost, booked reserve and conditional lifetime scenario.

   Modal documents that [deployed container crashes retry indefinitely](https://modal.com/docs/guide/retries), separately from configured function-failure retries. Its [timeout documentation](https://modal.com/docs/guide/timeouts) separates scheduling/startup/execution and allows execution to overrun by seconds. The nominal reaper period/stop allowance and 2x CPU/RAM basis do not establish an absolute worst case. Correct that wording from gravity21590. The v2 lifecycle expression also omits its separately calculated CPU reaper charge and explicit readings shutdown allowance.

2. Complete the all-charge mapping to the intended campaign consumer. A CPU probe of the real SlotSupervisor acknowledgement/request path produces sixty checkpoint-generation commit calls for two workers, not thirty: thirty acknowledged generations per cell. The unchanged supervisor also commits initial inheritance once, outputs and COMPLETE separately for each worker, and the runner commits on final exit. v2 budgets `30*(serialize+commit)`. That can only be a per-worker critical-path proxy, not the number of serialized supervisor commits. Some co-tenant compute overlaps a commit, so sixty waits should not be presented as a measured additive wall time either. Use a justified overlap model or a stated conservative charge allowance, and include initial/terminal publication, reload/hash/validation/output costs and restart commits. The sensitivity table shows that conservative checkpoint commit counting alone is a small roughly $1.23 reserve change, not the main $110 lifetime gap.

   T's serialize timer covers torch.save into BytesIO after training_state has already assembled/copied CPU tensors; it does not measure the complete atomic fsync/file-write path. Its commit probes use short-proof checkpoint sizes on one active profile container; concurrent nine-slot commits and 1500-row telemetry growth are not measured. Treat that extrapolation as an assumption and assign reserve coverage.

   The 300s startup constant must state what it covers. Models are built in worker execution, so a Modal startup_timeout alone does not bound model loading inside the function body. Explicitly cover initial and repeated model/checkpoint loads, parameter loading/validation across the single readings pass, stop/teardown and readings reaper costs, and any billed build objects. The $5 margin can cover named residual charges; do not silently count it twice or imply unmeasured costs are zero. The proof's full $8.57 remains separately booked until final app/build charge reconciliation, with no double reuse as campaign margin.

Required metadata and measurement corrections

- T is two warmup plus four measured updates per worker, six total. Both v1/v2 incorrectly say six measured updates in assumptions. Keep the short-run/single-host limit visible.
- Use the accepted primary fixed-work rate (two cells' total measured updates over earliest-start/latest-end span) for shared-container training life, or explicitly label the slower-worker mean as a proxy. The numerical difference here is tiny, about $0.007 expected and $0.015 reserved, but the consumed measurement definition should remain consistent.
- Record the imported memsub helper/source binding, prereg/amendment and accepted proof provenance in the executable package, not only hashes of grid/T/pricing script. Current imports and counts are independently verified now; future helper changes must not silently change a bound quote. Refuse missing, duplicate or incompatible T records rather than relying on dictionary replacement; consume the already accepted proof identity/schema/spec.
- v2's roughly 30% expected / 9% reserve reduction is a comparison of two arithmetic models. The older L40S ledger uses arm/N proxies and different restart/evaluation allowances. This is not an empirical matched-host cost or speedup measurement. No relative wall-clock claim is established without binding the comparison's GPU availability/concurrency schedule.

Next action

Claude should produce a new preserved-output pricing revision and a concrete lifetime/charge design addressing these findings, before asking the user for a choice or execution cap. Free implementation and review may continue within the already selected packed-P2.5 plan; paid work remains gated. The manifest-label correction, fully bound campaign runner/schema/registry, registered population validation and independent implementation audit remain campaign prerequisites. Scope reduction or an L40S alternative would need its own explicit protocol/authorization and must not be silently substituted.

Evidence in this reviewer-owned directory: v1-source-at-a4ce83b.txt, exact CLI v1/v2 reproductions, independent-priced-estimate-audit.json with all sensitivities, v2-independent-reconciliation-normalized.json, source-and-count-binding-check.json, and actual-supervisor-commit-count.json plus its scratch CPU records/scripts. No production-source edits or paid operations were made.
