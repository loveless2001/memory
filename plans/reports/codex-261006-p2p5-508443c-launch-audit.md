# P2.5 profile: launch provenance verified, result pending

Reviewed #gravity 21465 at frozen source commit
`508443c84391d2e4947a68fd07fafc295f481010`. The redeploy/spawn evidence matches
the reviewed single-profile clearance in 21464. No new execution is needed.

Deployment attempt 2 records `EXIT_STATUS=0`, the three functions and the
required mounts; the spawn log records one saved call and `EXIT_STATUS=0`.
The original failed-deploy log retains its previously audited SHA256. The
launch provenance matches the complete runner/profile/shared-logic/memsub
identity from the 508443c audit, the current local source, the source commit
and the recalculated profile ledger. Scoped source files remain clean.

- App: `ap-w0KWMJST1Dfg5ipxZQV7QV`.
- Call: `fc-01M48EPG6ZYYEQYR1ER9DRDFHX`.
- Actual deployment: **2026-10-06 11:13:22.850915 UTC**.
- Spawn: `1791285212.1514747` (**11:13:32.151475 UTC**).
- Absolute deadline: `1791287912.1514747` (**11:58:32.151475 UTC,
  18:58:32.151475 Bangkok**), exactly 2700 seconds after spawn.

Independent read-only live checks at **11:15:57–11:16:06 UTC** find the
expected named app bound to this exact app ID, deployed with two listed tasks
and two matching containers. The guard contains this app ID, call ID and
deadline, only `start1`, and the reaper's `first_tick` at
`1791285325.5507882`. The attempts Dict contains only
`profile-l40s#attempt1: true`. A nonblocking call read returns **pending**.
Two app-level containers are consistent with the GPU worker and scheduled
CPU reaper; container-list rows alone do not identify their individual
functions. They are not evidence of two GPU profile executions.

The saved collector log records pending, before-deadline, successful reads
at 18:13:46 and 18:15:48 Bangkok. Its latest status agrees with the independent
call read. No collector, source, guard or attempts state was modified by this
audit; no extra profile or paid proof was launched.

Reported object-filtered usage at this snapshot is **$0.06215959**:
profile app .06195527, failed deployment .00008124, proof .00012308.
The profile app includes L40S .04441701, CPU .00962002, memory .00762016,
network egress .00029808. No separate rows returned for the inspected image
IDs. This is a usage snapshot, not a final invoice or complete settled spend.
Retain **$2.605549225** combined reservation under the same approved $3:
proof .052740625 + proposed profile/lifetime 2.3844246 + failed-build .168384.
Do not reset the budget or release retained reserves based on early billing.

The raw app/container/lifecycle/guard/attempts/call/billing observations,
launch provenance, deadline, reservation and hashes of consumed files are
saved in `codex-261006-p2p5-508443c-launch-verification.json`.

Continue the existing collector and reaper within this clearance. At terminal,
retain exit JSON, progress, profile and source-bound usable/unusable verdict;
verify shutdown on the saved app ID with zero tasks and matching containers;
reconcile billing. First OOM/error/preemption/unusable result ends the attempt
without retry or workload change. The full campaign remains unapproved.

Launch, an attempt claim and pending state establish provenance and execution
state only. No complete profile, GPU-fit conclusion, update timings, accuracy
or learning result has been independently verified in this snapshot. The
absolute app deadline is an operational boundary, not an ETA for completion;
the nominal reaper scheduling and stop allowances remain explicit assumptions.
