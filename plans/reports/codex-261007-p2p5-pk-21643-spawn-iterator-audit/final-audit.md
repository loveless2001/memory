# Frozen spawn-iterator repair audit — 537ace8

**CLEARED for the single documented continuation of attempt 2 under the existing campaign approval.** Target: `537ace8bc30a5ec486e521b6adf7ee3c340abf9f`, frozen by Claude in gravity21649. No tracked implementation diff remains. The failed local spawn made no training call or admission, so the approved 18-cell campaign remains unused.

Both real spawn paths now consume the iterator returned by Modal 1.5.1 `Dict.keys()` and reject any populated guard, including a `None`, false, zero or empty-string key. Iterator failures propagate before local root creation, provenance, registration or a function call. This resolves the observed `len(generator)` failure and the proposed None-sentinel bypass identified in gravity21645.

| Independent check | Result |
|---|---|
| Focused campaign/control/hygiene suite | **86 passed, 2 opt-in slow tests skipped**, 10.21 s |
| Real spawn paths with CPU-only Modal fakes | **70 cases passed** across all nine slots and readings: empty, used, None, false, zero, empty string and a streaming iterator error |
| Private in-memory negative mutations | **20 cases reproduced** the old empty-guard TypeError and the None-sentinel bypass |
| Frozen package index | **28/28 hashes match**; index SHA `547e9d685ad9fce1fc903aa43255cfb26f9ec0773d3a2c6d1202c6e719e09e15` |
| Dependency manifest | SHA `2969d788a62febc5f6dd619fca004e6c6af9df24914f9d3f797d7feaec7bb74a`; both sections verify |
| Scientific inputs | Analysis and memsub unchanged; only the two runner launch hashes changed from e9833f1; prereg, grid, price ledger and scientific scripts unchanged |

Evidence: [tests](independent-tests.log), [independent probe](independent-spawn-probe.json), [probe source](independent-spawn-probe.py), [package checks](package-checks.json), [final live verification](final-live-verification.json). The focused suite was run with two CPU threads and a 180-second outer timeout. The full suite and paid GPU proof were not repeated for this two-line local spawn repair. Earlier preview-collision artifacts are retained and excluded from verification; the final checks above ran after the explicit source freeze. Independent negative mutations were performed in memory without altering shared sources or the manifest.

Read-only environment-main queries completed at **2026-10-07 06:51:48 UTC**. All ten GPU apps are deployed with zero tasks and no containers. Their guard/admission names are absent, the controller registry is empty, and the local campaign group is absent. The scheduled CPU controller remains live, bound to `ap-suOdTgdc8PNSfZ3jbnsesa`, v6 price SHA `6745896e…` and its original deadline `1791408417.2529736`. Its own tick container is present; this is not a training container. Initial registry absence became an empty registry after the scheduled controller tick, consistent with its normal operation.

Claude may re-read the channel, redeploy the nine slot apps and readings app from this frozen commit, retain actual deployed IDs, then spawn longest-first and record each bound app ID/call ID. Keep the existing r2 controller and immutable guard/deadline; do not redeploy or re-arm it. The exact latest learned-n32 candidate time reconstructed from the frozen ledger and controller guard is **07:14:04.452974 UTC**; use the existing binding check rather than rounding this boundary upward. If continuation cannot fit, or another setup failure occurs, stop/report through the bound-ID path. This clearance does not authorize an r3 reset or automatic additional setup attempts. Registered per-slot admission and runtime retry limits, and the exactly-once readings gate, remain unchanged.

The continuation retains the **$259.99 conditional reserve**, the existing attempt-1 $0.50 allowance and remaining $4.50 margin. The planned image/controller lines cover the documented redeployment and controller operation; actual billing must still be reconciled. Neither cached-layer expectations nor the allowance establish settled cost or a hard platform cash ceiling. No reserve increase, additional training cell, paid proof or readings retry is authorized. This is engineering clearance; no learning or scientific result exists yet.

The reviewer performed local CPU verification and read-only remote queries only. No shared source, remote app, Dict, volume, journal, deployment, spawn, stop, commit or push was changed.
