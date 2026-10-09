"""Model-free math for the Qwen value-token previous-key information probe (proposal v0.3).

Everything here is deterministic numpy (float64) with no model access, so C0 tests can check it:
fold assignment by episode, fold-local standardization, SVD ridge over a lambda grid, in-episode
candidate retrieval, the shuffled-target null permutation, episode bootstrap with per-statistic
Bonferroni levels, the frozen reading labels and the full-run admission formula.
"""

from __future__ import annotations

import numpy as np

LAMBDAS = (1e-2, 1e-1, 1.0, 10.0, 100.0, 1000.0)
N_LAYERS = 4
LAYER_ALPHA = 0.05 / N_LAYERS          # per-layer statistics: two-sided 98.75%
NULL_ALPHA = 0.05 / (2 * N_LAYERS)     # null/baseline family (E_v, V-shuf x 4 layers): 99.375%
STD_FLOOR = 1e-6
WALL_CAP_S = 4 * 3600


def require(ok: bool, msg: str) -> None:
    """Explicit refusal (survives python -O)."""
    if not ok:
        raise RuntimeError(msg)


def require_finite(a, what: str) -> None:
    require(bool(np.all(np.isfinite(np.asarray(a, np.float64)))), f"nonfinite {what}")


def validate_wall(w) -> float:
    """Full-run wall must be a finite positive number <= 4 h, independent of any JSON claim (codex 22408)."""
    require(isinstance(w, (int, float)) and not isinstance(w, bool), f"wall {w!r} is not a number")
    require(np.isfinite(w) and 0 < w <= WALL_CAP_S, f"wall {w!r} outside (0, {WALL_CAP_S}]")
    return float(w)


def episode_folds(n_episodes: int, k: int, seed: int) -> np.ndarray:
    """Fold id per EPISODE from a fixed permutation; sizes differ by at most one."""
    perm = np.random.default_rng(seed).permutation(n_episodes)
    folds = np.empty(n_episodes, dtype=np.int64)
    folds[perm] = np.arange(n_episodes) % k
    return folds


def fit_standardizer(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = x.mean(0)
    sd = np.maximum(x.std(0), STD_FLOOR)
    return mu, sd


def ridge_path(x: np.ndarray, y: np.ndarray, lambdas=LAMBDAS) -> dict:
    """Fit standardization + intercept on (x, y) only; return one solution per lambda.
    Loss: sum ||y - (W x~ + b)||^2 + lam ||W||_F^2 (not divided by n); b unpenalized."""
    x = np.asarray(x, np.float64); y = np.asarray(y, np.float64)
    require_finite(x, "probe features"); require_finite(y, "probe targets")
    mu, sd = fit_standardizer(x)
    xs = (x - mu) / sd
    ym = y.mean(0)
    u, s, vt = np.linalg.svd(xs, full_matrices=False)
    uty = u.T @ (y - ym)
    sols = {lam: vt.T @ ((s / (s * s + lam))[:, None] * uty) for lam in lambdas}
    for lam, w in sols.items():
        require_finite(w, f"ridge solution (lambda {lam})")
    return {"mu": mu, "sd": sd, "ym": ym, "W": sols}


def predict(model: dict, lam: float, x: np.ndarray) -> np.ndarray:
    require_finite(x, "features to predict")
    out = ((np.asarray(x, np.float64) - model["mu"]) / model["sd"]) @ model["W"][lam] + model["ym"]
    require_finite(out, "predictions")
    return out


def retrieval_ranks(pred: np.ndarray, cand_ep: np.ndarray, episode: np.ndarray, true_idx: np.ndarray) -> np.ndarray:
    """pred [n, d]; cand_ep [E, C, d] candidates per episode; episode [n] row -> episode; true_idx [n].
    Scored one episode at a time (no [n, C, d] materialization).
    rank = #{other candidates with cosine >= true cosine} (ties count against);
    a zero-norm prediction gets the worst rank C-1."""
    c = cand_ep.shape[1]
    require_finite(pred, "retrieval predictions"); require_finite(cand_ep, "retrieval candidates")
    ranks = np.empty(len(pred), dtype=np.int64)
    for e in np.unique(episode):
        rows = np.flatnonzero(episode == e)
        p = np.asarray(pred[rows], np.float64)
        pn = np.linalg.norm(p, axis=1)
        ce = np.asarray(cand_ep[e], np.float64)
        ce = ce / np.maximum(np.linalg.norm(ce, axis=1, keepdims=True), 1e-300)
        scores = (p / np.maximum(pn, 1e-300)[:, None]) @ ce.T
        true = scores[np.arange(len(rows)), true_idx[rows]]
        ge = (scores >= true[:, None]).sum(1) - 1       # exclude the true candidate itself
        ranks[rows] = np.where(pn == 0, c - 1, ge)
    require(bool(np.all((ranks >= 0) & (ranks <= c - 1))), "rank outside [0, C-1]")
    return ranks


def episode_top1(ranks: np.ndarray, episode: np.ndarray, n_episodes: int) -> np.ndarray:
    """Per-episode top-1 rate (each episode weighted equally)."""
    hits = np.bincount(episode, weights=(ranks == 0).astype(np.float64), minlength=n_episodes)
    counts = np.bincount(episode, minlength=n_episodes)
    return hits / counts


def cv_select_lambda(x, y, episode, folds, cand_ep, true_idx, lambdas=LAMBDAS) -> tuple[float, dict]:
    """Mean held-out-fold top-1 per lambda; standardization/solve refitted inside each train fold.
    Ties go to the LARGER lambda."""
    table = {lam: [] for lam in lambdas}
    for f in np.unique(folds):
        tr = folds[episode] != f
        model = ridge_path(x[tr], y[tr], lambdas)
        va = ~tr
        for lam in lambdas:
            r = retrieval_ranks(predict(model, lam, x[va]), cand_ep, episode[va], true_idx[va])
            table[lam].append(float((r == 0).mean()))
    means = {lam: float(np.mean(v)) for lam, v in table.items()}
    best = max(lambdas, key=lambda lam: (means[lam], lam))
    return best, means


def null_permutations(n_episodes: int, n_bind: int, seed: int) -> np.ndarray:
    """Independent uniform permutation per episode, fixed points ALLOWED (codex 22395):
    binding j's shuffled target is binding perm[e, j]'s key, uniform over all n_bind."""
    rng = np.random.default_rng(seed)
    return np.stack([rng.permutation(n_bind) for _ in range(n_episodes)])


def bootstrap_index(n_episodes: int, n_boot: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, n_episodes, size=(n_boot, n_episodes))


def interval(per_episode: np.ndarray, idx: np.ndarray, alpha: float) -> tuple[float, float, float]:
    """Point estimate + two-sided percentile interval at level 1 - alpha over episode resamples."""
    require_finite(per_episode, "per-episode statistic")
    boots = per_episode[idx].mean(1)
    lo, hi = np.quantile(boots, [alpha / 2, 1 - alpha / 2])
    out = (float(per_episode.mean()), float(lo), float(hi))
    require_finite(out, "interval")
    return out


def reading(stats: dict, chance: float) -> dict:
    """stats[layer][set] = (point, lo, hi) at the set's registered level; stats[layer]['dVK'] = paired
    V+K - V. Labels in precedence order (proposal v0.3)."""
    layers = sorted(stats)
    invalid = [(l, s) for l in layers for s in ("E_v", "V-shuf") if stats[l][s][1] > chance]
    calibrated = [l for l in layers if stats[l]["K"][0] >= 0.50 and stats[l]["K"][1] > 0.25]
    v = {l: stats[l]["V"] for l in calibrated}
    if invalid:
        label = "INVALID"
    elif not calibrated:
        label = "NO CALIBRATED LAYER"
    elif any(p >= 0.50 and lo > 0.10 for p, lo, _ in v.values()):
        label = "CARRIED"
    elif any(lo > 0.10 for _, lo, _ in v.values()):
        label = "PARTIAL"
    elif all(hi <= 0.10 for _, _, hi in v.values()):
        label = "WEAK LINEAR RECOVERY UNDER THIS PROBE"
    else:
        label = "INCONCLUSIVE"
    q2 = {}
    for l in calibrated:
        _, lo, hi = stats[l]["dVK"]
        q2[l] = "APPEND HELPS" if lo > 0.10 else ("NO MEASURABLE HELP" if lo >= -0.05 and hi <= 0.05 else "INCONCLUSIVE")
    return {"label": label, "calibrated_layers": calibrated, "invalid_cells": invalid, "q2": q2}


def admission(capture_s_per_episode: float, n_episodes: int, model_load_s: float, fit_s: float,
              boot_s: float, output_s: float, margin_s: float = 300.0) -> dict:
    """Full-run wall = 2 x (load + capture + fit + bootstrap + output + margin); refuse above 4 h."""
    parts = (capture_s_per_episode, model_load_s, fit_s, boot_s, output_s, margin_s)
    require_finite(parts, "admission inputs")
    require(all(x >= 0 for x in parts) and n_episodes > 0, "negative admission input")
    est = model_load_s + capture_s_per_episode * n_episodes + fit_s + boot_s + output_s + margin_s
    wall = 2.0 * est
    return {"estimate_s": est, "wall_s": wall, "admit": bool(0 < wall <= WALL_CAP_S)}
