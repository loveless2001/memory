"""The P2.5 speed-up parity checker must FAIL on structural defects (codex 21488
counterexamples): a missing gradient entry, a non-finite gradient, perturbed initial
weights, a shape change, missing keys or a renamed parameter. A clean match passes."""

import copy
import importlib.util
from pathlib import Path

import torch

SPEC = importlib.util.spec_from_file_location(
    "parity_check", Path(__file__).resolve().parents[1] / "scripts/sgm-p2p5-sgm-path-speedup-parity-check.py")
parity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parity)


def _result():
    w = torch.tensor([1.0, 2.0])
    return {"init": {"w": w.clone(), "b": torch.zeros(1)}, "loss": [torch.tensor(1.0), torch.tensor(0.5)],
            "grads": [[torch.tensor([0.1, 0.2]), None, torch.tensor([3.0])],
                      [torch.tensor([0.3, 0.4]), None, torch.tensor([1.0])]],
            "param_names": ["adapters.w", "adapters.frozen", "head.b"],
            "weights": {"w": w + 1, "b": torch.ones(1)}, "train_s": 1.0,
            "dev": {"accuracy": 0.5, "loss": 0.25}, "preds": [1, 2]}


def _fails(mutate) -> bool:
    ref, cand = _result(), _result()
    mutate(cand)
    return parity.compare(ref, cand, 1e-5)["pass"] is False


def test_identical_results_pass_bitwise():
    out = parity.compare(_result(), _result(), 1e-5)
    assert out["pass"] and out["bitwise"]


def test_missing_gradient_entry_fails():
    assert _fails(lambda c: c["grads"][1].pop())


def test_missing_update_fails():
    assert _fails(lambda c: c["grads"].pop())


def test_non_finite_candidate_gradient_fails():
    assert _fails(lambda c: c["grads"][0][0].__setitem__(1, float("nan")))
    assert _fails(lambda c: c["loss"].__setitem__(1, torch.tensor(float("inf"))))


def test_perturbed_initial_weights_fail_even_within_tolerance():
    assert _fails(lambda c: c["init"]["w"].__setitem__(0, 1.0 + 1e-6))


def test_shape_and_key_and_name_changes_fail():
    assert _fails(lambda c: c["weights"].__setitem__("w", torch.tensor([2.0, 3.0, 0.0])))
    assert _fails(lambda c: c["weights"].pop("b"))
    assert _fails(lambda c: c["init"].pop("b"))
    assert _fails(lambda c: c["param_names"].__setitem__(2, "head.renamed"))
    assert _fails(lambda c: c["grads"][0].__setitem__(1, torch.zeros(1)))      # presence differs


def test_tolerance_and_dev_predictions():
    ref, cand = _result(), copy.deepcopy(_result())
    cand["weights"]["w"] = cand["weights"]["w"] * (1 + 1e-7)
    out = parity.compare(ref, cand, 1e-5)
    assert out["pass"] and not out["bitwise"]
    assert _fails(lambda c: c["weights"].__setitem__("w", c["weights"]["w"] * (1 + 1e-3)))
    assert _fails(lambda c: c.__setitem__("preds", [1, 3]))
