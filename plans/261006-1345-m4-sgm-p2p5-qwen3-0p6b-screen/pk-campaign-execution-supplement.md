# P2.5 Amendment PK — campaign execution supplement (Gate-3 package, rev 3: launch attempt 2 after the attempt-1 hold)

Binds HOW the unchanged 18-cell P2.5 experiment (prereg v0.2, Amendment PK v0.4) would be executed. No paid
action is authorised by this document; launch needs codex's Gate-3 clearance AND the user's explicit cap.

## Components (all per-app isolated)
| component | file | GPU | starts | deadline |
|---|---|---|---|---|
| control-plane reaper (1 schedule, CPU) | `modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py` | — | schedule | armed once: spawn offset + longest slot + validation/setup + readings + slack; fallback after |
| 9 slot apps (one per PK1 pair) | `modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py` (`M4_PK_SLOT`) | A100-80GB | ≤ 4 admitted | one immutable candidate = the slot's v6 reserve life |
| readings app (exactly once) | `modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py` | A100-80GB | 1, retries 0 | one immutable candidate = v6 readings reserve life |

Pricing/horizon file: `pk6/priced-estimate-v6.json` (estimate $116.31; per-app planning reserve $259.99 —
a CONDITIONAL reserve under the ledger's stated assumptions, not a price guarantee, platform cash ceiling or
unconditional worst case). v5 is preserved byte-for-byte; v6 records its sha and the reason (codex 21617 R6).

## Source / analysis binding (codex 21617 R2; prereg R5)
- Frozen dependency manifest `configs/m4_sgm_p2p5_campaign_analysis_manifest.json` (non-circular; its own sha is
  carried by the launcher, the readings report and the package index):
  - `analysis`: the readings script + the EXACT closure of script modules it reaches (pretrained observer, P2.5 /
    P2G / P2D decision rules, common observer, manifest helper) + grid, campaign registry/schema, prereg, amendment;
  - `launch`: the three runners, reaper logic, shared stop logic, collector poll module, v6 ledger, this
    supplement and the source bridge;
  - memsub tree sha256.
- Every spawn (slots, readings) refuses a dirty tree or any manifest mismatch (both sections).
- The readings run verifies identity (memsub + manifest sha), every analysis file and the exact reached closure
  BEFORE any evidence or population access, and again at the end together with every bound checkpoint's bytes.
  An end mismatch makes every reading "unavailable" (prereg row 1); computed values stay, labelled.

## Order of operations
1. Clean tree at the cleared commit; manifest verified by each spawn; each runner re-checks its identity.
2. PRE-DEPLOY (inert, no spawn, no Dict): the 9 slot apps (`M4_PK_SLOT=<slot>`) and the readings app, so no image
   build can consume the spawn window (attempt 1 lost it to a failed build). Any failure stops here at $0 GPU.
3. Deploy the control-plane app; `arm` (write-once id, deadline, price sha) on the `-r2` control Dicts.
4. Within the 1800 s spawn-offset window, `spawn` each slot in the FIXED order of descending reserve life
   (learned-n32, oracle-n32, random_fixed-n32, single_cell-n32, learned-n16, random_fixed-n16, single_cell-n16,
   memory_off-n32, memory_off-n16) (manifest + read-only controller preflight → guard → provenance → control
   registration → one call). Only the longest slots are window-bound, and they go first.
5. Per-slot collector loop (`collect`, idempotent) until every slot is terminal or past its deadline. Each collect:
   validates provenance first (nonempty bound id, finite deadline, identity, this slot) or refuses with no side
   effect; stops via the strict wrapper (bound id required; a replaced live app is refused); verifies independently
   (stopped or unlisted, zero tasks, no containers; raw rows/errors kept) → `stopped_verified` or
   `shutdown_unresolved`; writes that evidence durably; fetches into a fresh `collect-<k>` directory; exports Dicts;
   reports every cell (COMPLETE validated / FAILED / LOST / INVALID with cause). A failed fetch or Dict export
   leaves every cell UNAVAILABLE (older local snapshots are never validated as fresh).
6. Validation: every slot `stopped_verified`, every registered cell COMPLETE and valid. Any FAILED / LOST /
   INVALID / UNAVAILABLE cell is reported; prereg row 1 makes the reading "unavailable" — no rerun, reseed, rescue.
7. Readings (app pre-deployed in step 2): `spawn` (requires the step-6 validation + manifest + controller binding); `collect` (same
   provenance/strict-stop/verification rules). Inside the one run: binding → bind 18 cells → parity (18 cells, first
   artifact batch) → phase 1: oracle interface at N32, then the N16 transfer (both before any other reserved
   access; oracle on none / bank_derange / read_offset per the prereg memory-arm matrix) → phase 2: remaining arms
   only at each N whose interface passed (independent per-N gating) → registered table → end binding; write-once.
8. Billing reconciliation (app-filtered, all 11 apps + attempt 1), terminal package for codex audit, report to the user.

## Stop rules (no operator discretion)
- A slot past its own deadline is stopped by the controller (bound id, verified); its unfinished cells are LOST.
- A worker exiting nonzero → FAILED; the co-tenant continues (policy, not immunity).
- Readings: one admitted start; crash re-entry refused before any reserved row; partial output kept, no rerun.
- No retries beyond the admitted starts, no expansion, no recipe/precision/batch change, no re-pairing.
- No collector or operator stop by app name alone, ever.

## Out of scope here
Scientific claims (the prereg reading table governs), P3, real text, matched-storage or scaling claims.

## Launch attempt 1 (2026-10-07, user 21627 "go"; held, codex 21630)
Controller deployed + armed (ap-eqwdT119XvSoBJC1I2kDqC); the first slot deploy (learned-n32) failed at image build:
the slot runner's module-level `M4_PK_SLOT` refusal ran inside the `_build_environment` build container (the `.env`
layer comes after `run_function`). No spawn, no slot/readings Dict, no volume path; the idle controller was stopped
by its bound id and verified. Fix: the refusal is local-only (`modal.is_local()`), `run_slot` fails closed on an
unset slot before admission. Reset: the attempt-1 control Dicts are preserved untouched (exported under
`pk-campaign-launch/attempt-1-failed-slot-image/`); attempt 2 uses `-r2` control Dict names.
