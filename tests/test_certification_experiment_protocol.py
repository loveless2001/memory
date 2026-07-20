import copy
import random

import pytest

from memsub.certification.experiment_protocol import (
    assert_train_eval_disjoint,
    build_training_manifest,
    canonical_sha256,
    max_contiguous_certified_depth,
    paired_metric_cis,
    paired_bootstrap_ci,
    select_holdout_documents,
)


DOMAINS = ("financial", "legal", "code", "literature")


def _eligible_items(docs_per_domain=2):
    rows = []
    lengths = {}
    for domain in DOMAINS:
        for doc_index in range(docs_per_domain + 1):
            doc_id = f"{domain}/{doc_index:03d}"
            lengths[doc_id] = 6000
            rows.extend([
                {"item_id": f"{doc_id}:needle", "doc_id": doc_id,
                 "chunk_token_start": 100, "chunk_token_end": 1124},
                {"item_id": f"{doc_id}:agg", "doc_id": doc_id,
                 "chunk_token_start": 3000, "chunk_token_end": 4024},
            ])
    return rows, lengths


def test_holdout_selection_is_order_independent_and_balanced():
    rows, lengths = _eligible_items()
    expected = select_holdout_documents(
        rows, lengths, domains=DOMAINS, docs_per_domain=2)
    shuffled = copy.deepcopy(rows)
    random.Random(19).shuffle(shuffled)

    actual = select_holdout_documents(
        shuffled, lengths, domains=DOMAINS, docs_per_domain=2)

    assert actual == expected
    assert len(actual) == 8
    assert [r["doc_id"] for r in actual[:2]] == [
        "financial/000", "financial/001"]
    assert all(r["needle_item_ids"] and r["aggregation_item_ids"]
               for r in actual)


def test_holdout_selection_fails_when_domain_is_short():
    rows, lengths = _eligible_items(docs_per_domain=0)

    with pytest.raises(ValueError, match="financial.*needed 2.*found 1"):
        select_holdout_documents(
            rows, lengths, domains=DOMAINS, docs_per_domain=2)


@pytest.mark.parametrize("training_rows,match", [
    ([{"doc_id": "financial/000", "item_id": "train-only"}],
     "document overlap"),
    ([{"doc_id": "other/001", "item_id": "financial/000:needle"}],
     "item overlap"),
])
def test_overlap_check_fails_closed_at_document_and_item_levels(
        training_rows, match):
    rows, lengths = _eligible_items()
    heldout = select_holdout_documents(
        rows, lengths, domains=DOMAINS, docs_per_domain=1)

    with pytest.raises(ValueError, match=match):
        assert_train_eval_disjoint(training_rows, heldout)


def test_overlap_check_returns_auditable_counts():
    rows, lengths = _eligible_items()
    heldout = select_holdout_documents(
        rows, lengths, domains=DOMAINS, docs_per_domain=1)

    audit = assert_train_eval_disjoint(
        [{"doc_id": "train/001", "item_id": "train-item"}], heldout)

    assert audit == {
        "training_documents": 1,
        "training_items": 1,
        "certification_documents": 4,
        "certification_items": 8,
        "document_overlap": [],
        "item_overlap": [],
    }


def test_canonical_hash_ignores_mapping_insertion_order():
    assert canonical_sha256({"a": 1, "b": [2, 3]}) == canonical_sha256(
        {"b": [2, 3], "a": 1})


def test_training_manifest_excludes_entire_holdout_documents():
    items = [
        {"doc_id": "financial/held", "item_id": "held-1"},
        {"doc_id": "financial/train", "item_id": "train-1"},
        {"doc_id": "financial/train", "item_id": "train-2"},
    ]

    result = build_training_manifest(
        items,
        traced_ids={"held-1", "train-1"},
        holdout_doc_ids={"financial/held"},
        domains=("financial",),
        domain_cap=2,
    )

    assert [row["item_id"] for row in result["items"]] == [
        "train-1", "train-2"]
    assert result["remainder_item_ids"] == ["train-2"]
    assert result["excluded_traced_item_ids"] == ["held-1"]
    assert result["orphan_traced_item_ids"] == []
    assert result["counts"]["financial"]["heldout_excluded"] == 1


def test_training_manifest_deduplicates_and_balances_after_holdout():
    items = [
        {"doc_id": "a/1", "item_id": "a1"},
        {"doc_id": "a/1", "item_id": "a1"},
        {"doc_id": "a/2", "item_id": "a2"},
        {"doc_id": "a/3", "item_id": "a3"},
        {"doc_id": "b/1", "item_id": "b1"},
        {"doc_id": "b/2", "item_id": "b2"},
    ]

    result = build_training_manifest(
        items, traced_ids=set(), holdout_doc_ids=set(),
        domains=("a", "b"), domain_cap=3, balance_to_smallest=True)

    assert result["effective_domain_cap"] == 2
    assert result["duplicate_item_ids"] == ["a1"]
    assert result["counts"]["a"]["selected"] == 2
    assert result["counts"]["b"]["selected"] == 2
    assert len({row["item_id"] for row in result["items"]}) == 4


def test_paired_bootstrap_ci_is_deterministic_and_tracks_direction():
    ref = [1.0, 2.0, 3.0, 4.0]
    candidate = [0.0, 1.0, 2.0, 3.0]

    first = paired_bootstrap_ci(ref, candidate, seed=7, n_resamples=500)
    second = paired_bootstrap_ci(ref, candidate, seed=7, n_resamples=500)

    assert first == second
    assert first["n"] == 4
    assert first["mean_diff"] == -1.0
    assert first["ci95"] == [-1.0, -1.0]
    assert first["excludes_zero"] is True
    assert first["documents_favoring_candidate"] == 4


def test_paired_bootstrap_ci_rejects_unpaired_or_too_small_inputs():
    with pytest.raises(ValueError, match="same length"):
        paired_bootstrap_ci([1.0], [1.0, 2.0])
    with pytest.raises(ValueError, match="at least two"):
        paired_bootstrap_ci([1.0], [0.0])


def _report(kl, acc, lost, lost_prior):
    return {
        "aggregation_axis": {"mean_kl": kl, "accuracy_delta": acc},
        "pointwise_axis": {
            "lost_fact_incident_rate": lost,
            "lost_fact_rate_given_prior_correct": lost_prior,
        },
    }


def test_paired_metric_cis_include_both_pointwise_denominators():
    results = {
        "eviction-matched": [
            _report(0.2, -0.1, 0.8, 0.7),
            _report(0.3, -0.2, 0.6, 0.5),
        ],
        "compactor-d1": [
            _report(0.1, 0.0, 0.4, 0.3),
            _report(0.2, -0.1, 0.2, 0.1),
        ],
    }

    intervals = paired_metric_cis(
        results, reference_arm="eviction-matched",
        candidate_arms=("compactor-d1",), n_resamples=100)

    assert set(intervals["compactor-d1"]) == {
        "mean_kl", "acc_delta", "lost_fact", "lost_prior"
    }
    assert intervals["compactor-d1"]["lost_prior"]["mean_diff"] == -0.4
    assert intervals["compactor-d1"]["acc_delta"][
        "documents_favoring_candidate"] == 2


@pytest.mark.parametrize("depth_passes,expected", [
    ([(1, False), (4, True)], 0),
    ([(1, True), (4, False)], 1),
    ([(1, True), (4, True)], 4),
])
def test_certified_depth_requires_a_contiguous_passing_prefix(
        depth_passes, expected):
    assert max_contiguous_certified_depth(depth_passes) == expected
