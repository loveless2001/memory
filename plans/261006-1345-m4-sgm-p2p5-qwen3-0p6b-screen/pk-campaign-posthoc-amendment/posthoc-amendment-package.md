# P2.5 PK: post-hoc validation amendment package (learned-n32-s1), for codex audit

Authority: user 21710 chose B. Scope: claude 21702, codex 21701/21703/21712. No remote action until codex clears it.
Spec of the deviation: `../prereg-amendment-posthoc-validation-learned-n32-s1.md`.

## Changed / new files (memsub tree UNCHANGED: 2eee4228…)
| file | sha256 (12) | change |
|---|---|---|
| configs/m4_sgm_p2p5_pk_posthoc_validation_amendment.json | 3bce0817a163 | NEW frozen spec: cell, slot, epoch, attempt, state d4996651…, done 33a3dafb…, 7 output hashes, terminal gen-30/step-1500 link (38982aab…), original reason/validation, 51 (step, key) leaves |
| scripts/sgm-p2p5-pk-posthoc-validation-amendment.py | c631815a81c6 | NEW: amended validation (criteria 1-5) + write-once record CLI |
| scripts/sgm-p2p5-pk-campaign-readings.py | 9648b08bb42d | bind original gate first (recorded), then amended gate (spec cell only); labels; AMD in closure; spec in consumed inputs |
| modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py | 161b2670ff75 | `amendment_gate` (record amended_valid + spec sha + cell); `slots_ready(local, amendment)` accepts ONLY the spec cell FAILED with the original reason; record + doc in the dirty-tree list |
| scripts/sgm-p2p5-pk-campaign-analysis-dependency-manifest.py | 8d3af8a87e75 | spec → ANALYSIS_INPUTS; doc + record → LAUNCH_INPUTS |
| configs/m4_sgm_p2p5_campaign_analysis_manifest.json | 882dd4a44330 | re-frozen from 2969d788…: exactly 7 entries changed/added (4 analysis, 3 launch); memsub unchanged |
| plans/…/prereg-amendment-posthoc-validation-learned-n32-s1.md | 5232c93e207e | NEW deviation doc |
| plans/…/pk-campaign-posthoc-amendment/learned-n32-s1-revalidation-record.json | e4a2a04e3e38 | NEW write-once local record: `amended_valid`, spec 3bce0817…, over the fetched copy `…/learned-n32/volume-evidence/collect-1/learned-n32` |
| tests/test_sgm_pk_posthoc_validation_amendment.py | 07d9a2f9f165 | NEW (17 tests, incl. real-evidence 18-cell bind) |
| tests/test_sgm_pk_campaign_readings_runner.py | 1d3a4c3d62f8 | spawn stub signature only (`slots_ready(local, amendment=None)`) |

Unchanged: prereg, Amendment PK, grid, registry, schema, supplement, price v5/v6, proof bytes, slot runner,
controller, memsub, every FAILED/COMPLETE record and output on the volume and in the local copies.

## Evidence (this dir)
- Real local bind over all 9 fetched slots (test): ORIGINAL gate → `learned-n32-s1: state FAILED` (17 bound);
  AMENDED gate → 18 bound, s1 bound to `cells/learned-n32-s1/epoch-1/attempt-1/out`; state.json sha unchanged;
  a spec naming s0 instead leaves the original failure.
- `sgm-suite.txt` + `sgm-suite.exit.txt`: tests/test_sgm_*.py + hygiene. **492 passed, 2 skipped, EXIT 0.**
- `mutation-checks-posthoc-amendment.{py,json,stdout.txt,exit.txt}`: 15 mutations + 1 baseline, each in a private
  scratch copy, with the manifest re-frozen inside the copy. The AIMED test must fail. The shared tree is only read.
  **all_ok: baseline 27 passed; 15/15 mutations caught by their aimed test; EXIT 0.** Shared-tree shas re-checked after.
- `SHA256SUMS-posthoc-amendment-package.txt`.

## Remote sequence after clearance (chat_read immediately before each paid step)
1. `modal deploy modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py`. This redeploys the INERT
   readings app so the container sees the amended scripts/configs/manifest (run_readings checks the manifest sha
   == the launcher's). Expect the same app id. No spawn, no Dict. Log → `pk-campaign-launch/attempt-2/90-…`.
2. `.venv/bin/python modal-runners/…-readings-runner.py spawn`, no later than 17:06:30.652974 UTC (codex 21706;
   the controller deadline is unchanged). Preconditions: clean tree, launch manifest, amendment_gate,
   slots_ready(amendment), controller binding, guard empty. Log → `91-…`.
3. `collect` until stopped_verified, then the readings report (both N labelled "post-hoc amended", original
   reading kept), billing reconciliation, terminal package.

Cost: readings only, inside the existing $259.99 reserve (v6 readings reserve). The extra original-gate binding adds
about 18 validator passes, a few seconds each, before any population access.

## Unresolved questions
- None blocking. The cause and effect of the missing L20 gradient stay undetermined; this is labelled in the report.
