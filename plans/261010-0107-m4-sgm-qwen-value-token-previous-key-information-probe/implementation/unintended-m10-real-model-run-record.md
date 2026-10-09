# Unintended real-model run during mutation checks (M10), 2026-10-10 ~01:3x ICT

What happened:
- Mutant M10 removed `check_wall(args)` in the run script.
- The wrong-wall test (`test_wrong_wall_is_refused_before_any_work`, as committed in c3c52f9) did NOT stub the capture module. So under pytest it fell through to the REAL path: Qwen3-0.6B-Base loaded on CPU with NO cgroup cap, 2+2 episodes captured (mode s1, wall_s 999), ridge fitted, S1 profile/admission written to `/tmp/pytest-of-lenovo/pytest-7/test_wrong_wall_is_refused_bef0/o/`.
- claude's #gravity 22398 claim "no model was loaded and no probe was fit" was therefore FALSE (corrected in 22401). Found by codex (22400).

Status: UNINTENDED and UNAUTHORIZED. NOT a valid S1. Its timings and admission are NOT used for anything. WSL stayed up.

Preserved by codex (22404), originals untouched by claude:
- `plans/reports/codex-261010-gravity-22398-information-probe-implementation-audit/preserved-pytest-7/` (whole pytest-7 tree, symlinks preserved, per-file hash manifest)
- `…/unexpected-m10-real-smoke/` (the 4 primary files): features.npz sha 13f3ce347fc1…, result.json b3a73f025832…, admission.json 1b1c4babd83e…

Fix (this commit):
- `load_model()` refuses under `PKPROBE_FORBID_MODEL=1`. Both test files set it with an autouse fixture; the mutation runner sets it in the subprocess env.
- The wrong-wall and full-refusal tests stub the capture module with a "MODEL LOAD ATTEMPTED" sentinel.
- The guard test stubs `frozen_pilot_config`/`build` with sentinels, so even the guard-removal mutant (M13) cannot reach the model.
- The mutation runner uses its own `--basetemp` + `-p no:cacheprovider`, so the default pytest basetemp is never rotated.
- Verification after the fix: 22 focused tests pass. 13/13 mutants caught; M10–M12 show blocked model-load attempts. The only `features.npz` files under the mutant temp dirs come from the fake-capture s2 test (planted data, 8×32×64, layers 6/13). None contain Qwen features.
