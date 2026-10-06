"""M4-SGM P2.5 PAID RE-TIMING (v2) on one Modal L40S after the option-A speed-up
(user 21501 "A": official re-timing, cap $3, separate from the $3 dev envelope).

v2 = a copy of the accepted v1 runner (modal-m4-sgm-p2p5-l40s-timing-profile.py,
codex 21462/21469) with ONLY: app / group / guard-Dict names, this docstring and cap
citation, and a DESCRIPTIVE GPU sampler (nvidia-smi every 500 ms, written beside the
profile output; never part of the usable-result rule). The registered profile script is
byte-identical to v1; the bound memsub source is the speed-up (b87a767b, stage 1 +
default-off resume; GPU parity run 2 c17cfcc). v1 docstring follows.

(v1) M4-SGM P2.5 PAID timing/fit profile on one Modal L40S (user 21446 "continue A";
cap $3 from 21436; prereg v0.2 `3bf8737` § Profile, Gate 2). Revised per codex
audit of 9e76787 (R1 bounded lifecycle, R2 atomic/untracked state, R3 usable-result
validation + evidence).

Exactly the registered matrix, ONCE: scripts/sgm-p2p5-local-gpu-timing-profile.py
(4 configs x (2 warmup + 8 measured) = 40 updates, four dev-batch timings, seed 99,
no artifact/reserved populations, no accuracy).

Bounded paid lifecycle (R1, revised per codex cd1c0c8 audit) — survives host and call-ID loss:
  * an in-app scheduled REAPER (CPU, every 2 min) stops the WHOLE app with
    modal.experimental.stop_app once the spawn-time deadline has passed (after
    cancelling the stored call with terminate_containers=True), and stops an
    abandoned deploy (never spawned) ABANDON_S after its first tick. With
    max_containers=1, GPU time is bounded by the app lifetime regardless of
    import/startup crashes;
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

    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile-v2-after-speedup.py plan
    .venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile-v2-after-speedup.py
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile-v2-after-speedup.py spawn
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile-v2-after-speedup.py collect   # idempotent
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

APP_NAME, GROUP, RUN_ID = "memsub-m4-sgm-p2p5-profile-v2", "p2p5-l40s-profile-v2", "profile-l40s"
PROFILE_SCRIPT = "scripts/sgm-p2p5-local-gpu-timing-profile.py"
LOCAL_OUT = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
MODEL_DIR, MODEL_REVISION = "/root/models/qwen3-0.6b-base", "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"
GPU, CPU_CORES, MEMORY_GIB = "L40S", 4.0, 32
OUTER_TIMEOUT_S, FUNCTION_TIMEOUT_S, STARTUP_S, EARLY_S = 1860, 2100, 300, 120
MAX_STARTS, OVERALL_S, COLLECT_GRACE_S = 2, 2700, 300
REAPER_PERIOD_S, STOP_LATENCY_S, ABANDON_S, MIN_REMAINING_S = 120, 120, 1800, 900
BUILD_S, BUILD_CPU, BUILD_GIB, BUILD_OVERUSE = 1200, 4.0, 8, 2.0        # ONE timed build function (pip + weights)
GUARD_DICT = "m4-sgm-p2p5-l40s-profile-v2-guard"
MIN_CHILD_S = 600                                      # below this the child is not launched (late start)
EXPECTED_ENV = {"python_prefix": "3.12.", "torch": "2.7.1+cu126", "cuda": "12.6", "gpu_contains": "L40S"}
CONTRACT = "full-gradient token-serial, fp32, TF32 off, batch 16, N32, seed 99"
PHASE_FILLER = {1: 0, 2: 40}
CAP_USD = 3.0                   # user-approved re-timing cap (#gravity 21498 option A, user 21501)
GPU_SAMPLE_MS = 500             # descriptive nvidia-smi sampling period (not a usability input)
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S = 0.000542, 0.0000131, 0.00000222   # modal.com/pricing, preemptible
FIXED_MARGIN_USD = 0.25
EXPECTED_CONFIGS = [("learned", 1), ("learned", 2), ("memory_off", 1), ("memory_off", 2)]


LOGIC_FILE = "modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py"   # shared with the CPU self-stop proof


def _load_logic():
    """The shared reaper logic sits next to this runner locally AND in the container."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("p2p5_reaper_logic", Path(__file__).with_name(LOGIC_FILE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_LOGIC = None
ENVIRONMENT = "main"                # must equal the shared logic's ENVIRONMENT (tested)


def logic():
    """LAZY: Modal imports this module inside the image-build step, before the logic file is
    mounted (deploy 18:01 failed with FileNotFoundError); only callers that need it load it."""
    global _LOGIC
    if _LOGIC is None:
        _LOGIC = _load_logic()
    return _LOGIC


def reap_decision(store, now: float) -> str | None:
    return logic().reap_decision(store, now, ABANDON_S)


def reap_and_stop(store, now: float, app_name: str, stopper, canceller=None) -> dict:
    return logic().reap_and_stop(store, now, app_name, stopper, canceller, ABANDON_S)


def stop_bound_app(app_name: str, expected_app_id: str | None, environment: str = ENVIRONMENT) -> None:
    return logic().stop_bound_app(app_name, expected_app_id, environment)


def _build_environment():
    """ALL build compute in one function with an enforced timeout: pinned wheels + weights."""
    import subprocess as sp
    sp.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "torch==2.7.1",
            "--index-url", "https://download.pytorch.org/whl/cu126"], check=True)
    sp.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "transformers==4.55.2",
            "safetensors==0.5.3", "numpy==2.2.6"], check=True)
    from huggingface_hub import snapshot_download
    snapshot_download("Qwen/Qwen3-0.6B-Base", revision=MODEL_REVISION, local_dir=MODEL_DIR,
                      allow_patterns=["config.json", "generation_config.json", "model.safetensors"])


app = modal.App(APP_NAME)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("huggingface_hub==0.36.2")                       # tiny bootstrap layer
         .run_function(_build_environment, timeout=BUILD_S, cpu=BUILD_CPU, memory=BUILD_GIB * 1024)
         .env({"HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false", "M4_SGM_QWEN3_0P6B_DIR": MODEL_DIR})
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_file(PROFILE_SCRIPT, f"/root/repo/{PROFILE_SCRIPT}")
         .add_local_file(f"modal-runners/{LOGIC_FILE}", f"/root/{LOGIC_FILE}"))
# the scheduled reaper needs ONLY the shared logic (codex 21458: it must not run on the bare default image)
reaper_image = modal.Image.debian_slim(python_version="3.12").add_local_file(f"modal-runners/{LOGIC_FILE}",
                                                                             f"/root/{LOGIC_FILE}")
artifacts = modal.Volume.from_name("memsub-artifacts")


def file_sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def admit(store, now: float) -> tuple[str | None, float]:
    """(refusal reason or None, seconds remaining before the deadline) for one start."""
    refused = guard_decision(store, now)
    deadline = store.get("deadline_epoch", None)
    remaining = (deadline - now) if isinstance(deadline, (int, float)) else 0.0
    if refused is None and remaining < MIN_REMAINING_S:
        refused = f"only {remaining:.0f}s before the deadline"
    return refused, remaining


def child_timeout_s(deadline, now: float) -> float | None:
    """Outer child timeout recomputed at launch: never past the deadline (90 s reserved for
    commit/return); None (do not launch) when under MIN_CHILD_S would remain."""
    if not isinstance(deadline, (int, float)):
        return None
    t = min(OUTER_TIMEOUT_S, deadline - now - 90)
    return t if t >= MIN_CHILD_S else None


def guard_decision(store, now: float) -> str | None:
    """None = this start may proceed; else the refusal reason (pure; Dict-like store)."""
    deadline = store.get("deadline_epoch", None)
    if not isinstance(deadline, (int, float)) or now > deadline:
        return "past the overall deadline (or deadline unset)"
    for k in range(1, MAX_STARTS + 1):
        if store.put(f"start{k}", now, skip_if_exists=True):
            return None
    return "start allowance exhausted"


@app.function(image=reaper_image, schedule=modal.Period(seconds=REAPER_PERIOD_S), cpu=0.125, memory=256, timeout=110,
              max_containers=1, retries=0)
def reaper() -> dict:
    """Independent server-side lifetime stop (no local host or call id needed)."""
    return reap_and_stop(modal.Dict.from_name(GUARD_DICT, create_if_missing=True), time.time(), APP_NAME,
                         stop_bound_app,
                         lambda c: modal.FunctionCall.from_id(c).cancel(terminate_containers=True))


@app.function(image=image, gpu=GPU, cpu=(CPU_CORES, CPU_CORES), memory=(MEMORY_GIB * 1024, MEMORY_GIB * 1024),
              timeout=FUNCTION_TIMEOUT_S, startup_timeout=STARTUP_S, retries=0, scaledown_window=2,
              max_containers=1, single_use_containers=True, volumes={"/artifacts": artifacts})
def run_profile(expected: dict) -> dict:
    sys.path.insert(0, "/root/repo")
    from memsub.sgm.p2d_launch_guard import (EARLY_DEADLINE_S, AllowanceExhausted, AttemptLedger,
                                             ReplayRefused, Watchdog)
    early = Watchdog(EARLY_DEADLINE_S)                # FIRST: bounds guard RPCs, imports and the claim
    try:   # ANY guard failure refuses (a crash here would be rescheduled; the reaper bounds the rest)
        refused, remaining = admit(modal.Dict.from_name(GUARD_DICT, create_if_missing=True), time.time())
    except Exception as e:
        refused, remaining = f"guard error {e!r:.200}", 0.0
    if refused:                                       # bounded restarts: the call completes
        early.cancel()
        return {"status": "guard_refused", "reason": refused}
    try:   # identity before the claim
        from memsub.sgm.synthetic_pilot_run import source_tree_sha256
        got = {"runner": file_sha(__file__), "profile_script": file_sha(f"/root/repo/{PROFILE_SCRIPT}"),
               "reaper_logic": file_sha(Path(__file__).with_name(LOGIC_FILE)),
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
    child_timeout = child_timeout_s(modal.Dict.from_name(GUARD_DICT).get("deadline_epoch", None), time.time())
    if child_timeout is None:                          # recomputed AT launch (codex 21456)
        return {"status": "late_refused", "reason": "too little time left at child launch"}
    sampler = start_gpu_sampler(out.parent / f"{RUN_ID}.gpu-util.csv")   # beside out: the profile creates out
    try:   # outer timeout + external exit capture around the child profile
        proc = subprocess.run([sys.executable, "-u", f"/root/repo/{PROFILE_SCRIPT}", "--out", str(out)],
                              cwd="/root/repo", capture_output=True, text=True, timeout=child_timeout)
        rc, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        rc, stdout, stderr = "outer_timeout", str(e.stdout or ""), str(e.stderr or "")
    finally:
        sampler_status = stop_gpu_sampler(sampler)
    (out.parent / f"{RUN_ID}.exit.json").write_text(json.dumps(
        {"child_exit": rc, "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-4000:],
         "gpu_sampler": sampler_status}, indent=2))
    artifacts.commit()
    profile = json.loads((out / "profile.json").read_text()) if (out / "profile.json").exists() else None
    usable, why = profile_usable(profile, rc, expected["memsub"])
    return {"status": "profiled" if usable else "profile_unusable", "reason": why, "child_exit": rc,
            "profile": profile}


def start_gpu_sampler(path: Path):
    """Descriptive GPU utilisation trace; any failure is recorded, never fatal."""
    try:
        return subprocess.Popen(["nvidia-smi", "--query-gpu=timestamp,utilization.gpu,utilization.memory,memory.used",
                                 "--format=csv,noheader,nounits", f"--loop-ms={GPU_SAMPLE_MS}", f"--filename={path}"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception as e:
        return f"sampler not started: {e!r:.200}"


def stop_gpu_sampler(sampler) -> str:
    if not isinstance(sampler, subprocess.Popen):
        return str(sampler)
    try:
        sampler.terminate()
        sampler.wait(timeout=10)
    except Exception:
        sampler.kill()
    return f"stopped (rc {sampler.returncode})"


def profile_usable(profile: dict | None, child_exit, memsub_sha: str) -> tuple[bool, str]:
    """R3: timings are usable only for exit 0, the bound source, a complete environment,
    status complete, exactly the registered four configs in order, each with 10 updates =
    2 finite positive warmups + 8 finite positive measured timings whose mean equals the
    reported mean, and finite positive dev-eval time and memory fields."""
    def pos(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0
    if child_exit != 0:
        return False, f"child exit {child_exit}"
    if not isinstance(profile, dict) or profile.get("status") != "complete":
        return False, f"profile status {profile.get('status') if isinstance(profile, dict) else None}"
    if profile.get("memsub_source_sha256") != memsub_sha:
        return False, "profile memsub source differs from the bound source"
    env = profile.get("environment") or {}
    if (not str(env.get("python", "")).startswith(EXPECTED_ENV["python_prefix"])
            or env.get("torch") != EXPECTED_ENV["torch"] or env.get("cuda") != EXPECTED_ENV["cuda"]
            or EXPECTED_ENV["gpu_contains"] not in str(env.get("gpu", "")) or not pos(env.get("gpu_total_bytes"))
            or env.get("tf32_matmul") is not False):
        return False, "environment differs from the registered pinned environment"
    if profile.get("contract") != CONTRACT:
        return False, "contract differs from the registered contract"
    cfgs = profile.get("configs") or []
    if [(c.get("arm"), c.get("phase")) for c in cfgs] != EXPECTED_CONFIGS:
        return False, "configs differ from the registered matrix"
    for c in cfgs:
        w, m = c.get("warmup_s") or [], c.get("measured_s") or []
        tag = f"{c.get('arm')} phase {c.get('phase')}"
        if c.get("train_filler_len") != PHASE_FILLER[c.get("phase")]:
            return False, f"{tag}: training filler length differs from the registered phase"
        if c.get("updates") != 10 or len(w) != 2 or len(m) != 8 or not all(pos(v) for v in w + m):
            return False, f"{tag}: incomplete or non-finite update timings"
        mean = c.get("mean_measured_s_per_update")
        if not pos(mean) or abs(mean - sum(m) / len(m)) > 1e-9 * max(1.0, mean):
            return False, f"{tag}: reported mean inconsistent with measured timings"
        if not all(pos(c.get(k)) for k in ("dev_eval_batch_s", "peak_train_memory_bytes", "peak_memory_bytes")):
            return False, f"{tag}: non-finite dev-eval time or memory field"
    return True, "complete registered matrix"


# ---------------- local side ----------------

def charge_bound() -> dict:
    """Lifetime basis: max_containers=1, so GPU-container time cannot exceed the app's
    life, which the in-app reaper ends at the deadline (+ one period + stop latency).
    Plus the scheduled reaper ticks, the single timed build function with a 2x CPU/RAM
    overuse allowance, and a fixed margin."""
    rate = GPU_USD_S + CPU_CORES * CPU_USD_CORE_S + MEMORY_GIB * MEM_USD_GIB_S
    reaper_rate = 0.125 * CPU_USD_CORE_S + 0.25 * MEM_USD_GIB_S
    reaper_ticks = math.ceil((ABANDON_S + OVERALL_S + REAPER_PERIOD_S + STOP_LATENCY_S) / REAPER_PERIOD_S)
    parts = {"gpu_container_lifetime_usd": (OVERALL_S + REAPER_PERIOD_S + STOP_LATENCY_S) * rate,
             "reaper_ticks_usd": reaper_ticks * 110 * reaper_rate,
             "image_build_usd": BUILD_S * BUILD_OVERUSE * (BUILD_CPU * CPU_USD_CORE_S + BUILD_GIB * MEM_USD_GIB_S),
             "fixed_margin_usd": FIXED_MARGIN_USD}
    total = sum(parts.values())
    return {**parts, "usd_per_container_hour": rate * 3600, "reserved_total_usd": total, "cap_usd": CAP_USD,
            "admitted": total <= CAP_USD, "gpu": GPU, "preemptible": True, "max_starts": MAX_STARTS,
            "overall_deadline_s": OVERALL_S, "reaper_period_s": REAPER_PERIOD_S, "abandon_s": ABANDON_S,
            "build_basis": f"one run_function: timeout {BUILD_S}s, {BUILD_CPU} cores/{BUILD_GIB} GiB requested, "
                           f"{BUILD_OVERUSE}x overuse allowance",
            "assumptions": ["reaper period and stop latency are nominal scheduling allowances, not platform guarantees",
                            "build CPU/RAM are requests; the 2x overuse allowance is an assumption",
                            "list prices from modal.com/pricing checked 2026-10-06"]}


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def expected_identity() -> dict:
    sys.path.insert(0, str(Path.cwd()))
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    return {"runner": file_sha(__file__), "profile_script": file_sha(PROFILE_SCRIPT),
            "reaper_logic": file_sha(Path(__file__).with_name(LOGIC_FILE)),
            "memsub": source_tree_sha256(Path("memsub"))}


def _load(path: str, name: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, Path(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def spawn() -> None:
    if subprocess.run(["git", "status", "--porcelain", "--", "memsub", __file__, PROFILE_SCRIPT,
                       f"modal-runners/{LOGIC_FILE}"],
                      capture_output=True, text=True, check=True).stdout.strip():
        raise SystemExit("refusing to spawn from a dirty tree")
    ledger = charge_bound()
    if not ledger["admitted"]:
        raise SystemExit(f"not admitted: ${ledger['reserved_total_usd']:.4f} > cap ${CAP_USD}")
    fn = modal.Function.from_name(APP_NAME, "run_profile")
    fn.hydrate()
    guard = modal.Dict.from_name(GUARD_DICT, create_if_missing=True)
    if set(guard.keys()) - {"first_tick"}:                 # only the reaper's first tick may precede spawn
        raise SystemExit("guard Dict already used: a profile was spawned before")
    root = Path(LOCAL_OUT) / GROUP
    root.mkdir(parents=True, exist_ok=False)           # a second spawn refuses here
    now = time.time()
    prov = {"expected_identity": expected_identity(), "ledger": ledger, "spawn_epoch": now,
            "deadline_epoch": now + OVERALL_S,
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "deployed_app_id": modal.App.lookup(APP_NAME).app_id}
    atomic_write(root / "launch_provenance.json", json.dumps(prov, indent=2))   # app id saved BEFORE spawn
    if not (guard.put("app_id", prov["deployed_app_id"], skip_if_exists=True)
            and guard.put("deadline_epoch", prov["deadline_epoch"], skip_if_exists=True)):
        raise SystemExit("guard app id / deadline already set")
    call = fn.spawn(prov["expected_identity"]).object_id
    atomic_write(root / "call.json", json.dumps({"call_id": call}))
    guard.put("call_id", call, skip_if_exists=True)        # lets the reaper cancel it server-side
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
        report["usable"], report["usable_reason"] = profile_usable(
            payload.get("profile"), payload.get("child_exit"), prov["expected_identity"]["memsub"])
    atomic_write(root / "collect_status.json", json.dumps(report, indent=2, default=str))
    print(json.dumps({k: v for k, v in report.items() if k != "result"}, default=str))
    return report


def fetch_evidence(root: Path) -> dict:
    """Pull m4-sgm/<GROUP> (exit json, profile.json, progress.jsonl, gpu-util.csv) from the volume."""
    dest = root / "volume-evidence"
    dest.mkdir(exist_ok=True)
    got = subprocess.run([sys.executable, "-m", "modal", "volume", "get", "--force", "memsub-artifacts",
                          f"m4-sgm/{GROUP}", str(dest)], capture_output=True, text=True, timeout=300)
    return {"returncode": got.returncode, "stderr_tail": got.stderr[-500:]}


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    {"plan": lambda: print(json.dumps(charge_bound(), indent=2)), "spawn": spawn, "collect": collect}[sys.argv[1]]()
