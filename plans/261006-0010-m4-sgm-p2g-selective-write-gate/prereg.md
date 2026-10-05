# P2G — selective-write gate + filler train×eval 2×2 (PREREG DRAFT v0.2)

v0.2 amends v0.1 (`86e9bab`) per codex audit `plans/reports/codex-261006-p2g-prereg-v01-audit.md` (items 1–6).
Evidence class: tiny-random-lm+taskhead, synthetic. No R3, scaling, pretrained or P3 claim.

## Gates (item 6)
1. Prereg clearance (codex) → authorizes implementation + CPU preflights only: unit/regression tests, step-0 init telemetry, parity fixtures (§Runtime), ledger dry-run. No training cell, no fresh-seed evaluation.
2. Implementation audit (codex) + user's scoped training authorization with the reviewed cap → execution of the six training cells. Local execution requires the same authorization, even with no Modal charge.
3. After all six cells validate → one readings run (all fresh-seed evaluations) → codex results audit + claude check.
User 21289 authorized drafting only.

## Questions
- Q1 (gate). The gate recipe shifts the β bias toward smaller writes, with no oracle mask. Does it reproducibly beat historical v2 with registered **pooled filler suppression**, and recover ≥ half of the filler-off gain?
- Q2 (phase). These are registered contrasts between training recipes (filler writes on/off) and evaluation settings (on/off) at N16 and N32. No unique causal blocker is asserted.
- Limits carried forward: historical cohorts differ in source/host (v2 `1d62903`/`a89284ea`, P2D `31aa4c8`/`d4effd0c`, P2G new source). The Step 2 seed-0 prefix discrepancy is unresolved. Same episode hashes make the evaluations paired; they do not make the training histories identical.

## Fixed protocol
- Recipe = P2 v2 `learned`: taskhead, batch 16, lr 3e-3, filler_len 40, 4 queries, 1500 steps, seed s ∈ {0,1} for init + train stream. Fixed endpoint = final params at step 1500; no checkpoints, no early stop, no selection. b0 and the ρ threshold are frozen here, never tuned on results.
- Final eval: fresh seed base **9_400_011**+s, heldout, 16×16 = 256 episodes × 4 queries, interventions none / bank_derange / read_offset, under the registered eval-write setting E.
  - Comparisons are episode-paired within seed s; abort if the hash sets differ.
- Uncertainty: rules module `88dda56b…` unchanged (`paired`, `reproducible`, `memory_use`). New rules go in a separate P2G rules file.

**Contrast classifier (ordered, total).** For a contrast with per-seed paired CIs:
1. **reproducible gain** — both seeds diff ≥ 0.05 and lo > 0;
2. **reproducible loss** — both seeds diff ≤ −0.05 and hi < 0;
3. **positive gain ≥5pp excluded** — both seeds hi < 0.05 (a bound, not proof of no effect);
4. **neither**.

Classes are assigned from the measured intervals at every N. Nothing is preset from point accuracies.

## Cells and inputs
**New training (6):**
- `gateclosed-learned-n16-s0/s1`, `gateclosed-learned-n32-s0/s1`;
- `filleroff-learned-n32-s0/s1`;
- new group `p2g-selective-write-v1`.

**Reused checkpoints (no training; identities validated before any evaluation; never relabelled into the new group):**

| corner | id | group | git / source | manifest sha | params sha |
|---|---|---|---|---|---|
| v2 (on) | main-learned-n16-s0 | p2-load-sweep-v2 | 1d62903 / a89284ea | 355b2b1f… | 3502f146… |
| v2 (on) | main-learned-n16-s1 | " | " | dfe3e410… | a92e8818… |
| v2 (on) | main-learned-n32-s0 | " | " | 93271938… | 18a19add… |
| v2 (on) | main-learned-n32-s1 | " | " | 93b60a21… | 3c2c214f… |
| filleroff (off) | filleroff-learned-n16-s0 | p2d-diagnostics-v1 | 31aa4c8 / d4effd0c | c8cd8bb4… | cc8636da… |
| filleroff (off) | filleroff-learned-n16-s1 | " | " | 3b2cd13d… | 9d1a5f33… |

Full hashes, paths and each cell's exact training config go in a committed inputs index (`configs/m4_sgm_p2g_inputs.json`) checked before evaluation.

**Gate knob (item 4).** New `PilotConfig.beta_bias_init: float | None = None`; `None` = unchanged.
- The gate arm sets −3.0. `build()` then applies `beta_proj.bias.fill_(-3.0)` in layers 1 and 3 (both heads) after the normal init.
- This is a **bias shift 0 → −3**; actual β = σ(W_β·x + b) with W_β's random nonzero draws unchanged. σ(−3) = 0.047 is the zero-input intercept, not every token's initial gate. The measured step-0 per-class β (dev) is a preflight output.
- The field is recorded in the pilot config, run manifest and result label (`DIAGNOSTIC-beta-bias-3`). SGMConfig/policy_id are unchanged.
- Tests:
  - the default build is bitwise identical to `cb452fb`;
  - the gate build differs only in `beta_proj.bias`;
  - old manifests and grids still validate.

## Runtime (item 1)
One common observer evaluates every T×E corner on the fresh seed: the P2G source tree, with existing `filler_writes` ingest masking as the E=off override. The frozen `1d62903` package has no E=off path. Before any fresh-seed use, two parity gates on fixed fixtures must pass, else STOP and report:
- **P-on.** Common observer, E=on, v2 N16/N32 s0/s1, seed 9_300_011+s. Rows must equal the committed Step 2 frozen-observer baseline rows (`step2-full-v1-r2/baseline-v2-learned-*-fresh-rows.jsonl`), both parsed-equal and byte-equal.
- **P-off.** Common observer, E=off, P2D filleroff N16 s0/s1, seed 9_300_011+s. Rows must equal those cells' validated Modal `per_example_results.jsonl` (source d4effd0c).

The analysis code and rules hashes plus the observer source hash are recorded. The checkpoint-loading path is shared across all corners.

## Q2 readings (2×2 per N ∈ {16, 32}; per seed X(T,E))
- C_T|off = X(off,off) − X(on,off); C_T|on = X(off,on) − X(on,on); C_E|Ton = X(on,off) − X(on,on); C_E|Toff = X(off,off) − X(off,on). Each gets the classifier label.
- T = both C_T are reproducible gains; E = both C_E are reproducible gains.
  - T∧E → "reproducible gains for both the no-filler-write training recipe and the no-filler-write eval setting".
  - T∧¬E → "reproducible gain for the no-filler-write training recipe at both eval settings; eval-setting conjunction not met".
  - ¬T∧E → "reproducible gain for the no-filler-write eval setting under both training recipes; training-recipe conjunction not met".
  - ¬T∧¬E → "neither conjunction met".
  - Every reading lists all four contrast labels. The interaction (C_T|off − C_T|on, paired CI) is descriptive and never changes a label.

## Q1 readings (per N)
- gain = classifier(gate − v2) is "reproducible gain".
- sup = ρ ≤ 0.20 for both seeds.
- mem = memory_use passes for both seeds.
- half ∈ {true, false, null}:
  - defined only if classifier(oracle − v2) is a reproducible gain, where oracle = filleroff X(off,off), same N, seed and episodes;
  - then true iff lo > 0 for both seeds on d_e = (gate_e − v2_e) − 0.5·(oracle_e − v2_e), else false;
  - otherwise **null (unavailable)**, never coerced to false.

Ordered table (total; all flags, intervals and labels are retained in the report):
1. gain ∧ sup ∧ mem ∧ half=true → "SUPPORTS: gate recipe reproducibly beats v2, recovers ≥ half of the oracle filler-off gain, with registered pooled filler suppression and memory use".
2. gain ∧ sup ∧ mem ∧ half=false → "reproducible gain with pooled suppression and memory use; ≥ half oracle recovery not established".
3. gain ∧ sup ∧ mem ∧ half=null → "reproducible gain with pooled suppression and memory use; half-oracle comparison unavailable (oracle prerequisite not met)".
4. gain ∧ sup ∧ ¬mem → "reproducible gain with pooled suppression; no registered memory-use evidence".
5. gain ∧ ¬sup → "reproducible gain without registered pooled suppression; mechanism unresolved".
6. ¬gain ∧ sup → "registered pooled suppression; gate−v2 contrast is <label>".
7. ¬gain ∧ ¬sup → "no reproducible gain and no registered pooled suppression; gate−v2 contrast is <label>".

## Suppression statistic (item 2)
- Population, on dev 4242: 4 batches × 16 rows = **64 episodes**. Token events per (layer ∈ {1,3}, head ∈ {0,1}). Sinks are excluded; binding = key ∪ value.
  - Filler: 64·40·4 = 10,240 events. Binding: 64·2N·4 = 8,192 (N16) or 16,384 (N32).
- Effective β = β actually applied. A skipped write (E=off mask) is a skipped event; in ρ it contributes **0** to the effective class mean. A write that was applied with a numerically tiny β is an applied event.
- ρ = mean effective β(filler events) ÷ mean effective β(binding events). It requires all β to be finite and the binding mean > 0, else it fails closed (SystemExit; no epsilon). It is registered for the gate arm (E=on) only; v2 and the other corners are descriptive.
- **Headline is limited to pooled filler suppression.** No token- or head-level claim is made.
- AUROC is descriptive, per (layer, head), over **applied** events only (skipped excluded). Binding is positive, score = effective β, P(bind > fill) + 0.5·P(tie) via average ranks. Undefined (an empty class) → null.
  - All four head values are reported, plus mean/min over defined heads and the count of defined heads.
  - Projected and effective class means are reported for every corner.

## Ledger (item 5)
Existing deadline policy, unchanged. Each timeout = 1.4 × the seed-specific v2 full-cell wall, with wall factor 1.0 for both arms. Rate $0.757728 per container-h (4 cores / 8 GiB, 3× nonpreemptible). Existing overheads and margins apply.

Timeouts (s):

| | s0 | s1 |
|---|---|---|
| gateclosed N16 | 6106 | 4640 |
| gateclosed N32 | 8773 | 6952 |
| filleroff N32 | 8773 | 6952 |

Admission reservation per codex: **$12.32978160**:
- training timeouts $8.88141408
- startup/teardown $0.45463680
- replay $0.53040960
- CPU-overuse $0.66332112
- image $0.30
- fixed $1.50

**Cap request to the user: $13** (≥ reservation), to be confirmed only after the implementation and exact dry-run ledger are reviewable. Expected spend ≈ $4 (top-up walls ran 1.5–2.3 s/step); that is not a reservation.

New scoped runner `modal-runners/modal-m4-sgm-p2g-nonpreemptible-spawn.py`:
- group `p2g-selective-write-v1`, exactly the 6 IDs above;
- its own claims and attempt counter, persisted call IDs, idempotent collect and stop-verify by app id;
- the same guard and watchdog;
- source and runner hashes bound at launch.

Shared helpers are factored rather than copied where that is safe. The old top-up IDs, group and claims are untouched, and no shared budget changes.

## Unresolved
- If P-on or P-off fails, Q2's fresh-seed corners need a reviewed observer fix before any reading. No fallback to mixed observers.
