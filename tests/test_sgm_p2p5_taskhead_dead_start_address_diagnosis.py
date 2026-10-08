"""Focused CPU checks for scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py (#gravity 21939/21940):
oracle query wiring, fail-closed dev-eval integrity, exact all-absent reads, enforced identity/step
binding, and retained ERROR evidence for setup failures."""

import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sgm-p2p5-taskhead-dead-start-address-diagnosis.py"
_spec = importlib.util.spec_from_file_location("dead_start_diag", SCRIPT)
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)

from memsub.runtime.sgm_model_runtime import EmptyReadWeight  # noqa: E402
from memsub.sgm.synthetic_pilot import PilotConfig, build  # noqa: E402


def _tiny(arm: str) -> PilotConfig:
    return PilotConfig(arm=arm, readout="taskhead", n_bindings=4, n_queries=2, filler_len=4, steps=10, batch=4, seed=0)


def test_oracle_query_wiring_aligns_exactly_and_reads_present_cells():
    pcfg = _tiny("oracle")
    _, backend, _ = build(pcfg)
    rep = D.diagnose(backend, pcfg)
    for lay in rep["per_layer_head"].values():
        assert lay["align_within_1_cell"] == [1.0] * len(lay["align_within_1_cell"])
        assert max(lay["query_read_absent_weight_mean"]) == 0.0
        assert max(lay["query_read_all_positive_cells_absent_fraction"]) == 0.0


def test_oracle_grad_at_init_runs_without_optimizer_and_clears_grads():
    pcfg = _tiny("oracle")
    runtime, backend, head = build(pcfg)
    before = {k: v.clone() for k, v in runtime.adapters.state_dict().items()}
    out = D.grad_reach_at_init(runtime, backend, head, pcfg)
    assert math.isfinite(out["loss"]) and out["head_grad_norm"] is not None
    assert all(torch.equal(v, runtime.adapters.state_dict()[k]) for k, v in before.items())
    assert all(p.grad is None for p in list(runtime.adapters.parameters()) + list(head.parameters()))


def test_learned_arm_without_oracle_still_runs():
    pcfg = _tiny("learned")
    _, backend, _ = build(pcfg)
    assert D.diagnose(backend, pcfg)["dev_queries"] == D.DEV_BATCHES * D.DEV_BATCH_SIZE * 2


def test_read_absence_is_exact_not_thresholded():
    # codex counterexample: 0.9999995 on absent cells, a positive-weight PRESENT cell remains
    w = torch.zeros(1, 1, 9)
    w[0, 0, 0], w[0, 0, 1] = 0.9999995, 5e-7
    mass, all_absent = D.read_absence(EmptyReadWeight(w, [False, True] + [False] * 7))
    assert mass.item() == pytest.approx(0.9999995) and not all_absent.item()
    # zero-weight present cell does not count; every positive-weight cell absent -> exact True
    w2 = torch.zeros(1, 1, 9)
    w2[0, 0, 0] = 1.0
    _, all_absent2 = D.read_absence(EmptyReadWeight(w2, [False, True] + [False] * 7))
    assert all_absent2.item()


def _telemetry(tmp_path, rows):
    f = tmp_path / "routing_telemetry.jsonl"
    f.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return {"telemetry": str(f)}


REPORT = {"per_layer_head": {"6": {"query_read_absent_weight_mean": [0.5, 0.5]}}, "bank": {"occupancy_mean": 10.0}}
GOOD = {"query_empty_read_weight": 0.5, "occupancy_mean": 10.0, "accuracy": 0.25}


def test_dev_eval_check_reproduces(tmp_path):
    out = D.training_dev_eval_check(_telemetry(tmp_path, [{"step": 0, "eval": GOOD}]), 0, REPORT)
    assert out["status"] == "reproduced" and out["logged_training_dev_accuracy_not_recomputed"] == 0.25


@pytest.mark.parametrize("rows", [
    [{"step": 100, "eval": GOOD}],                                                   # missing step
    [{"step": 0}],                                                                   # no eval logged
    [{"step": 0, "eval": GOOD}, {"step": 0, "eval": GOOD}],                           # ambiguous
    [{"step": 0, "eval": {**GOOD, "query_empty_read_weight": float("nan")}}],         # non-finite
    [{"step": 0, "eval": {**GOOD, "accuracy": float("inf")}}],                       # non-finite, uncompared
    [{"step": 0, "eval": {**GOOD, "occupancy_mean": None}}],                         # malformed
    [{"step": 0, "eval": {**GOOD, "query_empty_read_weight": 0.6}}],                  # mismatch
])
def test_dev_eval_check_fails_closed(tmp_path, rows):
    with pytest.raises(ValueError):
        D.training_dev_eval_check(_telemetry(tmp_path, rows), 0, REPORT)


def test_checkpoint_step_and_pilot_config_are_enforced(tmp_path):
    pcfg = _tiny("learned")
    runtime, _, head = build(pcfg)
    pilot = {k: getattr(pcfg, k) for k in pcfg.__dataclass_fields__}
    ck = {"step": 50, "pilot_config": pilot, "adapters": runtime.adapters.state_dict(), "head": head.state_dict()}
    f = tmp_path / "gen.pt"
    torch.save(ck, f)
    assert D.load_params(runtime, head, {"params": str(f), "expected_step": 50}, pilot)["step"] == 50
    with pytest.raises(ValueError):
        D.load_params(runtime, head, {"params": str(f), "expected_step": 100}, pilot)
    with pytest.raises(ValueError):
        D.load_params(runtime, head, {"params": str(f), "expected_step": 50}, {**pilot, "seed": 1})


def test_setup_identity_failure_retains_error_and_exits_nonzero(tmp_path):
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"run": {"memsub_source_sha256": "0" * 64, "torch": torch.__version__,
                                         "transformers": "x"}, "entries": []}))
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(SCRIPT), "--index", str(index), "--out", str(out)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode != 0
    err = (out / "ERROR.txt").read_text()
    assert err.startswith("stage: setup") and "run identity memsub_source_sha256" in err
    assert json.loads((out / "run.json").read_text())["done"] == []
