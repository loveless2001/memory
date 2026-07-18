# FOLLOWUP.md — Post-PROBE Micro-Experiments (blocking for paper v0.2 freeze)

Scope: three analyses against existing `memsub-artifacts:/probe/` captures
plus one cheap forward-pass run. No training beyond one probe refit, no new
corpus, no compactor work. ≈ $15. Precedence: this brief on scope, spec
v0.3.6 on semantics. Output: FOLLOWUP-REPORT.md; every number maps to a
⟨placeholder⟩ in gate_paper_draft_v0.2.md.

---

## F1 — Kernel-distance mechanics feature  [BLOCKING — decides §8's branch]

The delta-kernel finding implies a mechanics feature nobody computed:
**distance from the needle's source position(s) to the nearest KEPT source
position** (kept = the cross-attention argmax set, already in the c3a
capture shards; needle positions from corpus metadata).

```text
compute   per evicted-only item: d_min = min over needle tokens of
          distance to nearest kept position; also d_mean, and
          frac_needle_kept (needle tokens directly sampled)
evaluate  univariate AUC vs y_A (evicted-only, doc-level test split);
          then c0 + kernel features logistic (= "mechanics-with-kernel"
          arm); then c2-residualized: does c2's score correlate with
          d_min (Spearman), i.e. how much of 0.85 is kernel geometry
report    ⟨F1-uni⟩ univariate AUC · ⟨F1-arm⟩ mechanics-with-kernel AUC
          + CI · ⟨F1-corr⟩ c2-score↔d_min correlation
branch    ≥0.75 → subsampling loss IS mechanics-routable given the
                  kernel; paper keeps branch (i)
          0.60–0.75 → partial; branch (ii)
          <0.60 → smear dominates; branch (iii)
```

## F2 — Context-only probe control  [BLOCKING — validity of the 0.85]

Does c2 read memory content, or answer-confidence?

```text
run       re-forward the test-split evicted items with the SAME compact
          context but NO question appended; capture layer-30 residual
          at the last context token (~$8, light mode)
evaluate  (a) refit the linear probe on context-only states vs y_A
          (b) apply the question-conditioned probe to context-only
              states zero-shot
report    ⟨F2-refit⟩ and ⟨F2-zeroshot⟩ AUCs
reading   ⟨F2-refit⟩ near c2's 0.819 → probe reads memory content;
          near chance → 0.85 is substantially answer-confidence; the
          paper's claim downgrades from "sufficiency readout" to
          "behavioral-divergence predictor" (still deployable — but a
          different sentence)
```

## F3 — Standalone sink-head monitor  [near-blocking — the middle rung]

```text
compute   from existing captures: the 4 inventory heads' sink-mass +
          latent-mass statistics only (L25/H14, L26/H26, L28/H19,
          L35/H15); logistic on ≤ 8 scalars
evaluate  evicted-only AUC + CI, test split; τ operating point;
          GT22-style weighted end-to-end row (lost-fact @ expand) for
          the p2+sinkheads combination — zero capture infra, one
          forward, two scalar hooks
report    ⟨F3-AUC⟩ · ⟨F3-e2e⟩ lost @ expand
purpose   completes the deployment ladder: p2 (free, 0.638) →
          sink-heads (+2 hooks, ⟨F3⟩) → full stack (capture, 0.854)
```

## Deliverables

FOLLOWUP-REPORT.md with the three verdicts and the F1 branch selection
stated verbatim; updated arm-table.json rows; `f1-kernel-features.npz`,
`f2-context-only-states` shard, `f3-monitor.json`. Stop and report; no
further arms.