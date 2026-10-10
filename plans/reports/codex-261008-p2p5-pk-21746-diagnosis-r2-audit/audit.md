# Saved-evidence diagnosis rev 2: PASS

Reviewed owner commit `d3d4999e1b4058059064af8e5e73b86906441fb5`. All five findings from review 21745 are closed for this descriptive diagnosis. This is not approval of an experiment or its implementation.

- The four package hashes and their frozen bytes match. All 68 indexed inputs match their SHA256s. The original 55 input bindings and original intervention, phase, gradient and gate statistics are unchanged from the independently audited first version.
- The added checkpoint and P2C inputs match the bytes independently inspected during the prior review. The new extra module matches its frozen commit. Independent scalar double arithmetic agrees with the checkpoint norms, changes and changed-element counts. All added update-count fields agree with the saved telemetry.
- The 512 head/class gate means, 66 intermediate means, individual L20 gate means and P2C reference values agree with the saved inputs. The rounded development values are explicitly sourced to the P2C report.
- Replaying the reviewed owner script into this reviewer directory reproduces the rev 2 JSON byte for byte. The focused revision verifier records 713 passing checks; many are per-field comparisons.
- The report now describes small L20 drift and low nonzero final gates, preserves absent versus numerical-zero gradients, and leaves causes unresolved. It limits saturation claims, distinguishes prediction changes from accuracy effects, and labels the artifact-population exception exploratory.
- The proposed probe now uses the existing ordered contrast and memory-use rules and removes the unsupported binary causal interpretation. It evaluates a changed readout recipe; it cannot identify or exclude the local shortcut as the main blocker. The phase-1 memory-off curves establish an available local route, whose role in the transfer failure remains unresolved.

Reproduce with `.venv/bin/python plans/reports/codex-261008-p2p5-pk-21746-diagnosis-r2-audit/check-revision.py`. Details and hashes are in `audit-evidence.json`.

Scope remained local saved files and tensor inspection only: no model construction or forward pass, population generation, Modal call, or modification of the owner/campaign evidence. Original unavailable and post-hoc amended screen-not-passed outcomes remain distinct. Any future experiment still requires a frozen operational proposal, implementation audit and explicit user authorization with a cap. The proposed use of already examined artifact episodes is an exploratory diagnostic comparison.
