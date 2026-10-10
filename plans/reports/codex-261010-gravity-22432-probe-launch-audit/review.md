# Authorized CPU probe: launch and smoke-gate audit

**Launch/smoke gates PASS; the full numerical run is still RUNNING.** Read-only verification of the user's scoped go (#gravity 22424), implementation clearance (22430), launch handoff (22432) and stage progression (22435/22438). No launch, restart, retry, model load, real probe fit or profile was performed by this auditor.

The detached controller PID is 216781. The initial live S1 check confirmed Python PID216789 in `pkprobe-s1-1791573872.scope` with `memory.max=4613734400`, `memory.swap.max=1258291200`, eight-thread environment/pool settings and zero OOM/kill events. Sources matched the reviewed 935f91d package and the initial adapter content hash was `ef5741865072c27d7620d33ddbcb2d3c773e1e1ac5e23a8432b6f0e30d15c2f9`. The first audit artifact snapshot crossed S1 process completion; a missing PID in that later snapshot is consistent with the recorded successful terminal exit.

## Independently validated terminal smokes

S1 exited 0 at 19:26:05Z; S2 exited 0 at 19:27:15Z. Both actual receipts independently pass the immutable reviewed validator: final run/result agreement, source/feature binding, frozen specification and finite records. Their initial adapter hashes match. Their terminal files have been copied into this audit folder and hash-bound.

Fresh real S1 admission recomputes to estimate **2537.3524964670205 seconds**, twice-estimate wall **5074.704992934041 seconds**, and controller ceiling **5075 seconds**. It admits under the registered 14,400-second full-stage ceiling. Components are model load16.897651s, capture12.571026s per episode ×160, fit175.671305s, bootstrap0.058270s, output33.361122s and the fixed300s margin. No model-free or unintended M10 admission was used.

S1's INVALID label and S2's INCONCLUSIVE label both have `reading.read=false`. They are operational smoke outputs, not scientific findings from the full 64-episode readout. The registered protocol proceeds after mechanical receipt success and valid admission; this audit does not reinterpret those tiny-smoke metrics.

## Full run at the audit snapshot

The full stage started at 19:27:21Z (02:27:21 Bangkok). Scope `pkprobe-full-1791574041.scope` is active. Python PID220813 is wrapped by timeout PID220812 with `--signal=KILL 5075`; the CLI wall is5075 and S1/S2 paths are the registered ones. Actual full-scope caps are again4613734400 RAM bytes and1258291200 swap bytes. The19:28:36Z snapshot showed memory.current2913689600 bytes, zero swap usage and no OOM/max events; process thread environment values are8.

At19:29:46Z, the full run/status are RUNNING, the source map and frozen config match the reviewed package, and its initial adapter hash matches both smokes. Durable capture progress is **20/96 train episodes**; heldout capture and the full terminal result are pending. No result.json exists yet. The trained probe's eventual reading remains unverified.

## Stop point and monitoring

Read-only terminal wait **#50** is registered for controller PID216781 or `CHAIN COMPLETE|CHAIN STOPPED` in chain.log, with a100-minute monitoring timer. This timer does not extend the worker's5075-second execution limit. On wake, audit the full exit/status, complete JSON/feature/source/init bindings and registered control/readout rules; report in #gravity. No polling, dispatch or rerun is part of the wait.

The existing one-shot/no-retry, local CPU/$0, eight-thread and4400M/1200M memory limits remain. Prior evidence, including the unintended M10 preservation and the earlier negative campaign findings, stays protected. `manifest.json` and `SHA256SUMS` bind this audit's retained snapshots and copied terminal smokes.
