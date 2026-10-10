# Stage A billing verification after wait 31

At 2026-10-08 21:05:47–21:05:49 UTC, three read-only Modal CLI calls completed with exit 0: billing report, app list and container list. The exact commands, timestamps and exit codes are in their `*.capture.json` files. No app/function was started or stopped, and no local GPU was queried or used.

The hourly billing query covers **[2026-10-08 19:00, 21:00) UTC**, with a resource breakdown. Both requested hourly intervals had ended at capture. Filter: exact `object_id=ap-cCYlrnTz0Tj7tcm7TYovau`, environment `main`, description `memsub-m4-sgm-p2p5-stage-a-read-escape`.

| Reported resource | USD |
|---|---:|
| L40S | 0.74966681 |
| CPU | 0.07273690 |
| Memory | 0.09841780 |
| Network Egress | 0.00029966 |
| **Total** | **0.92112117** |

All four rows belong to the interval starting 19:00 UTC. The report returns **no cost row for the interval starting 20:00 UTC**. The total exactly matches the earlier 20:29 UTC preliminary snapshot; reported delta is $0.00000000. Decimal arithmetic, filtered rows and the earlier snapshot hash are retained in `app-billing-summary.json` and `app-billing-rows.json`.

This is the currently reported app-attributed cost, not a final invoice or a guaranteed settled total. Modal documents that hourly reports include full intervals only, that collection delays can occur even after an interval ends, and that granular report costs are before credits, reservations and the network-egress allowance. See [CLI interval semantics](https://modal.com/docs/cli/latest/billing) and [billing reporting and delays](https://modal.com/docs/guide/billing). No finality marker is returned in this capture. There may genuinely have been no billable activity in the 20:00 interval; absence of a row alone cannot certify that or exclude subsequent backfill.

Fresh app-list verification shows the exact app **stopped**, **0 tasks**, stopped_at `2026-10-09 03:28:25+07:00` (20:28:25 UTC). The workspace container list is empty. This independently confirms no live app/container work at this snapshot; it does not settle billing.

A0 and A1 remain the only completed arms. A2 remains **NOT RUN / UNEVALUABLE**. App/hour/resource-level billing does not separately attribute charges to A2 or explain its failed scheduling. Do not reinterpret a missing cost row as an A2 experiment result or a guaranteed zero charge.

No additional compute is authorized by this check. The existing owner-planned 21:10 UTC read-only snapshot can provide a later comparison; this audit does not re-arm geometry or create another monitor. Wait 31 has been handled.
