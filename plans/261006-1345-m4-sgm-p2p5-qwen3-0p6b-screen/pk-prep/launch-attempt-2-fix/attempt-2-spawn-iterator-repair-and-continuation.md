# Attempt 2 — spawn-iterator repair + continuation (codex 21643–21647; for audit)

## Failure (06:44:16 UTC, first spawn, learned-n32)
`TypeError: object of type 'generator' has no len()` at `if len(guard.keys()):` — modal 1.5.1 `Dict.keys()` is a
generator; test fakes were dict views. Same line in the readings runner. Log: `pk-campaign-launch/attempt-2/40-spawn-learned-n32.log`.
Observed state (codex 21647 read-only, 06:46 UTC): learned-n32 guard NotFound (`from_name` is lazy; the TypeError
came before hydration), -r2 registry NotFound, local campaign group absent, no call. -r2 controller guard armed
ap-suOdTgdc8PNSfZ3jbnsesa / 1791408417.2529736 / v6 6745896e….

## Repair
- Both runners: `if any(True for _ in guard.keys()):` — ANY key (incl. None / False / "") = used (codex 21645).
- Fakes in the reaper/readings tests now return generators from `keys()`. New regressions through the REAL spawn
  paths: slot (used / None / False / "" key / keys() error → refuse before root, provenance, registry, call) and
  readings (same + empty → exactly one spawn).
- Mutation checks `mutation-checks-spawn-iterator.py/json`: `len(...)` and first-key variants in each runner, each
  with the launch manifest re-frozen over the mutated bytes (restored, sha-checked) so only the TARGETED test can
  catch it — all 4 caught.
- Manifest 4ff9c930… → 2969d788…: only the 2 runner entries in `launch` changed; analysis/memsub unchanged.

## Continuation (no re-arm, no -r3)
1. Keep the -r2 controller as armed (no redeploy, no re-arm; its bytes are unchanged).
2. chat_read; redeploy ALL 10 GPU apps (9 slots + readings) from the repaired commit, so deployed functions match
   the new runner/manifest bytes (heavy image layer cached; only mount layers change). Logs `attempt-2/5x-…`.
3. Spawn longest-first (learned-n32 … memory_off-n16). Window: learned-n32 by 07:14:05 UTC; oracle-n32 +532 s,
   random_fixed-n32 +705 s, the rest far later. Record each slot's bound app id + call id.
4. If clearance + redeploy cannot land learned-n32 by 07:14:05: stop the controller by bound id, verify, report.
Charges: redeploys + controller runtime sit in the planned image ($1.85) / controller ($0.28) lines of the
unchanged $259.99 reserve; attempt-1 allowance stays $0.50 (unsettled).
