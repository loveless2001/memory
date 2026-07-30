# MergeCert Q1 Reference Table Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the Q1 report table so matched Q1 arms are paired and current n=60 historical references are separately labelled and evidence-bound.

**Architecture:** Preserve the immutable Q1 verdict/trigger chain. Extend report evidence loading to hash-bind the existing frozen report and clean unfrozen JSON, derive reference rows from those sources, and render them separately from Q1's matched arms. Extend fail-closed validation and the artifact manifest through the existing loaded-file provenance mechanism.

**Tech Stack:** Python 3.12, pytest 8.3.4, deterministic Markdown rendering, JSON and SHA-256 evidence binding.

## Global Constraints

- Do not modify `plans/260728-mergecert-q1/q1-verdict.json` or `plans/260728-mergecert-q1/q1-trigger.json`.
- Do not modify the user's primary-checkout `MERGECERT-Q1.md` or `MERGECERT-REPORT.md`.
- Do not push, publish, transmit, or run paid/GPU work.
- Historical reference rows must be explicitly described as not directly budget/population matched to Q1.
- Use `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` for the full local test suite.

---

### Task 1: Lock the corrected presentation contract

**Files:**
- Modify: `tests/test_mergecert_q1_report.py`

**Interfaces:**
- Consumes: `_build_bundle(tmp_path, positive=...)`, `renderer.load_evidence()`, and `renderer.render_report()`.
- Produces: regression assertions for matched-arm ordering, separated n=60 references, source drift rejection, and manifest coverage.

- [ ] **Step 1: Extend fixture evidence**

Copy `FULLRECIPE-REPORT.md` and
`plans/260719-2328-e1full-unfrozen-full-recipe/summary-e1full-clean-v1-n60.json`
into the temporary repository constructed by `_build_bundle`.

- [ ] **Step 2: Write the failing presentation test**

Assert that the matched table's data rows are exactly:

```python
[
    "eviction 0.25",
    "MERGE 0.25",
    "eviction 0.40",
    "MERGE 0.40",
    "zero-compression control",
]
```

Assert that a separately headed historical context table contains `0.2820`,
`+0.1019`, `0.210`, `0.1281`, `+0.0536`, and `0.050`, together with an
explicit not-directly-matched warning.

- [ ] **Step 3: Write failing provenance tests**

Assert that changing either authoritative source makes validation fail, and
that both source paths appear in the generated artifact manifest.

- [ ] **Step 4: Run the focused tests to verify RED**

Run:

```bash
/home/lenovo/projects/memory/.venv/bin/pytest -q tests/test_mergecert_q1_report.py
```

Expected: failures because the renderer still mixes stale reference rows into
the matched table and does not load the two n=60 sources.

### Task 2: Load and validate current reference evidence

**Files:**
- Modify: `plans/260728-mergecert-q1/render-report.py`
- Modify: `plans/260728-mergecert-q1/validate-report.py`
- Test: `tests/test_mergecert_q1_report.py`

**Interfaces:**
- Consumes: the frozen supersession sentence and
  `summary["compactor-d1"]` plus `provenance["overlap_audit"]`.
- Produces: `evidence["reference_context"]`, with rows containing `label`,
  `n`, `budget_note`, `mean_kl`, `accuracy_delta`, and `lost_prior`.

- [ ] **Step 1: Add authoritative sources to evidence loading**

Record both sources through `_record`, load the clean JSON, parse the frozen
n=60 supersession sentence, and build `reference_context`.

- [ ] **Step 2: Fail closed on semantic drift**

Require SHA-256
`58b95e104c0c1ab2e2bb47a222a3672bb5dbc58dee815de4ea02c3abcef5969d`
for `FULLRECIPE-REPORT.md` and
`a7636b54148e7133237af68bf63fbc23811d5ce80417f8447711a89a559dc2a8`
for the clean JSON. Require 60 clean certification documents, empty document
and item overlap lists, finite metrics, and exactly two labelled context rows.

- [ ] **Step 3: Run focused evidence tests**

Run:

```bash
/home/lenovo/projects/memory/.venv/bin/pytest -q tests/test_mergecert_q1_report.py -k "reference or manifest"
```

Expected: provenance tests pass; presentation remains red until Task 3.

### Task 3: Render the split Q1 presentation

**Files:**
- Modify: `plans/260728-mergecert-q1/render-report.py`
- Test: `tests/test_mergecert_q1_report.py`

**Interfaces:**
- Consumes: `q1["summaries"]` and `evidence["reference_context"]`.
- Produces: `_placement_table(q1)` containing only matched Q1 arms and
  `_reference_context_table(rows)` containing current n=60 context.

- [ ] **Step 1: Pair matched Q1 rows**

Render arms in this exact order:

```python
(
    "eviction-0.25",
    "merge-0.25",
    "eviction-0.40",
    "merge-0.40",
    "control-0.00",
)
```

- [ ] **Step 2: Render the separate context section**

Add `### Historical context — not directly budget/population matched` and a
table with regime, population/budget note, n, aggregate KL, aggregate accuracy
delta, and pointwise lost given prior.

- [ ] **Step 3: Run report tests to verify GREEN**

Run:

```bash
/home/lenovo/projects/memory/.venv/bin/pytest -q tests/test_mergecert_q1_report.py
```

Expected: all report tests pass.

### Task 4: Regenerate and verify the report bundle

**Files:**
- Modify: `MERGECERT-Q1-REPORT.md`
- Modify: `plans/260728-mergecert-q1/artifact-manifest.json`

**Interfaces:**
- Consumes: all hash-bound report evidence.
- Produces: deterministic corrected report and complete manifest.

- [ ] **Step 1: Record immutable hashes**

Run:

```bash
sha256sum plans/260728-mergecert-q1/q1-verdict.json plans/260728-mergecert-q1/q1-trigger.json
```

Expected:

```text
4266eb66c5b0979da504b124dfa0ceb89d50e29348ea78d9ca7ac8c2614ee036
009d1ba2879b76174c13dffbea27a458b10d9a859cdb69046f3afac31a2af5a1
```

- [ ] **Step 2: Render and validate**

Run:

```bash
/home/lenovo/projects/memory/.venv/bin/python plans/260728-mergecert-q1/render-report.py
/home/lenovo/projects/memory/.venv/bin/python plans/260728-mergecert-q1/validate-report.py
```

Expected: validation reports `"pass": true` and manifest includes both current
reference sources.

- [ ] **Step 3: Recheck immutable hashes and focused tests**

Run the hash command from Step 1 and:

```bash
/home/lenovo/projects/memory/.venv/bin/pytest -q tests/test_mergecert_q1_report.py
```

Expected: hashes unchanged and all report tests pass.

- [ ] **Step 4: Run the full offline suite**

Run:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /home/lenovo/projects/memory/.venv/bin/pytest -q
```

Expected: 504 tests plus the new regression tests pass, with 2 skips.

- [ ] **Step 5: Review the final diff**

Confirm that only the design/plan, renderer, validator, report tests, corrected
report, and manifest changed; confirm the primary checkout's user files retain
their original hashes.
