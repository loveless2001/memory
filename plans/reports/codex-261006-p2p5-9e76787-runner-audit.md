# P2.5 L40S paid-profile draft audit — HOLD

Reviewed `9e76787d9c8d0f891655caebb9e3690a9122ab7f` on 2026-10-06 in response
to #gravity 21447. User 21446 ("continue A") authorizes the single preemptible
L40S profile under the proposed **$3 total cap**, subject to runner audit.
That authorization remains valid; another approval request is unnecessary
for corrections inside this scope. **Do not deploy/spawn this draft yet.**
The full 18-cell campaign remains separately gated.

Runner SHA256:
`770d4d807c99e5ff5bdb63a05066f1ea355fa6f8e6ac3fe6323f54685fd48c40`.
Profile script SHA256:
`b5b0746a40afbd7c9feb2bcf7aa6967189903673829cf2a8d4a2afc25237a08c`.
Memsub SHA256:
`048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6`.
The cleared four-config/40-update profile and prior CPU checks are unchanged.

## Passing mechanics and evidence limits

`plan` reproduces the stated reservation exactly:
`$1.397424 + $0.199632 + $0.2794848 + $0.30 + $0.25 = $2.4265408`.
The rate is `$2.395584/container-hour`; the calculation rejects a smaller
$2 cap. L40S/CPU/RAM rates agree with the current [Modal pricing](https://modal.com/pricing).
This arithmetic is valid under its enumerated seconds/charges; it is not
yet a bound over every execution/deployment path.

Independent CPU fixtures are `codex-261006-p2p5-9e76787-runner-checks.py`
and adjacent JSON. All Modal RPCs, child workloads, watchdogs, volume commits
and shutdown actions are replaced with local fixtures. The checks exercise
the actual raw worker and collector; they build/deploy/spawn nothing.

Verified: identity mismatch returns before claiming/profiling; a first claim
runs one child; a subsequent invocation refuses profiling; child exit and
outer timeout are captured; parent completion commits; known terminal poll
states invoke shutdown with the saved app ID. No actual remote behavior or
shutdown was tested. The profile's independently verified internal watchdog
and cancellation behavior remain the earlier `50a7f2a` evidence.

## R1 — Bind total paid lifetime and build charges

`retries=0` does not disable infrastructure crash/preemption restarts.
Modal documents that deployed container crashes can be rescheduled
indefinitely, and that preemption restarts the same input. The first-attempt
claim protects against profiling again after it succeeds. Repeated startup
or pre-claim crashes, or crashes while refusing a replay, can nevertheless
create additional charged containers. The collector only stops on a
terminal poll result; a perpetually pending/crashing call has no elapsed
deadline. These findings follow the documented behavior and source control
flow; this audit did not induce real Modal crashes.
[Failures and retries](https://modal.com/docs/guide/retries),
[Preemption](https://modal.com/docs/guide/preemption).

Add and prove an app-ID-bound overall deadline/stop that covers failed
startup and all infrastructure restarts, including launch-host/call-ID loss.
Budget its monitoring, startup, teardown and possible overlap. Refused
replays must never profile, and automatic restart paths cannot consume an
unbounded number of charged attempts. Preserve a real stop point with
stopped/unlisted app, zero tasks and zero matching containers.

The flat $0.30 image-build reservation has no enforced time/resource basis
in this runner. Its model-download build function uses SDK 1.5.1 defaults
(`timeout=3600`, CPU/memory unspecified); pip builds also remain outside the
profile's 1,800-second watchdog. State a concrete bounded build strategy and
all charged components, or include them under the overall paid boundary.
Retain appropriate overuse/teardown allowance: CPU limits use throttling,
while RAM limits are hard, and billing follows requested/actual usage.
[Resource limits and billing](https://modal.com/docs/guide/resources).

## R2 — Recover missing/partial local launch state

`spawn()` writes provenance, accepts the remote call, then writes
`call.json` directly. A lost host or failed/truncated write after acceptance
leaves an untracked call. The fixture removed `call.json` while leaving the
saved app ID; `collect()` raised `FileNotFoundError` before reaching shutdown.
The existing root prevents a casual second spawn but does not recover this
state or stop it at a charged deadline.

Use atomic/fsynced launch-state writes and represent pending/untracked
acceptance explicitly. Recover through the saved app ID/claim/artifact
evidence without respawning; enforce R1's deadline even if a call ID is
missing or corrupt. Normal known-call terminal shutdown is already correct.

## R3 — Validate usable profile output and retain failure evidence

The worker returns `status="done"` on child exit 1, outer timeout, and a
synthetic `status="complete", configs=[]` report with exit 0. The collector
does not validate the matrix. A malformed result therefore enters the same
transport status as usable timings. These are directly reproduced CPU
fixtures, not real results.

Before classifying timings as usable, require exit 0, complete status, the
exact ordered four configurations, ten updates/config, two warmup/eight
measured durations, finite nonnegative memory and valid finite timing
fields, plus the expected source/compute/environment identity. Failure,
timeout, OOM and preemption retain stopped/unavailable status and partial
evidence; they cannot supply a full-ledger estimate. Preserve the exit
JSON, stdout/stderr and progress locally after collection as well as on
the volume, including when a replay-refused result supersedes a preempted
first attempt. Missing terminal evidence stays explicitly unavailable.

Modal documents periodic volume commits and a final shutdown snapshot.
The explicit commit after the child covers ordinary child completion/kill;
it does not prove every last fsynced event survives abrupt container loss.
Any missing tail must remain identified rather than inferred.
[Volume persistence](https://modal.com/docs/guide/volumes).

## Pricing correction and authorization boundary

The earlier 3x GPU-only comparison was a hypothetical multiplication, not
an available Modal non-preemptible GPU option: the current preemption guide
explicitly excludes GPU Functions from `nonpreemptible`. The approved
preemptible L40S option is unaffected. That correction was posted in 21449.
[GPU preemption support](https://modal.com/docs/guide/preemption).

Binding the prereg/model manifest and the reused lifecycle-helper hashes in
launch provenance will strengthen the review trail. All corrections must
preserve the fixed seed-99 matrix, no artifact/reserved populations, no
accuracy output, first error stop and no profile replay. No paid operation,
GPU work, dataset evaluation, or implementation-source change was performed
by this review. The original OOM artifacts are untouched.
