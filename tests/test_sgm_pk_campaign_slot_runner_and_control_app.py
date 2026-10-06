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
    price = json.loads((ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk6/priced-estimate-v4.json").read_text())
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
    assert m.EVAL == {"final_batches": 16, "final_batch_size": 16, "final_seed_base": 9_300_011, "dev_seed": 4242,
                      "train_eval_seed_base": 555_001}                 # registered populations; never 9_600_011


def test_control_app_deadline_armed_or_abandoned(monkeypatch):
    monkeypatch.chdir(ROOT)
    spec = importlib.util.spec_from_file_location("ctl", ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py")
    ctl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctl)
    armed = FakeDict(app_id="ap-c", deadline_epoch=500.0)
    assert ctl.control_view(armed, 10.0)["deadline_epoch"] == 500.0
    never = FakeDict()
    v1 = ctl.control_view(never, 10.0)
    v2 = ctl.control_view(never, 99.0)                                # first tick is write-once
    assert v1["deadline_epoch"] == v2["deadline_epoch"] == 10.0 + ctl.ABANDON_S
