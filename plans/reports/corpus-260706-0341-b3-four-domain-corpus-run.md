# B.3 Corpus Run — 4-Domain Test Corpus + 2k-Item MCQ Set + Certification

Date: 2026-07-06 · Runner: `modal-runners/modal-b3-corpus-pipeline.py` · GPU: H100 ×4 parallel

## Corpus (spec B.3 domains, all ungated HF parquet sources)

| Domain | Source | Docs | Est. tokens |
|---|---|---:|---:|
| financial | eloukas/edgar-corpus (SEC 10-K filings) | 2,000 | 49.2M |
| legal | HFforLegal/case-law (US court opinions) | 2,000 | 21.8M |
| code | codeparrot/github-code-clean (permissive licenses) | 2,000 | 31.4M |
| literature | sedthh/gutenberg_english | 1,232 | 53.2M |
| **total** | | **7,232** | **~155M** |

Filters: ≥24k chars/doc (≈6k tokens, dwarfs the 1k-token chunk unit), capped
at 200k chars. Stored as `corpus/<domain>.jsonl` + `corpus/manifest.json` in
the `memsub-artifacts` Modal volume. Spec full scale is ~1B tokens — this is
~15%; scaling = bump `n_shards`/`docs_per_domain` and rerun `assemble_corpus`.

## MCQ generation (B.3 filters, eq_policy_v1)

500 items per domain, **2,000 total kept** after both counterfactual filters
((a) teacher-answerable with context, (b) discarded if answerable without).
One 1k-token chunk sampled per doc → items spread across ~2k docs/domain.
Stored as `corpus-mcq/<domain>.json`. 4 H100 workers in parallel.

## Certification (spec 13.4, evict fraction 0.40, 3 contexts/domain)

12 reports in `corpus-certification/<domain>.json`. Axes reported separately:

- aggregation axis: mean KL 0.007–0.051; MCQ accuracy delta ≈ 0 across contexts.
- pointwise axis: lost_fact_incident_rate = 1.0 in 5/12 contexts (needle chunk
  inside the evicted range → silent loss detected), 0.0 where the needle fell
  outside the clamped eviction window — the instrument discriminates cleanly.
- certification_id:
  `evfid-v1:Qwen/Qwen3-4B-Instruct-2507#cfg=sha256:48a2eb73...:evict-oldest-nonsink-v1:evict-0.40`

## Interpretation (untrained eviction, M1 regime)

Consistent with spec 13.3/17.1: eviction barely moves the aggregation axis
(KL ~1e-2, no MCQ delta) while needle fidelity over evicted spans collapses —
exactly the two-workload split of spec 4.7. Shipping this configuration for
pointwise traffic requires the expansion gate active (M3, out of scope).

## Unresolved questions

- Literature capped at 1,232 docs (single shard had fewer ≥24k-char docs);
  add a second shard if exact parity matters.
- Full 1B-token corpus and 100–150k-item generation remain human-triggered
  (~$500+ GPU); pipeline is ready, parameters only.
