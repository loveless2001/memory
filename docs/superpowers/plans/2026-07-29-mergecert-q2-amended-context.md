# MergeCert Q2 Amended Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the selected Q2 variable-context amendment locally while
preserving the exact 30,847-item manifest, exact registered ratios, unchanged
long-context mechanics, and a fail-closed amendment hash chain through Q3 and
the private final report.

**Architecture:** A shared `memsub.certification` module owns the canonical
amendment, context-window, physical-budget, and per-item accounting
validators. The capture runner alone measures cache mutation on an independent
eviction clone; capture, probes, Q2 analysis, Q3, and reporting all validate
the same versioned accounting and amendment payload/hash. New evidence uses
only `/artifacts/mergecert/q2-amended-v2`; old fixed-context evidence remains
immutable and cannot authorize or resume amended work.

**Tech Stack:** Python 3.12, NumPy, PyTorch 2.7.1, Transformers 4.55.2,
Modal, pytest, canonical JSON, SHA-256.

## Global Constraints

- Work locally only. Do not run Modal, upload files, mutate volumes, launch a
  pilot/fleet/probe, or perform any other remote action.
- Preserve the exact 30,847 registered manifest items, item IDs, ordering
  rule, selection, fields, labels, ratios `{0.25, 0.40}`, model, tokenizer,
  four sink tokens, and Q1 trigger.
- Preserve exact 4,096-token Q2 behavior: targets `3,072` and `2,458`, recent
  starts `2,562` and `2,869`, and the complete existing merge block layouts.
- Use the exact registered ratio in
  `build_merge_plan(actual_context_length, ratio, sink_token_count=4)`. Do not
  synthesize an effective fraction.
- A window is admissible only when, for every registered ratio,
  `target_retained = n - floor(n * ratio)` and
  `target_retained - 4 >= 2`. The combined protocol rejects `n=8` because
  ratio 0.40 fails and accepts `n=9` for both ratios.
- Measure eviction on `full_cache.clone_detached()`. The untouched
  `full_cache` and real attention mass are the inputs to `merge_cache`.
- Do not pad, skip, replace, filter, relabel, delete, resume old evidence, or
  weaken validation.
- `plans/260728-mergecert-q1/q2-amendment.json` is the sole new Q2 protocol
  authority. `q1-trigger.json` remains required but is not the amendment.
- The existing trigger must remain byte-identical at SHA-256
  `009d1ba2879b76174c13dffbea27a458b10d9a859cdb69046f3afac31a2af5a1`.
- The next possible remote sequence, under separate fresh authorization, is
  one new 16-item amended pilot, review of its passing verdict, then at most
  one new eight-slice fleet over exactly 30,847 items.

---

### Task 1: Settled amendment artifact and shared accounting contract

**Files:**
- Create: `plans/260728-mergecert-q1/q2-amendment.json`
- Create: `memsub/certification/mergecert_q2_context.py`
- Modify: `memsub/certification/__init__.py`
- Create: `tests/test_mergecert_q2_amendment.py`

**Interfaces:**
- Consumes: registered ratios `(0.25, 0.40)`, reference context `4096`, sinks
  `4`, manifest row fields `item_id` and `chunk_rel_start`.
- Produces:
  - `load_q2_amendment(path: str | Path, expected_sha256: str | None) -> dict`
  - `derive_q2_context_window(document_tokens: int, chunk_token_start: int, chunk_rel_start: int) -> dict`
  - `validate_q2_context_length(context_tokens: int) -> None`
  - `expected_q2_plan_fields(context_tokens: int, ratio: float) -> dict`
  - `validate_q2_accounting_row(row: dict, manifest_row: dict | None = None, expected_ratio: float | None = None) -> dict`
  - `validate_q2_accounting_arrays(arrays: dict, expected_rows: list[dict], expected_ratio: float) -> dict`
  - `q2_accounting_sha256(rows: list[dict]) -> str`
  - constants `Q2_PROTOCOL_VERSION`, `Q2_CONTEXT_MECHANICS_VERSION`,
    `Q2_NAMESPACE_VERSION`, `Q2_AMENDMENT_SCHEMA`,
    `Q2_ACCOUNTING_INTEGER_FIELDS`, and `Q2_ACCOUNTING_ARRAY_FIELDS`.

- [ ] **Step 1: Write RED amendment and accounting tests**

Add literal tests that name each break:

```python
PROVEN_SHORT_ITEMS = (
    "mcq_code/00130_1230_28",
    "mcq_code/00130_204_27",
    "mcq_code/00130_239_29",
)


def test_q2_window_preserves_long_reference_and_proven_short_items():
    long = derive_q2_context_window(6000, 3000, 1024)
    assert long == {
        "source_document_token_count": 6000,
        "source_context_start": 1904,
        "source_context_end": 6000,
        "source_context_token_count": 4096,
        "model_input_token_count": 4096,
        "source_chunk_token_start": 3000,
        "source_chunk_context_start": 1096,
    }
    for item_id in PROVEN_SHORT_ITEMS:
        chunk = int(item_id.split("_")[-2])
        short = derive_q2_context_window(4073, chunk, 0)
        assert short["source_context_start"] == 0
        assert short["source_context_end"] == 4073
        assert short["source_context_token_count"] == 4073
        assert short["source_chunk_token_start"] == chunk


def test_q2_protocol_rejects_eight_tokens_and_accepts_nine():
    with pytest.raises(ValueError, match="retained"):
        validate_q2_context_length(8)
    validate_q2_context_length(9)


@pytest.mark.parametrize(
    ("ratio", "retained", "recent_start"),
    ((0.25, 3072, 2562), (0.40, 2458, 2869)),
)
def test_q2_long_context_plan_fields_are_unchanged(
    ratio, retained, recent_start
):
    fields = expected_q2_plan_fields(4096, ratio)
    old = build_merge_plan(4096, ratio, sink_token_count=4)
    assert fields["merge_target_retained"] == retained
    assert fields["merge_recent_start"] == recent_start
    assert old.target_retained == retained
    assert old.recent_start == recent_start
```

Build literal valid 4,096- and 4,073-token accounting rows. Parametrize
mutations for boolean integers, shifted context start/end, shifted eviction
start/end, wrong requested count, physical-before/after/removed mismatch,
wrong retained count, wrong merge target, wrong recent start, unregistered
ratio, wrong mechanics version, and a manifest item/anchor mismatch. Each
mutation must raise a field-specific `ValueError`.

- [ ] **Step 2: Run RED tests**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_mergecert_q2_amendment.py
```

Expected: collection fails because `mergecert_q2_context` and its interfaces
do not exist.

- [ ] **Step 3: Write the exact settled amendment JSON**

Create this canonical payload without a self-hash:

```json
{
  "schema": "mergecert-q2-amendment-v1",
  "protocol": "MERGECERT-Q2",
  "protocol_version": "mergecert-q2-amended-v2",
  "settled_date": "2026-07-29",
  "status": "settled",
  "authority": "user-selected-option-2",
  "model_id": "Qwen/Qwen3-4B-Instruct-2507",
  "population": {
    "manifest_items": 30847,
    "selection": "unchanged-standard-30847-manifest",
    "item_ids_labels_and_order_rule_unchanged": true
  },
  "ratios": [
    0.25,
    0.4
  ],
  "sink_token_count": 4,
  "reference_context_tokens": 4096,
  "minimum_context_tokens": 9,
  "budget_mode": "per-item-actual-context-matched-physical-v2",
  "context_mechanics_version": "mergecert-q2-context-mechanics-v2",
  "namespace_version": "mergecert-q2-amended-v2",
  "remote_root": "/artifacts/mergecert/q2-amended-v2",
  "context_rule": "canonical registered source window capped at 4096 pinned-tokenizer tokens",
  "requested_eviction_rule": "floor(source_context_token_count * ratio) from logical position 4",
  "physical_budget_rule": "measure removal on an independent full-cache clone and give merge the measured retained count",
  "merge_plan_rule": "build_merge_plan(source_context_token_count, exact registered ratio, sink_token_count=4)",
  "legacy_fixed_context_evidence_authorizes": false,
  "forbidden": [
    "padding",
    "runtime-skip",
    "replacement",
    "population-filter",
    "label-change",
    "silent-budget-change",
    "legacy-state-resume"
  ],
  "rerun_gate": {
    "new_pilot_items": 16,
    "pilot_review_required_before_fleet": true,
    "new_fleet_slices": 8,
    "fleet_items": 30847,
    "fresh_authorization_required": true
  }
}
```

Write it with `indent=2`, UTF-8, and one trailing newline. Record its digest
with:

```bash
sha256sum plans/260728-mergecert-q1/q2-amendment.json
```

- [ ] **Step 4: Implement the shared pure validator**

Implement canonical JSON hashing, exact artifact schema/value validation,
strict non-boolean integer checks, deterministic window clamping, and the
per-ratio retained invariant. Use:

```python
plan = build_merge_plan(
    context_tokens, ratio, sink_token_count=Q2_SINK_TOKEN_COUNT
)
requested = int(context_tokens * ratio)
expected_target = context_tokens - requested
if (
    plan.target_retained != expected_target
    or plan.target_retained - Q2_SINK_TOKEN_COUNT < 2
):
    raise ValueError("Q2 context violates the amended retained budget")
```

`validate_q2_accounting_arrays` must reconstruct one row per item from the
explicit arrays, convert NumPy scalars with `.item()`, validate against the
corresponding registered manifest row, and return:

```python
{
    "schema": "mergecert-q2-accounting-audit-v1",
    "rows": len(expected_rows),
    "ratio": expected_ratio,
    "short_context_rows": count_below_4096,
    "minimum_context_tokens": minimum,
    "maximum_context_tokens": maximum,
    "accounting_sha256": q2_accounting_sha256(validated_rows),
}
```

The accounting hash must be canonical JSON over the ordered validated rows,
including item IDs and ratio. Export the interfaces through
`memsub/certification/__init__.py`.

- [ ] **Step 5: Run GREEN tests and existing capture-schema tests**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_mergecert_q2_amendment.py \
  tests/test_mergecert_q2_capture_schema.py
```

Expected: all pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add plans/260728-mergecert-q1/q2-amendment.json \
  memsub/certification/mergecert_q2_context.py \
  memsub/certification/__init__.py \
  tests/test_mergecert_q2_amendment.py
git commit -m "feat: define amended MergeCert Q2 accounting"
```

---

### Task 2: Capture mechanics, complete accounting arrays, and clone isolation

**Files:**
- Modify: `modal-runners/modal-mergecert-q2-capture.py`
- Modify: `tests/test_mergecert_campaign_contract.py`
- Modify: `tests/test_mergecert_q2_capture_schema.py`

**Interfaces:**
- Consumes: Task 1 amendment loader, window/accounting validators, accounting
  field constants and hash.
- Produces:
  - `_measure_q2_budget(full_cache, *, context_tokens: int, ratio: float) -> tuple[dict, MergePlan]`
  - amended `_stack_chunk` arrays with every accounting field;
  - amended `_validate_capture_arrays` audit containing
    `context_accounting`;
  - state schema `mergecert-q2-capture-state-v2`.

- [ ] **Step 1: Add RED long/short runtime-budget and clone tests**

Add a fake cache whose `clone_detached()` returns an independently mutable
copy and whose `evict_logical_range(start, end)` deletes that logical range.
Assert:

```python
accounting, plan = runner._measure_q2_budget(
    full_cache, context_tokens=4073, ratio=0.40
)
assert full_cache.physical_length == 4073
assert full_cache.logical_positions == list(range(4073))
assert accounting["requested_evicted_token_count"] == 1629
assert accounting["physical_removed_count"] == 1629
assert accounting["retained_token_count"] == 2444
assert plan.sequence_length == 4073
assert plan.eviction_fraction == 0.40
assert plan.target_retained == 2444
```

For 4,096 tokens assert requested/retained/recent-start values match Task 1
and compare the complete returned plan to
`build_merge_plan(4096, ratio, sink_token_count=4)`. Assert the fake clone
received the mutation while the original cache remained untouched.

Extend `_arrays()` in `test_mergecert_q2_capture_schema.py` with literal valid
accounting arrays. Mutate a short row to contain 4,096-token fixed mechanics
and expect rejection.

- [ ] **Step 2: Run RED capture tests**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_mergecert_campaign_contract.py \
  tests/test_mergecert_q2_capture_schema.py \
  -k "q2 and (budget or context or capture)"
```

Expected: failures for missing amended constants, helper, arrays, and strict
accounting validation.

- [ ] **Step 3: Version and hash-bind the capture runner**

Add exact constants for the Task 1 digest:

```python
Q2_PROTOCOL_VERSION = "mergecert-q2-amended-v2"
Q2_CONTEXT_MECHANICS_VERSION = "mergecert-q2-context-mechanics-v2"
Q2_NAMESPACE_VERSION = "mergecert-q2-amended-v2"
CAPTURE_STATE_SCHEMA = "mergecert-q2-capture-state-v2"
CAPTURE_CHUNK_SCHEMA = "mergecert-q2-capture-chunk-v2"
CAPTURE_ROOT = "/artifacts/mergecert/q2-amended-v2"
LEGACY_CAPTURE_ROOT = "/artifacts/mergecert/q2"
Q2_AMENDMENT_IMAGE_PATH = (
    "/root/repo/plans/260728-mergecert-q1/q2-amendment.json"
)
```

Copy the amendment into the image with `.add_local_file(...)`. At every
capture entry point, load it and require its exact literal SHA-256 before
reading or writing an amended namespace.

- [ ] **Step 4: Implement deterministic context and measured budget**

Replace the `len(context_ids) != CTX` exception with the Task 1 window helper:

```python
window = derive_q2_context_window(
    len(document_ids), chunk_absolute, row["chunk_rel_start"]
)
validate_q2_context_length(window["source_context_token_count"])
context_ids = document_ids[
    window["source_context_start"] : window["source_context_end"]
]
```

After real-attention prefill, `_measure_q2_budget` must:

1. assert `full_cache.physical_length == len(context_ids)`;
2. clone the cache;
3. evict `[4, 4 + floor(len(context_ids) * ratio))` from the clone;
4. measure before, after, and removed from the clone;
5. call `build_merge_plan(len(context_ids), ratio, sink_token_count=4)`;
6. validate the full accounting row and exact plan target/recent start;
7. return the accounting plus plan without mutating `full_cache`.

Pass the untouched `full_cache` to `merge_cache`.

- [ ] **Step 5: Record and validate complete accounting**

Add the Task 1 accounting fields as one aligned NumPy array per capture row.
Use integer dtype `np.int64`, ratio dtype `np.float64`, and string dtype for
the mechanics version. Add singleton arrays for:

```text
capture_chunk_schema
q2_protocol_version
q2_namespace_version
q2_amendment_json
q2_amendment_sha256
```

`_validate_capture_arrays` must require exact singleton provenance, call the
existing `validate_capture_chunk`, then call
`validate_q2_accounting_arrays`. Store its returned audit under
`audit["context_accounting"]`.

Add state fields for schema, protocol, namespace, context-mechanics version,
amendment payload/hash, and amendment image path. Keep file rows strict;
their stored audit now includes the accounting hash. Old state schemas and
old paths must fail before resume.

- [ ] **Step 6: Run GREEN capture tests**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_mergecert_q2_amendment.py \
  tests/test_mergecert_q2_capture_schema.py \
  tests/test_mergecert_campaign_contract.py \
  -k "q2"
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 2**

```bash
git add modal-runners/modal-mergecert-q2-capture.py \
  tests/test_mergecert_campaign_contract.py \
  tests/test_mergecert_q2_capture_schema.py
git commit -m "feat: capture amended Q2 context accounting"
```

---

### Task 3: Isolated amended pilot, state gate, and frozen summary

**Files:**
- Modify: `modal-runners/modal-mergecert-q2-capture.py`
- Modify: `tests/test_mergecert_campaign_contract.py`

**Interfaces:**
- Consumes: Task 2 state/chunk schemas and exact amendment binding.
- Produces:
  - pilot namespace `/artifacts/mergecert/q2-amended-v2/pilot-amended-v2`;
  - verdict schema `mergecert-q2-pilot-verdict-v3-amended`;
  - slice namespaces `full-amended-v2-slice-00` through `-07`;
  - summary schema `mergecert-q2-capture-summary-v2`.

- [ ] **Step 1: Add RED namespace and authorization regressions**

Tests must assert:

- `REGISTERED_PILOT_TAG == "amended-v2"`;
- the registered pilot directory is under the amended root;
- old `pilot-q1-triggered`, `pilot-a`, `pilot-b`, and
  `/artifacts/mergecert/q2/pilot-verdict.json` cannot validate;
- an old v2 validator verdict cannot pass `_require_registered_pilot_verdict`;
- an old state without the amendment/schema fields cannot resume;
- a state with the right amendment payload but wrong hash cannot resume;
- `q2_capture_slice` outputs only `full-amended-v2-slice-{idx:02d}`;
- `fleet` validates the amended verdict before all eight spawns;
- the pilot still requires exactly 16 items even if those rows are long;
- freeze rejects a slice with shifted accounting audit/hash, wrong namespace,
  wrong amendment hash, or incomplete/duplicate item coverage.

- [ ] **Step 2: Run RED gate tests**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_mergecert_campaign_contract.py \
  -k "q2 and (pilot or namespace or fleet or freeze or state)"
```

Expected: failures because the runner still accepts legacy tags/paths and the
summary does not bind amended accounting.

- [ ] **Step 3: Remove legacy authorization and isolate all paths**

Keep legacy path constants only for explicit incompatibility tests and
evidence wording. Delete the repeated `a`/`b` validator fallback from the
amended authorization path. `q2_pilot` accepts only
`--run-tag amended-v2 --limit 16`. Existing old files are never listed,
opened, removed, or overwritten by amended entry points.

Change the Modal app name to `memsub-mergecert-q2-amended-v2-capture`.
Keep function names stable for future commands, but every output path must be
under the amended root.

- [ ] **Step 4: Bind the amended verdict and slice state**

The canonical pilot verdict must include exact:

```text
schema
protocol
protocol_version
namespace_version
context_mechanics_version
validator_version
q2_amendment
q2_amendment_sha256
q1_trigger
q1_trigger_sha256
source_manifest path/hash
state path/hash
ratio artifact paths/hashes/audits
compatibility fingerprint
items=16
ratios=[0.25,0.40]
pass=true
```

Every slice independently reconstructs that canonical verdict, compares exact
bytes, then stores its verdict SHA-256 in state.

- [ ] **Step 5: Freeze through full state validation**

For each slice, call `_validate_capture_state` with the exact amendment,
amended pilot verdict hash, registered rows, expected fingerprint, and amended
namespace. Do not trust state fields directly.

The frozen summary must include the summary schema and all protocol,
namespace, amendment, trigger, manifest, pilot-verdict, item-count, chunk,
and accounting-audit bindings. Require exactly 30,847 unique IDs per ratio and
the same ID set at both ratios.

- [ ] **Step 6: Run GREEN gate tests**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_mergecert_campaign_contract.py \
  -k "q2"
```

Expected: all Q2 contract tests pass.

- [ ] **Step 7: Commit Task 3**

```bash
git add modal-runners/modal-mergecert-q2-capture.py \
  tests/test_mergecert_campaign_contract.py
git commit -m "fix: isolate amended Q2 evidence gates"
```

---

### Task 4: Probe validation, variable mechanics, and score propagation

**Files:**
- Modify: `modal-runners/modal-mergecert-q2-probes.py`
- Modify: `tests/test_mergecert_campaign_contract.py`
- Create: `tests/test_mergecert_q2_probe_contract.py`

**Interfaces:**
- Consumes: amended summary/chunks and Task 1 shared validators.
- Produces:
  - amended fact-types state under the amended root;
  - routability schema `mergecert-q2-routability-v2`;
  - score schema `mergecert-q2-scores-v2`;
  - flattened complete accounting arrays for both ratios.

- [ ] **Step 1: Add RED probe gate and mechanics tests**

Build local temporary summary/chunk fixtures with one 4,096 row and the three
proven 4,073-token `code/00130` IDs. Assert `_require_gate_and_capture`
rejects old paths, missing amendment data, amendment hash drift, wrong summary
schema, wrong namespace, wrong context-mechanics version, and wrong trigger.

Test a pure assembly helper with a valid short row, then mutate:

- context start/end;
- physical removed;
- merge target;
- merge recent start;
- item ID;
- accounting hash.

Each must fail before a probe fit. Assert the C0 distance is exactly:

```python
merge_recent_start - (source_chunk_context_start + 1024)
```

and differs from the old fixed-4,096 expression for a short row.

- [ ] **Step 2: Run RED probe tests**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_mergecert_q2_probe_contract.py \
  tests/test_mergecert_campaign_contract.py \
  -k "q2 and probe"
```

Expected: failures for old paths, missing amendment validation, and the
fixed-4,096 distance expression.

- [ ] **Step 3: Version probe paths and gate**

Use:

```text
CAPTURE_SUMMARY=/artifacts/mergecert/q2-amended-v2/capture-summary.json
ROUTABILITY_OUTPUT=/artifacts/mergecert/q2-amended-v2/routability.json
SCORES_OUTPUT=/artifacts/mergecert/q2-amended-v2/scores.npz
FACT_TYPES_COMPLETE=/artifacts/mergecert/q2-amended-v2/fact-types-complete.json
```

Change the app name to `memsub-mergecert-q2-amended-v2-probes`, use
`.add_local_python_source("memsub")`, copy the amendment artifact into the
image, and require its exact literal hash. `_require_gate_and_capture` must
validate the complete amended summary contract, not just `pass` and trigger.

Bind amendment payload/hash into completed fact-types state so old fact-type
state cannot resume into amended probes.

- [ ] **Step 4: Validate chunks and propagate accounting**

Before assembly, verify every chunk file hash and call both
`validate_capture_chunk` and `validate_q2_accounting_arrays` against the
manifest rows for that exact chunk. Compare the returned accounting audit to
the frozen summary.

Allocate one vector per Task 1 accounting field in each ratio target, fill it
by manifest index, and require full seen coverage. Replace:

```python
recent_start = 4096 - ((4096 - int(4096 * ratio) - 4) // 2)
```

with the validated per-item `merge_recent_start` vector, and use captured
`source_chunk_context_start`.

Flatten every accounting vector into score NPZ order. Add singleton score
arrays for score schema, amendment JSON/hash, protocol version, namespace
version, context-mechanics version, capture-summary hash, and accounting audit
hash.

- [ ] **Step 5: Bind routability output**

Routability JSON must include schema, exact amendment payload/hash, protocol,
namespace, context-mechanics version, trigger/hash, summary hash, manifest
hash, score schema/hash after write, full accounting audit, ratio results, and
pooled results.

- [ ] **Step 6: Run GREEN probe tests**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_mergecert_q2_probe_contract.py \
  tests/test_mergecert_campaign_contract.py \
  -k "q2"
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 4**

```bash
git add modal-runners/modal-mergecert-q2-probes.py \
  tests/test_mergecert_q2_probe_contract.py \
  tests/test_mergecert_campaign_contract.py
git commit -m "feat: validate amended Q2 probe inputs"
```

---

### Task 5: Local Q2 analyzer amendment and accounting gate

**Files:**
- Modify: `plans/260727-mergecert/analyze-mergecert-q2.py`
- Modify: `tests/test_mergecert_q2_analysis.py`

**Interfaces:**
- Consumes: amended routability JSON, score NPZ, tracked amendment JSON, and
  unchanged Q1 trigger.
- Produces: Q2 verdict containing the exact amendment payload/hash and
  validated accounting audit.

- [ ] **Step 1: Add RED analyzer drift tests**

Extend `_fixture` with valid long/short flattened accounting and exact
amendment singleton arrays. Add `amendment_path` to `analyze(...)`.

Assert valid evidence passes, then independently mutate:

- local amendment file bytes;
- payload amendment payload/hash;
- score amendment JSON/hash;
- protocol or namespace version;
- one short row to fixed-4,096 counts;
- one shifted context/eviction range;
- one physical count;
- capture-summary or accounting audit hash;
- ratio item count or ID.

Each mutation must raise before metric recomputation.

- [ ] **Step 2: Run RED analyzer tests**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_mergecert_q2_analysis.py
```

Expected: failures because Q2 analysis does not require the amendment or
accounting arrays.

- [ ] **Step 3: Implement local amendment and accounting validation**

Add default amendment path
`plans/260728-mergecert-q1/q2-amendment.json`. Load and hash it independently.
Require exact agreement among local file, routability payload, source hashes,
and score singletons.

Require all flattened Task 1 accounting arrays. Validate each registered ratio
against the corresponding item/document/manifest row metadata carried by the
scores. Reject any missing, duplicate, shifted, impossible, old-version, or
fixed-4,096 short row.

Include in the returned Q2 verdict:

```text
protocol_version
namespace_version
context_mechanics_version
q2_amendment
q2_amendment_sha256
context_accounting_audit
```

- [ ] **Step 4: Run GREEN analyzer tests**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_mergecert_q2_analysis.py
```

Expected: all pass.

- [ ] **Step 5: Commit Task 5**

```bash
git add plans/260727-mergecert/analyze-mergecert-q2.py \
  tests/test_mergecert_q2_analysis.py
git commit -m "fix: gate Q2 analysis on amended accounting"
```

---

### Task 6: Q3 amendment binding

**Files:**
- Modify: `plans/260727-mergecert/analyze-mergecert-q3.py`
- Modify: `tests/test_mergecert_q3_analysis.py`

**Interfaces:**
- Consumes: amended Q2 verdict, amended score NPZ, tracked amendment JSON,
  unchanged trigger, and A/B/FR/E1F reference artifacts.
- Produces: Q3 result with identical amendment payload/hash and protocol
  versions.

- [ ] **Step 1: Add RED Q3 binding tests**

Extend the fixture with amendment payload/hash/version in both `q2_results`
and score singleton arrays. Add `amendment_path` to `analyze(...)`.

Parametrize independent drift in the local amendment file, Q2 result payload,
Q2 result hash, score payload, score hash, protocol version, namespace
version, context-mechanics version, and accounting audit hash. Each must fail
before selecting the ratio-0.40 E1 rows.

- [ ] **Step 2: Run RED Q3 tests**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_mergecert_q3_analysis.py
```

Expected: failures because Q3 binds only the Q1 trigger and score hash.

- [ ] **Step 3: Implement the Q3 amendment gate**

Load/hash the tracked amendment independently. Require identical payload/hash
and versions in the Q2 result and score NPZ, plus identical accounting audit
hashes. Preserve the existing 2,000-item E1 selection and reference
comparison unchanged.

Emit amendment payload/hash and all three amended protocol versions in the Q3
result.

- [ ] **Step 4: Run GREEN Q3 tests**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_mergecert_q3_analysis.py
```

Expected: all pass.

- [ ] **Step 5: Commit Task 6**

```bash
git add plans/260727-mergecert/analyze-mergecert-q3.py \
  tests/test_mergecert_q3_analysis.py
git commit -m "fix: bind Q3 to amended Q2 protocol"
```

---

### Task 7: Private report and plan amendment provenance

**Files:**
- Modify: `plans/260728-mergecert-q1/render-report.py`
- Modify: `plans/260728-mergecert-q1/validate-report.py`
- Modify: `tests/test_mergecert_q1_report.py`
- Modify: `docs/superpowers/plans/2026-07-28-mergecert-q1-completion.md`
- Modify ignored: `.superpowers/sdd/2026-07-28-mergecert-q1-completion/task-7-report.md`

**Interfaces:**
- Consumes: conditional-work declaration, Q2/Q3 evidence, tracked amendment
  artifact, unchanged trigger, and artifact manifest.
- Produces: hash-validated amended-Q2 conditional report wording and explicit
  rerun-required plan.

- [ ] **Step 1: Add RED report drift tests**

Update the positive report fixture to write the exact Task 1 amendment
artifact and include:

```json
"q2_amendment": {
  "path": "plans/260728-mergecert-q1/q2-amendment.json",
  "sha256": "the value returned by _sha256(amendment_path)"
}
```

in `conditional-work.json`, with the same payload/hash/version in Q2 and Q3.
Add tests that reject missing or drifted conditional declaration, amendment
file, Q2 binding, Q3 binding, protocol version, namespace version, mechanics
version, and accounting audit hash.

Assert rendered positive wording explicitly says “amended variable-context
Q2” and does not call the result the unchanged fixed-4,096 protocol.

- [ ] **Step 2: Run RED report tests**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_mergecert_q1_report.py
```

Expected: failures because renderer/validator do not load or require the Q2
amendment.

- [ ] **Step 3: Load and validate amendment evidence**

When conditional work is completed, `render-report.py` must load the declared
amendment path as a separate hashed evidence input. `validate-report.py`
independently validates its schema and actual SHA-256, then requires exact
payload/hash/version/accounting-audit agreement among conditional, Q2, and Q3
evidence.

Include the amendment in artifact-manifest output with unique relative path,
byte count, and SHA-256.

- [ ] **Step 4: Update report wording and execution plan**

Render the conditional section as amended variable-context Q2/Q3, preserving
the original 30,847-item population and describing per-item matched physical
budgets.

In the Task 7 execution plan:

- mark option 2 as selected and settled by the dated amendment;
- preserve `q2-fleet-attempt.json` as immutable failed fixed-context evidence;
- record the new amended-v2 pilot and fleet paths;
- require a new 16-item pilot even though the selected rows may be long;
- require review of the new verdict before one new eight-slice fleet;
- retain exactly 30,847 fleet items;
- state that no remote action occurred during implementation.

Append the spec, RED/GREEN evidence, exact amendment hash, changed files,
verification commands, and no-remote statement to the ignored Task 7 report.

- [ ] **Step 5: Run GREEN report tests**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_mergecert_q1_report.py
```

Expected: all pass.

- [ ] **Step 6: Commit Task 7**

```bash
git add plans/260728-mergecert-q1/render-report.py \
  plans/260728-mergecert-q1/validate-report.py \
  tests/test_mergecert_q1_report.py \
  docs/superpowers/plans/2026-07-28-mergecert-q1-completion.md
git commit -m "docs: bind reports to amended Q2 protocol"
```

Do not stage the ignored SDD report.

---

### Task 8: Cross-layer regression, hashes, and local completion

**Files:**
- Verify all files changed in Tasks 1–7.
- Modify ignored: `.superpowers/sdd/2026-07-28-mergecert-q1-completion/task-7-report.md`

**Interfaces:**
- Consumes: complete local amended protocol implementation.
- Produces: verified commits and a clean tracked worktree; no experiment
  result and no remote state.

- [ ] **Step 1: Run focused amended-Q2 suites**

```bash
./.venv/bin/python -m pytest -q \
  tests/test_mergecert_q2_amendment.py \
  tests/test_mergecert_q2_capture_schema.py \
  tests/test_mergecert_q2_probe_contract.py \
  tests/test_mergecert_q2_analysis.py \
  tests/test_mergecert_q3_analysis.py \
  tests/test_mergecert_q1_report.py \
  tests/test_mergecert_campaign_contract.py
```

Expected: zero failures.

- [ ] **Step 2: Run the complete pinned offline suite**

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  ./.venv/bin/python -m pytest tests -q
```

Expected: zero failures; only registered skips.

- [ ] **Step 3: Compile every changed Python consumer**

```bash
./.venv/bin/python -m py_compile \
  memsub/certification/mergecert_q2_context.py \
  modal-runners/modal-mergecert-q2-capture.py \
  modal-runners/modal-mergecert-q2-probes.py \
  plans/260727-mergecert/analyze-mergecert-q2.py \
  plans/260727-mergecert/analyze-mergecert-q3.py \
  plans/260728-mergecert-q1/render-report.py \
  plans/260728-mergecert-q1/validate-report.py
```

Expected: exit zero.

- [ ] **Step 4: Verify exact authority hashes**

```bash
sha256sum plans/260728-mergecert-q1/q2-amendment.json
sha256sum plans/260728-mergecert-q1/q1-trigger.json
```

Expected: amendment digest equals every pinned code/evidence constant; trigger
digest remains exactly
`009d1ba2879b76174c13dffbea27a458b10d9a859cdb69046f3afac31a2af5a1`.

- [ ] **Step 5: Audit namespace and fixed-context assumptions**

```bash
rg -n '/artifacts/mergecert/q2($|/)|pilot-q1-triggered|full-slice-' \
  modal-runners/modal-mergecert-q2-capture.py \
  modal-runners/modal-mergecert-q2-probes.py
rg -n '4096 -|build_merge_plan\\(4096|short Q2 context' \
  modal-runners/modal-mergecert-q2-capture.py \
  modal-runners/modal-mergecert-q2-probes.py
```

Expected: old paths appear only in explicit legacy incompatibility constants
or messages; no amended execution path contains a fixed-4,096 plan or probe
distance assumption.

- [ ] **Step 6: Run diff and status hygiene**

```bash
git diff --check
git status --short
```

Expected: only intentional unstaged changes, or clean after the final scoped
commit. The ignored Task 7 report remains untracked by Git.

- [ ] **Step 7: Append final local-only report evidence**

Record the RED failures, GREEN focused/full counts, compile result, amendment
and trigger hashes, commit IDs, exact changed paths, and:

```text
No Modal command, upload, pilot, fleet, probe, download, or remote mutation
ran during amendment implementation. No Q2 or Q3 scientific result is claimed.
```

- [ ] **Step 8: Resolve verification failures in their owning task**

If verification exposes a failure, return to the task that owns the affected
file, add or strengthen its RED regression, implement the minimal correction,
rerun that task's GREEN command and the full pinned suite, then use that
task's explicit `git add` file list and commit message. If no tracked
correction remains, do not create an empty commit.
