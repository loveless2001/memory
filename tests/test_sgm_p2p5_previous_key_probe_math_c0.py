"""C0 model-free checks for the previous-key information probe math (proposal v0.3, codex 22390/22395)."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _forbid_model_load(monkeypatch):
    """No test in this file may load Qwen by any path (codex 22400)."""
    monkeypatch.setenv("PKPROBE_FORBID_MODEL", "1")
spec = importlib.util.spec_from_file_location(
    "pkprobe", ROOT / "scripts/sgm-p2p5-previous-key-probe-ridge-retrieval-readings.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def planted(n_ep=24, n_bind=32, d=40, dy=16, noise=0.01, seed=0):
    rng = np.random.default_rng(seed)
    keys = rng.normal(size=(n_ep, n_bind, dy))
    w = rng.normal(size=(dy, d))
    x = np.einsum("ebk,kd->ebd", keys, w) + noise * rng.normal(size=(n_ep, n_bind, d))
    episode = np.repeat(np.arange(n_ep), n_bind)
    true_idx = np.tile(np.arange(n_bind), n_ep)
    return x.reshape(-1, d), keys.reshape(-1, dy), episode, keys, true_idx   # keys = cand_ep [E, C, dy]


def test_ridge_recovers_planted_map_and_retrieval_is_near_perfect():
    x, y, ep, cands, ti = planted()
    model = M.ridge_path(x, y)
    r = M.retrieval_ranks(M.predict(model, 1e-2, x), cands, ep, ti)
    assert (r == 0).mean() > 0.99


def test_standardization_and_solve_are_fold_local():
    x, y, ep, cands, ti = planted()
    folds = M.episode_folds(24, 4, seed=1)
    tr = folds[ep] != 0
    a = M.ridge_path(x[tr], y[tr])
    x2 = x.copy(); x2[~tr] *= 1e6                                # wreck held-out rows only
    b = M.ridge_path(x2[tr], y[tr])
    assert np.array_equal(a["mu"], b["mu"]) and np.array_equal(a["W"][1.0], b["W"][1.0])
    # a leak mutant (standardizer fit on all rows) would see the wrecked rows
    assert not np.allclose(M.fit_standardizer(x2)[0], a["mu"])


def test_folds_are_by_episode_and_balanced():
    f = M.episode_folds(96, 4, seed=9_700_041)
    assert sorted(np.bincount(f).tolist()) == [24, 24, 24, 24]
    assert np.array_equal(f, M.episode_folds(96, 4, seed=9_700_041))


def test_cv_ties_go_to_larger_lambda():
    x, y, ep, cands, ti = planted(noise=0.0)
    best, means = M.cv_select_lambda(x, y, ep, M.episode_folds(24, 4, 2), cands, ti)
    top = max(means.values())
    assert best == max(l for l, v in means.items() if v == top)


def test_null_permutation_allows_fixed_points_and_is_uniform():
    p = M.null_permutations(20000, 32, seed=9_700_031)
    assert all(sorted(row) == list(range(32)) for row in p[:50])
    fixed = (p == np.arange(32)).mean()
    assert abs(fixed - 1 / 32) < 0.002                          # uniform incl. own key
    assert not np.array_equal(p[:100], M.null_permutations(100, 32, seed=9_700_032))


def test_retrieval_ties_count_against_and_zero_norm_is_worst():
    cands = np.array([[[1.0, 0], [1.0, 0], [0, 1.0]]])
    e0 = np.array([0])
    assert M.retrieval_ranks(np.array([[1.0, 0]]), cands, e0, np.array([0]))[0] == 1
    assert M.retrieval_ranks(np.array([[0.0, 0]]), cands, e0, np.array([2]))[0] == 2
    assert M.retrieval_ranks(np.array([[0.0, 1]]), cands, e0, np.array([2]))[0] == 0


def test_retrieval_uses_each_rows_own_episode_candidates():
    cand_ep = np.array([[[1.0, 0], [0, 1.0]], [[0, 1.0], [1.0, 0]]])
    pred = np.array([[1.0, 0], [1.0, 0]])
    r = M.retrieval_ranks(pred, cand_ep, np.array([0, 1]), np.array([0, 0]))
    assert r.tolist() == [0, 1]


def test_bonferroni_levels():
    assert M.LAYER_ALPHA == pytest.approx(0.0125) and M.NULL_ALPHA == pytest.approx(0.00625)
    per = np.linspace(0, 1, 64)
    idx = M.bootstrap_index(64, 4000, seed=9_700_051)
    _, lo1, hi1 = M.interval(per, idx, M.LAYER_ALPHA)
    _, lo2, hi2 = M.interval(per, idx, M.NULL_ALPHA)
    assert lo2 <= lo1 and hi2 >= hi1                            # wider family interval


def _stats(v, k=(0.9, 0.8, 0.95), ev=(0.03, 0.0, 0.06), vs=(0.03, 0.0, 0.06), d=(0.0, -0.03, 0.03)):
    return {l: {"V": v, "K": k, "E_v": ev, "V-shuf": vs, "dVK": d} for l in (6, 13, 20, 27)}


@pytest.mark.parametrize("stats,label", [
    (_stats((0.6, 0.5, 0.7), ev=(0.1, 0.05, 0.15)), "INVALID"),
    (_stats((0.6, 0.5, 0.7), k=(0.4, 0.3, 0.5)), "NO CALIBRATED LAYER"),
    (_stats((0.6, 0.5, 0.7)), "CARRIED"),
    (_stats((0.3, 0.2, 0.4)), "PARTIAL"),
    (_stats((0.03, 0.0, 0.08)), "WEAK LINEAR RECOVERY UNDER THIS PROBE"),
    (_stats((0.05, 0.0, 0.2)), "INCONCLUSIVE"),
])
def test_label_precedence(stats, label):
    assert M.reading(stats, 1 / 32)["label"] == label


def test_q2_readings():
    r = M.reading(_stats((0.03, 0.0, 0.08), d=(0.5, 0.3, 0.6)), 1 / 32)
    assert set(r["q2"].values()) == {"APPEND HELPS"}
    r = M.reading(_stats((0.03, 0.0, 0.08), d=(0.0, -0.03, 0.04)), 1 / 32)
    assert set(r["q2"].values()) == {"NO MEASURABLE HELP"}
    r = M.reading(_stats((0.03, 0.0, 0.08), d=(0.05, -0.02, 0.12)), 1 / 32)
    assert set(r["q2"].values()) == {"INCONCLUSIVE"}


def test_admission_refuses_above_four_hours():
    assert M.admission(30.0, 160, 60, 600, 60, 30)["admit"]
    assert not M.admission(60.0, 160, 60, 600, 60, 30)["admit"]   # 2 x (60+9600+...) > 14400


def test_cv_solves_only_on_train_fold_rows(monkeypatch):
    x, y, ep, cands, ti = planted()
    folds = M.episode_folds(24, 4, seed=3)
    seen = []
    real = M.ridge_path
    monkeypatch.setattr(M, "ridge_path", lambda xx, yy, lams=M.LAMBDAS: (seen.append(xx.copy()), real(xx, yy, lams))[1])
    M.cv_select_lambda(x, y, ep, folds, cands, ti)
    assert len(seen) == 4
    for f, xx in zip(np.unique(folds), seen):
        tr = folds[ep] != f
        assert np.array_equal(xx, x[tr])                         # exactly the train-fold rows, nothing else


def test_nonfinite_inputs_are_refused():
    x, y, ep, cands, ti = planted()
    xb = x.copy(); xb[0, 0] = np.nan
    with pytest.raises(RuntimeError, match="nonfinite"):
        M.ridge_path(xb, y)
    model = M.ridge_path(x, y)
    pred = M.predict(model, 1.0, x); pred[3, 1] = np.nan
    with pytest.raises(RuntimeError, match="nonfinite"):
        M.retrieval_ranks(pred, cands, ep, ti)
    with pytest.raises(RuntimeError, match="nonfinite"):
        M.interval(np.array([0.1, np.nan]), M.bootstrap_index(2, 10, 0), M.LAYER_ALPHA)
    with pytest.raises(RuntimeError, match="nonfinite"):
        M.admission(float("nan"), 160, 60, 600, 60, 30)


@pytest.mark.parametrize("w", [0, -1, 0.0, float("inf"), float("nan"), 20000, 14400.5, True, "100", None])
def test_validate_wall_rejects_bad_values(w):
    with pytest.raises(RuntimeError):
        M.validate_wall(w)


def test_validate_wall_accepts_in_range():
    assert M.validate_wall(14400) == 14400.0 and M.validate_wall(1.5) == 1.5
