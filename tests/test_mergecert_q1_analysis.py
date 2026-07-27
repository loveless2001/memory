import importlib.util
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


def _report(doc_id, ratio, *, kl, acc_delta, lost, lost_prior):
    retained = 4096 - int(4096 * ratio)
    return {
        "doc_id": doc_id,
        "domain": doc_id.split("/", 1)[0],
        "context_sha256": f"sha-{doc_id}",
        "context_token_count": 4096,
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


def _payload():
    docs = ["financial/0", "legal/0", "code/0", "literature/0"]
    arms = {}
    for ratio in (0.25, 0.40, 0.90):
        arms[f"eviction-{ratio:.2f}"] = {
            "policy": "contiguous-eviction",
            "ratio": ratio,
            "target_retained": 4096 - int(4096 * ratio),
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
            "target_retained": 4096 - int(4096 * ratio),
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
        "target_retained": 4096,
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
            "ratios": [0.25, 0.40, 0.90],
            "sink_token_count": 4,
        },
        "q1_gate": {"p0_pass": True, "p0_verdict_sha256": "gate-sha"},
        "archived_m1": {
            "replay_pass": True,
            "replay_checks": [
                {
                    "archive": f"{domain}-evict{ratio:.2f}.json",
                    "doc_id": f"{domain}/0",
                    "pass": True,
                    "mismatches": [],
                }
                for domain in ("financial", "legal", "code", "literature")
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
                "context_token_count": 4096,
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
        "eviction-0.90",
        "merge-0.25",
        "merge-0.40",
        "merge-0.90",
    }
    assert verdict["summaries"]["control-0.00"]["mean_kl"] == 0.0
    assert verdict["paired_merge_minus_eviction"]["0.40"]["mean_kl"][
        "ci95"
    ] == [-0.2, -0.2]
    assert "frozen subsample (reference)" in verdict["markdown_table"]


def test_q1_analysis_fails_closed_when_p0_did_not_pass():
    analyzer = _load_analyzer()
    payload = _payload()
    payload["q1_gate"]["p0_pass"] = False

    with pytest.raises(ValueError, match="P0 gate"):
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

    payload = _payload()
    payload["arms"]["merge-0.90"]["target_retained"] = 411
    with pytest.raises(ValueError, match="budget"):
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
