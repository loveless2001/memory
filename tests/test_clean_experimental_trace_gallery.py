from copy import deepcopy
import json
from pathlib import Path

import pytest

from examples.build_clean_experimental_traces import (
    build_gallery,
    generate,
    validate_source,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "plans/260719-2328-e1full-unfrozen-full-recipe/"
    "summary-e1full-clean-v1-n60.json"
)


def load_source():
    return json.loads(SOURCE.read_text())


def test_rejects_unknown_clean_provenance():
    source = deepcopy(load_source())
    source["provenance"]["holdout_sha256"] = "tampered"

    with pytest.raises(ValueError, match="holdout_sha256"):
        validate_source(source)


def test_selects_three_distinct_registered_trace_categories():
    gallery = build_gallery(load_source())

    assert [
        (trace["category"], trace["document_id"])
        for trace in gallery["traces"]
    ] == [
        ("pointwise_recovery", "financial/00009"),
        ("axis_disagreement", "code/00011"),
        ("depth4_collapse", "financial/00002"),
    ]


def test_trace_records_align_real_predictions_across_all_arms():
    gallery = build_gallery(load_source())

    for trace in gallery["traces"]:
        assert set(trace["arm_metrics"]) == {
            "eviction-matched",
            "compactor-d1",
            "compactor-d4",
            "control-0",
        }
        assert trace["probe_records"]
        for record in trace["probe_records"]:
            assert len(record["options"]) == 4
            assert record["gold"] in "ABCD"
            assert set(record["pred_compacted_by_arm"]) == {
                "eviction-matched",
                "compactor-d1",
                "compactor-d4",
                "control-0",
            }
            assert all(
                prediction in "ABCD"
                for prediction in record["pred_compacted_by_arm"].values()
            )


def test_generate_writes_stable_json_and_markdown(tmp_path):
    json_out = tmp_path / "traces.json"
    markdown_out = tmp_path / "README.md"

    generate(SOURCE, json_out, markdown_out)

    gallery = json.loads(json_out.read_text())
    assert gallery["schema_version"] == "clean-e1full-trace-gallery-v1"
    assert len(gallery["traces"]) == 3
    markdown = markdown_out.read_text()
    assert "Real Held-Out E1FULL Certification Traces" in markdown
    assert "not token-level generation logs" in markdown
    assert markdown.endswith("\n")
