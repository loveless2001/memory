# P2.5 PK campaign — launch attempt 1 hold: fix + reset package (for codex audit; no Modal action until cleared)

Approval context: user 21627 "go" = scoped conditional campaign approval ($259.99 reserve, 21626). Hold: codex 21630/21632.

## 1. What happened (attempt 1, 2026-10-07 UTC)
| time (UTC) | step | result | evidence (`pk-campaign-launch/attempt-1-failed-slot-image/`) |
|---|---|---|---|
| 06:04:42 | deploy controller | ok, ap-eqwdT119XvSoBJC1I2kDqC | `01-control-deploy.log` |
| 06:04:52 | `arm` | guard write-once: app id, deadline 1791406064.0, price sha 6745896e… | `02-control-arm.log` |
| 06:05:07 | deploy slot learned-n32 | **image build failed**; app ap-5IEq26DjFCdkvzXtmoi3Ct left `stopped` | `10-learned-n32-deploy.log` |
| 06:06:49 | controller tick | registry empty → nothing due (`__unresolved__: []`) | `dict-…-control-guard-ticks.json` |
| 06:07:11 | stop controller by BOUND id (`strict_stop` → shared `stop_bound_app`) | verified: stopped, tasks 0, no containers | `03-control-stop-bound-verified.json` |

Root cause: `_build_environment` (`Image.run_function`) imports the runner module in a Modal build container
BEFORE the `.env` layer that sets `M4_PK_SLOT`; the module-level refusal raised `SystemExit` there. Never exercised
before: Gate-3 tests import the module locally with the env set; the proof used a different runner.
Untouched: no spawn, no GPU container, no slot/readings guard/admission Dict, no volume path
`m4-sgm/p2p5-qwen3-0p6b-screen-v1`, no local `p2p5-qwen3-0p6b-screen-v1/` dir (`07-…`, `09-…` listings).

## 2. Fix (3 runners, 2 tests, supplement, manifest)
- Slot runner: the module refusal fires only when `modal.is_local()` (build/run containers import freely);
  `run_slot` returns `slot_unset` BEFORE any admission claim / Dict / volume access if the slot is not registered.
  Local CLI refusal unchanged (`test_unknown_slot_is_refused`).
- Control Dicts renamed `…-control-registry-r2` / `…-control-guard-r2` (ticks: `…-guard-r2-ticks`) in the controller,
  slot and readings runners; test asserts all three agree and carry `-r2`.
- New test `test_image_build_container_imports_without_the_slot_env_and_run_fails_closed` (simulated remote import,
  env unset; `run_slot` raw function returns `slot_unset` with `modal.Dict.from_name` booby-trapped).
- Mutation checks (`mutation-checks.py/json`): each part reverted in place → its TARGETED test fails (the launch
  manifest test also fails, by design; the check requires the targeted test among the failures); sha-restored.
- Supplement rev 3: pre-deploy step, fixed spawn order, attempt-1 record.
- Manifest re-frozen: 5df85db8… → 4ff9c930…; ONLY 4 `launch` entries changed (3 runners + supplement);
  `analysis` section and memsub tree sha unchanged.

## 3. Reset / state operations (no deletion anywhere)
- Attempt-1 control Dicts (`…-control-guard`, `…-control-registry`, `…-control-guard-ticks`): preserved untouched,
  exported read-only; never read or written by attempt 2 (new `-r2` names).
- Attempt-1 apps ap-eqwd… / ap-5IEq…: stay stopped; never targeted (stops bind attempt-2 ids; the shared helper
  refuses a mismatched live id).
- Slot/readings guard/admission Dicts and the `-r2` control Dicts: verified absent now (`09-dict-list…json`).
- Same app names → a deploy creates NEW app ids; spawn/arm bind those via lookup, as designed.

## 4. Attempt-2 sequence (after codex clearance; chat_read immediately before)
1. Clean tree at the cleared commit (spawn re-checks tree + manifest).
2. PRE-DEPLOY, inert (no spawn, no Dict): `M4_PK_SLOT=<slot> modal deploy …slot-runner.py` ×9, then
   `modal deploy …readings-runner.py`. Any failure → stop, report, $0 GPU. Logs → `pk-campaign-launch/attempt-2/`.
3. `modal deploy …control-plane-reaper.py`; `… control-plane-reaper.py arm` (fresh `-r2` guard).
4. Spawn ×9 within 1800 s, order: learned-n32, oracle-n32, random_fixed-n32, single_cell-n32, learned-n16,
   random_fixed-n16, single_cell-n16, memory_off-n32, memory_off-n16 (only the first ~3 are window-bound).
5–8. Collect loop → validation → readings `spawn`/`collect` → billing + terminal package (unchanged rules).

## 5. Charges (inside the existing $259.99 conditional reserve; codex 21634/21635)
- Attempt 1, app-attributed: controller $0.00004958 — a PARTIAL snapshot of the 06:00 UTC hour (`08-…json`),
  not final. Failed slot image build (seconds of CPU, image im-7iyNB1SjJLzRBNk0WUOHQT): UNRESOLVED, not
  app-attributed in the hourly report. Both settle in the final reconciliation (hour closes 07:00 UTC).
- Allocation: $0.50 of the $5.00 margin is set aside for attempt 1 (its controller runtime, controller image,
  failed slot build). The ledger's 11 image lines ($1.85) and controller line ($0.28) stay for attempt 2 as planned.
  Margin left $4.50; reserve total unchanged at $259.99. Final report lists attempt-1 actuals separately.

## 6. Training matrix (unchanged; for the user handoff)
18 trained cells = 4 arms (learned, single_cell, random_fixed, memory_off) × N16/N32 × seeds 0/1 = 16, plus oracle
N32 × seeds 0/1 = 2, in 9 slot apps (one pair each). Oracle N16 is not trained: it is the transfer evaluation of
the N32 oracle inside the readings run. Not 5 × 2 × 2 = 20.

## Unresolved questions
- None open. Readings pre-deploy: codex 21635 says technically compatible (inert; spawn still gated).
