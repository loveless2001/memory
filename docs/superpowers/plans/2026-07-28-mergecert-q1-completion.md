# MergeCert Q1 Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the registered 0.25/0.40 MergeCert placement experiment, conditionally run Q2/Q3 only after a favorable Q1 confidence interval, and produce a private evidence-backed `MERGECERT-Q1-REPORT.md`.

**Architecture:** Extend the existing private Modal runner with addendum-specific Q1 authorization and moderate-ratio entry points while leaving every P0 entry point unchanged. Analyze copied artifacts locally, derive the conditional trigger from pure deterministic functions, bind any Q2 work to that trigger, and render the final report from validated evidence in a new `plans/260728-mergecert-q1/` bundle.

**Tech Stack:** Python 3.12, PyTorch 2.7.1, Transformers 4.55.2, NumPy, Modal H100, pytest, SHA-256 provenance, document-cluster bootstrap confidence intervals.

## Global Constraints

- `MERGECERT-Q1.md` overrides only the parent brief's scope and stop rule; spec v0.3.7 retains semantic precedence.
- Q1 ratios are exactly `(0.25, 0.40)`. Preserve the archived M1 population and
  match merge to each eviction arm's physical retained count under budget mode
  `archived-m1-per-document-matched-physical-v1`; lengths `3072` and `2458`
  apply to 4096-token documents.
- Never execute a Q1 `0.90` arm; import the settled P0 result instead.
- Use `Qwen/Qwen3-4B-Instruct-2507`, real accumulated attention, logical sinks `0..3`, exact recent KV, greedy scoring, and unchanged M1 probe semantics.
- Use all 20 archived M1 contexts: five per domain across financial, legal, code, and literature.
- Do not tune, train, add hybrid variants, perform cross-model work, publish artifacts, or modify the public spec.
- Q2/Q3 execute only when Q1's lost-prior CI is wholly below zero, mean-KL CI is wholly below zero, or accuracy-delta CI is wholly above zero.
- Q1 H100 spend requires explicit approval before smoke; conditional Q2/Q3 may spend only within the total `$45` ceiling after the registered trigger.
- Keep the user's existing `MERGECERT-REPORT.md` modification unstaged and unchanged.
- Use `UV_CACHE_DIR=/tmp/mergecert-uv-cache` for every Modal CLI command.

---

### Task 1: Addendum authorization and moderate-ratio runner contract

**Files:**
- Modify: `modal-runners/modal-mergecert-p0-q1.py:15-27,466-475,801-1025`
- Modify: `tests/test_mergecert_campaign_contract.py`
- Create: `plans/260728-mergecert-q1/source-provenance.json`
- Add to version control: `MERGECERT-Q1.md`

**Interfaces:**
- Consumes: `/artifacts/mergecert-q1/MERGECERT-Q1.md` and `/artifacts/mergecert-q1/p0-verdict.json`.
- Produces: `_load_q1_authorization() -> dict`, `Q1_RATIOS`, `q1_addendum_smoke()`, and `q1_addendum_certify()`.
- Authorization contains `protocol`, `addendum_sha256`, `p0_verdict_sha256`, and the settled P0 component booleans.

- [ ] **Step 1: Write failing contract tests for the addendum**

Add tests that pin separate P0 and Q1 ratio constants and call the authorization helper with temporary paths:

```python
def test_mergecert_q1_addendum_uses_only_moderate_ratios():
    constants = _literal_constants(RUNNER)
    assert constants["RATIOS"] == (0.25, 0.40, 0.90)
    assert constants["Q1_RATIOS"] == (0.25, 0.40)
    assert constants["Q1_ARTIFACT_ROOT"] == "/artifacts/mergecert-q1"


def test_mergecert_q1_addendum_accepts_only_the_settled_negative_p0(tmp_path):
    runner = _load_module(RUNNER, "mergecert_q1_addendum_gate")
    addendum = tmp_path / "MERGECERT-Q1.md"
    verdict = tmp_path / "p0-verdict.json"
    addendum.write_text("# MERGECERT-Q1.md\n")
    verdict.write_text(json.dumps({
        "p0_3": {"pass": False},
        "p0_4": {"pass": True},
        "real_attention": {"pass": True},
        "p0_pass": False,
        "stop_q1_q3": True,
    }))
    gate = runner._load_q1_authorization(
        addendum_path=str(addendum),
        p0_verdict_path=str(verdict),
    )
    assert gate["protocol"] == "MERGECERT-Q1"
    assert gate["settled_p0"]["p0_3_pass"] is False
    assert len(gate["addendum_sha256"]) == 64
    assert len(gate["p0_verdict_sha256"]) == 64
```

Also assert `_run_q1` constructs only `control-0.00`, `eviction-0.25`,
`eviction-0.40`, `merge-0.25`, and `merge-0.40`.

- [ ] **Step 2: Run the new tests and verify red**

Run:

```bash
./.venv/bin/python -m pytest \
  tests/test_mergecert_campaign_contract.py::test_mergecert_q1_addendum_uses_only_moderate_ratios \
  tests/test_mergecert_campaign_contract.py::test_mergecert_q1_addendum_accepts_only_the_settled_negative_p0 -q
```

Expected: failures for missing `Q1_RATIOS` and `_load_q1_authorization`.

- [ ] **Step 3: Implement the fail-closed addendum gate**

Retain `RATIOS` for P0 and add:

```python
Q1_RATIOS = (0.25, 0.40)
Q1_ARTIFACT_ROOT = "/artifacts/mergecert-q1"
Q1_ADDENDUM_PATH = f"{Q1_ARTIFACT_ROOT}/MERGECERT-Q1.md"
Q1_P0_VERDICT_PATH = f"{Q1_ARTIFACT_ROOT}/p0-verdict.json"
Q1_OUTPUT = f"{Q1_ARTIFACT_ROOT}/q1-certification.json"
Q1_SMOKE_OUTPUT = f"{Q1_ARTIFACT_ROOT}/q1-smoke.json"


def _load_q1_authorization(
    *,
    addendum_path: str = Q1_ADDENDUM_PATH,
    p0_verdict_path: str = Q1_P0_VERDICT_PATH,
) -> dict:
    if not os.path.exists(addendum_path) or not os.path.exists(p0_verdict_path):
        raise ValueError("Q1 addendum authorization files are missing")
    with open(p0_verdict_path) as handle:
        verdict = json.load(handle)
    settled = {
        "p0_3_pass": verdict.get("p0_3", {}).get("pass"),
        "p0_4_pass": verdict.get("p0_4", {}).get("pass"),
        "real_attention_pass": verdict.get("real_attention", {}).get("pass"),
        "p0_pass": verdict.get("p0_pass"),
        "stop_q1_q3": verdict.get("stop_q1_q3"),
    }
    expected = {
        "p0_3_pass": False,
        "p0_4_pass": True,
        "real_attention_pass": True,
        "p0_pass": False,
        "stop_q1_q3": True,
    }
    if settled != expected:
        raise ValueError("Q1 addendum requires the settled negative P0 verdict")
    return {
        "protocol": "MERGECERT-Q1",
        "addendum_sha256": _sha256_file(addendum_path),
        "p0_verdict_sha256": _sha256_file(p0_verdict_path),
        "settled_p0": settled,
    }
```

Use `Q1_RATIOS` in Q1 arm construction, cache construction, provenance, and
output validation. Rename the Modal functions to `q1_addendum_smoke` and
`q1_addendum_certify`; leave `smoke` and `p0_direction` unchanged.

- [ ] **Step 4: Write exact source provenance**

Create `plans/260728-mergecert-q1/source-provenance.json`:

```json
{
  "protocol": "MERGECERT-Q1",
  "model_id": "Qwen/Qwen3-4B-Instruct-2507",
  "upstream_commit": "cd4ed948d62231449dbab9669608bbb4fd220713",
  "upstream_files": {
    "README.md": "edfd5236d99dab5d6e4bf80b74dd79a54ffd94cec4b7066511dc6fd7ae7cae17",
    "benchmarks/modal_kv_real_bench.py": "518b2d2cd4b652f4cc83ef9c82593fe624301986e0e3e22780ee9f0bfe423bb8",
    "lego_server.py": "f1df91c8af05cf4ea5000f4027450bf91e5e269f4e922da8979fc0885d6ff228"
  },
  "ratios": [0.25, 0.4],
  "sink_token_count": 4,
  "addendum": {
    "path": "MERGECERT-Q1.md",
    "sha256": "faf1239bf21ed3ec4e33421645694cc7a70ecc04765961af04c3f4ff2f106df7"
  },
  "settled_p0": {
    "verdict_path": "plans/260727-mergecert/p0-verdict.json",
    "verdict_sha256": "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a",
    "raw_path": "plans/260727-mergecert/p0-direction-200.json",
    "raw_sha256": "2d12ae1de090f3d93ba3cad97f68a49f543cd4a0398078c625e2641981f10f6c"
  },
  "parent_source_provenance_sha256": "cbaaec6a20cb4e53ab36a56f377c91c6bd97b8028f1fd60e2c63bdb759576930"
}
```

- [ ] **Step 5: Run focused tests**

```bash
./.venv/bin/python -m pytest \
  tests/test_mergecert_campaign_contract.py \
  tests/test_attention_weighted_kv_merge.py \
  tests/test_real_attention_mass.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit the registered addendum and runner contract**

```bash
git add MERGECERT-Q1.md modal-runners/modal-mergecert-p0-q1.py \
  plans/260728-mergecert-q1/source-provenance.json \
  tests/test_mergecert_campaign_contract.py
git commit -m "feat: authorize moderate-ratio MergeCert Q1"
```

Do not stage `MERGECERT-REPORT.md`.

---

### Task 2: Q1 analyzer, per-domain slices, and conditional trigger

**Files:**
- Modify: `plans/260727-mergecert/analyze-mergecert-q1.py`
- Modify: `tests/test_mergecert_q1_analysis.py`
- Create during execution: `plans/260728-mergecert-q1/q1-verdict.json`
- Create during execution: `plans/260728-mergecert-q1/q1-trigger.json`
- Create during execution: `plans/260728-mergecert-q1/q1-table.md`

**Interfaces:**
- Consumes: copied Q1 certification JSON with five arms and addendum authorization.
- Produces: `classify_registered_readings(intervals: dict) -> dict`,
  `per_domain_summaries(reports_by_arm: dict) -> dict`, and the verdict fields
  `registered_readings`, `per_domain`, `run_q2_q3`, and `favorable_intervals`.

- [ ] **Step 1: Replace positive-parent fixtures with addendum fixtures**

Change fixture ratios to `(0.25, 0.40)` and gate data to:

```python
"q1_authorization": {
    "protocol": "MERGECERT-Q1",
    "addendum_sha256": "a" * 64,
    "p0_verdict_sha256": "b" * 64,
    "settled_p0": {
        "p0_3_pass": False,
        "p0_4_pass": True,
        "real_attention_pass": True,
        "p0_pass": False,
        "stop_q1_q3": True,
    },
}
```

Assert the analyzer rejects any `merge-0.90` or `eviction-0.90` arm.

- [ ] **Step 2: Write failing boundary tests for R1, R2, and R3**

```python
def test_q1_trigger_runs_for_any_favorable_registered_interval():
    analyzer = _load_analyzer()
    intervals = {
        "0.25": {
            "lost_prior": {"mean_diff": -0.1, "ci95": [-0.2, -0.01]},
            "mean_kl": {"mean_diff": 0.1, "ci95": [0.01, 0.2]},
            "acc_delta": {"mean_diff": 0.0, "ci95": [-0.1, 0.1]},
        },
        "0.40": {
            "lost_prior": {"mean_diff": 0.0, "ci95": [-0.1, 0.1]},
            "mean_kl": {"mean_diff": 0.0, "ci95": [-0.1, 0.1]},
            "acc_delta": {"mean_diff": 0.0, "ci95": [-0.1, 0.1]},
        },
    }
    reading = analyzer.classify_registered_readings(intervals)
    assert reading["r1"] == "R1"
    assert reading["run_q2_q3"] is True
    assert reading["favorable_intervals"] == ["0.25:lost_prior"]


def test_q1_trigger_skips_when_all_intervals_overlap_or_are_worse():
    analyzer = _load_analyzer()
    intervals = _overlapping_intervals()
    reading = analyzer.classify_registered_readings(intervals)
    assert reading["r1"] == "R2"
    assert reading["run_q2_q3"] is False
    assert reading["favorable_intervals"] == []
```

Add separate cases where only KL has `ci95[1] < 0` and only accuracy delta has
`ci95[0] > 0`.

- [ ] **Step 3: Run the boundary tests and verify red**

```bash
./.venv/bin/python -m pytest tests/test_mergecert_q1_analysis.py -q
```

Expected: failures for three-ratio assumptions, passing-P0 gate assumptions,
missing per-domain output, and missing classifier.

- [ ] **Step 4: Implement moderate-ratio analysis and classifier**

Set `RATIOS = (0.25, 0.40)`. Validate the exact settled authorization and five
arms. Implement:

```python
def classify_registered_readings(intervals: dict) -> dict:
    favorable = []
    pointwise = []
    aggregation = []
    for ratio in ("0.25", "0.40"):
        row = intervals[ratio]
        if row["lost_prior"]["ci95"][1] < 0:
            pointwise.append(f"{ratio}:lost_prior")
        if row["mean_kl"]["ci95"][1] < 0:
            aggregation.append(f"{ratio}:mean_kl")
        if row["acc_delta"]["ci95"][0] > 0:
            aggregation.append(f"{ratio}:acc_delta")
    favorable.extend(pointwise)
    favorable.extend(aggregation)
    return {
        "r1": "R1" if pointwise else "R2",
        "r3": "aggregation-positive" if aggregation else "aggregation-negative",
        "pointwise_favorable": pointwise,
        "aggregation_favorable": aggregation,
        "favorable_intervals": favorable,
        "run_q2_q3": bool(favorable),
    }
```

Compute each domain's arm summaries from the same reports without resampling
and include exact document and probe counts. Include the classifier output in
both `q1-verdict.json` and a minimal `q1-trigger.json` whose evidence hash is
the SHA-256 of the verdict file.

Add CLI flags:

```python
parser.add_argument("--expected-documents", type=int, default=20)
parser.add_argument("--n-resamples", type=int, default=20_000)
parser.add_argument("--trigger", type=Path)
```

Write a trigger only when `expected_documents == 20` and `--trigger` is
provided. Its exact schema is:

```python
trigger = {
    "protocol": "MERGECERT-Q1",
    "run_q2_q3": readings["run_q2_q3"],
    "favorable_intervals": readings["favorable_intervals"],
    "q1_verdict_sha256": _sha256_file(args.output),
    "addendum_sha256": authorization["addendum_sha256"],
    "p0_verdict_sha256": authorization["p0_verdict_sha256"],
}
```

- [ ] **Step 5: Run analyzer tests and static output checks**

```bash
./.venv/bin/python -m pytest tests/test_mergecert_q1_analysis.py -q
./.venv/bin/python -m py_compile \
  plans/260727-mergecert/analyze-mergecert-q1.py
```

Expected: all pass.

- [ ] **Step 6: Commit analyzer behavior**

```bash
git add plans/260727-mergecert/analyze-mergecert-q1.py \
  tests/test_mergecert_q1_analysis.py
git commit -m "feat: classify MergeCert Q1 placement"
```

---

### Task 3: Bind conditional Q2 to the Q1 trigger

**Files:**
- Modify: `modal-runners/modal-mergecert-q2-capture.py:25,64-74,238-274`
- Modify: `modal-runners/modal-mergecert-q2-probes.py:32,76-85,825-835`
- Modify: `plans/260727-mergecert/analyze-mergecert-q2.py:148-170`
- Modify: `tests/test_mergecert_campaign_contract.py`
- Modify: `tests/test_mergecert_q2_analysis.py`

**Interfaces:**
- Consumes: `/artifacts/mergecert-q1/q1-trigger.json`.
- Produces: `require_q1_trigger(path: str) -> dict` semantics shared verbatim
  across capture, probes, and local analysis.

- [ ] **Step 1: Write failing Q2 authorization tests**

Assert Q2 rejects missing trigger, `run_q2_q3: false`, an empty favorable list,
or a missing 64-character Q1 verdict hash. Assert it accepts:

```python
{
    "protocol": "MERGECERT-Q1",
    "run_q2_q3": True,
    "favorable_intervals": ["0.40:mean_kl"],
    "q1_verdict_sha256": "c" * 64,
    "addendum_sha256": "a" * 64,
    "p0_verdict_sha256": "b" * 64,
}
```

- [ ] **Step 2: Run tests and verify red**

```bash
./.venv/bin/python -m pytest \
  tests/test_mergecert_campaign_contract.py \
  tests/test_mergecert_q2_analysis.py -q
```

Expected: failures because all Q2 paths still require `p0_pass: true`.

- [ ] **Step 3: Replace the obsolete Q2 gate**

Use:

```python
Q1_TRIGGER_PATH = "/artifacts/mergecert-q1/q1-trigger.json"


def _require_q1_trigger(path: str = Q1_TRIGGER_PATH) -> dict:
    if not os.path.exists(path):
        raise ValueError("Q2 is blocked until q1-trigger.json exists")
    with open(path) as handle:
        trigger = json.load(handle)
    valid = (
        trigger.get("protocol") == "MERGECERT-Q1"
        and trigger.get("run_q2_q3") is True
        and bool(trigger.get("favorable_intervals"))
        and len(trigger.get("q1_verdict_sha256", "")) == 64
        and len(trigger.get("addendum_sha256", "")) == 64
        and len(trigger.get("p0_verdict_sha256", "")) == 64
    )
    if not valid:
        raise ValueError("Q2 is blocked by the registered Q1 trigger")
    return trigger
```

Store the complete trigger and trigger-file hash in every Q2 state, capture
summary, routability result, and score manifest. Make the local analyzer
recompute and validate the same conditions.

- [ ] **Step 4: Run focused Q2/Q3 tests**

```bash
./.venv/bin/python -m pytest \
  tests/test_mergecert_campaign_contract.py \
  tests/test_mergecert_q2_capture_schema.py \
  tests/test_mergecert_q2_analysis.py \
  tests/test_mergecert_q3_analysis.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit conditional authorization**

```bash
git add modal-runners/modal-mergecert-q2-capture.py \
  modal-runners/modal-mergecert-q2-probes.py \
  plans/260727-mergecert/analyze-mergecert-q2.py \
  tests/test_mergecert_campaign_contract.py \
  tests/test_mergecert_q2_analysis.py
git commit -m "fix: bind MergeCert Q2 to Q1 trigger"
```

---

### Task 4: Add deterministic Q1 report rendering and validation

**Files:**
- Create: `plans/260728-mergecert-q1/render-report.py`
- Create: `plans/260728-mergecert-q1/validate-report.py`
- Create: `tests/test_mergecert_q1_report.py`
- Create during execution: `MERGECERT-Q1-REPORT.md`
- Create during execution: `plans/260728-mergecert-q1/artifact-manifest.json`
- Create during execution: `plans/260728-mergecert-q1/compute-actuals.json`
- Create during execution: `plans/260728-mergecert-q1/conditional-work.json`

**Interfaces:**
- Consumes: source provenance, parent P0 verdict, Q1 verdict/trigger, conditional
  evidence or skip, compute actuals, and local privacy disposition.
- Produces: `render_report(evidence: dict) -> str` and
  `validate_report_text(report: str, evidence: dict) -> dict`.

- [ ] **Step 1: Write failing report-completeness tests**

Use small positive and negative fixtures. Require:

```python
REQUIRED_HEADINGS = {
    "## Settled 0.90 result",
    "## Q1 — Moderate-ratio placement",
    "## Per-domain slices",
    "## Registered readings",
    "## Conditional Q2/Q3",
    "## Compute provenance",
    "## For the KV-Merge README",
    "## For the spec",
    "## Limitations",
}
```

Assert the report includes all reference/control rows, R1/R2/R3 text from the
brief, CIs for both ratios and all three metrics, billing identifiers, and no
public URL, question-mark result cell, `Qwen2.5`, deployment claim, or
transmission-confirmed claim. Require the audience line
`Private to Tyler and Kevin.` without asserting that transmission occurred.

- [ ] **Step 2: Run report tests and verify red**

```bash
./.venv/bin/python -m pytest tests/test_mergecert_q1_report.py -q
```

Expected: import failures because renderer and validator do not exist.

- [ ] **Step 3: Implement evidence-only rendering**

Render every numeric cell directly from loaded JSON. Under R2, include exactly
one paragraph offering merge-plus-anchor as a theoretically motivated future
direction while stating it was not tested. Under a positive axis, describe
only the measured ratio and axis. Render either Q2/Q3 tables or:

```text
Q2 and Q3 were skipped because no merge-minus-eviction 95% interval was
favorable under the registered Q1 rule.
```

Describe privacy as local/private with transmission not recorded. Do not reuse
the parent report's delivery-waiver record as a new delivery event.

- [ ] **Step 4: Implement fail-closed validation and manifest writing**

Validate exact report equality against deterministic rendering, required
headings, Q1 trigger consistency, all artifact hashes, billing source and app
IDs, conditional evidence/skip, and the `$45` ceiling. Write SHA-256 and byte
count for every evidence file into `artifact-manifest.json`.

- [ ] **Step 5: Run report tests**

```bash
./.venv/bin/python -m pytest tests/test_mergecert_q1_report.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit report tooling**

```bash
git add plans/260728-mergecert-q1/render-report.py \
  plans/260728-mergecert-q1/validate-report.py \
  tests/test_mergecert_q1_report.py
git commit -m "feat: validate MergeCert Q1 report"
```

---

### Task 5: Verify the local implementation before compute

**Files:**
- Modify: `docs/superpowers/plans/2026-07-28-mergecert-q1-completion.md`

**Interfaces:**
- Consumes: Tasks 1-4 committed code.
- Produces: a green local gate and explicit approval request for Q1 compute.

- [x] **Step 1: Run the complete local suite offline**

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  ./.venv/bin/python -m pytest tests -q
```

Expected: zero failures; existing environment-dependent skips remain explicit.

- [x] **Step 2: Run source and contract audits**

```bash
./.venv/bin/python -m py_compile \
  modal-runners/modal-mergecert-p0-q1.py \
  modal-runners/modal-mergecert-q2-capture.py \
  modal-runners/modal-mergecert-q2-probes.py \
  plans/260727-mergecert/analyze-mergecert-q1.py \
  plans/260727-mergecert/analyze-mergecert-q2.py \
  plans/260728-mergecert-q1/render-report.py \
  plans/260728-mergecert-q1/validate-report.py
git diff --check
git status --short
```

Expected: only the user's pre-existing `MERGECERT-REPORT.md` modification plus
plan progress changes; no untracked implementation files.

- [x] **Step 3: Audit the Modal state without launching compute**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal app list --json
UV_CACHE_DIR=/tmp/mergecert-uv-cache \
  uv run modal volume ls memsub-artifacts /mergecert-q1 --json
```

Expected: no live app and no conflicting Q1 output.

- [x] **Step 4: Request one bounded Q1 approval**

Ask for explicit authorization to run the two-document smoke and, only if it
passes, the 20-document certification with a maximum Q1 spend of `$15`. Do not
launch either command until the user approves.

---

### Task 6: Execute and analyze Q1 under the approved bound

**Files:**
- Create from remote copy: `plans/260728-mergecert-q1/q1-smoke.json`
- Create from remote copy: `plans/260728-mergecert-q1/q1-certification.json`
- Create: `plans/260728-mergecert-q1/q1-verdict.json`
- Create: `plans/260728-mergecert-q1/q1-trigger.json`
- Create: `plans/260728-mergecert-q1/q1-table.md`
- Modify: `docs/superpowers/plans/2026-07-28-mergecert-q1-completion.md`

**Interfaces:**
- Consumes: approved Modal runner and private source artifacts.
- Produces: immutable Q1 evidence and the conditional trigger decision.

- [x] **Step 1: Upload the pre-amendment authorization inputs (superseded)**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume put \
  memsub-artifacts MERGECERT-Q1.md /mergecert-q1/MERGECERT-Q1.md
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume put \
  memsub-artifacts plans/260727-mergecert/p0-verdict.json \
  /mergecert-q1/p0-verdict.json
```

These files authorized the initial failed smoke. The addendum changed after
the settled 2026-07-29 budget amendment, so this completed upload does not make
the retry ready.

- [ ] **Step 1a: Extract, review, and bind the finalized Q1 registration**

Run the CPU-only, read-only
`modal-runners/modal-mergecert-q1-registration.py` entrypoint. It may read the
existing private archives, all-items registry, source corpus, and pinned
tokenizer, but it must not load model weights, request a GPU, write the remote
volume, or launch Q1. Save its small JSON result outside the production path
first. Verify the exact tokenizer revision and tokenizer-file digest set, the
corpus manifest and all-items digests, the exact 20-document source-hash set,
the two financial smoke documents, all 12 archive hashes, and every
per-document source/model length and 0.25/0.40 start/end/requested/physical
count. Then run:

```bash
./.venv/bin/python scripts/bind-mergecert-q1-registration.py \
  /path/to/reviewed-extractor-output.json
```

This single local binding action copies the reviewed bytes to
`plans/260728-mergecert-q1/q1-registration.json`, replaces the explicit
`PENDING_CPU_EXTRACTION` sentinel with one literal
`Q1_REGISTRATION_SHA256`, and records the same literal and finalized output
path in `plans/260728-mergecert-q1/source-provenance.json`. Run all local
validators, commit, and independently review that separate post-extraction
binding commit before any upload or smoke retry. This step is pending:
`q1-registration.json` is deliberately absent, the shared hash literal and
source provenance still say pending, and production lengths, source ends,
tokenizer digests, corpus-manifest digest, and source-document digests have
not been invented.

- [ ] **Step 1b: Upload and remotely verify all reviewed Q1 inputs**

Only after the Step 1a binding commit passes independent review, upload the
finalized registration to the exact runner path together with the amended
`MERGECERT-Q1.md` and unchanged registered P0 verdict:

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume put \
  memsub-artifacts plans/260728-mergecert-q1/q1-registration.json \
  /mergecert-q1/q1-registration.json
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume put \
  memsub-artifacts MERGECERT-Q1.md /mergecert-q1/MERGECERT-Q1.md
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume put \
  memsub-artifacts plans/260727-mergecert/p0-verdict.json \
  /mergecert-q1/p0-verdict.json
```

Retrieve all three remote files to a fresh temporary directory, hash the
retrieved bytes, and compare them byte-for-byte with the reviewed local files.

```bash
mkdir -p /tmp/mergecert-q1-reviewed-remote
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume get \
  memsub-artifacts /mergecert-q1/q1-registration.json \
  /tmp/mergecert-q1-reviewed-remote/q1-registration.json --force
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume get \
  memsub-artifacts /mergecert-q1/MERGECERT-Q1.md \
  /tmp/mergecert-q1-reviewed-remote/MERGECERT-Q1.md --force
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume get \
  memsub-artifacts /mergecert-q1/p0-verdict.json \
  /tmp/mergecert-q1-reviewed-remote/p0-verdict.json --force
cmp plans/260728-mergecert-q1/q1-registration.json \
  /tmp/mergecert-q1-reviewed-remote/q1-registration.json
cmp MERGECERT-Q1.md \
  /tmp/mergecert-q1-reviewed-remote/MERGECERT-Q1.md
cmp plans/260727-mergecert/p0-verdict.json \
  /tmp/mergecert-q1-reviewed-remote/p0-verdict.json
sha256sum /tmp/mergecert-q1-reviewed-remote/q1-registration.json \
  /tmp/mergecert-q1-reviewed-remote/MERGECERT-Q1.md \
  /tmp/mergecert-q1-reviewed-remote/p0-verdict.json
```

The remote registration SHA-256 must equal the exact literal
`Q1_REGISTRATION_SHA256` recorded by Step 1a. The remote authorization hashes
must be exactly
`35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509`
and
`4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a`.
Record this verification before Step 2. The existing remote addendum is stale,
the existing P0 verdict is unchanged but not yet reverified for this retry,
and no finalized registration has been uploaded. Do not launch the retry from
that pre-amendment state.

- [ ] **Step 2: Launch the two-document smoke**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run \
  modal-runners/modal-mergecert-p0-q1.py::q1_addendum_smoke
```

Copy `/mergecert-q1/q1-smoke.json` locally, then run the analyzer with
`--expected-documents 2 --n-resamples 2000`. Verify five arms, two documents,
identical partitions, exact zero control, archive replay, finite attention,
and per-document merge/eviction physical-budget equality. For 4096-token
documents, verify budgets `{0.25: 3072, 0.40: 2458}`.

- [ ] **Step 3: Stop on any smoke defect**

If any check fails, stop all Modal apps, diagnose under
`superpowers:systematic-debugging`, add a failing regression test, fix locally,
and rerun the smoke within the approved `$15` bound. Never launch full Q1 from
an invalid smoke.

- [ ] **Step 4: Launch full Q1 detached only after a valid smoke**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run --detach \
  modal-runners/modal-mergecert-p0-q1.py::q1_addendum_certify
```

Record the app ID, inspect logs, and poll `modal app list --json` until stopped.
Do not start another full app while the registered output is resumable.

- [ ] **Step 5: Retrieve and independently analyze full Q1**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume get \
  memsub-artifacts /mergecert-q1/q1-certification.json \
  plans/260728-mergecert-q1/q1-certification.json --force
./.venv/bin/python plans/260727-mergecert/analyze-mergecert-q1.py \
  --input plans/260728-mergecert-q1/q1-certification.json \
  --output plans/260728-mergecert-q1/q1-verdict.json \
  --table plans/260728-mergecert-q1/q1-table.md \
  --trigger plans/260728-mergecert-q1/q1-trigger.json
```

Expected: 20 documents, five per domain, five arms, all archived replay checks
passing, complete CIs, per-domain slices, and one deterministic trigger.

- [ ] **Step 6: Copy the trigger to the private volume**

Only if `run_q2_q3` is true:

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume put \
  memsub-artifacts plans/260728-mergecert-q1/q1-trigger.json \
  /mergecert-q1/q1-trigger.json
```

- [ ] **Step 7: Commit Q1 evidence**

```bash
git add plans/260728-mergecert-q1/q1-smoke.json \
  plans/260728-mergecert-q1/q1-certification.json \
  plans/260728-mergecert-q1/q1-verdict.json \
  plans/260728-mergecert-q1/q1-trigger.json \
  plans/260728-mergecert-q1/q1-table.md \
  docs/superpowers/plans/2026-07-28-mergecert-q1-completion.md
git commit -m "docs: record moderate-ratio MergeCert placement"
```

---

### Task 7: Execute conditional Q2/Q3 or record the registered skip

**Files:**
- Create: `plans/260728-mergecert-q1/conditional-work.json`
- Conditional create: `plans/260728-mergecert-q1/q2-capture-summary.json`
- Conditional create: `plans/260728-mergecert-q1/q2-routability-remote.json`
- Conditional create: `plans/260728-mergecert-q1/q2-scores.npz`
- Conditional create: `plans/260728-mergecert-q1/q2-verdict.json`
- Conditional create: `plans/260728-mergecert-q1/q3-fragility.json`

**Interfaces:**
- Consumes: `q1-trigger.json`.
- Produces: either a hash-bound skip record or complete Q2/Q3 evidence.

- [ ] **Step 1: Branch mechanically on the trigger**

If `run_q2_q3` is false, write:

```json
{
  "status": "skipped",
  "rule": "Q2/Q3 run only if R1 or the aggregation half of R3 has favorable CI separation",
  "triggered": false,
  "favorable_intervals": [],
  "q1_trigger_path": "plans/260728-mergecert-q1/q1-trigger.json"
}
```

After writing the file, add `q1_trigger_sha256` using the digest returned by:

```bash
sha256sum plans/260728-mergecert-q1/q1-trigger.json
```

Then skip Steps 2-7 and continue to Step 8.

- [ ] **Step 2: Confirm remaining budget before conditional launch**

Obtain current Q1 billing actuals. Run conditional work only if projected total
remains at or below `$45`; otherwise stop and report the budget ceiling.

- [ ] **Step 3: Run and validate the Q2 pilot**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run \
  modal-runners/modal-mergecert-q2-capture.py::q2_pilot \
  --run-tag q1-triggered --limit 16
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run \
  modal-runners/modal-mergecert-q2-capture.py::validate_pilot
```

Require both ratios, all registered capture tensors, finite values, binary
labels, locator evidence, and exact trigger provenance.

- [ ] **Step 4: Launch the eight-slice Q2 fleet**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run --detach \
  modal-runners/modal-mergecert-q2-capture.py::fleet
```

Monitor every spawned app/task. After all slices finish:

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run \
  modal-runners/modal-mergecert-q2-capture.py::freeze_capture_summary
```

- [ ] **Step 5: Run registered Q2 probes**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run \
  modal-runners/modal-mergecert-q2-probes.py::complete_fact_types
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run --detach \
  modal-runners/modal-mergecert-q2-probes.py::run_probes
```

Retrieve capture summary, routability JSON, and scores NPZ. Verify their hashes
and run `analyze-mergecert-q2.py`.

- [ ] **Step 6: Compute Q3 locally**

Copy `/preprobe/e1-relabel-A2.state.json`,
`/preprobe/e1-relabel-B.state.json`,
`/preprobe/e1-relabel-FR.state.json`, and
`/preprobe/e1-relabel-E1F.state.json` from `memsub-artifacts` into
`/tmp/mergecert-q1-q3-references`, verify their hashes, then run:

```bash
./.venv/bin/python plans/260727-mergecert/analyze-mergecert-q3.py \
  --scores plans/260728-mergecert-q1/q2-scores.npz \
  --q2-results plans/260728-mergecert-q1/q2-routability-remote.json \
  --reference-dir /tmp/mergecert-q1-q3-references \
  --output plans/260728-mergecert-q1/q3-fragility.json
```

- [ ] **Step 7: Write the completed conditional record**

Record `status: completed`, Q1 trigger hash, Q2/Q3 artifact hashes, Modal app
IDs, item counts, and output paths in `conditional-work.json`.

- [ ] **Step 8: Commit conditional evidence or skip**

```bash
git add plans/260728-mergecert-q1/conditional-work.json \
  plans/260728-mergecert-q1/q2-* \
  plans/260728-mergecert-q1/q3-fragility.json
git commit -m "docs: record MergeCert conditional placement work"
```

When skipped, stage only `conditional-work.json`; do not pass unmatched globs.

---

### Task 8: Billing, final report, and completion audit

**Files:**
- Create: `plans/260728-mergecert-q1/compute-actuals.json`
- Create: `MERGECERT-Q1-REPORT.md`
- Create: `plans/260728-mergecert-q1/artifact-manifest.json`
- Modify: `docs/superpowers/plans/2026-07-28-mergecert-q1-completion.md`

**Interfaces:**
- Consumes: all immutable experiment evidence and Modal billing report.
- Produces: validated private report and final clean local commit.

- [ ] **Step 1: Retrieve exact billing records**

Use Modal's billing report for the exact campaign interval. Record per-resource
charges, total cost, app IDs, created/stopped times, purpose, state, and task
count. Compute no cost from wall time when an exact billing row is available.

- [ ] **Step 2: Stop and audit every campaign app**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal app list --json
```

Expected: no live campaign app and zero tasks for every recorded run.

- [ ] **Step 3: Render and validate the report**

```bash
./.venv/bin/python plans/260728-mergecert-q1/render-report.py
./.venv/bin/python plans/260728-mergecert-q1/validate-report.py
```

Expected: validation pass, branch equal to `conditional-complete` or
`conditional-skip`, total cost no greater than `$45`, and complete file hashes.

- [ ] **Step 4: Run the complete verification suite**

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  ./.venv/bin/python -m pytest tests -q
git diff --check
git status --short
```

Expected: zero failures and only the intentionally preserved parent-report
modification plus final campaign files staged for commit.

- [ ] **Step 5: Audit every `MERGECERT-Q1.md` requirement**

Check and record evidence for:

- no 0.90 rerun;
- 20-context full M1 Q1 at both ratios;
- exact control/reference/merge/eviction rows;
- paired CIs on both axes and both ratios;
- per-domain slices;
- R1/R2/R3 verbatim plus measured verdicts;
- conditional Q2/Q3 completion or registered skip;
- README and §13.7 sections;
- billing-ID provenance;
- private/no-publication state;
- total spend at or below `$45`;
- stopped external jobs.

- [ ] **Step 6: Commit the final private bundle**

```bash
git add MERGECERT-Q1-REPORT.md \
  plans/260728-mergecert-q1/compute-actuals.json \
  plans/260728-mergecert-q1/artifact-manifest.json \
  docs/superpowers/plans/2026-07-28-mergecert-q1-completion.md
git commit -m "docs: complete MergeCert Q1 placement"
```

Do not stage or rewrite `MERGECERT-REPORT.md`. Do not push or publish.
