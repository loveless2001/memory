# Option B packing: one launch cleared

The user selected B in message 21528. Frozen source `57aad85` addresses the measurement and lifecycle findings from `03fbe79` and the remaining NaN-mean gap in `bf5c8b3`. Independent source, artifact, fixture and local orchestration checks pass. This clears one attached invocation of the existing dev runner for the fixed packing test, within the separately selected $2 envelope. Claude owns launch and collection. No fresh permission request is needed for this already selected scope.

The packing script is bound to `57aad85` (SHA prefix `873bca62`); runner SHA remains `5c1e287e11465db32cecfe5e9e6682a61994fc897fe750b240dd5ed5348838c1`, and memsub remains `b87a767baac578d94a6f778560f4fb451fd60679cca48412218adaac74f74085`. Complete source hashes are retained in `codex-261006-p2p5-packing-final-source-check.json`. Original v1 timing/protocol bytes remain unchanged.

The primary statistic counts all k×6 complete measured updates over the earliest post-warmup barrier release through the latest finish. Each phase's `speedup_vs_k1` uses that statistic. The fractional-overlap and reciprocal-mean statistics remain explicitly secondary estimates. Validation rejects invalid identity/update records, non-finite or inconsistent means/spans and non-positive overlap. The final-warmup barrier aligns measured starts. Workers check parent-death signal registration and expected parent identity; all started workers are killed/reaped in `finally` on test failure. Matrix execution stops at its first failed test.

Independent verification completed:

- 21 targeted tests passed in 0.93 seconds, including original adversarial examples, malformed records, real launch-failure/timeout cleanup and checked parent identity.
- Nine additional NaN/infinity probes across mean, start and end are rejected.
- A separate local CPU smoke completed all four tests with valid records, positive overlap, and independently recomputed primary rates/speedups. It ran at `bf5c8b3`; the subsequent four-line source change only strengthens validation, which was re-applied successfully to every saved worker record. CPU timings are not GPU evidence.
- Peer v2/v3 smoke artifacts byte-match their frozen commits; all worker JSON records reconcile with the saved summaries. The v3 package also validates completely.
- The previously executed 12 runner dispatch/error fixtures apply to the unchanged runner, and its shared execution body remains identical to the accepted dev implementation.
- Read-only preflight at 2026-10-06 15:44:41 UTC found every scoped prior dev app stopped with zero tasks and no live matching containers. `dev-gpu/packing-a100-v1` was absent.

Allowed matrix, in order: learned P2/filler40 k1 then k2; learned P1/filler0 k1 then k3. Each worker uses Qwen3-0.6B-Base, full-gradient FP32 token-serial training, residual readout, N32, batch16, two warmup plus six measured updates, seed99+rank and two PyTorch threads. No registered/artifact/reserved population, accuracy evaluation, checkpoint resume or campaign result is included. Primary P2 k2 speedup thresholds remain ≥1.5 for considering a priced design, <1.2 for little observed usefulness here, and otherwise inconclusive; these are descriptive decision heuristics.

Launch once from the repo root:

```bash
timeout --kill-after=15s 1320 .venv/bin/python -m modal run \
  modal-runners/modal-m4-sgm-p2p5-dev-gpu-test-runner.py \
  --gpu a100-80gb \
  --script scripts/sgm-p2p5-gpu-packing-concurrent-training-throughput-test.py \
  --out plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/dev-gpu/packing-a100-v1
```

Retain console and wrapper exit status beside the fresh output. The selected function uses one A100-80GB, `(8,8)` CPU and `(65536,65536)` MiB RAM, timeout1440, retries0 and max_containers1. The script watchdog is 1080 seconds and test timeout420 seconds. Run attached; do not redeploy persistently or add a GPU smoke.

Book **$1.98**: conservative runtime $1.71037440 over 1320-second attached-client lifetime plus an assumed 120 seconds detection/teardown, full build reserve $0.168384 and $0.10 margin total **$1.97875840**. This is a reservation within the separate $2 envelope, not a platform-enforced cash ceiling. Resource overuse, disconnect/teardown and build allowances remain assumptions. The existing runner's per-function charge omits cumulative starts/build/teardown; attached outer lifetime supplies the nominal cumulative basis. Platform crash restarts can occur despite `retries=0`.

No operator retry, OOM rescue, precision/batch change, added configuration, longer measurement or follow-on campaign is cleared. Any interruption is reported as failed; retain partial and failed evidence. Collect the terminal result, then verify the bound new app is stopped or unlisted, has zero tasks and has no matching containers. Report app-only billing as a snapshot and retain the full reservation until reconciliation; unused reserve does not authorize more work. Source changes or an already-existing destination require renewed review before launch.

This short, fixed-order A100 experiment cannot establish a CPU bottleneck, long-run packing behavior, GPU/campaign resume or a campaign price. Host, order, short warmup and six-update measurement limits remain. The audit itself used only CPU execution and read-only remote preflight.

Evidence: `codex-261006-p2p5-packing-final-source-check.py/.json`, `codex-261006-p2p5-packing-57aad85-tests.log`, `codex-261006-p2p5-packing-bf5c8b3-cpu-smoke/` and its log, `codex-261006-p2p5-packing-57aad85-prelaunch-state.json`, plus the preserved original counterexamples and runner checks.
