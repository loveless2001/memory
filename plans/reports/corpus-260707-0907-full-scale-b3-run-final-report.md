# Full-Scale B.3 Run — Final Report

Date: 2026-07-07 · Runner: `modal-runners/modal-b3-corpus-pipeline.py` · All artifacts in Modal volume `memsub-artifacts`

## Deliverables (spec B.3, full scale)

| Artifact | Location | Size |
|---|---|---|
| Corpus, 4 domains | `corpus/*.jsonl` + manifest | 40,000 docs, ~927M est. tokens |
| Verified MCQ items | `corpus-mcq-full/all-items.json` (+ per-slice state files) | **98,355 items** |
| Per-domain counts | `corpus-mcq-full/counts.json` | fin 25,000 · lit 25,002 · legal 24,790 · code 23,563 |
| Certification | `corpus-certification-full/<domain>-evict{0.25,0.40}.json` | 40 reports |

Corpus tokens/domain: financial 238M (SEC 10-K, edgar-corpus) · legal 119M
(HFforLegal/case-law) · code 154M (github-code-clean) · literature 416M
(gutenberg_english). Every item passed both counterfactual filters
((a) teacher-answerable with context, (b) discarded if answerable without);
eq_policy_v1. 98,355 = 98.4% of the 100k target (code keep-rate lowest);
spec range is "~100–150k".

## Execution

- Pass 1: 32 resume-safe H100 workers (8 slices × 4 domains), ~9h wall at
  ~10 concurrent → 74,196 items.
- Top-up pass: 12 shortfall-sized workers with fresh chunk seeds, ~3h wall
  → +24,159 items.
- Compute: ~120 H100-hours total ≈ $470–500 (below the ~$770 estimate;
  measured throughput ~2× the projection).
- Zero worker failures; per-group state checkpointing never needed for
  recovery but bounded worst-case loss to ~20 min of work.

## Certification (spec 13.4, full item set as probes, 5 contexts/domain)

| Config | mean KL (aggregation) | mean lost-fact rate (pointwise) | contexts w/ loss |
|---|---:|---:|---:|
| evict 0.25 | 0.0303 | 0.708 | 15/20 |
| evict 0.40 | 0.0339 | 0.808 | 17/20 |

Per-axis reporting only — no blended score exists in any report object.
certification_id family:
`evfid-v1:Qwen/Qwen3-4B-Instruct-2507#cfg=sha256:48a2eb73...:evict-oldest-nonsink-v1:evict-{0.25|0.40}`

**Reading (untrained-eviction regime, spec 13.3):** the aggregation axis is
nearly untouched at both fractions (KL ~3e-2, MCQ deltas ≈ 0), while
pointwise needle fidelity over evicted spans collapses (70–80% silent loss
without EXPAND) and worsens with eviction fraction. This reproduces the spec
4.7 two-workload antagonism on ~1B tokens of real 4-domain data and is the
quantitative case for the M1 verdict: untrained eviction must not serve
pointwise traffic without the expansion gate (M3) — exactly the spec 13.4
rule that a configuration certified only on the aggregation axis requires an
active, calibrated gate for needle queries.

## Unresolved questions

- Code domain stops at 23,563 (94% of per-domain target) — its docs yield
  fewer filter-surviving MCQs; another top-up pass would close it if exact
  parity matters.
- The gate that would consume these labels is M3 (explicitly out of MVP
  scope, BUILD.md 7). Data is ready for it: (q, R_raw, M_compact) labeling
  per spec B.5 can start from `all-items.json` whenever M3 is green-lit.
