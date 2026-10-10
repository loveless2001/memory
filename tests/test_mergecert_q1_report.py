import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "plans" / "260728-mergecert-q1"
RENDERER = PLAN / "render-report.py"
VALIDATOR = PLAN / "validate-report.py"
Q1_REGISTRATION_SOURCE = json.loads(
    (PLAN / "q1-registration-source.json").read_text()
)
FROZEN_REFERENCE = ROOT / "FULLRECIPE-REPORT.md"
CLEAN_UNFROZEN_REFERENCE_RELATIVE = (
    "plans/260719-2328-e1full-unfrozen-full-recipe/"
    "summary-e1full-clean-v1-n60.json"
)
CLEAN_UNFROZEN_REFERENCE = ROOT / CLEAN_UNFROZEN_REFERENCE_RELATIVE
SKIP_REASON = (
    "Q2 and Q3 were skipped because no merge-minus-eviction 95% interval was "
    "favorable under the registered Q1 rule."
)
Q1_APP_IDS = (
    "ap-LhQ8XuapnFgxvOgxih3tr3",
    "ap-n8C84UMNCvqC8Mc5bIM3c5",
)
Q2_APP_ID = "ap-Vm2RcWMIGSeIN2ykNdSyxB"
Q1_REGISTRATION_PENDING = "PENDING_CPU_EXTRACTION"
Q1_TOKENIZER_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
CORPUS_MANIFEST_SHA256 = "1" * 64
TOKENIZER_FILES_SHA256 = {
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


def _load(path, name, *, bind=True):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if bind and hasattr(module, "Q1_REGISTRATION_SHA256"):
        module.Q1_REGISTRATION_SHA256 = _q1_registration_sha256()
    return module


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, allow_nan=False))


def _source_document_sha256(doc_id):
    return hashlib.sha256(f"source:{doc_id}".encode()).hexdigest()


def _q1_verdict(*, positive, aggregation_only=False):
    intervals = {
        "0.25": {
            "lost_prior": {
                "mean_diff": (
                    -0.12 if positive and not aggregation_only else 0.02
                ),
                "ci95": (
                    [-0.18, -0.06]
                    if positive and not aggregation_only
                    else [-0.03, 0.07]
                ),
            },
            "mean_kl": {
                "mean_diff": 0.03,
                "ci95": [-0.01, 0.07],
            },
            "acc_delta": {
                "mean_diff": 0.01,
                "ci95": [-0.02, 0.04],
            },
        },
        "0.40": {
            "lost_prior": {
                "mean_diff": 0.04,
                "ci95": [-0.02, 0.10],
            },
            "mean_kl": {
                "mean_diff": -0.02,
                "ci95": [-0.05, 0.01],
            },
            "acc_delta": {
                "mean_diff": 0.05 if positive else -0.01,
                "ci95": [0.02, 0.08] if positive else [-0.04, 0.02],
            },
        },
    }
    summaries = {
        "control-0.00": {
            "documents": 20,
            "aggregation_probes": 40,
            "needle_probes": 60,
            "mean_kl": 0.0,
            "accuracy_delta": 0.0,
            "lost_fact": 0.0,
            "lost_prior": 0.0,
        },
        "eviction-0.25": {
            "documents": 20,
            "aggregation_probes": 40,
            "needle_probes": 60,
            "mean_kl": 0.25,
            "accuracy_delta": -0.12,
            "lost_fact": 0.31,
            "lost_prior": 0.40,
        },
        "eviction-0.40": {
            "documents": 20,
            "aggregation_probes": 40,
            "needle_probes": 60,
            "mean_kl": 0.40,
            "accuracy_delta": -0.20,
            "lost_fact": 0.42,
            "lost_prior": 0.50,
        },
        "merge-0.25": {
            "documents": 20,
            "aggregation_probes": 40,
            "needle_probes": 60,
            "mean_kl": 0.28,
            "accuracy_delta": -0.11,
            "lost_fact": 0.22 if positive else 0.33,
            "lost_prior": 0.28 if positive else 0.42,
        },
        "merge-0.40": {
            "documents": 20,
            "aggregation_probes": 40,
            "needle_probes": 60,
            "mean_kl": 0.38,
            "accuracy_delta": -0.15 if positive else -0.21,
            "lost_fact": 0.45,
            "lost_prior": 0.54,
        },
    }
    per_domain = {}
    for index, domain in enumerate(
        ("financial", "legal", "code", "literature")
    ):
        per_domain[domain] = {
            arm: {
                **row,
                "documents": 5,
                "aggregation_probes": 10,
                "needle_probes": 15,
                "mean_kl": row["mean_kl"] + index * 0.001,
            }
            for arm, row in summaries.items()
        }
    pointwise_favorable = (
        ["0.25:lost_prior"] if positive and not aggregation_only else []
    )
    aggregation_favorable = ["0.40:acc_delta"] if positive else []
    favorable = pointwise_favorable + aggregation_favorable
    per_document_budgets = {}
    sample_doc_ids = []
    for doc_id in Q1_REGISTRATION_SOURCE["population_doc_ids"]:
        sample_doc_ids.append(doc_id)
        source_tokens = 3921 if doc_id == "legal/00000" else 4096
        source_start = Q1_REGISTRATION_SOURCE[
            "eviction_source_start"
        ][doc_id]
        per_document_budgets[doc_id] = {
            f"{ratio:.2f}": {
                "source_context_token_count": source_tokens,
                "model_input_token_count": source_tokens,
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
        }
    return {
        "pass": True,
        "budget_mode": "archived-m1-per-document-matched-physical-v1",
        "authorization": {
            "protocol": "MERGECERT-Q1",
            "budget_mode": "archived-m1-per-document-matched-physical-v1",
            "addendum_sha256": (
                "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509"
            ),
            "p0_verdict_sha256": (
                "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
            ),
        },
        "documents": 20,
        "sample_doc_ids": sample_doc_ids,
        "archive_replay_matrix": [
            {
                "doc_id": doc_id,
                "archive": (
                    f"{doc_id.split('/', 1)[0]}-evict{ratio:.2f}.json"
                ),
                "arm": (
                    "control-0.00"
                    if ratio == 0.0
                    else f"eviction-{ratio:.2f}"
                ),
                "archive_sha256": Q1_REGISTRATION_SOURCE[
                    "archive_sha256"
                ][f"{doc_id.split('/', 1)[0]}-evict{ratio:.2f}.json"],
            }
            for doc_id in sample_doc_ids
            for ratio in (0.0, 0.25, 0.40)
        ],
        "domain_counts": {
            "financial": 5,
            "legal": 5,
            "code": 5,
            "literature": 5,
        },
        "archived_m1_replay_pass": True,
        "summaries": summaries,
        "references": {
            "frozen_subsample": {
                "mean_kl": 0.2566,
                "accuracy_delta": 0.063,
                "lost_prior": 0.188,
            },
            "unfrozen_compactor": {
                "mean_kl": 0.1385,
                "accuracy_delta": 0.042,
                "lost_prior": 0.083,
            },
        },
        "paired_merge_minus_eviction": intervals,
        "registered_readings": {
            "r1": "R1" if pointwise_favorable else "R2",
            "r3": "aggregation-positive" if positive else "aggregation-negative",
            "pointwise_favorable": pointwise_favorable,
            "aggregation_favorable": aggregation_favorable,
            "favorable_intervals": favorable,
            "run_q2_q3": positive,
        },
        "per_domain": per_domain,
        "per_document_budgets": per_document_budgets,
        "run_q2_q3": positive,
        "favorable_intervals": favorable,
    }


def _q1_registration():
    documents = []
    for doc_id in Q1_REGISTRATION_SOURCE["population_doc_ids"]:
        source_tokens = 3921 if doc_id == "legal/00000" else 4096
        source_start = Q1_REGISTRATION_SOURCE[
            "eviction_source_start"
        ][doc_id]
        documents.append(
            {
                "doc_id": doc_id,
                "context_start": max(
                    0,
                    Q1_REGISTRATION_SOURCE["anchor_chunk_token_start"][
                        doc_id
                    ]
                    - 1024,
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
        "source_registration_sha256": _sha256(
            PLAN / "q1-registration-source.json"
        ),
        "model_id": "Qwen/Qwen3-4B-Instruct-2507",
        "tokenizer": {
            "model_id": "Qwen/Qwen3-4B-Instruct-2507",
            "revision": Q1_TOKENIZER_REVISION,
            "files_sha256": TOKENIZER_FILES_SHA256,
            "artifact_sha256": hashlib.sha256(
                json.dumps(
                    TOKENIZER_FILES_SHA256,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
        },
        "source_hashes": {
            "corpus_manifest_sha256": CORPUS_MANIFEST_SHA256,
            "all_items_sha256": Q1_REGISTRATION_SOURCE[
                "all_items_sha256"
            ],
            "source_document_sha256": {
                doc_id: _source_document_sha256(doc_id)
                for doc_id in Q1_REGISTRATION_SOURCE[
                    "population_doc_ids"
                ]
            },
        },
        "population_doc_ids": Q1_REGISTRATION_SOURCE[
            "population_doc_ids"
        ],
        "smoke_doc_ids": Q1_REGISTRATION_SOURCE["smoke_doc_ids"],
        "all_items_sha256": Q1_REGISTRATION_SOURCE["all_items_sha256"],
        "archive_sha256": Q1_REGISTRATION_SOURCE["archive_sha256"],
        "documents": documents,
    }


def _q1_registration_sha256():
    return hashlib.sha256(
        json.dumps(
            _q1_registration(), indent=1, allow_nan=False
        ).encode()
        + b"\n"
    ).hexdigest()


def _build_bundle(tmp_path, *, positive, aggregation_only=False):
    root = tmp_path / "repo"
    plan = root / "plans" / "260728-mergecert-q1"
    parent = root / "plans" / "260727-mergecert"
    addendum = root / "MERGECERT-Q1.md"
    addendum.parent.mkdir(parents=True)
    addendum.write_bytes((ROOT / "MERGECERT-Q1.md").read_bytes())
    frozen_reference = root / FROZEN_REFERENCE.name
    frozen_reference.write_bytes(FROZEN_REFERENCE.read_bytes())
    clean_unfrozen_reference = root / CLEAN_UNFROZEN_REFERENCE_RELATIVE
    clean_unfrozen_reference.parent.mkdir(parents=True, exist_ok=True)
    clean_unfrozen_reference.write_bytes(
        CLEAN_UNFROZEN_REFERENCE.read_bytes()
    )
    registration_source = plan / "q1-registration-source.json"
    registration_source.parent.mkdir(parents=True, exist_ok=True)
    registration_source.write_bytes(
        (PLAN / "q1-registration-source.json").read_bytes()
    )
    parent_source = parent / "source-provenance.json"
    parent_raw = parent / "p0-direction-200.json"
    parent_verdict = parent / "p0-verdict.json"
    for target, source_path in (
        (
            parent_source,
            ROOT / "plans/260727-mergecert/source-provenance.json",
        ),
        (parent_raw, ROOT / "plans/260727-mergecert/p0-direction-200.json"),
        (parent_verdict, ROOT / "plans/260727-mergecert/p0-verdict.json"),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source_path.read_bytes())
    source = {
        "protocol": "MERGECERT-Q1",
        "model_id": "Qwen/Qwen3-4B-Instruct-2507",
        "upstream_commit": "cd4ed948d62231449dbab9669608bbb4fd220713",
        "upstream_files": {
            "README.md": (
                "edfd5236d99dab5d6e4bf80b74dd79a54ffd94cec4b7066511dc6fd7ae7cae17"
            ),
            "benchmarks/modal_kv_real_bench.py": (
                "518b2d2cd4b652f4cc83ef9c82593fe624301986e0e3e22780ee9f0bfe423bb8"
            ),
            "lego_server.py": (
                "f1df91c8af05cf4ea5000f4027450bf91e5e269f4e922da8979fc0885d6ff228"
            ),
        },
        "ratios": [0.25, 0.4],
        "sink_token_count": 4,
        "budget_mode": "archived-m1-per-document-matched-physical-v1",
        "settled_amendment_date": "2026-07-29",
        "q1_registration_source": {
            "path": (
                "plans/260728-mergecert-q1/q1-registration-source.json"
            ),
            "sha256": _sha256(registration_source),
            "status": (
                "source-evidence-only; finalized CPU extraction completed"
            ),
        },
        "q1_registration": {
            "path": "plans/260728-mergecert-q1/q1-registration.json",
            "remote_path": "/artifacts/mergecert-q1/q1-registration.json",
            "sha256": _q1_registration_sha256(),
            "status": "finalized and hash-bound",
        },
        "addendum": {
            "path": "MERGECERT-Q1.md",
            "sha256": _sha256(addendum),
        },
        "settled_p0": {
            "verdict_path": "plans/260727-mergecert/p0-verdict.json",
            "verdict_sha256": _sha256(parent_verdict),
            "raw_path": "plans/260727-mergecert/p0-direction-200.json",
            "raw_sha256": _sha256(parent_raw),
        },
        "parent_source_provenance_sha256": _sha256(parent_source),
    }
    _write_json(plan / "source-provenance.json", source)
    (plan / "q1-registration.json").write_text(
        json.dumps(_q1_registration(), indent=1, allow_nan=False) + "\n"
    )
    q1 = _q1_verdict(
        positive=positive, aggregation_only=aggregation_only
    )
    q1["q1_registration_sha256"] = _sha256(
        plan / "q1-registration.json"
    )
    _write_json(plan / "q1-verdict.json", q1)
    trigger = {
        "protocol": "MERGECERT-Q1",
        "budget_mode": "archived-m1-per-document-matched-physical-v1",
        "run_q2_q3": positive,
        "favorable_intervals": q1["favorable_intervals"],
        "q1_verdict_sha256": _sha256(plan / "q1-verdict.json"),
        "addendum_sha256": source["addendum"]["sha256"],
        "p0_verdict_sha256": source["settled_p0"]["verdict_sha256"],
    }
    _write_json(plan / "q1-trigger.json", trigger)
    if positive:
        amendment_path = plan / "q2-amendment.json"
        amendment_path.write_bytes((PLAN / "q2-amendment.json").read_bytes())
        amendment = json.loads(amendment_path.read_text())
        amendment_sha256 = _sha256(amendment_path)
        accounting_audit_sha256 = "a" * 64
        q2 = {
            "schema": "mergecert-q2-verdict-amended-v2",
            "pass": True,
            "q1_trigger": trigger,
            "q1_trigger_sha256": _sha256(plan / "q1-trigger.json"),
            "protocol_version": amendment["protocol_version"],
            "namespace_version": amendment["namespace_version"],
            "context_mechanics_version": amendment[
                "context_mechanics_version"
            ],
            "q2_amendment": amendment,
            "q2_amendment_sha256": amendment_sha256,
            "context_accounting_audit_sha256": accounting_audit_sha256,
            "registered_reading": "Merged loss is mechanics-routable.",
            "markdown_table": (
                "| Q2 arm | 0.25 | 0.40 |\n"
                "|---|---:|---:|\n"
                "| mechanics refit | 0.7500 | 0.7300 |\n"
            ),
            "f5_markdown_table": (
                "| F5 fifth-regime row | 0.25 | 0.40 |\n"
                "|---|---:|---:|\n"
                "| sink-head monitor | 0.7100 | 0.7000 |\n"
            ),
        }
        q3 = {
            "schema": "mergecert-q3-fragility-amended-v2",
            "q2_verdict_schema": "mergecert-q2-verdict-amended-v2",
            "pass": True,
            "q1_trigger": trigger,
            "q1_trigger_sha256": _sha256(plan / "q1-trigger.json"),
            "protocol_version": amendment["protocol_version"],
            "namespace_version": amendment["namespace_version"],
            "context_mechanics_version": amendment[
                "context_mechanics_version"
            ],
            "q2_amendment": amendment,
            "q2_amendment_sha256": amendment_sha256,
            "context_accounting_audit_sha256": accounting_audit_sha256,
            "interpretation": "Marginal-aware nesting interpretation.",
            "markdown_table": (
                "| Q3 reference | kappa | nesting |\n"
                "|---|---:|---:|\n"
                "| A | 0.4000 | 0.8000 |\n"
            ),
        }
        _write_json(plan / "q2-routability.json", q2)
        _write_json(plan / "q3-fragility.json", q3)
        conditional = {
            "protocol": "MERGECERT-Q1",
            "status": "completed",
            "q1_trigger_sha256": _sha256(plan / "q1-trigger.json"),
            "q2_amendment": {
                "path": "plans/260728-mergecert-q1/q2-amendment.json",
                "sha256": amendment_sha256,
            },
            "protocol_version": amendment["protocol_version"],
            "namespace_version": amendment["namespace_version"],
            "context_mechanics_version": amendment[
                "context_mechanics_version"
            ],
            "context_accounting_audit_sha256": accounting_audit_sha256,
            "q2": {
                "path": (
                    "plans/260728-mergecert-q1/q2-routability.json"
                ),
                "sha256": _sha256(plan / "q2-routability.json"),
            },
            "q3": {
                "path": "plans/260728-mergecert-q1/q3-fragility.json",
                "sha256": _sha256(plan / "q3-fragility.json"),
            },
        }
    else:
        conditional = {
            "protocol": "MERGECERT-Q1",
            "status": "skipped",
            "reason": SKIP_REASON,
            "q1_trigger_sha256": _sha256(plan / "q1-trigger.json"),
        }
    _write_json(plan / "conditional-work.json", conditional)
    compute = {
        "ceiling_usd": 45.0,
        "total_cost_usd": 12.5 if positive else 10.25,
        "phases": {
            "q1": {
                "phase": "Q1",
                "gpu": "H100",
                "gpu_seconds": 900.0,
                "cost_usd": 10.25,
                "source": (
                    "Modal billing report 2026-07-28 for apps "
                    f"{Q1_APP_IDS[0]} and {Q1_APP_IDS[1]}"
                ),
                "runs": [
                    {"app_id": Q1_APP_IDS[0], "purpose": "Q1 smoke"},
                    {
                        "app_id": Q1_APP_IDS[1],
                        "purpose": "Q1 certification",
                    },
                ],
            },
            **(
                {
                    "q2_q3": {
                        "phase": "Q2/Q3",
                        "gpu": "L4",
                        "gpu_seconds": 300.0,
                        "cost_usd": 2.25,
                        "source": (
                            "Modal billing report 2026-07-28 for app "
                            f"{Q2_APP_ID}"
                        ),
                        "runs": [
                            {
                                "app_id": Q2_APP_ID,
                                "purpose": "conditional Q2 capture",
                            }
                        ],
                    }
                }
                if positive
                else {}
            ),
        },
    }
    _write_json(plan / "compute-actuals.json", compute)
    return root, plan


def test_q1_placement_pairs_matched_arms_and_separates_current_context(
    tmp_path,
):
    renderer = _load(RENDERER, "mergecert_q1_renderer_split_tables")
    root, plan = _build_bundle(tmp_path, positive=False)
    report = renderer.render_report(
        renderer.load_evidence(plan, root=root)
    )

    matched_start = report.index("| matched Q1 arm |")
    matched_end = report.index("\n\n", matched_start)
    matched_table = report[matched_start:matched_end]
    matched_rows = [
        line.split("|")[1].strip()
        for line in matched_table.splitlines()[2:]
    ]
    assert matched_rows == [
        "eviction 0.25",
        "MERGE 0.25",
        "eviction 0.40",
        "MERGE 0.40",
        "zero-compression control",
    ]
    assert "reference" not in matched_table

    context_heading = (
        "### Historical context — not directly budget/population matched"
    )
    assert context_heading in report
    context_start = report.index(context_heading)
    context_end = report.index(
        "\n\n", report.index("| reference regime |", context_start)
    )
    context = report[context_start:context_end]
    for value in (
        "frozen full-recipe d1 (n=60)",
        "0.2820",
        "+0.1019",
        "0.210",
        "clean unfrozen d1 (n=60)",
        "0.1281",
        "+0.0536",
        "0.050",
    ):
        assert value in context
    assert "not Q1-matched comparators" in context


@pytest.mark.parametrize(
    ("relative_path", "message"),
    (
        ("FULLRECIPE-REPORT.md", "frozen reference source hash"),
        (
            CLEAN_UNFROZEN_REFERENCE_RELATIVE,
            "clean unfrozen reference source hash",
        ),
    ),
)
def test_reference_context_sources_are_hash_bound(
    tmp_path,
    relative_path,
    message,
):
    renderer = _load(RENDERER, "mergecert_q1_renderer_reference_hash")
    root, plan = _build_bundle(tmp_path, positive=False)
    source = root / relative_path
    source.write_text(source.read_text() + "\nsemantic drift\n")

    with pytest.raises(ValueError, match=message):
        renderer.load_evidence(plan, root=root)


def test_report_validation_rejects_a_fake_4096_one_token_budget(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_fake_budget")
    validator = _load(VALIDATOR, "mergecert_q1_validator_fake_budget")
    root, plan = _build_bundle(tmp_path, positive=False)
    evidence = renderer.load_evidence(plan, root=root)
    budget = evidence["q1"]["per_document_budgets"]["financial/00000"]["0.25"]
    budget.update(
        {
            "evicted_token_count": 1,
            "physical_after_count": 4095,
            "retained_token_count": 4095,
            "merge_target_retained": 4095,
        }
    )

    with pytest.raises(ValueError, match="budget"):
        validator._validate_q1(evidence)


def test_report_validation_rejects_duplicate_archive_replay_rows(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_duplicate_replay")
    validator = _load(VALIDATOR, "mergecert_q1_validator_duplicate_replay")
    root, plan = _build_bundle(tmp_path, positive=False)
    evidence = renderer.load_evidence(plan, root=root)
    matrix = evidence["q1"]["archive_replay_matrix"]
    matrix[-1] = dict(matrix[0])

    with pytest.raises(ValueError, match="replay"):
        validator._validate_q1(evidence)


def test_report_validation_accepts_registered_auxiliary_lost_fact_interval(
    tmp_path,
):
    renderer = _load(RENDERER, "mergecert_q1_renderer_lost_fact_interval")
    validator = _load(VALIDATOR, "mergecert_q1_validator_lost_fact_interval")
    root, plan = _build_bundle(tmp_path, positive=False)
    evidence = renderer.load_evidence(plan, root=root)
    for row in evidence["q1"]["paired_merge_minus_eviction"].values():
        row["lost_fact"] = dict(row["lost_prior"])

    validator._validate_q1(evidence)


@pytest.mark.parametrize("name", ("q2", "q3"))
@pytest.mark.parametrize("field", ("q1_trigger", "q1_trigger_sha256"))
def test_validator_requires_exact_trigger_binding_on_conditional_evidence(
    tmp_path, name, field
):
    renderer = _load(RENDERER, f"mergecert_q1_renderer_{name}_{field}")
    validator = _load(VALIDATOR, f"mergecert_q1_validator_{name}_{field}")
    root, plan = _build_bundle(tmp_path, positive=True)
    evidence = renderer.load_evidence(plan, root=root)
    evidence[name].pop(field)

    with pytest.raises(ValueError, match=f"conditional {name.upper()}"):
        validator._validate_conditional(evidence)


@pytest.mark.parametrize("name", ("q2", "q3"))
def test_validator_rejects_wrong_trigger_binding_on_conditional_evidence(
    tmp_path, name
):
    renderer = _load(RENDERER, f"mergecert_q1_renderer_wrong_{name}")
    validator = _load(VALIDATOR, f"mergecert_q1_validator_wrong_{name}")
    root, plan = _build_bundle(tmp_path, positive=True)
    evidence = renderer.load_evidence(plan, root=root)
    evidence[name]["q1_trigger_sha256"] = "f" * 64

    with pytest.raises(ValueError, match=f"conditional {name.upper()}"):
        validator._validate_conditional(evidence)


@pytest.mark.parametrize(
    ("path", "field"),
    (
        (("per_document_budgets", "financial/00000", "0.25"), "requested_evicted_token_count"),
        (("per_document_budgets", "financial/00000", "0.25"), "retained_token_count"),
    ),
)
def test_report_validation_rejects_non_strict_accounting_counts(
    tmp_path, path, field
):
    renderer = _load(RENDERER, f"mergecert_q1_renderer_count_{field}")
    validator = _load(VALIDATOR, f"mergecert_q1_validator_count_{field}")
    root, plan = _build_bundle(tmp_path, positive=False)
    evidence = renderer.load_evidence(plan, root=root)
    target = evidence["q1"]
    for component in path:
        target = target[component]
    target[field] = True

    with pytest.raises(ValueError, match="budget"):
        validator._validate_q1(evidence)


def test_report_validation_requires_strict_finalized_registration(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_registration_count")
    validator = _load(VALIDATOR, "mergecert_q1_validator_registration_count")
    root, plan = _build_bundle(tmp_path, positive=False)
    evidence = renderer.load_evidence(plan, root=root)
    evidence["registration"]["documents"][0]["budgets"]["0.25"][
        "requested_evicted_token_count"
    ] = True
    malformed_sha256 = validator.canonical_q1_registration_sha256(
        evidence["registration"]
    )
    validator.Q1_REGISTRATION_SHA256 = malformed_sha256
    evidence["q1"]["q1_registration_sha256"] = malformed_sha256
    evidence["_files"]["registration"]["sha256"] = malformed_sha256

    with pytest.raises(ValueError, match="registration counts"):
        validator._validate_q1(evidence)


def test_report_tools_fail_closed_while_registration_binding_is_pending(
    tmp_path,
):
    renderer = _load(
        RENDERER, "mergecert_q1_renderer_pending", bind=False
    )
    validator = _load(
        VALIDATOR, "mergecert_q1_validator_pending", bind=False
    )
    renderer.Q1_REGISTRATION_SHA256 = Q1_REGISTRATION_PENDING
    validator.Q1_REGISTRATION_SHA256 = Q1_REGISTRATION_PENDING
    root, plan = _build_bundle(tmp_path, positive=False)

    assert renderer.Q1_REGISTRATION_SHA256 == Q1_REGISTRATION_PENDING
    assert validator.Q1_REGISTRATION_SHA256 == Q1_REGISTRATION_PENDING
    with pytest.raises(ValueError, match="pending"):
        renderer.load_evidence(plan, root=root)


@pytest.mark.parametrize(
    "mutation",
    ("wrong_source_hash", "incomplete_hash_set", "duplicate", "forged_start"),
)
def test_report_validation_rejects_registration_source_integrity_drift(
    tmp_path, mutation
):
    renderer = _load(RENDERER, f"mergecert_q1_renderer_{mutation}")
    validator = _load(VALIDATOR, f"mergecert_q1_validator_{mutation}")
    root, plan = _build_bundle(tmp_path, positive=False)
    evidence = renderer.load_evidence(plan, root=root)
    registration = evidence["registration"]
    if mutation == "wrong_source_hash":
        registration["source_hashes"]["source_document_sha256"][
            "financial/00000"
        ] = "f" * 64
        _write_json(plan / "q1-registration.json", registration)
        with pytest.raises(ValueError, match="literal binding"):
            renderer.load_evidence(plan, root=root)
        return
    elif mutation == "incomplete_hash_set":
        registration["source_hashes"]["source_document_sha256"].pop(
            "financial/00000"
        )
    elif mutation == "duplicate":
        registration["documents"][-1] = dict(
            registration["documents"][0]
        )
    else:
        registration["documents"][0]["context_start"] += 1
    malformed_sha256 = validator.canonical_q1_registration_sha256(
        registration
    )
    validator.Q1_REGISTRATION_SHA256 = malformed_sha256
    evidence["q1"]["q1_registration_sha256"] = malformed_sha256
    evidence["_files"]["registration"]["sha256"] = malformed_sha256

    with pytest.raises(
        ValueError,
        match="source hash|population|context start",
    ):
        validator._validate_q1(evidence)


def test_report_validator_rejects_in_memory_self_relative_registration(
    tmp_path,
):
    renderer = _load(RENDERER, "mergecert_q1_renderer_self_relative")
    validator = _load(VALIDATOR, "mergecert_q1_validator_self_relative")
    root, plan = _build_bundle(tmp_path, positive=False)
    evidence = renderer.load_evidence(plan, root=root)
    evidence["registration"]["source_hashes"][
        "source_document_sha256"
    ]["financial/00000"] = "f" * 64

    with pytest.raises(ValueError, match="literal binding"):
        validator._validate_q1(evidence)


def test_validator_rejects_registered_source_provenance_drift(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_source_drift")
    validator = _load(VALIDATOR, "mergecert_q1_validator_source_drift")
    root, plan = _build_bundle(tmp_path, positive=False)
    source_path = plan / "source-provenance.json"
    source = json.loads(source_path.read_text())
    source["upstream_commit"] = "f" * 40
    _write_json(source_path, source)
    evidence = renderer.load_evidence(plan, root=root)
    report = renderer.render_report(evidence)

    with pytest.raises(ValueError, match="source provenance"):
        validator.validate_report_text(report, evidence)
