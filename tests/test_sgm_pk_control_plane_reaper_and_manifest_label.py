"""Amendment PK campaign control-plane reaper (one schedule for all apps; codex 21596) and the
manifest backbone-label fix (codex 21585)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cp", ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py")
cp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cp)


class FakeDict(dict):
    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self:
            return False
        self[k] = v
        return True


def test_only_overdue_apps_are_stopped_by_their_bound_ids():
    reg = {"slot-a": {"app_id": "ap-a", "deadline_epoch": 100.0}, "slot-b": {"app_id": "ap-b", "deadline_epoch": 500.0},
           "readings": {"app_id": "ap-r", "deadline_epoch": 50.0}}
    calls = []
    out = cp.control_tick(reg, 200.0, lambda n, i: calls.append((n, i)))
    assert calls == [("readings", "ap-r"), ("slot-a", "ap-a")]          # slot-b untouched (isolation)
    assert out["slot-b"] == "not due"


def test_malformed_entries_fail_closed_and_errors_are_contained():
    reg = {"x": {"app_id": "ap-x"}, "y": {"deadline_epoch": 1e12}, "z": "garbage",
           "w": {"app_id": "ap-w", "deadline_epoch": 1.0}}
    calls = []

    def stopper(n, i):
        calls.append(n)
        if n == "w":
            raise RuntimeError("already stopped")
    out = cp.control_tick(reg, 10.0, stopper)
    assert sorted(calls) == ["w", "x", "y", "z"] and out["w"].startswith("stop error")


def test_registration_is_write_once_and_never_reset():
    store = FakeDict()
    assert cp.register(store, "slot-a", "ap-a", 100.0)
    assert not cp.register(store, "slot-a", "ap-other", 9e9)            # deadline can never be extended
    assert store["slot-a"] == {"app_id": "ap-a", "deadline_epoch": 100.0}


def test_control_app_self_stops_only_after_its_own_deadline():
    reg = {"slot-a": {"app_id": "ap-a", "deadline_epoch": 100.0}}
    selfs = []
    ctl = {"app_name": "control", "app_id": "ap-c", "deadline_epoch": 300.0}
    cp.control_tick(reg, 200.0, lambda n, i: None, ctl, lambda n, i: selfs.append((n, i)))
    assert selfs == []
    out = cp.control_tick(reg, 301.0, lambda n, i: None, ctl, lambda n, i: selfs.append((n, i)))
    assert selfs == [("control", "ap-c")] and out["__control__"] == "self stop issued"


def test_manifest_backbone_label_names_the_pinned_checkpoint():
    from memsub.sgm.pinned_pretrained_qwen3_backbone import QWEN3_0P6B_BASE
    from memsub.sgm.synthetic_pilot import PilotConfig
    from memsub.sgm.synthetic_pilot_run import _backbone_label
    assert _backbone_label(PilotConfig()) == "tiny-qwen3-random-v1 (frozen, random init seed 0)"   # unchanged
    q = _backbone_label(PilotConfig(backbone="qwen3-0.6b-base"))
    assert QWEN3_0P6B_BASE["repo"] in q and QWEN3_0P6B_BASE["revision"] in q and "tiny" not in q
