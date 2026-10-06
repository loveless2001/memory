"""Amendment PK campaign control-plane reaper (one schedule for all apps; codex 21596) and the
manifest backbone-label fix (codex 21585)."""

import importlib.util
from pathlib import Path

import pytest

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


V = lambda n, i: True                                                   # noqa: E731  verifier: stopped


def test_only_overdue_apps_are_stopped_by_their_bound_ids():
    reg = {"slot-a": {"app_id": "ap-a", "deadline_epoch": 100.0}, "slot-b": {"app_id": "ap-b", "deadline_epoch": 500.0},
           "readings": {"app_id": "ap-r", "deadline_epoch": 50.0}}
    calls = []
    out = cp.control_tick(reg, 200.0, lambda n, i: calls.append((n, i)), V)
    assert sorted(calls) == [("readings", "ap-r"), ("slot-a", "ap-a")] and out["slot-b"] == "not due"
    assert out["slot-a"] == "stopped_verified" and out["__unresolved__"] == []


@pytest.mark.parametrize("bad", [{"app_id": "ap-x"}, {"deadline_epoch": 1.0}, {"app_id": None, "deadline_epoch": 1.0},
                                 {"app_id": "", "deadline_epoch": 1.0}, {"app_id": "ap", "deadline_epoch": float("nan")},
                                 {"app_id": "ap", "deadline_epoch": float("inf")}, {"app_id": "ap", "deadline_epoch": True},
                                 {"app_id": "ap", "deadline_epoch": -5.0}, "garbage"])
def test_malformed_entries_are_quarantined_never_name_only_stopped(bad):
    calls = []
    out = cp.control_tick({"x": bad, "ok": {"app_id": "ap-ok", "deadline_epoch": 1.0}}, 10.0,
                          lambda n, i: calls.append((n, i)), V)
    assert calls == [("ok", "ap-ok")] and out["x"].startswith("quarantined") and "x" in out["__unresolved__"]
    with pytest.raises(ValueError):
        cp.register(FakeDict(), "x", bad.get("app_id") if isinstance(bad, dict) else None,
                    bad.get("deadline_epoch") if isinstance(bad, dict) else None)


def test_registration_is_write_once_and_never_reset():
    store = FakeDict()
    assert cp.register(store, "slot-a", "ap-a", 100.0)
    assert not cp.register(store, "slot-a", "ap-other", 9e9)            # deadline can never be extended
    assert store["slot-a"] == {"app_id": "ap-a", "deadline_epoch": 100.0}


def test_self_stop_holds_while_targets_unresolved_then_finite_fallback():
    reg = {"slot-a": {"app_id": "ap-a", "deadline_epoch": 100.0}}
    ctl = {"app_name": "control", "app_id": "ap-c", "deadline_epoch": 300.0}
    selfs, failing = [], lambda n, i: (_ for _ in ()).throw(RuntimeError("stop failed"))
    out = cp.control_tick(reg, 301.0, failing, lambda n, i: False, ctl, lambda n, i: selfs.append(n), fallback_s=100.0)
    assert selfs == [] and out["__control__"] == "holding: unresolved targets" and out["__unresolved__"] == ["slot-a"]
    out = cp.control_tick(reg, 401.0, failing, lambda n, i: False, ctl, lambda n, i: selfs.append(n), fallback_s=100.0)
    assert selfs == ["control"] and "fallback" in out["__control__"]
    out = cp.control_tick(reg, 301.0, lambda n, i: None, V, ctl, lambda n, i: selfs.append(n))
    assert out["__control__"] == "self stop issued"                     # all resolved: stops at its deadline


def test_hung_stop_request_cannot_starve_other_targets():
    import threading
    import time as _t
    release = threading.Event()
    reg = {"a-hung": {"app_id": "ap-h", "deadline_epoch": 1.0}, "b-ok": {"app_id": "ap-b", "deadline_epoch": 1.0}}

    def stopper(n, i):
        if n == "a-hung":
            release.wait(5)
    t0 = _t.monotonic()
    out = cp.control_tick(reg, 10.0, stopper, V, request_timeout_s=0.5)
    release.set()
    assert out["b-ok"] == "stopped_verified" and out["a-hung"] == "stop/verify timeout" and _t.monotonic() - t0 < 2


def test_unarmed_controller_is_not_due_on_its_first_tick():
    spec = importlib.util.spec_from_file_location("ctl2", ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py")
    ctl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctl)
    view = ctl.control_view(FakeDict(), 10.0, lambda: "ap-self")
    assert view["app_id"] == "ap-self" and not cp.due(view, 10.0) and cp.due(view, 10.0 + ctl.ABANDON_S + 1)
    bad = ctl.control_view(FakeDict(deadline_epoch=float("nan")), 10.0, lambda: "ap-self")
    assert bad["deadline_epoch"] == 10.0 + ctl.ABANDON_S                # malformed arm -> bounded abandonment


def test_manifest_backbone_label_names_the_pinned_checkpoint():
    from memsub.sgm.pinned_pretrained_qwen3_backbone import QWEN3_0P6B_BASE
    from memsub.sgm.synthetic_pilot import PilotConfig
    from memsub.sgm.synthetic_pilot_run import _backbone_label
    assert _backbone_label(PilotConfig()) == "tiny-qwen3-random-v1 (frozen, random init seed 0)"   # unchanged
    q = _backbone_label(PilotConfig(backbone="qwen3-0.6b-base"))
    assert QWEN3_0P6B_BASE["repo"] in q and QWEN3_0P6B_BASE["revision"] in q and "tiny" not in q
