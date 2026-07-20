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


def test_contaminated_e1full_claims_are_prominently_invalidated():
    paths = [
        "E1FULL-REPORT.md",
        "README.md",
        "docs/draft2.md",
        "paper2/main.tex",
        "unified_memory_substrate_spec_v0.3.7.md",
        "modal-runners/modal-push-compactor-checkpoints-to-huggingface.py",
        "plans/260719-2328-e1full-unfrozen-full-recipe/plan.md",
    ]
    for relative in paths:
        head = (ROOT / relative).read_text()[:2500].upper()
        assert "INVALIDATED" in head, relative
        assert "TRAIN" in head and "HOLDOUT" in head, relative


def test_spec_no_longer_calls_e1full_first_task_certified():
    spec = (ROOT / "unified_memory_substrate_spec_v0.3.7.md").read_text()
    assert "First task-certified L3 configuration" not in spec
    assert "produced the first L3 configuration" not in spec


def test_manifest_modal_image_installs_memsub_import_dependencies():
    source = (ROOT / "modal-runners" /
              "modal-fullrecipe-c2-mixture-manifest.py").read_text()
    assert ".pip_install(*PINNED)" in source
