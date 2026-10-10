# Information-probe v0.5 follow-up: 94d85af

**HOLD: the producer does not emit the final run record required by the validator.** The prior invalid-receipt and consumed-source binding defects are repaired. An ordinary completed stage still fails validation because `run.json` lacks the feature hash added later to `result.run`. Correct that write and demonstrate model-free producer-to-validator success before numerical clearance.

Review is bound to commit `94d85af03fea707ecb271fafc943420e0bd654a6` and proposal v0.5. The audit retained 89 committed package/local-source files under `sources-94d85af/`, including the consumed memsub Python tree. No Qwen load/forward, real information-probe fit/profile, mutation-runner replay, GPU or Modal dispatch occurred. All actual numerical operations here were the declared small model-free tests and array/receipt checks.

## Verified repairs

The two declared test files independently passed: **55 passed in 3.33s**, exit 0, with `PKPROBE_FORBID_MODEL=1`, eight-thread environment settings, a 180-second deadline and an isolated basetemp. The capture guard and loader/construction sentinels remain in place.

The immutable validator independently accepted the unmodified frozen-schema fake fixtures and correctly refused external/embedded admission mismatch, a matching admission with an overflowing `1e999` profile part, a negative part despite a recomputed estimate, and consumed-source mismatch. A copy of the planted fake S2 output, with its run-record mismatch removed for this controlled check, is rejected specifically for incorrect frozen episode counts/splits/seeds. These checks are in `receipt-regressions.json`; no files were placed in actual launch directories.

The new map binds runner/math/capture/receipts, the frozen manifest, controller and the entire memsub Python tree. The independent snapshot tree hash matches `2eee4228124e9d292ed4079476ca276e8ce8f9ac7c8d83d44bcd51333687a19b`. Feature existence/hash/array-set/shape/finiteness checks and run/result/admission agreement checks are present. Admission parts are typed, finite and nonnegative, and the registered estimate, twice-estimate wall and admit decision are recomputed. Initial adapter hashes are checked across S1/S2 and at terminal full validation. Durations now use a monotonic clock.

The updated controller passed all **10 fake-command success/failure scenarios**, including the terminal full-validator call with both S1/S2 paths. This verifies sequence, argument construction, stop-on-failure and no retry; no real systemd scope, probe or timeout was launched.

The owner's committed mutation record reports 28/28 caught; this audit did not replay it. A live audit of all retained `/tmp/pkprobe-mut-*/features.npz` files found **453 files: 403 all-zero 1024-dimensional fixtures and 50 planted 64-dimensional fakes**, with no unexpected data. This live count is later than the owner's 266/41 snapshot; repair testing continued in parallel. Both earlier audit manifests were independently rechecked: all 36 original artifacts and all 213 v0.4 artifacts still match, including the preserved unintended M10 evidence.

## Producer/validator contract failure

In the reviewed runner, `body()` writes run.json before capture and after initial runtime identity recording (lines101/105). At line115 it adds `run["features_sha256"]` after saving features. The completed result at line164 contains that updated run object, while run.json remains the earlier version. The validator at line165 requires the two objects to be equal.

The independently executed ordinary fake S2 test confirms the mismatch: result.run has exactly one additional field, `features_sha256`; run.json has no value for it. Validation raises `RuntimeError('s2: run.json missing or differs')`. The retained `producer-contract-check.json` and the test output establish this without loading a model. The same unconditional write order affects real S1/S2/full, so the fail-stop controller would halt after the first completed S1 rather than progress.

The existing fake-output rejection assertion passes at this earlier mismatch and therefore does not by itself show that the intended frozen-schema rejection was reached. The independent regression check above removes the mismatch in a separate fake fixture and verifies the schema rejection.

Required repair: write the finalized run record, including the feature hash, so it exactly agrees with result.run. Add a model-free producer-to-validator success test using frozen-shaped fake captures and stubbed or tiny math/profile paths, with the real writer and validator. Retain negative schema checks with a matching run record so their refusal reason is not masked by this writer defect. No Qwen load or full-size profile is needed for that test.

## Stop point

The review of 94d85af is complete with one identified producer-contract blocker. Code-only repairs have started in the shared checkout and are outside the immutable reviewed package; source drift is recorded. Send the committed final-writer repair and isolated producer/validator evidence for follow-up. Numerical S1/S2/full remains unlaunched and still requires the user's scoped go after implementation clearance. The prior negative findings, M10 evidence and cleanup scope remain intact.

The manifest and SHA256SUMS bind the retained audit evidence and exclude themselves, symlink aliases and interpreter caches.
