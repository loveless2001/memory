import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path

from memsub.fingerprint import CompatibilityFingerprint


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "plans" / "260728-mergecert-q1"
CERTIFICATION = EVIDENCE_DIR / "q1-certification.json"
VERDICT = EVIDENCE_DIR / "q1-verdict.json"
TRIGGER = EVIDENCE_DIR / "q1-trigger.json"
TABLE = EVIDENCE_DIR / "q1-table.md"
RUN = EVIDENCE_DIR / "q1-certification-run.json"
REGISTRATION = EVIDENCE_DIR / "q1-registration.json"

HASHES = {
    CERTIFICATION: (
        "82b214ba7881a26ad9aea4f8ba7911e9d028006db5b12c06154b08125917b748"
    ),
    VERDICT: (
        "4266eb66c5b0979da504b124dfa0ceb89d50e29348ea78d9ca7ac8c2614ee036"
    ),
    TRIGGER: (
        "009d1ba2879b76174c13dffbea27a458b10d9a859cdb69046f3afac31a2af5a1"
    ),
    TABLE: (
        "2440fb16f86c770d67b0263a9321e5bc6fc6b044209566a037fd9541a23e6fbb"
    ),
}
ARMS = {
    "control-0.00": ("zero-compression-control", 0.0),
    "eviction-0.25": ("contiguous-eviction", 0.25),
    "eviction-0.40": ("contiguous-eviction", 0.40),
    "merge-0.25": ("attention-weighted-merge", 0.25),
    "merge-0.40": ("attention-weighted-merge", 0.40),
}


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_q1_full_outputs_are_immutable_and_trigger_is_deterministic():
    for path, expected in HASHES.items():
        assert _sha256(path) == expected

    verdict = json.loads(VERDICT.read_text())
    trigger = json.loads(TRIGGER.read_text())
    assert verdict["pass"] is True
    assert verdict["registered_readings"] == {
        "r1": "R1",
        "r3": "aggregation-negative",
        "pointwise_favorable": ["0.40:lost_prior"],
        "aggregation_favorable": [],
        "favorable_intervals": ["0.40:lost_prior"],
        "run_q2_q3": True,
    }
    assert trigger == {
        "protocol": "MERGECERT-Q1",
        "budget_mode": "archived-m1-per-document-matched-physical-v1",
        "run_q2_q3": True,
        "favorable_intervals": ["0.40:lost_prior"],
        "q1_verdict_sha256": _sha256(VERDICT),
        "addendum_sha256": (
            "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509"
        ),
        "p0_verdict_sha256": (
            "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
        ),
    }
    assert verdict["markdown_table"] == TABLE.read_text()


def test_q1_full_population_authorization_fingerprint_and_replay_pass():
    payload = json.loads(CERTIFICATION.read_text())
    registration = json.loads(REGISTRATION.read_text())
    documents = registration["population_doc_ids"]

    assert payload["done_documents"] == 20
    assert payload["sample_doc_ids"] == documents
    assert [row["doc_id"] for row in payload["documents"]] == documents
    assert len(set(documents)) == 20
    assert {
        domain: sum(doc_id.startswith(f"{domain}/") for doc_id in documents)
        for domain in ("code", "financial", "legal", "literature")
    } == {
        "code": 5,
        "financial": 5,
        "legal": 5,
        "literature": 5,
    }
    assert payload["q1_registration_sha256"] == _sha256(REGISTRATION)
    assert payload["q1_authorization"] == {
        "protocol": "MERGECERT-Q1",
        "budget_mode": "archived-m1-per-document-matched-physical-v1",
        "addendum_sha256": (
            "35869e386bb64242ad0067ab51d680779eed65d4a88bbb4ba7180aec634fd509"
        ),
        "p0_verdict_sha256": (
            "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
        ),
        "settled_p0": {
            "p0_3_pass": False,
            "p0_4_pass": True,
            "real_attention_pass": True,
            "p0_pass": False,
            "stop_q1_q3": True,
        },
    }

    semantics = {
        "version": "mergecert-q1-execution-semantics-v1",
        "archive_replay_prefill": {
            "attention_backend": "sdpa",
            "scope": "auxiliary-archive-replay-gate",
        },
        "reported_five_arm_prefill": {
            "attention_backend": "eager",
            "mode": "real-attention",
            "cache_policy": "single-common-prefill",
        },
        "continuation_and_scoring": {
            "attention_backend": "sdpa",
            "backend_state": "restored-configured",
        },
    }
    assert payload["execution_semantics"] == semantics
    assert payload["provenance"]["execution_semantics"] == semantics
    assert payload["compatibility_fingerprint_schema"] == (
        "memsub-compatibility-fingerprint-v1"
    )
    fingerprint = CompatibilityFingerprint.from_dict(
        payload["compatibility_fingerprint"]
    )
    fingerprint.validate()
    assert payload["compatibility_fingerprint_sha256"] == fingerprint.digest()

    replay = payload["archived_m1"]
    assert replay["replay_pass"] is True
    assert len(replay["replay_checks"]) == 60
    assert {
        (row["doc_id"], row["arm"])
        for row in replay["replay_checks"]
    } == {
        (doc_id, arm)
        for doc_id in documents
        for arm in ("control-0.00", "eviction-0.25", "eviction-0.40")
    }
    assert all(row["pass"] is True for row in replay["replay_checks"])
    assert max(len(row["mismatches"]) for row in replay["replay_checks"]) == 0


def test_q1_full_arms_share_partitions_baselines_attention_and_budgets():
    payload = json.loads(CERTIFICATION.read_text())
    registration = json.loads(REGISTRATION.read_text())
    documents = registration["population_doc_ids"]
    registered = {
        row["doc_id"]: row for row in registration["documents"]
    }
    document_rows = {row["doc_id"]: row for row in payload["documents"]}
    assert {
        arm: (value["policy"], value["ratio"])
        for arm, value in payload["arms"].items()
    } == ARMS

    partitions = {
        doc_id: (
            document_rows[doc_id]["needle_item_ids"],
            document_rows[doc_id]["aggregation_item_ids"],
        )
        for doc_id in documents
    }
    full_predictions = {}
    reports = {}
    for arm, value in payload["arms"].items():
        assert [row["doc_id"] for row in value["reports"]] == documents
        reports[arm] = {row["doc_id"]: row for row in value["reports"]}
        for report in value["reports"]:
            doc_id = report["doc_id"]
            assert (
                report["needle_item_ids"],
                report["aggregation_item_ids"],
            ) == partitions[doc_id]
            assert {
                row["item_id"] for row in report["probe_records"]
            } == set(sum(partitions[doc_id], []))
            baseline = {
                row["item_id"]: row["full_prediction"]
                for row in report["probe_records"]
            }
            if doc_id in full_predictions:
                assert baseline == full_predictions[doc_id]
            else:
                full_predictions[doc_id] = baseline
            for axis in ("aggregation_axis", "pointwise_axis"):
                for metric in report[axis].values():
                    assert not isinstance(metric, bool)
                    assert math.isfinite(metric)

    for doc_id in documents:
        document = document_rows[doc_id]
        assert math.isfinite(document["attention_mass_min"])
        assert math.isfinite(document["attention_mass_max"])
        assert math.isfinite(document["attention_mass_variance"])
        assert document["attention_mass_min"] >= 0.0
        assert document["attention_mass_variance"] > 0.0
        assert document["source_context_token_count"] == (
            registered[doc_id]["source_context_token_count"]
        )
        assert document["model_input_token_count"] == (
            registered[doc_id]["model_input_token_count"]
        )
        for ratio, registered_budget in registered[doc_id]["budgets"].items():
            assert {
                key: document["budgets"][ratio][key]
                for key in registered_budget
            } == registered_budget

        control = reports["control-0.00"][doc_id]
        assert control["aggregation_axis"]["mean_kl"] == 0.0
        assert control["aggregation_axis"]["accuracy_delta"] == 0.0
        assert (
            control["pointwise_axis"]["lost_fact_rate_given_prior_correct"]
            == 0.0
        )
        assert control["evicted_token_count"] == 0
        assert control["physical_before_count"] == (
            control["physical_after_count"]
        )
        assert all(
            row["candidate_prediction"] == row["full_prediction"]
            for row in control["probe_records"]
        )

        for ratio in ("0.25", "0.40"):
            budget = document["budgets"][ratio]
            eviction = reports[f"eviction-{ratio}"][doc_id]
            merge = reports[f"merge-{ratio}"][doc_id]
            assert budget["physical_before_count"] == (
                budget["physical_after_count"]
                + budget["evicted_token_count"]
            )
            assert budget["retained_token_count"] == (
                budget["physical_after_count"]
            )
            assert budget["merge_target_retained"] == (
                budget["retained_token_count"]
            )
            assert eviction["physical_after_count"] == (
                budget["retained_token_count"]
            )
            assert merge["physical_after_count"] == (
                budget["merge_target_retained"]
            )
            assert merge["target_retained"] == (
                budget["merge_target_retained"]
            )


def test_q1_full_verdict_has_complete_cis_and_domain_slices():
    verdict = json.loads(VERDICT.read_text())
    assert verdict["documents"] == 20
    assert verdict["domain_counts"] == {
        "code": 5,
        "financial": 5,
        "legal": 5,
        "literature": 5,
    }
    assert set(verdict["per_domain"]) == set(verdict["domain_counts"])
    for domain, arms in verdict["per_domain"].items():
        assert set(arms) == set(ARMS), domain
        assert all(summary["documents"] == 5 for summary in arms.values())

    for ratio in ("0.25", "0.40"):
        metrics = verdict["paired_merge_minus_eviction"][ratio]
        assert set(metrics) == {
            "mean_kl",
            "acc_delta",
            "lost_fact",
            "lost_prior",
        }
        for result in metrics.values():
            assert result["n"] == 20
            assert len(result["ci95"]) == 2
            assert all(math.isfinite(value) for value in result["ci95"])
            assert result["ci95"][0] <= result["ci95"][1]
            assert result["excludes_zero"] == (
                result["ci95"][0] > 0.0 or result["ci95"][1] < 0.0
            )


def test_q1_full_operations_record_cost_and_local_stop_boundary():
    evidence = json.loads(RUN.read_text(), parse_float=Decimal)
    assert evidence["status"] == "completed-and-independently-validated"
    assert evidence["reviewed_runner_commit"] == (
        "36475ded4264486b39d403943682ab0687bd2943"
    )
    assert evidence["terminal_inventory"] == {
        "command": "modal app list --json",
        "result": [
            {
                "app_id": "ap-bnyT0P9ay00aSaBC0u4gyc",
                "description": "memsub-mergecert-p0-q1",
                "state": "stopped",
                "tasks": "0",
                "created_at": "2026-07-29 14:54:12+07:00",
                "stopped_at": "2026-07-29 14:56:45+07:00",
            }
        ],
    }
    assert evidence["certification"]["app_lifetime_seconds"] == 153
    assert evidence["certification"]["tasks_after_stop"] == 0
    assert evidence["outputs"]["q1_certification_sha256"] == _sha256(
        CERTIFICATION
    )
    assert evidence["outputs"]["q1_verdict_sha256"] == _sha256(VERDICT)
    assert evidence["outputs"]["q1_trigger_sha256"] == _sha256(TRIGGER)
    assert evidence["outputs"]["q1_table_sha256"] == _sha256(TABLE)
    assert evidence["outputs"]["q1_trigger_uploaded"] is False
    assert evidence["outputs"]["q2_q3_launched"] is False

    rates = evidence["cost_estimate"]["rates_usd_per_second"]
    cost = Decimal(153) * (
        rates["h100"]
        + rates["physical_cpu_core"]
        + Decimal(64) * rates["memory_gib"]
    )
    assert cost == Decimal("0.19158354")
    assert evidence["cost_estimate"]["usd"] == cost
    cumulative = evidence["cumulative_conservative_campaign_estimate"]
    assert cumulative["prior_q1_usd"] == Decimal("0.26981812")
    assert cumulative["prior_q1_usd"] + cost == Decimal("0.46140166")
    assert cumulative["usd"] == Decimal("0.46140166")
    assert cumulative["within_bound"] is True
    assert cumulative["not_billing_actual"] is True
