"""CPU-only proof runner (codex 21458): every post-deploy failure ends as a FAILED proof with
an app-id-bound fallback stop and a written report; PASS needs a stop inside the intended
window, zero-resource verification and the reaper's bound log marker. Production reaper is
bound to a CPU image carrying the shared logic. All Modal operations are faked."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_registered(path: Path, name: str):
    """File-definition mode: module registered in sys.modules before exec (as the CLI does)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def proof(monkeypatch, tmp_path):
    monkeypatch.chdir(ROOT)
    mod = _load_registered(ROOT / "modal-runners" / "modal-m4-sgm-p2p5-reaper-self-stop-proof.py", "p2p5_proof")
    monkeypatch.setattr(mod, "LOCAL_OUT", str(tmp_path / "proof"))
    return mod


class FakeDict(dict):
    def __init__(self, fail_key=None):
        super().__init__()
        self.fail_key = fail_key

    def put(self, k, v, skip_if_exists=False):
        if k == self.fail_key:
            return False
        if skip_if_exists and k in self:
            return False
        self[k] = v
        return True


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def _run(proof, *, deploy=None, guard=None, stop_at=None, logs=None, lifecycle=None, lookup="ap-proof"):
    clock, stops = Clock(), []
    deploy = deploy or (lambda: SimpleNamespace(stdout="ok", stderr="", returncode=0))

    def lc(app_id):
        if stop_at is not None and clock() >= stop_at(clock):
            return SimpleNamespace(stopped_at=datetime.fromtimestamp(stop_at(clock), timezone.utc), stopped_by="svc")
        return SimpleNamespace(stopped_at=None, stopped_by=None)
    marker = f"M4SGM_REAPER_STOP app={proof.APP_NAME} bound={lookup} reason=deadline passed"
    rep = proof.prove(deploy=deploy, lookup=lambda: lookup, guard=guard or FakeDict(), lifecycle=lifecycle or lc,
                      verify=lambda a: {"verified": True}, stop=lambda a: stops.append(a),
                      logs=logs or (lambda a: f"... {marker} t=1\nEXIT_STATUS=0\n"), clock=clock, sleep=clock.sleep)
    written = json.loads((Path(proof.LOCAL_OUT) / "proof_report.json").read_text())
    assert written["result"] == rep["result"]
    return rep, stops


def test_true_self_stop_inside_the_window_passes_without_any_local_stop(proof):
    deadline_of = lambda c: 1000.0 + proof.DEADLINE_AFTER_DEPLOY_S
    rep, stops = _run(proof, stop_at=lambda c: deadline_of(c) + 30)
    assert rep["result"] == "PASS" and stops == [] and "fallback" not in rep


def test_deploy_timeout_is_a_failed_proof_with_logged_output_and_fallback(proof):
    def deploy():
        raise subprocess.TimeoutExpired("modal deploy", 600, output="partial out", stderr="partial err")
    rep, stops = _run(proof, deploy=deploy)
    assert rep["result"] == "FAILED" and stops == ["ap-proof"]
    log = (Path(proof.LOCAL_OUT) / "deploy.log").read_text()
    assert "partial out" in log and "EXIT_STATUS=deploy_timeout" in log


def test_binding_failure_is_failed_with_app_id_saved_and_fallback(proof):
    rep, stops = _run(proof, guard=FakeDict(fail_key="app_id"))
    prov = json.loads((Path(proof.LOCAL_OUT) / "proof_provenance.json").read_text())
    assert rep["result"] == "FAILED" and stops == ["ap-proof"] and prov["app_id"] == "ap-proof"
    assert "deadline_epoch" in prov                                   # saved before binding


def test_observer_exception_is_failed_with_fallback(proof):
    def lifecycle(app_id):
        raise RuntimeError("lifecycle RPC failed")
    rep, stops = _run(proof, lifecycle=lifecycle)
    assert rep["result"] == "FAILED" and stops == ["ap-proof"] and rep["errors"]


def test_early_unattributed_stop_is_not_a_pass(proof):
    rep, stops = _run(proof, stop_at=lambda c: 1010.0)               # before the bound deadline
    assert rep["result"] == "FAILED" and "outside the intended window" in rep["judgement"] and stops == ["ap-proof"]


def test_stop_without_the_bound_log_marker_is_not_a_pass(proof):
    deadline = 1000.0 + proof.DEADLINE_AFTER_DEPLOY_S
    rep, _ = _run(proof, stop_at=lambda c: deadline + 30, logs=lambda a: "no marker\nEXIT_STATUS=0\n")
    assert rep["result"] == "FAILED" and "log evidence" in rep["judgement"]


def test_claimed_life_covers_the_unbound_abandonment_path(proof):
    b = proof.charge_bound()
    assert proof.PROOF_ABANDON_S + 2 * proof.PERIOD_S <= b["max_app_life_s"] - proof.DEPLOY_TIMEOUT_S


def test_production_reaper_runs_on_a_cpu_image_with_the_shared_logic(monkeypatch):
    monkeypatch.chdir(ROOT)
    run = _load_registered(ROOT / "modal-runners" / "modal-m4-sgm-p2p5-l40s-timing-profile.py", "p2p5_prod_file_mode")
    uid = lambda img: img.local_uuid                         # Modal wraps the image object; compare identity
    assert uid(run.reaper.spec.image) == uid(run.reaper_image) != uid(run.image)
    assert uid(run.run_profile.spec.image) == uid(run.image) and not run.reaper.spec.gpus
    src = (ROOT / "modal-runners" / "modal-m4-sgm-p2p5-l40s-timing-profile.py").read_text()
    assert 'add_local_file(f"modal-runners/{LOGIC_FILE}",\n' in src and src.count('f"/root/{LOGIC_FILE}"') == 2
    assert run.logic().reap_and_stop is not None and run.ENVIRONMENT == run.logic().ENVIRONMENT


def test_runner_module_imports_without_the_logic_file_like_the_image_build_step(tmp_path, monkeypatch):
    """Deploy 18:01 failed: the build step imports the runner before the logic mount exists."""
    import shutil
    lone = tmp_path / "modal-m4-sgm-p2p5-l40s-timing-profile.py"
    shutil.copy(ROOT / "modal-runners" / lone.name, lone)                    # NO logic file beside it
    monkeypatch.chdir(ROOT)
    run = _load_registered(lone, "p2p5_build_step_import")
    assert run._LOGIC is None                                                 # import did not touch the file
    with pytest.raises(FileNotFoundError):
        run.reap_decision({}, 0.0)
