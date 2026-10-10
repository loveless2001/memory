# P2G code audit — 0726161

**Code audit PASS: all recorded implementation blockers are resolved.** Final execution clearance still requires the completed preflight-r3 package binding the updated validator. Separate scoped user authorization for the six training cells and reviewed cap remains required; no training is authorized by this code audit.

Reviewed commit: `07261613b206087dcddc50a1ed74ec5925ddb708`.
Coordination: #gravity 21327–21328. Earlier audits record the original three holds and the recovery integration gap.

## Recovery integration fix verified

- `training_eval_seed_base(grid)` selects artifact seed, then legacy final seed, then the historical v2 default. Conflicting explicit artifact/final seeds abort.
- The recovery CLI calls this helper before validation. It selects `9_300_011` for the registered P2G grid, preserving `9_400_011` for the post-validation readings population.
- Existing P2D/top-up grids retain `9_300_011`; legacy v2 retains its `9_100_003` default.
- Independent command: `.venv/bin/pytest -q tests/test_sgm_recovery_cli_seed_selection.py tests/test_sgm_grid_attempt_selection.py tests/test_sgm_grid_readings.py`.
- **29 passed in 15.19 s; no skips.** This includes the CLI integration and real saved P2D cell: the selected artifact seed validates; the old default reproduces the final-evaluation-seed mismatch.
- The seed separation, malformed telemetry/interval rejection, and before/after source/input checks reviewed at `e71784b` remain unchanged. The 62 focused P2G tests previously passed independently; the new change is confined to recovery seed selection and its regressions.

## Preflight-r2 independently verified

Evidence commit `0ea956f`; producer HEAD `c504a897be1a1cb2ceba0f8de071589f0eeb1fe5` (executed implementation `e71784b`).

- **6/6 parity files parsed-equal and byte-equal** to their frozen references, 5,120 rows each, 30,720 total.
- All files are also byte-identical to r1. Coverage checks confirm all five legacy interventions, 256 shared episodes per intervention, and four unique queries per episode.
- The complete start/end observer identities are equal. Every recorded script/index/grid hash matches the producer commit.
- Step-0 telemetry is identical to r1. It remains descriptive initialization evidence.
- Report SHA256: `f2e840e642742c7b45bb80e508e5872690e580f11a2dc6aaca3a86c19d34a820`.
- Detailed independent artifact: `plans/reports/codex-261006-p2g-preflight-r2-independent-checks.json`, SHA256 `3567b16bea0de717750620d783953b9c08bbea7cc0acc9eaee0d877dd0006c36`.

## Remaining gate

Claude's preflight-r3 is already running on the published fixture population to include the updated validator hash. No duplicate fixture evaluation or training was started by this audit. Review its six outputs and start/end identities before final implementation clearance and the subsequent concrete scoped cap request.

The reservation remains **$12.32978160**; proposed cap **$13** remains unapproved. `P2G_CAP_USD=None` continues to refuse ordinary launch planning.
