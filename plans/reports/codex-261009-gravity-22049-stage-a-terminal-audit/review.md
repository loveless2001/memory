# Independent Stage A terminal review and geometry clearance

Terminal artifacts accepted: **two valid arms, A2 unevaluable, paid app shutdown
verified independently**. The client exited 124 at 20:28:32Z while A2's remote
call was pending; cleanup exited 0 at 20:28:39Z. The bounded stop found the app
already stopped. A fresh independent query confirms bound app
ap-cCYlrnTz0Tj7tcm7TYovau stopped, zero tasks and zero containers.

All twenty owner terminal payload hashes and both binary hashes match, together
with the eleven launch-package hashes. Both arm classifications were recomputed
from retained telemetry; probe recipe, devseed4242, saved parameter hashes, and
TF32=false bindings verify. No model forward or paid compute occurred in this review.

| arm | result at update100 | pooled absent-read weight | kept through sampled updates |
|---|---|---:|---|
| A0 unchanged | valid / escaped | 0.9927543895319104 | false |
| A1 global lr .0003 | valid / partial | 0.6523364614695311 | false |
| A2 supervised routing | not run / unevaluable | no observation | no observation |

A0 reaches 0.9960536565631628 absent weight at update25. A1's trajectory is
0.0467013, 0.4886660, 0.5301996, 0.6111423, 0.6523365 at updates0/25/50/75/100.
The lower global rate reduces early absent weight on this one-seed dev screen,
but neither observed arm meets the <=.2 retention band. A1 does not isolate
address-specific learning rate or establish H2, useful discrimination or learning.
No kept-arm Stage B condition is demonstrated among observed arms.

The independent start-Dict read matches the frozen owner snapshot: deadline, A0,
A1 only; both claims refer to the same container. A2 has no claim, returned result,
telemetry or saved parameters. Under the audited pretraining claim guard this
establishes no A2 training start. It does not determine the scheduling delay's
cause or settle any infrastructure charges. A2 remains untested rather than
classified as a negative intervention. No retry, extension, or Stage B is cleared.

## Billing

The retained hourly report is filtered by exact app id, yielding **$0.92112117**
for the completed 19:00Z hour. The 20:00Z hour was incomplete at capture.
This is preliminary app-attributed usage; final/backfilled billing remains
unverified. The authorized cap is $4 and the audited reservation $3.4198416.
Obtain a later usage snapshot after the 20:00 hour closes; do not describe A2's
total infrastructure charge as conclusively zero from the absent training claim.

## Geometry: code/index cleared; queue behind the active local pilot

**CLEAR one $0 local no-optimizer geometry pass** using the owner's exact command
and fresh output directory, after the currently active smollm pilot finishes and
GPU availability is rechecked. Claude remains launch owner. No new user approval
is needed within the already scoped Stage A geometry readout.

- Index commit951f700, geometry-index-v1.json SHA256
  98d9c3835c9a5377a696bf5828e6b42a33655543224bca1729088856d1e0bb87.
- Exactly two entries: A0 and A1 final parameters at step100, geometry kind only.
  All six input hashes match. Parameter hashes equal their manifests; both PilotConfig
  endpoints are step100. No A2 entry, gradient entry, init reconstruction or new
  optimization/evaluation population is added.
- Cleared diagnosis script is unchanged: SHA256
  e9131a62ac57cca62915ae233914315412e302bf5ab954351f20544578311ea7.
  It replays the same seed4242 dev population, uses no-grad geometry, and requires
  endpoint absent-weight/occupancy replay checks. It retains earlier results if an
  entry errors and stops at that error.
- memsub tree hash matches the index (2eee4228...). The local .venv-gpu metadata
  query reports torch2.7.1+cu126, transformers4.55.2 and CUDA available. The diagnostic
  independently rechecks these identities and pinned Qwen files before model work.
- Whole-process timeout3600s, first-error stop, no retry or CPU fallback; retain
  console, exit status, both geometry outputs, run.json and post-run GPU cleanup.

```bash
timeout --signal=KILL 3600 .venv-gpu/bin/python scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py --index plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/geometry-index-v1.json --out plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/geometry-run-v1
```

At the resource snapshot, smollm controller PID2996958 and its arm PID2997017
were active on the local GPU (~77-83% utilization, ~1.34GiB used). Preserve that
experiment. Launch geometry after its controller exits and a fresh resource check
shows the compute lane idle; do not overlap the two experiments.

Evidence: live-terminal-state.json, verify-terminal-and-index.py, verify.log/exit,
verification.json and SHA256SUMS.txt. Previous wait25 is fulfilled. Resource and
later billing waits replace polling while these remaining readouts are pending.
