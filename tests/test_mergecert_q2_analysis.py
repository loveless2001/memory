import importlib.util
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from memsub.certification import (
    Q2_ACCOUNTING_ARRAY_FIELDS,
    Q2_CONTEXT_MECHANICS_VERSION,
    expected_q2_plan_fields,
    validate_q2_accounting_arrays,
)
from memsub.certification.mergecert_statistics import document_split


ROOT = Path(__file__).resolve().parents[1]
ANALYZER_PATH = (
    ROOT / "plans" / "260727-mergecert" / "analyze-mergecert-q2.py"
)
AMENDMENT_PATH = ROOT / "plans" / "260728-mergecert-q1" / "q2-amendment.json"
Q1_ADDENDUM_SHA256 = (
    "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509"
)
Q1_P0_VERDICT_SHA256 = (
    "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
)
ARMS = (
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


def _load_analyzer():
    spec = importlib.util.spec_from_file_location(
        "mergecert_q2_analysis", ANALYZER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _test_documents(n=8):
    documents = []
    index = 0
    while len(documents) < n:
        candidate = f"doc-{index}"
        if document_split(np.array([candidate]))[0] == 2:
            documents.append(candidate)
        index += 1
    return np.array(documents)


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


def _write_q1_trigger(tmp_path, trigger=None):
    path = tmp_path / "q1-trigger.json"
    path.write_text(json.dumps(trigger or _q1_trigger()))
    return path


def _write_amendment(tmp_path):
    path = tmp_path / "q2-amendment.json"
    path.write_bytes(AMENDMENT_PATH.read_bytes())
    return path


def _fixture(trigger_path, amendment_path=AMENDMENT_PATH):
    trigger = json.loads(trigger_path.read_text())
    trigger_sha256 = hashlib.sha256(trigger_path.read_bytes()).hexdigest()
    amendment = json.loads(amendment_path.read_text())
    amendment_json = amendment_path.read_text()
    amendment_sha256 = hashlib.sha256(amendment_path.read_bytes()).hexdigest()
    docs = _test_documents()
    n = len(docs)
    y = np.array([0, 1] * (n // 2), dtype=np.int8)
    item_ids = np.array([f"item-{index}" for index in range(n)])
    manifest_path = trigger_path.parent / "capture-manifest.json"
    manifest = [
        {
            "item_id": item_id,
            "doc_id": doc_id,
            "domain": domain,
            "chunk_rel_start": 100 + index,
        }
        for index, (item_id, doc_id, domain) in enumerate(
            zip(
                item_ids,
                docs,
                np.array(["financial", "legal", "code", "literature"] * 2),
            )
        )
    ]
    manifest_path.write_text(json.dumps(manifest))
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    arrays = {
        "q1_trigger_json": np.array(
            [
                json.dumps(
                    trigger,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ]
        ),
        "q1_trigger_sha256": np.array([trigger_sha256]),
        "item_ids": np.tile(item_ids, 2),
        "doc_ids": np.tile(docs, 2),
        "domain": np.tile(
            np.array(["financial", "legal", "code", "literature"] * 2),
            2,
        ),
        "ratio": np.repeat(
            np.array([0.25, 0.40], dtype=np.float64), n
        ),
        "y": np.tile(y, 2),
        "split": np.full(2 * n, 2, dtype=np.int8),
        "in_e1": np.tile(
            np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=np.int8), 2
        ),
    }
    for arm in ARMS:
        arrays[f"{arm}_separate"] = arrays["y"].astype(np.float32)
        arrays[f"{arm}_pooled"] = arrays["y"].astype(np.float32)
    flattened_contexts = np.tile(
        np.asarray([4073, 4096, 4096, 4096, 4096, 4096, 4096, 4096]), 2
    )
    flattened_chunk_starts = np.tile(np.arange(100, 108), 2)
    for index, ratio in enumerate((0.25, 0.40)):
        start = index * n
        end = start + n
        plans = [expected_q2_plan_fields(int(context), ratio) for context in flattened_contexts[start:end]]
        arrays.setdefault("item_id", arrays["item_ids"].copy())
        arrays.setdefault(
            "context_mechanics_version",
            np.full(2 * n, Q2_CONTEXT_MECHANICS_VERSION),
        )
        arrays.setdefault("source_document_token_count", flattened_contexts.copy())
        arrays.setdefault("source_context_start", np.zeros(2 * n, dtype=np.int64))
        arrays.setdefault("source_context_end", flattened_contexts.copy())
        arrays.setdefault("source_context_token_count", flattened_contexts.copy())
        arrays.setdefault("model_input_token_count", flattened_contexts.copy())
        arrays.setdefault("source_chunk_token_start", flattened_chunk_starts.copy())
        arrays.setdefault("source_chunk_context_start", flattened_chunk_starts.copy())
        for field in (
            "requested_eviction_start", "requested_eviction_end",
            "requested_evicted_token_count", "retained_token_count",
            "merge_target_retained", "merge_recent_start",
        ):
            values = arrays.get(field, np.empty(2 * n, dtype=np.int64))
            values[start:end] = [plan[field] for plan in plans]
            arrays[field] = values
        arrays.setdefault("physical_before_count", flattened_contexts.copy())
        arrays.setdefault("physical_after_count", np.empty(2 * n, dtype=np.int64))
        arrays.setdefault("physical_removed_count", np.empty(2 * n, dtype=np.int64))
        arrays["physical_after_count"][start:end] = [
            plan["retained_token_count"] for plan in plans
        ]
        arrays["physical_removed_count"][start:end] = [
            plan["requested_evicted_token_count"] for plan in plans
        ]
    audits = {}
    for ratio in (0.25, 0.40):
        mask = np.isclose(arrays["ratio"], ratio)
        segment = {field: arrays[field][mask] for field in Q2_ACCOUNTING_ARRAY_FIELDS}
        rows = [
            {"item_id": item_id, "chunk_rel_start": int(chunk_start)}
            for item_id, chunk_start in zip(
                arrays["item_ids"][mask], arrays["source_chunk_token_start"][mask]
            )
        ]
        audits[f"{ratio:.2f}"] = validate_q2_accounting_arrays(
            segment, rows, ratio
        )
    accounting_audit_sha256 = hashlib.sha256(
        json.dumps(audits, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    capture_summary_sha256 = "d" * 64
    arrays.update({
        "q2_amendment_json": np.array([amendment_json]),
        "q2_amendment_sha256": np.array([amendment_sha256]),
        "q2_protocol_version": np.array([amendment["protocol_version"]]),
        "q2_namespace_version": np.array([amendment["namespace_version"]]),
        "q2_context_mechanics_version": np.array([
            amendment["context_mechanics_version"]
        ]),
        "capture_summary_sha256": np.array([capture_summary_sha256]),
        "source_manifest_sha256": np.array([manifest_sha256]),
        "accounting_audit_sha256": np.array([accounting_audit_sha256]),
    })
    perfect = {
        "auc": 1.0,
        "ci95": [1.0, 1.0],
        "n_items": n,
        "n_documents": n,
        "positive_rate": 0.5,
        "n_resamples": 100,
        "per_domain_auc": {},
    }
    payload = {
        "q1_trigger": trigger,
        "q1_trigger_sha256": trigger_sha256,
        "model_id": "Qwen/Qwen3-4B-Instruct-2507",
        "ratios": [0.25, 0.40],
        "seeds": [0, 1, 2],
        "source_hashes": {
            "scores": "source",
            "q1_trigger": trigger_sha256,
            "q2_amendment": amendment_sha256,
            "capture_summary": capture_summary_sha256,
            "manifest": manifest_sha256,
        },
        "protocol_version": amendment["protocol_version"],
        "namespace_version": amendment["namespace_version"],
        "context_mechanics_version": amendment["context_mechanics_version"],
        "q2_amendment": amendment,
        "q2_amendment_sha256": amendment_sha256,
        "capture_summary_sha256": capture_summary_sha256,
        "manifest_sha256": manifest_sha256,
        "accounting_audit": audits,
        "accounting_audit_sha256": accounting_audit_sha256,
        "ratios_results": {
            key: {
                "items": n,
                "positive_rate": 0.5,
                "arms": {arm: dict(perfect) for arm in ARMS},
            }
            for key in ("0.25", "0.40")
        },
        "pooled": {
            "items": 2 * n,
            "positive_rate": 0.5,
            "arms": {
                arm: {**perfect, "n_items": 2 * n} for arm in ARMS
            },
        },
    }
    return payload, arrays


def test_q2_analysis_recomputes_every_headline_auc_and_emits_f5_table(tmp_path):
    analyzer = _load_analyzer()
    trigger_path = _write_q1_trigger(tmp_path)
    amendment_path = _write_amendment(tmp_path)
    payload, arrays = _fixture(trigger_path, amendment_path)

    verdict = analyzer.analyze(
        payload, arrays, expected_items_per_ratio=8,
        expected_e1_items=4, n_resamples=100, trigger_path=trigger_path,
        amendment_path=amendment_path,
        manifest_path=trigger_path.parent / "capture-manifest.json",
    )

    assert verdict["pass"] is True
    assert verdict["ratios"]["0.25"]["mechanics_refit"]["auc"] == 1.0
    assert verdict["pooled"]["residual_mlp"]["auc"] == 1.0
    assert "compactor to merge" in verdict["f5_markdown_table"]
    assert "mechanics-routable" in verdict["registered_reading"]
    assert verdict["q1_trigger"] == json.loads(trigger_path.read_text())
    assert verdict["q1_trigger_sha256"] == hashlib.sha256(
        trigger_path.read_bytes()
    ).hexdigest()
    assert verdict["q2_amendment"] == json.loads(amendment_path.read_text())
    assert verdict["q2_amendment_sha256"] == hashlib.sha256(
        amendment_path.read_bytes()
    ).hexdigest()
    assert verdict["context_accounting_audit"] == payload["accounting_audit"]
    assert verdict["context_accounting_audit_sha256"] == payload[
        "accounting_audit_sha256"
    ]


@pytest.mark.parametrize(
    "mutation",
    (
        "local-amendment-bytes",
        "payload-amendment",
        "payload-amendment-hash",
        "score-amendment",
        "score-amendment-json",
        "protocol-version",
        "namespace-version",
        "fixed-short-context",
        "shifted-context-range",
        "physical-count",
        "capture-summary-hash",
        "accounting-audit-hash",
        "ratio-count",
        "ratio-id",
        "manifest-association",
    ),
)
def test_q2_analysis_rejects_amendment_and_accounting_drift_before_metrics(
    tmp_path, monkeypatch, mutation
):
    """A missing validation gate would let a stale score archive reach AUC recomputation."""
    analyzer = _load_analyzer()
    trigger_path = _write_q1_trigger(tmp_path)
    amendment_path = _write_amendment(tmp_path)
    payload, arrays = _fixture(trigger_path, amendment_path)
    if mutation == "local-amendment-bytes":
        amendment_path.write_bytes(amendment_path.read_bytes() + b"\n")
    elif mutation == "payload-amendment":
        payload["q2_amendment"] = {**payload["q2_amendment"], "status": "stale"}
    elif mutation == "payload-amendment-hash":
        payload["q2_amendment_sha256"] = "0" * 64
    elif mutation == "score-amendment":
        arrays["q2_amendment_sha256"] = np.asarray(["0" * 64])
    elif mutation == "score-amendment-json":
        arrays["q2_amendment_json"] = np.asarray(["{}"])
    elif mutation == "protocol-version":
        arrays["q2_protocol_version"] = np.asarray(["mergecert-q2-v1"])
    elif mutation == "namespace-version":
        payload["namespace_version"] = "mergecert-q2-v1"
    elif mutation == "fixed-short-context":
        fixed = expected_q2_plan_fields(4096, 0.25)
        for field in ("source_document_token_count", "source_context_end",
                      "source_context_token_count", "model_input_token_count",
                      "physical_before_count"):
            arrays[field][0] = 4096
        for field, value in fixed.items():
            arrays[field][0] = value
    elif mutation == "shifted-context-range":
        arrays["source_context_start"][0] = 1
        arrays["source_context_end"][0] += 1
        arrays["source_chunk_context_start"][0] -= 1
    elif mutation == "physical-count":
        arrays["physical_removed_count"][0] += 1
    elif mutation == "capture-summary-hash":
        arrays["capture_summary_sha256"] = np.asarray(["0" * 64])
    elif mutation == "accounting-audit-hash":
        arrays["accounting_audit_sha256"] = np.asarray(["0" * 64])
    elif mutation == "ratio-count":
        arrays["ratio"][0] = 0.40
    elif mutation == "ratio-id":
        arrays["item_ids"][0] = arrays["item_ids"][1]
    elif mutation == "manifest-association":
        arrays["doc_ids"][0] = arrays["doc_ids"][1]

    def no_metric_recomputation(*args, **kwargs):
        raise AssertionError("amendment/accounting drift reached metric recomputation")

    monkeypatch.setattr(analyzer, "_recompute_metric", no_metric_recomputation)
    with pytest.raises(ValueError):
        analyzer.analyze(
            payload, arrays, expected_items_per_ratio=8,
            expected_e1_items=4, n_resamples=20, trigger_path=trigger_path,
            amendment_path=amendment_path,
            manifest_path=trigger_path.parent / "capture-manifest.json",
        )


def test_q2_analysis_rejects_remote_metric_drift_and_split_tampering(tmp_path):
    analyzer = _load_analyzer()
    trigger_path = _write_q1_trigger(tmp_path)
    amendment_path = _write_amendment(tmp_path)
    payload, arrays = _fixture(trigger_path, amendment_path)
    payload["ratios_results"]["0.25"]["arms"]["mechanics_refit"]["auc"] = 0.9
    with pytest.raises(ValueError, match="remote/local AUC"):
        analyzer.analyze(
            payload, arrays, expected_items_per_ratio=8,
            expected_e1_items=4, n_resamples=20, trigger_path=trigger_path,
            amendment_path=amendment_path,
            manifest_path=trigger_path.parent / "capture-manifest.json",
        )

    payload, arrays = _fixture(trigger_path, amendment_path)
    arrays["split"][0] = 0
    with pytest.raises(ValueError, match="split"):
        analyzer.analyze(
            payload, arrays, expected_items_per_ratio=8,
            expected_e1_items=4, n_resamples=20, trigger_path=trigger_path,
            amendment_path=amendment_path,
            manifest_path=trigger_path.parent / "capture-manifest.json",
        )


@pytest.mark.parametrize(
    "trigger",
    (
        {"protocol": "MERGECERT-Q1", "run_q2_q3": False},
        {
            "protocol": "MERGECERT-Q1",
            "run_q2_q3": True,
            "favorable_intervals": [],
            "q1_verdict_sha256": "c" * 64,
            "addendum_sha256": "a" * 64,
            "p0_verdict_sha256": "b" * 64,
        },
        {
            "protocol": "MERGECERT-Q1",
            "run_q2_q3": True,
            "favorable_intervals": ["0.40:mean_kl"],
            "q1_verdict_sha256": "c" * 63,
            "addendum_sha256": "a" * 64,
            "p0_verdict_sha256": "b" * 64,
        },
        _q1_trigger(favorable_intervals=[None]),
        _q1_trigger(favorable_intervals={"0.40:mean_kl": True}),
        _q1_trigger(q1_verdict_sha256=["c"] * 64),
        _q1_trigger(budget_mode="fixed-4096"),
        _q1_trigger(addendum_sha256="a" * 64),
        _q1_trigger(p0_verdict_sha256="b" * 64),
    ),
)
def test_q2_analysis_rejects_an_invalid_registered_q1_trigger(tmp_path, trigger):
    analyzer = _load_analyzer()
    trigger_path = _write_q1_trigger(tmp_path, trigger)
    payload, arrays = _fixture(trigger_path)

    with pytest.raises(ValueError, match="Q2 is blocked"):
        analyzer.analyze(
            payload, arrays, expected_items_per_ratio=8,
            expected_e1_items=4, n_resamples=20, trigger_path=trigger_path,
        )


def test_q2_analysis_accepts_the_registered_q1_trigger_file(tmp_path):
    analyzer = _load_analyzer()
    trigger_path = _write_q1_trigger(tmp_path)
    trigger = _fixture(trigger_path)[0]["q1_trigger"]

    assert analyzer._require_q1_trigger(str(trigger_path)) == trigger


def test_q2_analysis_rejects_score_manifest_q1_trigger_drift(tmp_path):
    analyzer = _load_analyzer()
    trigger_path = _write_q1_trigger(tmp_path)
    payload, arrays = _fixture(trigger_path)
    arrays["q1_trigger_sha256"] = np.array(["e" * 64])

    with pytest.raises(ValueError, match="score manifest Q1 trigger"):
        analyzer.analyze(
            payload, arrays, expected_items_per_ratio=8,
            expected_e1_items=4, n_resamples=20, trigger_path=trigger_path,
        )


def test_q2_analysis_rejects_a_stale_trigger_file_with_matching_copies(tmp_path):
    analyzer = _load_analyzer()
    trigger_path = _write_q1_trigger(tmp_path)
    payload, arrays = _fixture(trigger_path)
    trigger_path.write_text(json.dumps(_q1_trigger(favorable_intervals=["other"])))

    with pytest.raises(ValueError, match="trigger.*result"):
        analyzer.analyze(
            payload, arrays, expected_items_per_ratio=8,
            expected_e1_items=4, n_resamples=20, trigger_path=trigger_path,
        )
