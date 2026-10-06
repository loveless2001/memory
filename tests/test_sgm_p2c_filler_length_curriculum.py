"""P2C (prereg v0.2 0c8d358): label-free filler-length curriculum knob, P2C
reading table, scoped launcher, inputs binding and readings smoke. Local only."""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
from dataclasses import asdict
from pathlib import Path

import pytest
import torch

from memsub.sgm.synthetic_pilot import PilotConfig, build, train
from memsub.sgm.synthetic_pilot_evaluation import evaluate
from memsub.sgm.synthetic_pilot_run import save_trained_parameters, source_tree_sha256

ROOT = Path(__file__).resolve().parents[1]
# 3-update training fingerprints recorded on the pre-knob trainer (P2G source 5c3b5420)
PRE_KNOB_TRAIN = {0: ("70d42cd6523dcb5f17116cfe83b47c78772bae337d4c5d26b64f95a65f582388",
                      "dad1538a492ef35db1e82c65ebad38d0edd1718a4c71ef96dcc464f65b9c16a7"),
                  1: ("cb2b93380192cc5ad67dd5a4b0312bc556a129475eefd424d61c239306aa9dd8",
                      "5b0fe1077231fdf6ad990bb494ae08967b9bec22db874767fffcfc4f2da0dc5d")}
SCHEDULE = [[0, 0], [1000, 40]]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = _load(ROOT / "scripts" / "sgm-p2c-decision-rules.py", "p2c_rules")
PRE2C = _load(ROOT / "scripts" / "sgm-p2c-preflight.py", "p2c_pre")


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.chdir(ROOT)
    return _load(ROOT / "modal-runners" / "modal-m4-sgm-p2c-nonpreemptible-spawn.py", "p2c_runner")


# ---------------- knob ----------------

@pytest.mark.parametrize("seed", [0, 1])
def test_empty_schedule_is_bitwise_the_pre_knob_trainer(seed):
    p = PilotConfig(n_bindings=4, steps=3, seed=seed)
    assert PilotConfig(n_bindings=4, steps=3, seed=seed, filler_len_schedule=()) == p
    out = train(p, log=lambda r: None)
    h = hashlib.sha256()
    for k, v in sorted(out["runtime"].adapters.state_dict().items()) + sorted(out["head"].state_dict().items()):
        h.update(k.encode())
        h.update(v.detach().contiguous().numpy().tobytes())
    rows: list = []
    evaluate(out["backend"], out["head"], p.task_spec(), p.arm, p.readout, split="heldout", batches=1,
             batch_size=16, seed=777, per_example=rows)
    got = (h.hexdigest(), hashlib.sha256("".join(json.dumps(r) + "\n" for r in rows).encode()).hexdigest())
    assert got == PRE_KNOB_TRAIN[seed]


def test_schedule_lookup_and_validation():
    p = PilotConfig(filler_len_schedule=SCHEDULE)
    assert [p.training_filler_len(t) for t in (0, 999, 1000, 1499)] == [0, 0, 40, 40]
    assert p.task_spec().filler_len == 40 and PilotConfig().training_filler_len(5) == 40
    for bad in ([[1, 0]], [[0, 0], [0, 40]], [[0, 0], [500, 40], [200, 10]], [[0, -1]]):
        with pytest.raises(ValueError):
            PilotConfig(filler_len_schedule=bad).training_filler_len(0)


def test_schedule_smoke_trains_on_the_schedule_and_evaluates_full_filler(tmp_path):
    smoke = PRE2C.schedule_smoke(tmp_path)
    assert smoke["pass"] and smoke["train_filler_lens"] == [0, 0, 40, 40] and smoke["eval_filler_lens"] == [40]
    assert smoke["result_label"].endswith("+DIAGNOSTIC-filler-len-schedule")


def test_grid_pilots_round_trip_through_the_manifest_equality_check():
    v1 = _load(ROOT / "modal-runners" / "modal-m4-sgm-p2d-diagnostics-grid.py", "v1")
    grid = json.loads((ROOT / "configs" / "m4_sgm_p2c_grid.json").read_text())
    cells = v1.expand(grid)
    assert len(cells) == 4 and {t for _r, t, _p in cells} == {"curriculum"}
    later_defaults = {"backbone": "tiny", "device": "cpu"}   # PilotConfig fields added after P2C (P2.5)
    for _rid, _tag, pilot in cells:
        written = json.loads(json.dumps(asdict(PilotConfig(**pilot))))
        assert {k: v for k, v in written.items() if k in pilot} == pilot      # P2C source wrote exactly this
        assert {k: v for k, v in written.items() if k not in pilot} == later_defaults
        assert pilot["filler_len_schedule"] == SCHEDULE and pilot["filler_len"] == 40 and pilot["filler_writes"] is True
    assert (grid["artifact_eval_seed_base"], grid["readings_seed_base"]) == (9_300_011, 9_500_011)


# ---------------- reading table ----------------

def test_q_reading_is_total_and_ordered():
    labels = (C.P2G.GAIN, C.P2G.LOSS, C.P2G.EXCLUDED, C.P2G.NEITHER)
    out = {k: C.q_reading(*k) for k in itertools.product(labels, (True, False), (True, False, None))}
    assert len(out) == 24 and all(isinstance(v, str) and v for v in out.values())
    supports = [k for k, v in out.items() if v.startswith("SUPPORTS")]
    assert supports == [(C.P2G.GAIN, True, True)]
    assert "unavailable" in out[(C.P2G.GAIN, True, None)]
    assert out[(C.P2G.GAIN, False, None)] == "reproducible gain without registered memory-use evidence"
    assert out[(C.P2G.EXCLUDED, True, True)].endswith(C.P2G.EXCLUDED)
    for bad in (("gain-ish", True, None), (C.P2G.GAIN, 1, None), (C.P2G.GAIN, True, "null")):
        with pytest.raises(SystemExit):
            C.q_reading(*bad)


# ---------------- launcher ----------------

def test_exact_cells_timeouts_and_reservation_under_the_approved_cap(runner):
    assert runner.P2C_CAP_USD == runner.PROPOSED_CAP_USD == 12.0
    cells, ledger, prov = runner.plan()
    assert {r for r, _p, _t in cells} == runner.P2C_IDS and len(cells) == 4
    assert ledger["cell_timeouts_s"] == {"curriculum-learned-n32-s0": 8773, "curriculum-learned-n32-s1": 6952,
                                         "curriculum-learned-n64-s0": 11797, "curriculum-learned-n64-s1": 10809}
    assert ledger["reserved_total_usd"] == pytest.approx(11.12716980, abs=1e-8) and ledger["admitted"]
    # P2C is closed: its runner stays pinned to the source it launched (later memsub changes,
    # e.g. P2.5, must not move it); the launch provenance records the same source.
    assert prov["memsub_source_sha256"] == runner.SOURCE_SHA == "09b05c16459c2caba55cddee651bd232e9de4ac5a87ce5ad11f3f18a8ab6d966"
    launch = ROOT / "plans/261005-0210-m4-sgm-p0-p2/runs/p2c-filler-curriculum-v1/launch_provenance.json"
    if launch.exists():
        assert json.loads(launch.read_text())["memsub_source_sha256"] == runner.SOURCE_SHA
    assert prov["artifact_eval_seed_base"] == 9_300_011 and prov["readings_seed_base_reserved"] == 9_500_011


@pytest.mark.parametrize("cap", [None, 11.0])
def test_missing_or_insufficient_cap_is_refused(runner, cap):
    with pytest.raises(ValueError, match="not admitted"):
        runner.plan(cap=cap)


def test_reserved_seed_is_never_a_training_seed(runner):
    assert runner.artifact_seed_ok(9_300_011) and not runner.artifact_seed_ok(9_500_011)
    assert runner.GROUP == "p2c-filler-curriculum-v1" and runner.APP_NAME == "memsub-m4-sgm-p2c"


# ---------------- inputs + readings ----------------

def test_inputs_index_binds_every_reused_checkpoint_and_fixture():
    index = json.loads(PRE2C.INPUTS.read_text())
    bound = PRE2C.PRE.validate_inputs(index)
    assert set(bound) == ({f"v2-n{n}-s{s}" for n in (32, 64) for s in (0, 1)}
                          | {f"filleroff-n{n}-s{s}" for n in (16, 32, 64) for s in (0, 1)})
    assert [e["filler_writes"] for e in index["parity"]["P-on"]] == [True] * 4
    assert [e["filler_writes"] for e in index["parity"]["P-off"]] == [False] * 4
    bad = json.loads(json.dumps(index))
    bad["reused"]["filleroff-n64-s1"]["trained_parameters_sha256"] = "0" * 64
    with pytest.raises(SystemExit, match="identity mismatch"):
        PRE2C.PRE.validate_inputs(bad)


def _toy(tmp: Path, name: str, **over):
    pilot = {"n_bindings": 4, "seed": 0, **over}
    rt, _be, head = build(PilotConfig(**pilot))
    d = tmp / name
    d.mkdir()
    save_trained_parameters(rt, head, d / "trained_parameters.safetensors")
    (d / "routing_telemetry.jsonl").write_text(json.dumps({"step": 0, "eval": {"accuracy": 0.1}}) + "\n"
                                               + json.dumps({"step": 0, "loss": 1.0}) + "\n")
    return d, {"pilot_config": pilot, "run_id": name, "modal_group": "toy"}


DEV_BASE = 777_000          # smoke evaluations never use the reserved readings seed values (codex 21390)


def test_readings_pipeline_smoke_on_dev_seeds_only(tmp_path, monkeypatch):
    rd = _load(ROOT / "scripts" / "sgm-p2c-readings.py", "p2c_readings")
    monkeypatch.setattr(rd.OBS, "FINAL_BATCHES", 1)
    monkeypatch.setattr(rd.P2D, "N_EPISODES", 16)
    monkeypatch.setattr(rd, "READINGS_BASE", DEV_BASE)
    seeds, real = [], rd.OBS.eval_rows
    monkeypatch.setattr(rd.OBS, "eval_rows", lambda b, h, p, seed, ivs, w: seeds.append(seed) or real(b, h, p, seed, ivs, w))
    models = {"v2": _toy(tmp_path, "v2"), "reference": _toy(tmp_path, "ref", filler_writes=False),
              "curriculum": _toy(tmp_path, "cur", filler_len_schedule=[[0, 0], [1, 40]])}
    per_seed = {s: rd.evaluate_seed(4, s, models, tmp_path) for s in (0, 1)}
    assert seeds == [DEV_BASE] * 3 + [DEV_BASE + 1] * 3
    assert set(per_seed[0]["corners"]) == {"v2", "reference", "curriculum"}
    assert per_seed[0]["curriculum_dev_curve_descriptive"] == [[0, 0.1]]
    out = rd.read_n(per_seed)
    assert out["flags"]["half"] in (True, False, None) and isinstance(out["reading"], str)


def test_readings_reject_training_artifacts_on_the_reserved_seed(tmp_path):
    rd = _load(ROOT / "scripts" / "sgm-p2c-readings.py", "p2c_readings_guard")
    assert rd.READINGS_BASE == 9_500_011
    (tmp_path / "split_manifest.json").write_text(json.dumps({"seeds": {"final_eval": 9_300_012}}))
    assert rd.artifact_seed_problem(tmp_path, {"final_eval_seed": 9_300_012}, 1) is None
    (tmp_path / "split_manifest.json").write_text(json.dumps({"seeds": {"final_eval": 9_500_012}}))
    assert rd.artifact_seed_problem(tmp_path, {"final_eval_seed": 9_500_012}, 1)


def test_prereg_file_is_bound_at_validation_and_in_the_identity(monkeypatch):
    # binding logic only: accept the live memsub (P2C itself is pinned to 09b05c16 and closed)
    monkeypatch.setattr(PRE2C.PRE, "p2g_source_sha", lambda: source_tree_sha256(ROOT / "memsub"))
    index = json.loads(PRE2C.INPUTS.read_text())
    ident = PRE2C.PRE.observer_identity()
    assert ident["prereg_sha256"] == index["prereg"]["sha256"] == hashlib.sha256(
        (ROOT / index["prereg"]["path"]).read_bytes()).hexdigest()
    bad = json.loads(json.dumps(index))
    bad["prereg"]["sha256"] = "0" * 64
    with pytest.raises(SystemExit, match="prereg"):
        PRE2C.PRE.validate_inputs(bad)
    drifted = {**ident, "prereg_sha256": "0" * 64}
    assert PRE2C.PRE.identity_drift(ident, drifted) == ["prereg_sha256"]
    monkeypatch.setattr(PRE2C.PRE, "observer_identity", lambda: drifted)
    with pytest.raises(SystemExit, match="identity changed"):
        PRE2C.PRE.finish_identity(ident, index)
