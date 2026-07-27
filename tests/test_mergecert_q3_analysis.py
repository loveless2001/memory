import importlib.util
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
ANALYZER_PATH = (
    ROOT / "plans" / "260727-mergecert" / "analyze-mergecert-q3.py"
)


def _load_analyzer():
    spec = importlib.util.spec_from_file_location(
        "mergecert_q3_analysis", ANALYZER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture():
    item_ids = np.array(["a", "b", "c", "d"])
    domains = np.array(["financial", "legal", "code", "literature"])
    scores = {
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
    return scores, references, hashes


def test_q3_analysis_reports_kappa_directional_nesting_and_base_rates():
    analyzer = _load_analyzer()
    scores, references, hashes = _fixture()

    verdict = analyzer.analyze(
        scores, references, hashes, expected_items=4
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


def test_q3_analysis_rejects_reference_coverage_or_domain_drift():
    analyzer = _load_analyzer()
    scores, references, hashes = _fixture()
    references["FR"]["rows"].pop()
    references["FR"]["done"] = 3
    with pytest.raises(ValueError, match="FR.*coverage"):
        analyzer.analyze(scores, references, hashes, expected_items=4)

    scores, references, hashes = _fixture()
    references["A"]["rows"][0]["domain"] = "wrong"
    with pytest.raises(ValueError, match="domain"):
        analyzer.analyze(scores, references, hashes, expected_items=4)
