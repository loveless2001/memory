"""P2G registered decision rules (prereg v0.2 `25fdbc5`, sha c2fa7394…).

Pure functions; every rule fails closed (SystemExit) on malformed input.
Episode scoring, paired intervals, reproducibility and memory use are the
UNCHANGED P2D Step 2 rules (`sgm-p2d-step2-decision-rules.py`, 88dda56b…),
imported, never copied.
"""

import importlib.util
import math
from pathlib import Path

import torch

_spec = importlib.util.spec_from_file_location(
    "p2d_rules", Path(__file__).with_name("sgm-p2d-step2-decision-rules.py"))
P2D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P2D)

SEEDS, MIN_EFFECT, RHO_MAX = ("0", "1"), 0.05, 0.20
GAIN, LOSS, EXCLUDED, NEITHER = ("reproducible gain", "reproducible loss",
                                 "positive gain >=5pp excluded", "neither")
Q2_KEYS = ("C_T|off", "C_T|on", "C_E|Ton", "C_E|Toff")


def _seeds(per_seed: dict) -> dict:
    if set(per_seed) != set(SEEDS):
        raise SystemExit(f"rule needs seeds {SEEDS}, got {sorted(per_seed)}")
    return per_seed


def classify(per_seed: dict) -> str:
    """Ordered, total contrast classifier over per-seed paired intervals."""
    r = _seeds(per_seed).values()
    if all(x["diff"] >= MIN_EFFECT and x["lo"] > 0 for x in r):
        return GAIN
    if all(x["diff"] <= -MIN_EFFECT and x["hi"] < 0 for x in r):
        return LOSS
    if all(x["hi"] < MIN_EFFECT for x in r):
        return EXCLUDED
    return NEITHER


def linear_contrast(rows_list: list, coeffs: tuple) -> dict:
    """Per episode d_e = sum_i c_i * score_i(none) over runs sharing episode
    hashes; interval exactly as P2D `paired` (mean ± 1.96 sd/sqrt n, unbiased sd)."""
    scores = [P2D.episode_scores(rows, "none") for rows in rows_list]
    if len(scores) != len(coeffs) or any(set(s) != set(scores[0]) for s in scores):
        raise SystemExit("linear contrast runs do not share episode hashes")
    d = torch.tensor([sum(c * s[k] for c, s in zip(coeffs, scores)) for k in scores[0]], dtype=torch.float64)
    hw = float(1.96 * d.std() / math.sqrt(len(d)))
    return {"diff": float(d.mean()), "lo": float(d.mean()) - hw, "hi": float(d.mean()) + hw, "n": len(d)}


def half_oracle(gate_rows: list, v2_rows: list, oracle_rows: list) -> dict:
    """d_e = (gate - v2) - 0.5 (oracle - v2) = gate - 0.5 v2 - 0.5 oracle."""
    return linear_contrast([gate_rows, v2_rows, oracle_rows], (1.0, -0.5, -0.5))


def interaction(off_off: list, on_off: list, off_on: list, on_on: list) -> dict:
    """Descriptive: C_T|off - C_T|on = (ff - nf) - (fn - nn) per episode."""
    return linear_contrast([off_off, on_off, off_on, on_on], (1.0, -1.0, -1.0, 1.0))


def half_status(oracle_label: str, half_per_seed: dict) -> bool | None:
    """None (unavailable) unless the oracle-vs-v2 contrast is a reproducible gain."""
    if oracle_label != GAIN:
        return None
    return all(x["lo"] > 0 for x in _seeds(half_per_seed).values())


def q1_reading(gain_label: str, sup: bool, mem: bool, half: bool | None) -> str:
    """Prereg Q1 ordered table (rows 1-7); total over every flag combination."""
    gain = gain_label == GAIN
    if gain and sup and mem:
        return {True: "SUPPORTS: gate recipe reproducibly beats v2, recovers >= half of the oracle "
                      "filler-off gain, with registered pooled filler suppression and memory use",
                False: "reproducible gain with pooled suppression and memory use; >= half oracle "
                       "recovery not established",
                None: "reproducible gain with pooled suppression and memory use; half-oracle "
                      "comparison unavailable (oracle prerequisite not met)"}[half]
    if gain and sup:
        return "reproducible gain with pooled suppression; no registered memory-use evidence"
    if gain:
        return "reproducible gain without registered pooled suppression; mechanism unresolved"
    if sup:
        return f"registered pooled suppression; gate-v2 contrast is {gain_label}"
    return f"no reproducible gain and no registered pooled suppression; gate-v2 contrast is {gain_label}"


def q2_reading(labels: dict) -> str:
    """Prereg Q2: T/E conjunctions over the four 2x2 contrast labels."""
    if set(labels) != set(Q2_KEYS):
        raise SystemExit(f"Q2 needs contrasts {Q2_KEYS}")
    t = labels["C_T|off"] == GAIN and labels["C_T|on"] == GAIN
    e = labels["C_E|Ton"] == GAIN and labels["C_E|Toff"] == GAIN
    return {(True, True): "reproducible gains for both the no-filler-write training recipe and the "
                          "no-filler-write eval setting",
            (True, False): "reproducible gain for the no-filler-write training recipe at both eval "
                           "settings; eval-setting conjunction not met",
            (False, True): "reproducible gain for the no-filler-write eval setting under both "
                           "training recipes; training-recipe conjunction not met",
            (False, False): "neither conjunction met"}[(t, e)]


def suppression_ratio(filler_effective: list, binding_effective: list) -> float:
    """rho = mean effective beta(filler events) / mean effective beta(binding
    events). Skipped writes enter as 0. Non-finite values, an empty class or a
    non-positive binding mean fail closed (no epsilon)."""
    if not filler_effective or not binding_effective:
        raise SystemExit("rho: empty event class")
    if not all(math.isfinite(x) for x in [*filler_effective, *binding_effective]):
        raise SystemExit("rho: non-finite beta")
    bind = sum(binding_effective) / len(binding_effective)
    if not bind > 0:
        raise SystemExit("rho: binding mean is not positive")
    return (sum(filler_effective) / len(filler_effective)) / bind


def auroc(positives: list, negatives: list) -> float | None:
    """P(pos > neg) + 0.5 P(tie) via average ranks; None if a class is empty."""
    if not positives or not negatives:
        return None
    scored = sorted([(x, 1) for x in positives] + [(x, 0) for x in negatives])
    rank_sum, i = 0.0, 0
    while i < len(scored):
        j = i
        while j < len(scored) and scored[j][0] == scored[i][0]:
            j += 1
        avg = (i + 1 + j) / 2                                   # average 1-based rank of the tie block
        rank_sum += avg * sum(lab for _x, lab in scored[i:j])
        i = j
    p, n = len(positives), len(negatives)
    return (rank_sum - p * (p + 1) / 2) / (p * n)
