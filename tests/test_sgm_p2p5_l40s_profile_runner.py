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


def _profile(**over):
    cfg = lambda a, p: {"arm": a, "phase": p, "updates": 10, "measured_s": [1.5] * 8, "dev_eval_batch_s": 2.0,
                        "peak_train_memory_bytes": 2e10}
    return {"status": "complete", "configs": [cfg(a, p) for a, p in run_cfgs()], **over}


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
    assert run.profile_usable(profile, exit_code)[0] is ok


def test_profile_usable_rejects_nonfinite_or_short_timings(run):
    bad = _profile()
    bad["configs"][2]["measured_s"] = [1.0] * 7
    assert not run.profile_usable(bad, 0)[0]
    bad = _profile()
    bad["configs"][0]["measured_s"][3] = float("nan")
    assert not run.profile_usable(bad, 0)[0]


def test_charge_bound_admits_under_the_approved_cap(run):
    b = run.charge_bound()
    assert b["admitted"] and b["reserved_total_usd"] <= 3.0 and b["max_starts"] == 2 and b["preemptible"]


def _root(run, tmp_path, monkeypatch, call=True, deadline=1e12):
    monkeypatch.setattr(run, "LOCAL_OUT", str(tmp_path))
    root = tmp_path / run.GROUP
    root.mkdir(parents=True)
    (root / "launch_provenance.json").write_text(json.dumps({"deployed_app_id": "ap-prof", "deadline_epoch": deadline}))
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
