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


import subprocess  # noqa: E402


def launcher(kind, calls=None):
    """Owned children: 'ok' exits 0 (verified), 'unverified' exits 3, 'hung' sleeps (unique tag)."""
    def launch(name, app_id):
        if calls is not None:
            calls.append((name, app_id))
        k = kind(name) if callable(kind) else kind
        cmd = {"ok": ["true"], "unverified": ["sh", "-c", "exit 3"], "hung": ["sleep", "41.4243"]}[k]
        return subprocess.Popen(cmd)
    return launch


def alive(tag="41.4243"):
    return len(subprocess.run(["pgrep", "-fx", f"sleep {tag}"], capture_output=True, text=True).stdout.split())


def test_only_overdue_apps_are_stopped_by_their_bound_ids():
    reg = {"slot-a": {"app_id": "ap-a", "deadline_epoch": 100.0}, "slot-b": {"app_id": "ap-b", "deadline_epoch": 500.0},
           "readings": {"app_id": "ap-r", "deadline_epoch": 50.0}}
    calls = []
    out, self_due = cp.control_tick(reg, 200.0, launcher("ok", calls))
    assert sorted(calls) == [("readings", "ap-r"), ("slot-a", "ap-a")] and out["slot-b"] == "not due"
    assert out["slot-a"] == "stopped_verified" and out["__unresolved__"] == [] and not self_due


@pytest.mark.parametrize("bad", [{"app_id": "ap-x"}, {"deadline_epoch": 1.0}, {"app_id": None, "deadline_epoch": 1.0},
                                 {"app_id": "", "deadline_epoch": 1.0}, {"app_id": "ap", "deadline_epoch": float("nan")},
                                 {"app_id": "ap", "deadline_epoch": float("inf")}, {"app_id": "ap", "deadline_epoch": True},
                                 {"app_id": "ap", "deadline_epoch": -5.0}, "garbage"])
def test_malformed_entries_are_quarantined_never_name_only_stopped(bad):
    calls = []
    out, _ = cp.control_tick({"x": bad, "ok": {"app_id": "ap-ok", "deadline_epoch": 1.0}}, 10.0, launcher("ok", calls))
    assert calls == [("ok", "ap-ok")] and out["x"].startswith("quarantined") and "x" in out["__unresolved__"]
    with pytest.raises(ValueError):
        cp.register(FakeDict(), "x", bad.get("app_id") if isinstance(bad, dict) else None,
                    bad.get("deadline_epoch") if isinstance(bad, dict) else None)


def test_deadline_beyond_controller_horizon_is_held_not_ignored():
    ctl = {"app_name": "control", "app_id": "ap-c", "deadline_epoch": 300.0}
    out, self_due = cp.control_tick({"late": {"app_id": "ap-l", "deadline_epoch": 900.0}}, 301.0, launcher("ok"), ctl,
                                    fallback_s=100.0)
    assert out["late"].startswith("quarantined") and not self_due and out["__control__"] == "holding: unresolved targets"
    with pytest.raises(ValueError):
        cp.register(FakeDict(), "late", "ap-l", 900.0, horizon=300.0)


def test_registration_is_write_once_and_never_reset():
    store = FakeDict()
    assert cp.register(store, "slot-a", "ap-a", 100.0)
    assert not cp.register(store, "slot-a", "ap-other", 9e9)
    assert store["slot-a"] == {"app_id": "ap-a", "deadline_epoch": 100.0}


def test_self_stop_holds_while_unresolved_then_finite_fallback():
    reg = {"slot-a": {"app_id": "ap-a", "deadline_epoch": 100.0}}
    ctl = {"app_name": "control", "app_id": "ap-c", "deadline_epoch": 300.0}
    out, due1 = cp.control_tick(reg, 301.0, launcher("unverified"), ctl, fallback_s=100.0)
    assert not due1 and out["__unresolved__"] == ["slot-a"]
    out, due2 = cp.control_tick(reg, 401.0, launcher("unverified"), ctl, fallback_s=100.0)
    assert due2 and "fallback" in out["__control__"]
    out, due3 = cp.control_tick(reg, 301.0, launcher("ok"), ctl)
    assert due3 and out["__control__"] == "self stop due"


def test_repeated_ticks_with_multiple_hung_targets_leave_no_workers():
    import time as _t
    reg = {f"h{i}": {"app_id": f"ap-h{i}", "deadline_epoch": 1.0} for i in range(3)} | {"ok": {"app_id": "ap-ok", "deadline_epoch": 1.0}}
    for _ in range(2):
        t0 = _t.monotonic()
        out, _ = cp.control_tick(reg, 10.0, launcher(lambda n: "ok" if n == "ok" else "hung"), request_timeout_s=0.4)
        assert out["ok"] == "stopped_verified" and all("killed and reaped" in out[f"h{i}"] for i in range(3))
        assert _t.monotonic() - t0 < 2 and alive() == 0                  # owned children killed AND reaped


def _ctl_app():
    spec = importlib.util.spec_from_file_location("ctl3", ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py")
    ctl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctl)
    return ctl


def test_finish_tick_persists_evidence_before_a_bounded_self_stop():
    ctl, order = _ctl_app(), []
    w = lambda o: (order.append("evidence"), subprocess.Popen(["true"]))[1]       # noqa: E731
    st = ctl.finish_tick(cp, {"x": 1}, True, w, lambda: (order.append("self"), subprocess.Popen(["true"]))[1])
    assert order == ["evidence", "self"] and st == {"evidence": "stopped_verified", "self_stop": "stopped_verified"}
    bad = ctl.finish_tick(cp, {}, True, lambda o: subprocess.Popen(["sh", "-c", "exit 1"]),
                          lambda: subprocess.Popen(["true"]))                     # write failure still self-stops
    assert bad["evidence"].startswith("unverified") and bad["self_stop"] == "stopped_verified"
    hung = ctl.finish_tick(cp, {}, True, lambda o: subprocess.Popen(["true"]),
                           lambda: subprocess.Popen(["sleep", "41.4243"]), timeout_s=0.4)
    assert "killed and reaped" in hung["self_stop"] and alive() == 0
    written = []

    def immediate():                                                              # self-stop terminates us at once
        raise SystemExit("terminated")
    with pytest.raises(SystemExit):
        ctl.finish_tick(cp, {"term": 1}, True, lambda o: (written.append(o), subprocess.Popen(["true"]))[1], immediate)
    assert written == [{"term": 1}]                                               # evidence already persisted


def test_slot_runner_horizon_constants_match_the_controller():
    ctl = _ctl_app()
    src = (ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py").read_text()
    assert f"VALIDATION_SETUP_S, CONTROL_SLACK_S = {ctl.VALIDATION_SETUP_S}, {ctl.SLACK_S}" in src
    assert f'CONTROL_GUARD_DICT = "{ctl.CONTROL_GUARD}"' in src and f'"{ctl.REGISTRY_DICT}"' in src
    rd = (ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py").read_text()
    assert f'CONTROL_REGISTRY_DICT, CONTROL_GUARD_DICT = "{ctl.REGISTRY_DICT}", "{ctl.CONTROL_GUARD}"' in rd
    # attempt 1 (2026-10-07) armed the unsuffixed guard write-once; it stays preserved and is never reused
    assert ctl.CONTROL_GUARD.endswith("-r2") and ctl.REGISTRY_DICT.endswith("-r2")


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


# -- codex 21604: process groups, contained writer launch, complete controller binding --
def test_hung_descendants_are_killed_with_their_group_over_repeated_ticks():
    def launch(name, app_id):                     # parent spawns a hung DESCENDANT (like the nested CLI)
        return subprocess.Popen(["sh", "-c", "sleep 51.5151 & sleep 51.5152; wait"], start_new_session=True)
    for _ in range(2):
        out, _ = cp.control_tick({"h": {"app_id": "ap-h", "deadline_epoch": 1.0}}, 10.0, launch, request_timeout_s=0.4)
        assert "killed and reaped" in out["h"]
        import time as _t
        _t.sleep(0.2)
        assert alive("51.5151") == 0 and alive("51.5152") == 0


def test_writer_launch_failure_still_self_stops_with_fallback_evidence():
    ctl, stops = _ctl_app(), []

    def bad_writer(o):
        raise OSError("tempfile unavailable")
    st = ctl.finish_tick(cp, {"k": 1}, True, bad_writer, lambda: (stops.append(1), subprocess.Popen(["true"]))[1])
    assert stops == [1] and st["evidence"].startswith("writer launch error") and st["fallback_evidence"] == {"k": 1}
    st2 = ctl.finish_tick(cp, {}, True, lambda o: subprocess.Popen(["true"]),
                          lambda: (_ for _ in ()).throw(OSError("no fork")))
    assert st2["self_stop"].startswith("self-stop launch error")


def _slot(monkeypatch):
    monkeypatch.setenv("M4_PK_SLOT", "learned-n32")
    monkeypatch.chdir(ROOT)
    spec = importlib.util.spec_from_file_location("slotp", ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_controller_preflight_fails_closed_on_partial_stale_or_mismatched_state(monkeypatch):
    import hashlib
    m = _slot(monkeypatch)
    price = hashlib.sha256((ROOT / m.PRICE_FILE).read_bytes()).hexdigest()
    good = {"app_id": "ap-c", "deadline_epoch": 1e10, "price_sha256": price}
    ok = dict(live_id=lambda: "ap-c", live_state=lambda i: "deployed")
    assert m.controller_preflight(cp, good, 1e9, **ok) is None
    cases = [({"deadline_epoch": 1e10, "price_sha256": price}, ok, "incomplete"),
             ({**good, "deadline_epoch": float("nan")}, ok, "incomplete"),
             ({**good, "price_sha256": "x"}, ok, "different price"),
             (good, dict(live_id=lambda: "ap-other", live_state=lambda i: "deployed"), "differs"),
             (good, dict(live_id=lambda: "ap-c", live_state=lambda i: "stopped"), "not running"),
             (good, dict(live_id=lambda: (_ for _ in ()).throw(RuntimeError("x")), live_state=lambda i: "x"), "lookup failed"),
             ({**good, "deadline_epoch": 1e9 + 10}, ok, "beyond the controller horizon")]
    for control, live, needle in cases:
        assert needle in m.controller_preflight(cp, control, 1e9, **live)
    src = (ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py").read_text()
    body = src[src.index("def spawn() -> None:"):]
    assert body.index("controller_preflight(") < body.index("GUARD_DICT, create_if_missing") < body.index("root.mkdir(")


# -- codex 21606 --
def test_early_exit_leader_does_not_leave_descendants():
    def launch(name, app_id):
        return subprocess.Popen(["sh", "-c", "sleep 61.6161 & exit 0"], start_new_session=True)
    out, _ = cp.control_tick({"e": {"app_id": "ap-e", "deadline_epoch": 1.0}}, 10.0, launch, request_timeout_s=2.0)
    import time as _t
    _t.sleep(0.2)
    assert out["e"] == "stopped_verified" and alive("61.6161") == 0       # rc kept, group cleaned


def test_terminal_intent_logged_before_failing_writer_and_immediate_termination(capsys):
    ctl = _ctl_app()

    def bad_writer(o):
        raise OSError("no tempfile")

    def immediate():
        raise SystemExit("terminated")
    with pytest.raises(SystemExit):
        ctl.finish_tick(cp, {"slot-a": "stopped_verified", "__unresolved__": []}, True, bad_writer, immediate)
    logged = capsys.readouterr().out
    assert '"m4_pk_control_tick"' in logged and '"slot-a": "stopped_verified"' in logged and '"self_stop_due": true' in logged


def test_spawn_uses_one_immutable_deadline_despite_clock_advance(monkeypatch, tmp_path):
    import hashlib
    import types
    m = _slot(monkeypatch)
    clock = iter(float(1_000_000 + i) for i in range(100))               # +1 s per time.time() call
    monkeypatch.setattr(m.time, "time", lambda: next(clock))
    life = m.slot_deadline_s()
    readings = __import__("json").loads((ROOT / m.PRICE_FILE).read_text())["readings"]["reserve_life_s"]
    price = hashlib.sha256((ROOT / m.PRICE_FILE).read_bytes()).hexdigest()
    first = 1_000_000.0                                                   # the single candidate's clock reading
    dicts = {m.CONTROL_GUARD_DICT: FakeDict(app_id="ap-c", price_sha256=price,
                                            deadline_epoch=first + life + m.VALIDATION_SETUP_S + readings + m.CONTROL_SLACK_S)}
    fake = types.SimpleNamespace(
        Dict=types.SimpleNamespace(from_name=lambda n, **k: dicts.setdefault(n, FakeDict())),
        App=types.SimpleNamespace(lookup=lambda n, **k: types.SimpleNamespace(app_id="ap-c" if n == m.CONTROL_APP_NAME else "ap-slot")),
        Function=types.SimpleNamespace(from_name=lambda *a: types.SimpleNamespace(
            spawn=lambda *a: types.SimpleNamespace(object_id="fc-x"))))
    monkeypatch.setattr(m, "modal", fake)
    monkeypatch.setattr(m, "app_state", lambda i: "deployed")
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout=""))
    monkeypatch.setattr(m, "LOCAL_OUT", str(tmp_path))
    m.spawn()                                                             # exactly at the horizon boundary: accepted
    prov = __import__("json").loads((tmp_path / m.GROUP / m.SLOT / "launch_provenance.json").read_text())
    reg = dicts["m4-sgm-p2p5-pk-campaign-control-registry-r2"][m.APP_NAME]
    assert prov["deadline_epoch"] == dicts[m.GUARD_DICT]["deadline_epoch"] == reg["deadline_epoch"] == first + life
