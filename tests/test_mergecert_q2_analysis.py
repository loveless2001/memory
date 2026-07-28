import importlib.util
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from memsub.certification.mergecert_statistics import document_split


ROOT = Path(__file__).resolve().parents[1]
ANALYZER_PATH = (
    ROOT / "plans" / "260727-mergecert" / "analyze-mergecert-q2.py"
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
        "run_q2_q3": True,
        "favorable_intervals": ["0.40:mean_kl"],
        "q1_verdict_sha256": "c" * 64,
        "addendum_sha256": "a" * 64,
        "p0_verdict_sha256": "b" * 64,
    }
    trigger.update(overrides)
    return trigger


def _write_q1_trigger(tmp_path, trigger=None):
    path = tmp_path / "q1-trigger.json"
    path.write_text(json.dumps(trigger or _q1_trigger()))
    return path


def _fixture(trigger_path):
    trigger = json.loads(trigger_path.read_text())
    trigger_sha256 = hashlib.sha256(trigger_path.read_bytes()).hexdigest()
    docs = _test_documents()
    n = len(docs)
    y = np.array([0, 1] * (n // 2), dtype=np.int8)
    item_ids = np.array([f"item-{index}" for index in range(n)])
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
            np.array([0.25, 0.40], dtype=np.float32), n
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
        },
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
    payload, arrays = _fixture(trigger_path)

    verdict = analyzer.analyze(
        payload, arrays, expected_items_per_ratio=8,
        expected_e1_items=4, n_resamples=100, trigger_path=trigger_path,
    )

    assert verdict["pass"] is True
    assert verdict["ratios"]["0.25"]["mechanics_refit"]["auc"] == 1.0
    assert verdict["pooled"]["residual_mlp"]["auc"] == 1.0
    assert "compactor to merge" in verdict["f5_markdown_table"]
    assert "mechanics-routable" in verdict["registered_reading"]


def test_q2_analysis_rejects_remote_metric_drift_and_split_tampering(tmp_path):
    analyzer = _load_analyzer()
    trigger_path = _write_q1_trigger(tmp_path)
    payload, arrays = _fixture(trigger_path)
    payload["ratios_results"]["0.25"]["arms"]["mechanics_refit"]["auc"] = 0.9
    with pytest.raises(ValueError, match="remote/local AUC"):
        analyzer.analyze(
            payload, arrays, expected_items_per_ratio=8,
            expected_e1_items=4, n_resamples=20, trigger_path=trigger_path,
        )

    payload, arrays = _fixture(trigger_path)
    arrays["split"][0] = 0
    with pytest.raises(ValueError, match="split"):
        analyzer.analyze(
            payload, arrays, expected_items_per_ratio=8,
            expected_e1_items=4, n_resamples=20, trigger_path=trigger_path,
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
