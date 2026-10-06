"""M4-SGM P2.5 PAID timing/fit profile on one Modal L40S (user 21446 "continue A";
cap $3 from 21436; prereg v0.2 `3bf8737` § Profile, Gate 2). Revised per codex
audit of 9e76787 (R1 bounded lifecycle, R2 atomic/untracked state, R3 usable-result
validation + evidence).

Exactly the registered matrix, ONCE: scripts/sgm-p2p5-local-gpu-timing-profile.py
(4 configs x (2 warmup + 8 measured) = 40 updates, four dev-batch timings, seed 99,
no artifact/reserved populations, no accuracy).

Bounded paid lifecycle (R1) — survives host and call-ID loss:
  * server-side guard as the FIRST statement of every container start: a Modal
    Dict holds the spawn-time deadline; each start atomically claims one of
    MAX_STARTS slots (put skip_if_exists). Past the deadline or with no slot left
    the start returns at once, so the call COMPLETES and Modal stops
    rescheduling it (crash restarts happen even with retries=0);
  * only one start can run the profile (cleared AttemptLedger claim);
  * child profile: own 1800 s SIGKILL watchdog + OUTER subprocess timeout with
    exit capture; Modal function timeout backstop;
  * local collect stops + verifies the app by its spawn-time id when the call is
    terminal OR the overall deadline has passed — also with call.json missing.
Every charged second is reserved in `charge_bound()`; launch is refused above $3.

    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py plan
    .venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py spawn
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py collect   # idempotent
"""

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import modal

APP_NAME, GROUP, RUN_ID = "memsub-m4-sgm-p2p5-profile", "p2p5-l40s-profile-v1", "profile-l40s"
PROFILE_SCRIPT = "scripts/sgm-p2p5-local-gpu-timing-profile.py"
LOCAL_OUT = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
MODEL_DIR, MODEL_REVISION = "/root/models/qwen3-0.6b-base", "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"
GPU, CPU_CORES, MEMORY_GIB = "L40S", 4.0, 32
OUTER_TIMEOUT_S, FUNCTION_TIMEOUT_S, STARTUP_S, EARLY_S = 1860, 2100, 300, 120
MAX_STARTS, OVERALL_S, COLLECT_GRACE_S = 2, 3600, 300
BUILD_STEPS, BUILD_STEP_S, BUILD_CPU, BUILD_GIB = 3, 900, 4.0, 8        # pip, pip, weight download
CAP_USD = 3.0                   # user-approved profile cap (#gravity 21436 option (a), 21446)
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S = 0.000542, 0.0000131, 0.00000222   # modal.com/pricing, preemptible
FIXED_MARGIN_USD = 0.25
EXPECTED_CONFIGS = [("learned", 1), ("learned", 2), ("memory_off", 1), ("memory_off", 2)]


def _download_pinned_weights():
    from huggingface_hub import snapshot_download
    snapshot_download("Qwen/Qwen3-0.6B-Base", revision=MODEL_REVISION, local_dir=MODEL_DIR,
                      allow_patterns=["config.json", "generation_config.json", "model.safetensors"])


app = modal.App(APP_NAME)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.7.1", index_url="https://download.pytorch.org/whl/cu126")
         .pip_install("transformers==4.55.2", "safetensors==0.5.3", "numpy==2.2.6")
         .run_function(_download_pinned_weights, timeout=BUILD_STEP_S, cpu=BUILD_CPU, memory=BUILD_GIB * 1024)
         .env({"HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false", "M4_SGM_QWEN3_0P6B_DIR": MODEL_DIR})
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_file(PROFILE_SCRIPT, f"/root/repo/{PROFILE_SCRIPT}"))
artifacts = modal.Volume.from_name("memsub-artifacts")


def file_sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def guard_decision(store, now: float) -> str | None:
    """None = this start may proceed; else the refusal reason (pure; Dict-like store)."""
    deadline = store.get("deadline_epoch", None)
    if not isinstance(deadline, (int, float)) or now > deadline:
        return "past the overall deadline (or deadline unset)"
    for k in range(1, MAX_STARTS + 1):
        if store.put(f"start{k}", now, skip_if_exists=True):
            return None
    return "start allowance exhausted"


@app.function(image=image, gpu=GPU, cpu=(CPU_CORES, CPU_CORES), memory=(MEMORY_GIB * 1024, MEMORY_GIB * 1024),
              timeout=FUNCTION_TIMEOUT_S, startup_timeout=STARTUP_S, retries=0, scaledown_window=2,
              max_containers=1, single_use_containers=True, volumes={"/artifacts": artifacts})
def run_profile(expected: dict) -> dict:
    try:   # FIRST statement; ANY guard failure refuses (a crash here would be rescheduled)
        refused = guard_decision(modal.Dict.from_name(f"m4-sgm-{GROUP}-guard", create_if_missing=True),
                                 time.time())
    except Exception as e:
        refused = f"guard error {e!r:.200}"
    if refused:                                       # bounded restarts: the call completes
        return {"status": "guard_refused", "reason": refused}
    sys.path.insert(0, "/root/repo")
    from memsub.sgm.p2d_launch_guard import (EARLY_DEADLINE_S, AllowanceExhausted, AttemptLedger,
                                             ReplayRefused, Watchdog)
    early = Watchdog(EARLY_DEADLINE_S)
    try:   # identity before the claim
        from memsub.sgm.synthetic_pilot_run import source_tree_sha256
        got = {"runner": file_sha(__file__), "profile_script": file_sha(f"/root/repo/{PROFILE_SCRIPT}"),
               "memsub": source_tree_sha256(Path("/root/repo/memsub"))}
        if got != expected:
            return {"status": "identity_mismatch", "got": got}
        try:   # one profile only: preemption/replay is refused, never re-run
            AttemptLedger(modal.Dict.from_name(f"m4-sgm-{GROUP}-attempts", create_if_missing=True)).begin(RUN_ID)
        except (AllowanceExhausted, ReplayRefused) as e:
            return {"status": "replay_refused", "reason": str(e)}
    finally:
        early.cancel()
    out = Path("/artifacts/m4-sgm") / GROUP / RUN_ID
    out.parent.mkdir(parents=True, exist_ok=True)
    try:   # outer timeout + external exit capture around the child profile
        proc = subprocess.run([sys.executable, "-u", f"/root/repo/{PROFILE_SCRIPT}", "--out", str(out)],
                              cwd="/root/repo", capture_output=True, text=True, timeout=OUTER_TIMEOUT_S)
        rc, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        rc, stdout, stderr = "outer_timeout", str(e.stdout or ""), str(e.stderr or "")
    (out.parent / f"{RUN_ID}.exit.json").write_text(json.dumps(
        {"child_exit": rc, "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-4000:]}, indent=2))
    artifacts.commit()
    profile = json.loads((out / "profile.json").read_text()) if (out / "profile.json").exists() else None
    usable, why = profile_usable(profile, rc)
    return {"status": "profiled" if usable else "profile_unusable", "reason": why, "child_exit": rc,
            "profile": profile}


def profile_usable(profile: dict | None, child_exit) -> tuple[bool, str]:
    """R3: timings are usable only for exit 0 + complete status + exactly the registered
    four configs, each 10 updates with 8 finite positive measured timings, finite memory."""
    if child_exit != 0:
        return False, f"child exit {child_exit}"
    if not isinstance(profile, dict) or profile.get("status") != "complete":
        return False, f"profile status {profile.get('status') if isinstance(profile, dict) else None}"
    cfgs = profile.get("configs") or []
    if [(c.get("arm"), c.get("phase")) for c in cfgs] != EXPECTED_CONFIGS:
        return False, "configs differ from the registered matrix"
    for c in cfgs:
        m = c.get("measured_s") or []
        vals = m + [c.get("dev_eval_batch_s"), c.get("peak_train_memory_bytes")]
        if c.get("updates") != 10 or len(m) != 8 or not all(
                isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in vals):
            return False, f"{c.get('arm')} phase {c.get('phase')}: incomplete or non-finite timings"
    return True, "complete registered matrix"


# ---------------- local side ----------------

def charge_bound() -> dict:
    """Every charged second at list rates: one profiling start, the other allowed start
    (refused at claim), one guard refusal, the image build, and a fixed margin."""
    rate = GPU_USD_S + CPU_CORES * CPU_USD_CORE_S + MEMORY_GIB * MEM_USD_GIB_S
    build_rate = BUILD_CPU * CPU_USD_CORE_S + BUILD_GIB * MEM_USD_GIB_S
    parts = {"profiling_start_usd": (STARTUP_S + FUNCTION_TIMEOUT_S) * rate,
             "refused_starts_usd": (MAX_STARTS - 1) * (STARTUP_S + EARLY_S) * rate,
             "guard_refusal_start_usd": (STARTUP_S + 10) * rate,
             "image_build_usd": BUILD_STEPS * BUILD_STEP_S * build_rate,
             "fixed_margin_usd": FIXED_MARGIN_USD}
    total = sum(parts.values())
    return {**parts, "usd_per_container_hour": rate * 3600, "reserved_total_usd": total, "cap_usd": CAP_USD,
            "admitted": total <= CAP_USD, "gpu": GPU, "preemptible": True, "max_starts": MAX_STARTS,
            "overall_deadline_s": OVERALL_S,
            "build_basis": f"{BUILD_STEPS} layers x {BUILD_STEP_S}s at {BUILD_CPU} cores/{BUILD_GIB} GiB (assumed for pip layers)"}


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def expected_identity() -> dict:
    sys.path.insert(0, str(Path.cwd()))
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    return {"runner": file_sha(__file__), "profile_script": file_sha(PROFILE_SCRIPT),
            "memsub": source_tree_sha256(Path("memsub"))}


def _load(path: str, name: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, Path(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def spawn() -> None:
    if subprocess.run(["git", "status", "--porcelain", "--", "memsub", __file__, PROFILE_SCRIPT],
                      capture_output=True, text=True, check=True).stdout.strip():
        raise SystemExit("refusing to spawn from a dirty tree")
    ledger = charge_bound()
    if not ledger["admitted"]:
        raise SystemExit(f"not admitted: ${ledger['reserved_total_usd']:.4f} > cap ${CAP_USD}")
    fn = modal.Function.from_name(APP_NAME, "run_profile")
    fn.hydrate()
    guard = modal.Dict.from_name(f"m4-sgm-{GROUP}-guard", create_if_missing=True)
    if guard.len() != 0:
        raise SystemExit("guard Dict already used: a profile was spawned before")
    root = Path(LOCAL_OUT) / GROUP
    root.mkdir(parents=True, exist_ok=False)           # a second spawn refuses here
    now = time.time()
    prov = {"expected_identity": expected_identity(), "ledger": ledger, "spawn_epoch": now,
            "deadline_epoch": now + OVERALL_S,
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "deployed_app_id": modal.App.lookup(APP_NAME).app_id}
    atomic_write(root / "launch_provenance.json", json.dumps(prov, indent=2))   # app id saved BEFORE spawn
    if not guard.put("deadline_epoch", prov["deadline_epoch"], skip_if_exists=True):
        raise SystemExit("guard deadline already set")
    call = fn.spawn(prov["expected_identity"]).object_id
    atomic_write(root / "call.json", json.dumps({"call_id": call}))
    print("spawned", call)


def collect(poller=None, stopper=None, fetch=None, now=None) -> dict:
    """Idempotent. Stops + verifies the app when the call is terminal OR the deadline has
    passed (also with call.json missing/corrupt); always pulls the volume evidence."""
    root = Path(LOCAL_OUT) / GROUP
    prov = json.loads((root / "launch_provenance.json").read_text())
    tu, v1 = (_load("modal-runners/modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py", "topup"),
              _load("modal-runners/modal-m4-sgm-p2d-diagnostics-grid.py", "v1"))
    poller, stopper = poller or tu.poll, stopper or (lambda app_id: tu.shutdown(v1, app_id))
    try:
        call = json.loads((root / "call.json").read_text())["call_id"]
    except (OSError, ValueError, KeyError):
        call = None                                      # untracked: never respawned
    kind, payload = poller(call) if call else ("untracked", None)
    past_deadline = (now or time.time()) > prov["deadline_epoch"] + COLLECT_GRACE_S
    report = {"call_id": call, "poll": kind, "past_deadline": past_deadline, "result": payload}
    if kind not in ("pending", "untracked") or past_deadline:
        report["final_shutdown"] = stopper(prov["deployed_app_id"])
        report["evidence"] = (fetch or fetch_evidence)(root)
    if isinstance(payload, dict) and "profile" in payload:
        report["usable"], report["usable_reason"] = profile_usable(payload.get("profile"), payload.get("child_exit"))
    atomic_write(root / "collect_status.json", json.dumps(report, indent=2, default=str))
    print(json.dumps({k: v for k, v in report.items() if k != "result"}, default=str))
    return report


def fetch_evidence(root: Path) -> dict:
    """Pull m4-sgm/<GROUP> (exit json, profile.json, progress.jsonl) from the volume."""
    dest = root / "volume-evidence"
    dest.mkdir(exist_ok=True)
    got = subprocess.run([sys.executable, "-m", "modal", "volume", "get", "--force", "memsub-artifacts",
                          f"m4-sgm/{GROUP}", str(dest)], capture_output=True, text=True, timeout=300)
    return {"returncode": got.returncode, "stderr_tail": got.stderr[-500:]}


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    {"plan": lambda: print(json.dumps(charge_bound(), indent=2)), "spawn": spawn, "collect": collect}[sys.argv[1]]()
