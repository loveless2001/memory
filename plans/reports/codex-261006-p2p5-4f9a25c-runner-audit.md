# P2.5 profile follow-up: CPU self-stop proof next; GPU launch still held

Reviewed `4f9a25c07d9f4b98df320d99d29e38bb66e7129c` in response to
#gravity 21455. Runner SHA256:
`bf8d2c873b5497193d6f43ab352b84141b7d73a96dd1c28d61a1143f0454913e`.

The scheduled CPU reaper is a useful independent termination mechanism,
and a small CPU-only proof of its container credentials and whole-app stop
is the appropriate next stage. **R1 and the remaining R3 checks are not yet
closed; do not deploy/spawn the GPU profile.** User 21446's one-profile $3
authorization persists. Necessary proof work must be reserved within that
same total, with one attempt and no automatic retry. It does not authorize
the 18-cell campaign.

## Verified improvements

- Supplied CPU-only suite: **23 passed in 0.40s**, exit 0.
  `.venv/bin/python -m pytest -q tests/test_sgm_p2p5_l40s_profile_runner.py`.
- Independent probes now reject incorrect source, missing environment,
  missing warmups, non-finite/inconsistent mean, non-finite full peak and
  enabled TF32. Worker and collector pass the source binding to validation.
- The early watchdog is armed before the guard RPC. Admission refuses starts
  with less than 900 seconds remaining. A scheduled reaper now exists outside
  the GPU worker, addressing the previously absent host-independent stop.
- Heavy pip installs and model download share a 1,200-second build function.
  The stated 2x CPU/RAM overuse allowance makes its reservation basis explicit.
- Plan arithmetic reproduces **$2.3844246**, including GPU lifetime
  $1.9563936, reaper $0.009647, timed build $0.168384 and margin $0.25.
  Prices match the current [Modal pricing page](https://modal.com/pricing).
  This is a reservation under the stated schedule/stop/build allowances;
  CPU/RAM requests and a successful proof do not turn those allowances into
  universal platform guarantees. [Resource billing](https://modal.com/docs/guide/resources).
- Modal **1.5.1**'s installed `modal.experimental.stop_app` really accepts a
  deployed **name** and resolves it to an app ID before sending `AppStop`.
  The call's signature is correct. Its permission to stop an app from the
  container remains a remote question, as Claude identified.
- The profile script, memsub source, guard and retained original OOM evidence
  are unchanged. R2's previously verified collector recovery remains closed.

Evidence is in `codex-261006-p2p5-4f9a25c-runner-checks.py` and the adjacent
JSON. All Modal calls, volume commits and profile workloads in these checks
are substitutes. One disposable CPU subprocess uses the real Watchdog:
Python 3.12 POSIX `subprocess.run` returned after **0.152 s** for its 0.15 s
timeout, despite the helper's inherited capture pipe. That suspected pipe
delay was **not reproduced**; it is not a finding against this runner.
The owned fixture helper was stopped. No remote build, deployment, GPU work,
profile rerun or registered/reserved population access occurred.

## R1: fix the termination ordering and remaining time, then prove the API

In the actual reaper body, the optional
`FunctionCall.cancel(terminate_containers=True)` runs synchronously before
`stop_app`. Our substitute cancel blocks on an event: **no app stop is
attempted while cancellation is blocked**; the stop occurs only after that
event is released. Catching an exception does not bound a stalled call.
The 110-second function timeout can end a reaper tick before it reaches
the binding whole-app stop. Give the whole-app stop its own execution
budget and prevent optional cancellation or evidence writes from gating it.
The proof must test this corrected path, including a missing call ID and
an optional cancellation failure/stall, rather than only `reap_decision`.

The worker's `remaining` is cached at admission. A logical-time fixture
admits with 900 seconds remaining, spends 119 seconds in the early
identity/claim phase (below its 120-second watchdog), then grants the child
**810 seconds while only 781 remain**. Its allowed timeout ends 29 seconds
past the absolute deadline. This is a CPU control-flow fixture, not measured
GPU work. Recompute remaining time immediately before child launch, refusing
when the fixed reserve is exhausted; use the same absolute deadline for
subsequent collection/commit work as applicable.

The server-side stop currently resolves the constant app name. Bind the
proof and production stop target to the originating deployed app and its
environment, preserving the exact app ID in provenance. The CPU proof
should establish what that container client can stop; a name resolving to
some deployed app is not identity evidence by itself.

Prepare a frozen proof runner with a unique app/Dict, bare CPU image, explicit
short deadline and resource/lifetime reservation. It must contain the same
corrected reaper path, without the GPU function, Qwen build, artifact volume
or registered populations. Save code/hash, deployment app ID and deadline
before testing; let the scheduled reaper stop it independently of the launch
host. Retain server-side stop-attempt evidence and independently confirm
stopped/unlisted state, zero tasks and zero matching containers. A local
fallback stop must be labeled fallback and cannot count as proof of self-stop.
Reserve this proof in the existing $3 total before its single paid attempt;
failure means stop and preserve evidence, not automatic redeploy/retry.

The nominal 120-second schedule and 120-second stop-latency allowance remain
assumptions, not published worst-case deadlines. Modal documents that execution
timeouts exclude scheduling time. Record observed timing and avoid claiming
a platform-enforced spending cap from the arithmetic alone.
[Scheduling](https://modal.com/docs/guide/cron),
[timeouts](https://modal.com/docs/guide/timeouts).

## R3: expected environment/contract values remain unchecked

The validator tests whether Python/torch/CUDA/GPU fields are present, but
does not compare their values with the paid profile's bound environment.
Six independent otherwise-valid fixtures are still reported usable:

- `torch = 2.7.1+cpu`.
- An incorrect CUDA version string.
- `gpu = NVIDIA A10` rather than L40S.
- Missing contract.
- `contract = bf16 detached-source fixture`.
- Phase 2 `train_filler_len = 0` rather than 40.

The previous R3 requirement was expected source/**contract/CUDA environment**,
not metadata presence alone. Require the pinned torch/CUDA versions, expected
GPU identity and Python family, the fixed contract and per-phase filler values
in both worker and collector validation. Preserve unusable records with their
reason. Add these acceptance counterexamples to the local suite; they do not
require a profile rerun or any new scientific population.

No scientific or GPU fit result follows from this audit. The CPU proof is a
lifecycle/API check only; the single timing profile and full campaign remain
separate subsequent gates.
