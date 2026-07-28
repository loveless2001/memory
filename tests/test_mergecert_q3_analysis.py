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


def _fixture(tmp_path):
    trigger_path = tmp_path / "q1-trigger.json"
    trigger_path.write_text(json.dumps(_q1_trigger()))
    trigger = json.loads(trigger_path.read_text())
    trigger_sha256 = hashlib.sha256(trigger_path.read_bytes()).hexdigest()
    item_ids = np.array(["a", "b", "c", "d"])
    domains = np.array(["financial", "legal", "code", "literature"])
    scores = {
        "q1_trigger_json": np.array(
            [json.dumps(trigger, sort_keys=True, separators=(",", ":"))]
        ),
        "q1_trigger_sha256": np.array([trigger_sha256]),
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
        "q1_trigger": trigger,
        "q1_trigger_sha256": trigger_sha256,
        "source_hashes": {"q1_trigger": trigger_sha256},
    }
    return scores, references, hashes, q2_results, trigger_path


def test_q3_analysis_reports_kappa_directional_nesting_and_base_rates(tmp_path):
    analyzer = _load_analyzer()
    scores, references, hashes, q2_results, trigger_path = _fixture(tmp_path)

    verdict = analyzer.analyze(
        scores, references, hashes, q2_results,
        expected_items=4, trigger_path=trigger_path,
    )

    assert verdict["pass"] is True
    assert verdict["merge"]["failure_rate"] == 0.5
    assert verdict["comparisons"]["A"]["kappa"] == 0.0
    assert verdict["comparisons"]["A"]["nesting_fraction"] == 0.5
    assert verdict["comparisons"]["A"]["novel_merge_failures"] == 1
    assert verdict["comparisons"]["FR"]["kappa"] == 1.0
    assert verdict["comparisons"]["FR"]["nesting_fraction"] == 1.0
    assert verdict["headline_references"] == ["A", "FR", "E1F"]
    assert verdict["context_reference"] == "B"


def test_q3_analysis_rejects_reference_coverage_or_domain_drift(tmp_path):
    analyzer = _load_analyzer()
    scores, references, hashes, q2_results, trigger_path = _fixture(tmp_path)
    references["FR"]["rows"].pop()
    references["FR"]["done"] = 3
    with pytest.raises(ValueError, match="FR.*coverage"):
        analyzer.analyze(
            scores, references, hashes, q2_results,
            expected_items=4, trigger_path=trigger_path,
        )

    scores, references, hashes, q2_results, trigger_path = _fixture(tmp_path)
    references["A"]["rows"][0]["domain"] = "wrong"
    with pytest.raises(ValueError, match="domain"):
        analyzer.analyze(
            scores, references, hashes, q2_results,
            expected_items=4, trigger_path=trigger_path,
        )


def test_q3_analysis_rejects_missing_or_drifted_q1_authorization(tmp_path):
    analyzer = _load_analyzer()
    scores, references, hashes, q2_results, trigger_path = _fixture(tmp_path)

    with pytest.raises(ValueError, match="q1-trigger.json exists"):
        analyzer.analyze(
            scores, references, hashes, q2_results,
            expected_items=4, trigger_path=tmp_path / "missing.json",
        )

    trigger_path.write_text(json.dumps(_q1_trigger(favorable_intervals=["other"])))
    with pytest.raises(ValueError, match="trigger.*Q2 result"):
        analyzer.analyze(
            scores, references, hashes, q2_results,
            expected_items=4, trigger_path=trigger_path,
        )

    trigger_path.write_text(
        json.dumps(_q1_trigger(addendum_sha256="a" * 64))
    )
    with pytest.raises(ValueError, match="Q2 is blocked"):
        analyzer.analyze(
            scores, references, hashes, q2_results,
            expected_items=4, trigger_path=trigger_path,
        )
