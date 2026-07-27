# MERGECERT.md — Certifying Attention-Weighted KV Merging (fifth regime)

Campaign brief for evaluating the KV-Merge method (Kevin T.N.,
github.com/jkdkr2439/KV-Merge) on the house certification harness.
Authoritative documents: spec v0.3.7 (semantics, incl. §13.4 anchors and
diagnostics), the M1/E1FULL certification tables (comparison rows).
Precedence: this brief on scope, the spec on semantics.

**Framing (write into the report header, verbatim in spirit):** this run
evaluates the *method at its best* — real attention weights, proper
statistics, matched budgets — not the source repo's evaluation. It is a
scientific placement run: merging is the missing fourth training-free
point on the evict / subsample / synthesize spectrum, and every outcome
below is pre-registered as reportable, including the ones where merging
earns its place. The report is delivered to Tyler and Kevin before any
other use.

### Do-not-build list
- No cross-model comparison: the method is PORTED onto the house
  fingerprint (Qwen3-4B-Instruct-2507); no number from the source repo's
  Qwen2.5 runs enters any table.
- No hyperparameter tuning sweep: merge block size and ratios fixed to
  the source repo's defaults (one registered ratio grid only, matching
  the house eviction fractions for budget-matching).
- No deployment certification / L3-default contention — placement only.
- No training of any kind; merging is training-free by definition here.
- Report is private-first (Tyler + Kevin) — no public artifacts from
  this brief.

---

## P0 — Port and verify (blocks everything)

```text
P0.1  implement attention-weighted merging inside the house harness:
      old-region KV partitioned into blocks; each block's K and V
      replaced by attention-mass-weighted averages (REAL accumulated
      attention scores from the harness — the source repo approximated
      these via KV dot products; note the upgrade in the report);
      recent window at full resolution; sinks pinned per §13.2 (the
      source method has no sink handling — record this as a port
      addition, applied identically to all arms).
P0.2  budget matching: merged cache size computed in retained KV
      vectors; grid chosen so retained budget EXACTLY matches the
      house eviction rows (0.25 / 0.40 evicted-equivalent) plus one
      extreme point (0.90) for the graceful-degradation question.
P0.3  direction sanity (not number reproduction): at the 0.90 point,
      confirm the source repo's *qualitative* claim on a 200-item
      subsample — merging degrades gracefully where eviction collapses
      (house metrics, not cosine). If the direction does not
      reproduce with real attention weights, STOP and report — the
      port or the claim is wrong, and finding out costs $3.
P0.4  degeneracy check (the identical-numbers red flag from the repo
      review): verify the ported merge at 0.90 is NOT sink+recent in
      disguise — compare its kept/merged structure and outputs against
      a StreamingLLM-style arm; report overlap.
```

## Q1 — Two-axis placement at matched budget (the headline table)

M1 harness unchanged: per-axis, counterfactual probes, noise-floor row,
CIs, greedy, fingerprint pinned.

```text
| arm (matched budget)      | agg KL | agg accΔ | pointwise lost|prior |
| eviction 0.25 / 0.40      | (existing rows)                        |
| frozen subsample (ref)    | 0.2566 | +0.063   | 0.188               |
| unfrozen compactor (ref)  | 0.1385 | +0.042   | 0.083               |
| MERGE 0.25 / 0.40 / 0.90  | ?      | ?        | ?                   |
| zero-compression control  | 0.0000 | 0.000    | 0.000               |

registered readings:
  pointwise ≪ eviction at matched budget → the smuggling mechanism is
    general to blend-style compression, not specific to trained latents
  pointwise ≈ eviction → merging's preservation claim does not survive
    counterfactual probing (cosine hid it)
  aggregation: merging perturbs surviving-attention geometry (§13.1 —
    merged keys are convex combinations); whether KL lands nearer
    eviction or the frozen subsampler is genuinely open — report where.
  90% row: graceful-vs-catastrophic stated in house metrics with CIs —
    the source repo's one defensible headline, given real statistics.
```

## Q2 — Routability: can anything read merged loss?

The live theory test: merge mechanics are *externally visible* (block
boundaries, merge weights, per-block mass are all inspectable at write
time), unlike trained synthesis. Mechanics-routability theory predicts
merged loss should be MORE shadow/feature-routable than the compactor's.

```text
labels    GT16-protocol counterfactual relabel on the standard 30k
          manifest subsample at 0.25/0.40 (reuse the labeling fleet)
arms      (a) surface/c0 features  (b) merge-mechanics features (NEW,
          cheap: needle's merge-block size, its attention mass share
          within its block, block heterogeneity, distance to recent
          window)  (c) shadow gate zero-shot + refit  (d) sink-head
          monitor zero-shot (fifth-regime F5 row) + refit
          (e) residual probe refit (best-layer sweep)
registered readings:
  (b) ≥ 0.70 → merged loss is mechanics-routable; the routability
      ladder gains its predicted middle case (visible-mechanics blend)
  (b) ≈ 0.55 with (e) high → merging behaves like synthesis despite
      visible mechanics — internality is about the blend, not the
      inspectability of the blender; a strong, reportable surprise
  (d) transfer ≈ 0.72–0.78 → sink-as-sensor generalizes to a FIFTH
      regime (one more row in the F5 table)
```

## Q3 — Fragility placement

E1-protocol 2k relabel: does merged loss nest inside the existing
fragility ordering (A / FR / E1F failure sets)? Registered vocabulary:
nesting fraction + κ with per-instance base rates, per PREPROBE
practice. Content-intrinsic fragility predicts substantial nesting even
across a mechanism change; report where merging lands.

## Deliverables

MERGECERT-REPORT.md: P0 port notes (incl. the real-attention upgrade
and sink addition), Q1 placement table with all reference rows, Q2
routability table (+ the F5 fifth-regime row), Q3 nesting, and two
closing sections: **"For the KV-Merge README"** — the defensible claims
this run supports, stated in publishable form with CIs, plus the claims
it does not support, stated kindly and precisely (the repo review's fix
list resolved by measurement, not opinion); and **"For the spec"** — a
draft §13.7 note adding merge as the fourth training-free regime point
if Q1/Q2 justify it. Private to Tyler + Kevin.

## Compute budget

P0 port + sanity ≈ $8 · Q1 certification (3 ratios) ≈ $15 · Q2 relabel
subsample + captures + probe refits ≈ $25–35 · Q3 ≈ $4.
**Total ≈ $50–65.**

## Stop condition

P0.3 direction failure → stop and report (that alone is worth knowing).
Otherwise Q1–Q3 + deliverables → stop and report. No tuning, no
deployment work, no public artifacts.