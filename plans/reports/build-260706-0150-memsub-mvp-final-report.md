# memsub MVP (M0–M2) — Final Build Report

Date: 2026-07-06 · Branch: `mvp` · Scope: BUILD.md (spec v0.3.6.1 semantics)

## Outcome

M0, M1, M2 delivered as a Python library (`memsub`) + thin CLI. No training,
no vLLM, no HTTP, no channels — do-not-build fence respected. Local machine
(6.8GB RAM / 6GB GPU) runs all logic tests on a tiny random Qwen3-config
model; all model-bound acceptance runs executed on Modal (H100) against the
reference config Qwen/Qwen3-4B-Instruct-2507 bf16 + Qwen3-Embedding-0.6B.

## Golden tests (acceptance criteria)

| Test | Local (tiny cfg) | Reference (Modal, Qwen3-4B bf16) |
|---|---|---|
| GT1 identity round trip, memory+disk restore | PASS (T=256) | PASS (T=1024, 8192) |
| GT2 sink invariant (raise-before-mutation, ckpt records, hydrate order) | PASS | PASS |
| GT3 fingerprint gate (all 14 fields parameterized) | PASS | PASS |
| GT4 axes-separate report structure | PASS | PASS |
| GT4 needle flips after eviction; EXPAND recovers | n/a (needs real weights) | PASS |
| GT5 redaction traces derived_from graph, fails closed | PASS | PASS |
| GT5 resume survives when redaction kills every block | PASS | PASS |
| position math: evicted continuation ≡ dense masked forward | PASS | PASS |

Local: 32 passed, 2 skipped (reference-only). Reference: 36/36 passed.

## Milestone smokes (definition of done)

- `examples/m0-text-substrate-smoke.py` — archive → summaries → shadows →
  gated EXPAND recovers exact needle (QX-4417) via RETRIEVED_EXACT. PASS
  local + Modal.
- `examples/m1-compaction-certification-smoke.py` — sink refusal, compaction,
  two-axis certification report. PASS local + Modal (reference asserts the
  needle flip and nonzero KL).
- `examples/m2-delta-checkpoint-resume-smoke.py` — delta page reuse, mmap
  hydrate, fingerprint tamper → fallback re-prefill. PASS local + Modal.

## B.3 pilot (Modal)

MCQ pipeline over 4 public-domain long documents (literature/legal/economics/
science), extractive MCQs by the base model, filter (a) teacher-answerable
with context, filter (b) discard if answerable without context; eq_policy_v1.
Pilot items + per-document certification reports stored in the
`memsub-artifacts` Modal volume (`pilot-mcq-items.json`,
`pilot-certification-reports.json`). Results: see Modal section below.

## Key engineering decisions

1. **Position decoupling** (the one custom artifact, B.7 tier (a)):
   continuation passes `position_ids` = logical (RoPE) and `cache_position` =
   physical (mask sizing) through an unmodified HF forward. Surviving keys
   keep original rotations → relative geometry exact; verified by a dense
   4D-masked forward equivalence test, not just round-trip.
2. **Content addressing = delta + CoW.** 64-token safetensors pages keyed by
   content hash; unchanged pages dedupe across checkpoints (measured 12/16
   pages reused after append-only step); lineage via `parent_checkpoint_id`.
3. **Conservative redaction rule for KV**: any checkpoint whose logical
   coverage includes a redacted span is invalidated even without a graph
   edge — surviving KV encodes evicted context (stale survivors, spec 13.1),
   so edge-only invalidation would leak.
4. **Fail-closed everywhere**: redaction (RedactionError), fingerprint
   (CompatibilityError, all-or-nothing), integrity (checksum on blob read).
   GT3 additionally asserts the fallback path never opens a KV page blob.

## Deviations / notes

- Python package modules use snake_case (kebab-case is not importable);
  standalone scripts (examples, modal-runners) use kebab-case per repo rules.
- MemoryBlock auxiliary kv_pages representation omitted (MVP notes allow
  primary-only; compacted KV lives in checkpoints; YAGNI).
- Pilot dataset: 765 items (target 1000; strict counterfactual filters keep
  ~38%). Within pilot scale; reaching exactly 1–2k is a `target_items`
  parameter. The full ~100–150k corpus remains the later, human-triggered
  step per BUILD.md 3.
- After eviction, page alignment shifts, so delta reuse degrades across an
  eviction boundary — acceptable at MVP scale (BUILD.md forbids performance
  work before green tests).

## Modal reference results

All runs on Modal H100, image pinned identically to local (torch 2.7.1,
transformers 4.55.2, safetensors 0.5.3, py3.12), model weights cached in the
`memsub-hf-cache` volume.

- **Golden suite: 36/36 passed** (`pytest tests/` with MEMSUB_REFERENCE=1),
  including GT1 identity round trip at T=1024 and T=8192 through both the
  in-memory and disk (safetensors mmap) restore paths, and the GT4 semantic
  tests: planted-fact needle flips correct→incorrect after span eviction
  (lost_fact_incident_rate=1.0) and recovers with EXPAND
  (lost_fact_incident_rate=0.0).
- **Smokes**: M0 (EXPAND fired at cosine 0.753 with Qwen3-Embedding-0.6B and
  recovered the exact needle), M1 (real needle flip caught by the
  instrument), M2 (delta checkpoint reused 108/144 pages after an
  append-only step; tampered fingerprint fell back via summary re-prefill).
- **Two reference-only defects found and fixed** by these runs:
  (1) L0 resume fallback crashed if redaction had invalidated every block —
  now re-prefills from surviving spans only (regression test added);
  (2) the dense-equivalence test compared raw bf16 logits at fp32 tolerance —
  now compares softmax distributions with dtype-aware tolerance.
- **B.3 pilot**: strict counterfactual filters kept 154/≈400 candidate items
  in the first run (filter (b) discards anything answerable without
  context). Per-document certification at eviction fraction 0.40:
  mean KL 0.0095–0.0240, MCQ accuracy delta 0.0 on the aggregation axis;
  pointwise axis reported separately with lost-fact rates 0.0–1.0 depending
  on whether needles fell inside the evicted range. The scaled run kept
  **765 items** (filter keep-rate ≈38%; set target ≈2.5× desired size) with
  per-document certification: mean KL 0.0066–0.0448, lost-fact rates
  0.33–1.0. Artifacts `pilot-mcq-items.json` and
  `pilot-certification-reports.json` live in the `memsub-artifacts` volume.
  certification_id:
  `evfid-v1:Qwen/Qwen3-4B-Instruct-2507#cfg=sha256:48a2eb73...:evict-oldest-nonsink-v1:evict-0.40`

## Unresolved questions

- None blocking. M3+ (selector scoring, gate training, Still compactor) are
  explicitly deferred by BUILD.md 7.
