"""Amendment PK campaign runner, local only (fakes for Modal): one app per slot with unique identities, the
registered pairing, per-slot absolute deadline from the bound price file, admission bound, and the control-plane
app's own deadline (armed or abandoned)."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SLOTS = ("learned-n16", "learned-n32", "single_cell-n16", "single_cell-n32", "random_fixed-n16", "random_fixed-n32",
         "oracle-n32", "memory_off-n16", "memory_off-n32")


def load_slot(monkeypatch, slot):
    monkeypatch.setenv("M4_PK_SLOT", slot)
    monkeypatch.chdir(ROOT)
    spec = importlib.util.spec_from_file_location(f"slot_{slot}", ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeDict(dict):
    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self:
            return False
        self[k] = v
        return True


def test_unknown_slot_is_refused(monkeypatch):
    with pytest.raises(SystemExit):
        load_slot(monkeypatch, "learned-n64")


def test_each_slot_has_unique_identities_registered_pairing_and_deadline(monkeypatch):
    grid = json.loads((ROOT / "configs/m4_sgm_p2p5_grid.json").read_text())
    price = json.loads((ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk6/priced-estimate-v5.json").read_text())
    names, cells_all = set(), set()
    for slot in SLOTS:
        m = load_slot(monkeypatch, slot)
        names |= {m.APP_NAME, m.GUARD_DICT, m.ADMIT_DICT}
        cells = m.slot_cells(grid)
        assert sorted(p["seed"] for p in cells.values()) == [0, 1]
        assert len({(p["arm"], p["n_bindings"]) for p in cells.values()}) == 1
        cells_all |= set(cells)
        assert m.slot_deadline_s() == price["slots"][slot]["reserve_life_s"] > 0
    assert len(names) == 27 and len(cells_all) == 18                 # isolation + full registered universe


def test_slot_admission_bound_and_deadline(monkeypatch):
    m = load_slot(monkeypatch, "learned-n32")
    adm, guard = FakeDict(), FakeDict(deadline_epoch=100.0)
    assert [m.admit(adm, guard, float(i))[0] for i in range(5)] == [1, 2, 3, 4, None]
    assert "deadline" in m.admit(FakeDict(), FakeDict(deadline_epoch=100.0), 101.0)[1]
    assert "deadline" in m.admit(FakeDict(), FakeDict(), 1.0)[1]
    for bad in (float("nan"), float("inf"), True, -1.0):              # finite positive only (codex 21600 #4)
        assert m.admit(FakeDict(), FakeDict(deadline_epoch=bad), 1.0)[0] is None
    assert m.EVAL == {"final_batches": 16, "final_batch_size": 16, "final_seed_base": 9_300_011, "dev_seed": 4242,
                      "train_eval_seed_base": 555_001}                 # registered populations; never 9_600_011


def test_control_app_deadline_armed_or_abandoned(monkeypatch):
    monkeypatch.chdir(ROOT)
    spec = importlib.util.spec_from_file_location("ctl", ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py")
    ctl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctl)
    armed = FakeDict(app_id="ap-c", deadline_epoch=500.0)
    assert ctl.control_view(armed, 10.0, lambda: "ap-c")["deadline_epoch"] == 500.0
    never = FakeDict()
    v1 = ctl.control_view(never, 10.0, lambda: "ap-c")
    v2 = ctl.control_view(never, 99.0, lambda: "ap-c")                  # first tick is write-once
    assert v1["deadline_epoch"] == v2["deadline_epoch"] == 10.0 + ctl.ABANDON_S


# -- per-slot collect boundaries (fakes for Modal; real epoch-state records) --
def _evidence(m, tmp_path, monkeypatch, states):
    import json as _j
    from memsub.sgm import packed_slot_epoch_state as es
    monkeypatch.setattr(m, "LOCAL_OUT", str(tmp_path))
    root = tmp_path / m.GROUP / m.SLOT
    root.mkdir(parents=True)
    (root / "launch_provenance.json").write_text(_j.dumps({"deadline_epoch": 1000.0, "deployed_app_id": "ap-slot",
                                                           "expected_identity": {"memsub": "m"}}))
    cells = sorted(m.slot_cells(_j.loads((ROOT / m.GRID_FILE).read_text())))
    for cell, state in zip(cells, states):
        cdir = root / "volume-evidence" / m.SLOT / "cells" / cell
        rec = es.inherit(cdir, 1, [1], {"memsub": "m"}, 1500)
        if state == "COMPLETE":
            rec["chain"], rec["state"] = [{"epoch": 1, "g": 30, "step": 1500, "file": "x", "sha256": "y"}], es.TRAINED
            es.mark(rec, es.COMPLETE, outputs={"attempt": f"cells/{cell}/epoch-1/attempt-1", "files": {}})
        elif state == "FAILED":
            es.mark(rec, es.FAILED, reason="worker exit 3")
        es.write_record(cdir, rec)
    return root, cells


def _fakes(stops, verified=True, admission=None):
    return dict(stopper=lambda n, i: stops.append((n, i)), verifier=lambda n, i: verified,
                fetch=lambda r: {"returncode": 0}, export=lambda r: {"guard": {}, "admission": admission or {"start-1": 1.0}},
                validate=lambda *a, **k: None)


def test_collect_refuses_without_provenance(monkeypatch, tmp_path):
    m = load_slot(monkeypatch, "learned-n32")
    monkeypatch.setattr(m, "LOCAL_OUT", str(tmp_path))
    with pytest.raises(SystemExit, match="name-only"):
        m.collect(poller=lambda c: ("pending", None), **_fakes([]))


def test_collect_pending_before_deadline_does_not_stop(monkeypatch, tmp_path):
    import json as _j
    m = load_slot(monkeypatch, "learned-n32")
    root, _ = _evidence(m, tmp_path, monkeypatch, ["STARTED", "STARTED"])
    (root / "call.json").write_text(_j.dumps({"call_id": "fc-1"}))
    stops = []
    rep = m.collect(poller=lambda c: ("pending", None), now=500.0, **_fakes(stops))
    assert stops == [] and "final_shutdown" not in rep


@pytest.mark.parametrize("call, kind, now", [("fc-1", "result", 500.0), (None, None, 500.0), ("fc-1", "pending", 2000.0)])
def test_collect_stops_by_bound_id_and_reports_cells(monkeypatch, tmp_path, call, kind, now):
    import json as _j
    m = load_slot(monkeypatch, "learned-n32")
    root, cells = _evidence(m, tmp_path, monkeypatch, ["COMPLETE", "FAILED"])
    if call:
        (root / "call.json").write_text(_j.dumps({"call_id": call}))
    stops = []
    rep = m.collect(poller=lambda c: (kind, None), now=now, **_fakes(stops))
    assert stops == [(m.APP_NAME, "ap-slot")] and rep["final_shutdown"]["status"] == "stopped_verified"
    assert rep["cells"][cells[0]]["state"] == "COMPLETE" and rep["cells"][cells[0]]["validation"] == "valid"
    assert rep["cells"][cells[1]]["state"] == "FAILED" and "worker exit 3" in rep["cells"][cells[1]]["reason"]


def test_collect_marks_non_terminal_cells_lost_and_keeps_unresolved_shutdown(monkeypatch, tmp_path):
    import json as _j
    m = load_slot(monkeypatch, "learned-n32")
    root, cells = _evidence(m, tmp_path, monkeypatch, ["STARTED", "COMPLETE"])
    (root / "call.json").write_text(_j.dumps({"call_id": "fc-1"}))
    f = _fakes([], verified=False)
    f["stopper"] = lambda n, i: (_ for _ in ()).throw(RuntimeError("rpc"))
    f["validate"] = lambda *a, **k: "rows differ"
    rep = m.collect(poller=lambda c: ("failed", "boom"), now=500.0, **f)
    assert rep["final_shutdown"]["status"] == "shutdown_unresolved" and "stop_error" in rep["final_shutdown"]
    assert rep["cells"][cells[0]]["state"] == "LOST" and rep["cells"][cells[1]]["validation"] == "rows differ"


def test_collect_flags_unadmitted_epochs_invalid(monkeypatch, tmp_path):
    import json as _j
    m = load_slot(monkeypatch, "learned-n32")
    root, cells = _evidence(m, tmp_path, monkeypatch, ["COMPLETE", "COMPLETE"])
    (root / "call.json").write_text(_j.dumps({"call_id": "fc-1"}))
    rep = m.collect(poller=lambda c: ("result", None), now=500.0, **_fakes([], admission={"start-2": 1.0}))
    assert all(rep["cells"][c]["state"] == "INVALID" for c in cells)
