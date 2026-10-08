# Readout probe: corrected implementation package r2 (codex 21787 HOLD: P1 builder import, P2 smoke outer bound)

Authority: codex 21787 (HOLD, two blockers), 21782, 21783, 21786. Base: r1 package c3c6fa2 / code fbfebe0.
**Code commits: 8b476fd (fixes) + 51b333d (one added test case).**
- No Modal RPC, build, deploy or spawn.
- No GPU smoke and no Qwen forward pass.
- Nothing charged.

## What changed vs c3c6fa2 (`fix-diff-c3c6fa2-to-51b333d.patch`)
Only 3 r1-frozen files changed; the other 11 r1 checksums still pass:

| file | change |
|---|---|
| modal-runners/…-readout-probe-slot-runner.py | slot logic baked into a `copy=True` layer BEFORE `run_function`; the GPU image's later slot-logic mount was removed (it inherits the layer) |
| scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py | only launch form `timeout --signal=KILL 3600`; the parent argv and process-group check runs first; inner watchdog 3,540 s; torch import moved after the check |
| tests/test_sgm_p2p5_readout_probe_runner_reaper_reading.py | old loose smoke test removed (replaced by the tighter tests below) |
| tests/test_sgm_p2p5_readout_probe_build_stage_and_smoke_bound.py | NEW, 9 tests |

Unchanged:
- grid, registry, schema, freeze script, validator, slot logic, ledger script and ledger JSON, reading, proposal;
- memsub tree;
- every campaign file.

The ledger ($40.7401166468 by codex) and scope (4 TOTAL admitted starts, immutable 31,946.2 s) are untouched.

## P1: builder import
- **Cause (codex):** a non-serialized `run_function` builder gets only its SDK-declared source, the runner file at
  `/root/<runner>.py`. The runner loads the sibling slot logic at import, and final-image mounts do not exist at
  build time.
- **Fix:** `.add_local_file(L.SLOT_LOGIC_FILE, "/root/<slot-logic>.py", copy=True)` placed before `.run_function`. Its
  bytes are the same bound file. Side effect: changing the slot logic rebuilds the torch/model layer.
- **Regressions.** The runner is imported the way `modal deploy <file>` does it (`import_file_or_module`), and the
  stage files are read from the SDK's own lazy layer objects (Modal 1.5.1, no RPC):
  - Builder files = the FunctionInfo entrypoint mount (asserted to be exactly `{/root/<runner>.py}`) plus the COPY
    context mounts of the layers BEFORE the build layer (asserted to be exactly `{/root/<slot-logic>.py}`).
  - It is asserted that no deferred mount precedes the build step and that the final-image mounts are disjoint from
    the builder set.
  - The builder set is copied into an empty root, and the runner is imported there in a fresh `-I` interpreter (module
    name = file stem, `/root` on sys.path): it imports.
  - **Negative control**, SDK source only: it fails with FileNotFoundError naming the slot-logic file.
  - Runtime: `run_slot` and `reaper` each import from their own effective set (entrypoint mount, COPY layers and
    deferred mounts).

## P2: smoke outer bound
- **Launch:** `timeout --signal=KILL 3600 .venv-gpu/bin/python scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py --out <new dir>`.
  GNU timeout 9.4 without `--foreground` puts itself and the child in a new process group and SIGKILLs the group at
  3,600 s from launch.
- **The script refuses before any repo or torch import, output directory or model load** unless all of these hold:
  - its parent's argv is exactly `timeout --signal=KILL 3600` followed by this process's own `sys.orig_argv`;
  - its process group is the timeout's.
- **Inner watchdog:** a SIGKILL Watchdog of 3,540 s, armed before torch is imported. It fires before the outer bound,
  so its out-of-group sleeper cannot outlive the group.
- **Workers:** the supervisor's single `subprocess.Popen` has no new session, process group or preexec_fn (tested), so
  they share the group. PR_SET_PDEATHSIG is kept.
- **Tests:**
  - Exactly 20 updates. The pilot differs from the probe cell config only in the override keys, and every filler
    phase starts before update 20.
  - The documented command is exact and has no `--kill-after`. Order in main: check, then mkdir, then Watchdog, then
    torch, then the supervisor. Top-level imports are stdlib only.
  - **Real subprocess checks.** The exact parent → None. Each of these is refused:
    - no timeout
    - 3599
    - plain `timeout 3600`
    - TERM
    - `--foreground`
    - right prefix but a wrapped command
    - right parent but its own process group
  - Run without the bound, the script exits nonzero and does NOT create `--out`.
  - **Group kill:** the same `timeout --signal=KILL` form with a 2 s duration runs a harmless 3-deep plain-Popen tree.
    All 3 processes share one group, and all are dead or zombie within 10 s.

## Evidence (this dir)
- **Suite:** `sgm-suite.txt` / `.exit.txt`: tests/test_sgm_*.py + hygiene at 51b333d, **565 passed, 2 skipped, EXIT 0**.
  That is r1's 557, plus 9 new tests, minus the 1 replaced smoke test.
- **Mutation script** `mutation-checks-readout-probe-r2.py`: the 26 r1 mutations unchanged plus 12 P1/P2 mutations,
  run in private copies with re-freeze where needed, and the aimed test must fail. The P1/P2 mutations:
  - copy layer removed
  - the exact c3c6fa2 image block restored
  - copy turned into a deferred mount
  - refusal removed
  - any timeout options accepted
  - argv tail ignored
  - process-group check dropped
  - outer bound 3660
  - inner watchdog equal to the outer
  - 21 updates
  - torch imported before the check
  - supervisor workers in a new session
- **Run 1 at 8b476fd:** 37/38 caught (`…-run1-at-8b476fd-one-survivor.*`, EXIT_STATUS=1). The survivor was "argv tail
  ignored". 51b333d added the wrapped-command case.
- **Run 2 at 51b333d:** baseline 73 passed; **38/38 caught by their aimed test; all_ok, EXIT_STATUS=0**
  (`mutation-checks-readout-probe-r2.{json,stdout.txt,exit.txt}`).
- The exit files use the `EXIT_STATUS=<n>` format (r1 used `EXIT <n>`).

## Next gates
1. Codex byte review of this package.
2. One bounded local smoke (the command above), with no retry, and its evidence.
3. Codex smoke clearance.
4. chat_read, deploy, spawn, collect.

## Unresolved questions
- The runner is 227 lines, still over the 200-line guideline. It is kept whole so that all bindings stay in one place
  (as in r1).
