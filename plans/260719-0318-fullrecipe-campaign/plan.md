# FULLRECIPE Campaign — Full-Recipe Compactor vs Position-Kernel Collapse

Brief: /FULLRECIPE.md (authoritative on scope). Spec v0.3.6 semantics, COMPACTOR.md constants.
Framing: NOT building a better compactor — answering 5 pre-registered questions about whether
v0.4 Regime-II findings survive a real synthesizer. Every outcome reportable.

## Status

| Phase | Item | Status |
|---|---|---|
| P0 | C1 rationale audit | ✅ PARTIAL — 19,619/98,355 traced (code 4519/fin 5474/legal 3748/lit 5878). Remainder pass required. |
| P0 | C2 mixture manifest | ✅ 94,252 items (23,563/domain), sha256 8e0bb280…, 74,633 remainder, 0 orphans |
| P0 | C1 sample + equivalence | ✅ 200-sample: fmt 86.5%/acc 67.3% ≡ old traces (86.5%/66.0%); letter parity 23/24 |
| P0 | C1 remainder pass | ✅ done 03:35–07:30, 8×H100 ≈ 31 GPU-h ≈ $130. Final mixture 75,998 traced (80.6% of nominal; lit 23,075/fin 21,502/code 17,696/legal 13,725), mid 9,498 |
| P0 | ctx pack | ✅ ctx-tokens-full.npy 75,998×8192 + mid array, all rows filled |
| P0 | I1 entropy telemetry | ✅ smoke green (exit 0, DONE, telemetry; init entropy 0.000, kept-l0 1024) |
| P0 | I2 kernel-geometry probe | ✅ runner built (E1-relabel ⊕ F1-capture per step-tagged ckpt) |
| P0 | GT26 sanity | ✅ GT11 green (2 passed); GT12 tripwire wired @300 in full run |
| WP1 | mid-scale (1/8) train | 🔄 launched 07:44 (fc-01KXVXAA2D…), 9,498 items / 188 steps |
| WP1 | full recipe train | 🔄 launched 07:44 (fc-01KXVXAS0G…), 75,998 items / 1500 steps |
| WP1 | A/B I1 snapshots | 🔄 running (Q1 endpoints, measurement-identical) |
| WP2 | Q1 ESCAPE | ✅ outcome (c): entropy 1.16e-10 flat everywhere; kernel BITWISE frozen at init (J=1.000), stride-8 lattice; extension cancelled |
| WP2 | Q2 GT13 retry | ✅ NO-SHIP: KL 0.2566 vs 0.1218 (M3.5: 0.263/0.122 — scale changed nothing); accΔ flips + (+0.063); depth 0; policy 41e72e65… |
| WP2 | Q3 F1 retry | ✅ branch (iii): d_min 0.5165 [0.505,0.528] vs new labels; kernel bitwise = A at 4k shape; internality claim stands |
| WP2 | Q4 relabel+gate | ✅ 98,355 rows relabeled, y+ 0.135; A2 full .579/feat .567/emb .577; GT16 pass 0.139@0.055; marginal vs never 9.0% |
| WP2 | Q4 capture+probes | ✅ DEGRADED-readable: stack .802 [.793,.811] vs .854; sinkheads .730; c2 L25 .797; F2 null holds (.512); GT22 0.146@0.0095 vs gate 0.139@0.055 |
| WP2 | Q5 smuggling | ✅ 0.188 vs 0.583 lost|prior (M3.5: 0.271) — advantage persists AND grows; gate stays mandatory |
| WP2 | fragility recheck | ✅ FR y+ 0.321; κ(A↔FR) 0.567, κ(B↔FR) 0.588; nesting 94.1% (604/642 ⊂ A) — structure survives regime change |
| WP2 | I2 d_min sweep | 🔄 10 checkpoint workers running |
| — | FULLRECIPE-REPORT.md | ✅ complete — all verdicts in pre-registered vocabulary, consequences + paper #2 skeleton + ledger (~$440) |

## Logged decisions
- HARNESS BUG FOUND+FIXED: M3.5 trainer bypassed DDP forward → NO grad sync ever
  (verified via 2-rank gloo test: bypass=unsynced, wrapper=synced). Shipped ckpts
  A/B/sweep = batch-4 single-replica models (rank0 saved), per-rank init. v2 trainer:
  same-seed init + explicit all-reduce = true effective batch 32. → report §consequences.
- Mid-scale "1/8 recipe" = 1/8 data volume AND 1/8 steps (~190) — matches brief's $60–90
  cost point (full-config 1500-step run costs ~$53 actual per PREPROBE replication).
- Scale points on collapse curve: mid ≈11.8k items / A = 19,619 (existing, $0) / full ≈94k.
- Full-recipe triplets deterministically shuffled (seed 1234) at merge — Still mixture;
  prior harness consumed domain-grouped file order (data prep concern, not harness change).
- Trainer v2 = same objective/optimizer/harness + I1 telemetry + step-tagged saves every
  250 (resume-safe per brief) + save-then-exit watchdog (M3.5 NCCL mitigation).
- I2 runs post-hoc on step-tagged checkpoints (equivalent to online; keeps trainer lean).
- C1 batched pass replicates prep protocol exactly (same PROMPT, ctx-window seed math,
  greedy 96, eos) — batching sanctioned by brief ("batched, greedy").

## Pre-registered decision rules (fixed before first telemetry point)
- I1 metric: entropy_mean_over_layers (nats, block-1 cross-attn rows, 128-item probe).
- "Entropy still rising at 1500" (→ extend to 3000): mean(points in steps 1300–1500)
  − mean(points in steps 1000–1200) > 0.01 nats. Plateau or pinned-at-floor → no extension.
- Q1 "leaves zero": ≥2 consecutive telemetry points exceeding max(init point, instance-A
  snapshot) by > 0.1 nats. Transition step = first such point.
- Q1(c) confirmed at full recipe → extension cancelled (brief abort rule), Q2–Q5 proceed.

## Cost ledger (running)
- C1 audit: $0 (local). Everything else logged as spent.

## Key artifacts
- Volume: memsub-artifacts. New tree: corpus-fullrecipe/ (manifest, rationales, triplets),
  compactor-checkpoints/fullrecipe-*/, fullrecipe-telemetry/.
- Runners added: modal-fullrecipe-c2-mixture-manifest.py, modal-fullrecipe-c1-batched-rationale-prep.py,
  fullrecipe trainer launcher + inner script v2 (instrumented).
