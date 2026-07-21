import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_all_tracked_json_is_strictly_parseable():
    paths = subprocess.check_output(
        ["git", "ls-files", "*.json"], cwd=ROOT, text=True
    ).splitlines()
    failures = []
    for relative in paths:
        try:
            json.loads(
                (ROOT / relative).read_text(),
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f"non-finite constant {value}")),
            )
        except (ValueError, json.JSONDecodeError) as exc:
            failures.append(f"{relative}: {exc}")
    assert failures == []


def test_clean_e1full_result_is_tracked_and_fail_closed():
    relative = (
        "plans/260719-2328-e1full-unfrozen-full-recipe/"
        "summary-e1full-clean-v1-n60.json"
    )
    result = json.loads((ROOT / relative).read_text())
    provenance = result["provenance"]
    overlap = provenance["overlap_audit"]
    summary = result["summary"]

    assert provenance["holdout_sha256"] == (
        "64043bca6642b877af7366d4980a3bd9794184ff49e1702a4ef8a3db7398882d"
    )
    assert provenance["training_manifest_sha256"] == (
        "16e3ef0e7b9062218dc4f43a7ca53821c2194884b1c0580c62da2c9fba066aff"
    )
    assert overlap == {
        "training_documents": 35353,
        "training_items": 94056,
        "certification_documents": 60,
        "certification_items": 193,
        "document_overlap": [],
        "item_overlap": [],
    }
    assert summary["n_documents"] == 60
    assert summary["gt13_point_pass"] == {
        "compactor-d1": False,
        "compactor-d4": False,
    }
    assert summary["gt13_ship"] is False
    assert summary["gt15_max_certified_depth"] == 0
    assert summary["policy_version_e1full-clean-v1-t1024-T8k"] == (
        "still-compact-v1:t1024:depth0:sha256:c00b2437fdd813cc"
    )


def test_clean_e1full_result_is_propagated_to_publication_surfaces():
    paths = [
        "E1FULL-REPORT.md",
        "README.md",
        "docs/draft.md",
        "docs/draft2.md",
        "examples/experimental-traces/README.md",
        "paper/main.tex",
        "paper2/main.tex",
        "unified_memory_substrate_spec_v0.3.7.md",
        "modal-runners/modal-push-compactor-checkpoints-to-huggingface.py",
        "plans/260719-2328-e1full-unfrozen-full-recipe/plan.md",
    ]
    for relative in paths:
        text = (ROOT / relative).read_text()
        head = text[:3500].upper()
        assert "CLEAN" in head and "NO-SHIP" in head, relative
        assert "CLEAN RERUN PENDING" not in text.upper(), relative
        assert "PENDING THE CLEAN" not in text.upper(), relative
        assert "C00B2437FDD813CC" in text.upper(), relative


def test_paper1_scopes_its_original_certification_as_historical():
    paths = ["docs/draft.md", "paper/main.tex"]
    for relative in paths:
        text = (ROOT / relative).read_text().upper()
        assert "HISTORICAL 12-CONTEXT" in text, relative
        assert "NOT CLEAN HELD-OUT EVIDENCE" in text, relative
        assert "FROZEN" in text and "1/40" in text and "NOT RERUN" in text, relative


def test_spec_no_longer_calls_e1full_first_task_certified():
    spec = (ROOT / "unified_memory_substrate_spec_v0.3.7.md").read_text()
    assert "First task-certified L3 configuration" not in spec
    assert "produced the first L3 configuration" not in spec


def test_manifest_modal_image_installs_memsub_import_dependencies():
    source = (ROOT / "modal-runners" /
              "modal-fullrecipe-c2-mixture-manifest.py").read_text()
    assert ".pip_install(*PINNED)" in source
