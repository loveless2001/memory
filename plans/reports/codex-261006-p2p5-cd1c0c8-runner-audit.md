# P2.5 L40S profile runner follow-up — HOLD

Reviewed `cd1c0c8b15d77db8dc9e1d0574ea9e384f04c027`, runner SHA256
`4c0b4fd7ad9960f42314a133deb628ed736050d4226d0b81901577b656accfc4`,
on 2026-10-06 in response to #gravity 21451. **R2's missing/corrupt-call
collector behavior is verified; R1 and the remaining R3 validation checks
stay on HOLD.** User 21446's single-profile $3 authorization remains valid
within the agreed scope. Do not deploy/spawn this version.

## Verified improvements

- Independently ran the supplied suite: **13 passed in 0.34s**, exit 0.
  `.venv/bin/python -m pytest -q tests/test_sgm_p2p5_l40s_profile_runner.py`.
- Plan arithmetic reproduces **$2.5222592**, including $0.189432 for the
  assumed three build layers. This is an assumption-dependent reservation,
  not yet an enforced total paid-lifecycle bound.
- Additional checks reproduce shutdown/fetch through the saved app ID for
  both missing and corrupt call files when `collect()` is invoked after its
  deadline/grace. The original `FileNotFoundError` path is corrected. State
  writes use write/rename, and the launch app ID is saved before submission.
- The validator now rejects child failure, outer timeout, empty matrices,
  seven measured durations and non-finite measured durations. It verifies
  order, ten updates and positive measured/dev/training-peak fields.
- The profile script, memsub source and original OOM evidence are unchanged.

Independent counterexamples and bindings are in
`codex-261006-p2p5-cd1c0c8-runner-checks.py` and adjacent JSON. All Modal calls,
child workloads, watchdogs and commits are local substitutes; no model/GPU
work, deployment, build, remote write or population access occurred.

## R1 remains open: admission is not total lifecycle termination

The new guard is the first statement inside `run_profile()`. Container
startup, global imports and initialization precede that function. A crash
there never consumes a guard slot. Modal explicitly includes startup/global
import crashes among the failures it reschedules, and deployed crash loops
can continue indefinitely. Therefore `MAX_STARTS=2` does not bound all
physical charged starts. This is a documented platform/source gap; no
remote crashes were induced. [Modal crash behavior](https://modal.com/docs/guide/retries).

The guard Dict RPCs also occur before the early watchdog. The ledger
reserves ten execution seconds for a guard-refusal start, but the guard has
no ten-second hard deadline. Catching an exception cannot stop a stalled
RPC. Every admitted start must have a bounded guard phase too.

The absolute deadline is checked only at admission. In the independent
logical-time fixture, a start with **one second remaining** still receives
the complete **1,860-second outer timeout** and reports `profiled` after its
logical deadline. This is a substituted CPU control-flow counterexample,
not a timing measurement. The worker does not enforce remaining overall
time on its subsequent work.

`collect()` performs a stop only when someone invokes it. No independent
controller is launched by `spawn()`, so its deadline/grace stop does not
survive a lost launch host. Its saved-state recovery is useful and tested,
but the current claim that paid lifecycle termination is independent of
the host is unsupported.

Required: arm and verify an independent app-ID-bound stop before paid
work; include its charge and shutdown allowance. It must cover startup
crash loops, guard stalls, active late starts, and host/call-ID loss. Enforce
remaining overall time throughout a worker rather than grant a fresh full
child budget at a late admission. Test the actual termination path and
retain stopped/unlisted app, zero tasks and zero containers as the eventual
remote evidence. Keep all work inside the existing $3 scope; this does not
authorize any extra profile or retry.

The two pip-layer 900s/resource budgets remain unenforced assumptions.
The download layer now has a 900s function timeout, but scalar CPU/RAM
arguments specify requests. They do not establish a RAM usage ceiling or
fixed actual billing; requested or actual usage, whichever is greater,
is billed. Bound or externally contain all build phases and resources,
and carry a justified overuse margin before describing the ledger as a
complete cap. [Modal resources and billing](https://modal.com/docs/guide/resources).

## R3 remains partly open: validate the fields used as evidence

Five direct fixtures are still accepted as usable with exit 0 and the
otherwise correct matrix:

- Incorrect `memsub_source_sha256`.
- Missing environment metadata.
- Missing the two warmup durations.
- NaN `mean_measured_s_per_update`.
- NaN `peak_memory_bytes`.

The current checks cover `measured_s`, `dev_eval_batch_s` and
`peak_train_memory_bytes` only. The previous audit explicitly required
two warmups and the expected source/compute/environment identity in addition
to finite timing/memory output. These are remaining parts of that same R3.

Require the two warmup values, finite and consistent reported mean, finite
overall/training peaks, and expected source/contract/CUDA environment.
Validate the fields from the launch bindings in both the worker and
collector. Missing or malformed records must remain unusable with their
reason and retained evidence. The pure tests' abbreviated `_profile()`
fixture must cease to stand in for a fully valid bound report.

No GPU profile or full campaign result follows from these local checks.
The original OOM remains a retained incomplete fit attempt. The next
implementation audit can close these remaining gates without another user
approval request if the fixed protocol and $3 cap remain intact.
