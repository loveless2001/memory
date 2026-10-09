# Proposal v0.6 — producer/validator binding fix (codex 22418)

Supersedes v0.5 only here. v0.1–v0.5 are kept unchanged. Science and receipts are unchanged.

- **Bug (codex 22418):** `body()` wrote `run.json` before capture and added `run["features_sha256"]` later without rewriting it. Since v0.5 the validator requires `run.json == result["run"]`, so a genuine successful S1/S2 would have been refused.
- **Fix:** just before `result.json` is written, the final run record is normalized once (`json.loads(json.dumps(run, default=str))`), stored as `result["run"]`, and written to `run.json`. The two files carry the identical encoding.
- **New producer→validator success test (model-free):**
  - It runs the REAL run script for S1 and then S2. The capture is fake but frozen-shaped (4 layers × 1024 dims, schema-correct identities). The math is real on tiny data; only the full-size profile is stubbed with a consistent admission.
  - Then it checks `run.json == result.run`. Both receipts validate, and `full_wall(S1, S2) == 2584`.
  - The fake 8+6-episode S2 is now asserted to be refused for its schema ("episode counts"), not for the run.json mismatch.
- **Evidence:**
  - `implementation/focused-tests-r5.txt`: **56 passed**, EXIT_STATUS=0.
  - `mutation-checks.json`: **29/29 caught**, including the new M29 (final run.json rewrite removed).
  - Mutant runs stop at the first failure (`-x`), so the producer test's fake features never appear under the mutant temp dirs. No Qwen features anywhere.
