"""Model-free end-to-end check of the probe orchestrator: fake capture with a planted signal
(z_value linearly encodes the preceding key), real math, s2 path (4-fold CV). No model load."""

import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _forbid_model_load(monkeypatch):
    """No test in this file may load Qwen by any path (codex 22400)."""
    monkeypatch.setenv("PKPROBE_FORBID_MODEL", "1")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def _fake_capture_module(d=64, dk=48):
    rng = np.random.default_rng(0)
    vocab = rng.normal(size=(12000, dk))
    w = rng.normal(size=(dk, d))

    def capture(runtime, backend, pcfg, split, n, seed, batch=4, log=print):
        g = np.random.default_rng(seed)
        lo = 10000 if split == "train" else 10800
        keys = np.stack([lo + g.permutation(200)[:32] for _ in range(n)])
        vals = 3000 + g.integers(0, 64, size=(n, 32))
        out = {"layers": [6, 13], "key_ids": keys, "value_ids": vals}
        for l in (6, 13):
            out[f"zk_L{l}"] = vocab[keys] @ w + 0.01 * g.normal(size=(n, 32, d))
            out[f"zv_L{l}"] = (vocab[keys] @ w if l == 6 else g.normal(size=(n, 32, d))) + 0.01 * g.normal(size=(n, 32, d))
        return out

    mod = types.SimpleNamespace(MANIFEST=ROOT / "scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py",
                                load_model=lambda: (None, None, None), capture=capture,
                                embeddings=lambda rt, ids: vocab[ids])
    return mod


def test_s2_path_runs_end_to_end_with_planted_signal(tmp_path, monkeypatch):
    R = _load(ROOT / "scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py", "pkrun")
    real_load = R.load
    fake = _fake_capture_module()
    monkeypatch.setattr(R, "load", lambda path, name: fake if path == R.CAPTURE_PATH else real_load(path, name))
    monkeypatch.setitem(R.MODES, "s2", {**R.MODES["s2"], "fit": ("train", 8, 1), "ev": ("heldout", 6, 2)})
    monkeypatch.setattr(sys, "argv", ["x", "--mode", "s2", "--wall-s", "2400", "--out", str(tmp_path / "o")])
    R.main()
    res = json.loads((tmp_path / "o" / "result.json").read_text())
    m = res["metrics"]
    assert m["L6/V"]["top1_point_lo_hi"][0] > 0.9            # planted: value input encodes the key
    assert m["L13/V"]["top1_point_lo_hi"][0] < 0.2           # no signal at L13 by construction
    assert m["L6/K"]["top1_point_lo_hi"][0] > 0.9
    assert m["L6/V-shuf"]["top1_point_lo_hi"][0] < 0.2       # shuffled null near chance
    assert m["L6/V-shuf"]["fit_target_sha256"] != m["L6/V"]["fit_target_sha256"]   # null FIT on shuffled targets
    assert res["reading"]["read"] is False
    assert (tmp_path / "o" / "features.npz").exists()


def test_wrong_wall_is_refused_before_any_work(tmp_path, monkeypatch):
    R = _load(ROOT / "scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py", "pkrun2")
    real_load = R.load

    def sentinel(*a, **k):
        raise RuntimeError("MODEL LOAD ATTEMPTED")
    stub = types.SimpleNamespace(MANIFEST=ROOT / "scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py",
                                 load_model=sentinel, capture=sentinel, embeddings=sentinel)
    monkeypatch.setattr(R, "load", lambda path, name: stub if path == R.CAPTURE_PATH else real_load(path, name))
    monkeypatch.setattr(sys, "argv", ["x", "--mode", "s1", "--wall-s", "999", "--out", str(tmp_path / "o")])
    with pytest.raises(RuntimeError, match="frozen"):
        R.main()
    assert not (tmp_path / "o").exists()


def _sentinel_runner(name):
    R = _load(ROOT / "scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py", name)
    real_load = R.load

    def sentinel(*a, **k):
        raise RuntimeError("MODEL LOAD ATTEMPTED")
    stub = types.SimpleNamespace(MANIFEST=R.CAPTURE_PATH, load_model=sentinel, capture=sentinel, embeddings=sentinel)
    return R, (lambda path, n: stub if path == R.CAPTURE_PATH else real_load(path, n))


def test_capture_guard_refuses_model_load_under_test_flag(monkeypatch):
    C = _load(ROOT / "scripts/sgm-p2p5-previous-key-probe-capture-qwen-adapter-inputs.py", "pkcap_guard")

    def sentinel(*a, **k):        # second layer: even with the guard removed, nothing real is reached
        raise RuntimeError("SENTINEL: model construction reached")
    monkeypatch.setattr(C, "frozen_pilot_config", sentinel)
    monkeypatch.setattr(C, "build", sentinel)
    with pytest.raises(RuntimeError, match="PKPROBE_FORBID_MODEL"):
        C.load_model()


@pytest.mark.parametrize("admit,wall,match", [(False, 100, "refused"), (True, 999, "ceil")])
def test_full_mode_refuses_without_admitting_admission(tmp_path, monkeypatch, admit, wall, match):
    R, fake_load = _sentinel_runner(f"pkrun_full_{admit}")
    monkeypatch.setattr(R, "load", fake_load)
    adm = tmp_path / "admission.json"
    adm.write_text(json.dumps({"admit": admit, "wall_s": 100.0}))
    monkeypatch.setattr(sys, "argv", ["x", "--mode", "full", "--wall-s", str(wall), "--admission", str(adm),
                                      "--out", str(tmp_path / "o")])
    with pytest.raises(RuntimeError, match=match):
        R.main()
    assert not (tmp_path / "o").exists()
