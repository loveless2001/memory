# Clean Experimental Trace Gallery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and publish three reproducible, paper-ready traces selected only from the signed clean E1FULL held-out certification artifact.

**Architecture:** A standalone example generator validates the signed artifact, aligns document and probe records across four arms, deterministically selects three distinct trace categories, and renders stable JSON and Markdown. Tests exercise provenance failure, exact selection, schema alignment, checked-in regeneration, and publication links; README and paper #2 consume the generated gallery without introducing a second experimental source of truth.

**Tech Stack:** Python 3.12 standard library, pytest 8.3.4, JSON, Markdown, LaTeX/Tectonic.

## Global Constraints

- The sole experimental input is `plans/260719-2328-e1full-unfrozen-full-recipe/summary-e1full-clean-v1-n60.json`.
- Include no toy, synthetic, or contaminated historical trace rows.
- Label outputs as certification traces, not token-level generation logs.
- Preserve GT13 NO-SHIP, certified depth zero, and the exact clean provenance hashes.
- Select three distinct documents deterministically in category order: pointwise recovery, axis disagreement, depth-4 collapse.
- Fail closed on provenance, alignment, or eligibility errors.
- Do not publish remotely.

---

### Task 1: Deterministic Trace Selection And Rendering

**Files:**
- Create: `examples/build_clean_experimental_traces.py`
- Create: `tests/test_clean_experimental_trace_gallery.py`

**Interfaces:**
- Consumes: clean certification JSON with top-level `provenance`, `summary`, and `reports` objects.
- Produces: `validate_source(source: dict) -> None`, `build_gallery(source: dict) -> dict`, `render_markdown(gallery: dict) -> str`, and `generate(source_path: Path, json_path: Path, markdown_path: Path) -> None`.

- [x] **Step 1: Write failing provenance and selection tests**

```python
from copy import deepcopy
import json
from pathlib import Path

import pytest

from examples.build_clean_experimental_traces import build_gallery, validate_source

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plans/260719-2328-e1full-unfrozen-full-recipe/summary-e1full-clean-v1-n60.json"


def load_source():
    return json.loads(SOURCE.read_text())


def test_rejects_unknown_clean_provenance():
    source = deepcopy(load_source())
    source["provenance"]["holdout_sha256"] = "tampered"
    with pytest.raises(ValueError, match="holdout_sha256"):
        validate_source(source)


def test_selects_three_distinct_registered_trace_categories():
    gallery = build_gallery(load_source())
    assert [(row["category"], row["document_id"]) for row in gallery["traces"]] == [
        ("pointwise_recovery", "financial/00009"),
        ("axis_disagreement", "code/00011"),
        ("depth4_collapse", "financial/00002"),
    ]
```

- [x] **Step 2: Run the tests and verify RED**

Run: `./.venv/bin/python -m pytest tests/test_clean_experimental_trace_gallery.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'examples.build_clean_experimental_traces'`.

- [x] **Step 3: Implement validation, alignment, selection, and stable rendering**

Create `examples/build_clean_experimental_traces.py` with registered constants for the two source hashes, checkpoint hash, policy ID, overlap counts, and source path. Implement:

```python
def validate_source(source: dict) -> None:
    provenance = source["provenance"]
    summary = source["summary"]
    checks = {
        "holdout_sha256": (provenance["holdout_sha256"], EXPECTED_HOLDOUT_SHA),
        "training_manifest_sha256": (
            provenance["training_manifest_sha256"], EXPECTED_MANIFEST_SHA),
        "checkpoint_weights": (
            provenance["checkpoint_weights"][CHECKPOINT_NAME],
            f"sha256:{EXPECTED_CHECKPOINT_SHA}"),
        "overlap_audit": (provenance["overlap_audit"], EXPECTED_OVERLAP_AUDIT),
        "gt13_ship": (summary["gt13_ship"], False),
        "gt15_max_certified_depth": (summary["gt15_max_certified_depth"], 0),
    }
    for name, (actual, expected) in checks.items():
        if actual != expected:
            raise ValueError(f"{name}: expected {expected!r}, got {actual!r}")
```

Align reports by `eval_protocol.doc_id`; require identical document sets and pointwise item IDs across `eviction-matched`, `compactor-d1`, `compactor-d4`, and `control-0`. Compute recovery counts and document-level KL/loss gaps. Select candidates using the exact sort tuples from the design, excluding already selected documents. Build the registered JSON schema and render Markdown with one provenance header, one metrics table per trace, and question/options/prediction blocks. Serialize JSON with `indent=2`, `sort_keys=True`, and a trailing newline.

- [x] **Step 4: Run focused tests and verify GREEN**

Run: `./.venv/bin/python -m pytest tests/test_clean_experimental_trace_gallery.py -q`

Expected: all Task 1 tests pass.

- [x] **Step 5: Commit Task 1**

```bash
git add examples/build_clean_experimental_traces.py tests/test_clean_experimental_trace_gallery.py
git commit -m "feat: generate clean experimental trace gallery"
```

---

### Task 2: Checked-In Gallery And Publication Integration

**Files:**
- Create: `examples/experimental-traces/clean-e1full-traces.json`
- Create: `examples/experimental-traces/README.md`
- Modify: `tests/test_clean_experimental_trace_gallery.py`
- Modify: `tests/test_experiment_artifact_hygiene.py`
- Modify: `README.md`
- Modify: `paper2/main.tex`
- Modify: `paper2/main.pdf`
- Modify: `docs/project-changelog.md`

**Interfaces:**
- Consumes: `generate(...)` and the deterministic gallery from Task 1.
- Produces: checked-in JSON/Markdown artifacts plus publication pointers that name all three selected documents.

- [x] **Step 1: Add failing regeneration and publication tests**

```python
def test_checked_in_gallery_regenerates_byte_for_byte(tmp_path):
    json_out = tmp_path / "traces.json"
    markdown_out = tmp_path / "README.md"
    generate(SOURCE, json_out, markdown_out)
    assert json_out.read_bytes() == (ROOT / GALLERY_JSON).read_bytes()
    assert markdown_out.read_bytes() == (ROOT / GALLERY_MARKDOWN).read_bytes()


def test_publication_surfaces_link_real_trace_gallery():
    gallery = json.loads((ROOT / GALLERY_JSON).read_text())
    for relative in ["README.md", "paper2/main.tex"]:
        text = (ROOT / relative).read_text()
        assert "experimental-traces/clean-e1full-traces.json" in text
        for trace in gallery["traces"]:
            assert trace["document_id"] in text
        assert "NO-SHIP" in text and "depth" in text.lower()
```

Also extend the hygiene publication list to include `examples/experimental-traces/README.md` and require the clean checkpoint hash in its first 3,500 characters.

- [x] **Step 2: Run the tests and verify RED**

Run: `./.venv/bin/python -m pytest tests/test_clean_experimental_trace_gallery.py tests/test_experiment_artifact_hygiene.py -q`

Expected: failure because the checked-in gallery files and publication links do not exist.

- [x] **Step 3: Generate the gallery artifacts**

Run:

```bash
./.venv/bin/python examples/build_clean_experimental_traces.py
```

Expected: writes exactly three traces to `examples/experimental-traces/clean-e1full-traces.json` and `examples/experimental-traces/README.md`.

- [x] **Step 4: Integrate the gallery into README and paper #2**

Add a root README subsection after the clean E1FULL result containing a three-row table with category, document ID, and evidence shown. Link both generated artifacts.

Add a paper #2 appendix subsection with the same three document IDs, short evidence descriptions, the JSON path `examples/experimental-traces/clean-e1full-traces.json`, and an explicit sentence that the gallery is real held-out evidence but not token-level generation logging. Do not introduce a frozen-versus-unfrozen ranking.

Record the gallery in the 2026-07-21 clean recertification changelog entry.

- [x] **Step 5: Rebuild paper #2 and verify focused tests**

Run: `tectonic main.tex` from `paper2/`.

Expected: successful build with no TeX warnings.

Run: `./.venv/bin/python -m pytest tests/test_clean_experimental_trace_gallery.py tests/test_experiment_artifact_hygiene.py -q`

Expected: all focused tests pass.

- [x] **Step 6: Commit Task 2**

```bash
git add examples/experimental-traces README.md paper2/main.tex paper2/main.pdf docs/project-changelog.md tests/test_clean_experimental_trace_gallery.py tests/test_experiment_artifact_hygiene.py
git commit -m "docs: publish clean experimental trace examples"
```

---

### Task 3: Final Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-07-21-clean-experimental-trace-gallery.md`

**Interfaces:**
- Consumes: committed generator, gallery, publication surfaces, and tests.
- Produces: a checked completion record and clean repository state.

- [x] **Step 1: Regenerate into temporary files and compare bytes**

Run the focused regeneration test:

```bash
./.venv/bin/python -m pytest tests/test_clean_experimental_trace_gallery.py::test_checked_in_gallery_regenerates_byte_for_byte -q
```

Expected: `1 passed`.

- [x] **Step 2: Run complete verification**

```bash
./.venv/bin/python -m pytest tests -q
./.venv/bin/python -m compileall -q memsub examples tests
./.venv/bin/python -c "import json, subprocess; paths=subprocess.check_output(['git','ls-files','*.json'], text=True).splitlines(); [json.load(open(p, encoding='utf-8')) for p in paths]; print(f'{len(paths)} tracked JSON files OK')"
git diff --check
```

Expected: all tests pass, compileall is silent, every tracked JSON file parses, and `git diff --check` is silent.

- [x] **Step 3: Mark the plan complete and commit**

Change every checkbox in this plan to `[x]`, then run:

```bash
git add docs/superpowers/plans/2026-07-21-clean-experimental-trace-gallery.md
git commit -m "docs: complete clean trace gallery plan"
```

- [x] **Step 4: Confirm final state**

Run: `git status --short && git log -4 --oneline`

Expected: empty status and commits for the design, generator, gallery publication, and plan completion.
