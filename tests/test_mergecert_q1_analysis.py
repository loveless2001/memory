import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ANALYZER_PATH = (
    ROOT / "plans" / "260727-mergecert" / "analyze-mergecert-q1.py"
)


def _load_analyzer():
    spec = importlib.util.spec_from_file_location(
        "mergecert_q1_analysis", ANALYZER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _token_counts(doc_id):
    return (3921, 3921) if doc_id == "legal/0" else (4096, 4096)


def _report(doc_id, ratio, *, kl, acc_delta, lost, lost_prior):
    source_tokens, model_tokens = _token_counts(doc_id)
    evicted = int(source_tokens * ratio)
    retained = model_tokens - evicted
    return {
        "doc_id": doc_id,
        "domain": doc_id.split("/", 1)[0],
        "context_sha256": f"sha-{doc_id}",
        "source_context_token_count": source_tokens,
        "model_input_token_count": model_tokens,
        "context_token_count": model_tokens,
        "requested_evicted_token_count": evicted,
        "evicted_token_count": evicted,
        "target_retained": retained,
        "source_hashes": {
            "corpus_manifest_sha256": "manifest-sha",
            "all_items_sha256": "items-sha",
            "source_document_sha256": f"document-sha-{doc_id}",
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


def _payload(*, documents_per_domain=1):
    docs = [
        f"{domain}/{index}"
        for domain in ("financial", "legal", "code", "literature")
        for index in range(documents_per_domain)
    ]
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
            "addendum_sha256": "a" * 64,
            "p0_verdict_sha256": "b" * 64,
            "settled_p0": {
                "p0_3_pass": False,
                "p0_4_pass": True,
                "real_attention_pass": True,
                "p0_pass": False,
                "stop_q1_q3": True,
            },
        },
        "archived_m1": {
            "replay_pass": True,
            "replay_checks": [
                {
                    "archive": (
                        f"{doc.split('/', 1)[0]}-evict{ratio:.2f}.json"
                    ),
                    "doc_id": doc,
                    "pass": True,
                    "mismatches": [],
                }
                for doc in docs
                for ratio in (0.0, 0.25, 0.40)
            ],
            "files": {
                f"{domain}-evict{ratio:.2f}.json": {
                    "sha256": f"{domain}-{ratio}"
                }
                for domain in ("financial", "legal", "code", "literature")
                for ratio in (0.0, 0.25, 0.40)
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
            "corpus_manifest_sha256": "manifest-sha",
            "all_items_sha256": "items-sha",
        },
        "documents": [
            {
                "doc_id": doc,
                "domain": doc.split("/", 1)[0],
                "context_sha256": f"sha-{doc}",
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
                    "corpus_manifest_sha256": "manifest-sha",
                    "all_items_sha256": "items-sha",
                    "source_document_sha256": f"document-sha-{doc}",
                },
                "needle_item_ids": [f"{doc}:needle"],
                "aggregation_item_ids": [f"{doc}:agg"],
            }
            for doc in docs
        ],
        "arms": arms,
        "done_documents": len(docs),
    }


def test_q1_analysis_validates_all_registered_rows_and_paired_intervals():
    analyzer = _load_analyzer()

    verdict = analyzer.analyze(
        _payload(), expected_documents=4, n_resamples=200
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
    ] == [-0.2, -0.2]
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
        "documents": 1,
        "aggregation_probes": 1,
        "needle_probes": 1,
        "mean_kl": 0.125,
        "accuracy_delta": -0.125,
        "lost_fact": 0.125,
        "lost_prior": 0.125,
    }
    assert "frozen subsample (reference)" in verdict["markdown_table"]
    assert verdict["budget_mode"] == (
        "archived-m1-per-document-matched-physical-v1"
    )
    assert verdict["per_document_budgets"]["legal/0"]["0.25"][
        "retained_token_count"
    ] == 2941


def test_q1_analysis_requires_the_exact_settled_negative_authorization():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["q1_authorization"]["settled_p0"]["p0_3_pass"] = True

    with pytest.raises(ValueError, match="authorization"):
        analyzer.analyze(payload, expected_documents=4, n_resamples=20)


def test_q1_analysis_rejects_partition_drift_between_arms():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["arms"]["merge-0.40"]["reports"][0]["needle_item_ids"] = ["drift"]

    with pytest.raises(ValueError, match="partition"):
        analyzer.analyze(payload, expected_documents=4, n_resamples=20)


def test_q1_analysis_rejects_nonzero_control_and_wrong_budget():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["arms"]["control-0.00"]["reports"][0]["aggregation_axis"][
        "mean_kl"
    ] = 1e-4

    with pytest.raises(ValueError, match="control"):
        analyzer.analyze(payload, expected_documents=4, n_resamples=20)


def test_q1_analysis_rejects_merge_eviction_per_document_budget_drift():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["arms"]["merge-0.25"]["reports"][1]["target_retained"] += 1

    with pytest.raises(ValueError, match="per-document budget"):
        analyzer.analyze(payload, expected_documents=4, n_resamples=20)


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
        analyzer.analyze(payload, expected_documents=4, n_resamples=20)


def test_q1_analysis_rejects_ninety_percent_data_disguised_as_moderate_arm():
    analyzer = _load_analyzer()
    payload = _payload()
    arm = payload["arms"]["merge-0.25"]
    arm["ratio"] = 0.90
    for report in arm["reports"]:
        report["target_retained"] = 410

    with pytest.raises(ValueError, match="ratio"):
        analyzer.analyze(payload, expected_documents=4, n_resamples=20)


def test_q1_analysis_rejects_missing_source_hashes_or_replay_checks():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["arms"]["merge-0.25"]["reports"][0]["source_hashes"] = {}
    with pytest.raises(ValueError, match="source hash"):
        analyzer.analyze(payload, expected_documents=4, n_resamples=20)

    payload = _payload()
    payload["archived_m1"]["replay_checks"][0]["pass"] = False
    with pytest.raises(ValueError, match="replay check"):
        analyzer.analyze(payload, expected_documents=4, n_resamples=20)


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
        "addendum_sha256": "a" * 64,
        "p0_verdict_sha256": "b" * 64,
    }
    assert (
        table_path.read_text()
        == json.loads(output_path.read_text())["markdown_table"]
    )
