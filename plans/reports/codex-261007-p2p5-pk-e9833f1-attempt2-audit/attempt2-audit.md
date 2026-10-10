# Final attempt-2 repair/reset audit — e9833f1

**CLEARED for the documented attempt-2 startup sequence within the existing scoped campaign approval.** Review target: `e9833f192469c5a7cc9be2aeb60afffb5709921d`, submitted in gravity 21636. Claude held submitted paths and remote state unchanged during review (21639). The tracked implementation diff against HEAD remains empty.

User 21627 approved the unchanged 18-cell campaign under the $259.99 conditional reserve. Attempt 1 admitted no training or readings calls. This repair continues that approved campaign, preserving the failed setup and accounting for its charges within the same reserve; it does not repeat a trained cell, reset an admitted epoch or expand the experiment. Clearance covers the single documented attempt-2 setup, not open-ended additional setup retries.

## Verification

| Item | Result |
|---|---|
| Final package index | All **33 file hashes** match; index SHA `1bc47a4ed5e0bc9b724323dffcd9041ad087954c60f27370b7845e159acc4d24` |
| Dependency manifest | SHA `4ff9c9306dbf5c234c0f7e75d32b7897c1615143e920e468ab9e0ee1eb4ee77b`; launch manifest verifies |
| Scientific implementation | Analysis section and memsub tree unchanged; memsub SHA `2eee4228124e9d292ed4079476ca276e8ce8f9ac7c8d83d44bcd51333687a19b` |
| Protected bytes | Prereg, Amendment PK, grid, v5/v6 ledgers, rev2 index and original rev2 mutation evidence unchanged |
| Independent tests | **75 passed, 2 opt-in slow tests skipped**, 10.22 s |
| Build-context repair | Final runner bytes match the independently probed snapshot; old build-context import fails, repaired import succeeds, absent runtime slot refuses before admission, invalid local slots refuse, all nine identities preserved |
| Hygiene exception | Original evidence is pinned to SHA `26710b55…`; parsed sidecar equals its JSON object; a private one-byte change is rejected |
| Spawn order | The fixed order equals descending v6 slot reserve life |

Test command: `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 timeout 180s .venv/bin/python -m pytest -q tests/test_sgm_pk_campaign_*.py tests/test_sgm_pk_control_plane_reaper_and_manifest_label.py tests/test_experiment_artifact_hygiene.py`.

Evidence: [test log](independent-tests.log), [package checks](package-checks.json), [hygiene mutation probe](hygiene-mutation-probe.json), [prior independent build-context probe](../codex-261007-p2p5-pk-21629-launch-hold-audit/build-import-preview-probes.json).

The indexed owner full-suite log reports **464 passed / 2 skipped**, with both the original hygiene failure and the successful rerun preserved. I checked the hashes and logs, without independently repeating the full suite. The original mutation evidence has an `EXIT_STATUS=0` console trailer. Preserving those previously indexed bytes with an exact-SHA exception and a strict parsed sidecar is acceptable; arbitrary changed bytes do not receive that exception. The new mutation logs are strict JSON with separate exit evidence and identify the intended regression tests among the failures.

No new numerical implementation or analysis change occurred, so the previously verified 11-case bitwise tiny parity and accepted GPU resume proof remain applicable. This audit did not rerun GPU proof, slow tiny readings or a paid image build. CPU import tests establish the repair's control flow; the next real build supplies operational confirmation. The installed Modal SDK initializes its task lifecycle manager before user-function hydration, consistent with `modal.is_local()` being false in the image-build function context.

## State preservation and execution order

Independent read-only queries in environment `main`, completed at **2026-10-07 06:35:57 UTC**, verified both attempt-1 app IDs stopped, zero tasks and no containers. All three original control Dict names remain present. The three `-r2` control Dict names and all campaign slot/readings guard/admission names are absent. See [live state verification](live-state-verification.json) and retained raw query responses.

The controller, slot and readings runners agree on the new control guard/registry names; ticks derive from the new guard name. Original attempt-1 Dicts, exports, failure logs and billing snapshot are preserved. No deletion or journal rewrite is proposed. Bind actual post-deploy app IDs in the fresh guard/provenance and retain them in the launch handoff.

Pre-deploying the nine slot apps and readings app is compatible with the protocol: their GPU functions have no schedule or warm minimum, and deployment does not invoke them. Image-building CPU can still incur charges. Build all ten images before deploying/arming the controller, then spawn the nine slots in the documented order within the 1800-second window. The readings call still requires step-6 validation, its one-start admission guard and all analysis bindings. Another pre-deploy failure stops the sequence and is reported; this clearance does not authorize automatic further setup attempts.

The exact matrix is unchanged: four trained arms × N16/N32 × seeds 0/1 = 16, plus two oracle N32 cells = 18. Oracle N16 is transfer evaluation of the same N32-trained checkpoints.

## Accounting and limits

V6's runtime estimate and conditional reserve are unchanged from the independently reconstructed model: approximately **$116.31 runtime** and **$259.99 conditional reserve**. Attempt 1 receives **$0.50 from the existing $5 margin**, leaving **$4.50**. The eleven planned image lines and controller line remain assigned to attempt 2, avoiding reuse of those allowances for both attempts.

The $0.00004958 attempt-1 controller reading is a **partial hourly snapshot**. Failed-build billing remains **unresolved**, not app-attributed in that snapshot. The $0.50 allocation is an accounting allowance, not a settled invoice or verified cost ceiling. The user handoff should say billing remains unsettled; “a few cents at most” has not been established by the available billing evidence. Reconcile attempt-1 and attempt-2 actuals separately against the same total reserve. The earlier proof's separate billing hold remains separate.

The reserve retains its stated timing, restart, CPU/RAM, I/O and stop-latency assumptions. It is not a platform cash ceiling or unconditional worst case. Registered admission limits, deadline bindings, no reseeding/rescue and the one-start readings rule remain unchanged.

Claude can re-read the channel and execute this documented attempt-2 setup under user 21627's existing campaign authorization. This is engineering and operational clearance, not a scientific result or authorization for additional experiments, paid proofs, expanded reserve, extra training starts or further setup retries.

No shared source, proof artifacts, remote app, Dict, volume path or journal was modified by this audit. No deployment, spawn, remote stop, commit or push was performed.
