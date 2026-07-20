# Clean E1FULL Recertification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce and launch a leakage-free E1FULL training and n=60 certification pipeline with auditable provenance, correct paired statistics, and conservative deployment metadata.

**Architecture:** Pure helpers in `memsub.certification.experiment_protocol` own deterministic holdout selection, canonical hashing, disjointness checks, and paired intervals. Modal runners consume those helpers and exchange hashes through holdout, mixture, training-stat, checkpoint, and certification artifacts. Current prose is downgraded until the clean artifact exists; only measured clean values may restore claims.

**Tech Stack:** Python 3.12, pytest, NumPy, PyTorch, safetensors, Modal.

## Global Constraints

- Reserve 15 eligible documents per domain before constructing training data.
- Reject any document-level or item-level train/certification overlap.
- Record document IDs, probe IDs, input hashes, and paired 95% confidence intervals.
- Keep runtime `max_certified_depth` at zero unless primary distributional GT13 passes.
- Use new clean artifact/checkpoint names; do not overwrite contaminated evidence.
- Paid scope is one clean unfrozen E1FULL train plus n=60 certification, with no sweeps or gate reruns.

---

### Task 1: Pure Experiment Protocol

**Files:**
- Create: `memsub/certification/experiment_protocol.py`
- Modify: `memsub/certification/__init__.py`
- Create: `tests/test_certification_experiment_protocol.py`

**Interfaces:**
- Produces: `canonical_sha256(value)`, `select_holdout_documents(...)`, `assert_train_eval_disjoint(...)`, and `paired_bootstrap_ci(...)`.

- [ ] Write tests for order-independent 15-per-domain selection, insufficient candidates, both overlap levels, canonical hashes, and deterministic paired intervals.
- [ ] Run the focused tests and confirm failures occur because the helpers do not exist.
- [ ] Implement the minimal pure helpers and exports.
- [ ] Run the focused tests until green.

### Task 2: Holdout, Manifest, And Checkpoint Provenance

**Files:**
- Modify: `modal-runners/modal-m35-certification-and-gate-refresh.py`
- Modify: `modal-runners/modal-fullrecipe-c2-mixture-manifest.py`
- Modify: `modal-runners/modal-fullrecipe-c1-batched-rationale-prep.py`
- Modify: `modal-runners/modal-fullrecipe-instrumented-compactor-training.py`
- Modify: `modal-runners/fullrecipe-instrumented-ddp-training-inner-script.py`
- Modify: `memsub/compactor/still_amortized_kv_compactor.py`
- Modify: `tests/test_gt11_compactor_identity_passthrough.py`

**Interfaces:**
- Consumes: Task 1 helpers.
- Produces: `/artifacts/corpus-fullrecipe/certification-holdout-clean-v1.json`; a mixture manifest with `holdout_sha256`; checkpoint metadata fields `training_manifest_sha256` and `certification_holdout_sha256`.

- [ ] Add failing metadata round-trip and source-level runner contract tests.
- [ ] Run focused tests and observe the missing metadata/contract failures.
- [ ] Add the holdout builder, require/exclude its documents in the mixture and merge paths, pass hashes into training, and persist them in safetensors.
- [ ] Run focused tests until green.

### Task 3: Fail-Closed Certification And Complete Statistics

**Files:**
- Modify: `modal-runners/modal-m35-certification-and-gate-refresh.py`
- Modify: `tests/test_certification_experiment_protocol.py`

**Interfaces:**
- Consumes: holdout, training manifest, and checkpoint hash metadata from Task 2.
- Produces: `summary-e1full-clean-v1-n60.json` with full provenance and intervals for all four metrics.

- [ ] Add failing tests for the complete metric set and conservative depth mapping.
- [ ] Run focused tests and confirm the failures.
- [ ] Select only reserved documents, record every probe, assert exact holdout selection and zero overlap, verify checkpoint hashes, compute all paired intervals, and set single/iterative metadata from primary GT13 results only.
- [ ] Run focused tests until green.

### Task 4: Invalidate Unsupported Claims And Repair Data

**Files:**
- Modify: `E1FULL-REPORT.md`
- Modify: `README.md`
- Modify: `docs/draft2.md`
- Modify: `paper2/main.tex`
- Modify: `unified_memory_substrate_spec_v0.3.7.md`
- Modify: `modal-runners/modal-push-compactor-checkpoints-to-huggingface.py`
- Modify: `plans/260719-2328-e1full-unfrozen-full-recipe/plan.md`
- Modify: `plans/260717-2319-probe-sufficiency-arms/gt22-gt24.json`

**Interfaces:**
- Produces: prose that labels the old n=60 result contaminated and non-deployable, plus strict JSON.

- [ ] Add a repository test that strictly parses tracked JSON and checks the key documents do not retain the unsupported deployment/first-certification claims.
- [ ] Run it and confirm it fails on the existing artifacts.
- [ ] Replace unsupported claims with the contamination finding and pending-clean-rerun status; encode the infinite threshold as `null` with a descriptive mode.
- [ ] Rebuild `paper2/main.pdf` after the TeX edit.
- [ ] Run document/data tests until green.

### Task 5: Verify And Launch

**Files:**
- Modify: `plans/260719-2328-e1full-unfrozen-full-recipe/plan.md` with job IDs and state.

**Interfaces:**
- Produces: live Modal function/job IDs and, after completion, the clean certification artifact copied into the repository.

- [ ] Run `./.venv/bin/pytest tests/ -q`, `./.venv/bin/python -m compileall -q memsub modal-runners tests`, `git diff --check`, and strict JSON parsing.
- [ ] Run the remote holdout builder and manifest rebuild; inspect exact overlap counts and hashes.
- [ ] Merge filtered triplets, repack contexts, and verify training stats bind the holdout hash.
- [ ] Launch `e1full-clean-v1-t1024-T8k`; record the function call ID and stop if the tripwire fires.
- [ ] After training completes, run `summary-e1full-clean-v1-n60`; copy and audit the artifact.
- [ ] Update measured prose only from the clean artifact, rerun verification, and commit the final result.
