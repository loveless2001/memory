# B3 package handoff v3 — ledger/procedure correction (codex 22521/22522; NOT a launch)

Addendum to `b3-package-handoff-v2.md` (e551872, 0568f656…; unchanged, bound by codex's v2 re-audit, report sha
e6887f43…). **Replaces v2 §4 entirely.** Everything else in v2 (and the v1 sections it keeps) stands.
No model, cloud or paid action. Paid clearance and the user's $17 cap remain pending.

## Commits since e551872
- `c6441d6` fix: `WATCH_POLL_S = 60.0` constant; `watch(poll_s=WATCH_POLL_S)`; ledger window includes one poll of lag;
  test pins the window, the reservation, and that watch's default poll IS the ledger constant; harness v5 (M18 drops
  the poll lag from the window, M19 decouples watch's default poll from the constant).
- this note + `b3-mutation-checks-v5.json`.

Runtime behaviour is unchanged (watch already polled every 60 s); only the ledger, its test and the constant changed.
Evidence v5: baseline 42 passed; **19/19 CAUGHT by the exact expected test id**.

## Ledger (replaces v2 §4)
Rate unchanged: **$0.00067854/s** (L40S + 1.25 × 4 CPU cores + 32 GiB; base rates checked against current official
pricing by codex 22516). `max_containers=1`, so billed container-seconds ≤ wall time until the app is actually
stopped. With a healthy PC-side watch the stop is issued no later than:
campaign 23,400 s (spawn → deadline) + backstop grace 120 s + **one watch poll of lag 60 s** + the full cleanup budget
300 s (cleanup_verify gets its whole budget even after a late poll; there is no shared absolute deadline)
= **23,880 s**. Compute reservation **$16.2035352** + $0.10 build = **$16.3035352**; cap ask **$17**, headroom
**$0.6964648**.

Conditions (not enforced by code; the reservation holds only if all of them hold):
- ≤ 5 billed CPU cores; memory billed ≤ 32 GiB; rates unchanged; storage/transfer small and unpriced;
- the PC-side watch runs and stops the app inside the window. Status-call, network and `app stop` tails beyond the
  allowances above are NOT covered. A PC-down period, or a crash loop of rescheduled containers before worker entry,
  is NOT bounded by this reservation (v2 §3);
- **shutdown is established only by `cleanup_verify`'s independent check** (app stopped/unlisted AND zero tasks AND
  zero containers). A stop acknowledgement alone does NOT prove zero billed containers. v2's sentence "post-stop
  verification bills no containers" is WITHDRAWN;
- aggregate billed seconds and the settled total remain unestablished until billing settles; throughput is unprofiled
  (accepted risk: a slow run ends at the deadline with partial evals and no gate readout).

## Unresolved questions
1. Codex: paid-package verdict at this commit?
2. User (after PASS): approve the **$17 cap** for one B3 campaign (procedure v1 §4 as corrected by v2 §3; this ledger;
   storage v1 §6)?
