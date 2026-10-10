# P2.5 hard-deadline correction audit

Reviewed `4f30c154fcb6f90e0822a687e880c27d10581bec` on 2026-10-06 in response
to #gravity 21440. **The watchdog now enforces the deadline inside a stalled
configuration. One cleanup defect remains: setup exceptions leave the
independent watchdog alive. Future profile execution remains on HOLD until
that path is corrected and checked. No paid work is cleared.**

The commit changes only `scripts/sgm-p2p5-local-gpu-timing-profile.py`. Its
hash is `b165ea1049fc9f964588f77547a4bbdecdd1dbed8f2691bac7a570a84943d986`;
the unchanged guard hash is
`52c0ec5ec873fa4cfafe82f1fa612c71969e64e184b6bd557665e9b55f7f3054`.
The previous OOM artifact and log hashes are unchanged. Claude explicitly
confirmed that the original attempt had no outer supervisor and no captured
exit status. That closes the missing-launcher-evidence question; it does not
retroactively supply an enforced bound or exit evidence for the old attempt.

## Independent integration evidence

Checks and output: `codex-261006-p2p5-4f30c15-deadline-checks.py` and adjacent
JSON. Raw child logs/progress are in
`codex-261006-p2p5-4f30c15-deadline-fixtures-r2/`. Run with the CPU .venv.

These exercise the actual `main()` and `profile_config()` paths, with inert
CUDA stubs and substituted train/eval functions. The real independent OS
watchdog runs inside a disposable child. Stalled functions use a C sleep
holding the GIL; no model, training, evaluation data, or GPU work occurs.

| Fixture | Result | Retained evidence | Helper after worker exit |
|---|---|---|---|
| Stall inside substituted load/train | SIGKILL, exit -9 | start + config_start | gone |
| Stall inside substituted evaluation | SIGKILL, exit -9 | start + config_start + 10 completed updates | gone |
| Successful four-config matrix | exit 0 | 40 updates, four dev completions, four config summaries, end | cancelled |
| First-config OOM | exit 1; no later config | OOM summary + end | cancelled |
| First-config training error | exit 1; no later config | error summary + end | cancelled |
| Environment exception after watchdog arm | exit 1 | start only; traceback | **still alive** |

The first two fixtures use a 0.5s watchdog and an 8s C sleep; total child
wall time including imports was about 2.63s. They verify the hard stop beyond
cooperative Python checks. Fsynced progress survives SIGKILL; a terminal
`profile.json` is absent after a kill, so an eventual concrete launcher must
persist exit/deadline status externally rather than require that file.

The initial harness used captured pipes, which the independent helper
inherited. `communicate()` consequently waited for the helper after the
worker exited and obscured its orphan interval. Those first-pass fixtures
are retained separately. The corrected harness uses file descriptors and
waits on the worker alone, exposing the live helper. The audit parent killed
that fixture-owned helper immediately; it was not left running.

## Required correction and boundary

`watchdog.cancel()` currently runs only after successful report serialization
and the final progress write. An exception in the initial progress write,
environment/source setup, cache cleanup, report write, or final progress
write bypasses it. The guard's own documented contract requires cancellation
in `finally`. Put **all work after watchdog construction**, including setup
and output handling, under `try/finally: watchdog.cancel()`. Preserve the
existing first-error stop and incremental evidence behavior.

The independent helper targets a numeric PID after sleeping; leaving it
alive after the worker exits is incorrect cleanup. This is a reproduced
local integration defect, not a claim that a production process was killed.
After correction, verify the exception path has no surviving helper. No
laptop retry is required or authorized by this audit.

The promised outer `timeout` and captured exit status remain future-launch
requirements; the current commit contains instructions, not a concrete
launcher. A paid-profile runner, charge bound, input/environment bindings,
and shutdown proof still need their own audit and explicit scoped user
approval under prereg Gate 2. The original OOM supplies no throughput or
learning result.
