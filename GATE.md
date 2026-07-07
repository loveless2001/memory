# GATE.md — Expansion Gate Experiment (M3)

Handoff brief for the spec's §17.5 decoupled dual-encoder gate, consuming the
full-scale B.3 corpus run (`memsub-artifacts` Modal volume, report dated
2026-07-07). Authoritative design document: `unified_memory_substrate_spec_v0.3.6.md`
("the spec"). Precedence: this brief wins on scope, the spec wins on semantics.
BUILD.md's M0–M2 substrate is assumed green.

---

## 1. Mission and scope

Train, calibrate, and evaluate the **expansion gate**: a dual encoder that
scores, per (query, memory block), the probability that the block's compact
representation is insufficient and raw expansion is required (spec §17).
One trained model doubles as the learned selector (§9.5).

This is the project's first research deliverable: the evaluation grid in §5
is the results section of the gate paper.

### Do-not-build list
- No compactor training (M3.5), no backbone or LoRA training of any kind.
  The base model is used **offline for labels only**.
- No online/RL-style gate training; supervised counterfactual labels only.
- No serving integration; batch evaluation harness only.
- No new corpus generation beyond §2's control rows and the multi-hop slice.

---

## 2. P0 — Verification gate (blocks everything; also fixes the M1 report)

The M1 certification numbers are not citable until these land. All four are
cheap.

```text
V1  Eval-protocol appendix, emitted into every report object:
    exact item partition per axis (which items enter the aggregation
    metric vs the pointwise metric), whether summary text/KV was present
    in the compacted context during probing, EXPAND disabled confirmed,
    sampling params. Re-emit the 40 existing reports with this appendix.

V2  Control rows, same items, same protocol:
      evict-0.0     → defines the measurement noise floor; expected
                      lost-fact ≈ 0. All headline rates are re-stated
                      net of this floor.
      random-0.25   → isolates how much evict-oldest-nonsink's recency
                      structure matters (diagnostic, non-blocking).

V3  Manual audit: sample 20 pointwise failures, classify
    {genuine forgetting | eq_policy format noise | ambiguous item}.
    Report the breakdown; if format noise > ~15%, harden eq_policy_v1
    answer extraction before training on the labels.

V4  Per-item outcome check: if the 40 certification reports store
    per-item compact-vs-raw outcomes, gate labels already exist —
    extract them (§3) and skip the labeling runs. If only aggregates
    were stored, budget the labeling passes in §3.
```

---

## 3. Labels

Definition (spec §17.5): for item i with question q_i, source block b_i,
compacted context M, y_i = 1 iff answer under M ≢ answer under raw span,
judged by eq_policy_v1.

```text
source        all-items.json (98,355 items) × {evict-0.25, evict-0.40}
              (two label sets; train on the union with the eviction
              fraction as a feature, evaluate per-fraction)
if V4 = yes   extract (q, block_id, shadow, y, domain, evicted?, fraction)
              directly from certification per-item records
if V4 = no    two forward passes per item per fraction (compact, raw) on
              1–2 H100 workers; reuse the B.3 runner scaffolding
negatives     items whose source span SURVIVED eviction are y=0 rows with
              a different mechanism (nothing was lost) — keep them, they
              teach the gate that retained blocks don't need expansion
splits        GROUP SPLIT BY SOURCE DOCUMENT, stratified by domain —
              never by item; items from one document share content and
              item-level splits leak. 80/10/10 train/cal/test.
              Additionally hold out one domain entirely (rotate: report
              leave-one-domain-out as the generalization row).
```

## 4. Gate

```text
architecture   dual encoder over Qwen3-Embedding-0.6B (shadow-v1 — the
               SAME embedding model as the block shadows; a mismatch is a
               shadow-version change under spec §6.1):
                 f(query text ⊕ recent-context gloss) · g(block shadow)
               score → sigmoid → p(insufficient)
features       concatenated to the interaction: eviction fraction,
               block loss_estimate, evicted? flag, block kind;
               auxiliary head: query workload type (pointwise vs
               aggregative, spec §4.7/§17.5) — supervise it with a
               cheap heuristic label (does the gold answer string occur
               verbatim in the source span? verbatim → pointwise)
training       BCE on y; frozen embedder first (linear probe tier), then
               unfreeze top layers only if the probe underperforms GT8.
               Single GPU, hours.
calibration    temperature scaling on the cal split (isotonic as a
               fallback if the reliability curve is non-monotonic);
               report ECE and the full reliability curve. Calibrate
               PER EVICTION FRACTION.
```

## 5. Evaluation grid (spec §17.6 — this is the paper's results section)

All cells on the test split, per domain × eviction fraction, plus the
leave-one-domain-out row.

```text
metrics        expansion precision / recall (vs y)
               ECE + reliability curve
               end-to-end lost-fact incident rate WITH the gate active
               at its operating point (the number that pairs against
               M1's 0.708/0.808 baselines)
               expand-rate (compute regression proxy, spec §11.7 R3)
baselines      never-expand        (M1 numbers, restated net of V2 floor)
               always-expand       (correctness ceiling, cost ceiling)
               classify-and-expand (query-type head alone: expand iff
                                    pointwise — the interpretable
                                    baseline the gate must beat)
               oracle-expand       (expand iff y=1; target frontier)
plane          cost (expand-rate) vs correctness (lost-fact) — plot all
               five curves; the gate's operating point is chosen on the
               cal split, reported on test
multi-hop      construct a small slice (~500 items): compose k=2–3
               single-hop items from the SAME document into one question
               requiring both facts; report this slice separately (spec
               §4.7 middle-of-spectrum) — expected weakest cell; honesty
               beats omission
```

## 6. Golden tests (acceptance criteria)

```text
GT6   No leakage: retrain with item-level (wrong) splits and confirm the
      doc-level test metrics are LOWER — if they aren't, the features
      don't depend on content and something is broken. Document-level
      split is the shipped configuration.
GT7   Calibration: ECE ≤ 0.05 on test at each eviction fraction after
      temperature scaling.
GT8   The gate strictly dominates classify-and-expand somewhere useful:
      at matched expand-rate, lost-fact incident is lower; report the
      full curve, not one point.
GT9   End-to-end: with the gate at its chosen operating point, lost-fact
      incident on evicted-span items drops from 0.708/0.808 to ≤ 0.15
      net of the V2 floor, at expand-rate ≤ 0.5× always-expand.
      (If GT9's targets prove unreachable, do not tune them away —
      report where the frontier actually sits; that is still a paper.)
GT10  Budget behavior (spec §17.7): under a max_retrieved_tokens budget
      smaller than the demanded expansions, the harness surfaces budget
      exhaustion in the trace rather than silently dropping expansions.
```

## 7. Deliverables

```text
gate checkpoint + temperature/calibration params + config hash
  (these become part of any future compaction_policy_version that
   claims gate-protected pointwise traffic, spec §13.4)
re-emitted M1 reports with V1 appendix + V2 control rows
evaluation report: full §5 grid as JSON + rendered tables/plots
paper-ready artifacts: the cost/correctness plane figure, the
  reliability curves, the per-domain table, the multi-hop slice table
```

## 8. Compute estimate

```text
labeling (only if V4=no)   ~200k×2 short forward passes ≈ 30–60 H100-h
controls (V2)              ~⅓ of one M1 certification pass
gate training + eval       single GPU, < 1 day total including sweeps
multi-hop slice            teacher generation+filtering, ~2–4 H100-h
```

## 9. Stop condition

When GT6–GT10 are resolved (green or honestly documented as frontier
findings), stop and report. Do not proceed to M3.5, serving integration,
or any training touching the base model.