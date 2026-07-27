import numpy as np

from memsub.certification.mergecert_statistics import (
    cluster_bootstrap_auc,
    cohen_kappa,
    directional_failure_nesting,
    document_split,
    standardize_train_only,
    tie_aware_auc,
)


def test_tie_aware_auc_uses_average_ranks():
    y = np.array([0, 1, 0, 1])
    scores = np.array([0.0, 0.5, 0.5, 1.0])

    assert tie_aware_auc(y, scores) == 0.875


def test_document_split_is_deterministic_and_document_disjoint():
    docs = np.array(["a", "a", "b", "c", "c", "d"])

    first = document_split(docs)
    second = document_split(docs[::-1])[::-1]

    assert np.array_equal(first, second)
    for doc_id in set(docs):
        assert len(set(first[docs == doc_id])) == 1
    assert set(first) <= {0, 1, 2}


def test_standardization_uses_train_rows_only():
    values = np.array([[0.0], [2.0], [100.0]])
    train = np.array([True, True, False])

    normalized, mean, scale = standardize_train_only(values, train)

    assert mean.tolist() == [1.0]
    assert scale.tolist() == [1.0]
    assert normalized[:, 0].tolist() == [-1.0, 1.0, 99.0]


def test_cluster_bootstrap_auc_is_reproducible_and_reports_documents():
    y = np.array([0, 1, 0, 1, 0, 1])
    scores = np.array([0.0, 1.0, 0.2, 0.8, 0.1, 0.9])
    docs = np.array(["a", "a", "b", "b", "c", "c"])

    first = cluster_bootstrap_auc(y, scores, docs, seed=7, n_resamples=100)
    second = cluster_bootstrap_auc(y, scores, docs, seed=7, n_resamples=100)

    assert first == second
    assert first["auc"] == 1.0
    assert first["n_items"] == 6
    assert first["n_documents"] == 3
    assert first["ci95"] == [1.0, 1.0]


def test_cohen_kappa_matches_hand_computed_confusion_matrix():
    first = np.array([1, 1, 0, 0])
    second = np.array([1, 0, 1, 0])

    result = cohen_kappa(first, second)

    assert result["raw_agreement"] == 0.5
    assert result["expected_agreement"] == 0.5
    assert result["kappa"] == 0.0
    assert result["first_positive_rate"] == 0.5
    assert result["second_positive_rate"] == 0.5


def test_directional_nesting_conditions_on_merge_failures():
    merge = np.array([1, 1, 1, 0, 0])
    reference = np.array([1, 0, 1, 1, 0])

    result = directional_failure_nesting(merge, reference)

    assert result == {
        "n": 5,
        "merge_failure_rate": 0.6,
        "reference_failure_rate": 0.6,
        "merge_failure_denominator": 3,
        "intersection": 2,
        "novel_merge_failures": 1,
        "nesting_fraction": 2 / 3,
    }
