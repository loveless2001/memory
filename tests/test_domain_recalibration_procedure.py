"""A5 recalibration procedure (ABLATION.md): fitting a scalar temperature on
~200 labeled items from a new domain must repair a miscalibrated-but-
discriminative score, and the record must land in the checkpoint block."""

import numpy as np

from memsub.gate.domain_recalibration import (
    fit_temperature,
    recalibrate_domain,
    update_checkpoint_calibration,
)
from memsub.gate.gate_evaluation_metrics import expected_calibration_error


def _miscalibrated_logits(n, rng, scale=4.0):
    """Well-ranked but overconfident scores: true p from mild logits, emitted
    logits scaled by `scale` (the LODO failure mode)."""
    true_logit = rng.normal(0, 1.2, n)
    y = (rng.random(n) < 1 / (1 + np.exp(-true_logit))).astype(int)
    return true_logit * scale, y


def test_temperature_repairs_overconfident_scores():
    rng = np.random.default_rng(0)
    fit_logits, fit_y = _miscalibrated_logits(200, rng)
    eval_logits, eval_y = _miscalibrated_logits(5000, rng)
    rec = recalibrate_domain("synthetic", fit_logits, fit_y,
                             eval_logits, eval_y)
    assert rec.n_fit_items == 200
    assert rec.temperature > 1.5           # recovers the inflation
    assert rec.ece_after < rec.ece_before
    assert rec.ece_after <= 0.05           # the A5 bar, achievable here


def test_fit_temperature_identity_when_calibrated():
    rng = np.random.default_rng(1)
    logits, y = _miscalibrated_logits(4000, rng, scale=1.0)
    t = fit_temperature(logits, y)
    assert 0.7 <= t <= 1.4                 # near-identity


def test_checkpoint_record_update():
    rng = np.random.default_rng(2)
    lg, y = _miscalibrated_logits(300, rng)
    rec = recalibrate_domain("legal", lg[:200], y[:200], lg[200:], y[200:])
    ck = {"state_dict": {}, "temperatures": {"0.25": 1.0}}
    update_checkpoint_calibration(ck, rec)
    assert ck["domain_calibration"]["legal"]["temperature"] == rec.temperature
    assert "ece_after" in ck["domain_calibration"]["legal"]
