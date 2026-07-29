import hashlib
import json
import math
from pathlib import Path

from memsub.fingerprint import CompatibilityFingerprint


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "plans" / "260728-mergecert-q1"
SMOKE = EVIDENCE_DIR / "q1-smoke.json"
VERDICT = EVIDENCE_DIR / "q1-smoke-verdict.json"
TABLE = EVIDENCE_DIR / "q1-smoke-table.md"
TRIGGER = EVIDENCE_DIR / "q1-smoke-trigger.json"

DOCUMENTS = ["financial/00000", "financial/00008"]
ARMS = {
    "control-0.00": ("zero-compression-control", 0.0),
    "eviction-0.25": ("contiguous-eviction", 0.25),
    "eviction-0.40": ("contiguous-eviction", 0.40),
    "merge-0.25": ("attention-weighted-merge", 0.25),
    "merge-0.40": ("attention-weighted-merge", 0.40),
}
EXPECTED_BUDGETS = {
    "0.25": {
        "requested_evicted_token_count": 1024,
        "eviction_source_start": 1024,
        "eviction_source_end": 2048,
        "physical_after_count": 3072,
    },
    "0.40": {
        "requested_evicted_token_count": 1638,
        "eviction_source_start": 1024,
        "eviction_source_end": 2662,
        "physical_after_count": 2458,
    },
}


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_q1_smoke_evidence_is_immutable_and_non_authorizing():
    assert _sha256(SMOKE) == (
        "c3949b641e4ad0ed00596ec38194bed7a46084c58667750afb94bb7682e75564"
    )
    assert _sha256(VERDICT) == (
        "add8f2314121057bdcffe1d54507045a4c7a14f6dcf85d148d5d06be1abdd6b7"
    )
    assert _sha256(TABLE) == (
        "57c1d2ef647fe82caa248fdde1050e75817cbcbe7f7b196d69181a36c7170bc2"
    )
    assert not TRIGGER.exists()

    verdict = json.loads(VERDICT.read_text())
    assert verdict["pass"] is True
    assert verdict["documents"] == 2
    assert verdict["sample_doc_ids"] == DOCUMENTS
    assert verdict["archived_m1_replay_pass"] is True
    assert verdict["registered_readings"] == {
        "r1": "R2",
        "r3": "aggregation-negative",
        "pointwise_favorable": [],
        "aggregation_favorable": [],
        "favorable_intervals": [],
        "run_q2_q3": False,
    }
    assert verdict["run_q2_q3"] is False
    assert verdict["favorable_intervals"] == []
    assert verdict["markdown_table"] == TABLE.read_text()


def test_q1_smoke_raw_contract_and_replay_matrix_pass():
    payload = json.loads(SMOKE.read_text())
    assert payload["done_documents"] == 2
    assert payload["sample_doc_ids"] == DOCUMENTS
    assert [row["doc_id"] for row in payload["documents"]] == DOCUMENTS
    assert payload["q1_registration_sha256"] == (
        "6d90677469c5548d0fde863db886e7a6665e25f15c23d351ba07a0ad4db6e2d5"
    )
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
    assert len(replay["replay_checks"]) == 6
    assert {
        (row["doc_id"], row["arm"])
        for row in replay["replay_checks"]
    } == {
        (doc_id, arm)
        for doc_id in DOCUMENTS
        for arm in ("control-0.00", "eviction-0.25", "eviction-0.40")
    }
    assert all(row["pass"] is True for row in replay["replay_checks"])
    assert max(len(row["mismatches"]) for row in replay["replay_checks"]) == 0


def test_q1_smoke_five_arms_partitions_attention_and_budgets_pass():
    payload = json.loads(SMOKE.read_text())
    assert {
        arm: (value["policy"], value["ratio"])
        for arm, value in payload["arms"].items()
    } == ARMS

    partitions = {
        row["doc_id"]: (
            row["needle_item_ids"],
            row["aggregation_item_ids"],
        )
        for row in payload["documents"]
    }
    for document in payload["documents"]:
        assert document["attention_mass_min"] >= 0.0
        assert math.isfinite(document["attention_mass_min"])
        assert math.isfinite(document["attention_mass_max"])
        assert math.isfinite(document["attention_mass_variance"])
        assert document["attention_mass_variance"] > 0.0

    for arm, value in payload["arms"].items():
        assert [row["doc_id"] for row in value["reports"]] == DOCUMENTS
        for report in value["reports"]:
            assert (
                report["needle_item_ids"],
                report["aggregation_item_ids"],
            ) == partitions[report["doc_id"]]
            assert {
                row["item_id"] for row in report["probe_records"]
            } == set(sum(partitions[report["doc_id"]], []))
            for axis in ("aggregation_axis", "pointwise_axis"):
                for metric in report[axis].values():
                    assert not isinstance(metric, bool)
                    assert math.isfinite(metric)

            if arm == "control-0.00":
                assert report["aggregation_axis"]["mean_kl"] == 0.0
                assert report["aggregation_axis"]["accuracy_delta"] == 0.0
                assert (
                    report["pointwise_axis"]["lost_fact_incident_rate"] == 0.0
                )
                assert (
                    report["pointwise_axis"][
                        "lost_fact_rate_given_prior_correct"
                    ]
                    == 0.0
                )
                assert report["physical_before_count"] == 4096
                assert report["physical_after_count"] == 4096
                assert report["evicted_token_count"] == 0

    reports = {
        arm: {row["doc_id"]: row for row in value["reports"]}
        for arm, value in payload["arms"].items()
    }
    for document in payload["documents"]:
        doc_id = document["doc_id"]
        for ratio, expected in EXPECTED_BUDGETS.items():
            budget = document["budgets"][ratio]
            assert budget["source_context_token_count"] == 4096
            assert budget["model_input_token_count"] == 4096
            assert budget["physical_before_count"] == 4096
            assert budget["evicted_token_count"] == (
                expected["requested_evicted_token_count"]
            )
            assert budget["retained_token_count"] == (
                expected["physical_after_count"]
            )
            assert budget["merge_target_retained"] == (
                expected["physical_after_count"]
            )
            for key, expected_value in expected.items():
                assert budget[key] == expected_value

            eviction = reports[f"eviction-{ratio}"][doc_id]
            merge = reports[f"merge-{ratio}"][doc_id]
            assert eviction["physical_after_count"] == (
                merge["physical_after_count"]
            )
            assert eviction["physical_after_count"] == (
                budget["retained_token_count"]
            )
            assert merge["target_retained"] == budget["merge_target_retained"]
