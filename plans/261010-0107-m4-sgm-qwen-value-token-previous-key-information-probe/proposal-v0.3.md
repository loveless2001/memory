# Proposal v0.3 — previous-key information probe: corrections + implementation package

Supersedes v0.2 only where stated. v0.1 and v0.2 are kept unchanged. Applies codex 22395
(`plans/reports/codex-261010-gravity-22391-information-probe-v02-review/review.md`, sha 1002f367…).
Everything else in v0.2 stands, including the readings, the paired Δ, fold-local fitting and the single frozen init arm.
Authorizes nothing. Needs codex implementation audit, then the user's scoped numerical go for S1 → S2 → full.

## Correction 1: shuffled null (V-shuf)
- Each episode gets an independent uniform permutation π of its 32 bindings, with fixed points ALLOWED. Binding j's target is binding π(j)'s key embedding.
- π is fixed once per episode. Seeds: fit 9_700_031, eval 9_700_032; smokes 9_799_031 / 9_799_032.
- The probe is FIT and EVALUATED on the permuted targets, against the episode's original 32 candidates.
- Conditional on any prediction, the target is uniform over all 32, so the null reference is exactly 1/32. (A derangement would give 1/31 when the decoder can exclude the true key.)

## Correction 2: frozen walls and admission formula
- S1 wall = 1800 s and S2 wall = 2400 s. Both are hard `timeout --signal=KILL`, frozen in the script (`--wall-s` must equal them, checked before any model load).
- Full wall = ceil(2 × estimate), read from S1's `admission.json`:
  `estimate = model_load_s + capture_s_per_episode × 160 + fit_s + boot_s + output_s + 300`.
- `fit_s` comes from synthetic FULL-SHAPE timings measured in S1 after the model is released:
  - SVD ridge at 2304×1024, 2304×2048 (CV train folds) and 3072×1024, 3072×2048 (final);
  - 768-row CV prediction + retrieval over 6 λ;
  - formula: `fit_s = 4 layers × (4 sets × per_set(1024) + per_set(2048))`, where `per_set(d) = 4 × (cv_fit + cv_pred) + final_fit + cv_pred/2`.
  This puts the dimension-dependent SVD cost in the bound instead of an episode multiplier.
- `boot_s` = measured single-statistic bootstrap × 32. `output_s` = 30 s + full features bytes / 50 MB/s.
- If the full wall would exceed 14,400 s, S1 writes `admit: false` and the full run refuses before loading.
- S1 captures at batch 2 (2 episodes per split); the full run captures at batch 4. The per-episode capture estimate is therefore taken from the smaller batch.
- The model is released (`del` + `gc.collect()`) before any solve.
- A failed smoke (nonzero exit, KILL or refusal) stops progression. There is no retry, and partial evidence is kept.

## Reporting
Each statistic records its own adjustment: per-layer V/V+K/K/Δ at 98.75%; the E_v/V-shuf family at 99.375%. No joint 95% coverage is claimed over mixed verdicts.

## Implementation (branch `mvp`)
| File | Role |
|---|---|
| `scripts/sgm-p2p5-previous-key-probe-ridge-retrieval-readings.py` | model-free math: folds, fold-local ridge, retrieval, null permutation, bootstrap, readings, admission |
| `scripts/sgm-p2p5-previous-key-probe-capture-qwen-adapter-inputs.py` | frozen condition (manifest sha check, device=cpu only override, `requires_grad` off, `no_grad`), `project()` input tap with a one-call-per-step check, embeddings |
| `scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py` | modes s1/s2/full, wall check, capture → release → fit/eval → bootstrap → reading → result.json; S1 profile + admission |
| `tests/test_sgm_p2p5_previous_key_probe_math_c0.py` | C0 (17 tests) |
| `tests/test_sgm_p2p5_previous_key_probe_orchestration_fake_capture.py` | model-free s2 end-to-end with a planted signal + wall refusal (2 tests) |

- Evidence: `implementation/focused-tests.txt` (19 passed, EXIT_STATUS=0); `implementation/mutation-checks.{py,json}` (10/10 mutants caught).
- Refusals use explicit `RuntimeError`, not `assert`, so they survive `python -O`.

## Launch commands (each only after the user's scoped go; run from the memory repo root)
```bash
D=plans/261010-0107-m4-sgm-qwen-value-token-previous-key-information-probe
# S1 (frozen 1800 s)
systemd-run --user --scope --quiet --unit=pkprobe-s1 -p MemoryMax=4400M -p MemorySwapMax=1200M \
  timeout --signal=KILL 1800 .venv/bin/python scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py \
  --mode s1 --wall-s 1800 --out $D/s1-smoke > $D/s1-smoke.log 2>&1; echo $? > $D/s1-smoke.exit
# S2 (frozen 2400 s), only if S1 exit 0
systemd-run --user --scope --quiet --unit=pkprobe-s2 -p MemoryMax=4400M -p MemorySwapMax=1200M \
  timeout --signal=KILL 2400 .venv/bin/python scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py \
  --mode s2 --wall-s 2400 --out $D/s2-smoke > $D/s2-smoke.log 2>&1; echo $? > $D/s2-smoke.exit
# FULL, only if S2 exit 0 and S1 admission admits; detached
W=$(.venv/bin/python -c "import json,math;print(math.ceil(json.load(open('$D/s1-smoke/admission.json'))['wall_s']))")
setsid nohup bash -c "systemd-run --user --scope --quiet --unit=pkprobe-full -p MemoryMax=4400M -p MemorySwapMax=1200M \
  timeout --signal=KILL $W .venv/bin/python scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py --mode full \
  --wall-s $W --admission $D/s1-smoke/admission.json --out $D/probe-run-v1 > $D/probe-run-v1.log 2>&1; \
  echo \$? > $D/probe-run-v1.exit" > /dev/null 2>&1 < /dev/null &
```

## Known pre-existing issue (not from this package)
`tests/test_experiment_artifact_hygiene.py::test_all_tracked_json_is_strictly_parseable` already fails on older tracked JSON, e.g. `plans/261009-0030-…/mutation-checks.json` from Stage A (trailing data). Left untouched.
