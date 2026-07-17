# PREPROBE.md — Pre-Probe Experiments (blocking for PROBE.md)

Scope: two small experiments whose outcomes determine what PROBE.md is
allowed to claim and which probe arms it may contain. Re-analysis plus
~$30-class compute over existing `memsub-artifacts` artifacts and the M3.5
compactor checkpoints. Precedence: this brief on scope, spec v0.3.6 on
semantics. Do not begin any probe training; this brief ends with a report,
not a model.

---

## E1 — Label replicability across compactor instances  [BLOCKING]

**Question.** Is y ("this fact did not survive the blend") a stable property
of (query, block, regime), or an idiosyncrasy of one 50M-parameter
checkpoint? Read-side probes (attention statistics, hidden states) can only
learn a target that generalizes across instances; the self-scoring
compactor is the only arm that can work if y is instance-specific.

```text
sample      2,000 items, stratified: domain × y (from the M3.5 relabel)
            × needle-token rarity tercile (from E2's feature pass — run
            E2's feature extraction first, it's free)
instances   A = shipped t=1024 checkpoint (the M3.5 label source)
            B = one reseeded t=1024 checkpoint, identical config/data,
                new seed (~$25 of the sweep scaffolding)
            C = existing t=512 sweep checkpoint (capacity contrast, $0)
protocol    relabel the sample under B and C with the exact GT16 labeling
            protocol (same contexts, same eq_policy_v1, greedy)
report      pairwise y agreement A↔B (the headline: same capacity, seed
            only) and A↔C (capacity effect, diagnostic); Cohen's κ and
            raw agreement, overall and restricted to y=1 rows (loss-side
            agreement is what the probes need); per-domain breakdown
```

**Decision rule (write the verdict into the report verbatim):**

```text
κ(A↔B) ≥ 0.6   → CONTENT-STRUCTURED: all probe arms viable; PROBE.md
                  may claim checkpoint-independent sufficiency signal
0.3 ≤ κ < 0.6  → PARTIALLY STABLE: read-side arms trained and evaluated
                  per-checkpoint only; PROBE.md claims scoped accordingly;
                  report the stable fraction
κ(A↔B) < 0.3   → INSTANCE NOISE: read-side arms (attention, hidden-state)
                  are chasing an unlearnable target — PROBE.md becomes a
                  self-scoring-compactor brief with the read-side arms
                  documented as infeasible and E1 as the evidence
```

## E2 — Failure-structure autopsy  [free, run first]

**Question.** Is what dies in the blend structured by observable surface
features? Structure = cheap gate features now + supervision targets for
the self-scoring head later.

```text
sample      from the M3.5 relabel (t=1024 arm): all y=1 needle rows plus
            a matched y=0 sample (same domains, same spans where possible)
features    per item, computed from corpus + tokenizer only (no model):
              needle token rarity (min / mean corpus log-frequency of the
                gold-answer tokens under the Qwen tokenizer)
              fact type {number, name/entity, code symbol, date, common
                phrase} — classify with a cheap prompted pass
              needle position within source span (relative offset)
              source span length; distance from span to recent-raw window
              domain; block overlap feature from the M3 gate
analysis    (1) univariate: per-feature AUC against y
            (2) a 5-feature logistic model, doc-level splits, evicted-only
                protocol — report AUC with CI; this is arm c0's ceiling
                estimate and the number PROBE.md quotes as "surface
                features alone reach X"
            (3) qualitative: read 30 y=1 items, tag each with a one-line
                failure description; summarize recurring patterns
report      feature table + c0 AUC + the qualitative pattern list; flag
            any feature with univariate AUC ≥ 0.60
```

## Deliverables

`PREPROBE-REPORT.md` (one page): E1 κ values + verdict line per the
decision rule; E2 feature table, c0 AUC, pattern summary; a final section
titled "Consequences for PROBE.md" stating which arms survive and what c0
sets as the floor. Plus raw artifacts: relabel JSONs for B/C, feature
matrix, fitted c0 model.

## Compute

E2 ≈ $5 (prompted fact-type pass) · E1 ≈ $25–30 (one reseed train +
2k-item relabels ×2). Total ≤ $40.

## Stop condition

Report and stop. PROBE.md is written after — and conditioned on — this
report.