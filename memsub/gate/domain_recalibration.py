"""Per-domain recalibration procedure (ABLATION.md A5).

LODO showed gate discrimination transfers across domains but calibration
does not. Given a small labeled sample (~200 items) from a new domain, fit a
scalar temperature on FROZEN gate logits and record (domain, T, ECE
before/after) into the checkpoint's calibration record. No gate weights are
touched — this is a deployment procedure, not training.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .gate_evaluation_metrics import expected_calibration_error


@dataclass
class DomainCalibrationRecord:
    domain: str
    temperature: float
    n_fit_items: int
    ece_before: float
    ece_after: float
    bias: float = 0.0            # Platt fallback: sigmoid(logit/T + bias)
    method: str = "temperature"  # "temperature" | "platt"


def fit_temperature(logits: np.ndarray, y: np.ndarray) -> float:
    """Scalar temperature minimizing NLL (grid over log-space; convex)."""
    lg, yy = logits.astype(np.float64), y.astype(np.float64)
    best_t, best_nll = 1.0, np.inf
    for t in np.geomspace(0.25, 8.0, 61):
        p = np.clip(1 / (1 + np.exp(-lg / t)), 1e-7, 1 - 1e-7)
        nll = -np.mean(yy * np.log(p) + (1 - yy) * np.log(1 - p))
        if nll < best_nll:
            best_t, best_nll = float(t), float(nll)
    return best_t


def fit_platt(logits: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Temperature + bias grid (Platt scaling on frozen scores). Fallback for
    cross-domain shift where the miscalibration has a location component a
    pure temperature cannot repair."""
    lg, yy = logits.astype(np.float64), y.astype(np.float64)
    best, best_nll = (1.0, 0.0), np.inf
    for t in np.geomspace(0.25, 8.0, 31):
        for b in np.linspace(-2.0, 2.0, 41):
            p = np.clip(1 / (1 + np.exp(-(lg / t + b))), 1e-7, 1 - 1e-7)
            nll = -np.mean(yy * np.log(p) + (1 - yy) * np.log(1 - p))
            if nll < best_nll:
                best, best_nll = (float(t), float(b)), float(nll)
    return best


def recalibrate_domain(domain: str, fit_logits: np.ndarray, fit_y: np.ndarray,
                       eval_logits: np.ndarray, eval_y: np.ndarray,
                       ece_target: float = 0.05) -> DomainCalibrationRecord:
    """Fit T on the small labeled sample; report ECE before/after on the
    held-out evaluation portion of the same domain. Escalates to Platt
    (T + bias) when temperature alone misses ece_target on the FIT sample's
    own reliability (never peeks at eval)."""
    p_before = 1 / (1 + np.exp(-eval_logits))
    ece_before = expected_calibration_error(p_before, eval_y)

    t = fit_temperature(fit_logits, fit_y)
    fit_ece_t = expected_calibration_error(
        1 / (1 + np.exp(-fit_logits / t)), fit_y)
    if fit_ece_t <= ece_target:
        p_after = 1 / (1 + np.exp(-eval_logits / t))
        return DomainCalibrationRecord(
            domain=domain, temperature=t, n_fit_items=int(len(fit_y)),
            ece_before=ece_before,
            ece_after=expected_calibration_error(p_after, eval_y))

    t, b = fit_platt(fit_logits, fit_y)
    p_after = 1 / (1 + np.exp(-(eval_logits / t + b)))
    return DomainCalibrationRecord(
        domain=domain, temperature=t, bias=b, method="platt",
        n_fit_items=int(len(fit_y)), ece_before=ece_before,
        ece_after=expected_calibration_error(p_after, eval_y))


def update_checkpoint_calibration(checkpoint: dict,
                                  record: DomainCalibrationRecord) -> dict:
    """Emit the record into the checkpoint's calibration block (in place)."""
    block = checkpoint.setdefault("domain_calibration", {})
    block[record.domain] = {
        "temperature": record.temperature,
        "bias": record.bias,
        "method": record.method,
        "n_fit_items": record.n_fit_items,
        "ece_before": record.ece_before,
        "ece_after": record.ece_after,
    }
    return checkpoint
