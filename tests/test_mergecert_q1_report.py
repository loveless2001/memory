import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "plans" / "260728-mergecert-q1"
RENDERER = PLAN / "render-report.py"
VALIDATOR = PLAN / "validate-report.py"
REQUIRED_HEADINGS = {
    "## Settled 0.90 result",
    "## Q1 — Moderate-ratio placement",
    "## Per-domain slices",
    "## Registered readings",
    "## Conditional Q2/Q3",
    "## Compute provenance",
    "## For the KV-Merge README",
    "## For the spec",
    "## Limitations",
}
SKIP_REASON = (
    "Q2 and Q3 were skipped because no merge-minus-eviction 95% interval was "
    "favorable under the registered Q1 rule."
)
R1_TEXT = (
    "R1 pointwise: merge CI-below eviction on lost|prior at either ratio "
    "→ the preservation instinct holds at moderate ratios; scoped spectrum "
    'row earned ("blend-preserving at moderate ratios, collapsing at '
    'extreme"), §13.7 note upgraded accordingly.'
)
R2_TEXT = (
    "R2 pointwise: CI-overlapping or worse (the E2 interference prediction "
    "— averaging manufactures confusable-sibling blending) → placement "
    "closes negative on the needle axis at all ratios; the theory's "
    '"merging is structurally worst-case for bindings" reading is confirmed '
    "at deployment-relevant compression."
)
R3_TEXT = (
    "R3 aggregation: independent of R1/R2, report where merge KL/accΔ lands "
    "relative to eviction — a merge that loses needles but wins aggregation "
    "is STILL a coherent scoped result (gist tier behind a gate), and the "
    "two-axis protocol exists precisely to say so without blending."
)
Q1_APP_IDS = (
    "ap-LhQ8XuapnFgxvOgxih3tr3",
    "ap-n8C84UMNCvqC8Mc5bIM3c5",
)
Q2_APP_ID = "ap-Vm2RcWMIGSeIN2ykNdSyxB"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, allow_nan=False))


def _replace_q2_reading(plan, text):
    q2_path = plan / "q2-routability.json"
    q2 = json.loads(q2_path.read_text())
    q2["registered_reading"] = text
    _write_json(q2_path, q2)
    conditional_path = plan / "conditional-work.json"
    conditional = json.loads(conditional_path.read_text())
    conditional["q2"]["sha256"] = _sha256(q2_path)
    _write_json(conditional_path, conditional)


def _q1_verdict(*, positive, aggregation_only=False):
    intervals = {
        "0.25": {
            "lost_prior": {
                "mean_diff": (
                    -0.12 if positive and not aggregation_only else 0.02
                ),
                "ci95": (
                    [-0.18, -0.06]
                    if positive and not aggregation_only
                    else [-0.03, 0.07]
                ),
            },
            "mean_kl": {
                "mean_diff": 0.03,
                "ci95": [-0.01, 0.07],
            },
            "acc_delta": {
                "mean_diff": 0.01,
                "ci95": [-0.02, 0.04],
            },
        },
        "0.40": {
            "lost_prior": {
                "mean_diff": 0.04,
                "ci95": [-0.02, 0.10],
            },
            "mean_kl": {
                "mean_diff": -0.02,
                "ci95": [-0.05, 0.01],
            },
            "acc_delta": {
                "mean_diff": 0.05 if positive else -0.01,
                "ci95": [0.02, 0.08] if positive else [-0.04, 0.02],
            },
        },
    }
    summaries = {
        "control-0.00": {
            "documents": 20,
            "aggregation_probes": 40,
            "needle_probes": 60,
            "mean_kl": 0.0,
            "accuracy_delta": 0.0,
            "lost_fact": 0.0,
            "lost_prior": 0.0,
        },
        "eviction-0.25": {
            "documents": 20,
            "aggregation_probes": 40,
            "needle_probes": 60,
            "mean_kl": 0.25,
            "accuracy_delta": -0.12,
            "lost_fact": 0.31,
            "lost_prior": 0.40,
        },
        "eviction-0.40": {
            "documents": 20,
            "aggregation_probes": 40,
            "needle_probes": 60,
            "mean_kl": 0.40,
            "accuracy_delta": -0.20,
            "lost_fact": 0.42,
            "lost_prior": 0.50,
        },
        "merge-0.25": {
            "documents": 20,
            "aggregation_probes": 40,
            "needle_probes": 60,
            "mean_kl": 0.28,
            "accuracy_delta": -0.11,
            "lost_fact": 0.22 if positive else 0.33,
            "lost_prior": 0.28 if positive else 0.42,
        },
        "merge-0.40": {
            "documents": 20,
            "aggregation_probes": 40,
            "needle_probes": 60,
            "mean_kl": 0.38,
            "accuracy_delta": -0.15 if positive else -0.21,
            "lost_fact": 0.45,
            "lost_prior": 0.54,
        },
    }
    per_domain = {}
    for index, domain in enumerate(
        ("financial", "legal", "code", "literature")
    ):
        per_domain[domain] = {
            arm: {
                **row,
                "documents": 5,
                "aggregation_probes": 10,
                "needle_probes": 15,
                "mean_kl": row["mean_kl"] + index * 0.001,
            }
            for arm, row in summaries.items()
        }
    pointwise_favorable = (
        ["0.25:lost_prior"] if positive and not aggregation_only else []
    )
    aggregation_favorable = ["0.40:acc_delta"] if positive else []
    favorable = pointwise_favorable + aggregation_favorable
    return {
        "pass": True,
        "documents": 20,
        "domain_counts": {
            "financial": 5,
            "legal": 5,
            "code": 5,
            "literature": 5,
        },
        "archived_m1_replay_pass": True,
        "summaries": summaries,
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
        "paired_merge_minus_eviction": intervals,
        "registered_readings": {
            "r1": "R1" if pointwise_favorable else "R2",
            "r3": "aggregation-positive" if positive else "aggregation-negative",
            "pointwise_favorable": pointwise_favorable,
            "aggregation_favorable": aggregation_favorable,
            "favorable_intervals": favorable,
            "run_q2_q3": positive,
        },
        "per_domain": per_domain,
        "run_q2_q3": positive,
        "favorable_intervals": favorable,
    }


def _build_bundle(tmp_path, *, positive, aggregation_only=False):
    root = tmp_path / "repo"
    plan = root / "plans" / "260728-mergecert-q1"
    parent = root / "plans" / "260727-mergecert"
    addendum = root / "MERGECERT-Q1.md"
    addendum.parent.mkdir(parents=True)
    addendum.write_bytes((ROOT / "MERGECERT-Q1.md").read_bytes())
    parent_source = parent / "source-provenance.json"
    parent_raw = parent / "p0-direction-200.json"
    parent_verdict = parent / "p0-verdict.json"
    for target, source_path in (
        (
            parent_source,
            ROOT / "plans/260727-mergecert/source-provenance.json",
        ),
        (parent_raw, ROOT / "plans/260727-mergecert/p0-direction-200.json"),
        (parent_verdict, ROOT / "plans/260727-mergecert/p0-verdict.json"),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source_path.read_bytes())
    source = {
        "protocol": "MERGECERT-Q1",
        "model_id": "Qwen/Qwen3-4B-Instruct-2507",
        "upstream_commit": "cd4ed948d62231449dbab9669608bbb4fd220713",
        "upstream_files": {
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
        "ratios": [0.25, 0.4],
        "sink_token_count": 4,
        "addendum": {
            "path": "MERGECERT-Q1.md",
            "sha256": _sha256(addendum),
        },
        "settled_p0": {
            "verdict_path": "plans/260727-mergecert/p0-verdict.json",
            "verdict_sha256": _sha256(parent_verdict),
            "raw_path": "plans/260727-mergecert/p0-direction-200.json",
            "raw_sha256": _sha256(parent_raw),
        },
        "parent_source_provenance_sha256": _sha256(parent_source),
    }
    _write_json(plan / "source-provenance.json", source)
    q1 = _q1_verdict(
        positive=positive, aggregation_only=aggregation_only
    )
    _write_json(plan / "q1-verdict.json", q1)
    trigger = {
        "protocol": "MERGECERT-Q1",
        "run_q2_q3": positive,
        "favorable_intervals": q1["favorable_intervals"],
        "q1_verdict_sha256": _sha256(plan / "q1-verdict.json"),
        "addendum_sha256": source["addendum"]["sha256"],
        "p0_verdict_sha256": source["settled_p0"]["verdict_sha256"],
    }
    _write_json(plan / "q1-trigger.json", trigger)
    if positive:
        q2 = {
            "pass": True,
            "q1_trigger": trigger,
            "q1_trigger_sha256": _sha256(plan / "q1-trigger.json"),
            "registered_reading": "Merged loss is mechanics-routable.",
            "markdown_table": (
                "| Q2 arm | 0.25 | 0.40 |\n"
                "|---|---:|---:|\n"
                "| mechanics refit | 0.7500 | 0.7300 |\n"
            ),
            "f5_markdown_table": (
                "| F5 fifth-regime row | 0.25 | 0.40 |\n"
                "|---|---:|---:|\n"
                "| sink-head monitor | 0.7100 | 0.7000 |\n"
            ),
        }
        q3 = {
            "pass": True,
            "interpretation": "Marginal-aware nesting interpretation.",
            "markdown_table": (
                "| Q3 reference | kappa | nesting |\n"
                "|---|---:|---:|\n"
                "| A | 0.4000 | 0.8000 |\n"
            ),
        }
        _write_json(plan / "q2-routability.json", q2)
        _write_json(plan / "q3-fragility.json", q3)
        conditional = {
            "protocol": "MERGECERT-Q1",
            "status": "completed",
            "q1_trigger_sha256": _sha256(plan / "q1-trigger.json"),
            "q2": {
                "path": (
                    "plans/260728-mergecert-q1/q2-routability.json"
                ),
                "sha256": _sha256(plan / "q2-routability.json"),
            },
            "q3": {
                "path": "plans/260728-mergecert-q1/q3-fragility.json",
                "sha256": _sha256(plan / "q3-fragility.json"),
            },
        }
    else:
        conditional = {
            "protocol": "MERGECERT-Q1",
            "status": "skipped",
            "reason": SKIP_REASON,
            "q1_trigger_sha256": _sha256(plan / "q1-trigger.json"),
        }
    _write_json(plan / "conditional-work.json", conditional)
    compute = {
        "ceiling_usd": 45.0,
        "total_cost_usd": 12.5 if positive else 10.25,
        "phases": {
            "q1": {
                "phase": "Q1",
                "gpu": "H100",
                "gpu_seconds": 900.0,
                "cost_usd": 10.25,
                "source": (
                    "Modal billing report 2026-07-28 for apps "
                    f"{Q1_APP_IDS[0]} and {Q1_APP_IDS[1]}"
                ),
                "runs": [
                    {"app_id": Q1_APP_IDS[0], "purpose": "Q1 smoke"},
                    {
                        "app_id": Q1_APP_IDS[1],
                        "purpose": "Q1 certification",
                    },
                ],
            },
            **(
                {
                    "q2_q3": {
                        "phase": "Q2/Q3",
                        "gpu": "L4",
                        "gpu_seconds": 300.0,
                        "cost_usd": 2.25,
                        "source": (
                            "Modal billing report 2026-07-28 for app "
                            f"{Q2_APP_ID}"
                        ),
                        "runs": [
                            {
                                "app_id": Q2_APP_ID,
                                "purpose": "conditional Q2 capture",
                            }
                        ],
                    }
                }
                if positive
                else {}
            ),
        },
    }
    _write_json(plan / "compute-actuals.json", compute)
    return root, plan


def test_negative_report_is_complete_private_and_evidence_only(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_negative")
    validator = _load(VALIDATOR, "mergecert_q1_validator_negative")
    root, plan = _build_bundle(tmp_path, positive=False)
    evidence = renderer.load_evidence(plan, root=root)

    report = renderer.render_report(evidence)
    result = validator.validate_report_text(report, evidence)

    assert result == {
        "pass": True,
        "conditional_status": "skipped",
        "privacy_status": "local-private",
        "total_cost_usd": 10.25,
    }
    assert REQUIRED_HEADINGS <= set(report.splitlines())
    for row in (
        "eviction 0.25",
        "eviction 0.40",
        "frozen subsample (reference)",
        "unfrozen compactor (reference)",
        "MERGE 0.25",
        "MERGE 0.40",
        "zero-compression control",
    ):
        assert row in report
    for text in (R1_TEXT, R2_TEXT, R3_TEXT):
        assert text in report
    for interval in (
        "+0.0200 [-0.0300, +0.0700]",
        "+0.0300 [-0.0100, +0.0700]",
        "+0.0100 [-0.0200, +0.0400]",
        "+0.0400 [-0.0200, +0.1000]",
        "-0.0200 [-0.0500, +0.0100]",
        "-0.0100 [-0.0400, +0.0200]",
    ):
        assert interval in report
    assert SKIP_REASON in report
    assert "Private to Tyler and Kevin." in report
    assert (
        "Local/private report only. Transmission is not recorded. "
        "No public artifact is authorized."
    ) in report
    assert (
        "Scientific placement only; this is not a deployment certification."
    ) in report
    assert Q1_APP_IDS[0] in report
    assert Q1_APP_IDS[1] in report
    assert report.count("merge-plus-anchor") == 1
    assert "theoretically motivated future direction" in report
    assert "was not tested" in report
    for forbidden in (
        "https://",
        "http://",
        "| ? |",
        "Qwen2.5",
        "deployment-ready",
        "transmission confirmed",
    ):
        assert forbidden not in report


def test_positive_report_renders_conditional_evidence_and_scoped_axes(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_positive")
    validator = _load(VALIDATOR, "mergecert_q1_validator_positive")
    root, plan = _build_bundle(tmp_path, positive=True)
    evidence = renderer.load_evidence(plan, root=root)

    report = renderer.render_report(evidence)
    result = validator.validate_report_text(report, evidence)

    assert result["conditional_status"] == "completed"
    assert "| mechanics refit | 0.7500 | 0.7300 |" in report
    assert "### F5 fifth-regime row" in report
    assert "| sink-head monitor | 0.7100 | 0.7000 |" in report
    assert "| A | 0.4000 | 0.8000 |" in report
    assert "Measured favorable axis: 0.25 lost-prior." in report
    assert "Measured favorable axis: 0.40 accuracy-delta." in report
    assert "all moderate ratios" not in report
    assert "merge-plus-anchor" not in report
    assert Q2_APP_ID in report


def test_validator_requires_f5_evidence_for_completed_q2(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_missing_f5")
    validator = _load(VALIDATOR, "mergecert_q1_validator_missing_f5")
    root, plan = _build_bundle(tmp_path, positive=True)
    evidence = renderer.load_evidence(plan, root=root)
    report = renderer.render_report(evidence)
    evidence["q2"].pop("f5_markdown_table")

    with pytest.raises(ValueError, match="F5"):
        validator.validate_report_text(report, evidence)


@pytest.mark.parametrize(
    ("injected_text", "message"),
    (
        ("[public](HTTPS://example.com/result)", "public URL"),
        ("[public](//example.com/result)", "public URL"),
        ('<a href="https://example.com">text</a>', "public URL"),
        ('<img src="//example.com/x.png">', "public URL"),
        ("https:<span>//</span>example.com", "public URL"),
        ("https:**//**example.com", "public URL"),
        ("| **?** |", "question-mark result cell"),
        (r"| \*\*\?\*\* |", "question-mark result cell"),
        ("| [?](/result) |", "question-mark result cell"),
        ("The method was deployed successfully.", "forbidden claim"),
        ("Deployment succeeded.", "forbidden claim"),
        ("The method was deployed.", "forbidden claim"),
        ("The method did deploy.", "forbidden claim"),
        (
            "Deployment did not succeed, and Tyler received the report.",
            "forbidden claim",
        ),
        ("The method was deployed without errors.", "forbidden claim"),
        ("Sent to Tyler after validation.", "forbidden claim"),
        ("Tyler received the report.", "forbidden claim"),
        ("Kevin has the report.", "forbidden claim"),
        ("Transmission successfully completed.", "forbidden claim"),
        ("Transmission completed without delay.", "forbidden claim"),
        ("Delivery occurred.", "forbidden claim"),
    ),
)
def test_validator_rejects_formatted_or_case_variant_forbidden_claims(
    tmp_path, injected_text, message
):
    renderer = _load(RENDERER, f"mergecert_q1_renderer_{message}")
    validator = _load(VALIDATOR, f"mergecert_q1_validator_{message}")
    root, plan = _build_bundle(tmp_path, positive=True)
    _replace_q2_reading(plan, injected_text)
    evidence = renderer.load_evidence(plan, root=root)
    report = renderer.render_report(evidence)

    with pytest.raises(ValueError, match=message):
        validator.validate_report_text(report, evidence)


def test_validator_permits_explicit_negative_limitations(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_negative_claims")
    validator = _load(VALIDATOR, "mergecert_q1_validator_negative_claims")
    root, plan = _build_bundle(tmp_path, positive=True)
    negative = (
        "Deployment did not succeed. Tyler did not receive the report. "
        "Transmission was not completed."
    )
    _replace_q2_reading(plan, negative)
    evidence = renderer.load_evidence(plan, root=root)
    report = renderer.render_report(evidence)

    result = validator.validate_report_text(report, evidence)

    assert result["pass"] is True
    assert negative in report


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (
            lambda evidence: evidence["compute"]["phases"]["q1"]["runs"][
                0
            ].update({"app_id": "ap-"}),
            "app ID",
        ),
        (
            lambda evidence: evidence["compute"]["phases"]["q1"]["runs"][
                0
            ].update({"app_id": "ap-000000"}),
            "app ID",
        ),
        (
            lambda evidence: evidence["compute"]["phases"]["q1"].update(
                {"phase": "Q2/Q3"}
            ),
            "phase",
        ),
        (
            lambda evidence: evidence["compute"]["phases"]["q1"].update(
                {"source": "Modal billing report"}
            ),
            "billing source",
        ),
        (
            lambda evidence: evidence["compute"]["phases"]["q1"].update(
                {
                    "source": (
                        "Modal billing report 9999-99-99 for apps "
                        f"{Q1_APP_IDS[0]} and {Q1_APP_IDS[1]}"
                    )
                }
            ),
            "billing date",
        ),
        (
            lambda evidence: evidence["compute"]["phases"]["q1"].update(
                {
                    "source": (
                        "Modal billing report 2026-07-28 for apps "
                        f"{Q1_APP_IDS[0]} and {Q1_APP_IDS[1]} verified manually"
                    )
                }
            ),
            "billing source",
        ),
    ),
)
def test_validator_strictly_binds_billing_id_phase_and_source(
    tmp_path, mutate, message
):
    renderer = _load(RENDERER, f"mergecert_q1_renderer_billing_{message}")
    validator = _load(VALIDATOR, f"mergecert_q1_validator_billing_{message}")
    root, plan = _build_bundle(tmp_path, positive=True)
    evidence = renderer.load_evidence(plan, root=root)
    report = renderer.render_report(evidence)
    mutate(evidence)

    with pytest.raises(ValueError, match=message):
        validator.validate_report_text(report, evidence)


def test_aggregation_only_positive_report_names_the_measured_axis(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_aggregation_only")
    validator = _load(VALIDATOR, "mergecert_q1_validator_aggregation_only")
    root, plan = _build_bundle(
        tmp_path, positive=True, aggregation_only=True
    )
    evidence = renderer.load_evidence(plan, root=root)

    report = renderer.render_report(evidence)
    result = validator.validate_report_text(report, evidence)

    assert result["conditional_status"] == "completed"
    assert "Measured verdicts: R2 and aggregation-positive." in report
    assert "Measured favorable axis: 0.40 accuracy-delta." in report
    assert "Measured favorable axis: 0.25 lost-prior." not in report
    assert report.count("merge-plus-anchor") == 1


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (
            lambda evidence: evidence["trigger"].update(
                {"favorable_intervals": []}
            ),
            "trigger",
        ),
        (
            lambda evidence: evidence["conditional"].update(
                {"status": "skipped"}
            ),
            "conditional",
        ),
        (
            lambda evidence: evidence["compute"].update(
                {"total_cost_usd": 45.01}
            ),
            "ceiling",
        ),
        (
            lambda evidence: evidence["compute"]["phases"]["q1"].update(
                {"runs": []}
            ),
            "app ID",
        ),
    ),
)
def test_validator_fails_closed_on_trigger_conditional_or_billing_drift(
    tmp_path, mutate, message
):
    renderer = _load(RENDERER, f"mergecert_q1_renderer_{message}")
    validator = _load(VALIDATOR, f"mergecert_q1_validator_{message}")
    root, plan = _build_bundle(tmp_path, positive=True)
    evidence = renderer.load_evidence(plan, root=root)
    report = renderer.render_report(evidence)
    mutate(evidence)

    with pytest.raises(ValueError, match=message):
        validator.validate_report_text(report, evidence)


def test_validator_rejects_report_tampering_and_hash_drift(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_hash")
    validator = _load(VALIDATOR, "mergecert_q1_validator_hash")
    root, plan = _build_bundle(tmp_path, positive=False)
    evidence = renderer.load_evidence(plan, root=root)
    report = renderer.render_report(evidence)

    with pytest.raises(ValueError, match="deterministic"):
        validator.validate_report_text(
            report.replace("0.420", "0.920", 1), evidence
        )

    q1_path = plan / "q1-verdict.json"
    q1_path.write_text(q1_path.read_text() + "\n")
    with pytest.raises(ValueError, match="hash"):
        validator.validate_report_text(report, evidence)


def test_validator_rejects_loaded_evidence_that_differs_from_hashed_files(
    tmp_path,
):
    renderer = _load(RENDERER, "mergecert_q1_renderer_loaded_drift")
    validator = _load(VALIDATOR, "mergecert_q1_validator_loaded_drift")
    root, plan = _build_bundle(tmp_path, positive=False)
    evidence = renderer.load_evidence(plan, root=root)
    evidence["q1"]["summaries"]["merge-0.25"]["mean_kl"] = 9.0
    report = renderer.render_report(evidence)

    with pytest.raises(ValueError, match="loaded evidence"):
        validator.validate_report_text(report, evidence)


def test_validator_rejects_registered_source_provenance_drift(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_source_drift")
    validator = _load(VALIDATOR, "mergecert_q1_validator_source_drift")
    root, plan = _build_bundle(tmp_path, positive=False)
    source_path = plan / "source-provenance.json"
    source = json.loads(source_path.read_text())
    source["upstream_commit"] = "f" * 40
    _write_json(source_path, source)
    evidence = renderer.load_evidence(plan, root=root)
    report = renderer.render_report(evidence)

    with pytest.raises(ValueError, match="source provenance"):
        validator.validate_report_text(report, evidence)


def test_validator_rejects_nonfinite_numeric_evidence(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_nonfinite")
    validator = _load(VALIDATOR, "mergecert_q1_validator_nonfinite")
    root, plan = _build_bundle(tmp_path, positive=False)
    q1_path = plan / "q1-verdict.json"
    q1 = json.loads(q1_path.read_text())
    q1["summaries"]["merge-0.25"]["mean_kl"] = float("nan")
    q1_path.write_text(json.dumps(q1, indent=1))
    trigger_path = plan / "q1-trigger.json"
    trigger = json.loads(trigger_path.read_text())
    trigger["q1_verdict_sha256"] = _sha256(q1_path)
    _write_json(trigger_path, trigger)
    conditional_path = plan / "conditional-work.json"
    conditional = json.loads(conditional_path.read_text())
    conditional["q1_trigger_sha256"] = _sha256(trigger_path)
    _write_json(conditional_path, conditional)
    evidence = renderer.load_evidence(plan, root=root)
    report = renderer.render_report(evidence)

    with pytest.raises(ValueError, match="numeric"):
        validator.validate_report_text(report, evidence)


def test_manifest_records_report_and_every_loaded_evidence_file(tmp_path):
    renderer = _load(RENDERER, "mergecert_q1_renderer_manifest")
    validator = _load(VALIDATOR, "mergecert_q1_validator_manifest")
    root, plan = _build_bundle(tmp_path, positive=True)
    evidence = renderer.load_evidence(plan, root=root)
    report_path = root / "MERGECERT-Q1-REPORT.md"
    report_path.write_text(renderer.render_report(evidence))
    result = validator.validate_report_text(report_path.read_text(), evidence)
    manifest_path = plan / "artifact-manifest.json"

    manifest = validator.write_artifact_manifest(
        report_path, evidence, result, manifest_path
    )

    assert manifest_path.read_text() == (
        json.dumps(manifest, indent=1, allow_nan=False) + "\n"
    )
    assert manifest["validation"] == result
    assert set(manifest["files"]) == {
        "MERGECERT-Q1-REPORT.md",
        "MERGECERT-Q1.md",
        "plans/260727-mergecert/source-provenance.json",
        "plans/260727-mergecert/p0-direction-200.json",
        "plans/260727-mergecert/p0-verdict.json",
        "plans/260728-mergecert-q1/source-provenance.json",
        "plans/260728-mergecert-q1/q1-verdict.json",
        "plans/260728-mergecert-q1/q1-trigger.json",
        "plans/260728-mergecert-q1/conditional-work.json",
        "plans/260728-mergecert-q1/q2-routability.json",
        "plans/260728-mergecert-q1/q3-fragility.json",
        "plans/260728-mergecert-q1/compute-actuals.json",
    }
    for metadata in manifest["files"].values():
        assert len(metadata["sha256"]) == 64
        assert metadata["bytes"] > 0
