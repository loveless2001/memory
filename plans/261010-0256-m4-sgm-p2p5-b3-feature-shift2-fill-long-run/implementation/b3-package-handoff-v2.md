# B3 package handoff v2 (for codex package re-audit; NOT a launch)

Supersedes `b3-package-handoff.md` (52cd79b, e533ba77…; kept unchanged: it is bound by codex's REVISE verdict 22517,
report sha c1cb72b3…). Changes vs v1 = the two 22515 blockers fixed with negative tests, the 22516 procedure/crash-loop
/precheck corrections, and an amended ledger window. Everything else in v1 §1 (science), §3 (prior evidence), §6
(storage: ~197 MB peak, ~200 MB allowance estimate, CPU-proxy caveats) and §7 (risks) stands as written.
**No model, cloud or paid action. Paid clearance and the user's $17 cap remain pending.**

## 1. Commits since 52cd79b
- `a7cd135` fix: fail-closed Volume listing/collect, contained worker failures, ledger window; 10 new tests; harness v4.
- `b843724` evidence: `b3-mutation-checks-v4.json`.
Train script `3f653b79…` and memsub `d86639b9…` are unchanged since 52cd79b (empty diff).

| file | sha256 prefix |
|---|---|
| `modal-runners/modal-m4-sgm-p2p5-b3-shift2-fill-long-run-runner.py` | e7abd93048838bf2 |
| `scripts/sgm-p2p5-b3-shift2-fill-long-run-train.py` | 3f653b79fa70b5b2 |
| `tests/test_sgm_p2p5_b3_shift2_fill_long_run.py` | e3c4ba65317fb353 |
| `implementation/b3-mutation-checks.py` (v4) | 9ced6d1d247e199a |
| `implementation/b3-mutation-checks-v4.json` | 68ea065933502e61 |

## 2. Blocker fixes (codex 22515)
1. **Listing errors fail closed.** `_volume_files` treats ONLY `modal.exception.NotFoundError` / `FileNotFoundError`
   as "run dir absent" (Modal 1.5.1 `listdir` surfaces gRPC NOT_FOUND as `NotFoundError`); any other error propagates.
   `precheck` returns `"… listing failed (…): refusing"`; `collect` returns `ok=False` with the error. If the live
   server signals a missing dir some other way, precheck refuses: a safe failure (no spend), to be reported.
2. **No stale pass in collect.** The gate requires `B3/b3_result.json` to be fetched from the Volume IN THIS CALL;
   files left locally by an earlier collect can no longer produce `ok=True` (`files=0` → ok False).
3. **Nothing escapes the worker.** The watchdog and the Dict lookup now run inside the guarded block (body moved to
   `_admitted_start`). `mark_terminal` never raises: a failed write is returned and reported as
   `terminal_write_errors` (or `"no start Dict"` if the lookup itself failed); `cancel_killer` failures are reported,
   not raised. Every outcome is a returned dict, so no exception can reach Modal's function retries.
4. **Tests (42, all pass, capped scope):**
   - absent-path classes → fresh;
   - Timeout/Permission/Runtime listing errors → raise in `_volume_files`, refuse in precheck, `ok=False` in collect;
   - stale local result + absent run dir → `ok=False`, and a real fetch → `ok=True` with `resume.pt` skipped;
   - failed Dict lookup → refusal with the watchdog created 1 / cancelled 1;
   - failed terminal write on the versions, exception and completed paths → reported, not raised, watchdog cancelled.
5. **Mutants v4:** baseline 42 passed; **17/17 CAUGHT by the exact expected test id**. M12–M17 re-insert each
   original bug: guard + lookup outside `try`, terminal write re-raised, catch-all listing, collect ignoring the
   fetch, precheck letting a listing error escape, and the ledger without grace.

## 3. Procedure corrections (codex 22516; replaces v1 §4 steps 1 and the PC-dependence wording)
- Step 1 `precheck` is **resource preparation + check**, not read-only: it creates the start Dict and Volume if
  missing (empty), then requires both to be fresh and memsub bound. Anything but `ok` stops the campaign.
- **Starts vs container attempts:** ≤ 3 admitted starts bounds TRAINING STARTS only. Per Modal's retries guide, a
  crashing deployed container may be rescheduled indefinitely, separately from function retries; startup/refusal/
  crash attempts are NOT bounded by MAX_STARTS. After the deadline, every attempt that reaches the worker refuses at
  entry, but a crash before worker entry (e.g. at import/startup) can loop until the app is stopped.
- **PC-dependence:** zero-container idle is guaranteed only on a healthy completed path. With the PC down, a crash
  loop is not stopped and is NOT bounded by the reservation; the watch/cleanup-verify on the PC is the only stop.

## 4. Ledger (amended window; runner `ledger()`, asserted by test)
Rate unchanged: **$0.00067854/s** (L40S + 1.25 × 4 CPU cores + 32 GiB; base rates checked against current official
pricing by codex 22516). **Window = campaign 23,400 s + watch backstop grace 120 s + cleanup 300 s = 23,820 s.**
With `max_containers=1`, billed container-seconds ≤ wall time until the app stops, which with a healthy PC-side
watch is ≤ 23,820 s (v0.3 counted 23,700 s and omitted the grace). Condition: the watch notices the backstop up to
one poll (60 s) late and `app stop` takes ≤ 60 s (CLI timeout), so the 300 s cleanup allowance must absorb poll lag
+ stop latency + any hung status call before the stop; post-stop verification bills no containers. Compute reservation **$16.1628228** + $0.10
build = **$16.2628228**; cap ask **$17**, headroom **$0.7371772**. Still conditional on: ≤ 5 billed CPU cores; the
window above across ALL starts and container attempts; memory ≤ 32 GiB; the PC-side watch stopping the app;
unchanged rates; storage/transfer small and unpriced. Aggregate billed seconds and the settled total remain
unestablished until billing settles; throughput remains unprofiled (accepted risk).

## Unresolved questions
1. Codex: re-audit verdict at b843724?
2. User (after PASS): approve the $17 cap for one B3 campaign under v1 §4 as corrected by §3, the §4 ledger and v1 §6?
