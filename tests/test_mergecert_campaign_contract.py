import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "modal-runners" / "modal-mergecert-p0-q1.py"
PROVENANCE = ROOT / "plans" / "260727-mergecert" / "source-provenance.json"
Q2_RUNNER = ROOT / "modal-runners" / "modal-mergecert-q2-capture.py"
Q2_PROBE_RUNNER = ROOT / "modal-runners" / "modal-mergecert-q2-probes.py"


def _literal_constants(path):
    tree = ast.parse(path.read_text())
    constants = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        value = node.value
        if isinstance(target, ast.Name):
            try:
                constants[target.id] = ast.literal_eval(value)
            except (ValueError, TypeError):
                pass
    return constants


def test_mergecert_runner_pins_the_registered_private_campaign_contract():
    constants = _literal_constants(RUNNER)

    assert constants["MODEL_ID"] == "Qwen/Qwen3-4B-Instruct-2507"
    assert constants["UPSTREAM_COMMIT"] == (
        "cd4ed948d62231449dbab9669608bbb4fd220713"
    )
    assert constants["RATIOS"] == (0.25, 0.40, 0.90)
    assert constants["SINKS"] == 4
    assert constants["P0_ITEMS"] == 200
    assert constants["SEED"] == 20260727
    assert constants["ARTIFACT_ROOT"] == "/artifacts/mergecert"


def test_mergecert_source_provenance_pins_the_upstream_files_of_record():
    provenance = json.loads(PROVENANCE.read_text())

    assert provenance["repository"] == "https://github.com/jkdkr2439/KV-Merge"
    assert provenance["commit"] == "cd4ed948d62231449dbab9669608bbb4fd220713"
    assert provenance["files"] == {
        "README.md": "edfd5236d99dab5d6e4bf80b74dd79a54ffd94cec4b7066511dc6fd7ae7cae17",
        "benchmarks/modal_kv_real_bench.py": (
            "518b2d2cd4b652f4cc83ef9c82593fe624301986e0e3e22780ee9f0bfe423bb8"
        ),
        "lego_server.py": "f1df91c8af05cf4ea5000f4027450bf91e5e269f4e922da8979fc0885d6ff228",
    }


def test_mergecert_runner_contains_no_training_or_publication_path():
    source = RUNNER.read_text()

    for forbidden in (
        "Qwen2.5",
        "torch.optim",
        "Optimizer",
        "upload_file",
        "upload_folder",
        "huggingface_hub",
        "git push",
    ):
        assert forbidden not in source


def test_mergecert_runner_exposes_the_registered_p0_entrypoints():
    tree = ast.parse(RUNNER.read_text())
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    constants = _literal_constants(RUNNER)

    assert {"smoke", "p0_direction"} <= functions
    assert constants["CONTINUATION_TEXT"] == " The discussion continued."
    assert constants["P0_CHECKPOINT_EVERY"] == 10


def test_mergecert_runner_exposes_a_p0_gated_q1_contract():
    tree = ast.parse(RUNNER.read_text())
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    constants = _literal_constants(RUNNER)

    assert "q1_certify" in functions
    assert constants["Q1_CONTEXTS_PER_DOMAIN"] == 5
    assert constants["Q1_EXPECTED_DOCUMENTS"] == 20
    assert constants["Q1_ARCHIVE_ROOT"] == (
        "/artifacts/corpus-certification-full"
    )
    assert constants["Q1_ITEMS_PATH"] == (
        "/artifacts/corpus-mcq-full/all-items.json"
    )
    assert constants["Q1_OUTPUT"] == (
        "/artifacts/mergecert/q1-certification.json"
    )


def test_mergecert_q2_runner_pins_unified_capture_and_fixed_fleet_contract():
    constants = _literal_constants(Q2_RUNNER)
    tree = ast.parse(Q2_RUNNER.read_text())
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert constants["MODEL_ID"] == "Qwen/Qwen3-4B-Instruct-2507"
    assert constants["RATIOS"] == (0.25, 0.40)
    assert constants["CTX"] == 4096
    assert constants["SINKS"] == 4
    assert constants["Q2_ITEMS"] == 30_847
    assert constants["Q2_SLICES"] == 8
    assert constants["CAPTURE_ROOT"] == "/artifacts/mergecert/q2"
    assert constants["HEADS"] == (
        (25, 14),
        (26, 26),
        (28, 19),
        (35, 15),
    )
    assert {"q2_pilot", "q2_capture_slice", "freeze_capture_summary"} <= functions


def test_mergecert_q2_runner_has_no_training_or_publication_path():
    source = Q2_RUNNER.read_text()

    for forbidden in (
        "Qwen2.5",
        "torch.optim",
        "Optimizer",
        "upload_file",
        "upload_folder",
        "huggingface_hub",
        "git push",
    ):
        assert forbidden not in source


def test_mergecert_q2_probe_runner_pins_registered_arms_and_splits():
    constants = _literal_constants(Q2_PROBE_RUNNER)
    tree = ast.parse(Q2_PROBE_RUNNER.read_text())
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert constants["MODEL_ID"] == "Qwen/Qwen3-4B-Instruct-2507"
    assert constants["RATIOS"] == (0.25, 0.40)
    assert constants["SEEDS"] == (0, 1, 2)
    assert constants["TRAIN_END"] == 0.6
    assert constants["VALIDATION_END"] == 0.7
    assert constants["RESIDUAL_LAYERS"] == tuple(range(37))
    assert constants["CAPTURE_SUMMARY"] == (
        "/artifacts/mergecert/q2/capture-summary.json"
    )
    assert constants["ROUTABILITY_OUTPUT"] == (
        "/artifacts/mergecert/q2/routability.json"
    )
    assert constants["SCORES_OUTPUT"] == (
        "/artifacts/mergecert/q2/scores.npz"
    )
    assert constants["ARM_NAMES"] == (
        "c0_refit",
        "mechanics_refit",
        "shadow_zero_shot",
        "shadow_refit",
        "sink_compactor_zero_shot",
        "sink_eviction_zero_shot",
        "sink_refit",
        "residual_linear",
        "residual_mlp",
    )
    assert {"complete_fact_types", "run_probes"} <= functions
