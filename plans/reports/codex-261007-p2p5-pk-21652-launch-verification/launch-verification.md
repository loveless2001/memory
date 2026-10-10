# Attempt-2 launch verification — gravity21652

**Launch handoff verified read-only.** Snapshot: **2026-10-07 07:00:26–07:00:50 UTC**, environment `main`, source `537ace8bc30a5ec486e521b6adf7ee3c340abf9f` with no tracked diff. [Machine-readable evidence](launch-verification.json), [verification script](verify-launch.py), and the retained live app/container listings and first-cell record snapshots are in this directory.

All nine reported app IDs and call IDs match local launch provenance. Every slot has one live container/task, its call is pending and its admission Dict contains only `start-1`. Each slot guard and the nine-entry controller registry agree with provenance on app ID and immutable deadline. Lifetimes match the frozen v6 ledger, every candidate fits the original controller horizon, and provenance timestamps preserve the fixed longest-first spawn order. The controller remains bound to `ap-suOdTgdc8PNSfZ3jbnsesa` and deadline `1791408417.2529736`; no reset is observed.

All **18 registered cells** have acknowledged epoch-1 `STARTED` records. Their remote identities match the launch expectations, including repaired runner, memsub, grid, output registry/schema and price hashes. No FAILED/LOST state is present in this snapshot. The four memory-off cell records acknowledge generation steps through **100, 100, 100 and 150** respectively; the other fourteen records have no acknowledged generation yet. These are asynchronously collected startup/progress records, not a simultaneous training measurement. Checkpoint payload bytes, numerical behavior and scientific outcomes were not audited here.

The readings app is deployed with zero tasks and no containers; its guard and admission Dicts are absent. Readings remains behind the existing all-cell validation and exactly-once gate. The owner collector process (PID1543151) is live, and its first pass reports all nine calls pending. Its loop performs collection and shutdown checks, without spawning readings or training retries.

No new corrective action or added execution is required by this snapshot. Continue the already approved campaign and existing collection/validation sequence. The $259.99 reserve remains conditional, actual billing remains unsettled, and the completion estimates in the handoff are not independently established by these first records. No learning or reserved-readings result exists yet.

The reviewer performed no workload invocation, deployment, stop, remote write, journal update, source change, commit or push. Local reviewer evidence only was written.
