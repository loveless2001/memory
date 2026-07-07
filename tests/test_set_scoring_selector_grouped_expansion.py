"""s1 grouped-expansion selector logic (COMPACTOR.md WP2)."""

import numpy as np

from memsub.gate.set_scoring_selector import SetScoringSelector, fit_tau_entry


def test_gap_rule_takes_the_needed_pair():
    sel = SetScoringSelector(tau_entry=0.4)
    # two needed blocks score high, distractors low -> k=2 at the gap
    dec = sel.decide([0.81, 0.78, 0.22, 0.11])
    assert dec.entered and dec.k == 2
    assert dec.expand_mask == [True, True, False, False]


def test_single_candidate_degenerates_to_threshold():
    sel = SetScoringSelector(tau_entry=0.488)
    assert sel.decide([0.6]).expand_mask == [True]
    assert sel.decide([0.3]).expand_mask == [False]  # GT18 property


def test_entry_threshold_blocks_expansion():
    sel = SetScoringSelector(tau_entry=0.5)
    dec = sel.decide([0.4, 0.39, 0.38])
    assert not dec.entered and dec.k == 0


def test_budget_cap_and_flat_scores():
    sel = SetScoringSelector(tau_entry=0.4, k_max=3)
    dec = sel.decide([0.9, 0.89, 0.88, 0.87, 0.86])
    assert dec.k <= 3
    assert sum(dec.expand_mask) == dec.k


def test_fit_tau_entry_meets_recall_cheaply():
    rng = np.random.default_rng(0)
    scores, needed = [], []
    for _ in range(300):
        n_need = rng.integers(1, 3)
        s = list(rng.uniform(0.6, 0.95, n_need)) + list(rng.uniform(0, 0.3, 2))
        scores.append(s)
        needed.append([True] * n_need + [False, False])
    fit = fit_tau_entry(scores, needed, target_recall=0.85)
    assert fit["recall"] >= 0.85
    assert fit["expand_rate"] < 0.8
