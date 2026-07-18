# FOLLOWUP F1/F2/F3 — plan & provenance

Brief: `/FOLLOWUP.md` (post-PROBE micro-experiments, blocking for paper
v0.2 freeze). Report: `/FOLLOWUP-REPORT.md`. Cost ≈ $9.

## What ran

1. **GPU (H100, ~$8)** — `modal-followup-f1f2-context-only-and-kept-kernel.py`
   - pilot (16 items, `--dump-argmax`) → confirmed kept kernel = stride-≈3
     lattice, head-/item-invariant (→ `pilot-slice-00.npz`).
   - scaled 4-slice, frac=0.55 → 5,090 test-split evicted items, context-only
     (no question): layer-30 residual at last context token + per-item kept
     bitmap (`f1f2-slice-{00..03}.npz`).
2. **CPU (~$0.1)** — `modal-followup-f3-headfeats-and-f2-zeroshot-probe.py`
   - 8 sink/latent head scalars from existing shards (`f3-headfeats.npz`)
   - layer-30 question-conditioned probe weights (`f2-zeroshot-probe.npz`,
     test AUC 0.813 sanity).
3. **Local** — `analyze-followup-f1-f2-f3.py` → verdicts + artifacts.

## Verdicts

- **F1 → branch (iii)** smear dominates. d_min 0.509, c0+kernel 0.550
  (+0.003), c2↔d_min ρ=0.045. Kernel geometry loss-blind.
- **F2** context-only refit 0.502 / zero-shot 0.508 (vs 0.813) → the 0.85 is
  answer-confidence; downgrade "sufficiency readout" → "behavioral-divergence
  predictor."
- **F3** sink-head monitor 0.762 [0.753,0.771]; e2e lost 0.149 @ expand 0.060.
  Ladder: p2 0.638 → sink-heads 0.762 → stack 0.854.

## Deliverables (all present)

`f1-kernel-features.npz` · `f2-context-only-states.npz` · `f3-monitor.json`
· updated `../260717-2319-probe-sufficiency-arms/arm-table.json` rows ·
`/FOLLOWUP-REPORT.md`. Volume copies under `memsub-artifacts:/probe/followup-*`.

Stop condition met. No further arms.
