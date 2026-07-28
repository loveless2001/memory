import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ANALYZER_PATH = (
    ROOT / "plans" / "260727-mergecert" / "analyze-mergecert-q1.py"
)
Q1_ADDENDUM_SHA256 = (
    "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509"
)
Q1_P0_VERDICT_SHA256 = (
    "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
)
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
Q1_REGISTRATION_SOURCE = json.loads(
    (
        ROOT
        / "plans"
        / "260728-mergecert-q1"
        / "q1-registration-source.json"
    ).read_text()
)


def _load_analyzer(*, bind=True):
    spec = importlib.util.spec_from_file_location(
        "mergecert_q1_analysis", ANALYZER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if bind:
        module.Q1_REGISTRATION_SHA256 = _registration_sha256()
    raw_analyze = module.analyze

    def analyze_with_registration(payload, **kwargs):
        if "registration" not in kwargs:
            kwargs["registration"] = _registration()
            kwargs["registration_sha256"] = _registration_sha256()
        return raw_analyze(payload, **kwargs)

    module.analyze = analyze_with_registration
    return module


def _token_counts(doc_id):
    return (3921, 3921) if doc_id == "legal/00000" else (4096, 4096)


def _source_document_sha256(doc_id):
    return hashlib.sha256(f"source:{doc_id}".encode()).hexdigest()


def _registration():
    documents = []
    for doc_id in Q1_REGISTRATION_SOURCE["population_doc_ids"]:
        source_tokens, model_tokens = _token_counts(doc_id)
        source_start = Q1_REGISTRATION_SOURCE["eviction_source_start"][
            doc_id
        ]
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
                "model_input_token_count": model_tokens,
                "budgets": {
                    f"{ratio:.2f}": {
                        "requested_evicted_token_count": int(
                            source_tokens * ratio
                        ),
                        "eviction_source_start": source_start,
                        "eviction_source_end": (
                            source_start + int(source_tokens * ratio)
                        ),
                        "physical_before_count": model_tokens,
                        "physical_after_count": (
                            model_tokens - int(source_tokens * ratio)
                        ),
                        "evicted_token_count": int(source_tokens * ratio),
                        "retained_token_count": (
                            model_tokens - int(source_tokens * ratio)
                        ),
                        "merge_target_retained": (
                            model_tokens - int(source_tokens * ratio)
                        ),
                    }
                    for ratio in (0.25, 0.40)
                },
            }
        )
    source_path = (
        ROOT
        / "plans"
        / "260728-mergecert-q1"
        / "q1-registration-source.json"
    )
    return {
        "schema": "mergecert-q1-registration-v1",
        "status": "finalized",
        "source_registration_sha256": hashlib.sha256(
            source_path.read_bytes()
        ).hexdigest(),
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


def _registration_text():
    return json.dumps(_registration(), indent=1, allow_nan=False) + "\n"


def _registration_sha256():
    return hashlib.sha256(_registration_text().encode()).hexdigest()


def _report(doc_id, ratio, *, kl, acc_delta, lost, lost_prior):
    source_tokens, model_tokens = _token_counts(doc_id)
    evicted = int(source_tokens * ratio)
    retained = model_tokens - evicted
    source_start = (
        0
        if ratio == 0
        else Q1_REGISTRATION_SOURCE["eviction_source_start"][doc_id]
    )
    source_end = source_start + evicted
    return {
        "doc_id": doc_id,
        "domain": doc_id.split("/", 1)[0],
        "context_sha256": f"sha-{doc_id}",
        "source_context_token_count": source_tokens,
        "model_input_token_count": model_tokens,
        "context_token_count": model_tokens,
        "requested_evicted_token_count": evicted,
        "eviction_source_start": source_start,
        "eviction_source_end": source_end,
        "physical_before_count": model_tokens,
        "physical_after_count": retained,
        "evicted_token_count": evicted,
        "target_retained": retained,
        "source_hashes": {
            "corpus_manifest_sha256": CORPUS_MANIFEST_SHA256,
            "all_items_sha256": Q1_REGISTRATION_SOURCE[
                "all_items_sha256"
            ],
            "source_document_sha256": _source_document_sha256(doc_id),
        },
        "needle_item_ids": [f"{doc_id}:needle"],
        "aggregation_item_ids": [f"{doc_id}:agg"],
        "aggregation_axis": {
            "mean_kl": kl,
            "accuracy_delta": acc_delta,
            "probe_count": 1,
        },
        "pointwise_axis": {
            "lost_fact_incident_rate": lost,
            "lost_fact_rate_given_prior_correct": lost_prior,
            "needle_probe_count": 1,
        },
    }


def _payload(*, documents_per_domain=5, smoke=False):
    if documents_per_domain != 5:
        raise ValueError("fixture supports only the registered full population")
    docs = list(
        Q1_REGISTRATION_SOURCE[
            "smoke_doc_ids" if smoke else "population_doc_ids"
        ]
    )
    arms = {}
    for ratio in (0.25, 0.40):
        arms[f"eviction-{ratio:.2f}"] = {
            "policy": "contiguous-eviction",
            "ratio": ratio,
            "budget_mode": "archived-m1-per-document-matched-physical-v1",
            "reports": [
                _report(
                    doc,
                    ratio,
                    kl=ratio,
                    acc_delta=-ratio,
                    lost=ratio,
                    lost_prior=ratio,
                )
                for doc in docs
            ],
        }
        arms[f"merge-{ratio:.2f}"] = {
            "policy": "attention-weighted-merge",
            "ratio": ratio,
            "budget_mode": "archived-m1-per-document-matched-physical-v1",
            "reports": [
                _report(
                    doc,
                    ratio,
                    kl=ratio / 2,
                    acc_delta=-ratio / 2,
                    lost=ratio / 2,
                    lost_prior=ratio / 2,
                )
                for doc in docs
            ],
        }
    arms["control-0.00"] = {
        "policy": "zero-compression-control",
        "ratio": 0.0,
        "budget_mode": "archived-m1-per-document-matched-physical-v1",
        "reports": [
            _report(
                doc,
                0.0,
                kl=0.0,
                acc_delta=0.0,
                lost=0.0,
                lost_prior=0.0,
            )
            for doc in docs
        ],
    }
    return {
        "provenance": {
            "model_id": "Qwen/Qwen3-4B-Instruct-2507",
            "ratios": [0.25, 0.40],
            "sink_token_count": 4,
            "budget_mode": "archived-m1-per-document-matched-physical-v1",
        },
        "q1_authorization": {
            "protocol": "MERGECERT-Q1",
            "budget_mode": "archived-m1-per-document-matched-physical-v1",
            "addendum_sha256": Q1_ADDENDUM_SHA256,
            "p0_verdict_sha256": Q1_P0_VERDICT_SHA256,
            "settled_p0": {
                "p0_3_pass": False,
                "p0_4_pass": True,
                "real_attention_pass": True,
                "p0_pass": False,
                "stop_q1_q3": True,
            },
        },
        "q1_registration_sha256": _registration_sha256(),
        "archived_m1": {
            "replay_pass": True,
            "replay_checks": [
                {
                    "archive": (
                        f"{doc.split('/', 1)[0]}-evict{ratio:.2f}.json"
                    ),
                    "archive_sha256": Q1_REGISTRATION_SOURCE[
                        "archive_sha256"
                    ][f"{doc.split('/', 1)[0]}-evict{ratio:.2f}.json"],
                    "arm": (
                        "control-0.00"
                        if ratio == 0.0
                        else f"eviction-{ratio:.2f}"
                    ),
                    "doc_id": doc,
                    "pass": True,
                    "mismatches": [],
                }
                for doc in docs
                for ratio in (0.0, 0.25, 0.40)
            ],
            "files": {
                name: {"sha256": digest}
                for name, digest in Q1_REGISTRATION_SOURCE[
                    "archive_sha256"
                ].items()
            },
        },
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
        "reference_sources": {
            "frozen_subsample": {
                "path": "plans/260719-0318-fullrecipe-campaign/plan.md",
                "sha256": (
                    "5017c76fa4715eb4f883ae1e2bd7cb26bbe0518aac9dfe2a53"
                    "cff7ccdfb85dce"
                ),
            },
            "unfrozen_compactor": {
                "path": (
                    "plans/260719-2328-e1full-unfrozen-full-recipe/"
                    "summary-e1full-clean-v1-n60.json"
                ),
                "sha256": (
                    "a7636b54148e7133237af68bf63fbc23811d5ce80417f844771"
                    "1a89a559dc2a8"
                ),
            },
        },
        "source_hashes": {
            "corpus_manifest_sha256": CORPUS_MANIFEST_SHA256,
            "all_items_sha256": Q1_REGISTRATION_SOURCE[
                "all_items_sha256"
            ],
        },
        "documents": [
            {
                "doc_id": doc,
                "domain": doc.split("/", 1)[0],
                "context_sha256": f"sha-{doc}",
                "context_start": max(
                    0,
                    Q1_REGISTRATION_SOURCE["anchor_chunk_token_start"][
                        doc
                    ]
                    - 1024,
                ),
                "source_context_token_count": _token_counts(doc)[0],
                "model_input_token_count": _token_counts(doc)[1],
                "context_token_count": _token_counts(doc)[1],
                "budgets": {
                    f"{ratio:.2f}": {
                        "source_context_token_count": _token_counts(doc)[0],
                        "model_input_token_count": _token_counts(doc)[1],
                        "requested_evicted_token_count": int(
                            _token_counts(doc)[0] * ratio
                        ),
                        "eviction_source_start": Q1_REGISTRATION_SOURCE[
                            "eviction_source_start"
                        ][doc],
                        "eviction_source_end": (
                            Q1_REGISTRATION_SOURCE[
                                "eviction_source_start"
                            ][doc]
                            + int(_token_counts(doc)[0] * ratio)
                        ),
                        "physical_before_count": _token_counts(doc)[1],
                        "physical_after_count": (
                            _token_counts(doc)[1]
                            - int(_token_counts(doc)[0] * ratio)
                        ),
                        "evicted_token_count": int(
                            _token_counts(doc)[0] * ratio
                        ),
                        "retained_token_count": (
                            _token_counts(doc)[1]
                            - int(_token_counts(doc)[0] * ratio)
                        ),
                        "merge_target_retained": (
                            _token_counts(doc)[1]
                            - int(_token_counts(doc)[0] * ratio)
                        ),
                    }
                    for ratio in (0.25, 0.40)
                },
                "source_hashes": {
                    "corpus_manifest_sha256": CORPUS_MANIFEST_SHA256,
                    "all_items_sha256": Q1_REGISTRATION_SOURCE[
                        "all_items_sha256"
                    ],
                    "source_document_sha256": _source_document_sha256(doc),
                },
                "needle_item_ids": [f"{doc}:needle"],
                "aggregation_item_ids": [f"{doc}:agg"],
            }
            for doc in docs
        ],
        "arms": arms,
        "sample_doc_ids": docs,
        "done_documents": len(docs),
    }


def test_q1_analysis_validates_all_registered_rows_and_paired_intervals():
    analyzer = _load_analyzer()

    verdict = analyzer.analyze(
        _payload(), expected_documents=20, n_resamples=200
    )

    assert verdict["pass"] is True
    assert set(verdict["summaries"]) == {
        "control-0.00",
        "eviction-0.25",
        "eviction-0.40",
        "merge-0.25",
        "merge-0.40",
    }
    assert verdict["summaries"]["control-0.00"]["mean_kl"] == 0.0
    assert verdict["paired_merge_minus_eviction"]["0.40"]["mean_kl"][
        "ci95"
    ] == pytest.approx([-0.2, -0.2])
    assert verdict["registered_readings"]["r1"] == "R1"
    assert verdict["run_q2_q3"] is True
    assert verdict["favorable_intervals"] == [
        "0.25:lost_prior",
        "0.40:lost_prior",
        "0.25:mean_kl",
        "0.25:acc_delta",
        "0.40:mean_kl",
        "0.40:acc_delta",
    ]
    assert verdict["per_domain"]["financial"]["merge-0.25"] == {
        "documents": 5,
        "aggregation_probes": 5,
        "needle_probes": 5,
        "mean_kl": 0.125,
        "accuracy_delta": -0.125,
        "lost_fact": 0.125,
        "lost_prior": 0.125,
    }
    assert "frozen subsample (reference)" in verdict["markdown_table"]
    assert verdict["budget_mode"] == (
        "archived-m1-per-document-matched-physical-v1"
    )
    assert verdict["sample_doc_ids"] == Q1_REGISTRATION_SOURCE[
        "population_doc_ids"
    ]
    assert len(verdict["archive_replay_matrix"]) == 60
    assert verdict["per_document_budgets"]["legal/00000"]["0.25"][
        "retained_token_count"
    ] == 2941


def test_q1_analysis_accepts_exact_financial_smoke_and_rejects_other_counts():
    analyzer = _load_analyzer()

    verdict = analyzer.analyze(
        _payload(smoke=True), expected_documents=2, n_resamples=20
    )

    assert verdict["sample_doc_ids"] == Q1_REGISTRATION_SOURCE[
        "smoke_doc_ids"
    ]
    assert verdict["domain_counts"] == {"financial": 2}
    with pytest.raises(ValueError, match="2- or 20-document"):
        analyzer.analyze(_payload(), expected_documents=4, n_resamples=20)


def test_q1_analysis_requires_the_hash_bound_finalized_registration():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["q1_registration_sha256"] = "f" * 64

    with pytest.raises(ValueError, match="finalized registration"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)

    payload = _payload()
    registration = _registration()
    registration["documents"][0]["budgets"]["0.25"][
        "requested_evicted_token_count"
    ] = True
    malformed_sha256 = analyzer.canonical_q1_registration_sha256(
        registration
    )
    analyzer.Q1_REGISTRATION_SHA256 = malformed_sha256
    payload["q1_registration_sha256"] = malformed_sha256
    with pytest.raises(ValueError, match="registration counts"):
        analyzer.analyze(
            payload,
            expected_documents=20,
            n_resamples=20,
            registration=registration,
            registration_sha256=malformed_sha256,
        )


def test_q1_analysis_fails_closed_while_registration_binding_is_pending():
    analyzer = _load_analyzer(bind=False)

    assert analyzer.Q1_REGISTRATION_SHA256 == Q1_REGISTRATION_PENDING
    with pytest.raises(ValueError, match="pending"):
        analyzer.analyze(
            _payload(),
            expected_documents=20,
            n_resamples=20,
            registration=_registration(),
            registration_sha256=_registration_sha256(),
        )


@pytest.mark.parametrize(
    "mutation",
    ("wrong_source_hash", "incomplete_hash_set", "duplicate", "forged_start"),
)
def test_q1_analysis_rejects_registration_source_integrity_drift(mutation):
    analyzer = _load_analyzer()
    payload = _payload()
    registration = _registration()
    if mutation == "wrong_source_hash":
        registration["source_hashes"]["source_document_sha256"][
            "financial/00000"
        ] = "f" * 64
    elif mutation == "incomplete_hash_set":
        registration["source_hashes"]["source_document_sha256"].pop(
            "financial/00000"
        )
    elif mutation == "duplicate":
        registration["documents"][-1] = dict(registration["documents"][0])
    else:
        registration["documents"][0]["context_start"] += 1
    malformed_sha256 = analyzer.canonical_q1_registration_sha256(
        registration
    )
    analyzer.Q1_REGISTRATION_SHA256 = malformed_sha256
    payload["q1_registration_sha256"] = malformed_sha256

    with pytest.raises(
        ValueError,
        match="source hash|population|context start",
    ):
        analyzer.analyze(
            payload,
            expected_documents=20,
            n_resamples=20,
            registration=registration,
            registration_sha256=malformed_sha256,
        )


def test_q1_analysis_rejects_synchronized_self_relative_source_hashes():
    analyzer = _load_analyzer()
    payload = _payload()
    registration = _registration()
    forged = "f" * 64
    registration["source_hashes"]["source_document_sha256"][
        "financial/00000"
    ] = forged
    payload["documents"][0]["source_hashes"][
        "source_document_sha256"
    ] = forged
    for arm in payload["arms"].values():
        arm["reports"][0]["source_hashes"][
            "source_document_sha256"
        ] = forged

    with pytest.raises(ValueError, match="literal binding"):
        analyzer.analyze(
            payload,
            expected_documents=20,
            n_resamples=20,
            registration=registration,
            registration_sha256=_registration_sha256(),
        )


def test_q1_analysis_requires_the_exact_settled_negative_authorization():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["q1_authorization"]["settled_p0"]["p0_3_pass"] = True

    with pytest.raises(ValueError, match="authorization"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("addendum_sha256", "a" * 64),
        ("p0_verdict_sha256", "b" * 64),
    ),
)
def test_q1_analysis_rejects_arbitrary_authorization_hashes(field, value):
    analyzer = _load_analyzer()
    payload = _payload()
    payload["q1_authorization"][field] = value

    with pytest.raises(ValueError, match="authorization"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


def test_q1_analysis_rejects_partition_drift_between_arms():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["arms"]["merge-0.40"]["reports"][0]["needle_item_ids"] = ["drift"]

    with pytest.raises(ValueError, match="partition"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


def test_q1_analysis_rejects_nonzero_control_and_wrong_budget():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["arms"]["control-0.00"]["reports"][0]["aggregation_axis"][
        "mean_kl"
    ] = 1e-4

    with pytest.raises(ValueError, match="control"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


def test_q1_analysis_rejects_merge_eviction_per_document_budget_drift():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["arms"]["merge-0.25"]["reports"][1]["target_retained"] += 1

    with pytest.raises(ValueError, match="per-document budget"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


def test_q1_analysis_rejects_duplicate_replay_or_sample_identity_drift():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["archived_m1"]["replay_checks"][-1] = dict(
        payload["archived_m1"]["replay_checks"][0]
    )
    with pytest.raises(ValueError, match="replay"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)

    payload = _payload()
    payload["sample_doc_ids"][-1] = "foreign/document"
    with pytest.raises(ValueError, match="sample"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


def test_q1_analysis_rejects_foreign_document_or_archive_hash():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["documents"][-1]["doc_id"] = "foreign/document"
    with pytest.raises(ValueError, match="registered sample"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)

    payload = _payload()
    payload["archived_m1"]["files"]["legal-evict0.25.json"][
        "sha256"
    ] = "f" * 64
    with pytest.raises(ValueError, match="file hashes"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


def test_q1_analysis_rejects_a_4096_context_with_fake_one_token_removal():
    analyzer = _load_analyzer()
    payload = _payload()
    document = payload["documents"][0]
    budget = document["budgets"]["0.25"]
    budget.update(
        {
            "evicted_token_count": 1,
            "physical_after_count": 4095,
            "retained_token_count": 4095,
            "merge_target_retained": 4095,
        }
    )
    for arm_name in ("eviction-0.25", "merge-0.25"):
        report = payload["arms"][arm_name]["reports"][0]
        report.update(
            {
                "evicted_token_count": 1,
                "physical_after_count": 4095,
                "target_retained": 4095,
            }
        )

    with pytest.raises(ValueError, match="budget"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


def test_q1_analysis_rejects_boolean_token_counts():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["documents"][0]["source_context_token_count"] = True

    with pytest.raises(ValueError, match="token-length"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


@pytest.mark.parametrize(
    ("scope", "field"),
    (
        ("budget", "requested_evicted_token_count"),
        ("budget", "retained_token_count"),
        ("budget", "merge_target_retained"),
        ("report", "requested_evicted_token_count"),
        ("report", "physical_before_count"),
        ("report", "target_retained"),
    ),
)
def test_q1_analysis_rejects_non_strict_accounting_counts(scope, field):
    analyzer = _load_analyzer()
    payload = _payload()
    if scope == "budget":
        payload["documents"][0]["budgets"]["0.25"][field] = True
    else:
        payload["arms"]["merge-0.25"]["reports"][0][field] = True

    with pytest.raises(ValueError, match="budget"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


def test_q1_analysis_rejects_shifted_eviction_range_at_registered_count():
    analyzer = _load_analyzer()
    payload = _payload()
    budget = payload["documents"][0]["budgets"]["0.25"]
    budget["eviction_source_start"] = 4095
    budget["eviction_source_end"] = 4095 + budget[
        "requested_evicted_token_count"
    ]

    with pytest.raises(ValueError, match="budget"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


@pytest.mark.parametrize("arm", ("merge-0.90", "eviction-0.90"))
def test_q1_analysis_rejects_nonregistered_ninety_percent_arms(arm):
    analyzer = _load_analyzer()
    payload = _payload()
    payload["arms"][arm] = {
        "policy": "unexpected",
        "ratio": 0.90,
        "target_retained": 410,
        "reports": [],
    }

    with pytest.raises(ValueError, match="registered arm"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


def test_q1_analysis_rejects_ninety_percent_data_disguised_as_moderate_arm():
    analyzer = _load_analyzer()
    payload = _payload()
    arm = payload["arms"]["merge-0.25"]
    arm["ratio"] = 0.90
    for report in arm["reports"]:
        report["target_retained"] = 410

    with pytest.raises(ValueError, match="ratio"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


def test_q1_analysis_rejects_missing_source_hashes_or_replay_checks():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["arms"]["merge-0.25"]["reports"][0]["source_hashes"] = {}
    with pytest.raises(ValueError, match="source hash"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)

    payload = _payload()
    payload["archived_m1"]["replay_checks"][0]["pass"] = False
    with pytest.raises(ValueError, match="replay check"):
        analyzer.analyze(payload, expected_documents=20, n_resamples=20)


def _overlapping_intervals():
    return {
        ratio: {
            "lost_prior": {"mean_diff": 0.0, "ci95": [-0.1, 0.1]},
            "mean_kl": {"mean_diff": 0.0, "ci95": [-0.1, 0.1]},
            "acc_delta": {"mean_diff": 0.0, "ci95": [-0.1, 0.1]},
        }
        for ratio in ("0.25", "0.40")
    }


def test_q1_trigger_runs_for_any_favorable_registered_interval():
    analyzer = _load_analyzer()
    intervals = {
        "0.25": {
            "lost_prior": {"mean_diff": -0.1, "ci95": [-0.2, -0.01]},
            "mean_kl": {"mean_diff": 0.1, "ci95": [0.01, 0.2]},
            "acc_delta": {"mean_diff": 0.0, "ci95": [-0.1, 0.1]},
        },
        "0.40": {
            "lost_prior": {"mean_diff": 0.0, "ci95": [-0.1, 0.1]},
            "mean_kl": {"mean_diff": 0.0, "ci95": [-0.1, 0.1]},
            "acc_delta": {"mean_diff": 0.0, "ci95": [-0.1, 0.1]},
        },
    }
    reading = analyzer.classify_registered_readings(intervals)

    assert reading["r1"] == "R1"
    assert reading["run_q2_q3"] is True
    assert reading["favorable_intervals"] == ["0.25:lost_prior"]


def test_q1_trigger_skips_when_all_intervals_overlap_or_are_worse():
    analyzer = _load_analyzer()
    reading = analyzer.classify_registered_readings(_overlapping_intervals())

    assert reading["r1"] == "R2"
    assert reading["run_q2_q3"] is False
    assert reading["favorable_intervals"] == []


@pytest.mark.parametrize(
    ("metric", "ci95", "favorable"),
    (
        ("mean_kl", [-0.2, -0.01], ["0.40:mean_kl"]),
        ("acc_delta", [0.01, 0.2], ["0.40:acc_delta"]),
    ),
)
def test_q1_trigger_treats_aggregation_intervals_as_favorable(
    metric, ci95, favorable
):
    analyzer = _load_analyzer()
    intervals = _overlapping_intervals()
    intervals["0.40"][metric] = {"mean_diff": 0.1, "ci95": ci95}

    reading = analyzer.classify_registered_readings(intervals)

    assert reading["r1"] == "R2"
    assert reading["r3"] == "aggregation-positive"
    assert reading["favorable_intervals"] == favorable
    assert reading["run_q2_q3"] is True


def test_q1_cli_writes_trigger_with_the_verdict_evidence_hash(tmp_path, monkeypatch):
    analyzer = _load_analyzer()
    input_path = tmp_path / "q1-certification.json"
    output_path = tmp_path / "q1-verdict.json"
    table_path = tmp_path / "q1-table.md"
    trigger_path = tmp_path / "q1-trigger.json"
    registration_path = tmp_path / "q1-registration.json"
    registration_path.write_text(_registration_text())
    input_path.write_text(json.dumps(_payload(documents_per_domain=5)))
    monkeypatch.setattr(
        "sys.argv",
        [
            "analyze-mergecert-q1.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--table",
            str(table_path),
            "--trigger",
            str(trigger_path),
            "--registration",
            str(registration_path),
            "--n-resamples",
            "20",
        ],
    )

    analyzer.main()

    trigger = json.loads(trigger_path.read_text())
    assert trigger == {
        "protocol": "MERGECERT-Q1",
        "budget_mode": "archived-m1-per-document-matched-physical-v1",
        "run_q2_q3": True,
        "favorable_intervals": [
            "0.25:lost_prior",
            "0.40:lost_prior",
            "0.25:mean_kl",
            "0.25:acc_delta",
            "0.40:mean_kl",
            "0.40:acc_delta",
        ],
        "q1_verdict_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "addendum_sha256": Q1_ADDENDUM_SHA256,
        "p0_verdict_sha256": Q1_P0_VERDICT_SHA256,
    }
    assert (
        table_path.read_text()
        == json.loads(output_path.read_text())["markdown_table"]
    )
