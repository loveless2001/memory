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
TICK_TIMEOUT_S, CPU, MEM_MIB = 50, 0.125, 256
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
                            lg.stop_bound_app, None, 1800)


# ---------------- local side ----------------

def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def charge_bound() -> dict:
    life = DEPLOY_TIMEOUT_S + DEADLINE_AFTER_DEPLOY_S + WAIT_S
    ticks = life // PERIOD_S + 2
    usd = ticks * TICK_TIMEOUT_S * (CPU * CPU_USD_CORE_S + MEM_MIB / 1024 * MEM_USD_GIB_S) + MARGIN_USD
    return {"max_app_life_s": life, "max_ticks": ticks, "reserved_usd": usd,
            "note": "counted inside the $3 P2.5 profile scope (user 21446); bare image build is negligible"}


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def prove() -> dict:
    if subprocess.run(["git", "status", "--porcelain", "--", __file__, f"modal-runners/{LOGIC_FILE}"],
                      capture_output=True, text=True, check=True).stdout.strip():
        raise SystemExit("refusing to prove from a dirty tree")
    import importlib.util
    spec = importlib.util.spec_from_file_location("v1", "modal-runners/modal-m4-sgm-p2d-diagnostics-grid.py")
    v1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v1)
    from modal.experimental import get_app_lifecycle
    root = Path(LOCAL_OUT)
    root.mkdir(parents=True, exist_ok=False)                       # one proof attempt only
    guard = modal.Dict.from_name(GUARD_DICT, create_if_missing=True)
    if set(guard.keys()) - {"first_tick"}:
        raise SystemExit("proof Dict already used")
    prov = {"proof_runner_sha256": sha(__file__), "logic_sha256": sha(f"modal-runners/{LOGIC_FILE}"),
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "ledger": charge_bound()}
    atomic_write(root / "proof_provenance.json", json.dumps(prov, indent=2))
    dep = subprocess.run([sys.executable, "-m", "modal", "deploy", __file__], capture_output=True, text=True,
                         timeout=DEPLOY_TIMEOUT_S)
    (root / "deploy.log").write_text(dep.stdout + dep.stderr + f"\nEXIT_STATUS={dep.returncode}\n")
    if dep.returncode != 0:
        raise SystemExit(f"deploy failed ({dep.returncode}); see deploy.log")
    app_id = modal.App.lookup(APP_NAME).app_id
    deadline = time.time() + DEADLINE_AFTER_DEPLOY_S
    if not (guard.put("app_id", app_id, skip_if_exists=True) and guard.put("deadline_epoch", deadline, skip_if_exists=True)):
        raise SystemExit("proof Dict already bound")
    prov.update(app_id=app_id, deadline_epoch=deadline)
    atomic_write(root / "proof_provenance.json", json.dumps(prov, indent=2))
    observed, stopped_by_reaper = [], False
    while time.time() < deadline + WAIT_S:                         # WATCH ONLY: no local stop here
        time.sleep(POLL_S)
        lc = get_app_lifecycle(app_id)
        check = v1.verify_stopped(app_id)
        observed.append({"t": time.time(), "stopped_at": str(lc.stopped_at), "stopped_by": lc.stopped_by,
                         "verify": check})
        if lc.stopped_at is not None and check.get("verified"):
            stopped_by_reaper = True
            break
    report = {"app_id": app_id, "deadline_epoch": deadline, "observed": observed,
              "reaper_fired": guard.get("reaper_fired", None)}
    if stopped_by_reaper:
        report["result"] = "PASS: the app stopped itself (no local stop issued)"
    else:
        report["result"] = "FAILED: no self-stop within the wait bound; fallback stop issued"
        report["fallback"] = {"stop_error": None}
        try:
            v1.stop_app(app_id)
        except Exception as e:
            report["fallback"]["stop_error"] = repr(e)
        report["fallback"]["verify"] = v1.verify_stopped(app_id)
    report["final_verify"] = v1.verify_stopped(app_id)
    atomic_write(root / "proof_report.json", json.dumps(report, indent=2, default=str))
    print(report["result"])
    return report


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    {"plan": lambda: print(json.dumps(charge_bound(), indent=2)), "prove": prove}[sys.argv[1]]()
