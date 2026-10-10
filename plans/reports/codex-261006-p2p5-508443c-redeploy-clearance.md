# P2.5: build-import fix accepted; one reviewed redeployment cleared

Reviewed #gravity 21463 and commit
`508443c84391d2e4947a68fd07fafc295f481010`. The lazy import fixes the
reproduced build-stage failure. **Clear one reviewed redeploy and, only after
successful deploy, one spawn of the still-unstarted L40S timing/fit profile.**
User 21446's approval of option A in 21436 covers this preparation and the
single profile within the same total $3. No new user permission is needed:
the failed preparatory deployment never deployed successfully or spawned the
approved GPU profile. This review supplies the requested review before
redeployment; it does not permit an automatic retry or a second GPU profile.

## Fix and independent checks

My previous audit verified runtime image mounts but missed import ordering
inside the image-build container. The retained first deployment log demonstrates
that Modal imported the runner before its later shared-logic mount was present.
The failure happened before `_build_environment` began its pip or model work.

Independently reran the two targeted suites: **41 passed in 0.49s**, exit 0.
Additional independent probes, with no remote hydration/build/compute:

- Copying the old runner alone into an isolated directory reproduces the
  missing-shared-file failure. The current runner imports there with `_LOGIC=None`.
- Executing the actual current `_build_environment()` with pip and download
  substitutes completes, checks the pinned dependencies/model revision/files,
  and leaves `_LOGIC=None`. This checks the actual build function's dependency
  path, not a real image build or dependency installation.
- Runtime access without the shared file raises; supplying the unchanged
  shared file exercises lazy loading, caching, environment forwarding, the
  bound marker and whole-app-stop-before-cancel order.
- Actual Modal 1.5.1 file-definition SDK image graphs contain the shared file
  for both the CPU reaper and GPU worker. The reaper remains CPU-only without
  volumes. The source identity correctly binds the updated runner.

Checks are retained in `codex-261006-p2p5-508443c-build-checks.py/.json`.
The source diff changes only the runner's eager load and wrappers, plus the
new regression test and historical failure log. Shared logic, proof runner,
profile script and memsub source are byte-identical to 5b89067. The accepted
remote CPU self-stop proof therefore remains applicable to the shared stop
path; no proof rerun occurred. These checks establish the corrected import
path, not successful deployment, GPU fit, timings or learning results.

## Retained failed deployment and live state

First deployment app: **`ap-550Raz3HVjefV149OWcrXu`**. The live lifecycle has
creation at **2026-10-06 11:01:45.760194 UTC**, no `deployed_at`, and stop at
**11:02:02.687512 UTC**, duration **16.927318 seconds**. Independent read-only
checks at **11:08:44–11:08:50 UTC** confirm stopped, tasks=0, matching containers=0.
Both profile guard and attempts Dicts return NotFound; the profile output
directory is absent. The preserved failure is preparation evidence; no GPU
profile call or claim was made.

Failure log:
`plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-l40s-profile-v1.deploy-attempt1-failed.log`
(EXIT_STATUS=1), SHA256
`5f3f47988892d98528b4d0f5245a8bb2d803f0e74f8f1c55ad45096ff5b68759`.
It records bootstrap image `im-0XrXDp0cVeNVmwutXxnq4E` and failed function-build
image `im-tZEhGIaVTsgX4GyCjTKvex`. Keep this log unchanged and use separate
attempt-2 deployment output.

The live billing report now includes **$0.00008124** for the failed app:
CPU .00007422, memory .00000500, network egress .00000202. No separate rows
were returned for those two image IDs. The prior proof app remains reported
at **$0.00012308**. These are object-filtered usage snapshots, not a final
invoice; missing rows do not establish settled zero cost.
Raw live state and billing are in `codex-261006-p2p5-508443c-live-check.json`.

## Same total budget, including the failure

Do not discard the failed build cost or reset the approved cap. Retain:

| Reservation | USD |
|---|---:|
| Accepted CPU proof, full original reserve | 0.052740625 |
| Proposed profile deployment and paid lifetime, including its build and margin | 2.384424600 |
| Retained failed deployment, another full original build allowance | 0.168384000 |
| Combined | **2.605549225** |
| Remaining under the same $3 total | **0.394450775** |

The extra failed-deployment allowance equals the original 1200-second
build reserve with requested 4 CPU cores/8 GiB and assumed 2x overuse. It
conservatively retains a full build allowance for the observed 17-second
CPU preparation failure rather than charging only its currently reported
usage. The original .25 fixed margin remains in the proposed profile reserve.
Build resources, reaper schedule and stop latency remain the previously
declared assumptions; this arithmetic is not a platform hard spending limit.
Reconcile later billing without reducing these retained reserves at launch.

## Frozen identity and execution boundary

- Runner `6406e6415def0e28ccccbd67c0a424a5c052329c914c49828661bd89cf594e28`.
- Shared logic `32bb3a3a38bf375e4c9107e4b3d7dc4c6392076cb5ba55f7c599fab644329e6c`.
- Profile script `b5b0746a40afbd7c9feb2bcf7aa6967189903673829cf2a8d4a2afc25237a08c`.
- Memsub tree `048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6`.

From project cwd, preserve a separate attempt-2 deploy log and exit status:

```sh
.venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py
```

Only if that succeeds, run once:

```sh
.venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py spawn
```

Save deployment app ID, actual frozen hashes, launch provenance, absolute
deadline and call ID. Four fresh configurations, 40 total updates and four
dev-batch timings remain the complete profile: batch16/N32, seed99/dev4242,
full-gradient FP32 token-serial contract, TF32 off. The original profile
watchdogs, attempt claim, independent reaper, collector and validation apply.
First further deployment error or profile OOM/error/preemption/unusable result
ends this clearance; preserve evidence and stop. No automatic retry, extra
profile, altered matrix, laptop rerun or full 18-cell campaign is authorized.

Use the existing collector for terminal evidence and shutdown, then verify
the saved app ID is stopped/unlisted with zero tasks and zero matching containers.
Review actual bound artifacts before proposing any campaign cost or scientific
claim. This review performed local probes/report writes and read-only Modal
queries only; no deployment, GPU invocation or paid proof rerun was launched.
