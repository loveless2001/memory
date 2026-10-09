"""CPU checks for the B2 RESUME runner v0.4 (deploy + spawn ONE start-2 call from the update-750 checkpoint):
helpers verbatim from the cleared v0.3 runner, same campaign identity, start-1's recorded identity still
accepted by the unchanged train script, resume-only start rules, local precheck, write-once resume
deadline, spawn order, call-state/watch backstop, collect without resume.pt, ledger and launch order."""

import hashlib
import importlib.util
import inspect
import json
import subprocess
from pathlib import Path

import modal
import pytest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "plans/261009-1135-m4-sgm-p2p5-b2-occupied-fill-long-run"
SNAP = PLAN / "b2-run-v1-start1-volume-snapshot"


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _load("modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-resume-runner.py", "b2_resume_runner")
R3 = _load("modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-long-run-runner.py", "b2_runner_v03")
R1 = _load("modal-runners/modal-m4-sgm-p2p5-b1-occupied-fill-retention-screen-runner.py", "b1_runner")
B = _load("scripts/sgm-p2p5-b2-occupied-fill-long-run-train.py", "b2_train")
CAMPAIGN = json.loads((SNAP / "campaign.json").read_text())
D0 = CAMPAIGN["deadline"]


def test_shared_helpers_are_verbatim_v03():
    for name in ("_versions_ok", "deadline_killer", "kill_group", "cancel_killer", "supervise_child",
                 "campaign_dir_problem", "claim_start", "safe_commit", "local_memsub_sha256", "gate_ok", "cleanup_verify"):
        assert inspect.getsource(getattr(R, name)) == inspect.getsource(getattr(R3, name)), name


def test_same_campaign_new_deploy_name():
    for k in ("START_DICT", "VOLUME_NAME", "RUN_DIR", "EXPECT_MEMSUB_SHA256", "BASE_IMAGE_ID", "EXPECT_VERSIONS", "GPU",
              "CPU_CORES", "MEMORY_GIB", "ARMS", "SCRIPT", "STAGE_A_SCRIPT", "INPUT_MANIFEST", "MAX_STARTS", "MIN_START_S",
              "END_MARGIN_S", "COMMIT_EVERY_S", "CLEANUP_S", "CAP_USD", "GPU_USD_S", "CPU_USD_CORE_S", "MEM_USD_GIB_S"):
        assert getattr(R, k) == getattr(R3, k), k
    assert R.CAMPAIGN_APP == R3.APP_NAME and R.DEPLOY_APP not in (R3.APP_NAME, R1.APP_NAME)
    assert R.RUN_DIR == "/vol/" + R.RUN_REL and R.FUNCTION_S == R.RESUME_S and R.MIN_START_S > R.END_MARGIN_S
    run = json.loads((PLAN / "b2-run-v1/run.json").read_text())
    assert run["app_id"] == R.START1_APP_ID and R.local_memsub_sha256() == R.EXPECT_MEMSUB_SHA256


def test_start1_record_is_still_this_campaign_and_train_identity():
    assert R.campaign_identity(D0) == CAMPAIGN
    probe = ROOT / R.INPUT_MANIFEST
    sha = hashlib.sha256(probe.read_bytes()).hexdigest()
    pcfg = B.arm_config(json.loads(probe.read_text())["pilot_config"], "cuda")
    assert B.run_identity(pcfg, sha) == json.loads((SNAP / "B2_identity.json").read_text())   # start-2 accepts the run dir


def test_ledger_within_cap():
    led = R.ledger()
    rows = [0.08945059, 0.92192733, 0.12103251, 0.18920088, 1.95000912, 0.25600120, 0.17101618, 1.76258743, 0.23139609]
    assert R.START1_PROVISIONAL_USD == pytest.approx(sum(rows), abs=1e-8)
    assert led["reservation_usd"] == pytest.approx((R.RESUME_S + R.STARTUP_S) * led["rate_usd_s"])
    assert led["campaign_bound_usd"] == pytest.approx(R.START1_PROVISIONAL_USD + led["reservation_usd"])
    assert led["campaign_bound_usd"] <= led["cap_usd"] == 17.0


class _Dict:
    def __init__(self, **kw):
        self.d = dict(kw)

    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self.d:
            return False
        self.d[k] = v
        return True

    def get(self, k, default=None):
        return self.d.get(k, default)


def _campaign_dict(**extra):
    return _Dict(deadline=D0, **{"start-1": {"t": 1.0}}, **extra)


def _run_dir(tmp_path, campaign=CAMPAIGN, ckpt=True):
    run = tmp_path / "run"
    (run / "B2").mkdir(parents=True)
    (run / "campaign.json").write_text(json.dumps(campaign))
    if ckpt:
        (run / "B2" / "resume.pt").write_bytes(b"x")
    return run


def test_resume_start_rules(tmp_path):
    d = _campaign_dict(**{R.RESUME_KEY: 500.0})
    assert R.claim_start(d, {}) == "start-2"
    run = _run_dir(tmp_path)
    assert R.resume_start_problem("start-2", d.get, 500.0, run, "B2") is None
    assert R.resume_start_problem(None, d.get, 500.0, run, "B2")
    assert R.resume_start_problem("start-1", d.get, 500.0, run, "B2")
    assert R.resume_start_problem("start-2", d.get, 501.0, run, "B2")                       # not the write-once deadline
    assert R.resume_start_problem("start-2", _Dict(**{R.RESUME_KEY: 500.0}).get, 500.0, run, "B2")
    assert R.resume_start_problem("start-2", d.get, 500.0, _run_dir(tmp_path / "a", {**CAMPAIGN, "deadline": 1.0}), "B2")
    assert R.resume_start_problem("start-3", d.get, 500.0, _run_dir(tmp_path / "b", ckpt=False), "B2")
    assert not (tmp_path / "b" / "run" / "B2" / "identity.json").exists()                   # refusal writes nothing
    assert [R.claim_start(d, {}) for _ in range(3)] == ["start-3", None, None]


class _Entry:
    def __init__(self, path):
        self.path, self.type = path, modal.volume.FileEntryType.FILE


class _Vol:
    def __init__(self, files):
        self.files = {f"{R.RUN_REL}/{k}": v for k, v in files.items()}

    def listdir(self, path, recursive=False):
        assert path == R.RUN_REL and recursive
        return [_Entry(p) for p in self.files]

    def read_file(self, path):
        yield self.files[path]


def _vol(**over):
    files = {"campaign.json": json.dumps(CAMPAIGN).encode(), "B2/resume.pt": b"ckpt", "B2/identity.json": b"{}"}
    files.update(over)
    return _Vol({k: v for k, v in files.items() if v is not None})


def test_precheck_problem():
    files, camp = R.volume_state(_vol())
    assert R.precheck_problem(_campaign_dict().get, files, camp) is None
    assert R.precheck_problem(_Dict(deadline=D0).get, files, camp)                            # no start-1 claim
    for k in ("start-2", "start-3", R.RESUME_KEY):
        assert R.precheck_problem(_campaign_dict(**{k: 1}).get, files, camp)
    assert R.precheck_problem(_campaign_dict().get, *R.volume_state(_vol(**{"B2/resume.pt": None})))
    assert R.precheck_problem(_campaign_dict().get, *R.volume_state(_vol(**{"campaign.json": None})))
    bad = json.dumps({**CAMPAIGN, "app": "other"}).encode()
    assert R.precheck_problem(_campaign_dict().get, *R.volume_state(_vol(**{"campaign.json": bad})))


def test_resume_deadline_is_write_once():
    d = _campaign_dict()
    assert R.set_resume_deadline(d, 1000.0) == 1000.0 + R.RESUME_S
    with pytest.raises(SystemExit):
        R.set_resume_deadline(d, 2000.0)
    assert d.get(R.RESUME_KEY) == 1000.0 + R.RESUME_S


class _Fn:
    def __init__(self):
        self.calls = []

    def spawn(self, deadline):
        self.calls.append(deadline)
        return type("FC", (), {"object_id": "fc-test"})()


def _apps(n):
    return lambda args: [{"app_id": f"ap-{i}", "description": R.DEPLOY_APP, "state": "deployed"} for i in range(n)] + \
        [{"app_id": R.START1_APP_ID, "description": R.CAMPAIGN_APP, "state": "stopped"}]


def test_spawn_records_app_then_deadline_then_call(tmp_path):
    d, fn = _campaign_dict(), _Fn()
    m = R.spawn_resume(tmp_path / "o", starts=d, vol=_vol(), fn=fn, modal_json=_apps(1), clock=lambda: 100.0)
    assert (m["app_id"], m["call_id"], m["outcome"]) == ("ap-0", "fc-test", "spawned")
    assert fn.calls == [100.0 + R.RESUME_S] == [d.get(R.RESUME_KEY)]
    assert json.loads((tmp_path / "o" / "run.json").read_text())["call_id"] == "fc-test"
    with pytest.raises(SystemExit):                       # a second resume: the precheck sees RESUME_KEY
        R.spawn_resume(tmp_path / "o2", starts=d, vol=_vol(), fn=fn, modal_json=_apps(1), clock=lambda: 200.0)
    with pytest.raises(FileExistsError):
        R.spawn_resume(tmp_path / "o", starts=_campaign_dict(), vol=_vol(), fn=fn, modal_json=_apps(1))
    assert len(fn.calls) == 1


@pytest.mark.parametrize("n", [0, 2])
def test_spawn_needs_exactly_one_deployed_app_before_any_deadline(tmp_path, n):
    d, fn = _campaign_dict(), _Fn()
    with pytest.raises(SystemExit):
        R.spawn_resume(tmp_path / "o", starts=d, vol=_vol(), fn=fn, modal_json=_apps(n))
    assert d.get(R.RESUME_KEY) is None and fn.calls == []


def _from_id(behaviour):
    class _FC:
        def get(self, timeout=None):
            assert timeout == 0
            if isinstance(behaviour, Exception):
                raise behaviour
            return behaviour
    return lambda cid: _FC()


def test_call_state():
    assert R.call_state("fc", _from_id(TimeoutError())) == ("running", None)
    assert R.call_state("fc", _from_id({"returncode": 0}))[0] == "done"
    assert R.call_state("fc", _from_id(ConnectionError("net")))[0] == "unknown"
    assert R.call_state("fc", _from_id(modal.exception.FunctionTimeoutError("t")))[0] == "unknown"
    assert R.call_state("fc", _from_id("text"))[0] == "unknown"


def _watch(tmp_path, states, deadline=1000.0, step=60.0):
    out = tmp_path / "w"
    out.mkdir(parents=True)
    (out / "run.json").write_text(json.dumps({"call_id": "fc", "deadline": deadline, "app_id": "ap-x"}))
    clock, seen, cleaned = {"t": 0.0}, iter(states), []

    def state(cid):
        return next(seen, states[-1])
    rec = R.watch(out, poll_s=step, state=state, cleanup=lambda o: cleaned.append(clock["t"]) or {"status": "ok"},
                  clock=lambda: clock["t"], sleep=lambda s: clock.__setitem__("t", clock["t"] + s))
    return out, clock["t"], cleaned, rec


def test_watch_stops_on_return_or_deadline_never_on_unknown(tmp_path):
    out, t, cleaned, _ = _watch(tmp_path / "a", [("running", None), ("unknown", "net"), ("done", {"returncode": 0})])
    assert cleaned == [120.0] and json.loads((out / "call_result.json").read_text()) == {"returncode": 0}
    out, t, cleaned, _ = _watch(tmp_path / "b", [("unknown", "net")])
    assert cleaned and cleaned[0] >= 1000.0 + R.END_MARGIN_S and not (out / "call_result.json").exists()
    out, t, cleaned, _ = _watch(tmp_path / "c", [("running", None)])
    assert cleaned[0] >= 1000.0 + R.END_MARGIN_S and "deadline" in json.loads((out / "watch.json").read_text())["reason"]


def test_collect_skips_checkpoint_and_gates(tmp_path):
    ok = json.dumps({"status": "valid", "memory_used": False, "band_at_end": "kept"}).encode()
    vol = _vol(**{"B2/b2_result.json": ok, "B2/resume.pt.tmp": b"t"})
    (tmp_path / "call_result.json").write_text(json.dumps({"returncode": 0}))
    rec = R.collect(tmp_path, vol=vol)
    got = tmp_path / "volume" / R.RUN_REL
    assert rec["ok"] and (got / "B2" / "b2_result.json").exists() and (got / "campaign.json").exists()
    assert not (got / "B2" / "resume.pt").exists() and not (got / "B2" / "resume.pt.tmp").exists()
    (tmp_path / "call_result.json").unlink()
    assert not R.collect(tmp_path, vol=vol)["ok"]               # no recorded call result -> not gated ok


def test_cleanup_budget_unchanged(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"app_id": "ap-test"}))
    clock = {"t": 0.0}

    def hang(cmd, timeout, **kw):
        clock["t"] += timeout
        raise subprocess.TimeoutExpired(cmd, timeout)
    rec = R.cleanup_verify(tmp_path, cp=_load(R.CONTROL_LOGIC_FILE, "cp"), run=hang,
                           sleep=lambda s: clock.__setitem__("t", clock["t"] + s), clock=lambda: clock["t"])
    assert rec["status"] == "shutdown_unresolved" and clock["t"] <= R.CLEANUP_S


def test_launch_script_order_and_bounds():
    sh = (PLAN / "launch-b2-resume-once.sh").read_text()
    steps = [sh.index(s) for s in ('"$RN" precheck', '-m modal deploy "$RN"', '"$RN" spawn-resume', '"$RN" watch')]
    assert steps == sorted(steps)
    assert 'if [ -e "$OUT" ]' in sh and "dirty tracked tree" in sh and '"$RN" cleanup-verify' in sh
    watch_s = int(sh.split("timeout --signal=KILL ")[-1].split()[0])
    assert watch_s >= R.RESUME_S + R.END_MARGIN_S + R.CLEANUP_S + 60
