"""P2G fail-closed contracts (codex 21309/21312/21315): malformed intervals and
gate telemetry abort instead of reading or hanging; the registered readings
population is never used for training-artifact evaluation; executed
identities must be unchanged at the end of a run."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import signal
from pathlib import Path

import pytest

from memsub.sgm.synthetic_pilot import PilotConfig, build

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _load(ROOT / "scripts" / "sgm-p2g-decision-rules.py", "p2g_rules_fc")
OBS = _load(ROOT / "scripts" / "sgm-p2g-common-observer-evaluation.py", "p2g_obs_fc")
PRE = _load(ROOT / "scripts" / "sgm-p2g-preflight.py", "p2g_pre_fc")
GOOD = {"diff": .1, "lo": .05, "hi": .15, "n": 256}


@pytest.fixture
def alarm():
    """Turn a hang into a test failure (NaN tie loops used to spin forever)."""
    def _timeout(*_):
        raise TimeoutError("hung")
    old = signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(5)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old)


@pytest.mark.parametrize("pos,neg", [([math.nan], [0.1]), ([0.1], [math.nan]), ([math.inf], [0.1]), ([0.2, math.nan], [])])
def test_auroc_rejects_non_finite_without_hanging(alarm, pos, neg):
    with pytest.raises(SystemExit, match="non-finite"):
        R.auroc(pos, neg)


@pytest.mark.parametrize("bad", [
    {**GOOD, "hi": math.nan}, {**GOOD, "lo": -math.inf}, {**GOOD, "diff": math.nan},
    {**GOOD, "lo": .12},                       # lo > diff
    {**GOOD, "hi": .08},                       # diff > hi
    {**GOOD, "n": 255}, {**GOOD, "n": 256.0}, {**GOOD, "hi": True},
    {"diff": .1, "lo": .05, "hi": .15}, {**GOOD, "extra": 1}, None,
])
def test_classifier_and_half_status_reject_malformed_intervals(bad):
    with pytest.raises(SystemExit):
        R.classify({"0": GOOD, "1": bad})
    for oracle in (R.GAIN, R.NEITHER):         # validated even when half would be null
        with pytest.raises(SystemExit):
            R.half_status(oracle, {"0": GOOD, "1": bad})


def test_half_status_rejects_unknown_labels_and_missing_seeds():
    with pytest.raises(SystemExit):
        R.half_status("gain-ish", {"0": GOOD, "1": GOOD})
    with pytest.raises(SystemExit):
        R.classify({"0": GOOD})
    assert R.classify({"0": GOOD, "1": GOOD}) == R.GAIN


@pytest.fixture(scope="module")
def events():
    pcfg = PilotConfig(n_bindings=4, beta_bias_init=-3.0)
    _rt, backend, _head = build(pcfg)
    return OBS.gate_events(backend, pcfg, True), OBS.gate_events(backend, pcfg, False)


def _mutate(ev, fn):
    ev = copy.deepcopy(ev)
    fn(ev)
    return ev


@pytest.mark.parametrize("name,fn", [
    ("only L1h0", lambda e: [e.pop(k) for k in [(1, 1), (3, 0), (3, 1)]]),
    ("extra head", lambda e: e.__setitem__((2, 0), e[(1, 0)])),
    ("nan projected", lambda e: e[(3, 1)]["filler"]["projected"].__setitem__(5, math.nan)),
    ("nan effective", lambda e: (e[(1, 0)]["binding"]["effective"].__setitem__(0, math.nan),
                                 e[(1, 0)]["binding"]["applied"].__setitem__(0, math.nan))),
    ("beta > 1", lambda e: (e[(1, 0)]["binding"]["effective"].__setitem__(0, 1.5),
                            e[(1, 0)]["binding"]["applied"].__setitem__(0, 1.5))),
    ("partial applied", lambda e: e[(1, 0)]["filler"]["applied"].pop()),
    ("applied != effective", lambda e: e[(1, 0)]["filler"]["applied"].__setitem__(0, 0.0)),
    ("short projected", lambda e: e[(1, 1)]["binding"]["projected"].pop()),
    ("missing class", lambda e: e[(1, 1)].pop("binding")),
])
def test_gate_summary_rejects_malformed_telemetry(alarm, events, name, fn):
    with pytest.raises(SystemExit):
        OBS.gate_summary(_mutate(events[0], fn), 4)


def test_skipped_events_must_be_effective_zero(events):
    on, off = events
    assert OBS.gate_summary(off, 4)["rho_pooled_effective"] == 0.0     # registered skip semantics kept
    bad = _mutate(off, lambda e: e[(1, 0)]["filler"]["effective"].__setitem__(0, 0.2))
    with pytest.raises(SystemExit, match="effective beta 0"):
        OBS.gate_summary(bad, 4)
    assert OBS.gate_summary(on, 4)["auroc_defined_heads"] == 4


# ---------------- reserved readings population ----------------

def test_grid_and_inputs_reserve_the_readings_seed():
    grid = json.loads((ROOT / "configs" / "m4_sgm_p2g_grid.json").read_text())
    inputs = json.loads((ROOT / "configs" / "m4_sgm_p2g_inputs.json").read_text())
    assert "final_seed_base" not in grid and "final_seed_base" not in inputs
    for d in (grid, inputs):
        assert (d["artifact_eval_seed_base"], d["readings_seed_base"]) == (9_300_011, 9_400_011)


def test_runner_refuses_the_reserved_seed_for_training(monkeypatch, tmp_path):
    monkeypatch.chdir(ROOT)
    run = _load(ROOT / "modal-runners" / "modal-m4-sgm-p2g-nonpreemptible-spawn.py", "p2g_runner_fc")
    assert run.artifact_seed_ok(9_300_011) and not run.artifact_seed_ok(9_400_011)
    assert run.plan(cap=13.0)[2]["artifact_eval_seed_base"] == 9_300_011
    grid = json.loads((ROOT / run.GRID).read_text())
    grid["artifact_eval_seed_base"] = 9_400_011                       # tamper: train on the reserved seed
    g = tmp_path / "grid.json"
    g.write_text(json.dumps(grid))
    inputs = json.loads((ROOT / run.INPUTS).read_text())
    inputs["new_group"]["grid_sha256"] = hashlib.sha256(g.read_bytes()).hexdigest()
    i = tmp_path / "inputs.json"
    i.write_text(json.dumps(inputs))
    monkeypatch.setattr(run, "GRID", str(g))
    monkeypatch.setattr(run, "INPUTS", str(i))
    with pytest.raises(ValueError, match="seeds"):
        run.plan(cap=1e9)


def test_readings_reject_training_artifacts_evaluated_on_the_reserved_seed(tmp_path):
    rd = _load(ROOT / "scripts" / "sgm-p2g-readings.py", "p2g_readings_fc")
    def cell(seed_value):
        (tmp_path / "split_manifest.json").write_text(json.dumps({"seeds": {"final_eval": seed_value}}))
        return tmp_path
    assert rd.artifact_seed_problem(cell(9_300_012), {"final_eval_seed": 9_300_012}, 1) is None
    assert rd.artifact_seed_problem(cell(9_400_012), {"final_eval_seed": 9_400_012}, 1)
    assert rd.artifact_seed_problem(cell(9_400_012), {"final_eval_seed": 9_300_012}, 1)


# ---------------- executed identity ----------------

def test_any_executed_identity_change_fails_closed_but_git_head_alone_does_not(monkeypatch):
    start = PRE.observer_identity()
    assert "scripts/sgm-p2g-decision-rules.py" in start["analysis_sha256"]
    assert "modal-runners/modal-m4-sgm-p2g-nonpreemptible-spawn.py" in start["analysis_sha256"]
    assert PRE.identity_drift(start, {**start, "git_head": "x"}) == []
    changed = {**start, "analysis_sha256": {**start["analysis_sha256"], "scripts/sgm-p2g-decision-rules.py": "0"}}
    assert PRE.identity_drift(start, changed) == ["analysis_sha256"]
    for key in ("grid_sha256", "inputs_index_sha256", "memsub_source_sha256"):
        assert PRE.identity_drift(start, {**start, key: "0"}) == [key]
    monkeypatch.setattr(PRE, "observer_identity", lambda: changed)
    index = json.loads(PRE.INPUTS.read_text())
    with pytest.raises(SystemExit, match="identity changed"):
        PRE.finish_identity(start, index)
