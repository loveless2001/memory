"""Amendment PK exactly-once readings app, local only (fakes for Modal): single admitted start / re-entry refusal,
spawn preconditions over every slot, admission-name coupling with the slot apps, collect without provenance."""

import importlib.util
import json
from pathlib import Path

import pytest
from conftest import pk_runner_uses_current_memsub_manifest

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

    def keys(self):                                  # modal 1.x Dict.keys() is a generator: len() raises (attempt 2)
        return (k for k in dict.keys(self))


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
    with pytest.raises(SystemExit, match="refusing"):
        r.collect(poller=lambda c: ("pending", None), stopper=None, verifier=None, fetch=None)
    root = tmp_path / r.GROUP / "readings"
    root.mkdir(parents=True)
    (root / "launch_provenance.json").write_text(json.dumps({"deadline_epoch": 100.0, "deployed_app_id": "ap-r",
                                                             "expected_identity": {"memsub": "m"}}))
    (root / "call.json").write_text(json.dumps({"call_id": "fc-r"}))
    stops = []

    def fetch(dest):
        dest.mkdir(parents=True)
        return {"readings-v1": 0, "readings-v1.exit.json": 0}
    rep = r.collect(poller=lambda c: ("result", {"status": "read"}), stopper=lambda n, i, env: stops.append((n, i)),
                    verifier=lambda app_id: {"verified": True}, fetch=fetch, now=50.0)
    assert stops == [(r.APP_NAME, "ap-r")] and rep["final_shutdown"]["status"] == "stopped_verified"
    assert rep["evidence_complete"] is True
    rep2 = r.collect(poller=lambda c: ("result", {"status": "read"}), stopper=lambda n, i, env: None,
                     verifier=lambda app_id: {"verified": False, "verify_error": "x"},
                     fetch=lambda d: (d.mkdir(parents=True), {"readings-v1": 1})[1], now=50.0)
    assert rep2["final_shutdown"]["status"] == "shutdown_unresolved" and rep2["evidence_complete"] is False
    assert rep2["evidence_dir"].endswith("collect-2")


class RaisingKeysDict(FakeDict):
    def keys(self):
        raise RuntimeError("dict rpc down")


GUARDS = {"empty": FakeDict, "used": lambda: FakeDict(app_id="ap-old"), "none-key": lambda: FakeDict({None: 1}),
          "false-key": lambda: FakeDict({False: 0}), "empty-str-key": lambda: FakeDict({"": ""}),
          "keys-error": RaisingKeysDict}


@pytest.mark.parametrize("kind", list(GUARDS))
def test_spawn_guard_check_handles_modal_generator_keys(monkeypatch, tmp_path, kind):
    """Launch attempt 2 died on `len(guard.keys())` (modal Dict.keys() is a generator): an EMPTY guard must proceed
    to exactly one spawn; a guard with ANY key (incl. None / False / "") or a keys() error must stop before any
    root, provenance, registration or call (codex 21645)."""
    import types
    r = _load(monkeypatch, "modal-m4-sgm-p2p5-pk-campaign-readings-runner.py", "rr_gen")
    pk_runner_uses_current_memsub_manifest(monkeypatch, r, tmp_path / "current-memsub-manifest.json")
    price = r.file_sha(r.PRICE_FILE)
    dicts = {r.CONTROL_GUARD_DICT: FakeDict(app_id="ap-c", price_sha256=price, deadline_epoch=4e9),
             r.GUARD_DICT: GUARDS[kind]()}
    calls = []
    monkeypatch.setattr(r, "modal", types.SimpleNamespace(
        Dict=types.SimpleNamespace(from_name=lambda n, **k: dicts.setdefault(n, FakeDict())),
        App=types.SimpleNamespace(lookup=lambda n, **k: types.SimpleNamespace(app_id="ap-c" if n == r.CONTROL_APP_NAME else "ap-r")),
        Function=types.SimpleNamespace(from_name=lambda *a: types.SimpleNamespace(
            spawn=lambda *a: calls.append(a) or types.SimpleNamespace(object_id="fc-r")))))
    monkeypatch.setattr(r, "slots_ready", lambda local, amendment=None: None)
    monkeypatch.setattr(r, "app_state", lambda i: "deployed")
    monkeypatch.setattr(r.subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout=""))
    monkeypatch.setattr(r, "LOCAL_OUT", str(tmp_path))
    if kind != "empty":
        with pytest.raises(RuntimeError if kind == "keys-error" else SystemExit,
                           match="dict rpc down" if kind == "keys-error" else "readings guard already used"):
            r.spawn()
        assert calls == [] and not (tmp_path / r.GROUP / "readings").exists()
        assert r.APP_NAME not in dicts.get(r.CONTROL_REGISTRY_DICT, {})
    else:
        r.spawn()
        assert len(calls) == 1 and dicts[r.GUARD_DICT]["app_id"] == "ap-r"
        assert dicts[r.CONTROL_REGISTRY_DICT][r.APP_NAME]["app_id"] == "ap-r"
