"""P2.5 paid L40S profile runner (codex audit of 9e76787, R1–R3): server-side start
guard, usable-result validation, collect with missing/corrupt state and deadline
stop. Local only — fakes stand in for every Modal call."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def run(monkeypatch):
    monkeypatch.chdir(ROOT)
    spec = importlib.util.spec_from_file_location("p2p5_prof", ROOT / "modal-runners" / "modal-m4-sgm-p2p5-l40s-timing-profile.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeDict(dict):
    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self:
            return False
        self[k] = v
        return True


def test_guard_bounds_starts_and_deadline(run):
    d = FakeDict(deadline_epoch=100.0)
    assert run.guard_decision(d, 10.0) is None and run.guard_decision(d, 11.0) is None   # MAX_STARTS = 2
    assert run.guard_decision(d, 12.0) == "start allowance exhausted"
    assert "deadline" in run.guard_decision(FakeDict(deadline_epoch=100.0), 101.0)
    assert "deadline" in run.guard_decision(FakeDict(), 1.0)                            # unset deadline refuses


SHA = "f" * 64


def _profile(**over):
    cfg = lambda a, p: {"arm": a, "phase": p, "train_filler_len": 0 if p == 1 else 40, "updates": 10,
                        "warmup_s": [3.0, 2.0], "measured_s": [1.5] * 8,
                        "mean_measured_s_per_update": 1.5, "dev_eval_batch_s": 2.0,
                        "peak_train_memory_bytes": 2e10, "peak_memory_bytes": 2.1e10}
    env = {"python": "3.12.11", "torch": "2.7.1+cu126", "cuda": "12.6", "gpu": "NVIDIA L40S",
           "gpu_total_bytes": 4.8e10, "tf32_matmul": False}
    return {"status": "complete", "memsub_source_sha256": SHA, "environment": env,
            "contract": "full-gradient token-serial, fp32, TF32 off, batch 16, N32, seed 99",
            "configs": [cfg(a, p) for a, p in run_cfgs()], **over}


def run_cfgs():
    return [("learned", 1), ("learned", 2), ("memory_off", 1), ("memory_off", 2)]


@pytest.mark.parametrize("profile,exit_code,ok", [
    (_profile(), 0, True),
    (_profile(), 1, False),                                         # child error
    (_profile(), "outer_timeout", False),
    (_profile(status="stopped: OOM at learned phase 2"), 1, False),
    ({"status": "complete", "configs": []}, 0, False),              # complete report, empty matrix
    (None, 0, False),
])
def test_profile_usable_requires_exit_zero_and_the_full_finite_matrix(run, profile, exit_code, ok):
    assert run.profile_usable(profile, exit_code, SHA)[0] is ok


def _mut(fn):
    p = _profile()
    fn(p)
    return p


@pytest.mark.parametrize("bad", [
    _mut(lambda p: p["configs"][2].__setitem__("measured_s", [1.0] * 7)),
    _mut(lambda p: p["configs"][0]["measured_s"].__setitem__(3, float("nan"))),
    _mut(lambda p: p.__setitem__("memsub_source_sha256", "0" * 64)),          # wrong source (codex probe)
    _mut(lambda p: p.pop("environment")),                                      # missing environment
    _mut(lambda p: p["environment"].__setitem__("tf32_matmul", True)),
    _mut(lambda p: p["configs"][1].__setitem__("warmup_s", [])),               # missing warmups
    _mut(lambda p: p["configs"][1].__setitem__("mean_measured_s_per_update", float("nan"))),
    _mut(lambda p: p["configs"][1].__setitem__("mean_measured_s_per_update", 9.0)),   # inconsistent mean
    _mut(lambda p: p["configs"][3].__setitem__("peak_memory_bytes", float("nan"))),
    _mut(lambda p: p["environment"].__setitem__("torch", "2.7.1+cpu")),           # codex 21456 cases
    _mut(lambda p: p["environment"].__setitem__("cuda", "12.4")),
    _mut(lambda p: p["environment"].__setitem__("gpu", "NVIDIA A10")),
    _mut(lambda p: p.pop("contract")),
    _mut(lambda p: p.__setitem__("contract", "bf16 batch 8")),
    _mut(lambda p: p["configs"][1].__setitem__("train_filler_len", 0)),        # phase 2 must train at filler 40
])
def test_profile_usable_rejects_every_codex_probe(run, bad):
    assert not run.profile_usable(bad, 0, SHA)[0]


def test_reaper_stops_past_deadline_and_abandoned_deploys(run):
    d = FakeDict()
    assert run.reap_decision(d, 0.0) is None                                    # first tick, nothing spawned
    assert run.reap_decision(d, run.ABANDON_S - 1) is None
    assert "abandoned" in run.reap_decision(d, run.ABANDON_S + 1)
    d = FakeDict(deadline_epoch=500.0)
    assert run.reap_decision(d, 100.0) is None and run.reap_decision(d, 501.0) == "deadline passed"


def test_admission_refuses_late_starts_with_too_little_time(run):
    d = FakeDict(deadline_epoch=10_000.0)
    refused, remaining = run.admit(d, 10_000.0 - run.MIN_REMAINING_S + 1)
    assert refused and "before the deadline" in refused and remaining < run.MIN_REMAINING_S
    refused, remaining = run.admit(FakeDict(deadline_epoch=10_000.0), 0.0)
    assert refused is None and remaining == 10_000.0


def test_charge_bound_admits_under_the_approved_cap(run):
    b = run.charge_bound()
    assert b["admitted"] and b["reserved_total_usd"] <= 3.0 and b["max_starts"] == 2 and b["preemptible"]


def _root(run, tmp_path, monkeypatch, call=True, deadline=1e12):
    monkeypatch.setattr(run, "LOCAL_OUT", str(tmp_path))
    root = tmp_path / run.GROUP
    root.mkdir(parents=True)
    (root / "launch_provenance.json").write_text(json.dumps({"deployed_app_id": "ap-prof", "deadline_epoch": deadline,
                                                            "expected_identity": {"memsub": SHA}}))
    if call is True:
        (root / "call.json").write_text(json.dumps({"call_id": "fc-1"}))
    elif call == "corrupt":
        (root / "call.json").write_text("{not json")
    return root


def test_collect_pending_before_deadline_does_not_stop(run, tmp_path, monkeypatch):
    _root(run, tmp_path, monkeypatch)
    stops = []
    rep = run.collect(poller=lambda c: ("pending", None), stopper=lambda a: stops.append(a), fetch=lambda r: {}, now=0)
    assert rep["poll"] == "pending" and not stops


@pytest.mark.parametrize("call", [False, "corrupt"])
def test_untracked_call_still_reaches_the_bounded_stop(run, tmp_path, monkeypatch, call):
    _root(run, tmp_path, monkeypatch, call=call, deadline=100.0)
    stops, fetched = [], []
    rep = run.collect(poller=lambda c: pytest.fail("no call to poll"), stopper=lambda a: stops.append(a) or {"status": "stopped_verified"},
                      fetch=lambda r: fetched.append(r) or {"returncode": 0}, now=10_000.0)
    assert rep["poll"] == "untracked" and rep["past_deadline"] and stops == ["ap-prof"] and fetched


def test_terminal_result_stops_by_app_id_and_validates(run, tmp_path, monkeypatch):
    _root(run, tmp_path, monkeypatch)
    stops = []
    result = {"status": "profile_unusable", "child_exit": 1, "profile": {"status": "stopped: OOM", "configs": []}}
    rep = run.collect(poller=lambda c: ("result", result), stopper=lambda a: stops.append(a) or {}, fetch=lambda r: {}, now=0)
    assert stops == ["ap-prof"] and rep["usable"] is False


def test_reaper_stops_the_bound_app_first_and_ignores_optional_failures(run):
    order = []
    d = FakeDict(deadline_epoch=10.0, app_id="ap-bound", call_id="fc-1")
    def stopper(name, app_id):
        order.append(("stop", name, app_id))
    def canceller(call):
        order.append(("cancel", call))
        raise RuntimeError("stalled/failed cancel")
    out = run.reap_and_stop(d, 11.0, "the-app", stopper, canceller)
    assert out["stop"] and order[0] == ("stop", "the-app", "ap-bound") and order[1] == ("cancel", "fc-1")
    assert run.reap_and_stop(FakeDict(deadline_epoch=10.0), 5.0, "the-app", stopper)["stop"] is False


def test_stop_bound_app_refuses_a_different_live_app(run, monkeypatch):
    import modal
    monkeypatch.setattr(modal.App, "lookup", staticmethod(lambda name, environment_name=None: type("A", (), {"app_id": "ap-other"})()))
    with pytest.raises(RuntimeError, match="not stopping another app"):
        run.stop_bound_app("the-app", "ap-bound")


def test_child_timeout_is_recomputed_at_launch_and_never_passes_the_deadline(run):
    deadline = 10_000.0
    admitted_at = deadline - 900                                  # codex fixture: admitted with 900 s left,
    launch_at = admitted_at + 119                                 # 119 s of setup before the child
    t = run.child_timeout_s(deadline, launch_at)
    assert t is not None and launch_at + t <= deadline - 90 + 1e-9
    assert run.child_timeout_s(deadline, deadline - 600) is None  # too little left: child not launched
    assert run.child_timeout_s(None, 0.0) is None
    assert run.child_timeout_s(deadline, 0.0) == run.OUTER_TIMEOUT_S
