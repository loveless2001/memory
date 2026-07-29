import importlib.util
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
ANALYZER_PATH = (
    ROOT / "plans" / "260727-mergecert" / "analyze-mergecert-q3.py"
)
AMENDMENT_PATH = ROOT / "plans" / "260728-mergecert-q1" / "q2-amendment.json"
CANONICAL_TRIGGER_PATH = (
    ROOT / "plans" / "260728-mergecert-q1" / "q1-trigger.json"
)
CANONICAL_TRIGGER = json.loads(CANONICAL_TRIGGER_PATH.read_text())
Q1_ADDENDUM_SHA256 = (
    "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509"
)
Q1_P0_VERDICT_SHA256 = (
    "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
)


def _load_analyzer():
    spec = importlib.util.spec_from_file_location(
        "mergecert_q3_analysis", ANALYZER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _q1_trigger(**overrides):
    trigger = dict(CANONICAL_TRIGGER)
    trigger.update(overrides)
    return trigger


def _fixture(tmp_path):
    trigger_path = tmp_path / "q1-trigger.json"
    trigger_path.write_bytes(CANONICAL_TRIGGER_PATH.read_bytes())
    trigger = json.loads(trigger_path.read_text())
    trigger_sha256 = hashlib.sha256(trigger_path.read_bytes()).hexdigest()
    amendment_path = tmp_path / "q2-amendment.json"
    amendment_path.write_bytes(AMENDMENT_PATH.read_bytes())
    amendment_json = amendment_path.read_text()
    amendment = json.loads(amendment_json)
    amendment_sha256 = hashlib.sha256(amendment_path.read_bytes()).hexdigest()
    accounting_audit_sha256 = "a" * 64
    item_ids = np.array(["a", "b", "c", "d"])
    domains = np.array(["financial", "legal", "code", "literature"])
    scores = {
        "score_schema": np.array(["mergecert-q2-scores-amended-v2"]),
        "q1_trigger_json": np.array(
            [json.dumps(trigger, sort_keys=True, separators=(",", ":"))]
        ),
        "q1_trigger_sha256": np.array([trigger_sha256]),
        "q2_amendment_json": np.array([amendment_json]),
        "q2_amendment_sha256": np.array([amendment_sha256]),
        "q2_protocol_version": np.array([amendment["protocol_version"]]),
        "q2_namespace_version": np.array([amendment["namespace_version"]]),
        "q2_context_mechanics_version": np.array([
            amendment["context_mechanics_version"]
        ]),
        "accounting_audit_sha256": np.array([accounting_audit_sha256]),
        "item_ids": np.tile(item_ids, 2),
        "domain": np.tile(domains, 2),
        "ratio": np.repeat(np.array([0.25, 0.40]), 4),
        "y": np.array([0, 0, 0, 0, 1, 1, 0, 0], dtype=np.int8),
        "in_e1": np.ones(8, dtype=np.int8),
    }
    labels = {
        "A": [1, 0, 1, 0],
        "B": [1, 1, 1, 0],
        "FR": [1, 1, 0, 0],
        "E1F": [1, 0, 0, 0],
    }
    references = {
        name: {
            "done": 4,
            "rows": [
                {"item_id": item_id, "domain": domain, "y": y}
                for item_id, domain, y in zip(
                    item_ids[::-1], domains[::-1], values[::-1]
                )
            ],
        }
        for name, values in labels.items()
    }
    hashes = {name: f"sha-{name}" for name in references}
    q2_results = {
        "schema": "mergecert-q2-verdict-amended-v2",
        "score_schema": "mergecert-q2-scores-amended-v2",
        "q1_trigger": trigger,
        "q1_trigger_sha256": trigger_sha256,
        "source_hashes": {
            "q1_trigger": trigger_sha256,
            "q2_amendment": amendment_sha256,
        },
        "protocol_version": amendment["protocol_version"],
        "namespace_version": amendment["namespace_version"],
        "context_mechanics_version": amendment["context_mechanics_version"],
        "q2_amendment": amendment,
        "q2_amendment_sha256": amendment_sha256,
        "context_accounting_audit_sha256": accounting_audit_sha256,
        "accounting_audit_sha256": accounting_audit_sha256,
        "scores_sha256": "e" * 64,
    }
    return scores, references, hashes, q2_results, trigger_path, amendment_path


def test_q3_analysis_reports_kappa_directional_nesting_and_base_rates(tmp_path):
    analyzer = _load_analyzer()
    scores, references, hashes, q2_results, trigger_path, amendment_path = _fixture(tmp_path)

    verdict = analyzer.analyze(
        scores, references, hashes, q2_results,
        expected_items=4, trigger_path=trigger_path,
        amendment_path=amendment_path,
    )

    assert verdict["pass"] is True
    assert verdict["schema"] == "mergecert-q3-fragility-amended-v2"
    assert verdict["merge"]["failure_rate"] == 0.5
    assert verdict["comparisons"]["A"]["kappa"] == 0.0
    assert verdict["comparisons"]["A"]["nesting_fraction"] == 0.5
    assert verdict["comparisons"]["A"]["novel_merge_failures"] == 1
    assert verdict["comparisons"]["FR"]["kappa"] == 1.0
    assert verdict["comparisons"]["FR"]["nesting_fraction"] == 1.0
    assert verdict["headline_references"] == ["A", "FR", "E1F"]
    assert verdict["context_reference"] == "B"
    assert verdict["q1_trigger"] == json.loads(trigger_path.read_text())
    assert verdict["q1_trigger_sha256"] == hashlib.sha256(
        trigger_path.read_bytes()
    ).hexdigest()
    assert verdict["q2_amendment"] == json.loads(amendment_path.read_text())
    assert verdict["q2_amendment_sha256"] == hashlib.sha256(
        amendment_path.read_bytes()
    ).hexdigest()
    assert verdict["protocol_version"] == "mergecert-q2-amended-v2"
    assert verdict["namespace_version"] == "mergecert-q2-amended-v2"
    assert verdict["context_mechanics_version"] == (
        "mergecert-q2-context-mechanics-v2"
    )


def test_q3_analysis_rejects_reference_coverage_or_domain_drift(tmp_path):
    analyzer = _load_analyzer()
    scores, references, hashes, q2_results, trigger_path, amendment_path = _fixture(tmp_path)
    references["FR"]["rows"].pop()
    references["FR"]["done"] = 3
    with pytest.raises(ValueError, match="FR.*coverage"):
        analyzer.analyze(
            scores, references, hashes, q2_results,
            expected_items=4, trigger_path=trigger_path,
            amendment_path=amendment_path,
        )

    scores, references, hashes, q2_results, trigger_path, amendment_path = _fixture(tmp_path)
    references["A"]["rows"][0]["domain"] = "wrong"
    with pytest.raises(ValueError, match="domain"):
        analyzer.analyze(
            scores, references, hashes, q2_results,
            expected_items=4, trigger_path=trigger_path,
            amendment_path=amendment_path,
        )


def test_q3_analysis_rejects_missing_or_drifted_q1_authorization(tmp_path):
    analyzer = _load_analyzer()
    scores, references, hashes, q2_results, trigger_path, amendment_path = _fixture(tmp_path)

    with pytest.raises(ValueError, match="q1-trigger.json exists"):
        analyzer.analyze(
            scores, references, hashes, q2_results,
            expected_items=4, trigger_path=tmp_path / "missing.json",
            amendment_path=amendment_path,
        )

    trigger_path.write_text(json.dumps(_q1_trigger(favorable_intervals=["other"])))
    with pytest.raises(ValueError, match="Q2 is blocked"):
        analyzer.analyze(
            scores, references, hashes, q2_results,
            expected_items=4, trigger_path=trigger_path,
            amendment_path=amendment_path,
        )

    trigger_path.write_text(
        json.dumps(_q1_trigger(addendum_sha256="a" * 64))
    )
    with pytest.raises(ValueError, match="Q2 is blocked"):
        analyzer.analyze(
            scores, references, hashes, q2_results,
            expected_items=4, trigger_path=trigger_path,
            amendment_path=amendment_path,
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "local-amendment",
        "q2-amendment-payload",
        "q2-amendment-hash",
        "score-amendment-payload",
        "score-amendment-hash",
        "q2-verdict-schema",
        "score-schema",
        "q2-protocol-version",
        "score-protocol-version",
        "q2-namespace-version",
        "score-namespace-version",
        "q2-context-mechanics-version",
        "score-context-mechanics-version",
        "q2-accounting-audit-hash",
        "score-accounting-audit-hash",
        "near-ratio",
    ),
)
def test_q3_analysis_rejects_amended_q2_drift_before_e1_selection(
    tmp_path, monkeypatch, mutation
):
    """A stale Q2 protocol must not reach the fixed ratio-0.40 E1 selection."""
    analyzer = _load_analyzer()
    scores, references, hashes, q2_results, trigger_path, amendment_path = _fixture(tmp_path)
    if mutation == "local-amendment":
        amendment_path.write_bytes(amendment_path.read_bytes() + b"\n")
    elif mutation == "q2-amendment-payload":
        q2_results["q2_amendment"] = {**q2_results["q2_amendment"], "status": "stale"}
    elif mutation == "q2-amendment-hash":
        q2_results["q2_amendment_sha256"] = "0" * 64
    elif mutation == "score-amendment-payload":
        scores["q2_amendment_json"] = np.asarray(["{}"])
    elif mutation == "score-amendment-hash":
        scores["q2_amendment_sha256"] = np.asarray(["0" * 64])
    elif mutation == "q2-verdict-schema":
        q2_results["schema"] = "mergecert-q2-verdict-v1"
    elif mutation == "score-schema":
        scores["score_schema"] = np.asarray(["mergecert-q2-scores-v2"])
    elif mutation == "q2-protocol-version":
        q2_results["protocol_version"] = "mergecert-q2-v1"
    elif mutation == "score-protocol-version":
        scores["q2_protocol_version"] = np.asarray(["mergecert-q2-v1"])
    elif mutation == "q2-namespace-version":
        q2_results["namespace_version"] = "mergecert-q2-v1"
    elif mutation == "score-namespace-version":
        scores["q2_namespace_version"] = np.asarray(["mergecert-q2-v1"])
    elif mutation == "q2-context-mechanics-version":
        q2_results["context_mechanics_version"] = "fixed-4096"
    elif mutation == "score-context-mechanics-version":
        scores["q2_context_mechanics_version"] = np.asarray(["fixed-4096"])
    elif mutation == "q2-accounting-audit-hash":
        q2_results["context_accounting_audit_sha256"] = "0" * 64
    elif mutation == "score-accounting-audit-hash":
        scores["accounting_audit_sha256"] = np.asarray(["0" * 64])
    elif mutation == "near-ratio":
        scores["ratio"][4] = 0.4000005

    def selection_must_not_run(*args, **kwargs):
        raise AssertionError("amended Q2 drift reached ratio-0.40 E1 selection")

    monkeypatch.setattr(analyzer.np, "isclose", selection_must_not_run)
    with pytest.raises(ValueError):
        analyzer.analyze(
            scores, references, hashes, q2_results,
            expected_items=4, trigger_path=trigger_path,
            amendment_path=amendment_path,
        )


def test_actual_q2_analyzer_verdict_is_the_canonical_q3_input(tmp_path):
    from tests.test_mergecert_q2_analysis import (
        _fixture as q2_fixture,
        _load_analyzer as load_q2_analyzer,
        _write_amendment,
        _write_q1_trigger,
    )

    q2_analyzer = load_q2_analyzer()
    q3_analyzer = _load_analyzer()
    trigger_path = _write_q1_trigger(tmp_path)
    amendment_path = _write_amendment(tmp_path)
    routability, scores = q2_fixture(trigger_path, amendment_path)
    q2_verdict = q2_analyzer.analyze(
        routability,
        scores,
        expected_items_per_ratio=8,
        expected_e1_items=4,
        n_resamples=100,
        trigger_path=trigger_path,
        amendment_path=amendment_path,
        manifest_path=tmp_path / "capture-manifest.json",
    )
    selected = (scores["ratio"] == 0.40) & (scores["in_e1"] == 1)
    selected_ids = scores["item_ids"][selected]
    selected_domains = scores["domain"][selected]
    selected_labels = scores["y"][selected]
    references = {
        name: {
            "done": 4,
            "rows": [
                {"item_id": item_id, "domain": domain, "y": int(label)}
                for item_id, domain, label in zip(
                    selected_ids, selected_domains, selected_labels
                )
            ],
        }
        for name in ("A", "B", "FR", "E1F")
    }
    reference_hashes = {name: f"sha-{name}" for name in references}

    q3_verdict = q3_analyzer.analyze(
        scores,
        references,
        reference_hashes,
        q2_verdict,
        expected_items=4,
        trigger_path=trigger_path,
        amendment_path=amendment_path,
    )

    assert q2_verdict["schema"] == "mergecert-q2-verdict-amended-v2"
    assert q3_verdict["schema"] == "mergecert-q3-fragility-amended-v2"
    assert q3_verdict["q2_verdict_schema"] == q2_verdict["schema"]
