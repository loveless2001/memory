# FOLLOWUP2 F4/F5 — plan & provenance

Brief: `/FOLLOWUP2.md` (pre-submission micro-batch). Report:
`/FOLLOWUP2-REPORT.md`. Cost ≈ $14.

## What ran

1. **F4 GPU (~$8)** — `modal-followup2-f4-multilayer-context-only.py`:
   re-forward the same 5,090-item F2 test subsample context-only, capture
   layers {10,15,20,25,30,36} (`f4-slice-*.npz`, on volume).
2. **F5 GPU (~$6)** — `modal-followup2-f5-eviction-sinkhead-capture.py`:
   eviction-regime (f=0.40) attention on the 4 heads over 5,022 evicted
   rows; memory region = surviving compacted span (`f5-slice-*.npz`, kept).
3. **Local** — `analyze-followup2-f4-f5.py` (F4 via `run-f4.sh` detached).

## Verdicts

- **F4 → null UPGRADES.** Context-only probes all at chance: per-layer
  linear 0.496–0.506, MLP(L30) 0.508, concat lin/mlp 0.501/0.502. Max
  0.508 vs 0.813 question-conditioned. No decodable signal, linear or
  nonlinear, any probed layer.
- **F5 → regime-GENERAL.** Eviction sink-head monitor 0.783 [0.760,0.808]
  > shadow-gate mechanics 0.622; zero-shot transfer compactor→eviction
  0.744, eviction→compactor 0.717.

## Deliverables

`FOLLOWUP2-REPORT.md` (verdicts + exact §6.4/§6.3/limitations replacement
sentences); arm-table.json rows `f4_context_only_nonlinear`,
`f5_sinkheads_eviction`; paper/main.tex + docs/draft.md updated + recompiled
(13pp, clean). Volume: `memsub-artifacts:/probe/followup2-*`.

Stop condition met. No further arms.
