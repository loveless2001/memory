# P2G — selective-write gate + filler phase 2×2 (PREREG DRAFT v0.1)

Status: DRAFT for codex audit. Scope authorized by user 21289 ("continue after codex commit") = draft only.
No code, no local training, no Modal spend until audit clears + user go on the ledger cap.
Base: `cb452fb` (P2D Step 2 closed). Evidence class: tiny-random-lm+taskhead, synthetic. No R3, scaling, pretrained or P3 claim.

## Questions
- Q1 (gate). Can the existing learned write gate β, started closed, learn writes that are selective at token level (binding ≫ filler) with no oracle mask, and does that recover the filler-off gain at N16?
- Q2 (phase). Is the filler-write effect a training-phase or eval-phase effect? Full train-write × eval-write 2×2 at N16 and N32.
- Not asked: why seed-0 continuity differs; address supervision; budgets beyond 1500 steps.

## Fixed protocol (all cells)
- Recipe = P2 v2 `learned` exactly (taskhead, batch 16, lr 3e-3, filler_len 40, 4 queries, 1500 steps, seed s ∈ {0,1} for init + train stream). Fixed endpoint: final params at step 1500 only; no checkpoints, no early stop, no selection.
- Final eval: fresh seed base **9_400_011** (+s), heldout, 16×16 = 256 episodes, interventions none / bank_derange / read_offset (+ registered eval-write setting below). Every contrast is **episode-paired within seed s** (same 256 episode hashes; abort if hashes differ).
- Dev telemetry: dev seed 4242, 4×16 = 64 episodes (as P2D).
- Uncertainty: existing rules module `paired` (mean diff, ±1.96·sd/√256), `reproducible` (both seeds diff ≥ 0.05 and lo > 0), `memory_use` (derange acc ≤ 0.04, none−derange lo > 0, none−read_offset lo > 0). Rules file `88dda56b…` is reused unchanged; new rules go in a separate P2G rules file.
- Absence ("excluded"): a contrast is **excluded ≥5pp** if hi < 0.05 for both seeds; otherwise "no registered gain; ≥5pp not excluded".

## Cells
New Modal training (6 cells): `gateclosed` N16 s0/s1, `gateclosed` N32 s0/s1, `filleroff` N32 s0/s1.
Existing checkpoints, evaluated locally on the fresh seed (no training): v2 `learned` N16/N32 s0/s1 (`1d62903` frozen package), P2D `filleroff` N16 s0/s1 (v1 group).

**Gate arm.** `PilotConfig.beta_bias_init = -3.0` (new field, default `None` = unchanged). It is applied in `build()` after adapter init: `beta_proj.bias.fill_(-3.0)` for both selected layers (1, 3) and both heads. It touches nothing else; σ(−3) = 0.047 vs v2 init 0.5. Weights and all other params keep the v2 RNG draws. SGMConfig/policy_id are untouched (init-only knob). Regression tests: the default build is bitwise identical to `cb452fb`; the gate build differs only in `beta_proj.bias`; old manifests/grids still validate.

**Eval-write setting E ∈ {on, off}.** `off` = tail-filler steps skip writes at eval (`filler_writes=False`, existing code); applied to heldout + interventions.

## Readings
Notation per seed: X(T, E) = per-episode score of a model trained with filler writes T, evaluated with E. v2 = (on, on). filleroff = (off, off).

**R-Q2 (2×2, N16 and N32, 4 cells per seed; all four exist after training).**
- C_T|E=off = (off,off) − (on,off); C_T|E=on = (off,on) − (on,on); C_E|T=on = (on,off) − (on,on); C_E|T=off = (off,off) − (off,on).
- "training-phase filler effect (this recipe, this N)" iff both C_T reproducible. "eval-phase filler effect" iff both C_E reproducible.
- Each C is labelled reproducible / excluded ≥5pp / neither. Interaction (C_T|E=off − C_T|E=on) is descriptive only (paired CI). No single-cause claim: any other pattern reads "phase effects not separated at N".

**R-Q1 (gate, per N).** gain = reproducible(gate − v2). sel = ρ ≤ 0.20 both seeds. mem = memory_use both seeds. half = lo > 0 both seeds for d_e = (gate_e − v2_e) − 0.5·(oracle_e − v2_e), with oracle = filleroff (off,off) same N/seed/episodes.
- `half` is only defined if the oracle has a reproducible gain at that N; otherwise the fraction is descriptive.
- gain ∧ sel ∧ mem ∧ half → "SUPPORTS: closed-init learned gate recovers ≥ half of oracle filler-off gain with selective writes".
- gain ∧ sel ∧ mem ∧ ¬half → "registered gain with selectivity; ≥ half recovery not established".
- gain ∧ ¬sel → "gain without registered selectivity (not attributable to gating; e.g. uniform low-β regime)".
- gain ∧ sel ∧ ¬mem → "gain + selectivity without registered memory-use evidence".
- ¬gain ∧ sel → "gate selective; no registered gain". ¬gain ∧ ¬sel → "no registered gain or selectivity". Both of these also carry the excluded/not-excluded label.

**Selectivity metrics (dev 4242, effective β = β actually applied; sinks excluded; binding = key ∪ value tokens).**
- ρ (registered) = mean β over all filler token-events ÷ mean β over all binding token-events, pooled over layers {1,3} × heads {0,1} × 64 episodes × batch rows.
- AUROC (descriptive) per (layer, head): positives = binding events, negatives = filler events, score = β; AUROC = P(β_bind > β_fill) + 0.5·P(tie), exact via ranks with average ties. Reported per (layer, head) plus their unweighted mean and min. A head with no applied writes in a class → AUROC undefined (null), never imputed.
- Also descriptive: class means per (layer, head) for gate, v2 and filler-off (projected and effective).

## Ledger (priced; exact numbers from a dry-run script before launch)
- Basis: top-up actuals, nonpreemptible $0.757728/container-h; walls 1500-step N64 filleroff 4630 s; 4500-step long N16 ≈ 1.5 s/step, N32 ≈ 2.3 s/step.
- Expected: gate N16 2×~0.65 h + N32 cells 4×~1.0 h ≈ 5.3 h → **≈ $4**. Conservative at the v2 medians (2.73 / 3.94 s/step) ≈ 8.8 h → $6.7.
- Reserve: 1.4× watchdog timeouts on the conservative walls + startup/replay/image/margin as in the top-up ledger → **cap request ≤ $12** (user approves). Same launcher: deploy + spawn, nonpreemptible, guard, idempotent collect, stop-verify.
- Local evaluation (baselines, 2×2 eval-only cells, telemetry) is $0.
- Alternative: run the 6 cells locally for $0 (~2 h parallel; accepts the host-loss risk seen 2026-10-05).

## Order
prereg audit → implement (gate knob, P2G rules + readings, grid/runner reuse, tests, ledger dry-run) → impl audit → user go on cap → launch → validate → readings → codex results audit + claude check.

## Unresolved
- ρ threshold 0.20 and b0 = −3 are fixed by argument (≈5× below uniform; ≈10× below v2 init), not tuned. Open to the auditor's alternative before registration.
- Should the 2×2 at N32 count as informative if both (on,·) cells sit at chance? Proposed: yes for C_T, and C_E reads "neither"/excluded.
