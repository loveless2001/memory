"""P2G common observer, scoped launcher and preflight bindings (local only;
no Modal calls, no training)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import torch

from memsub.sgm.synthetic_pilot import PilotConfig, build
from memsub.sgm.synthetic_pilot_run import save_trained_parameters

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "modal-runners" / "modal-m4-sgm-p2g-nonpreemptible-spawn.py"
CODEX_TIMEOUTS = {"gateclosed-learned-n16-s0": 6106, "gateclosed-learned-n16-s1": 4640,
                  "gateclosed-learned-n32-s0": 8773, "gateclosed-learned-n32-s1": 6952,
                  "filleroff-learned-n32-s0": 8773, "filleroff-learned-n32-s1": 6952}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OBS = _load(ROOT / "scripts" / "sgm-p2g-common-observer-evaluation.py", "p2g_obs")


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.chdir(ROOT)
    return _load(RUNNER, "p2g_runner")


# ---------------- observer ----------------

def test_checkpoint_load_keeps_the_learned_beta_bias(tmp_path):
    pilot = {**json.loads((ROOT / "configs" / "m4_sgm_p2g_grid.json").read_text())["base"],
             "n_bindings": 16, "seed": 0, "beta_bias_init": -3.0}
    rt, _be, head = build(PilotConfig(**pilot))
    with torch.no_grad():
        for a in rt.adapters.values():
            a.beta_proj.bias.fill_(0.7)                      # "learned" value != init knob
    save_trained_parameters(rt, head, tmp_path / "p.safetensors")
    _pcfg, backend, _h = OBS.load_checkpoint(pilot, tmp_path / "p.safetensors")
    assert all((a.beta_proj.bias == 0.7).all() for a in backend.runtime.adapters.values())


@pytest.mark.parametrize("writes", [True, False])
def test_gate_events_population_and_skipped_writes(writes):
    pcfg = PilotConfig(n_bindings=4, beta_bias_init=-3.0)
    _rt, backend, _head = build(pcfg)
    ev = OBS.gate_events(backend, pcfg, writes)
    assert len(ev) == 4                                       # layers {1,3} x heads {0,1}
    for cls in ev.values():
        assert len(cls["filler"]["effective"]) == 64 * 40 and len(cls["binding"]["effective"]) == 64 * 8
        assert len(cls["filler"]["applied"]) == (64 * 40 if writes else 0)
    s = OBS.gate_summary(ev, 4)
    if writes:
        assert 0 < s["rho_pooled_effective"] and s["auroc_defined_heads"] == 4
    else:                                                     # skipped filler writes: effective 0, AUROC undefined
        assert s["rho_pooled_effective"] == 0.0 and s["auroc_defined_heads"] == 0
        assert s["auroc_mean_defined"] is None and all(h["auroc_applied"] is None for h in s["per_head"].values())


def test_gate_summary_rejects_a_wrong_event_population():
    pcfg = PilotConfig(n_bindings=4)
    _rt, backend, _head = build(pcfg)
    with pytest.raises(SystemExit, match="events"):
        OBS.gate_summary(OBS.gate_events(backend, pcfg, True), 5)


# ---------------- launcher ----------------

def test_exact_cells_timeouts_and_reservation_under_the_proposed_cap(runner):
    cells, ledger, prov = runner.plan(cap=runner.PROPOSED_CAP_USD)
    assert {r for r, _p, _t in cells} == runner.P2G_IDS == set(CODEX_TIMEOUTS)
    assert ledger["cell_timeouts_s"] == CODEX_TIMEOUTS
    assert ledger["reserved_total_usd"] == pytest.approx(12.32978160, abs=1e-8) and ledger["admitted"]
    assert prov["memsub_source_sha256"] == runner.SOURCE_SHA and prov["nonpreemptible"] is True


@pytest.mark.parametrize("cap", [None, 12.0])
def test_missing_or_insufficient_cap_is_refused(runner, cap):
    with pytest.raises(ValueError, match="not admitted"):
        runner.plan(cap=cap)


def test_bound_cap_is_the_user_approved_13_and_admits_exactly_the_reservation(runner):
    assert runner.P2G_CAP_USD == runner.PROPOSED_CAP_USD == 13.0      # #gravity 21341/21342
    _cells, ledger, _prov = runner.plan()                              # spawn() path, default cap
    assert ledger["cap_usd"] == 13.0 and ledger["admitted"]
    assert ledger["reserved_total_usd"] == pytest.approx(12.32978160, abs=1e-8)


def test_runner_pins_the_launched_p2g_source(runner):
    """P2G is closed: its runner stays pinned to the source it launched (later memsub
    changes, e.g. P2C, must not move it); the launch provenance records the same."""
    assert runner.SOURCE_SHA == "5c3b5420152de933a04264604fdc1fb6312a24609b631ad9fd0c614755bde6a2"
    launch = ROOT / "plans/261005-0210-m4-sgm-p0-p2/runs/p2g-selective-write-v1/launch_provenance.json"
    if launch.exists():
        assert json.loads(launch.read_text())["memsub_source_sha256"] == runner.SOURCE_SHA


def test_extra_cell_in_the_grid_is_refused(runner, tmp_path, monkeypatch):
    grid = json.loads((ROOT / runner.GRID).read_text())
    grid["blocks"][1]["n_bindings"] = [32, 64]
    bad = tmp_path / "grid.json"
    bad.write_text(json.dumps(grid))
    monkeypatch.setattr(runner, "GRID", str(bad))
    with pytest.raises(ValueError, match="does not bind"):    # inputs index pins the grid hash
        runner.plan(cap=1e9)


def _root(runner, tmp_path, monkeypatch, calls):
    monkeypatch.setattr(runner, "LOCAL_OUT", str(tmp_path))
    root = tmp_path / runner.GROUP
    root.mkdir(parents=True)
    (root / "grid.json").write_text((ROOT / runner.GRID).read_text())
    (root / "launch_provenance.json").write_text(json.dumps({"deployed_app_id": "ap-p2g"}))
    (root / "calls.json").write_text(json.dumps(calls))
    return root


def _fake_v1(monkeypatch, runner):
    v1, seen = runner.v1_runner(), []
    monkeypatch.setattr(v1, "stop_app", lambda app_id: seen.append(("stop", app_id)))
    monkeypatch.setattr(v1, "verify_stopped", lambda app_id: seen.append(("verify", app_id)) or {"verified": True})
    monkeypatch.setattr(runner, "v1_runner", lambda: v1)
    return seen


def test_collect_pending_is_not_terminal_and_terminal_stops_the_spawn_app(runner, tmp_path, monkeypatch):
    seen = _fake_v1(monkeypatch, runner)
    _root(runner, tmp_path, monkeypatch, {r: f"c-{r}" for r in runner.P2G_IDS})
    rep = runner.collect(poller=lambda cid: ("pending", None), claims=lambda r: {})
    assert rep["terminal"] is False and not seen
    rep = runner.collect(poller=lambda cid: ("result", {"run_id": cid[2:], "status": "replay_refused"}),
                         claims=lambda r: {})
    assert rep["terminal"] and rep["final_shutdown"]["status"] == "stopped_verified"
    assert ("stop", "ap-p2g") in seen


def test_collect_rejects_unregistered_calls(runner, tmp_path, monkeypatch):
    _fake_v1(monkeypatch, runner)
    _root(runner, tmp_path, monkeypatch, {**{r: f"c-{r}" for r in runner.P2G_IDS}, "rogue": "c"})
    with pytest.raises(SystemExit, match="unregistered"):
        runner.collect(poller=lambda cid: ("pending", None), claims=lambda r: {})


# ---------------- preflight bindings ----------------

def test_inputs_index_binds_reused_checkpoints_and_parity_references():
    pre = _load(ROOT / "scripts" / "sgm-p2g-preflight.py", "p2g_pre")
    index = json.loads(pre.INPUTS.read_text())
    bound = pre.validate_inputs(index)
    assert set(bound) == {f"v2-n{n}-s{s}" for n in (16, 32) for s in (0, 1)} | {"filleroff-n16-s0", "filleroff-n16-s1"}
    assert [e["filler_writes"] for e in index["parity"]["P-on"]] == [True] * 4
    assert [e["filler_writes"] for e in index["parity"]["P-off"]] == [False] * 2
    tampered = json.loads(json.dumps(index))
    tampered["reused"]["v2-n16-s0"]["trained_parameters_sha256"] = "0" * 64
    with pytest.raises(SystemExit, match="identity mismatch"):
        pre.validate_inputs(tampered)
    tampered = json.loads(json.dumps(index))
    tampered["parity"]["P-off"][0]["reference_sha256"] = "0" * 64
    with pytest.raises(SystemExit, match="reference file hash"):
        pre.validate_inputs(tampered)
