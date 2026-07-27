import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYZER_PATH = (
    ROOT / "plans" / "260727-mergecert" / "analyze-mergecert-p0.py"
)


def _load_analyzer():
    spec = importlib.util.spec_from_file_location("mergecert_p0_analysis", ANALYZER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload(merge_lost, eviction_lost):
    domains = ("financial", "legal", "code", "literature")
    rows = []
    for index, (merge, eviction) in enumerate(zip(merge_lost, eviction_lost)):
        rows.append(
            {
                "item_id": f"item-{index}",
                "doc_id": f"{domains[index % 4]}/doc-{index // 2}",
                "domain": domains[index % 4],
                "full_correct": 1,
                "merge_correct": 1 - merge,
                "eviction_correct": 1 - eviction,
                "streaming_correct": 1 - eviction,
                "merge_lost_prior_correct": merge,
                "eviction_lost_prior_correct": eviction,
                "streaming_lost_prior_correct": eviction,
                "merge_kl": 0.2,
                "eviction_kl": 0.3,
                "streaming_kl": 0.3,
                "merge_streaming_prediction_equal": 0,
                "attention_mass_min": 0.0,
                "attention_mass_max": 2.0,
                "attention_mass_variance": 0.2,
            }
        )
    return {
        "rows": rows,
        "done": len(rows),
        "sample_item_ids": [row["item_id"] for row in rows],
        "structure": {
            "target_retained": 410,
            "non_singleton_blocks": 203,
            "exact_slot_jaccard": 0.5,
            "cache_tensor_identical": False,
            "physical_max_abs_kv_difference": 2.0,
            "aligned_exact_max_abs_kv_difference": 0.0,
        },
    }


def test_p0_analysis_passes_only_when_merge_beats_eviction_with_a_negative_ci():
    analyzer = _load_analyzer()
    payload = _payload([0] * 8, [1] * 8)

    verdict = analyzer.analyze(payload, expected_items=8, n_resamples=200)

    assert verdict["p0_3"]["merge_lost_given_prior_correct"] == 0.0
    assert verdict["p0_3"]["eviction_lost_given_prior_correct"] == 1.0
    assert verdict["p0_3"]["paired_merge_minus_eviction"]["ci95"] == [-1.0, -1.0]
    assert verdict["p0_3"]["pass"] is True
    assert verdict["p0_4"]["pass"] is True
    assert verdict["p0_pass"] is True


def test_p0_analysis_fails_the_direction_gate_when_loss_is_equal():
    analyzer = _load_analyzer()
    payload = _payload([1] * 8, [1] * 8)

    verdict = analyzer.analyze(payload, expected_items=8, n_resamples=200)

    assert verdict["p0_3"]["paired_merge_minus_eviction"]["ci95"] == [0.0, 0.0]
    assert verdict["p0_3"]["pass"] is False
    assert verdict["p0_pass"] is False
