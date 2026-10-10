# Independent Stage A v0.4 launch review (gravity 22005)

Decision: **CLEAR the one already authorized Stage A launch** at commit
`fe43fc9f07f9f935be7e28950852081b392c6322`, using the committed
`plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/launch-stage-a-once.sh`.
User 21977's conditional Modal approval applies; no further approval is needed for this unchanged scope.
Claude remains launch owner. This review performs no paid launch or model forward.

## Verified evidence

- All eleven v0.4 package SHA256 bindings match; the launch guard's paths are clean.
  The train script is unchanged from v0.3, and the current memsub source hash equals
  the original bound seed-0 probe manifest.
- Independent focused suite: **28 passed in 11.80 s, exit 0**. This includes the old
  fake-clock reproducer: version setup crosses the deadline and no child is launched;
  insufficient time after setup also refuses. Entry within the 90 s margin arms nothing.
- Worker guard is armed before Dict RPCs/version imports. The training child starts
  in its own session, with a separate deadline guard targeting its process group;
  its relative timeout is bounded by remaining campaign time. A real process-group
  kill and cancellation test pass. Guards are cancelled on the normal/refusal/timeout
  return paths. Warm A0/A1/A2 use isolated temporary directories.
- Actual shell wrapper, copied into an isolated fixture with fake launch executables:
  exact timeout argv verified; client rc 7 still reaches cleanup; cleanup rc 1 is
  retained in its own exit marker; a repeat launch refuses before executing the client.
  The wrapper's final shell rc alone is not a success signal: inspect both exit markers
  and cleanup.json. No fixture invokes Modal or CUDA.
- Actual cleanup CLI on a missing run.json exits 1 and persists unresolved status
  rather than asserting shutdown. Cleanup reuses the unchanged strict PK verifier:
  bound app stopped/unlisted, zero tasks, and zero containers; query failures cannot pass.
- Owner's hash-bound mutation evidence reports 21/21 caught. The code and retained
  failure summaries were inspected; these mutation runs were not repeated by this audit.

## Scope and remaining evidence

One ephemeral run; A0 then A1/A2 only if A0 is valid and escaped at update 100.
At most 3 x 100 updates, seed 0 only, batch 16, fixed dev population, no reserved
test population, no retry or fallback. A1 changes the global learning rate. A2 uses
privileged training correspondence supervision; its retention cannot establish
useful discrimination or an unsupervised remedy. Stage B remains separately gated.

The $3.4198416 charge reservation includes the 25% CPU margin and 300 s app-stop
allowance under the $4 authorization. It is not a proven platform billing ceiling;
the proposal now states that limitation. Independent server-side guards address the
earlier unbounded arm-work/deadline issue. After launch, inspect the recorded app id,
both exit markers, raw artifacts, strict shutdown evidence, and actual billing.
An unresolved cleanup requires action on that bound app, not a repeat training launch.

Terminal review must preserve partial outputs if any arm fails. The proposed local
geometry pass still requires its new hash-bound checkpoint index and exact argv to
be reviewed before execution. No learning result is asserted by this launch clearance.

## Audit artifacts

- independent-focused-tests.txt and independent-focused-tests.exit.txt
- independent-checks.py, independent-checks.json, independent-checks.log and its exit marker
- SHA256SUMS.txt (audit bundle integrity)
