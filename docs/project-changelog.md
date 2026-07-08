# Project Changelog

## 2026-07-06 — MVP M0–M2 initial implementation (branch `mvp`)

- Repo re-initialized on orphan branch `mvp` (previous Zep history retired).
- **P0**: pinned environment (py3.12, torch 2.7.1, transformers 4.55.2,
  safetensors 0.5.3); `compatibility_fingerprint` module with operational
  `kernel_numeric_profile_hash` (env + fixed-input probe). First commit per
  BUILD.md ground rule 1.
- **P1**: `CompactedPrefixCache` (HF Cache subclass, pure PyTorch): logical
  RoPE positions decoupled from physical mask positions; GT1 identity round
  trip green (memory + disk restore paths) plus a dense-masked-forward
  equivalence test of the eviction geometry.
- **P2**: raw archive (content-addressed blobs + SQLite span index),
  turn-boundary segmenter with 1–2k token cap.
- **P3 (M0)**: base-model summaries, Qwen3-Embedding shadows (`shadow-v1`),
  naive top-k selector, runtime-gated EXPAND via RETRIEVED_EXACT.
- **P4 (M1)**: sink-pinned compaction/eviction (`evict-oldest-nonsink-v1`),
  MemoryBlock creation with provenance edges, offline certification harness
  (spec 13.4) with strictly separated aggregation/pointwise axes, B.3 pilot
  MCQ pipeline with counterfactual filters, eq_policy_v1.
- **P5 (M2)**: safetensors delta checkpoints (64-token content-addressed
  pages → delta + CoW lineage), mmap hydration with sink pages first,
  fingerprint-gated hydrate-or-fallback resume.
- Golden tests GT1–GT5 implemented; local suite green on tiny config;
  reference runs executed on Modal (H100) — see
  `plans/reports/build-260706-0150-memsub-mvp-final-report.md`.
- Explicitly deferred per BUILD.md 7: M3 selector/gate, M3.5 compactor,
  vLLM tier, HTTP API, channels/soft-slots/latent compression, any training.

## 2026-07-06 (later) — B.3 four-domain test corpus + 2k-item MCQ set

- Assembled real corpus per spec B.3 domains into `memsub-artifacts` volume:
  SEC 10-K filings, US court opinions, permissive-license code, literature —
  7,232 docs, ~155M est. tokens (`modal-runners/modal-b3-corpus-pipeline.py`).
- Generated 2,000 filter-verified MCQ items (500/domain, 4×H100 parallel).
- Certified untrained eviction at 0.40 over 12 contexts: aggregation axis
  nearly unmoved (KL ~1e-2, no MCQ delta), pointwise axis flips where the
  needle chunk is evicted — spec 4.7 two-workload split reproduced on real data.
- Report: plans/reports/corpus-260706-0341-b3-four-domain-corpus-run.md

## 2026-07-07 — Full-scale B.3 dataset complete

- 98,355 filter-verified MCQ items over the 927M-token 4-domain corpus
  (pass 1: 74,196 in ~9h; shortfall-sized top-up: +24,159 in ~3h;
  ~120 H100-hours ≈ $470–500, zero worker failures).
- Full-set certification, 40 reports: evict 0.25 → mean KL 0.030 /
  lost-fact 0.71; evict 0.40 → mean KL 0.034 / lost-fact 0.81. Aggregation
  axis flat, pointwise collapses — quantitative M1 verdict that untrained
  eviction needs the M3 gate for needle traffic.
- Report: plans/reports/corpus-260707-0907-full-scale-b3-run-final-report.md

## 2026-07-07 (later) — Certification made citable

- eval_protocol embedded in every CertificationReport: per-axis item
  partitions, compacted-context contents (surviving KV only), EXPAND state,
  scoring rule; probe_records for audits.
- Control arm (evict 0.0): conditioned lost-fact noise floor = 0.000
  (raw floor 0.167 = never-knew items). New citable headline: 55%/65%
  prior-correct facts silently lost at 25%/40% contiguous eviction.
- Matched-random arm: 4x less pointwise loss, 3x more aggregation KL than
  contiguous — recency structure concentrates and hides pointwise damage.
- Complete hand audit of 14 unique failures: 11 genuine forgetting,
  2 duplicate-option items, 1 question-gold mismatch, 0 format failures.
- Appendix: plans/reports/certification-260707-0907-eval-protocol-appendix.md

## 2026-07-07 (evening) — M3 expansion gate complete (GATE.md)

- 196,710 counterfactual labels (98,355 items × 2 fractions, ~$110 H100).
- Dual-encoder gate (frozen shadow-v1 embeddings, linear-probe tier):
  GT7 ECE 0.023/0.017; GT8 dominates classify-and-expand at every matched
  expand-rate; GT9 FEASIBLE — lost-fact 0.143 at expand-rate 0.169 (vs
  never 0.520, oracle 0 @ 0.194); GT10 budget tracing green; GT6 near-tie
  documented (LODO AUC 0.78-0.87 confirms generalization).
- Multi-hop slice (500 k=2 items): correctness holds (0.036) via 2.3×
  over-expansion — spec 4.7 middle-of-spectrum cost, not correctness.
- Checkpoint+calibration+grid in memsub-artifacts:/gate-eval; report:
  plans/reports/gate-260707-1319-m3-expansion-gate-final-report.md

## 2026-07-07 (night) — M3 ablation addendum (ABLATION.md)

- A1: headline discrimination corrected to EVICTED-ONLY AUC 0.622
  [CI 0.608-0.636]; pooled 0.83 conflated evicted/survived separation.
- A2: decomposition shows features-only ≈ full model (0.621 vs 0.624
  evicted-only AUC); embeddings-only 0.536 — the gate is a calibrated
  eviction-MECHANICS classifier; dual-encoder content pathway is a
  negative result; GT6 near-tie explained.
- A3: canonical M3-protocol never-expand rows 0.453/0.551 per fraction;
  M1 numbers flagged as different protocol.
- A4: GT9 restated as frontier (bootstrap upper CI 0.156 > 0.15; seeds
  0.126±0.014 lost at 0.177±0.007 expand).
- A5: domain_recalibration.py shipped — temperature with Platt escalation;
  all four LODO domains reach ECE ≤ 0.05 (0.014-0.035). Unit-tested.
- Deliverable: ADDENDUM.md (root, per brief); eval-grid.json updated.

## 2026-07-07 (late) — Paper draft in LaTeX

- paper/main.tex + references.bib + figures, compiled to main.pdf
  (tectonic). All draft.md fill-in tokens resolved from the ablation
  artifacts: A2 verdict = mechanics (kept that §5.2 paragraph), evicted-only
  AUC 0.622 headline, canonical baselines 0.453/0.551, GT9 frontier wording,
  Platt-escalation recalibration in §5.5. Citations flagged for verification
  against primaries before submission.

## 2026-07-08 — M3.5 complete (COMPACTOR.md): no-ship verdict, frontiers documented

- WP1: Still-class compactor trained (GT11/GT12 green; sweep t∈{128,512,1024}
  + iterative). GT13 NO-SHIP: aggregation KL 0.263 vs eviction 0.122 at
  matched budget (1/40-scale training caveat). GT14 surprise: synthesis
  HALVES silent needle loss (0.271 vs 0.583) but gate stays mandatory.
  GT15: depth-4 recurrence collapses (KL 2.29); max_certified_depth=0,
  refusal guard tested. GT16: refreshed gate matches M3 end-to-end at 13%
  lower expand cost (0.1461@0.147 vs 0.146@0.168); A2 decomposition FLIPS
  under synthesis (content > mechanics, both weak).
- WP2: s1/s2 set-scoring — GT17 frontier (2.15-2.24x vs 2.33x oracle
  overhang); diagnosed as bounded by gate discrimination (A2 headroom).
  GT18 green by construction.
- Compute ≈ $715 (budget $850-1,400). ADDENDUM-M35.md at repo root.

## 2026-07-08 (later) — Paper updated with M3.5 section

- New §6 "Does trained synthesis change the verdict?": matched-budget
  certification table, needle-halving finding, depth collapse, gate-signal
  family flip, set-scoring bound. Contribution (v) added; abstract,
  limitations, conclusion, compute ledger updated. 10 pages, compiles clean.
