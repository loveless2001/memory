# Wait #50 terminal audit: positive information-availability result

**PASS. Registered full reading: CARRIED. Q2: APPEND HELPS at all four calibrated layers.** This is a positive result for the preregistered information-availability question in the single frozen seed-0, shift=1, SGM-enabled init runtime. The preceding key is linearly recoverable from value-token adapter inputs on heldout keys. The earlier learned-memory negative results remain unchanged; this probe does not demonstrate trained routing or a successful shift=2 implementation.

The user authorized the $0 local CPU chain in #gravity22424, following implementation review935f91d. S1/S2/full all exited0 and have COMPLETE terminal records. The chain completed at19:47:49Z (02:47:49 Bangkok). Controller216781, timeout220812 and Python220813 have exited; no active pkprobe scope remains. The full stage was admitted for5075s from fresh real S1 evidence. Reported monotonic time through fitting is1287.009823s, with peak RSS3791.25MiB. Caps and eight-thread settings were independently observed in the earlier live audit.

## Registered readout

96 fit episodes contain3072 bindings; 64 heldout episodes contain2048 bindings. Retrieval selects among each episode's32 candidate keys; the chance reference is3.125%. V is the normalized PRE-attention input at the value token; K is the preceding key token's input; V+K is their concatenation supplied to an offline ridge decoder.

| Layer | V top-1, 98.75% episode CI | K top-1 | V+K top-1 | E_v baseline | V-shuf null | Paired V+K−V, 98.75% CI |
|---|---|---|---|---|---|---|
| 6 | 66.11% [63.82, 68.26] | 99.56% | 99.32% | 3.08% | 3.37% | +33.20pp [31.01, 35.50] |
| 13 | 35.06% [32.91, 37.16] | 99.56% | 99.17% | 3.08% | 3.17% | +64.11pp [61.91, 66.31] |
| 20 | 59.67% [56.98, 62.40] | 99.27% | 99.27% | 3.08% | 3.27% | +39.60pp [36.91, 42.33] |
| 27 | 24.41% [22.27, 26.71] | 94.38% | 91.26% | 3.08% | 2.98% | +66.85pp [64.16, 69.38] |

All K controls pass the calibration threshold. All eight null/baseline intervals, each at99.375%, include3.125%; no null-family interval lies entirely above chance. The null rates are near chance, not numerically identical to it. Layers6 and20 meet the registered CARRIED criterion (V point≥50%, lower bound>10%). Layers13/27 retain substantial recovery but fall below that point threshold. All four paired V+K−V lower bounds exceed10pp, yielding APPEND HELPS.

K alone already achieves94.38–99.56%. V+K−K is descriptive: −0.24/−0.39/0.00/−3.13pp for layers6/13/20/27; at27 the descriptive interval is[−4.49,−1.90]pp. Thus the append contrast establishes improvement over V and does not establish benefit over the key-state control.

The result weakens the strong hypothesis that shift=1 value-token inputs contain no preceding-key information. It leaves learned extraction, address-map compatibility, optimization and memory use unresolved. These features came from the shift=1 init runtime; deeper features include upstream init SGM effects. No memory-disabled arm was run. The offline V+K comparison does not test the full shift=2 bundle, which also changes other projections, initialization/scaling and upstream runtime behavior. Describing it as proof that a shift=2 runtime receives a "clean key" exceeds this experiment.

## Independent terminal checks

- The immutable reviewed validator independently accepts all three actual receipts and the full cross-stage validation. Exit0/COMPLETE, final run/result agreement, admitted wall, frozen specification, exact feature set/shapes/finiteness and source/feature hashes pass.
- All91 retained reviewed package/local-source files still match the checkout. The execution head was935f91d; the later result-record commit3d7b4d1 changes the evidence record without changing the reviewed source set. The source map includes the four probe scripts, manifest, controller and whole memsub Python tree.
- Initial adapter content hash matches S1/S2/full: `ef5741865072c27d7620d33ddbcb2d3c773e1e1ac5e23a8432b6f0e30d15c2f9`.
- The saved key/value IDs exactly match regeneration from the unchanged data generator using the registered seeds and batch4. Fit uses782 unique IDs in10000–10799; heldout uses all200 IDs in10800–10999. The two key-ID sets are disjoint and every episode has32 unique candidate keys. These are data-ID checks, not model forwards.
- All three pinned weight/config file hashes match. Reading only the key-embedding rows from the safetensors file reproduces the true fit target fingerprint`4389a14130d97149` and uniform-permuted fit target fingerprint`e33e7d84bf2e8a05`; they match every feature-set metric. The shuffled null allows fixed points as corrected in v0.3.
- Selected lambdas match the stored CV argmax with the larger-lambda tie rule. Metric levels, bounds, rank ranges,2048-example point/count consistency and paired point differences pass. Applying the registered decision function to the stored intervals reproduces CARRIED, all calibrated layers, no invalid cells and all four APPEND HELPS readings.
- Full result SHA256:`241deb707ef3d39ebad81f454f2953ab25e4d8dc619950c13ac241ccff55af43`. Full features SHA256:`7e2d968a96b8200037864d12ad97417bd047cf8aff9127f691db1a466faafb30`;167859130bytes. The complete full feature archive and terminal records were independently copied into `terminal-copies/` and hash-bound.

This audit did not instantiate Qwen, execute a forward, fit/refit a decoder, rerun bootstrap intervals, dispatch or retry. It verifies provenance, target/data bindings and the recorded decision logic. Per-example predictions, fitted decoder parameters and per-episode hit arrays are not retained by the implementation, so the reported ranks/intervals were not reproduced from scratch in this no-rerun audit. This is one initialized runtime and one registered data-seed pair, with per-statistic adjustments; no joint confidence claim is made across all mixed verdicts.

## Stop point

The authorized one-shot CPU probe is complete and the terminal audit is positive within its information-availability scope. No process/scope remains active, no further experiment is authorized, and no retry or paid run was performed. Prior campaign evidence, the preserved unintended M10 attempt and cleanup boundaries remain intact. Findings were posted in #gravity22457; this report and the retained evidence are bound by manifest.json/SHA256SUMS.
