# Independent final readings artifact audit

**PASS for the collected post-hoc amended analyses.** Both N32 and N16 read **screen not passed**. Registered memory use is false at both sizes. The original protocol outcome remains **unavailable: learned-n32-s1: state FAILED** at both N. This audit does not turn the amended analyses into an unamended preregistered result.

## Independent numerical verification

All **53,248 saved rows in 20 evaluation files** passed strict JSON, exact schema, uniqueness, population coverage and SHA256 checks. Every episode hash, query key and target label matches the published `9_600_011+s` population under frozen CPU sampling. No model was loaded or evaluated. Independent standard-library arithmetic recomputed all accuracies, episode-paired normal 95% intervals, control labels, oracle interface flags, per-seed memory-use tests, read-address labels and final readings. Every reported value agrees within `1e-12`.

Reserved-population accuracy, percent; seed 0 / seed 1:

| N | Oracle | Learned | Single cell | Random fixed | Memory off |
|---|---|---|---|---|---|
| 32 | 100.00 / 97.85 | 6.93 / 5.86 | 8.59 / 5.96 | 12.50 / 8.89 | 1.46 / 1.86 |
| 16 | 100.00 / 98.63 | 3.91 / 2.15 | 4.00 / 3.91 | 8.20 / 1.66 | 1.46 / 2.83 |

Oracle interface passes at both N; N16 is the declared transfer of N32-trained oracle checkpoints. N32 control labels are memory_off **neither**, single_cell and random_fixed **positive gain >=5pp excluded**. At N16 all three controls have that exclusion label. These labels exclude the registered gain, not every possible positive effect.

At N32 the learned-minus-random-fixed contrasts are **−5.57 pp [−7.54, −3.59]** and **−3.03 pp [−5.10, −0.95]**. Read-address use is established at N32 and not established at N16. The registered memory-use conjunction fails in every learned cell: N32 bank derangement produces no established accuracy decrease; N16 seed 0 also lacks that decrease, and seed 1 lacks an established read-offset effect. Thus the read-offset effects alone do not establish registered memory use or identify a failure mechanism.

Whole-campaign and both-N **post-hoc amended** labels and the original unavailable outcomes are present and exact. N16 evaluations use their own learned checkpoints; its original availability still depended on the global all-18-valid gate. Seed 0's N32 contrast already prevents the all-seed/all-control pass conjunction regardless of the amended seed 1 score, but that counterfactual does not restore original protocol validity.

Saved descriptive gate summaries have the exact 16-head population. Pooled ratios and AUROC aggregates agree with their saved per-head summaries. Raw gate events were not retained, so their AUROCs were not independently replayed. Successful parity and execution order are supported by rc0 and successful output under the frozen runtime identity and control flow; no model replay was performed.

## Artifact and lifecycle verification

The call is `fc-01M4BG37XCKFD3A9WRJ91D44MB`; independent remote polling confirms `{status: read, rc: 0}`. Remote report/exit bytes match the collected copies. Launch identity, immutable guard, exactly one admitted start, and controller registry/deadline match the independently verified launch. Source remains clean and report identity matches memsub `2eee4228…` and manifest `882dd4a4…`.

A fresh real artifact binding again yields 17 valid original cells plus the original FAILED gate, and 18 accepted under the exact amendment. All 18 state files and terminal checkpoint payloads match the previous independent audit. Remote FAILED state and done.json bytes still match the frozen exception spec.

The retained readings stop at **17:42:47 UTC** precedes its **19:26:04.843969 UTC** deadline. The owner subsequently stopped the controller by its bound ID at **17:50:07 UTC**. At **2026-10-07 17:53:57 UTC**, an independent live refresh verifies **all 12 campaign app IDs** (nine slots, readings, both controller attempts) stopped or unlisted, with zero tasks and containers. The original -r2 guard, ten-entry registry and all 332 exported ticks remain preserved. Lifecycle shutdown is verified (`all-stopped-check.json`).

## Terminal package and preliminary billing

Package commit **428fc6d67feef70de47b6dd95569ef0cee7ec76e**, following **44b1f18**, passes the archive review (`terminal-package-check.json`, 14 checks). Changes relative to the frozen scientific commit are additions only. All 25 result/provenance/collection files are committed and unchanged; metadata indexes match. All 1,374 per-slot non-binary volume files are committed. The original package's 1,478 non-metadata payload files also include slot metadata, launch/collection logs and readings; that count is broader than per-slot volume evidence alone.

The binary exclusion index exactly covers **558 local checkpoint/safetensors files**, none committed. Independent streaming SHA256 checks passed for every payload, totaling **12,378,547,780 bytes**. Hashes preserve identity; the binaries themselves are retained outside git.

The saved hourly billing source hash, per-app attribution, exclusion of unrelated apps, all nine slot subtotals and the exact decimal total agree. Preliminary app-attributed cost is **$126.44110087**: slots $119.27095429, readings $7.08987892, -r2 controller $0.08021808, and attempt-1 controller $0.00004958. This is a snapshot with an open billing hour, not a settled invoice. Later backfill and the unattributed failed image-build charge remain unresolved; the **$8.57 proof hold stays separate**. The conditional reserve is not a platform cash ceiling. Final financial reconciliation remains pending the owner's later billing refresh.

Evidence: [saved-results-check.json](saved-results-check.json) (72 checks), [terminal-state-check.json](terminal-state-check.json) (9 checks), [terminal-package-check.json](terminal-package-check.json), [all-stopped-check.json](all-stopped-check.json), and the accompanying verifier scripts and captured live listings. No shared artifact edit, remote mutation, new invocation, model evaluation or GPU launch was performed.
