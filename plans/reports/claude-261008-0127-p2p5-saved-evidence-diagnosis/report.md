# P2.5 PK: $0 diagnosis from saved evidence (claude, 2026-10-08)

Authority: user 21741 (option 1). Scope: claude 21742, codex 21743. Local saved files only: no forward pass, no
population generation, no Modal. Descriptive only. The original (`unavailable`) and post-hoc amended (`screen not
passed`) outcomes are unchanged. No follow-up is authorized by this report.

Bindings:
- script `p2p5-saved-evidence-diagnosis.py`
- output `p2p5-saved-evidence-diagnosis.json`, which holds the sha256 of every consumed file (55 inputs = 18 cells ×
  metrics/per-example/telemetry + readings.json). Shas are in `SHA256SUMS.txt`.
- extra read-only inspection, quoted inline below:
  - learned-n32 s0/s1 checkpoints gen-1/2/10/30, L20 `beta_proj` parameters
  - P2C curriculum-learned-n32 metrics.json and `readings-v1/RESULTS.md`

Telemetry granularity:
- 150 logged training rows (every 10th of 1,500 updates)
- 16 dev evals (every 100 updates, 64 episodes, filler 40)
- final artifact evals (256 episodes × 4 queries)

Curriculum phase 1 = updates 0–999 with filler 0. Phase 2 = updates 1000–1499 with filler 40.

## F1. Query-time bank content: no established accuracy benefit, within the bank_derange boundary (Q1)

Paired none − intervention on the same saved artifact rows (episode-paired interval exactly as P2D `paired`).
Each intervention entry gives the paired diff in pp [CI], then predictions changed of 1,024, then answers gained/lost.

| cell | none | bank_derange | read_offset | query_off |
|---|---|---|---|---|
| learned-n32-s0 | 7.2% | +0.0 [−0.7,+0.7]; 89; +6/−6 | +5.1 [+3.3,+6.8]; 982 | +5.0 [+3.2,+6.7]; 983 |
| learned-n32-s1 | 6.3% | +0.1 [−0.5,+0.7]; 132; +5/−6 | +2.6 [+0.9,+4.4]; 913 | +2.6 [+0.9,+4.4]; 913 |
| learned-n16-s0/s1 | 3.2 / 2.2% | +0.0 / +0.4, CIs include 0 | +1.8 / +0.3 | +1.8 / +0.0 |
| randomfixed-n32-s0/s1 | 13.0 / 10.5% | −0.3 / +0.4, CIs include 0 | +10.9 / +7.4 | +11.0 / +7.4 |
| singlecell-n32-s0/s1 | 7.5 / 5.0% | +0.4 / +0.4, CIs include 0 | 0 (one cell) | +5.8 / +2.1 |
| oracle-n32-s0/s1 | 100 / 98.1% | +98.7 / +97.2 | +98.6 / +96.6 | +98.7 / +96.8 |

- Oracle: swapping in another episode's bank removes everything. The correct episode's bank carries the answer.
- Learned, random_fixed and single_cell: the bank swap changes 68–699 predictions per cell, but gained ≈ lost. No
  paired accuracy benefit from the correct episode's bank is established. The one exception is singlecell-n16-s1,
  at +2.6 [+1.5,+3.8].
- Boundary (codex 21743 #2): bank_derange swaps banks AFTER source ingest and leaves the source-influenced recent KV
  intact. Source-time memory use (memory reads during ingest flowing into later tokens' KV) is NOT ruled out.
- The query-time read path does matter: read_offset and query_off lower accuracy and change 75–100% of predictions (single_cell read_offset: 0, one cell).
  These are large perturbations of the read path. They do not show episode-specific retrieval.

## F2. Curriculum phase 1 is solvable WITHOUT memory under the residual-head readout (strongest finding)

Mean logged training accuracy, phase 1 → phase 2:

| arm | N16 s0 / s1 | N32 s0 / s1 |
|---|---|---|
| memory_off (no SGM at all) | 90.0 / 89.5 → 1.8 / 1.6 | 41.5 / 41.9 → 1.7 / 1.8 |
| single_cell | 98.6 / 98.8 → 2.0 / 2.2 | 52.2 / 52.8 → 6.3 / 5.9 |
| random_fixed | 98.7 / 98.6 → 2.1 / 1.9 | 52.8 / 53.0 → 10.8 / 8.6 |
| learned | 98.5 / 98.2 → 1.7 / 1.9 | 52.3 / 52.5 → 6.4 / 5.6 |
| oracle | n/a | 93.2 / 94.1 → 99.9 / 99.7 |

- With filler 0, the 2N binding tokens directly precede the query: 32 tokens at N16, 64 at N32. The runtime keeps the
  4 sinks plus the 32 most recent tokens. At N16 every binding is in that window; at N32 only the last 16 bindings are.
  The residual head reads the backbone's final hidden state, which attends to that window. memory_off, which has no
  SGM at all, reaches 90% (N16) and ~42% (N32) in phase 1.
- Dev accuracy at filler 40 stays near chance (0–3.9% on 64-episode dev evals at updates 0–1000) through phase 1
  for every non-oracle arm. The oracle is already at 99–100% by update 300.
- P2C (tiny model) used `readout = taskhead`, whose features are the memory reads only. There, no local route to the
  head existed in phase 1. The same curriculum then transferred fast in phase 2: P2C N32 dev 1.6 / 5.1% at update
  1000 → 9.4 / 34.4% at 1200 → 61.3 / 69.5% at 1500 (RESULTS.md). P2.5 learned N32 went 2.0 / 3.1% → 4.7 / 7.8% →
  6.6 / 6.2% over the same updates.
- Reading: the readout change (taskhead → residual_head) interacting with curriculum phase 1 is the strongest saved-
  evidence candidate for the transfer failure. In phase 1 the trained arms could use the local window.
- NOT isolated:
  - Backbone, layers, dimensions and hidden scale also changed.
  - Learned N32 phase 1 (52%) exceeds memory_off (42%) by an amount these files cannot attribute.
  - Low phase-1 transfer does not prove that phase 1 trained nothing in the memory path.

## F3. Write gates: per-head saturated, not binding-selective; gate gradients tiny (Q4)

- Readings gate telemetry (descriptive, final weights): in every SGM arm, including oracle, per-head effective gates sit
  near 0 or 1. The binding/filler ratio rho is 0.95–1.05 and the mean AUROC is 0.36–0.61.
  - Oracle does not need gate selectivity: its addresses separate value writes from the rest.
- Logged beta gradient medians, learned N32: ~5e-4 to 3e-7 per layer and phase (s1 L20: ~1e-15).
  k_proj/value/address_mlp medians are ~7e-3 to 3e-1.
- P2C learned N32 last logged row: beta gradient norms 0.49 (L1) and 0.077 (L3).
- P2C final gate class means were value-selective (value 0.41–0.46 vs key 0.26–0.30 vs filler 0.29–0.35). P2.5 learned
  is flat (key ≈ value ≈ filler).
- Different models: the magnitudes are not directly comparable, but the gap is several orders of magnitude.
- When saturation began is not recoverable without forward passes (gates are input-conditioned).

## F4. learned-n32-s1 L20 (Q3; None kept separate from 0.0)

- Logged rows: L20 k_proj/value/beta are None on 17/150 rows (first at update 50) and numeric on the others.
- Numeric L20 medians are ~1e-15 to 1e-16 in both phases, for address_mlp, k_proj, value and beta. Exact 0.0 occurs on 5–27
  rows per L20 group.
- L20 `beta_proj` parameters are unchanged from update 50 to 1500 (bias identical to 2 decimals; weight norm
  2.31 → 2.32). In s0 they move (bias 0.12 by 1500; norm 2.35 → 3.24).
- Readings telemetry: all 4 L20 heads in s1 have effective gate 0.0 for binding and filler events.
- The s1 dev mean gate fell from 0.55 to 0.31 by update 100 (s0 rose to 0.60).
- This is consistent with L20 write gates closing early, so no write leads to no gradient. The cause of the closure is
  not isolated. The effect is not isolated either: s1's accuracy is similar to s0's, but that is not a controlled
  comparison.

## F5. Routing summaries (Q2, descriptive only)

| arm (N32) | empty-read interp. weight | effective cells | address std |
|---|---|---|---|
| P2.5 learned | 0.56 / 0.78 | 10.4 / 10.4 | 4.3 / 13.0 |
| P2.5 random_fixed | 0.20 / 0.20 | 8.6 / 8.4 | ~0.95 |
| P2.5 oracle | 0 | 117 / 127 | 19 |
| P2C learned | 0.016 / 0.0 | 35.5 / 28.3 | — |

- Empty-read weight is a fraction of interpolation weight, not a share of queries that read nothing.
- Effective cells is exp(entropy) of cell norms. It is not a fact count, and not collision evidence.
- Key-to-cell alignment is UNAVAILABLE: no write/read event traces were saved, and weights cannot recover
  input-conditioned routes.

## Not established
- Why the learned arms fail. F2 is the strongest candidate, not a demonstrated cause.
- Whether any source-time memory use exists (outside the bank_derange boundary).
- Collision or overwrite. Whether gate saturation (F3) matters once phase 1 cannot be solved locally.

## ONE proposed follow-up (NOT authorized; needs a prereg-lite, codex audit and user approval)
**Readout-isolation probe.** learned N32 × s0/s1 on frozen Qwen3-0.6B with `readout = taskhead`, the P2C readout
(memory-read features only). Everything else is held: curriculum, 1,500 updates, layers, populations and evals.
- Comparator: the existing P2.5 learned-n32 cells.
- Dev/artifact populations only. Never the reserved population.
- Interpretation rule, fixed in advance:
  - If dev at 1,500 rises far above the 6–12% band toward the P2C range, the phase-1 local shortcut is the main
    blocker. Next would be a residual-head recipe that removes the shortcut, e.g. keeping phase-1 bindings outside the
    local window.
  - If it stays near chance, the shortcut is not the main blocker, and F3 (gate saturation) is the next suspect.
- Cost: one A100 slot ≈ $20 (actual learned-n32 slot billing was $20.10).

## Unresolved questions
- Should the probe also include random_fixed + taskhead N32 (a second slot, ≈ $15), so that address learning can be
  separated from the readout effect?
