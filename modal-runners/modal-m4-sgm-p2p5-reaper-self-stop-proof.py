"""CPU-only proof that the P2.5 in-app reaper STOPS ITS OWN APP with container
credentials (codex 21456; inside user 21446's $3 profile scope).

A throwaway app with a unique name/Dict, bare debian_slim image, no GPU, no Qwen, no
volume, no populations, no retries. Its only function is a scheduled reaper calling the
SHARED production logic (`modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py`, mounted
beside it). `prove` deploys it once, binds app id + a short deadline in the Dict, then
only WATCHES (read-only) for the self-stop. A fallback stop is used only after the wait
bound and is recorded as a FAILED proof.

    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-reaper-self-stop-proof.py plan
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-reaper-self-stop-proof.py prove
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import modal

APP_NAME = "memsub-m4-sgm-p2p5-reaper-proof"
GUARD_DICT = "m4-sgm-p2p5-reaper-proof-guard"
LOGIC_FILE = "modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py"
LOCAL_OUT = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/reaper-self-stop-proof-v1"
PERIOD_S, DEADLINE_AFTER_DEPLOY_S, WAIT_S, POLL_S, DEPLOY_TIMEOUT_S = 60, 120, 600, 20, 600
PROOF_ABANDON_S = 240                 # unbound deploy (host/binding loss) self-stops inside the claimed life
TICK_TIMEOUT_S, CPU, MEM_MIB, LOGS_TIMEOUT_S = 50, 0.125, 256, 120
CPU_USD_CORE_S, MEM_USD_GIB_S, MARGIN_USD = 0.0000131, 0.00000222, 0.05

app = modal.App(APP_NAME)
image = modal.Image.debian_slim(python_version="3.12").add_local_file(f"modal-runners/{LOGIC_FILE}",
                                                                      f"/root/{LOGIC_FILE}")


def _logic():
    import importlib.util
    spec = importlib.util.spec_from_file_location("p2p5_reaper_logic", Path(__file__).with_name(LOGIC_FILE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@app.function(image=image, schedule=modal.Period(seconds=PERIOD_S), cpu=CPU, memory=MEM_MIB,
              timeout=TICK_TIMEOUT_S, max_containers=1, retries=0)
def reaper() -> dict:
    lg = _logic()
    return lg.reap_and_stop(modal.Dict.from_name(GUARD_DICT, create_if_missing=True), time.time(), APP_NAME,
                            lg.stop_bound_app, None, PROOF_ABANDON_S)


# ---------------- local side ----------------

def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def charge_bound() -> dict:
    life = DEPLOY_TIMEOUT_S + max(DEADLINE_AFTER_DEPLOY_S + WAIT_S + PERIOD_S, PROOF_ABANDON_S + 2 * PERIOD_S)
    ticks = life // PERIOD_S + 2
    usd = ticks * TICK_TIMEOUT_S * (CPU * CPU_USD_CORE_S + MEM_MIB / 1024 * MEM_USD_GIB_S) + MARGIN_USD
    return {"max_app_life_s": life, "max_ticks": ticks, "reserved_usd": usd,
            "note": "counted inside the $3 P2.5 profile scope (user 21446); bare image build is negligible"}


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def lookup_app_id() -> str | None:
    """Read-only: the uniquely named proof app's id, or None if not deployed."""
    try:
        return modal.App.lookup(APP_NAME).app_id
    except Exception:
        return None


def fetch_logs(app_id: str) -> str:
    got = subprocess.run([sys.executable, "-m", "modal", "app", "logs", app_id, "--tail", "1000"],
                         capture_output=True, text=True, timeout=LOGS_TIMEOUT_S)
    return got.stdout + got.stderr + f"\nEXIT_STATUS={got.returncode}\n"


def judge(deadline: float, stopped_at: float | None, verified: bool, logs: str, app_id: str) -> tuple[bool, str]:
    """PASS only for a stop inside [deadline, deadline + WAIT_S + PERIOD_S], verified stopped with
    zero tasks/containers, and the reaper's bound marker for THIS app in the server-side logs."""
    if stopped_at is None:
        return False, "never stopped"
    if not deadline <= stopped_at <= deadline + WAIT_S + PERIOD_S:
        return False, f"stop at {stopped_at:.0f} outside the intended window [{deadline:.0f}, ...]"
    if not verified:
        return False, "not verified stopped with zero tasks/containers"
    marker = f"M4SGM_REAPER_STOP app={APP_NAME} bound={app_id} reason=deadline passed"
    if marker not in logs:
        return False, "no server-side log evidence of the bound scheduled stop"
    return True, "self-stop by the bound scheduled reaper inside the intended window"


def prove(deploy=None, lookup=lookup_app_id, guard=None, lifecycle=None, verify=None, stop=None,
          logs=fetch_logs, clock=time.time, sleep=time.sleep) -> dict:
    """One attempt. Every post-deploy failure ends as a recorded FAILED proof with an
    app-id-bound fallback stop + verify; the report is always written."""
    if deploy is None:                                            # real dependencies
        if subprocess.run(["git", "status", "--porcelain", "--", __file__, f"modal-runners/{LOGIC_FILE}"],
                          capture_output=True, text=True, check=True).stdout.strip():
            raise SystemExit("refusing to prove from a dirty tree")
        import importlib.util
        spec = importlib.util.spec_from_file_location("v1", "modal-runners/modal-m4-sgm-p2d-diagnostics-grid.py")
        v1 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(v1)
        from modal.experimental import get_app_lifecycle
        deploy = lambda: subprocess.run([sys.executable, "-m", "modal", "deploy", __file__], capture_output=True,
                                        text=True, timeout=DEPLOY_TIMEOUT_S)
        guard = modal.Dict.from_name(GUARD_DICT, create_if_missing=True)
        lifecycle, verify, stop = get_app_lifecycle, v1.verify_stopped, v1.stop_app
    root = Path(LOCAL_OUT)
    root.mkdir(parents=True, exist_ok=False)                       # one proof attempt only
    if set(guard.keys()) - {"first_tick"}:
        raise SystemExit("proof Dict already used")
    prov = {"proof_runner_sha256": sha(__file__), "logic_sha256": sha(Path(__file__).with_name(LOGIC_FILE)),
            "ledger": charge_bound()}
    atomic_write(root / "proof_provenance.json", json.dumps(prov, indent=2))
    report, app_id, deadline, passed = {"errors": [], "observed": []}, None, None, False
    try:
        try:
            dep = deploy()
            out, rc = dep.stdout + dep.stderr, dep.returncode
        except subprocess.TimeoutExpired as e:
            out, rc = f"{e.stdout or ''}{e.stderr or ''}", "deploy_timeout"
        (root / "deploy.log").write_text(f"{out}\nEXIT_STATUS={rc}\n")
        app_id = lookup()                                         # read-only, before any binding
        prov["app_id"] = app_id
        atomic_write(root / "proof_provenance.json", json.dumps(prov, indent=2))
        if rc != 0 or app_id is None:
            raise RuntimeError(f"deploy exit {rc}, app id {app_id}")
        deadline = clock() + DEADLINE_AFTER_DEPLOY_S
        prov["deadline_epoch"] = deadline
        atomic_write(root / "proof_provenance.json", json.dumps(prov, indent=2))    # saved BEFORE binding
        if not guard.put("deadline_epoch", deadline, skip_if_exists=True):
            raise RuntimeError("deadline already bound")
        if not guard.put("app_id", app_id, skip_if_exists=True):
            raise RuntimeError("app id already bound")
        stopped_at = None
        while clock() < deadline + WAIT_S + PERIOD_S:               # WATCH ONLY: no local stop here
            sleep(POLL_S)
            lc = lifecycle(app_id)
            stopped_at = lc.stopped_at.timestamp() if lc.stopped_at else None
            report["observed"].append({"t": clock(), "stopped_at": stopped_at, "stopped_by": lc.stopped_by})
            if stopped_at is not None:
                break
        verified = bool(verify(app_id).get("verified"))
        log_text = logs(app_id)
        (root / "app-logs.txt").write_text(log_text)
        passed, why = judge(deadline, stopped_at, verified, log_text, app_id)
        report["judgement"] = why
    except Exception as e:
        report["errors"].append(repr(e)[:500])
    finally:
        report.update(app_id=app_id, deadline_epoch=deadline)
        if not passed:                                            # fallback = FAILED proof, never PASS
            app_id = app_id or lookup()
            report["fallback"] = {"app_id": app_id}
            if app_id:
                try:
                    stop(app_id)
                except Exception as e:
                    report["fallback"]["stop_error"] = repr(e)[:300]
                try:
                    report["fallback"]["verify"] = verify(app_id)
                except Exception as e:
                    report["fallback"]["verify_error"] = repr(e)[:300]
        report["result"] = "PASS" if passed else "FAILED"
        atomic_write(root / "proof_report.json", json.dumps(report, indent=2, default=str))
    print(report["result"], report.get("judgement"), report["errors"])
    return report


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    {"plan": lambda: print(json.dumps(charge_bound(), indent=2)), "prove": prove}[sys.argv[1]]()
