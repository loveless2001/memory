# Independent launch verification

The approved PK proof launch is independently verified. This is running-state/provenance evidence, not proof acceptance or a scientific result. Only read-only checks and new reviewer-owned reports were performed; no deploy, spawn, collect, stop, retry, controller-state modification, commit or push was performed.

- User approval21577 binds a $8.57 planning cap to the frozen proof. The saved reservation is $8.560027 under its disclosed assumptions; this is not observed or settled spend.
- App `ap-NtWFBICc4quJgMn9gUqeTB`, the launch head `d62602c`, all nine expected identity hashes and the seven unique call IDs match the approved package. Current bound file hashes are unchanged.
- Current head `92267bc` differs only by four saved deployment/spawn/provenance/call artifacts. It is not source drift.
- Live main-environment app inventory identifies the bound app as deployed. The live guard binds that exact app ID and the saved deadline, **03:48:01 Bangkok, October7**, exactly6600 seconds after spawn. Its first reaper tick is recorded. The observed admission keys are within the fixed allowances.
- The02:01 Bangkok snapshot shows `A-start-1`, seven pending calls and the detached collector process alive. At02:03:31, a separate bound-function read shows `run_unit` with **one total runner, one running input and backlog5**; `reaper` has zero current runners. The GPU function's frozen configuration is A100-80GB with max_containers=1. The earlier two-container app inventory includes the separately scheduled CPU reaper and should not be read as two GPU runners.
- Collector logs/status show the existing loop polling, without final shutdown at the snapshot. No second collector or additional launch was created by this reviewer.

Actual settled charges, GPU equality/resume outcomes, completed timing, proof acceptance and final zero-task/zero-container shutdown remain for terminal audit. The ETA is an estimate; the guard deadline is the actual configured boundary, subject to the already disclosed scheduling/stop assumptions. Campaign work and reserved readings remain unapproved.

Evidence: `codex-261007-p2p5-pk-21579-launch-verification.py/.json/.txt` and `codex-261007-p2p5-pk-21579-live-function-stats.json`. Snapshots retain their individual timestamps and do not imply all call states stayed unchanged between reads.
