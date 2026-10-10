# Wait49 terminal audit: CPU gradient-path diagnosis

**COMPLETE, diagnostic only.** Independent artifact verification passed for all three conditions. This is a local CPU, forward/backward-only diagnosis over sixteen train-split episodes/64 queries per condition, B=1/K=16, N=32, filler40, data seed777. It is neither a new training result nor a B2 held-out endpoint evaluation. No structural break was observed on the direct taskhead→memory-read/write route. At the trained endpoint, small deeper-layer gradients co-occur with suppressed gates/reads and more similar projected directions. Their causal relationship remains untested.

## Completion, identity, and terminal state

All three conditions have exactly sixteen finite loss rows, complete batch0–15 log sequences, matching logged CE/accuracy values, exit0 shell receipts and exit0 `/usr/bin/time` receipts. No traceback/killed receipt exists. All expected gradient groups are present; every numeric group reports n_batches16/n_none0 and a finite positive mean norm with consistency within [0,1]. Expected structural None groups match the source: taskhead L27 output/alpha, plus oracle address-MLP groups; anchor-only expected unused groups are also correct. All-None groups serialize as strings, so their per-batch None count is source-derived rather than individually retained in JSON. Gradient vectors/raw per-query geometry are not retained; validation checks recorded summaries and source arithmetic, without a fresh numerical replay.

Script SHA256 `0a3d6e96f3ffe578f182a95daeffd3e553f199d57a203b91f4ad9de8bc770eea` matches launch and the byte-exact script at74fd599. Current owner records were at2847f89 at numerical-validation capture and theneb311b5 for the corrected readout; the source/JSON data did not change. Wrapper SHA256 `d5facdf3e2e029ee1369db511bb7187cf4eee7121650964378f94f31b5290f76` matches launch. Local memsub hash `d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532` exactly matches B2's manifest. Derived init/final configuration matches B2 except CPU vs CUDA; the actual diagnostic batch/split/filler settings are explicit deviations from training and endpoint evaluation. Final weights SHA256 `2149c97517ad0f844b30a82f52b0072090f02b1709809f6bac5f09afe107fdb3` matches B2's final manifest and the previously independently checked step1500 provenance. Oracle explicitly changes arm and disables fill/anchor.

JSON hashes: init `1476ae62ae0947f164697d5134827a380b281d16ea882dab29f7b2ee983adc91`; final `6daeed844b828805b412ff3aba55f234b7ee85589f0b4d5526749d2401788f93`; oracle `c1514c379f2a42d034dadc0c5e30d10e2bec96dafe9f7c92d6ceb4a86e21299d`. These confirm Claude's correction22349; the original22348 labeling was reversed.

Run ended17:06:07Z /00:06:07 Bangkok on10October. Live terminal check17:10:46Z found no launcher19449, no watcher21705, no numerical worker, and no active r3 systemd scope. This audit did not stop a healthy process or dispatch a new one. The launch wrapper's nonzero-exit fallthrough/five-second eventual-stop limitation remains preserved, but all actual condition exits were zero. ALL DONE was not used as the completion criterion. Retained RAM/swap observations verify enforced limits for the observed init/oracle snapshots; final scope control files are gone, so no terminal cgroup-event history is claimed for every condition. Time receipts give RSS peaks init4,540,676 KiB, final4,535,032 KiB, oracle4,553,348 KiB (about4.33/4.32/4.34GiB). The script's log label GB means GiB.

## Verified measurements

| Condition | Mean task CE | Correct /64 | Mean unscaled anchor |
|---|---:|---:|---:|
| init |4.236623|0|0.010167|
| B2 final weights |4.153723|2|0.547257|
| oracle at init, fill/anchor off |4.148411|0|—|

Chance CE is ln64≈4.158883. These small train-split diagnostic samples are not another held-out learning test. Oracle uses an untrained initial head and has no final-weight oracle counterpart, so it cannot establish that correct addressing would or would not rescue trained B2.

Task CE reaches q/k/value/beta/address and head at initialization and reaches the expected active groups at the final weights. L27 output/alpha have no path because the taskhead consumes raw reads recorded before residual injection; this is expected, not a broken value/write route. The oracle bypasses address MLPs but still provides value/beta task gradients.

| Layer | Task value norm, init→final | Init/final norm ratio | Value-token beta, init→final | Read norm, init→final | Projected key pair cosine, init→final |
|---|---:|---:|---:|---:|---:|
|L6|0.2835→0.04895|5.79×|0.5542→0.000502|0.2640→0.02558|0.5116→0.9495|
|L13|1.0587→0.00005896|17,956×|0.4508→0.005801|0.9530→0.00006804|0.7131→0.9504|
|L20|3.4894→0.0008101|4,307×|0.3604→0.2277|2.6510→0.0006158|0.6771→0.9572|
|L27|7.0771→0.00001080|655,538×|0.7363→0.2489|6.4213→0.000008505|0.6773→0.9802|

Final projected value direction pair cosines are0.887–0.924 vs init0.533–0.716. These are projections at value-token write time, not a measurement of all bank contents. High mean direction similarity does not show identical vectors, identical magnitudes, erased label information, or indistinguishable bindings. The lingering sentence about stored bindings being nearly indistinguishable in owner's r2 readout overstates these data and was flagged separately.

Final address mean ranks are15.09–16.08 (zero-based among32 candidate writes), with bound distances similar to other-write median distances. Final q·k top1 spans0.015625–0.035156 vs descriptive reference1/32. `top1_qk` is not address top1. The reported means show no evident average targeting advantage in this sample; they are not a statistical test, and heads/queries are not independent. L6 bound read/write distance is998.42 vs1.98 at init.

Anchor measurements are unscaled. Applying B2's coefficient0.1 gives final L6 q-projection mean norm0.8635 vs task0.4140, but address-MLP anchor1.0572 vs task6.9799; scalar anchor contribution0.05473 vs taskCE4.15372. The evidence supports anchor predominance in that q group, not the full objective or every routing group.

## Oracle and interpretation limits

Oracle source coordinates place each bound value at a disjoint stencil, with one value write and no other binding/junk write overlapping it. From `delta_memory.py` and the shared read/write stencil, this source control gives `r=(sum_c w_c²) beta (q·k) v_bound`. Thus normalized read/value cosine can be positive or negative according to q·k. Its averaged cosine/rank need not describe graded access to the correct item; sign changes can cancel in the mean. This is an algebraic source inference, not an added numerical condition. q and k are already L2-normalized in `layer_adapter.py`; another L2 normalization is not a missing fix established by this audit.

Consistency is across sixteen one-episode gradients, not eight two-episode mean gradients. 1/sqrt16=.25 is a descriptive heuristic, not a significance threshold or causal criterion. Small norms/ratios and endpoint collapse do not alone establish the cause of failed learning, training chronology, or how Adam's preconditioning interacted with these signals. No optimizer update, ablation, or final+oracle rescue was performed here.

Claude withdrew causal language in22351 and preserved the original readout. Verified conclusion: the task-loss graph reaches the intended parameters; the trained endpoint is strongly suppressed in several measured channels, with more aligned projected directions and no evident targeting advantage. The proposed noisy-reads→suppression mechanism remains a hypothesis. This diagnostic does not overturn B2's previously audited narrow negative memory-use result, or establish that frozen Qwen cannot use memory in general.

## Protected continuation evidence and stop point

The protected step750 checkpoint is available at `plans/reports/codex-261009-gravity-wait38-b2-manual-stop-audit/volume-evidence-verified/b2-run-v1/B2/resume.pt` in the main checkout. Read-only rehash matches exact `cd1a7e72cbbf4fc2cf92e029395c7e4f78a727d2b6d165b5030bacc1bd753394`. Availability/hash are verified; this audit did not load it or perform another geometry diagnosis. An intermediate checkpoint cannot establish the precise onset by itself.

Wait49 is closed. No monitor is rearmed. Numerical diagnosis is complete, causal question remains open. No new training, CPU forward/backward, GPU/Modal dispatch, rerun, budget change, or extra condition followed from this audit. Any follow-up remains a separate decision; existing original crash/stopped attempts and trained weights are preserved.
