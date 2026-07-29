import ast
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest
import torch

from memsub.fingerprint import CompatibilityFingerprint
from memsub.runtime import CompactedPrefixCache


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "modal-runners" / "modal-mergecert-p0-q1.py"
PROVENANCE = ROOT / "plans" / "260727-mergecert" / "source-provenance.json"
Q1_PROVENANCE = (
    ROOT / "plans" / "260728-mergecert-q1" / "source-provenance.json"
)
Q1_REGISTRATION_EXTRACTION = (
    ROOT
    / "plans"
    / "260728-mergecert-q1"
    / "q1-registration-extraction.json"
)
Q1_SMOKE_ATTEMPT = (
    ROOT / "plans" / "260728-mergecert-q1" / "q1-smoke-attempt.json"
)
Q1_SMOKE_RETRY = (
    ROOT / "plans" / "260728-mergecert-q1" / "q1-smoke-retry.json"
)
Q1_REGISTRATION_SOURCE = (
    ROOT / "plans" / "260728-mergecert-q1" / "q1-registration-source.json"
)
Q1_REGISTRATION_RUNNER = (
    ROOT / "modal-runners" / "modal-mergecert-q1-registration.py"
)
Q1_REGISTRATION_BINDER = (
    ROOT / "scripts" / "bind-mergecert-q1-registration.py"
)
Q1_REGISTRATION_PENDING = "PENDING_CPU_EXTRACTION"
Q1_REGISTRATION_SHA256 = (
    "6d90677469c5548d0fde863db886e7a6665e25f15c23d351ba07a0ad4db6e2d5"
)
Q1_TOKENIZER_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
Q1_TOKENIZER_FILES_SHA256 = {
    "config.json": (
        "5beea1a4a34c62782bfb2f911c606741a3bab8f92d80a118fa053c28af12e8ba"
    ),
    "merges.txt": (
        "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ),
    "tokenizer.json": (
        "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4"
    ),
    "tokenizer_config.json": (
        "a62ff0a2472a0fa1b8eaabcb57c59b58afa42a22831dc141400b6e0cf2b65ce3"
    ),
    "vocab.json": (
        "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ),
}
Q1_TOKENIZER_ARTIFACT_SHA256 = (
    "709a32d47b81b8466749dac3f8c4718b901bad95c534a486a8ac0b388094f6c9"
)
Q1_ADDENDUM_SHA256 = (
    "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509"
)
Q1_P0_VERDICT_SHA256 = (
    "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
)
Q1_EXECUTION_SEMANTICS_VERSION = "mergecert-q1-execution-semantics-v1"
Q1_FINGERPRINT_SCHEMA = "memsub-compatibility-fingerprint-v1"
Q2_RUNNER = ROOT / "modal-runners" / "modal-mergecert-q2-capture.py"
Q2_PROBE_RUNNER = ROOT / "modal-runners" / "modal-mergecert-q2-probes.py"


def _q1_trigger(**overrides):
    trigger = {
        "protocol": "MERGECERT-Q1",
        "budget_mode": "archived-m1-per-document-matched-physical-v1",
        "run_q2_q3": True,
        "favorable_intervals": ["0.40:mean_kl"],
        "q1_verdict_sha256": "c" * 64,
        "addendum_sha256": Q1_ADDENDUM_SHA256,
        "p0_verdict_sha256": Q1_P0_VERDICT_SHA256,
    }
    trigger.update(overrides)
    return trigger


def _write_q2_pilot_fixture(tmp_path, runner, run_tags):
    capture_root = tmp_path / "q2"
    trigger_path = tmp_path / "q1-trigger.json"
    trigger = _q1_trigger()
    trigger_path.write_text(json.dumps(trigger))
    manifest_path = tmp_path / "capture-manifest.json"
    manifest = [
        {
            "item_id": f"item-{index:02d}",
            "doc_id": f"doc-{index // 2:02d}",
            "domain": "financial",
            "question": f"Question {index}",
            "options": ["one", "two", "three", "four"],
            "gold": "A",
            "pred_raw": "A",
            "chunk_rel_start": index,
            "y": 0,
            "in_e1": index % 2,
            "raw_correct": 1,
            "pilot": 1,
        }
        for index in range(16)
    ]
    manifest_path.write_text(json.dumps(manifest))
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    trigger_sha256 = hashlib.sha256(trigger_path.read_bytes()).hexdigest()
    item_ids = [row["item_id"] for row in manifest]
    for run_tag in run_tags:
        output_dir = capture_root / f"pilot-{run_tag}"
        output_dir.mkdir(parents=True)
        files = {}
        for ratio in (0.25, 0.40):
            mechanics = np.full((16, 4), 0.5, dtype=np.float32)
            mechanics[:, 0] = 4
            arrays = {
                "item_ids": np.asarray(item_ids),
                "doc_ids": np.asarray([row["doc_id"] for row in manifest]),
                "domain": np.asarray([row["domain"] for row in manifest]),
                "pred_raw": np.asarray(["A"] * 16),
                "pred_merge": np.asarray(["A", "B"] * 8),
                "y": np.asarray([0, 1] * 8, dtype=np.int8),
                "raw_correct": np.ones(16, dtype=np.int8),
                "in_e1": np.asarray([0, 1] * 8, dtype=np.int8),
                "locator_found": np.ones(16, dtype=np.int8),
                "merge_overlap": np.zeros(16, dtype=np.float32),
                "mechanics": mechanics,
                "sink_features": np.zeros((16, 8), dtype=np.float32),
                "residuals": np.zeros((16, 37, 2560), dtype=np.float16),
                "ratio": np.asarray([ratio], dtype=np.float32),
                "source_manifest_sha256": np.asarray([manifest_sha256]),
            }
            path = output_dir / f"ratio-{ratio:.2f}-rows-00000-00016.npz"
            np.savez(path, **arrays)
            files[f"{ratio:.2f}"] = {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "audit": {
                    "rows": 16,
                    "unique_item_ids": 16,
                    "locator_found": 16,
                    "positive_labels": 8,
                },
            }
        fingerprint = _q2_fingerprint()
        state = {
            "q1_trigger": trigger,
            "q1_trigger_sha256": trigger_sha256,
            "model_id": runner.MODEL_ID,
            "ratios": [0.25, 0.40],
            "sink_token_count": runner.SINKS,
            "source_manifest_path": str(manifest_path),
            "source_manifest_sha256": manifest_sha256,
            "slice_idx": 0,
            "n_slices": 1,
            "registered_item_count": 16,
            "registered_item_ids_sha256": runner._item_ids_sha256(item_ids),
            "completed_count": 16,
            "completed_item_ids": item_ids,
            "chunks": [
                {
                    "start": 0,
                    "end": 16,
                    "item_ids_sha256": runner._item_ids_sha256(item_ids),
                    "files": files,
                }
            ],
            "compute_seconds": 1.0,
            "compatibility_fingerprint_schema": (
                "memsub-compatibility-fingerprint-v1"
            ),
            "compatibility_fingerprint": fingerprint.to_dict(),
            "compatibility_fingerprint_sha256": fingerprint.digest(),
        }
        (output_dir / "state.json").write_text(json.dumps(state))
    return {
        "capture_root": capture_root,
        "trigger_path": trigger_path,
        "trigger": trigger,
        "trigger_sha256": trigger_sha256,
        "manifest_path": manifest_path,
    }


def _configure_q2_pilot_fixture(runner, monkeypatch, fixture):
    commits = []
    monkeypatch.setattr(runner, "CAPTURE_ROOT", str(fixture["capture_root"]))
    monkeypatch.setattr(
        runner, "Q1_TRIGGER_PATH", str(fixture["trigger_path"])
    )
    monkeypatch.setattr(
        runner, "MANIFEST_PATH", str(fixture["manifest_path"])
    )
    monkeypatch.setattr(runner, "Q2_ITEMS", 16)
    monkeypatch.setattr(
        runner, "artifacts", types.SimpleNamespace(commit=lambda: commits.append(1))
    )
    return commits


def _rewrite_q2_pilot_array(fixture, ratio, key, value):
    from memsub.compaction import validate_capture_chunk

    state_path = fixture["capture_root"] / "pilot-q1-triggered" / "state.json"
    state = json.loads(state_path.read_text())
    file_row = state["chunks"][0]["files"][f"{ratio:.2f}"]
    path = Path(file_row["path"])
    with np.load(path, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    arrays[key][0] = value
    np.savez(path, **arrays)
    file_row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    file_row["audit"] = validate_capture_chunk(
        arrays, expected_ratio=ratio
    )
    state_path.write_text(json.dumps(state))


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _q1_fingerprint(*, runtime_version="test-runtime"):
    return CompatibilityFingerprint(
        model_id="test-model",
        tokenizer_hash="sha256:" + "1" * 64,
        chat_template_hash="sha256:" + "2" * 64,
        rope_config_hash="sha256:" + "3" * 64,
        sliding_window_config="none",
        attention_impl="sdpa",
        kv_layout="gqa",
        quantization="bfloat16",
        adapter_hash=None,
        runtime_version=runtime_version,
        compaction_policy_version="evict-oldest-nonsink-v1",
        position_policy_version="pos-v1-preserve-logical-rope",
        channel_registry_version="memchan-v1",
        kernel_numeric_profile_hash="sha256:" + "4" * 64,
    )


def _q2_fingerprint(
    *,
    runtime_version="hf-transformers-4.55.2+torch-2.7.1+cu126",
):
    fingerprint = _q1_fingerprint(runtime_version=runtime_version)
    return CompatibilityFingerprint(
        **{
            **fingerprint.to_dict(),
            "model_id": (
                "Qwen/Qwen3-4B-Instruct-2507#cfg=sha256:"
                + "1" * 16
            ),
        }
    )


def _q2_fake_runtime(fingerprint=None):
    model = types.SimpleNamespace(
        config=types.SimpleNamespace(_attn_implementation="sdpa"),
        model=types.SimpleNamespace(layers=[]),
    )
    return types.SimpleNamespace(
        model=model,
        tokenizer=types.SimpleNamespace(),
        fingerprint=lambda: fingerprint or _q2_fingerprint(),
    )


def _q1_resume_state(runner, *, done=0, fingerprint=None):
    fingerprint = fingerprint or _q1_fingerprint()
    doc_ids = ["financial/00000", "financial/00008"]
    arm_names = (
        "control-0.00",
        "eviction-0.25",
        "eviction-0.40",
        "merge-0.25",
        "merge-0.40",
    )
    replay_arms = (
        "control-0.00",
        "eviction-0.25",
        "eviction-0.40",
    )
    return {
        "provenance": runner._q1_provenance(),
        "execution_semantics": runner._q1_execution_semantics(),
        "compatibility_fingerprint_schema": Q1_FINGERPRINT_SCHEMA,
        "compatibility_fingerprint": fingerprint.to_dict(),
        "compatibility_fingerprint_sha256": fingerprint.digest(),
        "q1_authorization": {"authorization": "test"},
        "q1_registration_sha256": "a" * 64,
        "sample_doc_ids": doc_ids,
        "documents": [
            {"doc_id": doc_id} for doc_id in doc_ids[:done]
        ],
        "arms": {
            arm: {
                "reports": [
                    {"doc_id": doc_id} for doc_id in doc_ids[:done]
                ]
            }
            for arm in arm_names
        },
        "archived_m1": {
            "replay_checks": [
                {"doc_id": doc_id, "arm": arm, "pass": True}
                for doc_id in doc_ids[:done]
                for arm in replay_arms
            ],
            "replay_pass": done == len(doc_ids),
        },
        "done_documents": done,
    }


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


def _fake_final_registration():
    source = json.loads(Q1_REGISTRATION_SOURCE.read_text())
    documents = []
    for doc_id in source["population_doc_ids"]:
        source_tokens = 3921 if doc_id == "legal/00000" else 4096
        source_start = source["eviction_source_start"][doc_id]
        documents.append(
            {
                "doc_id": doc_id,
                "context_start": max(
                    0,
                    source["anchor_chunk_token_start"][doc_id] - 1024,
                ),
                "source_context_token_count": source_tokens,
                "model_input_token_count": source_tokens,
                "budgets": {
                    f"{ratio:.2f}": {
                        "requested_evicted_token_count": int(
                            source_tokens * ratio
                        ),
                        "eviction_source_start": source_start,
                        "eviction_source_end": (
                            source_start + int(source_tokens * ratio)
                        ),
                        "physical_before_count": source_tokens,
                        "physical_after_count": (
                            source_tokens - int(source_tokens * ratio)
                        ),
                        "evicted_token_count": int(source_tokens * ratio),
                        "retained_token_count": (
                            source_tokens - int(source_tokens * ratio)
                        ),
                        "merge_target_retained": (
                            source_tokens - int(source_tokens * ratio)
                        ),
                    }
                    for ratio in (0.25, 0.40)
                },
            }
        )
    return {
        "schema": "mergecert-q1-registration-v1",
        "status": "finalized",
        "source_registration_sha256": hashlib.sha256(
            Q1_REGISTRATION_SOURCE.read_bytes()
        ).hexdigest(),
        "model_id": "Qwen/Qwen3-4B-Instruct-2507",
        "tokenizer": {
            "model_id": "Qwen/Qwen3-4B-Instruct-2507",
            "revision": Q1_TOKENIZER_REVISION,
            "files_sha256": Q1_TOKENIZER_FILES_SHA256,
            "artifact_sha256": Q1_TOKENIZER_ARTIFACT_SHA256,
        },
        "source_hashes": {
            "corpus_manifest_sha256": "1" * 64,
            "all_items_sha256": source["all_items_sha256"],
            "source_document_sha256": {
                doc_id: hashlib.sha256(
                    f"source:{doc_id}".encode()
                ).hexdigest()
                for doc_id in source["population_doc_ids"]
            },
        },
        "population_doc_ids": source["population_doc_ids"],
        "smoke_doc_ids": source["smoke_doc_ids"],
        "all_items_sha256": source["all_items_sha256"],
        "archive_sha256": source["archive_sha256"],
        "documents": documents,
    }


def _prepare_binder_root(tmp_path):
    root = tmp_path / "repo"
    binding_path = root / "memsub" / "mergecert_q1_registration.py"
    plan = root / "plans" / "260728-mergecert-q1"
    provenance_path = plan / "source-provenance.json"
    source_path = plan / "q1-registration-source.json"
    binding_path.parent.mkdir(parents=True)
    plan.mkdir(parents=True)
    binding_text = (
        ROOT / "memsub" / "mergecert_q1_registration.py"
    ).read_text()
    binding_path.write_text(
        binding_text.replace(
            f'Q1_REGISTRATION_SHA256 = "{Q1_REGISTRATION_SHA256}"',
            "Q1_REGISTRATION_SHA256 = Q1_REGISTRATION_PENDING",
        )
    )
    source_path.write_bytes(Q1_REGISTRATION_SOURCE.read_bytes())
    provenance_path.write_text(
        json.dumps(
            {
                "q1_registration": {
                    "path": (
                        "plans/260728-mergecert-q1/q1-registration.json"
                    ),
                    "remote_path": (
                        "/artifacts/mergecert-q1/q1-registration.json"
                    ),
                    "sha256": Q1_REGISTRATION_PENDING,
                    "status": (
                        "pending CPU extraction and independent review"
                    ),
                }
            },
            indent=1,
        )
        + "\n"
    )
    extracted = tmp_path / "extracted.json"
    raw = (
        json.dumps(
            _fake_final_registration(), indent=1, allow_nan=False
        )
        + "\n"
    ).encode()
    extracted.write_bytes(raw)
    return root, binding_path, provenance_path, extracted, raw


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
    addendum.write_bytes((ROOT / "MERGECERT-Q1.md").read_bytes())
    verdict.write_bytes(
        (ROOT / "plans/260727-mergecert/p0-verdict.json").read_bytes()
    )

    gate = runner._load_q1_authorization(
        addendum_path=str(addendum),
        p0_verdict_path=str(verdict),
    )

    assert gate["protocol"] == "MERGECERT-Q1"
    assert gate["budget_mode"] == (
        "archived-m1-per-document-matched-physical-v1"
    )
    assert gate["settled_p0"]["p0_3_pass"] is False
    assert len(gate["addendum_sha256"]) == 64
    assert len(gate["p0_verdict_sha256"]) == 64


@pytest.mark.parametrize("changed", ("addendum", "p0"))
def test_mergecert_q1_addendum_rejects_nonregistered_authorization_hashes(
    tmp_path, changed
):
    runner = _load_module(RUNNER, f"mergecert_q1_hash_gate_{changed}")
    addendum = tmp_path / "MERGECERT-Q1.md"
    verdict = tmp_path / "p0-verdict.json"
    addendum.write_bytes((ROOT / "MERGECERT-Q1.md").read_bytes())
    verdict.write_bytes(
        (ROOT / "plans/260727-mergecert/p0-verdict.json").read_bytes()
    )
    target = addendum if changed == "addendum" else verdict
    target.write_bytes(target.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="registered.*hash"):
        runner._load_q1_authorization(
            addendum_path=str(addendum),
            p0_verdict_path=str(verdict),
        )


def test_mergecert_q1_provenance_binds_the_settled_budget_amendment():
    provenance = json.loads(Q1_PROVENANCE.read_text())

    assert provenance["budget_mode"] == (
        "archived-m1-per-document-matched-physical-v1"
    )
    assert provenance["settled_amendment_date"] == "2026-07-29"
    assert provenance["addendum"]["sha256"] == hashlib.sha256(
        (ROOT / "MERGECERT-Q1.md").read_bytes()
    ).hexdigest()
    assert provenance["q1_registration_source"] == {
        "path": "plans/260728-mergecert-q1/q1-registration-source.json",
        "sha256": hashlib.sha256(
            Q1_REGISTRATION_SOURCE.read_bytes()
        ).hexdigest(),
        "status": "source-evidence-only; finalized CPU extraction completed",
    }
    assert provenance["q1_registration"] == {
        "path": "plans/260728-mergecert-q1/q1-registration.json",
        "remote_path": "/artifacts/mergecert-q1/q1-registration.json",
        "sha256": Q1_REGISTRATION_SHA256,
        "status": "finalized and hash-bound",
    }


def test_mergecert_q1_records_the_bounded_cpu_extraction():
    evidence = json.loads(Q1_REGISTRATION_EXTRACTION.read_text())
    registration_path = ROOT / evidence["registration"]["path"]

    assert evidence["status"] == "completed-reviewed-and-bound"
    assert evidence["modal"] == {
        "app_id": "ap-Bx0LRrGGZ0yUchiepNVrtV",
        "app_name": "mergecert-q1-registration",
        "state": "stopped",
        "tasks_after_stop": 0,
        "created_at": "2026-07-29 02:41:10+07:00",
        "stopped_at": "2026-07-29 02:42:10+07:00",
        "app_lifetime_seconds": 60,
        "function_call_id": "fc-01KYN3YPCSNQ0KBJJYNS5BZMNA",
        "gpu_requested": False,
        "model_weights_loaded": False,
        "remote_volume_written": False,
    }
    assert evidence["cost_estimate"]["usd"] < (
        evidence["cost_estimate"]["campaign_bound_usd"]
    )
    assert evidence["registration"]["sha256"] == hashlib.sha256(
        registration_path.read_bytes()
    ).hexdigest()
    assert evidence["registration"]["bytes"] == (
        registration_path.stat().st_size
    )
    assert evidence["registration"]["sha256"] == Q1_REGISTRATION_SHA256


def test_mergecert_q1_records_remote_verification_and_smoke_stop():
    evidence = json.loads(Q1_SMOKE_ATTEMPT.read_text())

    assert evidence["status"] == "failed-before-user-code"
    assert evidence["step_1b"] == {
        "status": "remote-byte-verification-passed",
        "files": {
            "/mergecert-q1/q1-registration.json": Q1_REGISTRATION_SHA256,
            "/mergecert-q1/MERGECERT-Q1.md": Q1_ADDENDUM_SHA256,
            "/mergecert-q1/p0-verdict.json": Q1_P0_VERDICT_SHA256,
        },
        "byte_comparison_passed": True,
    }
    assert evidence["smoke"]["app_id"] == "ap-amdd5k9Ybxoxv1d8c3vbon"
    assert evidence["smoke"]["state"] == "stopped"
    assert evidence["smoke"]["tasks_after_stop"] == 0
    assert evidence["smoke"]["failure_stage"] == (
        "container hydration before user code"
    )
    assert evidence["outputs"] == {
        "q1_smoke_artifact_produced": False,
        "independent_analyzer_run": False,
        "full_q1_launched": False,
        "q2_q3_launched": False,
    }
    assert evidence["cost_estimate"]["usd"] < (
        evidence["cost_estimate"]["campaign_bound_usd"]
    )


def test_mergecert_q1_records_the_reviewed_smoke_retry_stop():
    evidence = json.loads(Q1_SMOKE_RETRY.read_text())

    assert evidence["reviewed_fix_commit"] == (
        "a2f82932702b13cdfc8f71a1ab2fe99404a564ec"
    )
    assert evidence["status"] == "failed-registered-archive-replay"
    assert evidence["smoke"]["app_id"] == "ap-FS1Y8Y3bcazBqzMybadmyo"
    assert evidence["smoke"]["state"] == "stopped"
    assert evidence["smoke"]["tasks_after_stop"] == 0
    assert evidence["milestones"] == [
        "mounted PythonPackage:memsub",
        "container hydration passed",
        "loaded three model checkpoint shards",
        "entered registered archived M1 replay validation",
    ]
    assert evidence["failure"] == {
        "error_type": "ValueError",
        "document_id": "financial/00000",
        "arm": "eviction-0.25",
        "metric": "aggregation_axis.mean_kl",
        "actual": 0.068229,
        "registered_archive": 0.063958,
        "absolute_difference": 0.004271,
        "message": (
            "financial/00000: archived M1 replay failed for "
            "eviction-0.25: ['aggregation_axis.mean_kl: "
            "0.068229 != 0.063958']"
        ),
    }
    assert evidence["outputs"] == {
        "q1_smoke_artifact_retrieved": False,
        "independent_analyzer_run": False,
        "full_q1_launched": False,
        "q2_q3_launched": False,
    }
    assert evidence["cost_estimate"]["usd"] < (
        evidence["cost_estimate"]["campaign_bound_usd"]
    )


def test_mergecert_q1_image_packages_memsub_as_importable_python_source():
    runner = _load_module(RUNNER, "mergecert_q1_image_contract")
    image_impl = next(
        value
        for name, value in vars(runner.image).items()
        if name.startswith("_sync_original_")
    )

    assert image_impl._added_python_source_set == {"memsub"}


def test_mergecert_q1_registration_source_pins_exact_population_and_archives():
    registration = json.loads(Q1_REGISTRATION_SOURCE.read_text())

    assert registration["schema"] == "mergecert-q1-registration-source-v1"
    assert registration["tokenizer_revision"] == Q1_TOKENIZER_REVISION
    assert registration["population_doc_ids"] == [
        "financial/00000",
        "financial/00008",
        "financial/00016",
        "financial/00024",
        "financial/00032",
        "legal/00000",
        "legal/00008",
        "legal/00016",
        "legal/00024",
        "legal/00032",
        "code/00008",
        "code/00016",
        "code/00024",
        "code/00032",
        "code/00040",
        "literature/00000",
        "literature/00008",
        "literature/00016",
        "literature/00024",
        "literature/00032",
    ]
    assert registration["smoke_doc_ids"] == [
        "financial/00000",
        "financial/00008",
    ]
    assert set(registration["archive_sha256"]) == {
        f"{domain}-evict{ratio:.2f}.json"
        for domain in ("financial", "legal", "code", "literature")
        for ratio in (0.0, 0.25, 0.40)
    }
    assert all(
        len(value) == 64
        for value in registration["archive_sha256"].values()
    )
    assert registration["eviction_source_start"]["code/00024"] == 845
    assert all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in registration["eviction_source_start"].values()
    )


def test_mergecert_q1_registration_extractor_is_cpu_read_only_and_no_model():
    source = Q1_REGISTRATION_RUNNER.read_text()
    constants = _literal_constants(Q1_REGISTRATION_RUNNER)

    assert constants["MODEL_ID"] == "Qwen/Qwen3-4B-Instruct-2507"
    assert constants["TOKENIZER_REVISION"] == Q1_TOKENIZER_REVISION
    assert "gpu=" not in source
    assert "artifacts.commit" not in source
    assert 'local_files_only=True' in source
    assert '"HF_HUB_OFFLINE": "1"' in source
    assert "open(" in source
    for forbidden in (
        "AutoModel",
        "build_runtime",
        "torch",
        "volume put",
        "upload_file",
    ):
        assert forbidden not in source


def test_mergecert_q1_registration_extractor_hashes_exact_tokenizer_revision(
    tmp_path, monkeypatch
):
    extractor = _load_module(
        Q1_REGISTRATION_RUNNER,
        "mergecert_q1_registration_tokenizer_provenance",
    )
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    contents = {
        "config.json": b"config",
        "merges.txt": b"merges",
        "tokenizer.json": b"tokenizer",
        "tokenizer_config.json": b"tokenizer-config",
        "vocab.json": b"vocab",
    }
    for name, value in contents.items():
        (snapshot / name).write_bytes(value)
    (snapshot / "model.safetensors").write_bytes(b"must-not-be-emitted")
    files = {
        name: hashlib.sha256(value).hexdigest()
        for name, value in contents.items()
    }
    artifact_sha256 = hashlib.sha256(
        json.dumps(
            files, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    monkeypatch.setattr(
        extractor, "Q1_TOKENIZER_FILES_SHA256", files, raising=False
    )
    monkeypatch.setattr(
        extractor,
        "Q1_TOKENIZER_ARTIFACT_SHA256",
        artifact_sha256,
        raising=False,
    )

    class ExactRevisionTokenizer:
        @classmethod
        def from_pretrained(
            cls, model_id, *, revision, local_files_only
        ):
            if (
                model_id != "Qwen/Qwen3-4B-Instruct-2507"
                or revision != Q1_TOKENIZER_REVISION
                or local_files_only is not True
            ):
                raise AssertionError("tokenizer revision was not exact")
            return object()

    def snapshot_download(
        *,
        repo_id,
        revision,
        local_files_only,
        allow_patterns,
    ):
        if (
            repo_id != "Qwen/Qwen3-4B-Instruct-2507"
            or revision != Q1_TOKENIZER_REVISION
            or local_files_only is not True
            or not allow_patterns
        ):
            raise AssertionError("snapshot revision was not exact")
        return str(snapshot)

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        types.SimpleNamespace(AutoTokenizer=ExactRevisionTokenizer),
    )
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        types.SimpleNamespace(snapshot_download=snapshot_download),
    )

    assert hasattr(extractor, "_load_tokenizer_with_provenance")
    _, provenance = extractor._load_tokenizer_with_provenance()

    assert provenance == {
        "model_id": "Qwen/Qwen3-4B-Instruct-2507",
        "revision": Q1_TOKENIZER_REVISION,
        "files_sha256": files,
        "artifact_sha256": artifact_sha256,
    }


@pytest.mark.parametrize("mutation", ("missing", "extra", "wrong"))
def test_mergecert_q1_tokenizer_manifest_rejects_any_file_drift(
    tmp_path, mutation
):
    binding = _load_module(
        ROOT / "memsub" / "mergecert_q1_registration.py",
        f"mergecert_q1_tokenizer_manifest_{mutation}",
    )
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    contents = {
        "config.json": b"config",
        "merges.txt": b"merges",
        "tokenizer.json": b"tokenizer",
        "tokenizer_config.json": b"tokenizer-config",
        "vocab.json": b"vocab",
    }
    expected = {
        name: hashlib.sha256(value).hexdigest()
        for name, value in contents.items()
    }
    for name, value in contents.items():
        (snapshot / name).write_bytes(value)
    if mutation == "missing":
        (snapshot / "merges.txt").unlink()
    elif mutation == "extra":
        (snapshot / "special_tokens_map.json").write_bytes(b"extra")
    else:
        (snapshot / "vocab.json").write_bytes(b"wrong")

    assert hasattr(binding, "tokenizer_artifact_digests")
    with pytest.raises(ValueError, match="tokenizer artifact"):
        binding.tokenizer_artifact_digests(
            snapshot, expected_files_sha256=expected
        )


def test_mergecert_q1_pins_the_exact_five_tokenizer_artifacts():
    binding = _load_module(
        ROOT / "memsub" / "mergecert_q1_registration.py",
        "mergecert_q1_exact_tokenizer_manifest",
    )

    assert binding.Q1_TOKENIZER_FILES_SHA256 == Q1_TOKENIZER_FILES_SHA256
    assert (
        binding.Q1_TOKENIZER_ARTIFACT_SHA256
        == Q1_TOKENIZER_ARTIFACT_SHA256
    )


@pytest.mark.parametrize("mode", ("duplicate", "incomplete"))
def test_mergecert_q1_registration_extractor_rejects_bad_source_rows(
    tmp_path, mode, monkeypatch
):
    extractor = _load_module(
        Q1_REGISTRATION_RUNNER,
        f"mergecert_q1_registration_source_{mode}",
    )
    rows = [{"doc_id": "financial/00000", "text": "first"}]
    if mode == "duplicate":
        rows.append({"doc_id": "financial/00000", "text": "second"})
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "financial.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows)
    )
    monkeypatch.setattr(extractor, "CORPUS_ROOT", str(corpus))
    expected = (
        {"financial/00000"}
        if mode == "duplicate"
        else {"financial/00000", "financial/00008"}
    )

    with pytest.raises(ValueError, match=mode):
        extractor._load_source_texts(expected)


def test_mergecert_q1_registration_binding_is_finalized_and_exact():
    runner = _load_module(RUNNER, "mergecert_q1_final_binding")
    registration = (
        ROOT / "plans" / "260728-mergecert-q1" / "q1-registration.json"
    )

    assert runner.Q1_REGISTRATION_SHA256 == Q1_REGISTRATION_SHA256
    assert hashlib.sha256(registration.read_bytes()).hexdigest() == (
        Q1_REGISTRATION_SHA256
    )


@pytest.mark.parametrize("mutation", ("wrong_hash", "duplicate"))
def test_mergecert_q1_runner_rejects_live_source_integrity_drift(
    tmp_path, mutation
):
    runner = _load_module(
        RUNNER, f"mergecert_q1_live_source_{mutation}"
    )
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    manifest = corpus / "manifest.json"
    items = tmp_path / "all-items.json"
    manifest.write_bytes(b"manifest")
    items.write_bytes(b"items")
    rows = [{"doc_id": "financial/00000", "text": "source"}]
    if mutation == "duplicate":
        rows.append({"doc_id": "financial/00000", "text": "duplicate"})
    (corpus / "financial.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows)
    )
    registration = {
        "source_hashes": {
            "corpus_manifest_sha256": hashlib.sha256(
                b"manifest"
            ).hexdigest(),
            "all_items_sha256": hashlib.sha256(b"items").hexdigest(),
            "source_document_sha256": {
                "financial/00000": hashlib.sha256(b"source").hexdigest()
            },
        }
    }
    if mutation == "wrong_hash":
        registration["source_hashes"]["source_document_sha256"][
            "financial/00000"
        ] = "f" * 64

    assert hasattr(runner, "_verify_q1_source_integrity")
    with pytest.raises(ValueError, match="source document hash|duplicate"):
        runner._verify_q1_source_integrity(
            registration,
            ["financial/00000"],
            corpus_root=str(corpus),
            manifest_path=str(manifest),
            items_path=str(items),
        )


def test_mergecert_q1_runner_checks_live_sources_before_model_runtime():
    runner = _load_module(RUNNER, "mergecert_q1_early_source_gate")
    calls = [
        node
        for node in ast.walk(
            next(
                node
                for node in ast.parse(RUNNER.read_text()).body
                if isinstance(node, ast.FunctionDef)
                and node.name == "_run_q1"
            )
        )
        if isinstance(node, ast.Call)
    ]
    names = [
        (
            call.func.id
            if isinstance(call.func, ast.Name)
            else call.func.attr
            if isinstance(call.func, ast.Attribute)
            else ""
        )
        for call in calls
    ]

    assert hasattr(runner, "_verify_q1_source_integrity")
    assert hasattr(runner, "_verify_q1_tokenizer_integrity")
    assert names.index("_verify_q1_source_integrity") < names.index(
        "build_runtime"
    )
    assert names.index("_verify_q1_tokenizer_integrity") < names.index(
        "build_runtime"
    )


def test_mergecert_q1_runtime_build_is_revision_pinned_and_offline():
    tree = ast.parse(RUNNER.read_text())
    run_q1 = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_run_q1"
    )
    call = next(
        node
        for node in ast.walk(run_q1)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_runtime"
    )
    keywords = {item.arg: ast.literal_eval(item.value) for item in call.keywords}

    assert keywords == {
        "reference": True,
        "revision": Q1_TOKENIZER_REVISION,
        "local_files_only": True,
    }


def test_reference_runtime_forwards_revision_to_model_and_tokenizer(
    monkeypatch,
):
    import memsub.runtime as runtime_module
    from memsub import reference_config

    sentinel = object()

    class ExactPinnedRuntime:
        @classmethod
        def load(
            cls,
            model_id,
            *,
            device,
            dtype,
            attention_impl,
            revision,
            local_files_only,
        ):
            if (
                model_id != "Qwen/Qwen3-4B-Instruct-2507"
                or revision != Q1_TOKENIZER_REVISION
                or local_files_only is not True
            ):
                raise ValueError("reference runtime is unpinned")
            return sentinel

    monkeypatch.setattr(
        runtime_module, "HFModelRuntime", ExactPinnedRuntime
    )

    assert (
        reference_config.build_runtime(
            reference=True,
            revision=Q1_TOKENIZER_REVISION,
            local_files_only=True,
        )
        is sentinel
    )


def test_hf_runtime_load_pins_model_and_tokenizer_to_same_snapshot(
    monkeypatch,
):
    from memsub.runtime import HFModelRuntime

    calls = {}

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, model_id, **kwargs):
            calls["tokenizer"] = (model_id, kwargs)
            return object()

    class FakeModel:
        @classmethod
        def from_pretrained(cls, model_id, **kwargs):
            calls["model"] = (model_id, kwargs)
            return cls()

        def to(self, device):
            calls["device"] = device
            return self

        def eval(self):
            return self

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        types.SimpleNamespace(
            AutoTokenizer=FakeTokenizer,
            AutoModelForCausalLM=FakeModel,
        ),
    )
    HFModelRuntime.load(
        "Qwen/Qwen3-4B-Instruct-2507",
        device="cpu",
        revision=Q1_TOKENIZER_REVISION,
        local_files_only=True,
    )

    for component in ("tokenizer", "model"):
        model_id, kwargs = calls[component]
        assert model_id == "Qwen/Qwen3-4B-Instruct-2507"
        assert kwargs["revision"] == Q1_TOKENIZER_REVISION
        assert kwargs["local_files_only"] is True


def test_mergecert_q1_binder_updates_one_literal_and_provenance(
    tmp_path,
):
    assert Q1_REGISTRATION_BINDER.exists()
    binder = _load_module(
        Q1_REGISTRATION_BINDER, "mergecert_q1_registration_binder"
    )
    root, binding_path, provenance_path, extracted, reviewed_bytes = (
        _prepare_binder_root(tmp_path)
    )
    expected_sha256 = hashlib.sha256(reviewed_bytes).hexdigest()

    result = binder.bind_registration(extracted, root=root)

    target = (
        root
        / "plans"
        / "260728-mergecert-q1"
        / "q1-registration.json"
    )
    provenance = json.loads(provenance_path.read_text())
    assert result == {
        "path": target,
        "sha256": expected_sha256,
    }
    assert target.read_bytes() == reviewed_bytes
    assert (
        f'Q1_REGISTRATION_SHA256 = "{expected_sha256}"'
        in binding_path.read_text()
    )
    assert provenance["q1_registration"] == {
        "path": "plans/260728-mergecert-q1/q1-registration.json",
        "remote_path": "/artifacts/mergecert-q1/q1-registration.json",
        "sha256": expected_sha256,
        "status": "finalized and hash-bound",
    }


def test_mergecert_q1_binder_rejects_noncanonical_or_repeated_binding(
    tmp_path,
):
    binder = _load_module(
        Q1_REGISTRATION_BINDER, "mergecert_q1_registration_one_shot"
    )
    root, binding_path, _, extracted, reviewed_bytes = _prepare_binder_root(
        tmp_path
    )
    extracted.write_bytes(reviewed_bytes.rstrip())

    with pytest.raises(ValueError, match="canonical"):
        binder.bind_registration(extracted, root=root)
    assert "Q1_REGISTRATION_SHA256 = Q1_REGISTRATION_PENDING" in (
        binding_path.read_text()
    )
    assert not (
        root
        / "plans"
        / "260728-mergecert-q1"
        / "q1-registration.json"
    ).exists()

    extracted.write_bytes(reviewed_bytes)
    binder.bind_registration(extracted, root=root)
    with pytest.raises(ValueError, match="already finalized|inconsistent"):
        binder.bind_registration(extracted, root=root)


def test_mergecert_q1_binder_rejects_inconsistent_pending_state(tmp_path):
    binder = _load_module(
        Q1_REGISTRATION_BINDER, "mergecert_q1_registration_inconsistent"
    )
    root, binding_path, provenance_path, extracted, _ = (
        _prepare_binder_root(tmp_path)
    )
    provenance = json.loads(provenance_path.read_text())
    provenance["q1_registration"]["sha256"] = "f" * 64
    provenance_path.write_text(
        json.dumps(provenance, indent=1, allow_nan=False) + "\n"
    )

    with pytest.raises(ValueError, match="inconsistent"):
        binder.bind_registration(extracted, root=root)
    assert "Q1_REGISTRATION_SHA256 = Q1_REGISTRATION_PENDING" in (
        binding_path.read_text()
    )


@pytest.mark.parametrize(
    ("location", "field"),
    (
        ("top", "raw_corpus"),
        ("tokenizer", "document_content"),
        ("source_hashes", "raw_corpus"),
        ("document", "document_content"),
        ("budget", "raw_corpus"),
    ),
)
def test_mergecert_q1_registration_schema_rejects_unknown_leakage_fields(
    tmp_path, location, field
):
    binder = _load_module(
        Q1_REGISTRATION_BINDER,
        f"mergecert_q1_registration_leak_{location}",
    )
    root, binding_path, _, extracted, _ = _prepare_binder_root(tmp_path)
    registration = _fake_final_registration()
    if location == "top":
        target = registration
    elif location == "tokenizer":
        target = registration["tokenizer"]
    elif location == "source_hashes":
        target = registration["source_hashes"]
    elif location == "document":
        target = registration["documents"][0]
    else:
        target = registration["documents"][0]["budgets"]["0.25"]
    target[field] = "private source body"
    extracted.write_text(
        json.dumps(registration, indent=1, allow_nan=False) + "\n"
    )

    with pytest.raises(ValueError, match="schema|unknown"):
        binder.bind_registration(extracted, root=root)
    assert "Q1_REGISTRATION_SHA256 = Q1_REGISTRATION_PENDING" in (
        binding_path.read_text()
    )


@pytest.mark.parametrize(
    ("operation", "failure_index"),
    (
        ("stage", 1),
        ("stage", 2),
        ("stage", 3),
        ("replace", 1),
        ("replace", 2),
        ("replace", 3),
    ),
)
def test_mergecert_q1_binder_faults_never_enable_partial_state(
    tmp_path, monkeypatch, operation, failure_index
):
    binder = _load_module(
        Q1_REGISTRATION_BINDER,
        f"mergecert_q1_registration_fault_{operation}_{failure_index}",
    )
    root, binding_path, _, extracted, _ = _prepare_binder_root(tmp_path)
    function_name = (
        "_stage_bytes" if operation == "stage" else "_replace_staged"
    )
    original = getattr(binder, function_name)
    calls = 0

    def fail_at_index(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == failure_index:
            raise OSError(f"injected {operation} failure {failure_index}")
        return original(*args, **kwargs)

    monkeypatch.setattr(binder, function_name, fail_at_index)

    with pytest.raises(OSError, match="injected"):
        binder.bind_registration(extracted, root=root)
    assert "Q1_REGISTRATION_SHA256 = Q1_REGISTRATION_PENDING" in (
        binding_path.read_text()
    )


def test_mergecert_q1_registration_extractor_builds_runner_shaped_exact_budget():
    extractor = _load_module(
        Q1_REGISTRATION_RUNNER, "mergecert_q1_registration_extractor"
    )

    class IdentityTokenizer:
        def encode(self, value, add_special_tokens=False):
            assert add_special_tokens is False
            return list(range(4096)) if value == "source" else list(value)

        def decode(self, token_ids):
            return list(token_ids)

    document = extractor.build_document_registration(
        IdentityTokenizer(),
        doc_id="code/00024",
        text="source",
        anchor_chunk_token_start=845,
        registered_source_start=845,
    )

    assert document == {
        "doc_id": "code/00024",
        "context_start": 0,
        "source_context_token_count": 4096,
        "model_input_token_count": 4096,
        "budgets": {
            "0.25": {
                "requested_evicted_token_count": 1024,
                "eviction_source_start": 845,
                "eviction_source_end": 1869,
                "physical_before_count": 4096,
                "physical_after_count": 3072,
                "evicted_token_count": 1024,
                "retained_token_count": 3072,
                "merge_target_retained": 3072,
            },
            "0.40": {
                "requested_evicted_token_count": 1638,
                "eviction_source_start": 845,
                "eviction_source_end": 2483,
                "physical_before_count": 4096,
                "physical_after_count": 2458,
                "evicted_token_count": 1638,
                "retained_token_count": 2458,
                "merge_target_retained": 2458,
            },
        },
    }


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


def test_mergecert_q1_gates_real_attention_prefill_on_auxiliary_replay():
    tree = ast.parse(RUNNER.read_text())
    run_q1 = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_run_q1"
    )
    run_source = ast.unparse(run_q1)

    replay_prefill = (
        "replay_full_cache, _ = runtime.prefill(context['context_ids'])"
    )
    q1_prefill = (
        "q1_full_cache, _, attention_mass = "
        "prefill_with_real_attention(runtime, context['context_ids'])"
    )
    assert replay_prefill in run_source
    assert q1_prefill in run_source
    assert (
        run_source.index(replay_prefill)
        < run_source.index("_verify_archived_replay(replay_report, archive")
        < run_source.index(q1_prefill)
    )


def test_mergecert_q1_uses_sdpa_only_for_auxiliary_replay_and_one_q1_prefill():
    source = RUNNER.read_text()
    tree = ast.parse(source)
    run_q1 = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_run_q1"
    )
    run_source = ast.unparse(run_q1)

    assert "_prefill_q1_document" not in run_source
    assert (
        "candidate_caches = {'control-0.00': "
        "q1_full_cache.clone_detached()}"
        in run_source
    )
    assert "eviction = q1_full_cache.clone_detached()" in run_source
    assert "merge_cache(q1_full_cache, attention_mass, plan)" in run_source
    assert "cache=q1_full_cache" in run_source
    assert "full_cache=q1_full_cache" in run_source
    assert "replay_eviction = replay_full_cache.clone_detached()" in run_source
    assert "full_cache=replay_full_cache" in run_source
    assert "_verify_archived_replay(replay_report, archive" in run_source
    assert "reference_cache =" not in run_source


def test_mergecert_q1_records_exact_versioned_execution_semantics():
    runner = _load_module(RUNNER, "mergecert_q1_execution_semantics")
    constants = _literal_constants(RUNNER)
    semantics = runner._q1_execution_semantics()

    assert constants["Q1_EXECUTION_SEMANTICS_VERSION"] == (
        Q1_EXECUTION_SEMANTICS_VERSION
    )
    assert semantics == {
        "version": Q1_EXECUTION_SEMANTICS_VERSION,
        "archive_replay_prefill": {
            "attention_backend": "sdpa",
            "scope": "auxiliary-archive-replay-gate",
        },
        "reported_five_arm_prefill": {
            "attention_backend": "eager",
            "mode": "real-attention",
            "cache_policy": "single-common-prefill",
        },
        "continuation_and_scoring": {
            "attention_backend": "sdpa",
            "backend_state": "restored-configured",
        },
    }
    assert runner._q1_provenance()["execution_semantics"] == semantics


def test_mergecert_q1_zero_progress_legacy_partial_smoke_resets_wholly_fresh():
    runner = _load_module(RUNNER, "mergecert_q1_legacy_smoke_resume")
    selected_doc_ids = ["financial/00000", "financial/00008"]
    fresh = _q1_resume_state(runner)
    prior = _q1_resume_state(
        runner, fingerprint=_q1_fingerprint(runtime_version="stale")
    )
    prior["provenance"].pop("execution_semantics")
    prior.pop("execution_semantics")
    prior.pop("compatibility_fingerprint_schema")
    prior["peak_gpu_bytes"] = 123
    prior["documents"] = [{"doc_id": "financial/00000"}]
    report_counts = {
        "control-0.00": 1,
        "eviction-0.25": 1,
        "eviction-0.40": 0,
        "merge-0.25": 0,
        "merge-0.40": 0,
    }
    for arm_name, count in report_counts.items():
        prior["arms"][arm_name]["reports"] = [
            {"doc_id": "financial/00000"}
        ][:count]
    prior["archived_m1"]["replay_checks"] = [
        {
            "doc_id": "financial/00000",
            "arm": arm_name,
            "pass": True,
        }
        for arm_name in ("control-0.00", "eviction-0.25")
    ]

    resumed = runner._resume_q1_state(prior, fresh, selected_doc_ids)

    assert resumed is fresh
    assert resumed["documents"] == []
    assert all(not arm["reports"] for arm in resumed["arms"].values())
    assert resumed["archived_m1"]["replay_checks"] == []
    assert resumed["compatibility_fingerprint"] == (
        _q1_fingerprint().to_dict()
    )
    assert "peak_gpu_bytes" not in resumed


def test_mergecert_q1_zero_progress_stale_fingerprint_is_reset():
    runner = _load_module(RUNNER, "mergecert_q1_stale_fingerprint_reset")
    fresh = _q1_resume_state(runner)
    prior = _q1_resume_state(
        runner, fingerprint=_q1_fingerprint(runtime_version="stale")
    )

    resumed = runner._resume_q1_state(
        prior, fresh, fresh["sample_doc_ids"]
    )

    assert resumed is fresh
    assert resumed["compatibility_fingerprint"] != prior[
        "compatibility_fingerprint"
    ]


def test_mergecert_q1_completed_prefix_rejects_old_execution_semantics():
    runner = _load_module(RUNNER, "mergecert_q1_old_semantics_resume")
    fresh = _q1_resume_state(runner, done=1)
    prior = _q1_resume_state(runner, done=1)
    prior["execution_semantics"]["archive_replay_prefill"][
        "attention_backend"
    ] = "eager"

    with pytest.raises(ValueError, match="execution semantics"):
        runner._resume_q1_state(
            prior, fresh, fresh["sample_doc_ids"]
        )


def test_mergecert_q1_matching_completed_prefix_is_preserved():
    runner = _load_module(RUNNER, "mergecert_q1_matching_resume")
    fresh = _q1_resume_state(runner)
    prior = _q1_resume_state(runner, done=1)

    resumed = runner._resume_q1_state(
        prior, fresh, fresh["sample_doc_ids"]
    )

    assert resumed is prior
    assert resumed["done_documents"] == 1
    assert resumed["documents"] == [{"doc_id": "financial/00000"}]
    assert all(
        arm["reports"] == [{"doc_id": "financial/00000"}]
        for arm in resumed["arms"].values()
    )


@pytest.mark.parametrize("mutation", ("digest", "live"))
def test_mergecert_q1_completed_prefix_rejects_fingerprint_drift(mutation):
    runner = _load_module(
        RUNNER, f"mergecert_q1_bad_fingerprint_resume_{mutation}"
    )
    fresh = _q1_resume_state(runner)
    prior = _q1_resume_state(runner, done=1)
    if mutation == "digest":
        prior["compatibility_fingerprint_sha256"] = (
            "sha256:" + "f" * 64
        )
    else:
        stale = _q1_fingerprint(runtime_version="stale")
        prior["compatibility_fingerprint"] = stale.to_dict()
        prior["compatibility_fingerprint_sha256"] = stale.digest()

    with pytest.raises(ValueError, match="compatibility fingerprint"):
        runner._resume_q1_state(
            prior, fresh, fresh["sample_doc_ids"]
        )


def test_mergecert_q1_releases_auxiliary_and_document_gpu_caches_in_order():
    tree = ast.parse(RUNNER.read_text())
    run_q1 = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_run_q1"
    )
    run_source = ast.unparse(run_q1)

    document_cleanup = (
        "del candidate_caches, q1_full_cache, full_predictions"
    )
    auxiliary_cleanup = [
        "del replay_report, replay_candidate_caches",
        "del replay_full_predictions, replay_full_cache",
        "del replay_eviction",
    ]
    q1_prefill = (
        "q1_full_cache, _, attention_mass = "
        "prefill_with_real_attention(runtime, context['context_ids'])"
    )
    assert (
        run_source.index("_verify_archived_replay(replay_report, archive")
        < min(run_source.index(cleanup) for cleanup in auxiliary_cleanup)
        <= max(run_source.index(cleanup) for cleanup in auxiliary_cleanup)
        < run_source.index(q1_prefill)
    )
    assert (
        run_source.index(document_cleanup)
        < run_source.index("torch.cuda.empty_cache()")
    )


def test_mergecert_q1_resume_discards_only_an_unfinished_document():
    runner = _load_module(RUNNER, "mergecert_q1_partial_resume")
    state = {
        "done_documents": 1,
        "documents": [
            {"doc_id": "financial/00000"},
            {"doc_id": "financial/00008"},
        ],
        "arms": {
            arm: {
                "reports": [
                    {"doc_id": "financial/00000"},
                    {"doc_id": "financial/00008"},
                ]
            }
            for arm in (
                "control-0.00",
                "eviction-0.25",
                "eviction-0.40",
                "merge-0.25",
                "merge-0.40",
            )
        },
        "archived_m1": {
            "replay_checks": [
                {"doc_id": doc_id, "arm": arm, "pass": True}
                for doc_id in ("financial/00000", "financial/00008")
                for arm in (
                    "control-0.00",
                    "eviction-0.25",
                    "eviction-0.40",
                )
            ],
            "replay_pass": True,
        },
    }

    runner._restore_q1_completed_prefix(
        state,
        ["financial/00000", "financial/00008"],
    )

    assert state["documents"] == [{"doc_id": "financial/00000"}]
    assert all(
        arm["reports"] == [{"doc_id": "financial/00000"}]
        for arm in state["arms"].values()
    )
    assert len(state["archived_m1"]["replay_checks"]) == 3
    assert state["archived_m1"]["replay_pass"] is False


def test_mergecert_q1_reconstructs_the_original_short_archived_m1_context():
    runner = _load_module(RUNNER, "mergecert_q1_short_context_replay")

    class IdentityTokenizer:
        def encode(self, value, add_special_tokens=False):
            assert add_special_tokens is False
            return list(range(3921)) if value == "source" else list(value)

        def decode(self, token_ids):
            return list(token_ids)

    reconstructed = runner._reconstruct_q1_context_ids(
        IdentityTokenizer(), "source", chunk_token_start=0
    )

    assert reconstructed["context_start"] == 0
    assert reconstructed["source_context_token_count"] == 3921
    assert reconstructed["model_input_token_count"] == 3921
    assert reconstructed["context_ids"] == list(range(3921))


@pytest.mark.parametrize(
    ("source_tokens", "model_tokens", "ratio", "evicted", "retained"),
    (
        (3921, 3921, 0.25, 980, 2941),
        (3921, 3921, 0.40, 1568, 2353),
        (4096, 4096, 0.25, 1024, 3072),
        (4096, 4096, 0.40, 1638, 2458),
    ),
)
def test_mergecert_q1_matches_merge_to_each_document_eviction_budget(
    source_tokens, model_tokens, ratio, evicted, retained
):
    runner = _load_module(RUNNER, "mergecert_q1_per_document_budget")

    budget = runner._q1_document_budget(source_tokens, model_tokens, ratio)
    plan = runner._q1_merge_plan(model_tokens, retained)

    assert budget == {
        "source_context_token_count": source_tokens,
        "model_input_token_count": model_tokens,
        "requested_evicted_token_count": evicted,
        "eviction_source_start": 4,
        "eviction_source_end": 4 + evicted,
        "physical_before_count": model_tokens,
        "physical_after_count": retained,
        "evicted_token_count": evicted,
        "retained_token_count": retained,
        "merge_target_retained": retained,
    }
    assert plan.sequence_length == model_tokens
    assert plan.target_retained == retained


def test_mergecert_q1_uses_the_eviction_cache_measured_physical_budget():
    runner = _load_module(RUNNER, "mergecert_q1_measured_budget")

    budget = runner._q1_document_budget(
        4096,
        4000,
        0.40,
        evicted_token_count=1000,
        eviction_source_start=3000,
        eviction_source_end=4638,
        physical_before_count=4000,
        physical_after_count=3000,
    )

    assert budget == {
        "source_context_token_count": 4096,
        "model_input_token_count": 4000,
        "requested_evicted_token_count": 1638,
        "eviction_source_start": 3000,
        "eviction_source_end": 4638,
        "physical_before_count": 4000,
        "physical_after_count": 3000,
        "evicted_token_count": 1000,
        "retained_token_count": 3000,
        "merge_target_retained": 3000,
    }


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
    ("run_tag", "output_name"),
    (
        ("q1-triggered", "pilot-q1-triggered"),
        ("a", "pilot-a"),
        ("b", "pilot-b"),
    ),
)
def test_q2_pilot_maps_registered_and_legacy_tags_to_isolated_outputs(
    monkeypatch, run_tag, output_name
):
    runner = _load_module(
        Q2_RUNNER, f"mergecert_q2_pilot_contract_{run_tag}"
    )
    calls = []

    def fake_run_capture(**kwargs):
        calls.append(kwargs)
        return {"output": kwargs["output_name"]}

    monkeypatch.setattr(runner, "_run_capture", fake_run_capture)

    result = runner.q2_pilot.get_raw_f()(run_tag, 16)

    assert result == {"output": output_name}
    assert calls == [
        {
            "slice_idx": 0,
            "n_slices": 1,
            "limit": 16,
            "output_name": output_name,
            "verify_mode_parity": True,
        }
    ]


def test_q2_pilot_complete_resume_is_fully_validated_and_idempotent(
    tmp_path, monkeypatch
):
    from memsub import reference_config

    runner = _load_module(
        Q2_RUNNER, "mergecert_q2_pilot_complete_resume"
    )
    fixture = _write_q2_pilot_fixture(
        tmp_path, runner, ("q1-triggered",)
    )
    _configure_q2_pilot_fixture(runner, monkeypatch, fixture)
    runtime_calls = []
    monkeypatch.setattr(
        reference_config,
        "build_runtime",
        lambda reference: runtime_calls.append(reference)
        or _q2_fake_runtime(),
    )
    output_dir = fixture["capture_root"] / "pilot-q1-triggered"
    before = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in output_dir.iterdir()
    }

    result = runner._run_capture(
        slice_idx=0,
        n_slices=1,
        limit=16,
        output_name="pilot-q1-triggered",
        verify_mode_parity=True,
    )

    after = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in output_dir.iterdir()
    }
    assert result["items"] == 16
    assert result["chunks"] == 1
    assert runtime_calls == [True]
    assert after == before


def test_q2_pilot_resume_rejects_semantic_tamper_before_runtime(
    tmp_path, monkeypatch
):
    from memsub import reference_config

    runner = _load_module(
        Q2_RUNNER, "mergecert_q2_pilot_tampered_resume"
    )
    fixture = _write_q2_pilot_fixture(
        tmp_path, runner, ("q1-triggered",)
    )
    _configure_q2_pilot_fixture(runner, monkeypatch, fixture)
    _rewrite_q2_pilot_array(fixture, 0.25, "doc_ids", "doc-wrong")
    runtime_calls = []
    monkeypatch.setattr(
        reference_config,
        "build_runtime",
        lambda reference: runtime_calls.append(reference)
        or _q2_fake_runtime(),
    )

    with pytest.raises(ValueError, match="registered manifest"):
        runner._run_capture(
            slice_idx=0,
            n_slices=1,
            limit=16,
            output_name="pilot-q1-triggered",
            verify_mode_parity=True,
        )
    assert runtime_calls == []


def test_q2_pilot_resume_rejects_live_fingerprint_drift(
    tmp_path, monkeypatch
):
    from memsub import reference_config

    runner = _load_module(
        Q2_RUNNER, "mergecert_q2_pilot_live_fingerprint_drift"
    )
    fixture = _write_q2_pilot_fixture(
        tmp_path, runner, ("q1-triggered",)
    )
    _configure_q2_pilot_fixture(runner, monkeypatch, fixture)
    stale = _q2_fingerprint(
        runtime_version="hf-transformers-4.55.2+torch-2.7.1+cu999"
    )
    monkeypatch.setattr(
        reference_config,
        "build_runtime",
        lambda reference: _q2_fake_runtime(stale),
    )

    with pytest.raises(ValueError, match="compatibility fingerprint"):
        runner._run_capture(
            slice_idx=0,
            n_slices=1,
            limit=16,
            output_name="pilot-q1-triggered",
            verify_mode_parity=True,
        )


def test_q2_registered_pilot_validates_both_ratios_and_trigger_provenance(
    tmp_path, monkeypatch
):
    runner = _load_module(
        Q2_RUNNER, "mergecert_q2_registered_pilot_validation"
    )
    fixture = _write_q2_pilot_fixture(
        tmp_path, runner, ("q1-triggered",)
    )
    commits = _configure_q2_pilot_fixture(runner, monkeypatch, fixture)

    result = runner.validate_pilot.get_raw_f()()

    assert result["pass"] is True
    assert result["validation_mode"] == "single-registered-run"
    assert result["run_tags"] == ["q1-triggered"]
    assert result["q1_trigger"] == fixture["trigger"]
    assert result["q1_trigger_sha256"] == fixture["trigger_sha256"]
    assert result["ratios"] == [0.25, 0.40]
    assert result["audits"]["0.25"]["rows"] == 16
    assert result["audits"]["0.40"]["rows"] == 16
    assert commits == [1]
    verdict_path = (
        fixture["capture_root"]
        / "pilot-q1-triggered"
        / "pilot-verdict.json"
    )
    assert verdict_path.exists()
    assert set(path.name for path in verdict_path.parent.iterdir()) == {
        "state.json",
        "ratio-0.25-rows-00000-00016.npz",
        "ratio-0.40-rows-00000-00016.npz",
        "pilot-verdict.json",
    }
    assert result["validator_version"] == runner.PILOT_VALIDATOR_VERSION
    assert result["validation_mode"] == "single-registered-run"
    assert result["run_tag"] == "q1-triggered"
    assert result["state"]["sha256"] == hashlib.sha256(
        (
            fixture["capture_root"]
            / "pilot-q1-triggered"
            / "state.json"
        ).read_bytes()
    ).hexdigest()
    assert set(result["artifacts"]) == {"0.25", "0.40"}
    assert verdict_path.read_bytes() == runner._canonical_json_bytes(result)
    assert runner._require_registered_pilot_verdict() == result
    verdict_bytes = verdict_path.read_bytes()
    assert runner.validate_pilot.get_raw_f()() == result
    assert verdict_path.read_bytes() == verdict_bytes
    assert commits == [1, 1]

    state_path = fixture["capture_root"] / "pilot-q1-triggered" / "state.json"
    state = json.loads(state_path.read_text())
    state["q1_trigger_sha256"] = "0" * 64
    state_path.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="registered inputs"):
        runner.validate_pilot.get_raw_f()()


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("item_ids", "item-99"),
        ("doc_ids", "doc-wrong"),
        ("domain", "legal"),
        ("pred_raw", "B"),
        ("pred_merge", "E"),
        ("y", 1),
        ("raw_correct", 0),
        ("in_e1", 1),
    ),
)
def test_q2_registered_pilot_rejects_rehashed_manifest_row_tampering(
    tmp_path, monkeypatch, key, value
):
    runner = _load_module(
        Q2_RUNNER, f"mergecert_q2_pilot_tamper_{key}"
    )
    fixture = _write_q2_pilot_fixture(
        tmp_path, runner, ("q1-triggered",)
    )
    _configure_q2_pilot_fixture(runner, monkeypatch, fixture)
    _rewrite_q2_pilot_array(fixture, 0.25, key, value)

    with pytest.raises(ValueError, match="Q2 pilot"):
        runner.validate_pilot.get_raw_f()()


def test_q2_registered_pilot_rejects_extra_namespace_files(
    tmp_path, monkeypatch
):
    runner = _load_module(
        Q2_RUNNER, "mergecert_q2_pilot_extra_namespace"
    )
    fixture = _write_q2_pilot_fixture(
        tmp_path, runner, ("q1-triggered",)
    )
    _configure_q2_pilot_fixture(runner, monkeypatch, fixture)
    (
        fixture["capture_root"]
        / "pilot-q1-triggered"
        / "unexpected.json"
    ).write_text("{}")

    with pytest.raises(ValueError, match="namespace"):
        runner.validate_pilot.get_raw_f()()


def test_q2_registered_pilot_rejects_compatibility_fingerprint_tampering(
    tmp_path, monkeypatch
):
    runner = _load_module(
        Q2_RUNNER, "mergecert_q2_pilot_fingerprint_tamper"
    )
    fixture = _write_q2_pilot_fixture(
        tmp_path, runner, ("q1-triggered",)
    )
    _configure_q2_pilot_fixture(runner, monkeypatch, fixture)
    state_path = fixture["capture_root"] / "pilot-q1-triggered" / "state.json"
    state = json.loads(state_path.read_text())
    stale = _q2_fingerprint(runtime_version="stale")
    state["compatibility_fingerprint"] = stale.to_dict()
    state["compatibility_fingerprint_sha256"] = stale.digest()
    state_path.write_text(json.dumps(state))

    with pytest.raises(ValueError, match="compatibility fingerprint"):
        runner.validate_pilot.get_raw_f()()


def test_q2_legacy_pilots_keep_repeated_run_bit_identity_validation(
    tmp_path, monkeypatch
):
    runner = _load_module(
        Q2_RUNNER, "mergecert_q2_legacy_pilot_validation"
    )
    fixture = _write_q2_pilot_fixture(tmp_path, runner, ("a", "b"))
    commits = _configure_q2_pilot_fixture(runner, monkeypatch, fixture)

    result = runner.validate_pilot.get_raw_f()()

    assert result["pass"] is True
    assert result["validation_mode"] == "repeated-run-bit-identical"
    assert result["run_tags"] == ["a", "b"]
    assert result["comparisons"] == {
        "0.25": {"bit_identical": True, "unequal_arrays": []},
        "0.40": {"bit_identical": True, "unequal_arrays": []},
    }
    assert commits == [1]


def test_q2_capture_slice_requires_registered_pilot_before_capture(monkeypatch):
    runner = _load_module(
        Q2_RUNNER, "mergecert_q2_slice_pilot_gate"
    )
    events = []
    verdict = {"pass": True, "run_tag": "q1-triggered"}
    monkeypatch.setattr(
        runner,
        "_require_registered_pilot_verdict",
        lambda: events.append("gate") or verdict,
        raising=False,
    )
    monkeypatch.setattr(
        runner,
        "_run_capture",
        lambda **kwargs: events.append(("capture", kwargs)) or {"pass": True},
    )

    result = runner.q2_capture_slice.get_raw_f()(3, 8)

    assert result == {"pass": True}
    assert events[0] == "gate"
    assert events[1][0] == "capture"
    assert events[1][1]["required_pilot_verdict"] == verdict


def test_q2_capture_slice_stops_when_registered_pilot_is_missing(monkeypatch):
    runner = _load_module(
        Q2_RUNNER, "mergecert_q2_slice_missing_pilot"
    )
    captures = []

    def reject():
        raise ValueError("registered Q2 pilot verdict is missing")

    monkeypatch.setattr(
        runner, "_require_registered_pilot_verdict", reject, raising=False
    )
    monkeypatch.setattr(
        runner, "_run_capture", lambda **kwargs: captures.append(kwargs)
    )

    with pytest.raises(ValueError, match="pilot verdict is missing"):
        runner.q2_capture_slice.get_raw_f()(0, 8)
    assert captures == []


def test_q2_fleet_checks_registered_pilot_before_spawning(monkeypatch):
    runner = _load_module(Q2_RUNNER, "mergecert_q2_fleet_pilot_gate")
    events = []

    class Gate:
        @staticmethod
        def remote():
            events.append("gate")
            return {"pass": True}

    class Slice:
        @staticmethod
        def spawn(slice_idx, n_slices):
            events.append(("spawn", slice_idx, n_slices))
            return slice_idx

    monkeypatch.setattr(runner, "pilot_gate", Gate, raising=False)
    monkeypatch.setattr(runner, "q2_capture_slice", Slice)

    runner.fleet()

    assert events == [
        "gate",
        *(("spawn", slice_idx, 8) for slice_idx in range(8)),
    ]


def test_q2_fleet_stops_before_spawn_when_pilot_gate_fails(monkeypatch):
    runner = _load_module(Q2_RUNNER, "mergecert_q2_fleet_missing_pilot")
    spawned = []

    class Gate:
        @staticmethod
        def remote():
            raise ValueError("registered Q2 pilot verdict is missing")

    class Slice:
        @staticmethod
        def spawn(slice_idx, n_slices):
            spawned.append((slice_idx, n_slices))

    monkeypatch.setattr(runner, "pilot_gate", Gate, raising=False)
    monkeypatch.setattr(runner, "q2_capture_slice", Slice)

    with pytest.raises(ValueError, match="pilot verdict is missing"):
        runner.fleet()
    assert spawned == []


def test_q2_registered_pilot_gate_rejects_tampered_verdict(
    tmp_path, monkeypatch
):
    runner = _load_module(
        Q2_RUNNER, "mergecert_q2_tampered_pilot_verdict"
    )
    fixture = _write_q2_pilot_fixture(
        tmp_path, runner, ("q1-triggered",)
    )
    _configure_q2_pilot_fixture(runner, monkeypatch, fixture)
    runner.validate_pilot.get_raw_f()()
    verdict_path = (
        fixture["capture_root"]
        / "pilot-q1-triggered"
        / "pilot-verdict.json"
    )
    verdict = json.loads(verdict_path.read_text())
    verdict["pass"] = False
    verdict_path.write_text(json.dumps(verdict))

    with pytest.raises(ValueError, match="pilot verdict"):
        runner._require_registered_pilot_verdict()


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
        _q1_trigger(budget_mode="fixed-4096"),
        _q1_trigger(addendum_sha256="a" * 64),
        _q1_trigger(p0_verdict_sha256="b" * 64),
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
