# Option A dev testing: keep run 1; fix reporting and budget before later runs

User 21476 explicitly authorizes moving option-A GPU testing to Modal after
laptop crashes. That authorizes the development move; no redundant user
permission request is needed for necessary testing in the announced cumulative
$3 envelope. The completed original timing profile is separate evidence and
budget. Final registered re-timing/campaign are outside this development scope.

Reviewed #gravity 21477, 21481 and 21483, with launched source now frozen at
`19f51b9d969af7bc0b51016c7f2cae6ac2cbff78`:

- Dev runner SHA256 `52b3da22236527c20319cbbb28958ec936635e7fab1fc2239513944f10a0fe38`.
- Hotspot script SHA256 `c4f6e77e70797a328797c382fa96d69164f04690e45d6d427b05ff44bdc96d82`.
- Saved run-1 app `ap-UUv74AxrTl2LhmY6g128Jk`.

The current attached run was already in flight when my preliminary review
arrived. **Let it finish; do not stop and relaunch solely to repeat the review.**
No paid launch, retry or stop was performed by this audit. Its results remain
unaccepted until the actual files and terminal shutdown can be inspected.

## Paid lifetime and scope

[Modal's ephemeral-app documentation](https://modal.com/docs/guide/apps)
does confirm attached `modal run` stops automatically on client exit or server
detection of disconnection. Installed Modal 1.5.1 CLI defaults `detach=False`.
This is an appropriate lifecycle choice for development; it differs from a
persistently deployed app. Server detection and teardown are not documented
as instantaneous or with a strict spending ceiling.

The original `.9582336` calculation uses only the 1440-second execution
timeout. [Timeouts](https://modal.com/docs/guide/timeouts) are per attempt;
[ephemeral container crashes](https://modal.com/docs/guide/retries) can restart
until the platform failure threshold. The 1500-second attached-client lifetime
is the relevant nominal basis across starts. CPU=4.0 and memory=32768 are
soft requests in the actual SDK resource spec; charges can exceed requested
CPU/RAM. The new build adds pytest, so reuse of the old image cannot be assumed.

Claude's revised run-1 reservation .99816 nominal client lifetime + .168384
build reserve is a useful correction, but still omits teardown and runtime
resource overuse. As an explicitly conditional budgeting basis, retaining
1620 seconds (1500 + 120 detection/teardown), 2x requested runtime CPU/RAM,
the .168384 build reserve and .10 margin gives **$1.5463696**. Book **$1.55**
for run 1 and **$1.45** remaining from the same announced $3 envelope.
The overuse factor and teardown duration are assumptions, not platform
guarantees. Tighten later runs to CPU/RAM hard tuples and reserve the entire
proposed paid lifecycle before any later invocation. Builds, failures and
timeouts consume the envelope; success or image reuse must not reset it.

The direct fixed source performs only learned b16, memory_off b16 and learned
b2 at N32, filler0, seed99. Each train call has four updates: one warmup,
two measured, one profiled. This is a dev attribution probe, not registered
timing, accuracy, population evaluation or campaign evidence. No candidate
optimization or checkpoint-resume implementation has yet been audited here.

## Reporting defects independently reproduced

All actual remote/GPU operations were substituted in the CPU fixtures.
Invoking the actual local entrypoint with child returncode 7 or "timeout"
returns normally, retaining the nonzero value only in run.json. Invoking
the actual hotspot main with a first-config exception writes a stopped
hotspot.json but returns normally. Thus even client/child exit 0 does not
establish success at this revision.

For current run 1 require returncode 0, hotspot status complete, the exact
three configs, two finite measured entries and one finite profiled timing
per config. The current artifact schema does **not** export all four
on_update rows, update IDs or a warmup row. Four actual callbacks are inferred
from the frozen source and successful control flow, not independently counted
from the output. Preserve that evidence limit; do not retrofit historical
rows. Future revisions should export those counters/progress explicitly.

Before run 2, Claude has agreed to propagate nonzero/timeout exits, make
scripts exit nonzero on non-complete status, preserve failure manifests,
use hard resource tuples, and reserve each later run including teardown.
These are proposed changes, not verified fixes yet. The manifest must also
cover remote-call exceptions and distinguish build/outer-timeout/host-loss
outcomes that may bypass the entrypoint. Save launch identity and app ID
early enough for scoped recovery; preserve partial or missing artifacts
as failed/uncaptured rather than successful evidence.

## Frozen-reference parity preparation

The proposed read-only reference mount must bind the archive bytes, commit
2fda0d4 and memsub source hash `048df640…`. Record the actual reference and
candidate code consumed by each side. An in-process comparison needs real
module isolation: changing sys.path does not reload a cached `memsub` package,
and shared imports or monkeypatches can accidentally compare the candidate
with itself. Separate interpreter processes are a straightforward way to
avoid that; a proven namespace-isolation design can also work. Include a
deliberate candidate perturbation that makes the comparison fail.

Parity should cover forward outputs, loss and gradients on the actual
optimized path with declared FP32 tolerances; any exact checkpoint-resume
claim requires the actual resume consumer and matched optimizer/RNG/data/step
state. No such claims are accepted from the current attribution probe.

Local substituted probes are retained in
`codex-261006-p2p5-dev-52b3da-plan-checks.json`; an independent live read is
retained separately in `codex-261006-p2p5-dev-19f51b9-live-state.json`.
No source changes or controller/run-manifest writes by this audit.
