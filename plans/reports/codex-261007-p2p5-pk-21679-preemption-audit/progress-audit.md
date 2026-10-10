# Progress and restart-boundary audit — gravity21679

**Read-only snapshot PASS**, environment `main`, **2026-10-07 09:32:20–09:32:41 UTC**. No operational intervention is indicated by this snapshot. Source remains `537ace8bc30a5ec486e521b6adf7ee3c340abf9f`, with no tracked diff. [Machine-readable evidence](progress-verification.json), [audit script](verify-progress.py), raw live listings and collected record/worker-argument snapshots are retained here.

Both memory-off slots are COMPLETE at epoch 1. The four fetched output bundles independently pass the frozen output-hash, population, row/schema, telemetry, tensor registry and finite-value checks. Both bound apps are independently observed stopped, with zero tasks and no containers. This establishes four valid completed cells, not a comparative or reserved-readings result.

The other seven calls remain pending, with one observed container per slot and all fourteen authoritative cell records STARTED. No deadline or registry binding changed from the independently captured launch snapshot. The controller retains its original app ID, price hash and absolute deadline.

| Restarted slot | Admitted starts | Remaining start allowance | Latest acknowledged steps, seeds 0/1 |
|---|---|---|---|
| single_cell-n32 | 1, 2, 3 | 1 | 1000 / 1050 |
| oracle-n32 | 1, 2 | 2 | 700 / 700 |
| random_fixed-n32 | 1, 2 | 2 | 1000 / 1000 |

All other slots have only start-1. The restarted cells' canonical predecessor snapshots pass their digest/epoch checks and retain the expected identities. Actual latest worker arguments match the inherited checkpoint step, digest and path: single-cell resumes from step250, oracle from step100, random-fixed from step350. Later acknowledged progress is present. This verifies the observed recovery metadata and argument binding; checkpoint payload bytes and numerical equivalence were not re-audited. Platform preemption as the termination cause is attributed to Claude's reported logs, rather than independently established by these records.

Readings remains deployed and idle, with no containers or guard/admission names. The collector process PID1543151 remains live. Continue the existing collection and all-cell validation gates within the unchanged admission/deadline limits. No additional starts, deadline reset, rescue, expanded spending or analysis access is cleared by this status review. Incomplete cells remain unevaluable for the campaign decision.

This is an asynchronous snapshot, not a simultaneous progress measurement or an ETA. Charges were not reconciled in this check. No remote workload invocation, stop, deployment, write, journal update, shared-source change, commit or push was performed; only reviewer-local evidence was written.
