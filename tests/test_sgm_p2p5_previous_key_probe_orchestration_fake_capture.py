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
                                identities=lambda rt, pcfg: {"fake": True},
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


def _receipts():
    return _load(ROOT / "scripts/sgm-p2p5-previous-key-probe-stage-receipts-and-admission-validation.py", "pkrx_t")


def _stage(tmp, name, mode, shas, exit_code="0", state="COMPLETE", wall=1000.0, admit=True, metric=0.5):
    d = tmp / name
    d.mkdir()
    (tmp / f"{name}.exit").write_text(exit_code + "\n")
    (d / "status.json").write_text(json.dumps({"state": state}))
    (d / "result.json").write_text(json.dumps({"run": {"mode": mode, "sha256": shas}, "metrics": {"m": metric},
                                               "timing_s": {"t": 1.0}, "reading": {"label": "x"}}))
    if mode == "s1":
        (d / "admission.json").write_text(json.dumps({"admit": admit, "wall_s": wall}))
    return d


@pytest.mark.parametrize("case,match", [
    ("missing", "exit receipt"), ("wall0", "outside"), ("wall20000", "outside"), ("s2_running", "not COMPLETE"),
    ("s2_exit1", "exit receipt"), ("sha", "source hashes"), ("nan", "nonfinite"), ("argwall", "admitted wall"),
    ("noadmit", "did not admit"),
])
def test_full_mode_receipt_gate_refuses(tmp_path, monkeypatch, case, match):
    R, fake_load = _sentinel_runner(f"pkrun_full_{case}")
    monkeypatch.setattr(R, "load", fake_load)
    shas = _receipts().source_shas()
    bad = {**shas, "x": "0"} if case == "sha" else shas
    if case != "missing":
        _stage(tmp_path, "s1", "s1", bad, wall={"wall0": 0, "wall20000": 20000}.get(case, 1000.0),
               admit=case != "noadmit", metric=float("nan") if case == "nan" else 0.5)
        _stage(tmp_path, "s2", "s2", shas, state="RUNNING" if case == "s2_running" else "COMPLETE",
               exit_code="1" if case == "s2_exit1" else "0")
    wall = "999" if case == "argwall" else "1000"
    monkeypatch.setattr(sys, "argv", ["x", "--mode", "full", "--wall-s", wall, "--s1-dir", str(tmp_path / "s1"),
                                      "--s2-dir", str(tmp_path / "s2"), "--out", str(tmp_path / "o")])
    with pytest.raises(RuntimeError, match=match):
        R.main()
    assert not (tmp_path / "o").exists()


def test_full_mode_valid_receipts_pass_gate_then_hit_sentinel(tmp_path, monkeypatch):
    R, fake_load = _sentinel_runner("pkrun_full_ok")
    monkeypatch.setattr(R, "load", fake_load)
    shas = _receipts().source_shas()
    _stage(tmp_path, "s1", "s1", shas, wall=999.2)
    _stage(tmp_path, "s2", "s2", shas)
    monkeypatch.setattr(sys, "argv", ["x", "--mode", "full", "--wall-s", "1000", "--s1-dir", str(tmp_path / "s1"),
                                      "--s2-dir", str(tmp_path / "s2"), "--out", str(tmp_path / "o")])
    with pytest.raises(RuntimeError, match="MODEL LOAD ATTEMPTED"):
        R.main()
    assert json.loads((tmp_path / "o" / "status.json").read_text())["state"] == "FAILED"


def test_receipt_cli_full_wall(tmp_path, monkeypatch, capsys):
    RX = _receipts()
    shas = RX.source_shas()
    _stage(tmp_path, "s1", "s1", shas, wall=1234.1)
    _stage(tmp_path, "s2", "s2", shas)
    monkeypatch.setattr(sys, "argv", ["x", "--full-wall", "--s1", str(tmp_path / "s1"), "--s2", str(tmp_path / "s2")])
    assert RX.main() == 0 and capsys.readouterr().out.strip() == "1235"
    (tmp_path / "s2.exit").write_text("137\n")
    assert RX.main() == 1


def test_strict_json_reader_rejects_nan(tmp_path):
    RX = _receipts()
    f = tmp_path / "x.json"
    f.write_text('{"a": NaN}')
    with pytest.raises(RuntimeError, match="nonfinite"):
        RX.strict_json(f)
    f.write_text('{"a": 1.5}')
    assert RX.strict_json(f) == {"a": 1.5}
