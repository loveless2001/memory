"""Model-free checks of the probe orchestrator and stage receipts (proposal v0.5). No model load anywhere:
PKPROBE_FORBID_MODEL=1 (autouse) + sentinel stubs on every gate path (codex 22400/22408/22412)."""

import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
RUN_PATH = ROOT / "scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py"
RX_PATH = ROOT / "scripts/sgm-p2p5-previous-key-probe-stage-receipts-and-admission-validation.py"


@pytest.fixture(autouse=True)
def _forbid_model_load(monkeypatch):
    """No test in this file may load Qwen by any path (codex 22400)."""
    monkeypatch.setenv("PKPROBE_FORBID_MODEL", "1")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def _sentinel(*a, **k):
    raise RuntimeError("MODEL LOAD ATTEMPTED")


def _runner(name, capture_mod=None, rx=None):
    """Run-script module whose capture (and optionally receipts) module is replaced."""
    R = _load(RUN_PATH, name)
    real = R.load
    stub = capture_mod or types.SimpleNamespace(load_model=_sentinel, capture=_sentinel, embeddings=_sentinel,
                                                identities=_sentinel)
    R.load = lambda path, n: stub if path == R.CAPTURE_PATH else (rx if (rx is not None and path == R.RECEIPTS_PATH) else real(path, n))
    return R


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

    return types.SimpleNamespace(load_model=lambda: (None, None, None), capture=capture,
                                 identities=lambda rt, pcfg: {"fake": True}, embeddings=lambda rt, ids: vocab[ids])


def test_s2_path_runs_end_to_end_with_planted_signal_and_fake_output_fails_receipt(tmp_path, monkeypatch):
    rx = _load(RX_PATH, "pkrx_s2")
    rx.MODES["s2"] = {**rx.MODES["s2"], "fit": ("train", 8, 1), "ev": ("heldout", 6, 2)}
    R = _runner("pkrun", _fake_capture_module(), rx)
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
    assert json.loads((tmp_path / "o" / "status.json").read_text())["state"] == "COMPLETE"
    # codex 22412 counterexample: this fake output must NOT validate as an S2 receipt, even with exit 0
    (tmp_path / "o.exit").write_text("0\n")
    assert json.loads((tmp_path / "o" / "run.json").read_text()) == res["run"]     # producer binding holds
    with pytest.raises(RuntimeError, match="episode counts"):                      # refused for the fake schema (8+6 eps), not run.json
        _load(RX_PATH, "pkrx_s2_check").validate_receipt(tmp_path / "o", "s2")


def test_wrong_wall_is_refused_before_any_work(tmp_path, monkeypatch):
    R = _runner("pkrun2")
    monkeypatch.setattr(sys, "argv", ["x", "--mode", "s1", "--wall-s", "999", "--out", str(tmp_path / "o")])
    with pytest.raises(RuntimeError, match="frozen"):
        R.main()
    assert not (tmp_path / "o").exists()


def test_capture_guard_refuses_model_load_under_test_flag(monkeypatch):
    C = _load(ROOT / "scripts/sgm-p2p5-previous-key-probe-capture-qwen-adapter-inputs.py", "pkcap_guard")

    def sentinel(*a, **k):        # second layer: even with the guard removed, nothing real is reached
        raise RuntimeError("SENTINEL: model construction reached")
    monkeypatch.setattr(C, "frozen_pilot_config", sentinel)
    monkeypatch.setattr(C, "build", sentinel)
    with pytest.raises(RuntimeError, match="PKPROBE_FORBID_MODEL"):
        C.load_model()


# ---------- stage receipts ----------

COMPS = {"capture_s_per_episode": 5.0, "model_load_s": 60.0, "fit_s": 100.0, "boot_s": 1.0, "output_s": 31.0}


def _admission(comps=COMPS):
    est = comps["model_load_s"] + comps["capture_s_per_episode"] * 160 + comps["fit_s"] + comps["boot_s"] + comps["output_s"] + 300.0
    return {"estimate_s": est, "wall_s": 2 * est, "admit": bool(0 < 2 * est <= 14400), "components": dict(comps)}


def _valid_stage(tmp, name, mode, rx, init="a" * 64, comps=COMPS):
    d = tmp / name
    d.mkdir()
    (tmp / f"{name}.exit").write_text("0\n")
    m = rx.MODES[mode]
    arrays = {}
    for pre, (_, n, _) in (("fit", m["fit"]), ("ev", m["ev"])):
        arrays[f"{pre}_key_ids"] = np.zeros((n, 32), np.int64); arrays[f"{pre}_value_ids"] = np.zeros((n, 32), np.int64)
        for l in rx.LAYERS:
            arrays[f"{pre}_zk_L{l}"] = np.zeros((n, 32, 1024), np.float32); arrays[f"{pre}_zv_L{l}"] = np.zeros((n, 32, 1024), np.float32)
    np.savez(d / "features.npz", **arrays)
    run = {"mode": mode, "wall_s": m["wall"] or 1000, "threads": 8, "n_boot": 4000, "seeds": m["seeds"],
           "fit": list(m["fit"]), "ev": list(m["ev"]), "sha256": rx.source_shas(),
           "blas_env": {v: "8" for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
           "threadpools": [], "git_head": "x",
           "identities": {"pilot_config_resolved": rx.expected_pilot_config(),
                          "sgm_config_resolved": {"selected_layers": [6, 13, 20, 27], "feature_shift": 1},
                          "backbone_pin": json.loads(json.dumps(rx.QWEN3_0P6B_BASE)), "initial_adapter_params_sha256": init},
           "features_sha256": hashlib.sha256((d / "features.npz").read_bytes()).hexdigest()}
    metrics = {f"L{l}/{s}": {"top1_point_lo_hi": [0.5, 0.4, 0.6]} for l in rx.LAYERS for s in rx.SETS}
    for l in rx.LAYERS:
        metrics[f"L{l}/dVK"] = {"point_lo_hi": [0.0, -0.1, 0.1]}
        metrics[f"L{l}/dVK_vs_K (descriptive)"] = {"point_lo_hi": [0.0, -0.1, 0.1]}
    res = {"run": run, "metrics": metrics, "reading": {"label": "INCONCLUSIVE", "read": mode == "full"}, "timing_s": {"start": 0.0}}
    if mode == "s1":
        res["admission"] = _admission(comps)
        (d / "admission.json").write_text(json.dumps(res["admission"]))
    (d / "run.json").write_text(json.dumps(run))
    (d / "result.json").write_text(json.dumps(res))
    (d / "status.json").write_text(json.dumps({"state": "COMPLETE"}))
    return d


def _edit(d, fname, fn):
    p = d / fname
    o = json.loads(p.read_text()); fn(o); p.write_text(json.dumps(o))


def _edit_run(d, fn):   # keep run.json and result.json["run"] consistent
    _edit(d, "run.json", fn); _edit(d, "result.json", lambda r: fn(r["run"]))


CORRUPT = {
    "missing": None,
    "s2_running": lambda s1, s2: (s2 / "status.json").write_text(json.dumps({"state": "RUNNING"})),
    "s2_exit1": lambda s1, s2: (s2.parent / "s2.exit").write_text("1\n"),
    "sha": lambda s1, s2: _edit_run(s1, lambda r: r["sha256"].update(memsub_tree="0" * 64)),
    "nan": lambda s1, s2: (s1 / "result.json").write_text((s1 / "result.json").read_text().replace("0.4", "NaN", 1)),
    "adm_mismatch": lambda s1, s2: _edit(s1, "admission.json", lambda a: a.update(wall_s=1.0)),
    "no_run": lambda s1, s2: (s2 / "run.json").unlink(),
    "no_features": lambda s1, s2: (s2 / "features.npz").unlink(),
    "feat_sha": lambda s1, s2: _edit_run(s2, lambda r: r.update(features_sha256="0" * 64)),
    "fake_identities": lambda s1, s2: _edit_run(s2, lambda r: r.update(identities={"fake": True})),
    "seeds": lambda s1, s2: _edit_run(s2, lambda r: r["seeds"].update(boot=1)),
    "init_mismatch": lambda s1, s2: _edit_run(s2, lambda r: r["identities"].update(initial_adapter_params_sha256="b" * 64)),
    "metric_keys": lambda s1, s2: _edit(s2, "result.json", lambda r: r["metrics"].pop("L27/V")),
}
MATCH = {"missing": "exit receipt", "s2_running": "not COMPLETE", "s2_exit1": "exit receipt", "sha": "source hashes",
         "nan": "nonfinite", "adm_mismatch": "differs from result", "no_run": "run.json missing",
         "no_features": "features.npz missing", "feat_sha": "features sha", "fake_identities": "PilotConfig",
         "seeds": "seeds differ", "init_mismatch": "initial adapter hashes", "metric_keys": "metric keys"}


@pytest.mark.parametrize("case", sorted(CORRUPT))
def test_full_mode_receipt_gate_refuses(tmp_path, monkeypatch, case):
    rx = _load(RX_PATH, f"pkrx_{case}")
    if case != "missing":
        s1, s2 = _valid_stage(tmp_path, "s1", "s1", rx), _valid_stage(tmp_path, "s2", "s2", rx)
        CORRUPT[case](s1, s2)
    R = _runner(f"pkrun_full_{case}")
    monkeypatch.setattr(sys, "argv", ["x", "--mode", "full", "--wall-s", "2584", "--s1-dir", str(tmp_path / "s1"),
                                      "--s2-dir", str(tmp_path / "s2"), "--out", str(tmp_path / "o")])
    with pytest.raises(RuntimeError, match=MATCH[case]):
        R.main()
    assert not (tmp_path / "o").exists()


def test_full_mode_wrong_wall_arg_and_non_admitting_s1_refused(tmp_path, monkeypatch):
    rx = _load(RX_PATH, "pkrx_w")
    _valid_stage(tmp_path, "s1", "s1", rx); _valid_stage(tmp_path, "s2", "s2", rx)
    R = _runner("pkrun_w")
    monkeypatch.setattr(sys, "argv", ["x", "--mode", "full", "--wall-s", "2583", "--s1-dir", str(tmp_path / "s1"),
                                      "--s2-dir", str(tmp_path / "s2"), "--out", str(tmp_path / "o")])
    with pytest.raises(RuntimeError, match="admitted wall"):
        R.main()
    big = {**COMPS, "capture_s_per_episode": 60.0}           # 2 x estimate > 4 h -> consistent admit:false
    _valid_stage(tmp_path, "s1b", "s1", rx, comps=big)
    with pytest.raises(RuntimeError, match="did not admit"):
        rx.validate_receipt(tmp_path / "s1b", "s1")


def test_full_mode_valid_receipts_pass_gate_then_hit_sentinel(tmp_path, monkeypatch):
    rx = _load(RX_PATH, "pkrx_ok")
    _valid_stage(tmp_path, "s1", "s1", rx); _valid_stage(tmp_path, "s2", "s2", rx)
    R = _runner("pkrun_ok")
    monkeypatch.setattr(sys, "argv", ["x", "--mode", "full", "--wall-s", "2584", "--s1-dir", str(tmp_path / "s1"),
                                      "--s2-dir", str(tmp_path / "s2"), "--out", str(tmp_path / "o")])
    with pytest.raises(RuntimeError, match="MODEL LOAD ATTEMPTED"):
        R.main()
    assert json.loads((tmp_path / "o" / "status.json").read_text())["state"] == "FAILED"


@pytest.mark.parametrize("bad,match", [
    ({"fit_s": -1.0}, "finite and >= 0"), ({"fit_s": float("inf")}, "finite and >= 0"),
    ({"estimate_s": 1.0}, "does not recompute"), ({"wall_s": 1.0}, "2 x estimate"), ({"admit": False}, "admit flag"),
])
def test_admission_is_recomputed_and_parts_checked(bad, match):
    rx = _load(RX_PATH, "pkrx_adm")
    adm = _admission()
    if "fit_s" in bad:
        adm["components"].update(bad)
    else:
        adm.update(bad)
    with pytest.raises(RuntimeError, match=match):
        rx.validate_admission(adm)
    assert rx.validate_admission(_admission()) == _admission()["wall_s"]


def test_receipt_cli_full_wall(tmp_path, monkeypatch, capsys):
    rx = _load(RX_PATH, "pkrx_cli")
    _valid_stage(tmp_path, "s1", "s1", rx); _valid_stage(tmp_path, "s2", "s2", rx)
    monkeypatch.setattr(sys, "argv", ["x", "--full-wall", "--s1", str(tmp_path / "s1"), "--s2", str(tmp_path / "s2")])
    assert rx.main() == 0 and capsys.readouterr().out.strip() == "2584"
    (tmp_path / "s2.exit").write_text("137\n")
    assert rx.main() == 1


def test_source_shas_bind_memsub_tree_and_probe_files():
    rx = _load(RX_PATH, "pkrx_src")
    s = rx.source_shas()
    assert s["memsub_tree"] == rx.source_tree_sha256(ROOT / "memsub")
    assert {p.name for p in rx.SOURCES} <= set(s) and len(s) == len(rx.SOURCES) + 1


def test_strict_json_reader_rejects_nan(tmp_path):
    rx = _load(RX_PATH, "pkrx_strict")
    f = tmp_path / "x.json"
    f.write_text('{"a": NaN}')
    with pytest.raises(RuntimeError, match="nonfinite"):
        rx.strict_json(f)
    f.write_text('{"a": 1.5}')
    assert rx.strict_json(f) == {"a": 1.5}


def _frozen_fake_capture_module(rx, d=1024):
    """Fake capture with the FROZEN shapes (4 layers, 1024-dim) and schema-correct identities; no model."""
    rng = np.random.default_rng(1)
    vocab = rng.normal(size=(12000, d)).astype(np.float32)

    def capture(runtime, backend, pcfg, split, n, seed, batch=4, log=print):
        g = np.random.default_rng(seed)
        lo = 10000 if split == "train" else 10800
        keys = np.stack([lo + g.permutation(200)[:32] for _ in range(n)])
        vals = 3000 + g.integers(0, 64, size=(n, 32))
        out = {"layers": list(rx.LAYERS), "key_ids": keys, "value_ids": vals}
        for l in rx.LAYERS:
            out[f"zk_L{l}"] = (vocab[keys] + 0.01 * g.normal(size=(n, 32, d))).astype(np.float32)
            base = vocab[keys] if l == 6 else g.normal(size=(n, 32, d))
            out[f"zv_L{l}"] = (base + 0.01 * g.normal(size=(n, 32, d))).astype(np.float32)
        return out

    ids = {"pilot_config_resolved": rx.expected_pilot_config(),
           "sgm_config_resolved": {"selected_layers": list(rx.LAYERS), "feature_shift": 1},
           "backbone_pin": json.loads(json.dumps(rx.QWEN3_0P6B_BASE)), "initial_adapter_params_sha256": "c" * 64,
           "torch_version": "fake", "torch_threads": 8}
    return types.SimpleNamespace(load_model=lambda: (None, None, None), capture=capture,
                                 identities=lambda rt, pcfg: ids, embeddings=lambda rt, x: vocab[x])


def test_producer_to_validator_success_s1_s2_full_wall(tmp_path, monkeypatch):
    """codex 22418: an ordinary successful S1/S2 produced by the real run script must validate."""
    rx = _load(RX_PATH, "pkrx_prod")
    fake = _frozen_fake_capture_module(rx)
    for mode, wall in (("s1", "1800"), ("s2", "2400")):
        R = _runner(f"pkrun_prod_{mode}", fake)
        monkeypatch.setattr(R, "profile_and_admit", lambda M, t, n_cap, out_bytes: _admission())   # no full-size profile
        monkeypatch.setattr(sys, "argv", ["x", "--mode", mode, "--wall-s", wall, "--out", str(tmp_path / mode)])
        R.main()
        (tmp_path / f"{mode}.exit").write_text("0\n")
        run_json = json.loads((tmp_path / mode / "run.json").read_text())
        assert run_json == json.loads((tmp_path / mode / "result.json").read_text())["run"]
        v = rx.validate_receipt(tmp_path / mode, mode)
        assert v["initial_adapter_params_sha256"] == "c" * 64
    assert rx.full_wall(tmp_path / "s1", tmp_path / "s2") == 2584
