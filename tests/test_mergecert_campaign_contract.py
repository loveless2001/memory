import ast
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest
import torch

from memsub.runtime import CompactedPrefixCache


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "modal-runners" / "modal-mergecert-p0-q1.py"
PROVENANCE = ROOT / "plans" / "260727-mergecert" / "source-provenance.json"
Q1_PROVENANCE = (
    ROOT / "plans" / "260728-mergecert-q1" / "source-provenance.json"
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
Q1_TOKENIZER_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
Q1_ADDENDUM_SHA256 = (
    "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509"
)
Q1_P0_VERDICT_SHA256 = (
    "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
)
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
        "status": "source-evidence-only; finalized CPU extraction pending",
    }
    assert provenance["q1_registration"] == {
        "path": "plans/260728-mergecert-q1/q1-registration.json",
        "remote_path": "/artifacts/mergecert-q1/q1-registration.json",
        "sha256": Q1_REGISTRATION_PENDING,
        "status": "pending CPU extraction and independent review",
    }


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
    (snapshot / "tokenizer.json").write_bytes(b"tokenizer-bytes")
    (snapshot / "tokenizer_config.json").write_bytes(b"config-bytes")
    (snapshot / "model.safetensors").write_bytes(b"must-not-be-emitted")

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

    files = {
        "tokenizer.json": hashlib.sha256(b"tokenizer-bytes").hexdigest(),
        "tokenizer_config.json": hashlib.sha256(b"config-bytes").hexdigest(),
    }
    assert provenance == {
        "model_id": "Qwen/Qwen3-4B-Instruct-2507",
        "revision": Q1_TOKENIZER_REVISION,
        "files_sha256": files,
        "artifact_sha256": hashlib.sha256(
            json.dumps(
                files,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    }


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


def test_mergecert_q1_registration_binding_is_explicitly_pending():
    runner = _load_module(RUNNER, "mergecert_q1_pending_binding")

    assert runner.Q1_REGISTRATION_SHA256 == Q1_REGISTRATION_PENDING


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
    assert names.index("_verify_q1_source_integrity") < names.index(
        "build_runtime"
    )


def test_mergecert_q1_binder_updates_one_literal_and_provenance(
    tmp_path,
):
    assert Q1_REGISTRATION_BINDER.exists()
    binder = _load_module(
        Q1_REGISTRATION_BINDER, "mergecert_q1_registration_binder"
    )
    root = tmp_path / "repo"
    binding_path = root / "memsub" / "mergecert_q1_registration.py"
    provenance_path = (
        root / "plans" / "260728-mergecert-q1" / "source-provenance.json"
    )
    binding_path.parent.mkdir(parents=True)
    provenance_path.parent.mkdir(parents=True)
    binding_path.write_text(
        (
            ROOT / "memsub" / "mergecert_q1_registration.py"
        ).read_text()
    )
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
    )
    extracted = tmp_path / "extracted.json"
    extracted_payload = {
        "schema": "mergecert-q1-registration-v1",
        "status": "finalized",
        "source_registration_sha256": "a" * 64,
        "documents": [],
    }
    extracted.write_text(
        json.dumps(extracted_payload, indent=1, allow_nan=False)
    )
    expected_bytes = (
        json.dumps(extracted_payload, indent=1, allow_nan=False) + "\n"
    ).encode()
    expected_sha256 = hashlib.sha256(expected_bytes).hexdigest()

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
    assert target.read_bytes() == expected_bytes
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
