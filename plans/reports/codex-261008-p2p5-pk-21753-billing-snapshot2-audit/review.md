# Billing snapshot 2: arithmetic and package integrity PASS

Verified saved evidence at owner commit 13d6fe5. Exact Decimal arithmetic gives an app-attributed campaign total of **$126.44196052**, up **$0.00085965** from **$126.44110087**. The entire campaign delta is the controller-r2 17:00 UTC row; its subtotal changes from $0.08021808 to $0.08107773.

The nine slot subtotals remain $119.27095429 in total, the readings app remains $7.08987892, and attempt-1 controller remains $0.00004958. All slot/readings/attempt-1-controller rows match the prior snapshot. Both snapshots contain 64 campaign rows with identical app/hour keys; no selected campaign row occurs after 17:00 UTC. The unrelated echo-puzzle-a12 rows, including later added hours, are excluded.

Snapshot 2 and the empty stderr file match committed bytes. The refreshed three-entry terminal-package index matches all listed metadata hashes and committed contents; the new Markdown hash is `24001932642fc701aef53d5e69ec756ff0ace2390fbf44f8a2e60473fdb98568`. The original reconciliation JSON remains explicitly the first-snapshot record; the new snapshot is separately described and git-bound.

Billing remains PRELIMINARY. Later hourly backfill, the unattributed attempt-1 image build, and the separate $8.57 proof hold remain unresolved. These totals are not a full settled-account reconciliation or new spending authorization.

Scope: saved snapshots, baseline app identities, index files and documentation only. No live API, new app-state check, model evaluation or campaign modification. The fetch instant and successful command exit are reported by the owner; the raw JSON has no embedded fetch-command provenance. Empty stderr is independently verified. Probe test-count claims will be checked with its frozen implementation package, not through this billing audit.

Reproduce with `python plans/reports/codex-261008-p2p5-pk-21753-billing-snapshot2-audit/check-billing.py`. Exact totals, all checks and consumed file hashes are in `evidence.json`.
