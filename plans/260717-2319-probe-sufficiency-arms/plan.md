# PROBE.md execution plan — content-aware sufficiency probes

Brief: /PROBE.md. Deliverable: /PROBE-REPORT.md + arm table + artifacts.
Reference instance A = single-t1024-T8k; target = y_still (y_A) labels;
eval = evicted-only AUC, doc-level splits, cluster-bootstrap CI.

## Design decisions
- ONE unified capture pass per item serves p1/p2/c1/c2/c3a:
  prefill (sdpa) → compact under A with block-1 cross-attn capture (c3a)
  → answer trial pass w/ eager attentions + hidden states (p1/c1/c2)
  → 3 greedy decode steps w/ attentions → self-check forward (p2).
- Capture manifest = E2 sample ∪ E1 sample (~31k items; E1 rows needed
  for p3 ordering, GT24 capacity transfer, GT25).
- GT19 discipline: capture runs on the 1k pilot subset FIRST; p1/p2 bars
  decide the c1 plan before scaling to the full manifest.
- GT22 end-to-end uses natural-prevalence importance weights on the
  captured sample (capturing all 82k evicted rows would triple cost);
  documented as weighted estimate.
- attn implementation toggled per-forward via config._attn_implementation
  (sdpa prefill, eager capture); guarded by a logit-equivalence check.

## Phases
- [x] P1 capture manifest (30,847 = E2 ∪ E1) + 1k pilot
- [x] P2 unified capture runner + p3 harness (classes 955/209/790)
- [x] P3 P0: p1 all < 0.55 (best 0.536) → c1 DEMOTED; p2 = 0.659 ≥ 0.62;
      c3a cross-attn = delta position kernel (purity 1.0, entropy 0.0,
      zero variance) → content-blind routing, c3a infeasible, c3b OFF
- [x] P4 full capture (light mode; slice-00 preemption + corrupt-shard
      recovery; + 2k multihop capture for GT23)
- [x] P5 c0.5: NULL — 0.535 alone, 0.568 [0.557,0.579] with c0 (bar
      0.575 not met); "interference only measurable inside the
      computation" + now mechanistically explained
- [x] P6 arms (interim): p2 0.637 · c1d 0.709 · c2_lin 0.818 (layer 29)
      · c2_mlp 0.847 · stack 0.851 [0.843,0.860]; GT20 all pass; GT21
      target smashed; head inventory emitted (top head 0.72)
- [x] P7 c3b not run (gate failed by design: c3a mechanism-null)
- [x] P8 (interim) GT22 lost 0.147 @ expand_all 0.048 (gate: 0.146 @
      0.147) · GT23 1.94× @ recall 0.824 (frontier, targets missed) ·
      GT24 held-out drop 0.204 · GT25 τ 0.580 CI excludes 0
- [x] P9 FINAL (all 30,847 + 2k mh): p2 0.638 · c1d 0.767 · c2_lin
      0.819 (layer 30) · c2_mlp 0.852 · stack 0.854 [0.846, 0.862];
      GT22 WIN 0.146 @ 0.050 vs gate 0.146 @ 0.147; GT23 frontier
      1.98×; GT24 drop 0.214; GT25 τ 0.575. Report: /PROBE-REPORT.md
