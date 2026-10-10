# P2.5 proof review: R3 closed; correct three proof/lifecycle blockers

Reviewed `8f4a27f33ceb540debc40d6e51bb1106888bda83` for #gravity 21457.
Independent supplied-suite result: **32 passed in 0.40s**, exit 0.
The six remaining environment/contract/filler fixtures now reject correctly;
**R3 is closed for the requested checks.** R2 remains closed. Stop-before-
cancellation ordering and recomputing the child timeout also pass independent
local checks. The previous 900-second/119-second fixture now grants 691 seconds,
preserving its 90-second reserve.

The exact CPU proof and production reaper still need the corrections below.
**Do not run `prove` at this revision.** This is an implementation/evidence
hold, not a request for new user authorization. User 21446 already authorized
the single-profile $3 scope, and 21456 placed the necessary one-attempt CPU
proof inside it. The combined stated reservation is **$2.4370556**:
$2.3844246 profile plus $0.052631 proof. Preserve the stated scheduling,
stop-latency and build/resource assumptions. Neither arithmetic nor this
CPU proof alone certifies a platform-enforced spending cap.

Frozen reviewed identities:

- Profile: `5af72fd1e9a0f4b9a0f38e0b0a376b27d08d3b547a7cf0026b0bd7fb2ed67c42`.
- Shared logic: `fe4825a80d1b3f77b76338c9fe1d2e2af81ed6f2acaba7f3f8e9d66d571198ed`.
- CPU proof: `31e83604c564847e6b335d350d216938a61329196338d94b92899200001416a2`.

Reproductions are in `codex-261006-p2p5-8f4a27f-proof-checks.py` and its JSON.
All Modal, deployment, lifecycle and stop operations are substitutes. Local
SDK object inspection does not hydrate anything. No remote operation, GPU
work, paid build, deployment or population access occurred.

## 1. Production reaper does not mount the shared logic

The GPU function has the explicit `image=image` with the shared file. The
production scheduled `reaper()` has no explicit image, and the app has no
default image containing that file. Its local Modal **1.5.1** `FunctionSpec`
therefore uses a bare default image with **no shared-logic file dependency**.
Only its entrypoint runner and Modal client source are automatically mounted.

The CPU proof's `FunctionSpec` does include
`/root/modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py` in its image
dependency graph. Thus the proof and production do not currently have the
same deployable stop path. The production runner executes `_load_logic()`
at global import, before any worker watchdog; absent the file, the production
reaper cannot import and run.

These are local SDK construction facts, not an induced remote crash. The
inspection registers each module in `sys.modules`, matching the Modal CLI's
file-based import. The supplied pytest loader does not register its module,
so those raw-function tests do not check the actual entrypoint mount graph.
SDK `FunctionInfo.get_entrypoint_mount()` mounts only the runner file in this
file-based case; `_FunctionSpec.image` for reaper is the bare default image.

Attach a small CPU image containing the shared logic to the **production
reaper**, avoiding the heavy GPU/model image. Check both reapers' SDK dependency
graphs in file-definition mode and retain the bindings. Modal's documented
route for extra local files is explicit inclusion through images.
[Local data and files](https://modal.com/docs/guide/local-data).

## 2. Exceptions bypass the proof's cleanup and evidence

Three independent calls to the real local `prove()` with substituted external
dependencies produce these failures:

| Failure point | Retained state | Cleanup/report |
| --- | --- | --- |
| Deploy command raises `TimeoutExpired` | Initial provenance only; no deploy log or app ID | No stop attempted; no proof report |
| Deadline binding RPC fails after app-ID put | Deploy log; guard has app ID, no deadline; provenance has no app ID | No stop attempted; no proof report |
| Lifecycle observer RPC raises | Provenance and guard contain app ID/deadline | No stop attempted; no proof report |

The fallback exists only after a normal monitoring loop. It is not in a
protected cleanup path. A deployment can be accepted before its CLI times
out; timeout is not evidence that no app exists. A partial binding similarly
leaves an app without the short deadline. Its abandonment rule is 1,800
seconds after the first tick, longer than the proof ledger's asserted
1,320-second maximum app life.

The two `guard.put` calls are individually atomic, **not an atomic pair**.
That is sufficient only if partial state is explicitly handled. Save the
resolved app ID before guard binding, retain deploy stdout/stderr and the
timeout/exit classification on every path, and wrap all post-deploy work in
failure cleanup that records FAILED and stops/verifies the known app. If
deployment outcome or ID is uncertain, recover the uniquely named proof app
read-only and record that recovery before an ID-bound fallback stop.
Persist observations/errors as they occur, not just after the successful loop.

Keep the proof's host-loss abandonment timeout within its declared reservation,
and bound observer calls by the remaining monitoring/cleanup allowance. A
fallback stop may clean up the paid attempt but must never make the proof PASS.
These corrections need CPU-only exception-path fixtures before the one paid
attempt; they do not require an automatic retry or expansion of the cap.

## 3. Proof incorrectly attributes any verified stop to the reaper

Our substituted lifecycle returns an explicitly unrelated actor's stop at
epoch **1010**, while the bound reaper deadline is **1120**. The first
observation at epoch 1020 verifies stopped/zero tasks/zero containers.
There is **no `reaper_fired` evidence**. Nevertheless the current code returns:

`PASS: the app stopped itself (no local stop issued)`.

The frozen deadline logic cannot produce that early stop. This acceptance
counterexample means stopped state alone does not establish that the
container credentials successfully invoked the shared stop API.

Require a stop within the intended deadline window and retain evidence of
the scheduled reaper's bound stop attempt, tied to the actual app ID, code
identity and deployment. Capture the server-side function logs or another
non-gating observable of the shared stop path alongside lifecycle attribution
and final shutdown checks. Evidence written only after stopping one's own
app may be absent if the container exits immediately; do not rely solely
on that optional tail write. Missing attribution must remain unproven/FAILED,
and an early or unrelated stop must not pass. Add this exact fixture.

The next review can clear the single CPU proof after these concrete changes,
using the already-valid $3 scope. GPU deployment/spawn remains held until
the real corrected proof is reviewed; the 18-cell campaign is still outside
that approval.
