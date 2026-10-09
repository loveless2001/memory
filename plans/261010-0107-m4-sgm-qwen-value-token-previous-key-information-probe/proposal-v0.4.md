# Proposal v0.4 — previous-key information probe: execution-safety repairs (codex 22400/22408/22409)

Supersedes v0.3 only where stated. v0.1–v0.3 are kept unchanged. The science (question, data, probe, readings, Q2, intervals, frozen init arm, V-shuf with fixed points) is unchanged from v0.3.
Authorizes nothing. Needs codex follow-up audit, then the user's scoped go. Execution is ONLY via the controller below.

## Repairs
1. **Isolated tests and mutants (22400).**
   - `load_model()` refuses under `PKPROBE_FORBID_MODEL=1`. Both test files set it with an autouse fixture, and the mutation runner sets it in the subprocess env.
   - Every gate test stubs the capture module with a "MODEL LOAD ATTEMPTED" sentinel. The guard test also stubs `frozen_pilot_config`/`build`.
   - The mutation runner uses its own `--basetemp` + `-p no:cacheprovider`.
   - The unintended M10 real-model run is recorded (`implementation/unintended-m10-real-model-run-record.md`). It is not a valid S1, and its timings/admission are unused.
2. **Wall and stage binding (22408).**
   - `validate_wall()` requires a finite positive real number ≤ 14,400 s, independent of any JSON claim.
   - The full run requires VALID S1 **and** S2 receipts (stage receipts module), plus `--wall-s == ceil(validated S1 wall)`. Both are checked before any model load.
   - A receipt is valid iff all of these hold:
     - the `<dir>.exit` file reads 0;
     - `status.json` says COMPLETE (a KILL leaves RUNNING);
     - `result.json` has the right mode and the CURRENT source hashes (run, math, capture, receipts, manifest);
     - every number is finite;
     - for S1, `admission.json` has `admit: true` with a valid wall.
3. **Concrete fail-stop controller:** `run-probe-chain-s1-s2-full.sh`.
   - It refuses if any stage dir or `.exit` already exists.
   - Sequence: S1 → validate → S2 → validate → admitted wall → FULL → validate.
   - Each stage runs in a cgroup scope (4400M/1200M) under `timeout --signal=KILL`. The exit code is written synchronously.
   - Any failure writes `chain-status.txt: STOPPED` and exits. There is no retry.
4. **Real BLAS limit.** `OMP/OPENBLAS/MKL_NUM_THREADS=8` is set before numpy loads (in the script and the controller), plus `threadpoolctl.threadpool_limits(8)` around fitting/profiling. `threadpool_info()` is recorded in run.json. Verified: openblas 8 threads.
5. **Downstream finiteness / rank / strict JSON.**
   - Nonfinite features, targets, embeddings, ridge solutions, predictions, retrieval inputs, per-episode statistics, intervals and admission inputs are refused.
   - Ranks must lie in [0, C−1].
   - Outputs are written with `allow_nan=False`. Receipts are read with a strict parser that rejects NaN/Infinity.
6. **Durable identities and progress.**
   - run.json records:
     - the resolved PilotConfig and SGMConfig;
     - the backbone pin (repo, revision, file sha256s);
     - a content sha256 of the initial adapter parameters;
     - torch version/threads, BLAS env and threadpools;
     - source hashes and the git head.
   - `progress.log` is flushed and fsynced per line.
   - `status.json` is written atomically: RUNNING → COMPLETE | FAILED, with the error recorded.

## Files (branch `mvp`)
- `scripts/sgm-p2p5-previous-key-probe-ridge-retrieval-readings.py` (math + `validate_wall` + finiteness)
- `scripts/sgm-p2p5-previous-key-probe-capture-qwen-adapter-inputs.py` (+ test guard, `identities()`)
- `scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py` (receipt-gated, status/progress, BLAS limit)
- `scripts/sgm-p2p5-previous-key-probe-stage-receipts-and-admission-validation.py` (NEW: receipts, strict JSON, CLI)
- `run-probe-chain-s1-s2-full.sh` (NEW: controller)
- tests: `tests/test_sgm_p2p5_previous_key_probe_math_c0.py`, `tests/test_sgm_p2p5_previous_key_probe_orchestration_fake_capture.py`

## Evidence (`implementation/`)
- `focused-tests-r3.txt`: **44 passed**, EXIT_STATUS=0. Covers C0, nonfinite refusals, wall-validator edge cases, the 9-way full-mode receipt gate, the valid-receipt pass-through to the sentinel, the receipt CLI and the strict JSON reader.
- `mutation-checks.json`: **20/20 mutants caught**, including the gate/receipt/BLAS-adjacent mutants M10–M20.
  - M10–M12, M15, M16 and M19 log *blocked* model-load attempts.
  - Every `features.npz` produced under mutant temp dirs is the fake planted data (8×32×64). None is Qwen.

## Launch (only after the user's scoped go)
`setsid nohup bash plans/261010-0107-m4-sgm-qwen-value-token-previous-key-information-probe/run-probe-chain-s1-s2-full.sh > /dev/null 2>&1 < /dev/null &`
