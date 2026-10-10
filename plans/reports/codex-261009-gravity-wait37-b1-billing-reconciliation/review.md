# B1 wait #37 billing reconciliation

The scheduled after-05:05Z check is complete. Both the 03:00 and 04:00 UTC hours have closed. The bound B1 app `ap-ROPSmaSeABkUyr4X1d4RD2` reports **$0.71087544** in attributed usage, unchanged from the independent 04:21:29Z snapshot. The difference is **$0.00000000**. This remains below the B1 campaign's approved $2.50 at this snapshot.

| Closed UTC hour | Reported USD |
| --- | ---: |
| 2026-10-09 03:00 | 0.06919454 |
| 2026-10-09 04:00 | 0.64168090 |
| Total | **0.71087544** |

| Resource | Reported USD |
| --- | ---: |
| L40S | 0.57849977 |
| CPU | 0.05612931 |
| Memory | 0.07594663 |
| Network egress | 0.00029973 |

The calculation uses Decimal sums of exactly seven resource rows for this app ID in environment main, from a read-only hourly billing query for `[2026-10-09T03:00:00Z, 2026-10-09T05:00:00Z)`. It is not a workspace aggregate or the launch reservation. Both sums independently agree. Raw data, prior snapshot, timestamps, and comparisons are retained in `reconciliation.json`, `billing-report.json`, and `previous-snapshot.json`.

Fresh read-only app/container listings verify the app **stopped**, tasks **0**, and matching containers **0**. The recorded stop time remains 04:16:07Z. The existing fail-closed shutdown verifier independently accepts these rows. No stop command, collection GPU, training, retry, or other new compute was performed.

The amount is a **provisional usage report before credits and included allowances**, rather than a finalized invoice. Closing the reporting hours and observing an unchanged total do not certify that all accounting backfill has arrived. Modal documents possible collection delays and recommends a buffer beyond the queried interval; it also explains that granular reports precede credits and included egress allowances. [Modal billing documentation](https://modal.com/docs/guide/billing)

Wait #37 is fulfilled. No additional billing polling or paid continuation is started by this reconciliation. B1 remains a valid PARTIAL routing result with no observed dev gain; billing reconciliation does not change its scientific readout. Separately, B2 v0.3's CPU package was cleared at 24b1432 in #gravity 22159, while the user's scoped $17 approval remained pending at the latest channel snapshot.
