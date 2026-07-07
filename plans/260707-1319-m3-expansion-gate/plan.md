# M3 Expansion Gate (GATE.md) — Plan

Scope: GATE.md; semantics: spec §17.5/§17.6. Base substrate green (M0–M2).

## P0 verification gate — STATUS
- V1 eval-protocol appendix: DONE (2026-07-07, embedded in report objects).
- V2 control rows: DONE — evict-0.0 conditioned floor = 0.000 (raw 0.167 =
  never-knew); random-0.25 diagnostic run (4× less pointwise loss, 3× KL).
- V3 manual audit: DONE — 14/14 unique failures reviewed: 11 genuine, 2
  duplicate-option items, 1 q-gold mismatch, 0 format noise (<15% → no
  eq_policy hardening needed).
- V4: NO per-item outcomes for the 98k set (probe_records cover only ~25
  needles) → labeling passes required.

## Phases
- [x] P1 labeling fleet (Modal): per item, one 4096-tok context prefill
      (item-hash-random placement), clone+evict at f∈{0.25,0.40} (oldest-
      nonsink window), answers: compact×2 + raw-span; y_f = compact_f ≠ raw
      (eq_policy_v1); features: overlap_f, evicted_f, pointwise heuristic
      (gold verbatim in chunk); store glosses for embeddings. Resume-safe
      slices → corpus-gate-labels/. (98,355 items done, ~$60)
- [x] P2 embeddings (Modal): Qwen3-Embedding-0.6B (shadow-v1): q_emb
      (question ⊕ ctx-tail gloss), b_emb (chunk gloss) → npz shards.
- [x] P3 gate library (memsub/gate/): doc-level stratified splits + LODO,
      dual-encoder linear-probe gate (+feature head, aux workload head),
      temperature scaling per fraction, ECE/reliability, threshold sweep,
      baselines (never/always/classify/oracle), budget harness (GT10).
      Local tests on synthetic data.
- [x] P4 gate training + §5 evaluation grid on Modal (GT6 leakage control,
      GT7 ECE, GT8 dominance curve, GT9 end-to-end, LODO rotation).
- [x] P5 multi-hop slice (~500 k=2 items, same-doc pairs, teacher-filtered),
      labeled + evaluated separately.
- [x] P6 deliverables: checkpoint+calibration+config hash in volume, eval
      grid JSON, plane/reliability figures, per-domain tables, final report.

## Status: COMPLETE 2026-07-07 — see plans/reports/gate-260707-1319-m3-expansion-gate-final-report.md
GT7/GT8/GT9/GT10 green; GT6 near-tie honestly documented (LODO confirms generalization).
