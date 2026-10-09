"""Model-free / cloud-free CPU checks for the B3 package (B2 recipe + feature_shift=2; proposal v0.3).
Every test runs with cloud SENTINELS (Modal Dict/Function/FunctionCall lookups raise), a fake deadline
killer (no real SIGKILL sleeper) and a fake Volume commit. Training checks use the TINY backbone on CPU only."""

import hashlib
import importlib.util
import inspect
import json
import types
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load("scripts/sgm-p2p5-b3-shift2-fill-long-run-train.py", "b3_train")
B2 = _load("scripts/sgm-p2p5-b2-occupied-fill-long-run-train.py", "b2_train_ref")
R = _load("modal-runners/modal-m4-sgm-p2p5-b3-shift2-fill-long-run-runner.py", "b3_runner")
R2 = _load("modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-resume-runner.py", "b2_resume_ref")
PROBE = ROOT / R.INPUT_MANIFEST


def _cloud_sentinel(*a, **k):
    raise RuntimeError("CLOUD ACCESS ATTEMPTED")


class _Proc:
    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """No test may reach Modal, kill pytest, or commit a real Volume (codex 22400/22473)."""
    for obj, attr in ((R.modal.Dict, "from_name"), (R.modal.Function, "from_name"), (R.modal.FunctionCall, "from_id")):
        monkeypatch.setattr(obj, attr, _cloud_sentinel)
    monkeypatch.setattr(R, "deadline_killer", lambda target, seconds: _Proc())
    monkeypatch.setattr(R, "safe_commit", lambda: 0)


# ---------- training script (B3 = B2 + feature_shift 2) ----------

def test_config_is_b2_plus_feature_shift2_only():
    assert hashlib.sha256(PROBE.read_bytes()).hexdigest() == B.STAGE_A.PROBE_S0_MANIFEST_SHA256
    base = json.loads(PROBE.read_text())["pilot_config"]
    b3, b2 = asdict(B.arm_config(base, "cuda")), asdict(B2.arm_config(base, "cuda"))
    assert b3["sgm"] == {**B2.FILL, "feature_shift": 2} == B.SGM_OVERRIDES
    assert {k: v for k, v in b3.items() if k != "sgm"} == {k: v for k, v in b2.items() if k != "sgm"}
    assert {k: v for k, v in b3["sgm"].items() if k != "feature_shift"} == b2["sgm"]
    for bad in ({"steps": 100}, {"eval_every": 25}, {"sgm": {"address_scale": 4.0}}, {"lr": 3e-4}):
        with pytest.raises(ValueError):
            B.arm_config({**base, **bad}, "cuda")


def test_shift2_widens_adapter_inputs_to_2048_without_qwen():
    from memsub.sgm.config import SGMConfig
    from memsub.sgm.layer_adapter import SGMLayerAdapter
    from memsub.sgm.pinned_pretrained_qwen3_backbone import P2P5_SGM_DEFAULTS
    mc = types.SimpleNamespace(hidden_size=1024, num_hidden_layers=28, model_type="qwen3")
    cfg = SGMConfig(**{**P2P5_SGM_DEFAULTS, **B.SGM_OVERRIDES, "address_mode": "learned"}).resolve(mc)
    a = SGMLayerAdapter(cfg, 6)
    assert cfg.feature_shift == 2 and a.q_proj.in_features == 2048
    n = sum(sum(p.numel() for p in SGMLayerAdapter(cfg, l).parameters()) for l in cfg.selected_layers)
    assert n + 4 * 4 * 32 * 64 + 64 == 3_744_604                      # proposal v0.3 / codex 22479


def test_b3_identity_differs_from_b2_and_refuses_b2_contents(tmp_path):
    pcfg = _tiny()
    i3, i2 = B.run_identity(pcfg, None), B2.run_identity(pcfg, None)
    assert i3["campaign"] != i2["campaign"] and i3["script_sha256"] != i2["script_sha256"]
    d = tmp_path / "B3"
    B2.prepare_out(d, pcfg, i2)                                     # a B2-identity run dir
    with pytest.raises(SystemExit):
        B.prepare_out(d, pcfg, i3)


def _tiny():
    from memsub.sgm.synthetic_pilot import PilotConfig
    return PilotConfig(arm="learned", readout="taskhead", n_bindings=4, n_queries=2, filler_len=4, batch=4,
                       eval_batches=1, seed=0, steps=4, eval_every=2, sgm=dict(B.SGM_OVERRIDES))


def _params_sha(out):
    return hashlib.sha256((out / "trained_parameters.safetensors").read_bytes()).hexdigest()


def _rows_wo_time(out):
    return [{k: v for k, v in json.loads(x).items() if k != "sec_per_step"}
            for x in (out / "routing_telemetry.jsonl").read_text().splitlines()]


def test_tiny_shift2_fill_runs_finite_and_crash_after_checkpoint_resumes_identically(tmp_path, monkeypatch):
    ref = tmp_path / "ref" / "B3"
    B.run_b3(_tiny(), ref, {}, checkpoint_every=2)
    rows = _rows_wo_time(ref)
    assert rows and all(isinstance(r.get("loss", 0.0), float) for r in rows)
    out = tmp_path / "crash" / "B3"
    real = B.save_atomic

    def save_then_crash(state, path):
        real(state, path)
        if state["step"] == 2:
            raise RuntimeError("simulated preemption right after the step-2 checkpoint")
    monkeypatch.setattr(B, "save_atomic", save_then_crash)
    with pytest.raises(RuntimeError):
        B.run_b3(_tiny(), out, {}, checkpoint_every=2)
    monkeypatch.setattr(B, "save_atomic", real)
    B.run_b3(_tiny(), out, {}, checkpoint_every=2)
    starts = [json.loads(x) for x in out.with_name("B3.starts.jsonl").read_text().splitlines()]
    assert [(s["start"], s["resume_step"]) for s in starts] == [(1, None), (2, 2)]
    assert _params_sha(out) == _params_sha(ref) and _rows_wo_time(out) == _rows_wo_time(ref)
    assert (out / "b3_result.json").exists() and "b3_identity" in B.load(out / "resume.pt")


# ---------- runner ----------

def test_ledger_matches_proposal_v03():
    """v0.3 rate; window amended to campaign + watch grace + cleanup = 23,820 s (package audit)."""
    L = R.ledger()
    assert L["rate_usd_s"] == pytest.approx(0.00067854) and L["window_s"] == 23_400 + 120 + 300
    assert L["reservation_usd"] == pytest.approx(16.2628228, abs=1e-6)
    assert L["headroom_usd"] == pytest.approx(0.7371772, abs=1e-6) and L["cap_usd"] == 17.0


def test_fresh_identities_and_bound_memsub():
    assert len({R.DEPLOY_APP, R.START_DICT, R.VOLUME_NAME} & {R2.DEPLOY_APP, R2.START_DICT, R2.VOLUME_NAME}) == 0
    assert R.SCRIPT.endswith("b3-shift2-fill-long-run-train.py") and R.EXPECT_MEMSUB_SHA256 == R2.EXPECT_MEMSUB_SHA256
    assert R.local_memsub_sha256() == R.EXPECT_MEMSUB_SHA256


@pytest.mark.parametrize("name", ["deadline_killer", "kill_group", "cancel_killer", "supervise_child",
                                  "campaign_dir_problem", "claim_start", "safe_commit", "local_memsub_sha256", "call_state"])
def test_shared_helpers_are_verbatim_b2(name):
    strip = lambda f: inspect.getsource(f).replace("# verbatim B2", "").replace(" ", "")   # noqa: E731
    mod3 = _load("modal-runners/modal-m4-sgm-p2p5-b3-shift2-fill-long-run-runner.py", "b3_runner_pristine")
    assert strip(getattr(mod3, name)) == strip(getattr(R2, name))


class _Dict:
    def __init__(self, d=None):
        self.d = dict(d or {})

    def put(self, k, v, skip_if_exists=False):
        if skip_if_exists and k in self.d:
            return False
        self.d[k] = v
        return True

    def get(self, k):
        return self.d.get(k)

    def keys(self):
        return list(self.d)


class _Vol:
    def reload(self):
        pass


def _worker(tmp_path, monkeypatch, starts, rc=0, versions_ok=True, raise_in=None, deadline=10_000.0, now=0.0):
    monkeypatch.setattr(R, "RUN_DIR", str(tmp_path / "run"))

    def versions():
        if raise_in == "versions":
            raise ValueError("boom")
        return {"ok": versions_ok, "got": {"torch": "x"}}
    popen = lambda *a, **k: types.SimpleNamespace(pid=1)     # noqa: E731
    return R.worker(deadline, starts=starts, vol=_Vol(), versions=versions, popen=popen,
                    supervise=lambda *a, **k: (rc, 0), clock=lambda: now)


@pytest.mark.parametrize("rc,reason", [(0, "completed"), ("timeout", "deadline"), (1, "run-side failure rc 1")])
def test_worker_marks_terminal_on_every_non_interruption_outcome(tmp_path, monkeypatch, rc, reason):
    st = _Dict({R.DEADLINE_KEY: 10_000.0})
    res = _worker(tmp_path, monkeypatch, st, rc=rc)
    assert res["returncode"] == rc and res["start"] == "start-1" and st.d[R.TERMINAL_KEY]["reason"] == reason
    again = _worker(tmp_path, monkeypatch, st)                       # any later start refuses: no retry
    assert "campaign is terminal" in again["refused"] and "start-2" not in st.d


@pytest.mark.parametrize("case", ["versions", "exception", "deadline_mismatch", "populated_run_dir", "budget"])
def test_worker_refusals_and_exceptions_are_terminal(tmp_path, monkeypatch, case):
    st = _Dict({R.DEADLINE_KEY: 10_000.0 if case != "deadline_mismatch" else 1.0})
    if case == "populated_run_dir":
        (tmp_path / "run").mkdir(); (tmp_path / "run" / "x").write_text("x")
    if case == "budget":
        st.d.update({f"start-{k}": {} for k in (1, 2, 3)})
    res = _worker(tmp_path, monkeypatch, st, versions_ok=case != "versions", raise_in="versions" if case == "exception" else None)
    assert "refused" in res and R.TERMINAL_KEY in st.d


def test_platform_interruption_leaves_no_marker_and_the_next_start_resumes_same_campaign(tmp_path, monkeypatch):
    st = _Dict({R.DEADLINE_KEY: 10_000.0})
    monkeypatch.setattr(R, "RUN_DIR", str(tmp_path / "run"))
    assert R.claim_start(st, {}) == "start-1"                          # start-1 admitted ...
    R.campaign_dir_problem(tmp_path / "run", "start-1", R.campaign_identity(10_000.0))   # ... wrote campaign.json
    assert R.TERMINAL_KEY not in st.d                                  # ... then the container was lost
    res = _worker(tmp_path, monkeypatch, st, rc=0)
    assert res["start"] == "start-2" and st.d[R.TERMINAL_KEY]["reason"] == "completed"


def test_worker_refuses_at_entry_past_deadline_without_claiming(tmp_path, monkeypatch):
    st = _Dict({R.DEADLINE_KEY: 100.0})
    res = _worker(tmp_path, monkeypatch, st, deadline=100.0, now=50.0)
    assert "refused" in res and "start-1" not in st.d


def test_precheck_and_deadline_are_fresh_and_write_once():
    assert R.precheck_problem([], set()) is None
    assert "not empty" in R.precheck_problem(["start-1"], set())
    assert "not empty" in R.precheck_problem([], {"B3/resume.pt"})
    st = _Dict()
    d = R.set_campaign_deadline(st, 1000.0)
    assert d == 1000.0 + R.CAMPAIGN_S
    with pytest.raises(SystemExit):
        R.set_campaign_deadline(st, 2000.0)


def test_gate_reads_b3_result(tmp_path):
    (tmp_path / "B3").mkdir()
    (tmp_path / "B3" / "b3_result.json").write_text(json.dumps({"status": "valid", "memory_used": False, "band_at_end": "partial"}))
    assert R.gate_ok("B3", tmp_path, {"returncode": 0})[0] is True
    assert R.gate_ok("B3", tmp_path, {"returncode": 1})[0] is False


def test_watch_stops_on_return_or_deadline_never_on_unknown(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"call_id": "fc-x", "deadline": 1000.0, "app_id": "ap-x"}))
    seq, t = iter([("unknown", "e"), ("running", None), ("done", {"returncode": 0})]), [0.0]
    r = R.watch(tmp_path, poll_s=60.0, state=lambda c: next(seq), cleanup=lambda out: {"status": "stopped_verified", "app_id": "ap-x"},
                clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s))
    assert r["status"] == "stopped_verified" and json.loads((tmp_path / "watch.json").read_text())["reason"] == "call returned"


class _DeployedAppCli:
    """Realistic non-interactive Modal CLI for a DEPLOYED app: `app stop` without --yes aborts (B2's failure)."""
    def __init__(self):
        self.calls, self.stopped = [], False

    def __call__(self, argv, capture_output, text, timeout, check):
        args = argv[3:]
        self.calls.append(args)
        if args[:2] == ["app", "stop"]:
            if "--yes" not in args:
                return types.SimpleNamespace(returncode=1, stdout="", stderr="Aborted. rerun with --yes")
            self.stopped = True
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[:2] == ["app", "list"]:
            state = "stopped" if self.stopped else "deployed"
            return types.SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(
                [{"app_id": "ap-b3", "description": R.DEPLOY_APP, "state": state, "tasks": "0"}]))
        if args[:2] == ["container", "list"]:
            return types.SimpleNamespace(returncode=0, stderr="", stdout="[]")
        raise AssertionError(f"unexpected CLI call {args}")


def test_cleanup_uses_yes_and_verifies_a_deployed_app(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"app_id": "ap-b3"}))
    cli = _DeployedAppCli()
    t = [0.0]                                    # fake clock advanced by the fake sleep: never a real-time spin
    rec = R.cleanup_verify(tmp_path, run=cli, sleep=lambda s: t.__setitem__(0, t[0] + s), clock=lambda: t[0])
    assert ["app", "stop", "--yes", "ap-b3"] in cli.calls and rec["stop"]["returncode"] == 0
    assert rec["status"] == "stopped_verified"


def test_cleanup_recheck_loop_is_bounded_even_if_sleep_does_not_wait(tmp_path):
    """Regression for the 2026-10-10 local OOM: a frozen clock + no-op sleep + never-verified app must stop at
    MAX_CHECKS. The fake verifier itself fails after 50 calls, so removing the cap fails fast instead of spinning."""
    (tmp_path / "run.json").write_text(json.dumps({"app_id": "ap-b3"}))
    calls = []

    def verify(app_id, modal_json):
        calls.append(app_id)
        assert len(calls) <= 50, "re-check loop is unbounded"
        return {"app_id": app_id, "verified": False}

    rec = R.cleanup_verify(tmp_path, run=_DeployedAppCli(), budget_s=300.0, wait_s=20.0, sleep=lambda s: None,
                           clock=lambda: 0.0, cp=types.SimpleNamespace(verify_stopped=verify))
    assert rec["status"] == "shutdown_unresolved" and len(rec["checks"]) == 300 // 20 + 2


def test_cleanup_without_yes_would_leave_the_deployed_app_unresolved(tmp_path, monkeypatch):
    """Regression for B2: the same fake CLI with the stop issued WITHOUT --yes never verifies."""
    (tmp_path / "run.json").write_text(json.dumps({"app_id": "ap-b3"}))
    cli = _DeployedAppCli()
    no_yes = lambda argv, **k: cli([a for a in argv if a != "--yes"], **k)   # noqa: E731
    t = [0.0]
    rec = R.cleanup_verify(tmp_path, run=no_yes, budget_s=60.0, wait_s=20.0, sleep=lambda s: t.__setitem__(0, t[0] + s),
                           clock=lambda: t[0])
    assert rec["stop"]["returncode"] == 1 and rec["status"] == "shutdown_unresolved"


def test_cloud_sentinels_block_every_lookup():
    for f in (lambda: R.modal.Dict.from_name("x"), lambda: R.modal.Function.from_name("a", "b"),
              lambda: R.modal.FunctionCall.from_id("fc")):
        with pytest.raises(RuntimeError, match="CLOUD ACCESS ATTEMPTED"):
            f()


# ---------- fail-closed listing / collect and contained worker failures (codex 22515) ----------

class _ListVol:
    """Volume fake: `listdir` raises `exc` or returns FILE entries for `files` {rel: bytes}."""
    def __init__(self, files=None, exc=None):
        self.files, self.exc = files or {}, exc

    def listdir(self, path, recursive=False):
        if self.exc is not None:
            raise self.exc
        return [types.SimpleNamespace(path=f"{R.RUN_REL}/{rel}", type=R.modal.volume.FileEntryType.FILE) for rel in self.files]

    def read_file(self, path):
        return [self.files[path.removeprefix(R.RUN_REL + "/")]]


@pytest.mark.parametrize("exc", [R.modal.exception.NotFoundError("no such path"), FileNotFoundError("gone")])
def test_volume_listing_absent_means_fresh(exc):
    assert R._volume_files(_ListVol(exc=exc)) == []


@pytest.mark.parametrize("exc", [TimeoutError("slow"), PermissionError("denied"), RuntimeError("rpc")])
def test_volume_listing_errors_fail_closed_in_precheck_and_collect(tmp_path, exc):
    with pytest.raises(type(exc)):
        R._volume_files(_ListVol(exc=exc))
    assert "listing failed" in R.precheck(starts=_Dict(), vol=_ListVol(exc=exc))
    (tmp_path / "call_result.json").write_text(json.dumps({"returncode": 0}))
    rec = R.collect(tmp_path, vol=_ListVol(exc=exc))
    assert rec["ok"] is False and "listing failed" in rec["why"]


def test_collect_never_passes_on_stale_local_results(tmp_path):
    stale = tmp_path / "volume" / R.RUN_REL / "B3"
    stale.mkdir(parents=True)
    good = json.dumps({"status": "valid", "memory_used": True, "band_at_end": "partial"}).encode()
    (stale / "b3_result.json").write_bytes(good)                       # left by an earlier collect
    (tmp_path / "call_result.json").write_text(json.dumps({"returncode": 0}))
    rec = R.collect(tmp_path, vol=_ListVol(exc=R.modal.exception.NotFoundError("absent")))
    assert rec["ok"] is False and rec["files"] == 0 and "not fetched" in rec["why"]
    rec = R.collect(tmp_path, vol=_ListVol(files={"B3/b3_result.json": good, "B3/resume.pt": b"x"}))
    assert rec["ok"] is True and rec["files"] == 1                      # fetched now; resume.pt skipped


class _FailingTerminalDict(_Dict):
    def put(self, k, v, skip_if_exists=False):
        if k == R.TERMINAL_KEY:
            raise ConnectionError("dict unavailable")
        return super().put(k, v, skip_if_exists)


class _CountingKiller:
    def __init__(self):
        self.created, self.cancelled = 0, 0

    def __call__(self, target, seconds):
        self.created += 1
        outer = self

        class P(_Proc):
            def wait(self, timeout=None):
                outer.cancelled += 1
                return 0
        return P()


def test_worker_contains_a_failed_dict_lookup_and_cancels_its_watchdog(tmp_path, monkeypatch):
    killer = _CountingKiller()
    monkeypatch.setattr(R, "deadline_killer", killer)
    res = _worker(tmp_path, monkeypatch, None)                          # Dict.from_name -> cloud sentinel raises
    assert res["refused"] == "worker exception RuntimeError" and res["terminal_write_errors"] == ["no start Dict"]
    assert (killer.created, killer.cancelled) == (1, 1)


@pytest.mark.parametrize("case", ["versions", "exception", "completed"])
def test_worker_reports_a_failed_terminal_write_instead_of_raising(tmp_path, monkeypatch, case):
    killer = _CountingKiller()
    monkeypatch.setattr(R, "deadline_killer", killer)
    st = _FailingTerminalDict({R.DEADLINE_KEY: 10_000.0})
    res = _worker(tmp_path, monkeypatch, st, versions_ok=case != "versions", raise_in="versions" if case == "exception" else None)
    assert res["terminal_write_errors"] and "ConnectionError" in res["terminal_write_errors"][0]
    assert (res.get("returncode") == 0) if case == "completed" else ("refused" in res)
    assert (killer.created, killer.cancelled) == (1, 1)
