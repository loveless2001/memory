# P2.5 Amendment PK — campaign execution supplement (draft for the Gate-3 package)

Binds HOW the unchanged 18-cell P2.5 experiment (prereg v0.2, Amendment PK v0.4) would be executed. No paid
action is authorised by this document; launch needs codex's Gate-3 clearance AND the user's explicit cap.

## Components (all per-app isolated)
| component | file | GPU | starts | deadline |
|---|---|---|---|---|
| control-plane reaper (1 schedule, CPU) | `modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py` | — | schedule | armed once: spawn offset + longest slot + validation/setup + readings + slack; fallback after |
| 9 slot apps (one per PK1 pair) | `modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py` (`M4_PK_SLOT`) | A100-80GB | ≤ 4 admitted | one immutable candidate = the slot's v5 reserve life |
| readings app (exactly once) | `modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py` | A100-80GB | 1, retries 0 | one immutable candidate = v5 readings reserve |

Pricing/horizon file: `pk6/priced-estimate-v5.json` (estimate $114.47; per-app envelope reserve $256.38).

## Order of operations
1. Clean tree at the cleared commit; every bound sha re-checked by each runner (identity).
2. Deploy the control-plane app; `arm` (write-once id, deadline, price sha).
3. For each slot in a fixed order, within the 1800 s spawn-offset window: deploy with `M4_PK_SLOT=<slot>`, then
   `spawn` (read-only controller preflight → guard → provenance → control registration → one call).
4. Per-slot collector loop (`collect`, idempotent) until every slot is terminal or past its deadline; each
   collect stops + verifies by the bound app id, pulls evidence, exports Dicts, reports every cell.
5. Validation: every slot `stopped_verified`, every registered cell COMPLETE and valid (shared validator, frozen
   campaign registry/schema). Any FAILED / LOST / INVALID cell is reported; prereg row 1 makes the reading
   "unavailable" — no rerun, reseed or rescue.
6. Readings: deploy the readings app; `spawn` (requires step 5 + controller binding); `collect`. The readings
   script re-binds every cell from the volume, runs parity, the oracle interface first, then the remaining arms
   only for an N whose interface passed; write-once output.
7. Billing reconciliation (app-filtered, all 11 apps), terminal package for codex audit, report to the user.

## Stop rules (no operator discretion)
- A slot past its own deadline is stopped by the controller (bound id, verified); its unfinished cells are LOST.
- A worker exiting nonzero → FAILED; the co-tenant continues (policy, not immunity).
- Readings: one admitted start; crash re-entry refused before any reserved row; partial output kept, no rerun.
- No retries beyond the admitted starts, no expansion, no recipe/precision/batch change, no re-pairing.

## Out of scope here
Scientific claims (the prereg reading table governs), P3, real text, matched-storage or scaling claims.
