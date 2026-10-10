# B1 run v1 readout r2 — corrections to r1 (codex 22143/22144 audit)

r1 (`b1-run-v1-readout.md`, c002fd2) is kept unchanged; this file supersedes its interpretation lines. Core numbers unchanged and independently recomputed by codex: valid PARTIAL, pre-fill missing weight 0.2600495 at 100 (A0 0.9927544), kept_through_100 false, params sha 96d40040…, app stopped 04:16:07Z, 0 tasks, 0 containers.

## Corrected
1. **Train loss.** r1 said loss sits above ln 64, so reads add noise. WRONG: the logged loss includes 0.1 × read_anchor. Task CE = loss − 0.1 × anchor: 4.232 (0), 4.164 (10), 4.178, 4.190, 4.165, 4.163, **4.147 (60), 4.148 (70)**, 4.168, 4.164 (90); ln 64 = 4.159. Task CE ≈ the uniform/head-bias level, like A0. No evidence either way that reads add noise.
2. **"Fill does not carry most reads."** WRONG inference: partially absent reads also receive the fill (weight = missing mass). Mean missing mass is still 26% at 100; only the fully-absent share is 13.2%. The fill's contribution to predictions needs an ablation/norm or task intervention, not done.
3. **"Reads and writes both spread wider."** Occupancy growth (34 → 55 cells) means more distinct written cells; it does not by itself establish write-address spread. Read-address std 0.97 → 10.6 cells stands as measured.
4. **Step-time cause.** 8.6–9.0 s vs A0 5.03 s (1.73×) is observed; the cause is not isolated (fill gather is a candidate, not shown).
5. **1500-step cost.** A 1500-step run enters the unprofiled filler-40 phase at step 1000. Short filler-0 timing does NOT bound an all-in $10–12 or a $15 ceiling. Any long-run budget must come from an enforced deadline plus a profile, not this extrapolation.
6. **Queue time.** The 0.67 s gap is local pre-call setup. Call → worker entry was ~17.9 s (queue + startup).
7. **Billing.** $0.71087544 provisional (03:00 $0.06919454 + open 04:00 $0.64168090; backfilled from r1's $0.70688). Codex reconciles after 05:05Z.

## Still true
- Dev accuracy 8/256 at 100 vs 9/256 at init: no demonstrated dev gain (100 updates is not designed to show retrieval).
- On one seed, the fill+anchor bundle substantially changed recorded support geometry vs A0; it did not pass the retention band.
