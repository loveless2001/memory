# B3 (shift2 bundle) final readout r2: VALID_NEGATIVE, memory_used FALSE

r2 supersedes `b3-final-readout.md` (cccf237, sha ca3ac71f; kept unchanged: it is codex's as-found copy). Applies codex
22603/22604 (terminal audit PASS / VALID_NEGATIVE, report `memory/plans/reports/codex-261010-gravity-wait55-b3-terminal-audit/review.md`
sha 64c780ef…). Run, gate, billing and hash sections of r1 stand unless changed below.

## Scope
Shift2 bundle (B2 fill+anchor recipe + `sgm.feature_shift=2`), **training seed 0**, **development seed 4242** (reused,
inspected dev data), one run, 1,500 updates. Exploratory dev screen.

## Gate (unchanged)
Final normal 8/256, bank-deranged 8/256, drop 0; needs ≥ 12 AND drop ≥ 6 → **not met**. Codex verified all 16
registered dev evals and 166 telemetry rows; final checkpoint step 1500 (resume.pt sha c9bb2293…), 46 adapter/head tensors
= `trained_parameters.safetensors` 7e0b4999….

## Telemetry (corrected: near-steady, NOT frozen)
- Beta class means barely move after update 300 (ranges: key 4.2e-4, value 3.6e-4, filler 2.4e-4; ≈ .313 each), but
  beta PARAMETERS keep updating: final logged update norms L6 .0205 / L13 .0037 / L20 7.5e-6 / L27 2.9e-5.
- Alpha ranges after update 540: L6 2.1e-5, L13 1.1e-4, L20 2.6e-4, L27 0 (L27 output/alpha are unused by the
  taskhead by design). Final .018274 / .018993 / .018278 / .017986.
- Class-averaged means cannot diagnose freezing. r1's "flat/frozen" wording is withdrawn; parameter freezing is not
  established and no mechanism is claimed.

## Reading (corrected)
The $0 previous-key probe (3d7b4d1) ran on the **shift1** runtime: its V+K reading concatenated the key features
offline. It showed key information is partly present in the value-token input. It did NOT test live shift2 recovery.
B3 trained the shift2 bundle under this recipe and shows no demonstrated memory use (training seed 0, dev seed 4242).
Why is not established.

## Billing (still provisional)
App-attributed hourly and daily reports agree at $6.64800992 (codex). The 03Z hour looks incomplete, so this is not a
settled cost; the wall-time estimate is ≈ $8.29. Both are under the $16.3035352 reservation and the $17 cap. Codex holds
one billing recheck.
