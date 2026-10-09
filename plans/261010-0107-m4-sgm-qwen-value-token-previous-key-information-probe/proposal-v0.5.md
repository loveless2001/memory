# Proposal v0.5 — previous-key information probe: receipt validity + consumed-source binding (codex 22412/22413)

Supersedes v0.4 only where stated. v0.1–v0.4 are kept unchanged. The science is unchanged.
Authorizes nothing. Needs codex follow-up audit, then the user's scoped go; execution only via the controller.

## Repairs
1. **Full-schema receipts.** The stage-receipts module now validates, per mode:
   - the frozen episode counts, splits and seeds; threads 8 and n_boot 4000; the BLAS env;
   - resolved PilotConfig = frozen manifest + device=cpu;
   - SGM selected_layers (6,13,20,27) with feature_shift 1;
   - backbone pin = the pinned Qwen3-0.6B-Base spec (repo, revision, file sha256s);
   - a 64-hex initial-adapter content hash.

   Codex's fake S2 output (8+6 episodes, 2 layers, `identities={fake:true}`) is now refused even with exit 0 (tested).
2. **Bound artifacts.**
   - `run.json` must exist and equal `result["run"]`.
   - `features.npz` must hash to `run.features_sha256`, contain exactly the frozen arrays/shapes, and be all finite.
   - The metric key set must be exact, with values finite and in range; `reading.read == (mode == full)`.
   - For S1, `admission.json` must equal `result["admission"]`.
3. **Admission recomputed.**
   - The parts (capture/episode, load, fit, boot, output) must be numbers, finite and ≥ 0. Overflow literals such as `1e999` parse to inf and are refused.
   - `estimate = load + capture×160 + fit + boot + output + 300` and `wall = 2×estimate` are recomputed.
   - `admit` must equal `(0 < wall ≤ 14,400)`.
4. **Cross-stage identity.** S1 and S2 must share the same initial-adapter hash. The full run's hash must equal S1's, and its run wall must equal the admitted wall.
5. **Consumed sources bound.** The source map covers:
   - the 4 probe scripts;
   - the frozen manifest;
   - the controller script;
   - the **whole memsub tree** (`source_tree_sha256(memsub)`, currently 2eee4228…), which covers the task, runtime, backend and backbone code actually consumed.
6. **Monotonic durations.** All timing and profile durations use `time.monotonic()`. Wall-clock time appears only in log timestamps.
7. **Single schema source.** `MODES` now lives in the receipts module, and the run script reads it from there.

## Evidence (`implementation/`)
- `focused-tests-r4.txt`: **55 passed**, EXIT_STATUS=0. Covers:
  - a 13-way corrupted-receipt gate: missing, S2 RUNNING, S2 exit 1, memsub-tree hash, NaN, admission mismatch, missing run.json, missing features, features hash, fake identities, seeds, initial-hash mismatch, metric keys;
  - wrong wall argument and a consistent non-admitting S1;
  - valid receipts reaching the sentinel;
  - 5 admission recompute/parts cases;
  - the receipt CLI, the source-map coverage and the strict JSON reader.
- `mutation-checks.json`: **28/28 mutants caught**. M21–M28 remove each new binding: run.json, features hash, estimate recompute, S1/S2 initial-hash consistency, memsub tree, PilotConfig, metric keys, admission part signs.
- Mutant temp dirs hold 266 all-zero 1024-dim test receipts and 41 fake 64-dim planted files. No Qwen features.
- Note: `/tmp/pytest-of-lenovo` has rotated to pytest-12/13/14 (timestamps 01:58–02:02, not from my isolated-basetemp runs). The M10 evidence of record is codex's preserved copy.

## Launch (unchanged; only after the user's scoped go)
`setsid nohup bash plans/261010-0107-m4-sgm-qwen-value-token-previous-key-information-probe/run-probe-chain-s1-s2-full.sh > /dev/null 2>&1 < /dev/null &`
