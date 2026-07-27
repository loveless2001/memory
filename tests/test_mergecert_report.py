import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "plans" / "260727-mergecert"
RENDERER = PLAN / "render-mergecert-report.py"
VALIDATOR = PLAN / "validate-mergecert-report.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _positive_evidence():
    return {
        "source": {
            "repository": "https://github.com/jkdkr2439/KV-Merge",
            "commit": "cd4ed948d62231449dbab9669608bbb4fd220713",
            "files": {
                "README.md": (
                    "edfd5236d99dab5d6e4bf80b74dd79a54ffd94cec4b7066511dc6fd7ae7cae17"
                ),
                "benchmarks/modal_kv_real_bench.py": (
                    "518b2d2cd4b652f4cc83ef9c82593fe624301986e0e3e22780ee9f0bfe423bb8"
                ),
                "lego_server.py": (
                    "f1df91c8af05cf4ea5000f4027450bf91e5e269f4e922da8979fc0885d6ff228"
                ),
            },
            "port": {
                "model_id": "Qwen/Qwen3-4B-Instruct-2507",
            },
        },
        "p0": {
            "p0_pass": True,
            "stop_q1_q3": False,
            "sample": {
                "n_items": 200,
                "n_documents": 120,
                "domain_counts": {
                    "financial": 50,
                    "legal": 50,
                    "code": 50,
                    "literature": 50,
                },
                "prior_correct": 180,
                "pass": True,
            },
            "p0_3": {
                "merge_lost_given_prior_correct": 0.20,
                "eviction_lost_given_prior_correct": 0.60,
                "paired_merge_minus_eviction": {
                    "mean_diff": -0.40,
                    "ci95": [-0.50, -0.30],
                },
                "merge_accuracy_delta": -0.10,
                "eviction_accuracy_delta": -0.40,
                "mean_merge_kl": 0.2,
                "mean_eviction_kl": 0.8,
                "pass": True,
            },
            "p0_4": {
                "exact_slot_jaccard": 0.5,
                "non_singleton_blocks": 203,
                "merge_streaming_prediction_equal_rate": 0.4,
                "aligned_exact_max_abs_kv_difference": 0.0,
                "physical_max_abs_kv_difference": 2.0,
                "pass": True,
            },
            "real_attention": {
                "minimum": 0.0,
                "maximum": 2.0,
                "minimum_variance": 0.1,
                "pass": True,
            },
        },
        "q1": {
            "pass": True,
            "summaries": {
                "eviction-0.25": {"lost_prior": 0.55},
                "eviction-0.40": {"lost_prior": 0.65},
                "merge-0.25": {"lost_prior": 0.20},
                "merge-0.40": {"lost_prior": 0.30},
            },
            "paired_merge_minus_eviction": {
                "0.25": {
                    "lost_prior": {
                        "mean_diff": -0.35,
                        "ci95": [-0.45, -0.25],
                    }
                },
                "0.40": {
                    "lost_prior": {
                        "mean_diff": -0.35,
                        "ci95": [-0.47, -0.23],
                    }
                },
            },
            "markdown_table": (
                "| arm | agg KL | agg accDelta | pointwise lost|prior |\n"
                "|---|---:|---:|---:|\n"
                "| MERGE 0.25 | 0.1000 | +0.010 | 0.200 |\n"
                "| MERGE 0.40 | 0.2000 | -0.010 | 0.300 |\n"
                "| MERGE 0.90 | 0.8000 | -0.300 | 0.700 |\n"
                "| frozen subsample (reference) | 0.2566 | +0.063 | 0.188 |\n"
                "| unfrozen compactor (reference) | 0.1385 | +0.042 | 0.083 |\n"
                "| zero-compression control | 0.0000 | +0.000 | 0.000 |\n"
            ),
        },
        "q2": {
            "pass": True,
            "ratios": {
                "0.25": {
                    "mechanics_refit": {"auc": 0.75, "ci95": [0.72, 0.78]},
                    "residual_mlp": {"auc": 0.82, "ci95": [0.80, 0.84]},
                    "sink_refit": {"auc": 0.74, "ci95": [0.71, 0.77]},
                },
                "0.40": {
                    "mechanics_refit": {"auc": 0.73, "ci95": [0.70, 0.76]},
                    "residual_mlp": {"auc": 0.81, "ci95": [0.79, 0.83]},
                    "sink_refit": {"auc": 0.72, "ci95": [0.69, 0.75]},
                },
            },
            "registered_reading": "Merged loss is mechanics-routable.",
            "markdown_table": (
                "| arm | merge 0.25 | merge 0.40 | pooled |\n"
                "|---|---:|---:|---:|\n"
                "| merge mechanics refit | 0.7500 | 0.7300 | 0.7400 |\n"
                "| residual best-layer MLP | 0.8200 | 0.8100 | 0.8150 |\n"
            ),
            "f5_markdown_table": (
                "| F5 fifth-regime row | merge 0.25 | merge 0.40 |\n"
                "|---|---:|---:|\n"
                "| compactor to merge zero-shot | 0.7300 | 0.7100 |\n"
                "| eviction to merge zero-shot | 0.7500 | 0.7400 |\n"
                "| merge refit | 0.7400 | 0.7200 |\n"
            ),
        },
        "q3": {
            "pass": True,
            "merge": {"failures": 500, "failure_rate": 0.25},
            "comparisons": {
                "A": {
                    "kappa": 0.40,
                    "nesting_fraction": 0.80,
                    "reference_failure_rate": 0.30,
                },
                "B": {
                    "kappa": 0.42,
                    "nesting_fraction": 0.82,
                    "reference_failure_rate": 0.32,
                },
                "FR": {
                    "kappa": 0.50,
                    "nesting_fraction": 0.78,
                    "reference_failure_rate": 0.28,
                },
                "E1F": {
                    "kappa": 0.45,
                    "nesting_fraction": 0.70,
                    "reference_failure_rate": 0.26,
                },
            },
            "interpretation": "Marginal-aware nesting interpretation.",
            "markdown_table": (
                "| reference regime | Cohen kappa | nesting |\n"
                "|---|---:|---:|\n"
                "| A | 0.4000 | 0.8000 |\n"
                "| B | 0.4200 | 0.8200 |\n"
                "| FR | 0.5000 | 0.7800 |\n"
                "| E1F | 0.4500 | 0.7000 |\n"
            ),
        },
        "compute": {
            "p0": {
                "gpu": "H100",
                "gpu_seconds": 600,
                "cost_usd": 3.0,
                "source": "Modal run record",
            },
            "q1": {
                "gpu": "H100",
                "gpu_seconds": 1200,
                "cost_usd": 8.0,
                "source": "Modal run record",
            },
            "q2": {
                "gpu": "H100 plus L4",
                "gpu_seconds": 3600,
                "cost_usd": 30.0,
                "source": "Modal run records",
            },
            "q3": {
                "gpu": "none",
                "gpu_seconds": 0,
                "cost_usd": 0.0,
                "source": "local analysis",
            },
        },
    }


def test_positive_report_contains_every_registered_surface_and_validates():
    renderer = _load(RENDERER, "mergecert_renderer")
    validator = _load(VALIDATOR, "mergecert_validator")
    evidence = _positive_evidence()
    delivery = {
        "status": "pending",
        "audience": ["Tyler", "Kevin"],
    }

    report = renderer.render_report(evidence, delivery)
    result = validator.validate_report_text(
        report, evidence, delivery, require_delivery=False
    )

    assert result["branch"] == "positive"
    assert result["pass"] is True
    assert "method at its best" in report
    assert "real accumulated attention" in report
    assert "sink addition" in report
    assert "## Q1" in report
    assert "## Q2" in report
    assert "## Q3" in report
    assert "## For the KV-Merge README" in report
    assert "## For the spec" in report
    assert "Private to Tyler and Kevin" in report


def test_positive_readme_claims_are_evidence_backed_and_spec_promotion_requires_q1_ci():
    renderer = _load(RENDERER, "mergecert_renderer_claims")
    evidence = _positive_evidence()
    delivery = {"status": "pending", "audience": ["Tyler", "Kevin"]}

    report = renderer.render_report(evidence, delivery)

    readme = report.split("## For the KV-Merge README\n", 1)[1].split(
        "## For the spec", 1
    )[0]
    assert "Q1 supported claim" in readme
    assert "-0.3500 [-0.4500, -0.2500]" in readme
    assert "Q2 supported claim" in readme
    assert "0.7500 [0.7200, 0.7800]" in readme
    assert "Q3 measured placement" in readme
    assert "A: kappa 0.4000, nesting 0.8000" in readme
    assert "add merge as the fourth training-free regime point" in report

    evidence["q1"]["paired_merge_minus_eviction"]["0.40"]["lost_prior"][
        "ci95"
    ] = [-0.47, 0.03]
    report = renderer.render_report(evidence, delivery)

    assert "add merge as the fourth training-free regime point" not in report
    assert "measured fourth candidate" in report


def test_report_validator_rejects_tampering_publication_and_unconfirmed_delivery():
    renderer = _load(RENDERER, "mergecert_renderer_tamper")
    validator = _load(VALIDATOR, "mergecert_validator_tamper")
    evidence = _positive_evidence()
    delivery = {"status": "pending", "audience": ["Tyler", "Kevin"]}
    report = renderer.render_report(evidence, delivery)

    with pytest.raises(ValueError, match="deterministic evidence rendering"):
        validator.validate_report_text(
            report.replace("0.7500", "0.9500", 1),
            evidence,
            delivery,
            require_delivery=False,
        )
    with pytest.raises(ValueError, match="public URL"):
        validator.validate_report_text(
            report + "\nhttps://example.com/public\n",
            evidence,
            delivery,
            require_delivery=False,
        )
    with pytest.raises(ValueError, match="delivery"):
        validator.validate_report_text(
            report, evidence, delivery, require_delivery=True
        )


def test_report_validator_rejects_source_or_p0_consistency_tampering():
    renderer = _load(RENDERER, "mergecert_renderer_evidence_tamper")
    validator = _load(VALIDATOR, "mergecert_validator_evidence_tamper")
    delivery = {"status": "pending", "audience": ["Tyler", "Kevin"]}

    evidence = _positive_evidence()
    evidence["source"]["commit"] = "wrong-upstream-commit"
    report = renderer.render_report(evidence, delivery)
    with pytest.raises(ValueError, match="source provenance"):
        validator.validate_report_text(
            report, evidence, delivery, require_delivery=False
        )

    evidence = _positive_evidence()
    evidence["p0"]["p0_4"]["pass"] = False
    report = renderer.render_report(evidence, delivery)
    with pytest.raises(ValueError, match="P0 component"):
        validator.validate_report_text(
            report, evidence, delivery, require_delivery=False
        )


def test_negative_report_stops_after_p0_and_excludes_q1_q3_tables():
    renderer = _load(RENDERER, "mergecert_renderer_negative")
    validator = _load(VALIDATOR, "mergecert_validator_negative")
    evidence = _positive_evidence()
    evidence["p0"]["p0_pass"] = False
    evidence["p0"]["stop_q1_q3"] = True
    evidence["p0"]["p0_3"]["pass"] = False
    for key in ("q1", "q2", "q3"):
        evidence.pop(key)
    delivery = {"status": "pending", "audience": ["Tyler", "Kevin"]}

    report = renderer.render_report(evidence, delivery)
    result = validator.validate_report_text(
        report, evidence, delivery, require_delivery=False
    )

    assert result["branch"] == "negative"
    assert "Q1-Q3 were not launched" in report
    assert "## Q1" not in report
    assert "## Q2" not in report
    assert "## Q3" not in report


def test_negative_report_does_not_misstate_a_non_degeneracy_failure_as_direction_failure():
    renderer = _load(RENDERER, "mergecert_renderer_degeneracy_failure")
    validator = _load(VALIDATOR, "mergecert_validator_degeneracy_failure")
    evidence = _positive_evidence()
    evidence["p0"]["p0_pass"] = False
    evidence["p0"]["stop_q1_q3"] = True
    evidence["p0"]["p0_4"]["pass"] = False
    for key in ("q1", "q2", "q3"):
        evidence.pop(key)
    delivery = {"status": "pending", "audience": ["Tyler", "Kevin"]}

    report = renderer.render_report(evidence, delivery)
    result = validator.validate_report_text(
        report, evidence, delivery, require_delivery=False
    )

    assert result["branch"] == "negative"
    assert "Failed registered check: P0.4 non-degeneracy." in report
    assert "P0.3 did not reproduce" not in report
    assert "direction gate failed" not in report
    assert "no scientific placement conclusion is drawn" in report
