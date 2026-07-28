import ast
import importlib.util
import json
from pathlib import Path

import pytest
import torch

from memsub.runtime import CompactedPrefixCache


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "modal-runners" / "modal-mergecert-p0-q1.py"
PROVENANCE = ROOT / "plans" / "260727-mergecert" / "source-provenance.json"
Q2_RUNNER = ROOT / "modal-runners" / "modal-mergecert-q2-capture.py"
Q2_PROBE_RUNNER = ROOT / "modal-runners" / "modal-mergecert-q2-probes.py"


def _q1_trigger(**overrides):
    trigger = {
        "protocol": "MERGECERT-Q1",
        "run_q2_q3": True,
        "favorable_intervals": ["0.40:mean_kl"],
        "q1_verdict_sha256": "c" * 64,
        "addendum_sha256": "a" * 64,
        "p0_verdict_sha256": "b" * 64,
    }
    trigger.update(overrides)
    return trigger


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_mergecert_runner_audits_all_registered_budgets_on_runtime_cache_objects():
    runner = _load_module(RUNNER, "mergecert_p0_runner_budget_audit")
    sequence_length = 4096
    keys = torch.arange(sequence_length, dtype=torch.float32).view(
        1, 1, sequence_length, 1
    )
    cache = CompactedPrefixCache.from_tensors(
        [keys],
        [10 * keys],
        logical_positions=list(range(sequence_length)),
        next_logical_position=sequence_length,
        sink_token_count=4,
    )
    attention_mass = torch.ones((1, 1, sequence_length))

    audit, merged = runner._runtime_budget_audit(cache, attention_mass)

    assert {
        ratio: row["physical_length"] for ratio, row in audit.items()
    } == {"0.25": 3072, "0.40": 2458, "0.90": 410}
    assert all(row["kv_finite"] for row in audit.values())
    assert merged.physical_length == 410


def test_mergecert_runner_exposes_a_p0_gated_q1_contract():
    tree = ast.parse(RUNNER.read_text())
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    constants = _literal_constants(RUNNER)

    assert {"q1_addendum_smoke", "q1_addendum_certify"} <= functions
    assert constants["Q1_CONTEXTS_PER_DOMAIN"] == 5
    assert constants["Q1_EXPECTED_DOCUMENTS"] == 20
    assert constants["Q1_ARCHIVE_ROOT"] == (
        "/artifacts/corpus-certification-full"
    )
    assert constants["Q1_ITEMS_PATH"] == (
        "/artifacts/corpus-mcq-full/all-items.json"
    )
    source = RUNNER.read_text()
    assert 'Q1_OUTPUT = f"{Q1_ARTIFACT_ROOT}/q1-certification.json"' in source


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
    verdict.write_text(
        json.dumps(
            {
                "p0_3": {"pass": False},
                "p0_4": {"pass": True},
                "real_attention": {"pass": True},
                "p0_pass": False,
                "stop_q1_q3": True,
            }
        )
    )

    gate = runner._load_q1_authorization(
        addendum_path=str(addendum),
        p0_verdict_path=str(verdict),
    )

    assert gate["protocol"] == "MERGECERT-Q1"
    assert gate["settled_p0"]["p0_3_pass"] is False
    assert len(gate["addendum_sha256"]) == 64
    assert len(gate["p0_verdict_sha256"]) == 64


def test_mergecert_q1_constructs_only_control_and_moderate_ratio_arms():
    tree = ast.parse(RUNNER.read_text())
    run_q1 = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_run_q1"
    )
    arm_spec_assign = next(
        node
        for node in ast.walk(run_q1)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "arm_specs"
            for target in node.targets
        )
    )
    arm_spec_source = ast.unparse(arm_spec_assign.value)

    assert "control-0.00" in arm_spec_source
    assert "eviction-{ratio:.2f}" in arm_spec_source
    assert "merge-{ratio:.2f}" in arm_spec_source
    assert "Q1_RATIOS" in arm_spec_source
    assert "RATIOS" not in arm_spec_source.replace("Q1_RATIOS", "")


def test_mergecert_q1_artifact_uses_analyzer_authorization_schema():
    source = RUNNER.read_text()
    tree = ast.parse(source)
    run_q1 = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_run_q1"
    )
    state_assign = next(
        node
        for node in run_q1.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "state"
            for target in node.targets
        )
    )
    state_source = ast.unparse(state_assign.value)

    assert "'q1_authorization': gate" in state_source
    assert "q1_gate" not in state_source
    assert 'prior.get("q1_authorization") != gate' in source


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


@pytest.mark.parametrize(
    "trigger",
    (
        None,
        _q1_trigger(run_q2_q3=False),
        _q1_trigger(favorable_intervals=[]),
        _q1_trigger(q1_verdict_sha256=""),
        _q1_trigger(favorable_intervals=[None]),
        _q1_trigger(favorable_intervals={"0.40:mean_kl": True}),
        _q1_trigger(q1_verdict_sha256=["c"] * 64),
    ),
)
def test_q2_runners_reject_a_missing_or_non_authorizing_q1_trigger(
    tmp_path, trigger
):
    trigger_path = tmp_path / "q1-trigger.json"
    if trigger is not None:
        trigger_path.write_text(json.dumps(trigger))

    for path, name in (
        (Q2_RUNNER, "mergecert_q2_capture_q1_trigger"),
        (Q2_PROBE_RUNNER, "mergecert_q2_probes_q1_trigger"),
    ):
        runner = _load_module(path, name)
        with pytest.raises(ValueError, match="Q2 is blocked"):
            runner._require_q1_trigger(str(trigger_path))


def test_q2_runners_accept_the_registered_q1_trigger(tmp_path):
    trigger = _q1_trigger()
    trigger_path = tmp_path / "q1-trigger.json"
    trigger_path.write_text(json.dumps(trigger))

    for path, name in (
        (Q2_RUNNER, "mergecert_q2_capture_q1_trigger_accept"),
        (Q2_PROBE_RUNNER, "mergecert_q2_probes_q1_trigger_accept"),
    ):
        runner = _load_module(path, name)
        assert runner._require_q1_trigger(str(trigger_path)) == trigger


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
