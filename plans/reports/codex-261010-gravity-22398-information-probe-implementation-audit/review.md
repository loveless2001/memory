# Information-probe implementation audit: c3c52f9

**Numerical execution HOLD.** The core feature tap and model-free math checks pass, but the reviewed package has test isolation, admission, launch progression, thread-limit and finiteness/provenance gaps. An unintended real CPU smoke occurred during the owner's M10 mutation check. Its artifacts are preserved and must not count as an authorized S1 or supply the future launch admission.

This audit independently ran the normal 19-test suite, tiny model-free counterexamples and a fake-input capture-hook check. It performed **zero Qwen loads/backbone forwards**, zero real information-probe fits, zero mutation-runner executions and zero GPU/Modal dispatches. Source review is bound to commit `c3c52f9` and the copied `sources-c3c52f9/` tree. Fixes have since begun in the shared checkout; `source-drift-at-terminal.json` records that they are outside this completed review.

## Verified checks

The two declared test files passed independently: **19 passed in 0.55s**, exit 0, with bounded BLAS/PyTorch environment settings and a 180-second test deadline. These baseline tests do not exercise the dangerous M10 bypass.

The actual capture wrapper passed an additional fake-input check for all four layers: key/value token IDs and source positions match, partial batches retain episode order, original hooks are restored after success, and nonfinite captured input is rejected with hooks restored after failure. No backbone was instantiated. The inspected runtime routes the normalized pre-attention input into this wrapper.

The math source implements fold-local standardization/centering, the declared sum-SSE ridge with unpenalized intercept, SVD reuse across lambda, larger-lambda CV ties, within-episode cosine retrieval, uniform shuffled target permutations with fixed points allowed, paired episode bootstrap contrasts and the registered reading precedence. Equal row counts per episode make the current row-level CV mean equal the declared episode mean. The nested detached command's dollar-status escaping was checked with a harmless failing command and correctly reports exit 1; it is not an identified defect.

## 1. Confirmed unintended M10 model execution

The wrong-wall test in `tests/test_sgm_p2p5_previous_key_probe_orchestration_fake_capture.py` does not stub the capture loader. M10 replaces the call to `check_wall(args)` with `pass`, allowing the test to enter the real Qwen loader and subsequent S1 work before it fails its expected-refusal assertion.

Existing files in `/tmp/pytest-of-lenovo/pytest-7/test_wrong_wall_is_refused_bef0/o/` establish the actual work: `run.json` records mode S1, wall 999, two fit/two evaluation episodes, real capture/manifest hashes and the altered runner hash. That hash exactly equals the M10 transformation of the reviewed runner: `9eac67d8911fb1e2a0f6cff1fc1c6bdd5a6f3322602bdb80a0e82e0eb4237476`. `features.npz` contains the expected 20 arrays, including four-layer 1024-dimensional feature captures. `result.json` contains actual ridge metrics and reports model load at 6.884s, capture completion at 45.373s and peak RSS 3801.984375 MiB. `admission.json` was also generated. The mutation-check record reports the test failed after approximately 137 seconds.

The owner confirmed in #gravity 22401 that this ran without a cgroup cap, was unintended and unauthorized, and contradicts the original “no model loaded/no probe fit” claim. Historical cgroup enforcement was not independently recorded in the attempt. None of its metrics is used here to judge key-information availability, and its admission is not cleared for reuse.

Preservation is complete: the four primary files were copied into `unexpected-m10-real-smoke/`, then the entire pytest-7 directory was copied into `preserved-pytest-7/` with symlinks preserved. The two primary copies match. The complete directory has seven regular files totaling 5,144,029 bytes; hashes are in `pytest-7-copy-manifest.json`. The pytest temp directory is no longer the only copy.

Required repair: fail-before-model guards for every tested numerical entry path, an explicit wrong-wall loader sentinel, isolated mutation environments and a corrected attempt record. Rerun model-free mutants only after those controls are in place. “Mutant caught” must not mean that a real model workload occurred before a final assertion failed.

## 2. Admission and staged launch must enforce the bounds

`check_wall` at runner lines58–65 accepts JSON whose `admit` flag is true and whose wall equals the CLI value. It does not independently enforce positivity or the four-hour ceiling, validate component values or bind the profile to successful authorized S1/current source. Model-free checks show that **wall 0 and wall 20,000 are both accepted**. In the external timeout, zero disables the time limit; this must be refused before any load.

Require a finite, positive wall no greater than 14,400 seconds independently of the admission flag, typed/finite/nonnegative profile components and exact reviewed profile/result/source identities. Bind admission to the authorized S1 run. Require successful, complete S2 evidence as well.

The proposal's pasted S1→S2→full commands state conditions in comments; they do not programmatically halt progression on S1/S2 failure. Provide a concrete one-shot controller or explicit stage validator that records each exit, validates the completed output and source/config binding, and refuses the next stage on any failure. The old unintended M10 output must remain outside that path. No automatic retry follows a failure.

## 3. Actual BLAS thread limit

The runner calls only `torch.set_num_threads(8)`. Independent inspection of installed pools showed NumPy OpenBLAS at **16 threads both before and after** that call, while Torch OpenMP became eight. Thus the dominant NumPy SVD/profile work is not under the declared eight-thread limit.

Set BLAS limits before imports or use a verified threadpool limiter around fitting and profiling; record effective pool counts. Make the profile and full run use the same enforced settings. Use a monotonic clock for durations and retain UTC separately for provenance.

## 4. Finiteness and result invariants

The capture rejects nonfinite raw adapter inputs, but downstream embeddings/normalization, ridge/predictions, retrieval statistics and admission values have no equivalent enforcement. A two-dimensional model-free example with a NaN prediction returns retrieval rank **−1** rather than raising. That is outside the registered 0–31 rank range and can silently reach serialized metrics.

Reject nonfinite/zero-invalid targets and candidates, nonfinite solves/predictions/metrics, out-of-range ranks and invalid admission/profile values before writing a successful result. Write strict JSON without NaN/Infinity. Add meaningful model-free counterexamples at the relevant boundaries.

## 5. Identity, progress and terminal records

Current `run.json` records the three scripts, manifest and git head, but omits the promised resolved PilotConfig/SGMConfig, full consumed source/model/version identities and initial adapter parameter hashes. Save those before capture so “same initialized runtime” can be independently audited, including CPU and no-training construction.

Redirected capture prints can remain buffered until exit. Flush stage/batch progress and write durable stage status/failure receipts so a timeout preserves an observable stop point. Distinguish a wrapper receipt, a completed JSON and a scientifically valid reading. These records must remain available after process exit or kill.

## Stop point

The numerical package is not cleared by this audit. The reviewed positive math/capture checks stand, and the owner has acknowledged the unintended mutation execution and started code-only repairs. Supply a fresh committed package, corrected attempt record and safely isolated model-free checks for follow-up review. S1, S2 and full still require the user's scoped numerical go after that review. The prior campaign's negative results and Q1-only cleanup remain unchanged.

`manifest.json` and `SHA256SUMS` bind the audit artifacts and exclude themselves. Current-source drift is recorded; the immutable reviewed source copy is retained so subsequent repairs cannot erase these findings.
