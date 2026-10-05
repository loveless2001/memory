"""P2D top-up launcher (modal-runners/modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py):
config identity with v1, non-preemptible ledger, poll/collect state handling.
Local only - no Modal calls."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOPUP = ROOT / "modal-runners" / "modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py"
V1 = ROOT / "modal-runners" / "modal-m4-sgm-p2d-diagnostics-grid.py"
LOST = {"filleroff-learned-n64-s1", "long-learned-n16-s0", "long-learned-n16-s1",
        "long-learned-n32-s0", "long-learned-n32-s1", "addrsup-learned-n64-s0"}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def topup(monkeypatch):
    monkeypatch.chdir(ROOT)
    return _load(TOPUP, "p2d_topup")


def test_topup_cells_are_exactly_the_lost_v1_cells_with_registered_configs(topup):
    cells, ledger, prov = topup.plan_topup(cap=1e9)
    v1 = _load(V1, "p2d_v1")
    registered = {rid: p for rid, _t, p in v1.expand(json.loads((ROOT / topup.V1_GRID).read_text()))}
    assert {rid for rid, _p, _t in cells} == LOST
    assert all(registered[rid] == pilot for rid, pilot, _t in cells)
    assert prov["nonpreemptible"] is True and prov["memsub_source_sha256"] == topup.SOURCE_SHA


def test_tampered_topup_config_is_refused(topup, tmp_path, monkeypatch):
    grid = json.loads((ROOT / topup.GRID).read_text())
    grid["blocks"][1]["override"]["steps"] = 4000
    bad = tmp_path / "grid.json"
    bad.write_text(json.dumps(grid))
    monkeypatch.setattr(topup, "GRID", str(bad))
    with pytest.raises(ValueError, match="differs from the v1 registered cell"):
        topup.plan_topup(cap=1e9)


def test_ledger_scales_rate_based_reservations_by_three(topup):
    _c, ledger, _p = topup.plan_topup(cap=1e9)
    v1 = _load(V1, "p2d_v1")
    _c1, one_x, _p1 = v1.plan(Path(topup.GRID), Path(topup.V2_RUNS))
    for k in ("train_timeouts_usd", "startup_teardown_usd", "replay_allowance_usd", "cpu_overuse_margin_usd"):
        assert ledger[k] == pytest.approx(3 * one_x[k])
    for k in ("image_build_usd", "fixed_margin_usd"):
        assert ledger[k] == one_x[k]
    parts = [v for k, v in ledger.items() if k.endswith("_usd") and k not in ("reserved_total_usd", "cap_usd")]
    assert ledger["reserved_total_usd"] == pytest.approx(sum(parts))
    assert ledger["reserved_total_usd"] == pytest.approx(26.1300174)


@pytest.mark.parametrize("cap", [None, 26.0])
def test_missing_or_insufficient_cap_is_not_admitted(topup, cap):
    with pytest.raises(ValueError, match="not admitted"):
        topup.plan_topup(cap=cap)


def test_training_wrapper_is_verbatim_v1_and_function_is_nonpreemptible(topup):
    def body(path):
        fn = next(n for n in ast.parse(path.read_text()).body
                  if isinstance(n, ast.FunctionDef) and n.name == "_train_cell")
        return ast.dump(ast.Module(body=fn.body[1:] if isinstance(fn.body[0], ast.Expr) else fn.body,
                                   type_ignores=[]))
    assert body(TOPUP) == body(V1)
    assert "nonpreemptible=True" in TOPUP.read_text()


class _Call:
    def __init__(self, outcome):
        self.outcome = outcome

    def get(self, timeout=None):
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def test_poll_maps_pending_expired_failed_and_result(topup, monkeypatch):
    import modal
    from modal.exception import OutputExpiredError
    outcomes = {"p": TimeoutError(), "e": OutputExpiredError(), "f": RuntimeError("killed"), "r": {"status": "done"}}
    monkeypatch.setattr(modal.FunctionCall, "from_id", staticmethod(lambda cid: _Call(outcomes[cid])))
    assert topup.poll("p") == ("pending", None)
    assert topup.poll("e") == ("expired", None)
    assert topup.poll("f")[0] == "failed" and "killed" in topup.poll("f")[1]
    assert topup.poll("r") == ("result", {"status": "done"})


IDS = sorted(LOST)


def _setup_root(topup, tmp_path, monkeypatch, calls, grid=None):
    """A saved group root: registered grid, provenance with the spawn-time app ID, calls."""
    monkeypatch.setattr(topup, "LOCAL_OUT", str(tmp_path))
    root = tmp_path / topup.GROUP
    root.mkdir(parents=True)
    (root / "grid.json").write_text(grid if grid is not None else (ROOT / topup.GRID).read_text())
    (root / "launch_provenance.json").write_text(json.dumps({"deployed_app_id": "ap-spawned"}))
    if calls is not None:
        (root / "calls.json").write_text(json.dumps(calls))
    return root


def _fake_v1(monkeypatch, topup, stop=None, verified=True):
    v1, seen = _load(V1, "p2d_v1"), []

    def stop_app(app_id):
        seen.append(("stop", app_id))
        if stop:
            raise stop
    monkeypatch.setattr(v1, "stop_app", stop_app)
    monkeypatch.setattr(v1, "verify_stopped", lambda app_id: seen.append(("verify", app_id)) or
                        {"verified": verified})
    monkeypatch.setattr(topup, "v1_runner", lambda: v1)
    return seen


def _no_claims(rids):
    return {r: False for r in rids}


def test_collect_writes_done_cells_and_is_not_terminal_while_pending(topup, tmp_path, monkeypatch):
    root = _setup_root(topup, tmp_path, monkeypatch, {r: f"c-{r}" for r in IDS})
    a, b, c, d = IDS[:4]
    done = {"run_id": a, "status": "done",
            "metrics": {"final": {"none": {"accuracy": 0.5}}, "per_example": [{"x": 1}, {"x": 2}]}}
    polls = {f"c-{a}": ("result", done), f"c-{b}": ("pending", None),
             f"c-{c}": ("result", {"run_id": c, "status": "replay_refused"}),
             f"c-{d}": ("failed", "RuntimeError()")}
    seen = _fake_v1(monkeypatch, topup)
    report = topup.collect(poller=lambda cid: polls.get(cid, ("pending", None)), claims=_no_claims)
    assert report["terminal"] is False and report["consume_status"] == "complete" and seen == []
    assert json.loads((root / a / "metrics.json").read_text()) == {"final": {"none": {"accuracy": 0.5}}}
    assert (root / a / "per_example_results.jsonl").read_text().splitlines() == ['{"x": 1}', '{"x": 2}']
    assert not (root / c).exists()
    saved = json.loads((root / "collect_status.json").read_text())["cells"]
    assert saved[b]["poll"] == "pending" and saved[d]["error"] == "RuntimeError()"
    assert saved[c]["status"] == "replay_refused" and set(saved) == LOST


def test_collect_on_exhaustion_stops_and_verifies_the_spawn_time_app_id(topup, tmp_path, monkeypatch):
    root = _setup_root(topup, tmp_path, monkeypatch, {r: f"c-{r}" for r in IDS})
    seen = _fake_v1(monkeypatch, topup)
    report = topup.collect(poller=lambda cid: ("result", {"run_id": cid[2:], "status": "allowance_exhausted"}),
                           claims=_no_claims)
    assert report["consume_status"] == "halted" and "final_shutdown" not in report
    assert seen == [("stop", "ap-spawned"), ("verify", "ap-spawned")]
    assert json.loads((root / "shutdown.json").read_text())["status"] == "halted"


@pytest.mark.parametrize("stop,verified,expected", [
    (None, True, "stopped_verified"),
    (RuntimeError("already stopped"), True, "stopped_verified"),
    (None, False, "shutdown_unresolved")])
def test_all_six_tracked_and_terminal_stops_and_verifies(topup, tmp_path, monkeypatch, stop, verified,
                                                          expected):
    root = _setup_root(topup, tmp_path, monkeypatch, {r: f"c-{r}" for r in IDS})
    seen = _fake_v1(monkeypatch, topup, stop=stop, verified=verified)
    report = topup.collect(poller=lambda cid: ("result", {"run_id": cid[2:], "status": "replay_refused"})
                           if cid.endswith("s0") else ("expired", None), claims=_no_claims)
    assert report["terminal"] is True and report["final_shutdown"]["status"] == expected
    assert seen == [("stop", "ap-spawned"), ("verify", "ap-spawned")]
    saved = json.loads((root / "collect_status.json").read_text())
    assert saved["final_shutdown"]["status"] == expected
    assert ("stop_error" in saved["final_shutdown"]) == (stop is not None)


@pytest.mark.parametrize("recorded", [1, 0, None])   # 1 call saved / empty calls.json / no calls.json
def test_partial_spawn_never_reports_terminal_or_stops(topup, tmp_path, monkeypatch, recorded):
    calls = None if recorded is None else {r: f"c-{r}" for r in IDS[:recorded]}
    root = _setup_root(topup, tmp_path, monkeypatch, calls)
    seen, asked = _fake_v1(monkeypatch, topup), []
    report = topup.collect(poller=lambda cid: ("result", {"run_id": cid[2:], "status": "replay_refused"}),
                           claims=lambda rids: asked.extend(rids) or {r: True for r in rids})
    missing = IDS[(recorded or 0):]
    assert report["terminal"] is False and "final_shutdown" not in report and seen == []
    assert sorted(report["untracked"]) == missing and sorted(asked) == missing
    assert all(report["cells"][r] == {"poll": "untracked", "claimed": True} for r in missing)
    saved = json.loads((root / "collect_status.json").read_text())
    assert sorted(saved["untracked"]) == missing and "never respawned" in saved["untracked_recovery"].lower()


def test_collect_rejects_unregistered_calls_and_a_shrunken_saved_grid(topup, tmp_path, monkeypatch):
    _fake_v1(monkeypatch, topup)
    _setup_root(topup, tmp_path / "x", monkeypatch, {**{r: f"c-{r}" for r in IDS}, "rogue-cell": "c"})
    with pytest.raises(SystemExit, match="unregistered"):
        topup.collect(poller=lambda cid: ("pending", None), claims=_no_claims)
    grid = json.loads((ROOT / topup.GRID).read_text())
    grid["blocks"] = grid["blocks"][:1]
    _setup_root(topup, tmp_path / "y", monkeypatch, {IDS[0]: "c"}, grid=json.dumps(grid))
    with pytest.raises(SystemExit, match="not the authorized 6-cell"):
        topup.collect(poller=lambda cid: ("pending", None), claims=_no_claims)


@pytest.mark.parametrize("edit", ["drop", "extra"])
def test_plan_enforces_exactly_the_six_authorized_cells(topup, tmp_path, monkeypatch, edit):
    grid = json.loads((ROOT / topup.GRID).read_text())
    if edit == "drop":
        grid["blocks"] = grid["blocks"][:1]                       # 1-cell top-up
    else:
        grid["blocks"][0]["seeds"] = [0, 1]                       # adds v1-identical filleroff N64 s0
    path = tmp_path / "grid.json"
    path.write_text(json.dumps(grid))
    monkeypatch.setattr(topup, "GRID", str(path))
    with pytest.raises(ValueError, match="exactly the 6 authorized cells"):
        topup.plan_topup(cap=1e9)


def test_atomic_write_never_leaves_truncated_state(topup, tmp_path, monkeypatch):
    import os
    target = tmp_path / "calls.json"
    topup.atomic_write(target, '{"a": 1}')
    assert json.loads(target.read_text()) == {"a": 1} and not list(tmp_path.glob("*.tmp"))
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("host died")))
    with pytest.raises(OSError):
        topup.atomic_write(target, '{"a": 1, "b": 2}')
    assert json.loads(target.read_text()) == {"a": 1}            # previous complete state intact


def test_heavy_imports_hashing_and_claim_run_under_the_early_watchdog(topup):
    fn = next(n for n in ast.parse(TOPUP.read_text()).body
              if isinstance(n, ast.FunctionDef) and n.name == "run_cell")
    i_early = next(i for i, st in enumerate(fn.body) if isinstance(st, ast.Assign)
                   and getattr(st.targets[0], "id", None) == "early")
    before = [st for st in fn.body[:i_early] if isinstance(st, (ast.Import, ast.ImportFrom))]
    assert [st.module for st in before] == ["memsub.sgm.p2d_launch_guard"]   # stdlib-only module
    guarded = fn.body[i_early + 1]
    assert isinstance(guarded, ast.Try)
    inner = ast.dump(ast.Module(body=guarded.body, type_ignores=[]))
    for name in ("synthetic_pilot_run", "source_tree_sha256", "AttemptLedger"):
        assert name in inner


def test_registered_cap_admits_the_topup_ledger(topup):
    assert topup.TOPUP_CAP_USD == 27.0
    _c, ledger, _p = topup.plan_topup()
    assert ledger["admitted"] and ledger["cap_usd"] == 27.0
