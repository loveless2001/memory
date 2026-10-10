# Information-probe v0.6 implementation clearance: 935f91d

**PASS for the user's already approved one-shot local CPU S1 → S2 → conditional full chain.** Commit `935f91dba30f439c60e1424a40ba05b382985883` repairs the final run-record blocker. The earlier review holds are resolved for this implementation. User approval is recorded in #gravity 22424; Claude remains the launch owner. No repeat approval request is required.

The runner normalizes the final run record once, writes it to run.json and stores the same record in result.run. Independent checks passed **56 tests in 10.89s**, exit 0, under `PKPROBE_FORBID_MODEL=1`, eight-thread settings, a 180-second deadline and an isolated basetemp. The new model-free test runs the actual S1/S2 producer with frozen-shaped four-layer fake capture, real math on small episode counts and a stubbed full-size profile. Both emitted receipts validate, both feature hashes bind, run.json equals result.run, and the fake fixture's admitted wall resolves to 2584 seconds. **That fake timing/admission is test evidence only and must not supply launch admission.** The planted differently configured S2 is now explicitly rejected for its frozen-schema mismatch.

The resolved PilotConfig was independently instantiated without a model and matches the manifest-plus-CPU expectation. Selected layers are 6/13/20/27 with feature_shift 1. The immutable snapshot's memsub source-tree hash is `2eee4228124e9d292ed4079476ca276e8ce8f9ac7c8d83d44bcd51333687a19b`. All 91 retained committed source/package files match the live checkout at the pre-clearance check; HEAD is the reviewed commit and all three launch stage paths/exit receipts were absent.

The reviewed receipt validator, controller and consumed memsub sources are unchanged from v0.5. Their earlier positive evidence stands: current source/controller/whole-memsub binding; exact feature set/shapes/hash/finiteness; run/result/admission agreement; recomputed finite nonnegative admission parts; S1/S2 initial-identity comparison and terminal full identity/wall checks; monotonic durations; and 10 simulated controller success/failure cases with fail-stop/no retry. Eight-thread OpenBLAS/PyTorch limits and isolated test-loader sentinels remain. The committed mutation record reports 29/29 caught, including removal of the final writer; this audit did not replay the mutation runner.

## Authorized launch boundary

- Local CPU, $0 paid compute; use the committed controller only.
- One S1 at 1800 seconds, then one S2 at 2400 seconds only after a valid S1 receipt.
- One full run only after valid S1/S2 and **fresh real S1 admission**, with wall `ceil(2 * estimate)` no greater than 14,400 seconds.
- Controller stage memory limits: 4400M RAM and 1200M swap; eight compute threads. No retry, extra arm/seed, wall extension, GPU or Modal dispatch.
- Full registered data: 96 train + 64 heldout episodes; unchanged frozen init arm, four layers and five feature sets. S1/S2 metrics remain operational evidence and are not the scientific readout.
- Any stage/receipt failure stops the chain and preserves partial evidence. The unintended earlier M10 run and all model-free fixtures are excluded from numerical admission/results.

This is implementation clearance, not proof of actual cgroup enforcement, runtime fit/throughput, completed numerical work or a scientific finding. Those depend on the authorized launch and terminal artifacts. The maximum sum of declared stage timeouts is 18,600 seconds (5h10m), with the full-stage bound at most four hours.

The auditor executed zero Qwen loads/backbone forwards, zero real information-probe fits/profiles, zero mutator replays and zero GPU/Modal launches. `manifest.json` and `SHA256SUMS` bind the audit report, immutable sources and isolated fake-data checks, excluding themselves, symlink aliases and interpreter caches. Prior evidence and cleanup scope remain protected.
