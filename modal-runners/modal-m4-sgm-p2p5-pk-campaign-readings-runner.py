"""M4-SGM P2.5 Amendment PK — EXACTLY-ONCE readings app (prereg v0.2 Gate 4; codex 21596).

    .venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py spawn|collect

ONE GPU function (A100-80GB, max_containers=1, single_use_containers, retries=0) with ONE admitted start (atomic
Dict claim): any deployed-crash re-entry finds the claim taken and returns BEFORE touching the reserved population.
Absolute deadline written once at spawn (= the v6 readings reserve life), bound to the control plane, SIGKILL
watchdog to it. Spawn requires every slot collected with a verified stop and every registered cell COMPLETE and
valid; the readings script then re-binds every cell itself from the volume (fail closed) and writes once.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import modal

APP_NAME = "memsub-m4-sgm-p2p5-pk-campaign-readings"
GUARD_DICT, ADMIT_DICT = f"{APP_NAME}-guard", f"{APP_NAME}-admission"
CONTROL_REGISTRY_DICT, CONTROL_GUARD_DICT = "m4-sgm-p2p5-pk-campaign-control-registry-r2", "m4-sgm-p2p5-pk-campaign-control-guard-r2"
CONTROL_APP_NAME, CONTROL_SLACK_S = "memsub-m4-sgm-p2p5-pk-campaign-control", 1800
SCRIPT = "scripts/sgm-p2p5-pk-campaign-readings.py"
MANIFEST_FILE = "configs/m4_sgm_p2p5_campaign_analysis_manifest.json"
PRICE_FILE = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk6/priced-estimate-v6.json"
GROUP, LOCAL_OUT = "p2p5-qwen3-0p6b-screen-v1", "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
SLOTS = ("learned-n16", "learned-n32", "single_cell-n16", "single_cell-n32", "random_fixed-n16", "random_fixed-n32",
         "oracle-n32", "memory_off-n16", "memory_off-n32")
MODEL_DIR, MODEL_REVISION = "/root/models/qwen3-0.6b-base", "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"
EARLY_S = 120


def _build_environment():
    import subprocess as sp
    sp.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "torch==2.7.1",
            "--index-url", "https://download.pytorch.org/whl/cu126"], check=True)
    sp.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "transformers==4.55.2",
            "safetensors==0.5.3", "numpy==2.2.6", "pytest==8.4.1"], check=True)
    from huggingface_hub import snapshot_download
    snapshot_download("Qwen/Qwen3-0.6B-Base", revision=MODEL_REVISION, local_dir=MODEL_DIR,
                      allow_patterns=["config.json", "generation_config.json", "model.safetensors"])


app = modal.App(APP_NAME)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("huggingface_hub==0.36.2")
         .run_function(_build_environment, timeout=1200, cpu=4.0, memory=8 * 1024)
         .env({"HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false", "M4_SGM_QWEN3_0P6B_DIR": MODEL_DIR})
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_dir("scripts", "/root/repo/scripts", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_dir("configs", "/root/repo/configs")
         .add_local_file(f"{LOCAL_OUT}/prereg.md", f"/root/repo/{LOCAL_OUT}/prereg.md")
         .add_local_file(f"{LOCAL_OUT}/prereg-amendment-pk-packed-a100-resume.md",
                         f"/root/repo/{LOCAL_OUT}/prereg-amendment-pk-packed-a100-resume.md"))
artifacts = modal.Volume.from_name("memsub-artifacts")


def file_sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def admit_once(adm, guard, now: float) -> str | None:
    """None iff THIS is the single admitted start (finite deadline not passed, claim not yet taken)."""
    import math
    d = guard.get("deadline_epoch", None)
    if not (isinstance(d, (int, float)) and not isinstance(d, bool) and math.isfinite(d) and d > 0) or now > d:
        return "past the readings deadline (or unset / non-finite)"
    return None if adm.put("start-1", now, skip_if_exists=True) else "re-entry refused: readings already admitted once"


@app.function(image=image, gpu="A100-80GB", cpu=(8.0, 8.0), memory=(64 * 1024, 64 * 1024), timeout=86400,
              startup_timeout=300, max_containers=1, single_use_containers=True, retries=0,
              volumes={"/artifacts": artifacts})
def run_readings(expected: dict) -> dict:
    sys.path.insert(0, "/root/repo")
    from memsub.sgm.p2d_launch_guard import Watchdog
    early = Watchdog(EARLY_S)
    try:
        adm, guard = modal.Dict.from_name(ADMIT_DICT, create_if_missing=True), modal.Dict.from_name(GUARD_DICT)
        refused = admit_once(adm, guard, time.time())
        deadline = guard.get("deadline_epoch", None)
        admitted = {} if refused else {
            s: sorted(int(k.split("-")[1]) for k in dict(modal.Dict.from_name(
                f"memsub-m4-sgm-p2p5-pk-campaign-{s.replace('_', '')}-admission").items()) if k.startswith("start-"))
            for s in SLOTS}
    except Exception as e:
        refused = f"admission error {e!r:.200}"
    finally:
        early.cancel()
    if refused:
        return {"status": "admission_refused", "reason": refused}
    life = Watchdog(max(1.0, deadline - time.time()))
    try:
        from memsub.sgm.synthetic_pilot_run import source_tree_sha256
        got = {"memsub": source_tree_sha256(Path("/root/repo/memsub")), "manifest": file_sha(f"/root/repo/{MANIFEST_FILE}")}
        if got != expected:
            return {"status": "identity_mismatch", "got": got}
        work = Path("/tmp/readings-inputs")
        work.mkdir()
        (work / "admitted.json").write_text(json.dumps(admitted))
        (work / "expected.json").write_text(json.dumps(expected))
        artifacts.reload()
        root = Path("/artifacts/m4-sgm") / GROUP
        proc = subprocess.run([sys.executable, "-u", f"/root/repo/{SCRIPT}", "--evidence-root", str(root),
                               "--admitted", str(work / "admitted.json"), "--expected", str(work / "expected.json"),
                               "--out", str(root / "readings-v1")], cwd="/root/repo", capture_output=True, text=True,
                              timeout=max(60, deadline - time.time() - 120))
        (root / "readings-v1.exit.json").write_text(json.dumps({"rc": proc.returncode, "stdout_tail": proc.stdout[-4000:],
                                                                "stderr_tail": proc.stderr[-4000:]}, indent=2))
        artifacts.commit()
        return {"status": "read" if proc.returncode == 0 else "readings_failed", "rc": proc.returncode}
    finally:
        life.cancel()


# ---------------- local side ----------------

def expected_identity() -> dict:
    sys.path.insert(0, str(Path.cwd()))
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    return {"memsub": source_tree_sha256(Path("memsub")), "manifest": file_sha(MANIFEST_FILE)}   # the script re-verifies all


def slots_ready(local_root: Path) -> str | None:
    """Every slot collected with a verified stop and every registered cell COMPLETE + valid (spawn precondition)."""
    for s in SLOTS:
        try:
            st = json.loads((local_root / s / "collect_status.json").read_text())
        except (OSError, ValueError):
            return f"{s}: not collected"
        if (st.get("final_shutdown") or {}).get("status") != "stopped_verified":
            return f"{s}: stop not verified"
        bad = {c: v for c, v in (st.get("cells") or {}).items()
               if v.get("state") != "COMPLETE" or v.get("validation") != "valid"}
        if bad or len(st.get("cells") or {}) != 2:
            return f"{s}: cells not all COMPLETE and valid: {sorted(bad)}"
    return None


def load_cp():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cp", Path(__file__).with_name("modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py"))
    cp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cp)
    return cp


def app_state(app_id: str) -> str:
    rows = json.loads(subprocess.run([sys.executable, "-m", "modal", "app", "list", "--json"], check=True,
                                     capture_output=True, text=True, timeout=30).stdout)
    mine = [r for r in rows if r.get("app_id") == app_id]
    return str(mine[0].get("state")) if mine else "none"


def spawn() -> None:
    tracked = ["memsub", "scripts", "configs", "modal-runners", PRICE_FILE, f"{LOCAL_OUT}/prereg.md",
               f"{LOCAL_OUT}/prereg-amendment-pk-packed-a100-resume.md"]
    if subprocess.run(["git", "status", "--porcelain", "--", *tracked], capture_output=True, text=True,
                      check=True).stdout.strip():
        raise SystemExit("refusing to spawn from a dirty tree")
    problem = load_cp().launch_manifest_problem(Path.cwd())
    if problem:
        raise SystemExit(f"refusing to spawn: {problem}")
    local = Path(LOCAL_OUT) / GROUP
    problem = slots_ready(local)
    if problem:
        raise SystemExit(f"readings precondition failed: {problem}")
    cp = load_cp()
    candidate = time.time() + json.loads(Path(PRICE_FILE).read_text())["readings"]["reserve_life_s"]   # ONE deadline
    control = dict(modal.Dict.from_name(CONTROL_GUARD_DICT).items())
    problem = cp.binding_problem(control, file_sha(PRICE_FILE), lambda: modal.App.lookup(CONTROL_APP_NAME).app_id,
                                 app_state, candidate, CONTROL_SLACK_S)
    if problem:
        raise SystemExit(f"controller preflight failed: {problem}")
    guard = modal.Dict.from_name(GUARD_DICT, create_if_missing=True)
    if len(guard.keys()):
        raise SystemExit("readings guard already used: readings were spawned before (exactly once)")
    root = local / "readings"
    root.mkdir(parents=True, exist_ok=False)
    app_id = modal.App.lookup(APP_NAME).app_id
    prov = {"expected_identity": expected_identity(), "deadline_epoch": candidate, "deployed_app_id": app_id,
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()}
    (root / "launch_provenance.json").write_text(json.dumps(prov, indent=2))
    if not (guard.put("app_id", app_id, skip_if_exists=True) and guard.put("deadline_epoch", candidate, skip_if_exists=True)):
        raise SystemExit("readings guard already set")
    if not cp.register(modal.Dict.from_name(CONTROL_REGISTRY_DICT, create_if_missing=True), APP_NAME, app_id, candidate,
                       horizon=control["deadline_epoch"]):
        raise SystemExit("readings already registered with the control plane")
    call = modal.Function.from_name(APP_NAME, "run_readings").spawn(prov["expected_identity"]).object_id
    (root / "call.json").write_text(json.dumps({"call_id": call}))
    print("spawned readings", call)


def collect(poller=None, stopper=None, verifier=None, fetch=None, now=None) -> dict:
    """Idempotent: once the call is terminal / untracked / past its deadline, stop + independently verify the
    readings app by its bound id, then pull the write-once readings output into a fresh per-collect directory.
    Provenance is validated before any poll or side effect (codex 21617 R3); `stopped_verified` needs stopped/
    unlisted + zero tasks + no containers (R4); shutdown evidence is durable before the fetch (R5)."""
    cp = load_cp()
    root = Path(LOCAL_OUT) / GROUP / "readings"
    try:
        prov = json.loads((root / "launch_provenance.json").read_text())
    except (OSError, ValueError):
        prov = None
    problem = cp.provenance_problem(prov)
    if problem:
        raise SystemExit(f"readings: {problem}: refusing")
    try:
        call = json.loads((root / "call.json").read_text())["call_id"]
    except (OSError, ValueError, KeyError, TypeError):
        call = None
    kind, payload = (poller(call) if call else ("untracked", None))
    past = (now if now is not None else time.time()) > prov["deadline_epoch"] + 300
    report = {"call_id": call, "poll": kind, "result": payload, "past_deadline": past}
    if kind not in ("pending", "untracked") or past or call is None:
        sd = {"app_id": prov["deployed_app_id"]}
        try:
            cp.strict_stop(stopper, APP_NAME, prov["deployed_app_id"])
        except Exception as e:
            sd["stop_error"] = repr(e)[:300]
        sd["verification"] = verifier(prov["deployed_app_id"])
        sd["status"] = "stopped_verified" if sd["verification"].get("verified") is True else "shutdown_unresolved"
        report["final_shutdown"] = sd
        (root / "collect_status.json").write_text(json.dumps(report, indent=2, default=str))   # durable first
        dest = root / "volume-evidence" / f"collect-{1 + len(list((root / 'volume-evidence').glob('collect-*')))}"
        report["evidence"] = fetch(dest)
        report["evidence_complete"] = bool(report["evidence"]) and all(rc == 0 for rc in report["evidence"].values())
        report["evidence_dir"] = str(dest)
    (root / "collect_status.json").write_text(json.dumps(report, indent=2, default=str))
    return report


def _real_collect():
    import importlib.util
    spec = importlib.util.spec_from_file_location("topup", Path(__file__).with_name("modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py"))
    tu = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tu)
    spec2 = importlib.util.spec_from_file_location("shared", Path(__file__).with_name("modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py"))
    shared = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(shared)
    cp = load_cp()

    def fetch(dest):
        dest.mkdir(parents=True, exist_ok=False)
        out = {}
        for path in (f"m4-sgm/{GROUP}/readings-v1", f"m4-sgm/{GROUP}/readings-v1.exit.json"):
            g = subprocess.run([sys.executable, "-m", "modal", "volume", "get", "memsub-artifacts", path, str(dest)],
                               capture_output=True, text=True, timeout=1800)
            out[path] = g.returncode
        return out
    return collect(poller=tu.poll, stopper=shared.stop_bound_app,
                   verifier=lambda app_id: cp.verify_stopped(app_id, cp.modal_cli_json), fetch=fetch)


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    {"spawn": spawn, "collect": _real_collect}[sys.argv[1]]()
