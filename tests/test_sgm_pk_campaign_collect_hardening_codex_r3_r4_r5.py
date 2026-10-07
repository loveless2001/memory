"""Regression tests for codex 21617 R3/R4/R5 (Gate-3 audit of f8d8592), local only with Modal faked:
R3 no collector path reaches a name-only stop (null/empty/missing/non-str bound id, wrong slot, replaced live app —
exercised through the REAL shared `stop_bound_app`); R4 `stopped_verified` needs stopped/unlisted + zero tasks + no
containers, with raw rows / errors kept; R5 one malformed cell is contained as INVALID with its cause, shutdown
evidence is durable, and a failed fetch / Dict export never validates older local evidence."""

import importlib.util
import json
import shutil
import sys
import types
from pathlib import Path

import pytest

from test_sgm_pk_campaign_slot_runner_and_control_app import _evidence, _fakes, load_slot

ROOT = Path(__file__).resolve().parents[1]


def _mod(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "modal-runners" / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


CP = _mod("cp_r3", "modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py")
SHARED = _mod("shared_r3", "modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py")


def _never(*a, **k):
    raise AssertionError("must not be called before provenance is validated")


@pytest.mark.parametrize("app_id", [None, "", "   ", 5, "MISSING"])
def test_slot_collect_refuses_without_a_nonempty_bound_id_before_any_side_effect(monkeypatch, tmp_path, app_id):
    m = load_slot(monkeypatch, "learned-n32")
    root, _ = _evidence(m, tmp_path, monkeypatch, ["COMPLETE", "COMPLETE"], app_id=app_id)
    if app_id == "MISSING":
        prov = json.loads((root / "launch_provenance.json").read_text())
        del prov["deployed_app_id"]
        (root / "launch_provenance.json").write_text(json.dumps(prov))
    (root / "call.json").write_text(json.dumps({"call_id": "fc-1"}))
    with pytest.raises(SystemExit, match="no bound app id"):
        m.collect(poller=_never, stopper=_never, verifier=_never, fetch=_never, export=_never, now=5000.0)
    assert not (root / "collect_status.json").exists()


def test_slot_collect_refuses_provenance_of_another_slot(monkeypatch, tmp_path):
    m = load_slot(monkeypatch, "learned-n32")
    root, _ = _evidence(m, tmp_path, monkeypatch, ["COMPLETE", "COMPLETE"])
    prov = json.loads((root / "launch_provenance.json").read_text())
    (root / "launch_provenance.json").write_text(json.dumps({**prov, "slot": "oracle-n32"}))
    with pytest.raises(SystemExit, match="not 'learned-n32'"):
        m.collect(poller=_never, stopper=_never, verifier=_never, fetch=_never, export=_never, now=5000.0)


def _fake_modal(monkeypatch, live_id):
    calls = {"lookup": 0, "stop": []}

    def lookup(name, environment_name=None):
        calls["lookup"] += 1
        return types.SimpleNamespace(app_id=live_id)
    import modal
    import modal.experimental
    monkeypatch.setattr(modal.App, "lookup", staticmethod(lookup))
    monkeypatch.setattr(modal.experimental, "stop_app", lambda name, environment_name=None: calls["stop"].append(name))
    return calls


def test_strict_stop_through_the_real_shared_helper(monkeypatch):
    calls = _fake_modal(monkeypatch, live_id="ap-bound")
    for bad in (None, "", "  "):                              # the helper would stop by NAME for None
        with pytest.raises(ValueError, match="name-only"):
            CP.strict_stop(SHARED.stop_bound_app, "app-x", bad)
    assert calls == {"lookup": 0, "stop": []}
    CP.strict_stop(SHARED.stop_bound_app, "app-x", "ap-bound")
    assert calls == {"lookup": 1, "stop": ["app-x"]}
    calls = _fake_modal(monkeypatch, live_id="ap-later-deploy")  # replaced live app under the same name
    with pytest.raises(RuntimeError, match="not stopping another app"):
        CP.strict_stop(SHARED.stop_bound_app, "app-x", "ap-bound")
    assert calls["stop"] == []


def test_readings_collect_refuses_null_bound_id(monkeypatch, tmp_path):
    monkeypatch.chdir(ROOT)
    r = _mod("rr_r3", "modal-m4-sgm-p2p5-pk-campaign-readings-runner.py")
    monkeypatch.setattr(r, "LOCAL_OUT", str(tmp_path))
    root = tmp_path / r.GROUP / "readings"
    root.mkdir(parents=True)
    (root / "launch_provenance.json").write_text(json.dumps({"deadline_epoch": 100.0, "deployed_app_id": None,
                                                             "expected_identity": {"memsub": "m"}}))
    with pytest.raises(SystemExit, match="no bound app id"):
        r.collect(poller=_never, stopper=_never, verifier=_never, fetch=_never, now=5000.0)


@pytest.mark.parametrize("apps, conts, ok", [
    ([], [], True),                                                                         # unlisted, nothing left
    ([{"app_id": "ap-1", "state": "stopped", "tasks": "0"}], [], True),
    ([{"app_id": "ap-1", "state": "stopped", "tasks": "7"}], [], False),                   # codex probe
    ([{"app_id": "ap-1", "state": "stopped", "tasks": "0"}], [{"app_id": "ap-1", "container_id": "ta-1"}], False),
    ([{"app_id": "ap-1", "state": "deployed", "tasks": "0"}], [], False),
    ([{"app_id": "ap-2", "state": "deployed", "tasks": "3"}], [{"app_id": "ap-2"}], True),  # another app only
])
def test_verify_stopped_requires_zero_tasks_and_no_containers(apps, conts, ok):
    v = CP.verify_stopped("ap-1", lambda args: apps if args[0] == "app" else conts)
    assert v["verified"] is ok and all(r["app_id"] == "ap-1" for r in v["app_rows"] + v["container_rows"])


@pytest.mark.parametrize("modal_json", [lambda a: (_ for _ in ()).throw(RuntimeError("cli down")), lambda a: {"rows": 1}])
def test_verify_stopped_errors_stay_unverified(modal_json):
    v = CP.verify_stopped("ap-1", modal_json)
    assert v["verified"] is False and "verify_error" in v


def test_collect_with_live_tasks_is_shutdown_unresolved(monkeypatch, tmp_path):
    m = load_slot(monkeypatch, "learned-n32")
    root, _ = _evidence(m, tmp_path, monkeypatch, ["COMPLETE", "COMPLETE"])
    f = _fakes([], remote=tmp_path / "remote")
    f["verifier"] = lambda app_id: CP.verify_stopped(
        app_id, lambda a: [{"app_id": app_id, "state": "stopped", "tasks": "7"}] if a[0] == "app" else [])
    rep = m.collect(poller=lambda c: ("result", None), now=500.0, **f)
    assert rep["final_shutdown"]["status"] == "shutdown_unresolved"
    assert rep["final_shutdown"]["verification"]["app_rows"][0]["tasks"] == "7"


def test_malformed_record_is_contained_per_cell(monkeypatch, tmp_path):
    m = load_slot(monkeypatch, "learned-n32")
    root, cells = _evidence(m, tmp_path, monkeypatch, ["COMPLETE", "COMPLETE"])
    for st in (tmp_path / "remote" / m.SLOT / "cells" / cells[0]).rglob("state.json"):
        st.write_text("{not json")
    rep = m.collect(poller=lambda c: ("result", None), now=500.0, **_fakes([], remote=tmp_path / "remote"))
    assert rep["cells"][cells[0]]["state"] == "INVALID" and "malformed" in rep["cells"][cells[0]]["problem"]
    assert rep["cells"][cells[1]]["state"] == "COMPLETE" and rep["final_shutdown"]["status"] == "stopped_verified"
    assert json.loads((root / "collect_status.json").read_text())["cells"][cells[1]]["state"] == "COMPLETE"


def test_failed_fetch_never_validates_older_local_evidence(monkeypatch, tmp_path):
    m = load_slot(monkeypatch, "learned-n32")
    root, cells = _evidence(m, tmp_path, monkeypatch, ["COMPLETE", "COMPLETE"])
    shutil.copytree(tmp_path / "remote", root / "volume-evidence" / "collect-1")    # an older good snapshot
    rep = m.collect(poller=lambda c: ("result", None), now=500.0, **_fakes([], remote=tmp_path / "remote", rc=1))
    assert all(rep["cells"][c]["state"] == "UNAVAILABLE" for c in cells)
    assert (root / "volume-evidence" / "collect-2").is_dir() and "evidence_dir" not in rep
    status = json.loads((root / "collect_status.json").read_text())
    assert status["final_shutdown"]["status"] == "stopped_verified"


def test_failed_dict_export_leaves_cells_unavailable(monkeypatch, tmp_path):
    m = load_slot(monkeypatch, "learned-n32")
    _root, cells = _evidence(m, tmp_path, monkeypatch, ["COMPLETE", "COMPLETE"])
    f = _fakes([], remote=tmp_path / "remote")
    f["export"] = lambda r: (_ for _ in ()).throw(RuntimeError("dict rpc"))
    rep = m.collect(poller=lambda c: ("result", None), now=500.0, **f)
    assert all(rep["cells"][c]["state"] == "UNAVAILABLE" for c in cells) and "dict rpc" in rep["dicts_error"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
