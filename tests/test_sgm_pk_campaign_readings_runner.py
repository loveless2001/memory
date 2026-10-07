"""Amendment PK exactly-once readings app, local only (fakes for Modal): single admitted start / re-entry refusal,
spawn preconditions over every slot, admission-name coupling with the slot apps, collect without provenance."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(monkeypatch, name, mod, slot=None):
    if slot:
        monkeypatch.setenv("M4_PK_SLOT", slot)
    monkeypatch.chdir(ROOT)
    spec = importlib.util.spec_from_file_location(mod, ROOT / "modal-runners" / name)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class FakeDict(dict):
    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self:
            return False
        self[k] = v
        return True


def test_single_admitted_start_and_re_entry_refused(monkeypatch):
    r = _load(monkeypatch, "modal-m4-sgm-p2p5-pk-campaign-readings-runner.py", "rr")
    adm = FakeDict()
    assert r.admit_once(adm, FakeDict(deadline_epoch=100.0), 1.0) is None
    assert "re-entry refused" in r.admit_once(adm, FakeDict(deadline_epoch=100.0), 2.0)
    for bad in (None, float("nan"), float("inf"), True, -1.0):
        assert "deadline" in r.admit_once(FakeDict(), FakeDict(deadline_epoch=bad), 1.0)
    assert "deadline" in r.admit_once(FakeDict(), FakeDict(deadline_epoch=100.0), 101.0)


def test_admission_dict_names_match_the_slot_apps(monkeypatch):
    r = _load(monkeypatch, "modal-m4-sgm-p2p5-pk-campaign-readings-runner.py", "rr2")
    for s in r.SLOTS:
        m = _load(monkeypatch, "modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py", f"slot_{s}", slot=s)
        assert m.ADMIT_DICT == f"memsub-m4-sgm-p2p5-pk-campaign-{s.replace('_', '')}-admission"


def test_spawn_preconditions_require_every_slot_verified_and_valid(monkeypatch, tmp_path):
    r = _load(monkeypatch, "modal-m4-sgm-p2p5-pk-campaign-readings-runner.py", "rr3")
    good = {"final_shutdown": {"status": "stopped_verified"},
            "cells": {"a": {"state": "COMPLETE", "validation": "valid"}, "b": {"state": "COMPLETE", "validation": "valid"}}}
    for s in r.SLOTS:
        (tmp_path / s).mkdir()
        (tmp_path / s / "collect_status.json").write_text(json.dumps(good))
    assert r.slots_ready(tmp_path) is None
    bad = json.loads(json.dumps(good))
    bad["cells"]["b"] = {"state": "LOST"}
    (tmp_path / "oracle-n32" / "collect_status.json").write_text(json.dumps(bad))
    assert "oracle-n32" in r.slots_ready(tmp_path)
    (tmp_path / "oracle-n32" / "collect_status.json").write_text(json.dumps({**good, "final_shutdown": {"status": "shutdown_unresolved"}}))
    assert "stop not verified" in r.slots_ready(tmp_path)
    (tmp_path / "learned-n16" / "collect_status.json").unlink()
    assert "not collected" in r.slots_ready(tmp_path)


def test_collect_refuses_without_provenance_and_stops_by_bound_id(monkeypatch, tmp_path):
    r = _load(monkeypatch, "modal-m4-sgm-p2p5-pk-campaign-readings-runner.py", "rr4")
    monkeypatch.setattr(r, "LOCAL_OUT", str(tmp_path))
    with pytest.raises(SystemExit, match="name-only"):
        r.collect(poller=lambda c: ("pending", None), stopper=None, verifier=None, fetch=None)
    root = tmp_path / r.GROUP / "readings"
    root.mkdir(parents=True)
    (root / "launch_provenance.json").write_text(json.dumps({"deadline_epoch": 100.0, "deployed_app_id": "ap-r"}))
    (root / "call.json").write_text(json.dumps({"call_id": "fc-r"}))
    stops = []
    rep = r.collect(poller=lambda c: ("result", {"status": "read"}), stopper=lambda n, i: stops.append((n, i)),
                    verifier=lambda n, i: True, fetch=lambda root: {"ok": 0}, now=50.0)
    assert stops == [(r.APP_NAME, "ap-r")] and rep["final_shutdown"]["status"] == "stopped_verified"
