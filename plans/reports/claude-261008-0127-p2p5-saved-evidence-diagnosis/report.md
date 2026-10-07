# P2.5 PK: $0 diagnosis from saved evidence (claude, 2026-10-08), rev 2

**rev 2** applies codex review 21745 (`plans/reports/codex-261008-p2p5-pk-21744-diagnosis-audit/`):
- F4 claims corrected: the L20 weights were not frozen, the gates were not 0.0, and closure is not shown to cause the
  None gradients.
- F3 and F1 language narrowed.
- Every consumed file is now hash-bound.
- Probe rewritten as a readout-recipe rescue probe with a frozen rule and no causal claim.

Authority: user 21741 (option 1). Scope: claude 21742, codex 21743. Local saved files only: no forward pass, no
population generation, no Modal. Descriptive only. The original (`unavailable`) and post-hoc amended (`screen not
passed`) outcomes are unchanged. Nothing here authorizes an experiment.

Bindings: `p2p5-saved-evidence-diagnosis.py` with its imported `p2p5-diagnosis-extra-evidence-checkpoints-p2c-gate-heads.py`
produces `p2p5-saved-evidence-diagnosis.json`. The json binds 68 inputs by sha256:
- 18 cells × metrics / per-example / telemetry
- readings.json
- 8 learned-n32 checkpoints
- 2 P2C metrics files and P2C RESULTS.md
- the imported P2D paired-interval source and the extra module

Every number below is in that json. Package shas: `SHA256SUMS.txt`.

Granularity:
- 150 logged training rows (every 10th of 1,500 updates)
- 16 dev evals (every 100 updates, 64 episodes, filler 40)
- final artifact evals: 256 episodes × 4 queries, artifact population 9_300_011+s

Curriculum phase 1 = updates 0–999 with filler 0. Phase 2 = updates 1000–1499 with filler 40.

## F1. Query-time bank content and the read path (Q1)

Episode-paired none − intervention, accuracy in pp [95% CI], on the same saved artifact rows. "chg" = predictions
changed out of 1,024; +gained / −lost = correct answers.

| cell | none | bank_derange | read_offset | query_off |
|---|---|---|---|---|
| learned-n32-s0 | 7.2% | +0.0 [−0.7,+0.7]; chg 89; +6/−6 | +5.1 [+3.3,+6.8]; chg 982 | +5.0 [+3.2,+6.7]; chg 983 |
| learned-n32-s1 | 6.3% | +0.1 [−0.5,+0.7]; chg 132; +5/−6 | +2.6 [+0.9,+4.4]; chg 913 | +2.6 [+0.9,+4.4]; chg 913 |
| learned-n16-s0 | 3.2% | +0.0 [−0.4,+0.4]; chg 73 | +1.8 [+0.7,+2.9]; chg 770 | +1.8 [+0.7,+2.9]; chg 766 |
| learned-n16-s1 | 2.2% | +0.4 [−0.5,+1.2]; chg 365 | +0.3 [−0.8,+1.4]; chg 922 | +0.0 [−1.2,+1.2]; chg 918 |
| randomfixed-n32-s0/s1 | 13.0/10.5% | −0.3 / +0.4, CIs contain 0 | +10.9 / +7.4, lo > 0 | +11.0 / +7.4, lo > 0 |
| randomfixed-n16-s0/s1 | 7.7/1.7% | −0.2 / +0.0, CIs contain 0 | +5.9 / −0.2 | +5.9 / −0.2 |
| singlecell-n32-s0/s1 | 7.5/5.0% | +0.4 / +0.4, CIs contain 0 | 0 (one cell) | +5.8 / +2.1, lo > 0 |
| singlecell-n16-s0/s1 | 3.4/4.5% | +0.8 [−0.3,+1.9] / **+2.6 [+1.5,+3.8]** | 0 | +1.4 / +2.3 |
| oracle-n32-s0/s1 | 100/98.1% | +98.7 / +97.2 | +98.6 / +96.6 | +98.7 / +96.8 |

- **Prediction dependence.** read_offset and query_off change most predictions in every learned and random_fixed
  cell (766–1,024 of 1,024). bank_derange changes 68–699 in non-oracle cells. single_cell read_offset changes none,
  since it has only one cell.
- **Accuracy differences** are per cell and shown with intervals. Some cells have no accuracy drop despite many
  changed predictions: learned-n16-s1 query_off is 23 vs 23 correct with 918 changes; randomfixed-n16-s1 likewise.
- **bank_derange.** No non-oracle cell shows an established accuracy benefit from the correct episode's query-time
  bank, except singlecell-n16-s1 (+2.6 [+1.5,+3.8]). That is an exploratory artifact-population exception and does
  not change the registered outcome. Oracle: +97–99pp.
- **Boundary.** bank_derange swaps banks AFTER source ingest and leaves the source-influenced recent KV intact.
  Source-time memory use is not ruled out.

## F2. Curriculum phase 1 was solvable through a direct local route under the residual-head readout

Mean logged training accuracy, phase 1 → phase 2:

| arm | N16 s0 / s1 | N32 s0 / s1 |
|---|---|---|
| memory_off (no SGM) | 90.0 / 89.5 → 1.8 / 1.6 | 41.5 / 41.9 → 1.7 / 1.8 |
| single_cell | 98.6 / 98.8 → 2.0 / 2.2 | 52.2 / 52.8 → 6.3 / 5.9 |
| random_fixed | 98.7 / 98.6 → 2.1 / 1.9 | 52.8 / 53.0 → 10.8 / 8.6 |
| learned | 98.5 / 98.2 → 1.7 / 1.9 | 52.3 / 52.5 → 6.4 / 5.6 |
| oracle | n/a | 93.2 / 94.1 → 99.9 / 99.7 |

- With filler 0, the 2N binding tokens directly precede the query: 32 tokens at N16, 64 at N32. The runtime keeps
  4 sinks plus the 32 most recent tokens. At N16 every binding is in that window; at N32 the last 16 are.
- The residual head reads the backbone's final hidden state. memory_off has no SGM at all and still reaches 90% (N16)
  and ~42% (N32) in phase 1. A direct local route was therefore available in phase 1.
- Dev at filler 40 stays near chance (0–3.9% on 64-episode evals, updates 0–1000) for every non-oracle arm. The oracle
  is at 99–100% by update 300.
- **P2C (tiny model)** used `readout = taskhead`, which takes the memory reads as its features. That removes the
  direct final-hidden-state feature route. Context can still enter through the context-dependent query projection
  (r = Sᵀq). P2C N32 dev rose from 1.56 / 5.08% at update 1000 to 9.38 / 34.38% at 1200 and 61.33 / 69.53% at 1500
  (RESULTS.md). P2.5 learned N32 went 2.0 / 3.1% → 4.7 / 7.8% → 6.6 / 6.2%.
- **Reading:** the available local route under the residual-head readout is a plausible candidate contributor to the
  transfer failure. Its role is NOT isolated:
  - backbone, layers, dimensions and hidden scale also differ from P2C
  - learned N32 phase 1 (52%) exceeds memory_off (42%) by an amount these files cannot attribute
  - low phase-1 transfer does not prove phase 1 trained nothing in the memory path

## F3. Write gates (Q4), descriptive

Readings gate telemetry (final weights): 512 per-head binding/filler mean gates across 16 SGM corners.
- Many head/class means are near 0 or 1. **66 of 512** lie strictly between 0.01 and 0.99; that cutoff is only an
  illustrative count. For example, learned-n32-s1 L6h1 is 0.334 for binding and 0.337 for filler; learned-n16-s1 L6
  and L13 heads sit at 0.10–0.16.
- The pooled binding/filler ratio rho is 0.95–1.05 in every corner, and the mean AUROC is 0.36–0.61.
- Pooled means near endpoints and rho ≈ 1 do NOT establish saturation or non-selectivity for every head or event.
  The oracle has rho ≈ 1 and needs no gate selectivity, because its addresses separate value writes.
- Logged beta gradient medians, learned N32 (per layer and phase): ~5e-4 to 3e-7, and ~1e-15 for s1 L20.
  k_proj/value/address_mlp medians are ~7e-3 to 3e-1.
- P2C learned N32, last logged row (update 1490): beta gradient norms 0.49 and 0.077 (s0), plus s1 in the json.
  P2C final gate class means were value-higher (value 0.41–0.46 vs key 0.26–0.30 vs filler 0.29–0.35).
- Cross-model, last-row versus phase-median magnitudes are descriptive only.

## F4. learned-n32-s1 L20 (Q3): tiny gradients, small drift, low final gates; causes unresolved

- **Gradients.** L20 k_proj/value/beta grad_norm is None (absent) on 17/150 logged rows, first at update 50. Exact
  0.0 occurs on 5–9 logged rows per group, counted separately. Numeric medians are ~1e-15 to 1e-17 in both phases.
- **Updates.** update_norm is positive on 133/150 logged rows for each of these groups.
- **Weights.** L20 `beta_proj` from update 50 to 1500: all 4096 weight elements and all 4 biases change. Weight Δ L2
  0.0199 (max 5.9e-4); bias Δ L2 6.5e-4. For comparison, s0's L20 weight Δ L2 is 2.26.
- **Final gates** (readings telemetry): s1 L20 binding means are 1.06e-5, 2.01e-5, 1.93e-4 and 2.47e-8. Filler means
  are also small and nonzero.
- The s1 dev mean gate (all layers pooled) fell from 0.55 to 0.31 by update 100.
- Low gates, tiny gradients and small drift co-occur. Whether low gates caused the None gradients, when saturation
  began, and what effect it had on accuracy all remain UNRESOLVED.

## F5. Routing summaries (Q2, descriptive only)

| arm (N32) | empty-read interp. weight | effective cells | address std |
|---|---|---|---|
| P2.5 learned | 0.56 / 0.78 | 10.4 / 10.4 | 4.3 / 13.0 |
| P2.5 random_fixed | 0.20 / 0.20 | 8.6 / 8.4 | ~0.95 |
| P2.5 oracle | 0 | 117 / 127 | 19 |
| P2C learned | 0.016 / 0.0002 | 35.5 / 28.3 | — |

- Empty-read weight is a fraction of interpolation weight. Effective cells is exp(entropy) of cell norms; it is not
  a fact count and not collision evidence.
- Key-to-cell alignment is UNAVAILABLE: no event traces were saved, and weights cannot recover input-conditioned
  routes.

## Not established
- Why the learned arms fail. F2 is a plausible candidate contributor, not a demonstrated cause.
- Source-time memory use.
- Collision or overwrite.
- The role of the gate behaviour (F3/F4).

## Proposed follow-up (NOT authorized; needs a frozen proposal, implementation audit and explicit user approval)
**Readout-recipe rescue probe.** It asks: does the P2C readout recipe rescue learned N32 on frozen Qwen3-0.6B?

- **Arms:** learned N32 × s0/s1 with `readout = taskhead`. Everything else stays as in P2.5: curriculum, 1,500
  updates, layers, optimizer and data.
- **Population:** artifact population 9_300_011+s. These are the same episodes as the saved P2.5 learned-n32 rows,
  so the comparison is episode-paired by hash. The reserved population is never used.
- **Comparator:** the existing P2.5 learned-n32 artifact rows (residual-head readout). Dev evals are logged but are
  not decision inputs.
- **Frozen rules, reused and unchanged:**
  - recipe contrast = P2G `classify` over the per-seed `P2D.paired(taskhead, residual-head)` intervals (5pp, lo > 0,
    both seeds)
  - episode-specific bank dependence = `P2D.memory_use` on the taskhead rows (bank_derange accuracy ≤ 0.04, and
    none−derange and none−read_offset lo > 0)
  - all interventions retained
- **What it can show:** whether the changed readout recipe improves learned N32, and whether any improvement depends
  on the episode's bank.
- **What it CANNOT show:** whether the local shortcut was the main blocker, in either direction. Taskhead also changes
  feature dimensions, head initialization, gradient routes and optimization, and context still enters through q.
- **Not included:** random_fixed + taskhead would add an address-learning contrast but not fix that limitation. It
  stays out unless separately selected and capped.
- **Cost:** about $20 (the learned-n32 slot actually billed $20.10). This is a historical reference, not a cap.

## Unresolved questions
- Whether to write the frozen probe proposal, or stop at this diagnosis. That is the user's call.
