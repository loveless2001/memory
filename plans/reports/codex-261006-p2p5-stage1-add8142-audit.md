# P2.5 option-A dev review: stage 1 and runner v2

Run 1 is accepted as a complete development diagnostic. Proposed GPU parity run 2
is held on reproducible correctness gaps in the parity checker and the no-gradient
scatter path. This review performs no paid launch and does not authorize a campaign
or replace the original registered profile.

## Independently verified

- Eight run-1 files match their bytes in commit `add8142`. The app reports child
  returncode 0, remote wall 787.849 s, and client wall 793.575 s. The hotspot file
  has complete status, exactly learned/b16, memory_off/b16 and learned/b2 at N32,
  filler 0, and two finite measured timings per configuration. Recomputed means
  agree. Its source hash is the original reference
  `048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6`.
- Read-only Modal checks ended at 2026-10-06 12:50:43 UTC. App
  `ap-UUv74AxrTl2LhmY6g128Jk` is stopped, with zero tasks and zero matching
  containers; lifecycle has a stop timestamp. App-only reported usage is
  `$0.53878894`. This is a billing snapshot, not a final invoice or proof of settled
  build cost. Retain the full `$1.55` run-1 reserve.
- The 11 tiny CPU parity cases reproduce bitwise at the stage-1 candidate source
  `d5a4002583c4e37e7bfa86d496c94b86c43decf0e41a62926fb0663baf2b876f`.
  The deliberate delta perturbation fails with maximum relative difference
  `0.6779181889985972`; reference/candidate namespace isolation passes.
  Core/runtime pytest checks pass: 25 tests. These observations concern that
  tested source, not later uncommitted checkpoint changes.
- Runner v2 SHA
  `e20463f42f3506bde8a1671cf321d54670771cb08c8ec874cec5aeee57ed34ac`
  has SDK CPU `(4,4)` and RAM `(32768,32768)` request/limit tuples. Invoking its
  actual local entrypoint with substituted remote results verifies success,
  child rc7, child timeout, remote exception, malformed archive and SIGTERM.
  All failures propagate and preserve a terminal manifest. The actual hotspot
  main exits 1 after an injected first-configuration failure.

## Changes required before GPU parity

The actual checker `compare()` accepts a missing gradient entry and a NaN candidate
gradient. Truncated `zip()` omits the missing entry; NaN can disappear from the
maximum reduction when a finite row is first. It also accepts a small nonidentical
initial weight despite its stated bitwise-initialization requirement. Require
matching tensor shapes, complete parameter key sets, matching per-update gradient
counts and parameter identities, finite tensors, and exact initial equality.
Compare declared numeric metrics/telemetry explicitly, or narrow the declaration.
Repeat the negative fixtures after the repair as well as the meaningful CPU parity
suite. The deliberate delta perturbation alone does not detect these defects.

The optimized scatter unconditionally stores views from the input write buffer.
In the no-gradient path, one 16-byte logical cell now retains a 144-byte backing
buffer, and mutating the caller's input changes the stored cell. The reference
clones, retaining 16 bytes and preserving ownership. Restore the no-gradient clone
while retaining the differentiable-path unbind optimization, or establish an
explicitly changed storage contract and accounting with tests. CPU training parity
does not cover this behavior.

Freeze the corrected candidate tree, checker and runner before launch. The image
mounts the working tree, including uncommitted files; a commit identifier alone
does not bind that consumed tree. The original reference remains unchanged.

## Budget and evidence limits

The proposed run-2 `$1.17` reserve fits after the full run-1 `$1.55` reservation.
With hard tuples, 1320 seconds plus `$0.03` build and `$0.10` margin calculates to
`$1.0083808`. The author's optional 2x CPU/RAM arithmetic calculates to
`$1.1713216`; rounding that basis upward calls for `$1.18`, making cumulative
reservation `$2.73` within the authorized `$3` development envelope. The `$0.03`
build allowance assumes reuse of the existing cached build layer. A new build or
retry needs a new within-envelope reservation; this does not grant an automatic
retry. Add `timeout --kill-after=15s` so SIGTERM cleanup cannot leave the client
unbounded. Disconnect/teardown time remains an allowance, not a platform guarantee.

The manifest field `charge_bound_usd=0.9582` remains function-only arithmetic and
must not be used as the cumulative app/build budget bound. Local fixtures do not
prove remote shutdown, build-failure reporting, SIGKILL handling or host-loss
behavior.

Original run-1 artifacts lack a full update-index table; source implies four
updates/configuration, but this review does not fabricate missing rows. Profiler
counts show substantial backward bookkeeping and synchronization activity. They
do not prove the time saved by removing any particular operation. Several labelled
CPU totals are zero and cannot attribute critical-path time. Learned/b2 versus
memory_off/b16 changes both arm and batch size. No observed GPU speed-up, learning
result, original-profile replacement or laptop crash-cause conclusion follows.

The reported full-suite baseline failures have not been independently reproduced
in this review. Keep the historical `independent-stop-verify.json` bytes intact;
if its console trailer needs JSON hygiene handling, create a parsed sidecar with
an explicit historical-file exception rather than overwriting audited evidence.

## Reproducible evidence

- `codex-261006-p2p5-dev-run1-terminal-check.py` and `.json`
- `codex-261006-p2p5-dev-v2-failure-check.py` and `.json`
- `codex-261006-p2p5-stage1-parity-counterexamples.json`
- `codex-261006-p2p5-stage1-tiny-cpu-parity/parity.json` and its `.log`

The counterexample file records checker SHA `1408d91b...`; the only subsequent
checker change in `add8142` is CUDA garbage collection, outside `compare()`.
No implementation source, historical run evidence, controller journal or remote
application was modified by this review.
