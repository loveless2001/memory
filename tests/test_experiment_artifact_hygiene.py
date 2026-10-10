import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# Legacy evidence committed as JSON + a console trailer; bytes are kept unchanged and
# pinned here (a parsed copy sits beside it as *.parsed-sidecar.json). Any byte change
# removes the exemption.
LEGACY_JSON_WITH_CONSOLE_TRAILER = {
    "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-l40s-profile-v1/independent-stop-verify.json":
        "40f6bac90ae5cde26e4c17cd2e9152e7553899d733f8d5517b77882eb1d7a559",
    # codex-cleared Gate-3 rev2 evidence (indexed in SHA256SUMS-gate3-package-rev2.txt): bytes kept as cleared
    "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk-prep/gate3-rev2/mutation-checks.json":
        "26710b5553dc27bfc6fcce4adbc4ba246b9402adf2678ee9980e8af51b2fe860",
    # audited M4-SGM mutation evidence with an `EXIT_STATUS=0` console trailer: bytes kept (codex 22668 review)
    "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/mutation-checks.json":
        "58a2ac2d9990633679d8d951aebd7d77f63dc791854fd72416e99c9d00d87f18",
    "plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis/mutation-checks.json":
        "937e006620e240bc2fd38659a636eabd9a09c4860fb5cef93625ce3c43519186",
}


def test_all_tracked_json_is_strictly_parseable():
    paths = subprocess.check_output(
        ["git", "ls-files", "*.json"], cwd=ROOT, text=True
    ).splitlines()
    failures = []
    for relative in paths:
        if relative in LEGACY_JSON_WITH_CONSOLE_TRAILER:
            import hashlib
            digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            if digest != LEGACY_JSON_WITH_CONSOLE_TRAILER[relative]:
                failures.append(f"{relative}: legacy exemption pinned bytes changed ({digest})")
            continue
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
