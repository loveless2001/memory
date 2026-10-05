"""End-to-end smoke of the P2G readings pipeline (corner evaluation -> Q1/Q2
readings) on UNTRAINED toy checkpoints. Never touches registered checkpoints
or the fresh final seed's registered population: episode count is shrunk to
one 16-episode batch and N=4, so it exercises code paths only."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from memsub.sgm.synthetic_pilot import PilotConfig, build
from memsub.sgm.synthetic_pilot_run import save_trained_parameters

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cell(tmp: Path, name: str, **over):
    pilot = {"n_bindings": 4, "seed": 0, **over}
    rt, _be, head = build(PilotConfig(**pilot))
    d = tmp / name
    d.mkdir()
    save_trained_parameters(rt, head, d / "trained_parameters.safetensors")
    return d, {"pilot_config": pilot, "run_id": name, "modal_group": "toy"}


def test_corner_evaluation_and_readings_are_well_formed(tmp_path, monkeypatch):
    rd = _load(ROOT / "scripts" / "sgm-p2g-readings.py", "p2g_readings")
    monkeypatch.setattr(rd.OBS, "FINAL_BATCHES", 1)            # 16 episodes instead of 256
    monkeypatch.setattr(rd.P2D, "N_EPISODES", 16)
    monkeypatch.setattr(rd, "READINGS_BASE", 777_000)          # never the reserved seed values (codex 21390)
    seeds, real = [], rd.OBS.eval_rows
    monkeypatch.setattr(rd.OBS, "eval_rows", lambda b, h, p, seed, ivs, w: seeds.append(seed) or real(b, h, p, seed, ivs, w))
    models = {"T_on": _cell(tmp_path, "on"), "T_off": _cell(tmp_path, "off", filler_writes=False),
              "gate": _cell(tmp_path, "gate", beta_bias_init=-3.0)}
    per_seed = {s: rd.evaluate_cell(4, s, models, tmp_path) for s in (0, 1)}
    assert set(seeds) == {777_000, 777_001}
    one = per_seed[0]
    assert set(one["corners"]) == {"Ton-Eon", "Ton-Eoff", "Toff-Eoff", "Toff-Eon", "Tgate-Eon"}
    assert one["corners"]["Toff-Eoff"]["gate"]["rho_pooled_effective"] == 0.0   # skipped filler writes
    assert one["corners"]["Tgate-Eon"]["gate"]["rho_pooled_effective"] > 0
    assert len(list(tmp_path.glob("rows-n4-s0-*.jsonl"))) == 5
    out = rd.read_n(per_seed)
    classes = {rd.RULES.GAIN, rd.RULES.LOSS, rd.RULES.EXCLUDED, rd.RULES.NEITHER}
    assert set(out["q2_labels"]) == set(rd.RULES.Q2_KEYS) and set(out["q2_labels"].values()) <= classes
    assert out["q1_flags"]["half"] in (True, False, None)
    assert isinstance(out["q1_reading"], str) and isinstance(out["q2_reading"], str)
