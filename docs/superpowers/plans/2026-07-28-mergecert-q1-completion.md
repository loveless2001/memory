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

- [x] **Step 1a: Extract, review, and bind the finalized Q1 registration**

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
binding commit before any upload or smoke retry.

Completed on 2026-07-29 by the reviewed CPU-only, read-only Modal app
`ap-Bx0LRrGGZ0yUchiepNVrtV`. The canonical 20,240-byte output is bound at
SHA-256
`6d90677469c5548d0fde863db886e7a6665e25f15c23d351ba07a0ad4db6e2d5`;
the app stopped with zero tasks after a 60-second lifetime. The extraction
and cost-estimate record is
`plans/260728-mergecert-q1/q1-registration-extraction.json`. No upload or
smoke was performed as part of Step 1a.

- [x] **Step 1b: Upload and remotely verify all reviewed Q1 inputs**

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
set -euo pipefail
q1_review_dir="$(mktemp -d /tmp/mergecert-q1-reviewed-remote.XXXXXX)"
trap 'rm -rf -- "$q1_review_dir"' EXIT
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume get \
  memsub-artifacts /mergecert-q1/q1-registration.json \
  "$q1_review_dir/q1-registration.json" --force
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume get \
  memsub-artifacts /mergecert-q1/MERGECERT-Q1.md \
  "$q1_review_dir/MERGECERT-Q1.md" --force
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume get \
  memsub-artifacts /mergecert-q1/p0-verdict.json \
  "$q1_review_dir/p0-verdict.json" --force
cmp plans/260728-mergecert-q1/q1-registration.json \
  "$q1_review_dir/q1-registration.json"
cmp MERGECERT-Q1.md \
  "$q1_review_dir/MERGECERT-Q1.md"
cmp plans/260727-mergecert/p0-verdict.json \
  "$q1_review_dir/p0-verdict.json"
sha256sum "$q1_review_dir/q1-registration.json" \
  "$q1_review_dir/MERGECERT-Q1.md" \
  "$q1_review_dir/p0-verdict.json"
```

The remote registration SHA-256 must equal the exact literal
`Q1_REGISTRATION_SHA256` recorded by Step 1a. The remote authorization hashes
must be exactly
`35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509`
and
`4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a`.
Record this verification before Step 2. Completed on 2026-07-29: all three
remote files were retrieved into a unique temporary directory, matched the
reviewed local bytes with `cmp`, and had the three exact SHA-256 values above.

- [x] **Step 2: Launch the two-document smoke**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run \
  modal-runners/modal-mergecert-p0-q1.py::q1_addendum_smoke
```

Copy `/mergecert-q1/q1-smoke.json` locally, then run the analyzer with
`--expected-documents 2 --n-resamples 2000`. Verify five arms, two documents,
identical partitions, exact zero control, archive replay, finite attention,
and per-document merge/eviction physical-budget equality. For 4096-token
documents, verify budgets `{0.25: 3072, 0.40: 2458}`. The one authorized
retry launched as app `ap-amdd5k9Ybxoxv1d8c3vbon` but failed during
container hydration, before user code or artifact creation, with
`ModuleNotFoundError: No module named 'memsub'`.

- [x] **Step 3: Stop on any smoke defect**

If any check fails, stop all Modal apps, diagnose under
`superpowers:systematic-debugging`, add a failing regression test, fix locally,
and rerun the smoke within the approved `$15` bound. Never launch full Q1 from
an invalid smoke. The failed app was stopped with zero tasks. Under the
one-retry execution instruction, no duplicate smoke was launched and full Q1
remains blocked. The immutable attempt record is
`plans/260728-mergecert-q1/q1-smoke-attempt.json`.

After independent review of the packaging repair at `a2f8293`, one authorized
smoke retry launched as app `ap-FS1Y8Y3bcazBqzMybadmyo`. Packaging and
hydration passed, all three model shards loaded, and execution reached the
registered archive replay gate. It then failed for `financial/00000`,
`eviction-0.25`: `aggregation_axis.mean_kl` was `0.068229`, versus the
registered `0.063958`. The app stopped with zero tasks. No smoke artifact was
accepted or retrieved, no analyzer ran, and full Q1 remains blocked. The
immutable retry record is
`plans/260728-mergecert-q1/q1-smoke-retry.json`.

After independent review of the replay-semantics and strict-fingerprint
repairs through `e83e0f2`, the directly authorized two-document diagnostic
launched as app `ap-f53tWxXjsQH95pN0uZzxQx` and completed both registered
financial documents. The copied artifact is
`plans/260728-mergecert-q1/q1-smoke.json` at SHA-256
`c3949b641e4ad0ed00596ec38194bed7a46084c58667750afb94bb7682e75564`.
Independent local analysis with `--expected-documents 2 --n-resamples 2000`
passed: all six auxiliary archive rows replayed with zero recorded
mismatches; all five reported arms used identical partitions; control was
exact zero; attention was finite and nondegenerate; and both documents had
matched eviction/merge retained counts of 3,072 at 0.25 and 2,458 at 0.40.
The separate smoke verdict and table are
`plans/260728-mergecert-q1/q1-smoke-verdict.json` and
`plans/260728-mergecert-q1/q1-smoke-table.md`.
The tracked operational record is
`plans/260728-mergecert-q1/q1-smoke-success.json`: the terminal inventory
shows the app stopped with zero tasks at 14:20:03 +07:00 after a 60-second
lifetime. At the official Modal rates checked on 2026-07-29, charging the
whole lifetime at one H100, one physical core, and 64 GiB gives a conservative
`$0.0751308` smoke estimate. Applying the same rates to the extractor and all
four recorded smoke attempts gives a transparent cumulative conservative
estimate of `$0.26981812`, not an exact billing actual.

The smoke preview had no favorable intervals and `run_q2_q3=false`, but it is
not a registered campaign decision: the analyzer intentionally writes a
trigger only for `--expected-documents 20`. Therefore no smoke trigger was
created or copied, and no full Q1, Q2, or Q3 action is authorized by this
evidence. Full Q1 remains pending a separate controller decision and
independent review of this smoke-evidence commit.

- [x] **Step 4: Launch full Q1 detached only after a valid smoke**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run --detach \
  modal-runners/modal-mergecert-p0-q1.py::q1_addendum_certify
```

Record the app ID, inspect logs, and poll `modal app list --json` until stopped.
Do not start another full app while the registered output is resumable.
Completed as app `ap-bnyT0P9ay00aSaBC0u4gyc`: all 20 documents completed,
and the terminal inventory showed state `stopped`, zero tasks, and a
153-second lifetime from 14:54:12 to 14:56:45 +07:00. The tracked operations
record is `plans/260728-mergecert-q1/q1-certification-run.json`.

- [x] **Step 5: Retrieve and independently analyze full Q1**

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
Passed locally with the exact 20 registered documents, five in each domain,
five arms, 60/60 auxiliary replay rows with zero recorded mismatches, exact
authorization/registration/fingerprint/execution semantics, common
partitions and full-prediction baselines, zero-change control, finite
nondegenerate attention, matched per-document physical budgets, complete
paired CIs, and all four domain slices. The deterministic registered result is
`R1` / `aggregation-negative`, with favorable interval
`0.40:lost_prior` and `run_q2_q3=true`.

- [x] **Step 6: Copy the trigger to the private volume**

Only if `run_q2_q3` is true:

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal volume put \
  memsub-artifacts plans/260728-mergecert-q1/q1-trigger.json \
  /mergecert-q1/q1-trigger.json
```

Completed after controller review at runner commit `307e764`: the exact
433-byte trigger was uploaded to `/mergecert-q1/q1-trigger.json`, retrieved
again, and compared byte-for-byte with the tracked source. Both copies have
SHA-256
`009d1ba2879b76174c13dffbea27a458b10d9a859cdb69046f3afac31a2af5a1`.
This upload authorized only the separately approved registered pilot; it did
not launch the Q2 fleet or Q3.

- [x] **Step 7: Commit Q1 evidence**

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
- Conditional create: `plans/260728-mergecert-q1/q2-pilot-run.json`
- Conditional create: `plans/260728-mergecert-q1/q2-pilot-state.json`
- Conditional create: `plans/260728-mergecert-q1/q2-pilot-verdict.json`
- Conditional create: `plans/260728-mergecert-q1/q2-fleet-attempt.json`
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

- [x] **Step 2: Confirm remaining budget before conditional launch**

Obtain current Q1 billing actuals. Run conditional work only if projected total
remains at or below `$45`; otherwise stop and report the budget ceiling.

Confirmed before the bounded trigger/pilot phase. Exact billing after the
pilot is `$0.42725261`, consisting of `$0.32849690` before the pilot plus
pilot rows of H100 `$0.08681040`, memory `$0.01125239`, and CPU
`$0.00069292` (`$0.09875571` pilot total). This leaves `$44.57274739`
under the `$45` ceiling. These are billing actuals, not lifetime estimates.

- [x] **Step 3: Run and validate the Q2 pilot**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run \
  modal-runners/modal-mergecert-q2-capture.py::q2_pilot \
  --run-tag q1-triggered --limit 16
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run \
  modal-runners/modal-mergecert-q2-capture.py::validate_pilot
```

Require both ratios, all registered capture tensors, finite values, binary
labels, locator evidence, and exact trigger provenance.

The conditional interface uses the isolated `pilot-q1-triggered` namespace.
One invocation writes separate 0.25 and 0.40 NPZ artifacts from the same
registered 16 items. `validate_pilot` independently verifies the live trigger
and hash, sorted-manifest provenance and item order, state/chunk/file hashes,
registered document/domain/raw-label/correctness/E1 fields, recomputed
`eq_policy_v1` labels, the pinned runtime fingerprint, exact namespace, and
the complete capture schema for both ratios. Only then does it write the
canonical private verdict at
`/artifacts/mergecert/q2/pilot-q1-triggered/pilot-verdict.json`. That verdict
binds validator version `mergecert-q2-pilot-validator-v2`, mode and tag, the
exact Q1 trigger payload/hash, manifest path/hash, state path/hash, both ratio
artifact paths/hashes/audits, and compatibility fingerprint. The older
`pilot-a` / `pilot-b` namespaces remain available as a legacy repeated-run
bit-identity check, but they cannot authorize the conditional fleet.

Completed at reviewed runner commit `307e764`. Pilot app
`ap-Oxquib97yXgc1yG3xQ5UpQ` captured all 16 registered items and stopped with
zero tasks after 110 seconds. Validator app
`ap-vl15qY3btFGWZEFMILacJU` wrote the canonical verdict and stopped with zero
tasks after 25 seconds. The remote namespace contains exactly the verdict,
state, and one NPZ for each registered ratio.

All four namespace files, the bound 30,847-row source manifest, and the exact
remote trigger were retrieved read-only into an isolated local directory.
Independent local validation passed exact hashes, schemas, item/document/domain
and raw-label bindings, recomputed `y`, binary fields, both complete finite
tensor sets, locator evidence (`10/16` for each ratio), state/chunk coverage,
the pinned compatibility fingerprint, and the canonical verdict bytes. The
tracked evidence is `q2-pilot-run.json`, `q2-pilot-state.json`, and
`q2-pilot-verdict.json`. The raw ratio tensors remain on the private volume;
their exact hashes and audited schemas are recorded in the run evidence. The
fleet and probes were not launched.

- [x] **Step 4: Launch the eight-slice Q2 fleet — stopped on defect**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run --detach \
  modal-runners/modal-mergecert-q2-capture.py::fleet
```

Before spawning, `fleet` must validate that exact current canonical verdict
through a private CPU gate. Every `q2_capture_slice` must independently
revalidate the same verdict before capture and bind its hash plus live runtime
fingerprint into new or resumed slice state. Missing, failed, legacy, stale,
tampered, or namespace-drifted pilot evidence blocks all slice launches.

Monitor every spawned app/task. After all slices finish:

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run \
  modal-runners/modal-mergecert-q2-capture.py::freeze_capture_summary
```

One fleet app, `ap-94yLmlHzYzxS6y44wZocc8`, spawned the registered eight
slices from local launch entrypoint `fleet` and showed nine tasks. The remote
slice function was `q2_capture_slice`, function ID
`fu-SN6sadtSpowHTq1pdAgS8j`; that ID does not identify the local entrypoint.
Logs then reported registered items failing with
`ValueError: short Q2 context`, including
`mcq_code/00130_1230_28`, `mcq_code/00130_204_27`, and
`mcq_code/00130_239_29`. The app was stopped immediately and terminal
inventory showed `stopped` with zero tasks at 18:20:59 +07:00 after a
136-second lifetime. No duplicate fleet, freeze, probe, or Q3 action ran.

Exact fleet billing was H100 `$0.95836057`, memory `$0.12440516`, and CPU
`$0.00862954`, totaling `$1.09139527`; delayed validator billing was
`$0.00139660`. Exact campaign actual is now `$1.52004448`. The immutable
attempt record is `plans/260728-mergecert-q1/q2-fleet-attempt.json`.
Read-only namespace and state audit found one committed 100-row chunk in each
of slices 00, 01, 06, and 07; slices 02, 03, 04, and 05 were empty. Every
audited state binds the canonical pilot-verdict hash. The raw partial NPZs
were not downloaded, and no partial output is accepted as a campaign result.

The exception is a latent contradiction in the original registration, not
recent code drift. Commit `e6f5496` introduced both fixed `CTX = 4096` and
the short-context exception, while the standard-manifest builder filtered
only on a 24,000-character heuristic and never verified document length with
the pinned tokenizer. The Q1 variable-length amendment is scoped to Q1 and
does not authorize changing the parent's unchanged Q2 fixed-context mechanics
or budgets.

The registered 16-row pilot missed the defect because it covered sorted rows
0–15 from nine early code documents; the first observed short document,
`code/00130`, occurs at global rows 130–132. A controller-capped local scan
with the exact registered tokenizer completed only the code domain and proved
two short documents (`code/00130`: 4,073 tokens; `code/05272`: 4,067 tokens)
affecting seven registered items. This is a whole-manifest lower bound, not a
total; financial, legal, and literature were not scanned, and the scan or
downloads must not be restarted.

Three scientifically honest dispositions are recorded:

1. **Stop and report (initially recommended):** make no Q2 routability or Q3 fragility
   claim. This changes no registered population, context, budget, or Q2
   semantics.
2. **Version a variable-length Q2 amendment:** preserve all 30,847 rows, but
   change fixed-4096 mechanics/budgets. Any future result would be an amended
   mixed-length Q2 claim and requires fresh review, validation, pilot, and
   authorization.
3. **Re-register a tokenizer-filtered full-length population:** preserve
   fixed-4096 mechanics/budgets, but change the sampled population and all
   dependent hashes/pilot evidence. Any claim would apply only to that
   filtered population.

Padding, runtime skipping, replacement, or silent budget variation are not
valid alternatives. At this point in the record, no protocol amendment had
been implemented.

- [x] **Step 5: Do not run registered Q2 probes after the stopped fleet**

```bash
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run \
  modal-runners/modal-mergecert-q2-probes.py::complete_fact_types
UV_CACHE_DIR=/tmp/mergecert-uv-cache uv run modal run --detach \
  modal-runners/modal-mergecert-q2-probes.py::run_probes
```

Retrieve capture summary, routability JSON, and scores NPZ. Verify their hashes
and run `analyze-mergecert-q2.py`.

Not run. The stopped fleet produced no capture summary, and the recommended
least claim-changing disposition ends Q2/Q3 without a routability result.

- [x] **Step 6: Do not compute Q3 without registered Q2 evidence**

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

Not run. The registered Q3 inputs do not exist, so no fragility result is
claimed.

- [x] **Step 7: Write the immutable failed-conditional record**

Record `status: completed`, Q1 trigger hash, Q2/Q3 artifact hashes, Modal app
IDs, item counts, and output paths in `conditional-work.json`.

The conditional phase did not complete and was not a trigger-based skip.
Instead, `q2-fleet-attempt.json` records the exact third terminal state:
stopped on a registered-protocol contradiction. It binds the app/log items,
terminal inventory, partial-state audit, exact billing, local diagnostic
scope, decision options, and the recommended stop-and-report disposition.
No Q2 or Q3 result is recorded.

- [x] **Step 8: Commit the failed-fleet evidence and protocol decision**

```bash
git add plans/260728-mergecert-q1/q2-fleet-attempt.json \
  tests/test_mergecert_campaign_contract.py \
  docs/superpowers/plans/2026-07-28-mergecert-q1-completion.md
git commit -m "docs: record stopped MergeCert Q2 fleet"
```

No unmatched globs, partial raw outputs, or unregistered result files are
staged.

---

### Task 7 amendment: selected variable-context Q2 rerun

Option 2 is selected and settled by the dated 2026-07-29 amendment
`plans/260728-mergecert-q1/q2-amendment.json`, SHA-256
`7b510a5b0af827516894fe806281cfa877e2234135dccc297c8d8bd823a87b0a`.
The amended protocol is `mergecert-q2-amended-v2`: it retains the original
30,847-item standard manifest and uses per-item actual-context matched physical
budgets. This is an amended variable-context Q2/Q3 result, not a result under
the failed fixed-context protocol.

`plans/260728-mergecert-q1/q2-fleet-attempt.json` remains immutable failed
fixed-context evidence. It does not authorize amendment-state reuse, a result
claim, a fleet retry, probes, or Q3.

- [ ] **Step A: Run one new amended-v2 pilot only after fresh authorization**

The pilot path is
`/artifacts/mergecert/q2-amended-v2/pilot-amended-v2/`. Run exactly 16
registered items, even if the selected rows happen to be long-context rows;
the amendment's accounting and provenance checks, rather than row length,
define the pilot. Validate and review the new canonical pilot verdict at
`/artifacts/mergecert/q2-amended-v2/pilot-amended-v2/pilot-verdict.json`
before authorizing any fleet work.

- [ ] **Step B: Run one new amended-v2 fleet only after pilot-verdict review and fresh authorization**

Run one eight-slice fleet, retaining exactly 30,847 items per registered ratio,
under these amended-v2 paths:

- `/artifacts/mergecert/q2-amended-v2/full-amended-v2-slice-00/`
- `/artifacts/mergecert/q2-amended-v2/full-amended-v2-slice-01/`
- `/artifacts/mergecert/q2-amended-v2/full-amended-v2-slice-02/`
- `/artifacts/mergecert/q2-amended-v2/full-amended-v2-slice-03/`
- `/artifacts/mergecert/q2-amended-v2/full-amended-v2-slice-04/`
- `/artifacts/mergecert/q2-amended-v2/full-amended-v2-slice-05/`
- `/artifacts/mergecert/q2-amended-v2/full-amended-v2-slice-06/`
- `/artifacts/mergecert/q2-amended-v2/full-amended-v2-slice-07/`

No remote action occurred while implementing this amendment/report provenance
binding. The pilot, fleet, capture summary, probes, and Q3 remain pending their
separate authorization gates.

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
