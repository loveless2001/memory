"""Readout probe: bindings, admission, the probe reaper decision (codex 21752), collect and the reading rules.

No Modal call is made: the runner module is imported locally (it only BUILDS objects), and stores, stoppers,
pollers, verifiers and fetchers are in-memory fakes.
"""

import ast
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py"


def load(rel, name):
    s = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


L = load("modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-logic.py", "probe_slot_logic_t")
CP = load(L.CONTROL_LOGIC_FILE, "cp_t")
READ = load("scripts/sgm-p2p5-readout-probe-reading.py", "probe_reading_t")
P2D = load("scripts/sgm-p2d-step2-decision-rules.py", "p2d_t")
P2G = load("scripts/sgm-p2g-decision-rules.py", "p2g_t")
LEDGER = load("scripts/sgm-p2p5-readout-probe-priced-ledger.py", "probe_ledger_t")


class Store(dict):
    """Modal Dict stand-in (get / put skip_if_exists / contains)."""
    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self:
            return False
        self[k] = v
        return True

    def contains(self, k):
        return k in self


# ---- bindings ----------------------------------------------------------------------------------------------------

def test_bindings_are_probe_only():
    values = [L.APP_NAME, L.GUARD_DICT, L.ADMIT_DICT, L.VOLUME_SUBPATH, L.LOCAL_OUT, L.GROUP, L.LEDGER_FILE,
              L.GRID_FILE, L.REGISTRY_FILE, L.SCHEMA_FILE]
    assert not any(c in v for v in values for c in L.CAMPAIGN_WRITABLE)
    assert L.VOLUME_SUBPATH == "m4-sgm/p2p5-readout-probe-v1/taskhead-learned-n32"
    assert L.GUARD_DICT == "memsub-m4-sgm-p2p5-readout-probe-guard" and L.MAX_STARTS == 4 and L.C == 50
    assert L.EVAL["final_seed_base"] == 9_300_011 and 9_600_011 not in L.EVAL.values()


def test_runner_bound_objects_and_resources():
    r = load("modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py", "probe_runner_t")
    assert r.app.name == L.APP_NAME and sorted(r.app.registered_functions) == ["reaper", "run_slot"]
    gpu, reaper = r.run_slot.spec, r.reaper.spec
    assert gpu.gpus == "A100-80GB" and gpu.cpu == (8.0, 8.0) and gpu.memory == (65536, 65536)
    assert list(gpu.volumes) == ["/artifacts"] and reaper.cpu == 0.125 and reaper.memory == 256 and not reaper.gpus


def _decorators():
    tree = ast.parse(RUNNER.read_text())
    out = {}
    for f in tree.body:
        if isinstance(f, ast.FunctionDef):
            for d in f.decorator_list:
                if isinstance(d, ast.Call) and ast.unparse(d.func) == "app.function":
                    out[f.name] = {k.arg: ast.unparse(k.value) for k in d.keywords}
    return out


def test_decorator_lifetime_arguments():
    d = _decorators()
    assert d["run_slot"]["max_containers"] == "1" and d["run_slot"]["single_use_containers"] == "True"
    assert d["run_slot"]["timeout"] == "L.FUNCTION_MAX_S" and "L.MAX_STARTS - 1" in d["run_slot"]["retries"]
    assert d["reaper"]["schedule"] == "modal.Period(seconds=L.REAPER_PERIOD_S)" and d["reaper"]["retries"] == "0"
    assert d["reaper"]["timeout"] == "110" and int(d["reaper"]["timeout"]) < L.REAPER_PERIOD_S   # a hung stop is bounded
    assert d["reaper"]["max_containers"] == "1"


def test_image_inputs_are_the_bound_probe_files():
    src = RUNNER.read_text()
    calls = [ast.unparse(n.args[0]) for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr in ("add_local_file", "add_local_dir")]
    assert sorted(calls) == sorted(["'memsub'", "'configs'", "L.LEDGER_FILE", "L.VALIDATOR_FILE", "L.SLOT_LOGIC_FILE",
                                    "L.LIFETIME_LOGIC_FILE", "L.SLOT_LOGIC_FILE", "L.LIFETIME_LOGIC_FILE"])
    assert "pk-campaign" not in src.replace("pk-control-plane-reaper-logic", "")      # no campaign module import


# ---- admission ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("guard,why", [
    ({"deadline_epoch": 2e9}, "no bound app id"),
    ({"app_id": "", "deadline_epoch": 2e9}, "no bound app id"),
    ({"app_id": "ap-x"}, "deadline"),
    ({"app_id": "ap-x", "deadline_epoch": math.nan}, "deadline"),
    ({"app_id": "ap-x", "deadline_epoch": math.inf}, "deadline"),
    ({"app_id": "ap-x", "deadline_epoch": True}, "deadline"),
    ({"app_id": "ap-x", "deadline_epoch": -5.0}, "deadline"),
    ({"app_id": "ap-x", "deadline_epoch": 100.0}, "deadline"),          # passed
])
def test_admission_refuses_unbound_or_malformed_guards(guard, why):
    n, reason = L.admit(Store(), Store(guard), now=1000.0)
    assert n is None and why in reason


def test_admission_claims_at_most_four_starts():
    adm, guard = Store(), Store(app_id="ap-x", deadline_epoch=2e9)
    assert [L.admit(adm, guard, 1.0)[0] for _ in range(5)] == [1, 2, 3, 4, None]


# ---- the probe reaper decision (codex 21752) ---------------------------------------------------------------------

SELF = "ap-self"
SHARED_LIFETIME_SHA = "32bb3a3a38bf375e4c9107e4b3d7dc4c6392076cb5ba55f7c599fab644329e6c"


def decide(store, now, self_id=SELF):
    return L.reap_decision(store, now, self_id)


def test_reaper_stops_after_a_valid_deadline_with_the_bound_id():
    s = Store(app_id=SELF, deadline_epoch=500.0)
    assert decide(s, 400.0) == (None, SELF, None)
    assert decide(s, 501.0) == ("deadline passed", SELF, None)


@pytest.mark.parametrize("deadline", [math.nan, math.inf, True, -1.0, "x", None])
def test_malformed_or_missing_deadline_takes_bounded_abandonment(deadline):
    s = Store(app_id=SELF, deadline_epoch=deadline, first_tick=100.0)
    assert decide(s, 100.0 + L.ABANDON_S - 1)[0] is None
    assert decide(s, 100.0 + L.ABANDON_S + 1) == ("abandoned or malformed binding", SELF, None)


def test_unspawned_and_interrupted_binding_are_abandoned_with_the_self_id():
    unspawned = Store()
    assert decide(unspawned, 10.0) == (None, SELF, None) and unspawned["first_tick"] == 10.0
    assert decide(unspawned, 10.0 + L.ABANDON_S + 1)[0] is not None
    interrupted = Store(app_id=SELF, first_tick=100.0)                    # spawn wrote the id, not the deadline
    assert decide(interrupted, 100.0 + L.ABANDON_S + 1) == ("abandoned or malformed binding", SELF, None)
    assert decide(Store(app_id=SELF, first_tick=0.0), 1e9)[2].startswith("first_tick malformed")


@pytest.mark.parametrize("store,self_id,problem", [
    (Store(app_id=SELF, deadline_epoch=1.0), None, "own app id unavailable"),
    (Store(app_id=SELF, deadline_epoch=1.0), "", "own app id unavailable"),
    (Store(self_app_id="ap-old", app_id="ap-old", deadline_epoch=1.0), SELF, "bound self id"),
    (Store(app_id="ap-other", deadline_epoch=1.0), SELF, "is not this app"),
])
def test_missing_or_mismatched_ids_never_stop(store, self_id, problem):
    reason, bound, why = decide(store, 1e9, self_id)
    assert reason is None and bound is None and problem in why


def test_reap_and_stop_never_passes_none_and_records_stop_errors():
    calls = []
    out = L.reap_and_stop(Store(app_id=SELF, deadline_epoch=1.0), 5.0, SELF, lambda n, i: calls.append((n, i)))
    assert calls == [(L.APP_NAME, SELF)] and out["stop"] is True
    s = Store(app_id=SELF, deadline_epoch=1.0)

    def boom(n, i):
        raise RuntimeError("bound app ap-self != live ap-y")
    out = L.reap_and_stop(s, 5.0, SELF, boom)
    assert "stop_error" in out and s["reaper_fired"]["bound"] == SELF
    nothing = []
    out = L.reap_and_stop(Store(app_id="ap-other", deadline_epoch=1.0), 5.0, SELF, lambda n, i: nothing.append(i))
    assert nothing == [] and out["stop"] is False and "problem" in out
    out = L.reap_and_stop(Store(app_id=SELF, deadline_epoch=1.0), 5.0, None, lambda n, i: nothing.append(i))
    assert nothing == [] and out["stop"] is False


def test_shared_stop_helper_is_unchanged_and_used_only_with_a_bound_id():
    src = (ROOT / "modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py").read_text()
    body = src.split("def reaper")[1].split("def identity_now")[0]
    assert "L.reap_and_stop" in body and "lifetime().stop_bound_app" in body
    assert "lt.reap_and_stop" not in src and ".reap_decision(" not in src        # the shared decision is never used
    shared = (ROOT / L.LIFETIME_LOGIC_FILE).read_bytes()
    import hashlib
    assert hashlib.sha256(shared).hexdigest() == SHARED_LIFETIME_SHA


@pytest.mark.parametrize("guard,now,ok", [
    ({}, 0.0, True),
    ({"first_tick": 100.0, "self_app_id": SELF}, 160.0, True),
    ({"first_tick": 100.0}, 100.0 + L.ABANDON_S - L.SPAWN_MARGIN_S + 1, False),
    ({"first_tick": 100.0, "self_app_id": "ap-old"}, 160.0, False),
    ({"first_tick": 100.0, "app_id": SELF}, 160.0, False),
    ({"first_tick": 100.0, "reaper_fired": {}}, 160.0, False),
    ({"first_tick": 0.0}, 60.0, False),
    ({"first_tick": math.nan}, 60.0, False),
])
def test_spawn_guard(guard, now, ok):
    assert (L.spawn_guard_problem(guard, SELF, now) is None) == ok


# ---- collect with fakes ------------------------------------------------------------------------------------------

def _prov(root: Path, **over):
    root.mkdir(parents=True, exist_ok=True)
    prov = {"slot": L.SLOT, "deployed_app_id": SELF, "deadline_epoch": 1000.0, "expected_identity": {"memsub": "m"}, **over}
    (root / "launch_provenance.json").write_text(json.dumps(prov))
    (root / "call.json").write_text(json.dumps({"call_id": "fc-1"}))


def _collect(root, kind="result", now=10.0, fetch_rc=0, stops=None):
    stops = [] if stops is None else stops
    return L.collect(root, cp=CP, poller=lambda c: (kind, None), stopper=lambda n, i, env="main": stops.append((n, i)),
                     verifier=lambda i: {"verified": True}, fetch=lambda d: (d.mkdir(parents=True), {"returncode": fetch_rc})[1],
                     export=lambda r: {"guard": {}, "admission": {"start-1": 1.0}}, now=now,
                     cells={"taskhead-learned-n32-s0": {}, "taskhead-learned-n32-s1": {}}, registry={}, schema={},
                     validate=lambda *a: None)


def test_collect_pending_does_nothing_and_terminal_stops_by_bound_id(tmp_path):
    _prov(tmp_path)
    stops = []
    assert "final_shutdown" not in _collect(tmp_path, kind="pending", stops=stops) and stops == []
    rep = _collect(tmp_path, kind="result", stops=stops)
    assert stops == [(L.APP_NAME, SELF)] and rep["final_shutdown"]["status"] == "stopped_verified"
    assert all(c["state"] == "LOST" for c in rep["cells"].values())        # no evidence for either cell -> LOST


def test_collect_past_deadline_stops_and_failed_fetch_is_unavailable(tmp_path):
    _prov(tmp_path)
    stops = []
    rep = _collect(tmp_path, kind="pending", now=1000.0 + L.COLLECT_GRACE_S + 1, fetch_rc=1, stops=stops)
    assert stops and all(c["state"] == "UNAVAILABLE" for c in rep["cells"].values())


def test_collect_refuses_without_a_bound_id(tmp_path):
    _prov(tmp_path, deployed_app_id="")
    with pytest.raises(SystemExit, match="bound app id"):
        _collect(tmp_path)


# ---- reading rules -----------------------------------------------------------------------------------------------

def _rows(acc: dict, seed: int, hash_salt: str = "") -> list:
    """256 episodes x 4 queries per intervention; acc[iv] = fraction of episodes fully correct (0..1)."""
    rows = []
    for iv, a in acc.items():
        for e in range(256):
            for q in range(4):
                ok = e < int(a * 256)
                rows.append({"batch": e // 16, "episode": e % 16, "episode_hash": f"h{seed}-{e}{hash_salt}", "query": q,
                             "key": q, "label": 1, "pred": 1 if ok else 2, "correct": ok, "intervention": iv})
    return rows


GOOD = {"none": 0.6, "bank_derange": 0.0, "read_offset": 0.0, "coord_shuffle": 0.1, "query_off": 0.0}
NO_BANK = {"none": 0.6, "bank_derange": 0.6, "read_offset": 0.0, "coord_shuffle": 0.1, "query_off": 0.0}
RESID = {"none": 0.07, "bank_derange": 0.07, "read_offset": 0.02, "coord_shuffle": 0.05, "query_off": 0.02}
OK = {"taskhead-learned-n32-s0": {"state": "COMPLETE", "validation": "valid"},
      "taskhead-learned-n32-s1": {"state": "COMPLETE", "validation": "valid"}}


def _decide(t_acc, states=OK, salt=""):
    t = {s: _rows(t_acc, int(s), salt) for s in ("0", "1")}
    r = {s: _rows(RESID, int(s)) for s in ("0", "1")}
    return READ.decide(states, t, r, P2D, P2G)


def test_reading_gain_with_and_without_the_reused_bank_criterion():
    assert _decide(GOOD)["reading"] == READ.GAIN_B
    assert _decide(NO_BANK)["reading"] == READ.GAIN_NO_B


def test_reading_not_shown_and_unavailable_paths():
    assert _decide(RESID)["reading"].startswith("rescue by the taskhead recipe not shown")
    assert "probe unavailable: seed 0" in _decide(GOOD, salt="x")["reading"]          # hashes differ: never re-paired
    failed = {**OK, "taskhead-learned-n32-s1": {"state": "FAILED", "reason": "worker exit 1"}}
    assert _decide(GOOD, states=failed)["reading"].startswith("probe unavailable: taskhead-learned-n32-s1: FAILED")
    lost = {**OK, "taskhead-learned-n32-s0": {"state": "COMPLETE", "validation": "probe schema: x"}}
    assert "probe unavailable" in _decide(GOOD, states=lost)["reading"]


def test_reading_comparator_hashes_match_the_bound_files_and_the_amendment():
    import hashlib
    for s, (rel, h) in READ.COMPARATOR.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == h
    spec = json.loads((ROOT / READ.AMENDMENT_SPEC).read_text())
    assert spec["outputs"]["per_example_results.jsonl"] == READ.COMPARATOR["1"][1]


# ---- ledger ------------------------------------------------------------------------------------------------------

def test_ledger_prices_the_full_deadline_from_v6():
    v6 = json.loads(LEDGER.V6.read_text())
    frozen = json.loads((ROOT / L.LEDGER_FILE).read_text())
    assert frozen == LEDGER.ledger()
    assert frozen["deadline_s"] == v6["slots"]["learned-n32"]["reserve_life_s"] == L.deadline_s(frozen)
    src = (ROOT / "scripts/sgm-p2p5-pk6-packed-campaign-priced-estimate.py").read_text()
    assert "GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S, CORES, GIB = 0.000694, 0.0000131, 0.00000222, 8, 64" in src
    gpu = (frozen["deadline_s"] + 240) * LEDGER.rate(2.0)
    assert abs(frozen["items_usd"]["gpu_app_full_deadline"] - gpu) < 1e-9 and frozen["cap_request_usd"] >= gpu + 2
    for bad in (math.nan, math.inf, True, 0, -1):
        with pytest.raises(SystemExit):
            L.deadline_s({"deadline_s": bad})
