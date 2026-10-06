"""Amendment PK proof runner, local only (fakes stand in for every Modal call): admission bounds
and deadline, fresh-container + retry settings, charge bound arithmetic, collect paths."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def run(monkeypatch):
    monkeypatch.chdir(ROOT)
    spec = importlib.util.spec_from_file_location("pk_runner", ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-packed-slot-proof-runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeDict(dict):
    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self:
            return False
        self[k] = v
        return True


def test_admission_bounds_starts_per_scenario_and_deadline(run):
    adm, guard = FakeDict(), FakeDict(deadline_epoch=100.0)
    assert run.admit(adm, guard, "B", 1.0, run.MAX_STARTS["B"]) == (1, None)
    assert run.admit(adm, guard, "B", 2.0, run.MAX_STARTS["B"]) == (2, None)
    assert run.admit(adm, guard, "B", 3.0, run.MAX_STARTS["B"]) == (None, "start allowance exhausted")
    assert run.admit(adm, guard, "A", 4.0, run.MAX_STARTS["A"]) == (1, None)        # independent per scenario
    assert run.admit(adm, guard, "A", 5.0, run.MAX_STARTS["A"])[0] is None          # A: one start only
    assert "deadline" in run.admit(FakeDict(), FakeDict(deadline_epoch=100.0), "C", 101.0, 2)[1]
    assert "deadline" in run.admit(FakeDict(), FakeDict(), "C", 1.0, 2)[1]


def test_max_starts_match_amendment(run):
    assert run.MAX_STARTS == {"A": 1, "Aprime": 1, "E": 1, "B": 2, "C": 2, "D": 2}
    grid = json.loads((ROOT / run.GRID_FILE).read_text())
    assert set(run.MAX_STARTS) == set(grid["scenarios"])
    for s, spec in grid["scenarios"].items():                  # faulted scenarios get exactly one resume start
        assert run.MAX_STARTS[s] == (2 if spec["faults"] else 1)


def test_slot_function_is_single_use_with_one_retry(run):
    src = (ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-packed-slot-proof-runner.py").read_text()
    slot_decl = src[src.index("def run_slot") - 400:src.index("def run_slot")]
    assert "single_use_containers=True" in slot_decl and "max_retries=1" in slot_decl


def test_charge_bound_is_the_sum_of_its_parts(run):
    led = run.charge_bound()
    parts = [led[k] for k in ("slot_starts_usd", "timing_usd", "reaper_usd", "image_reserve_usd", "fixed_margin_usd")]
    assert abs(led["reserved_total_usd"] - sum(parts)) < 1e-9
    assert led["slot_starts"] == 9
    assert abs(led["slot_starts_usd"] - 9 * (run.SLOT_START_TIMEOUT_S + run.STARTUP_S) * run.rate(2.0)) < 1e-9
    assert led["hard_tuple_total_usd"] < led["reserved_total_usd"]


def _prov(tmp_path, run):
    root = tmp_path / run.LOCAL_OUT / run.GROUP
    root.mkdir(parents=True)
    (root / "launch_provenance.json").write_text(json.dumps({"deadline_epoch": 1000.0, "deployed_app_id": "ap-x"}))
    (root / "calls.json").write_text(json.dumps({"A": "fc-a", "timing": "fc-t"}))
    return root


def test_collect_pending_before_deadline_does_not_stop(run, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _prov(tmp_path, run)
    stops = []
    rep = run.collect(poller=lambda c: ("pending", None), stopper=lambda a: stops.append(a), fetch=lambda r: {},
                      now=10.0)
    assert stops == [] and "final_shutdown" not in rep


def test_collect_terminal_or_past_deadline_stops_by_app_id(run, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = _prov(tmp_path, run)
    stops = []
    run.collect(poller=lambda c: ("result", {"status": "slot_done"}), stopper=lambda a: stops.append(a) or {"ok": 1},
                fetch=lambda r: {"returncode": 0}, now=10.0)
    run.collect(poller=lambda c: ("pending", None), stopper=lambda a: stops.append(a) or {"ok": 1},
                fetch=lambda r: {"returncode": 0}, now=2000.0)
    (root / "calls.json").unlink()                              # untracked calls still reach the stop
    run.collect(poller=lambda c: ("pending", None), stopper=lambda a: stops.append(a) or {"ok": 1},
                fetch=lambda r: {"returncode": 0}, now=10.0)
    assert stops == ["ap-x", "ap-x", "ap-x"]
