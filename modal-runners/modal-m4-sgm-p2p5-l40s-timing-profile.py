"""M4-SGM P2.5 PAID timing/fit profile on one Modal L40S (user 21446 "continue A";
cap $3 from 21436; prereg v0.2 `3bf8737` § Profile, Gate 2).

Exactly the registered local matrix, run ONCE: scripts/sgm-p2p5-local-gpu-timing-profile.py
(4 configs, 2 warmup + 8 measured updates each = 40, four dev-batch timings, seed 99,
no artifact/reserved populations, no accuracy), under:
  * a first-attempt claim (cleared P2D AttemptLedger): a preempted or replayed input
    is REFUSED, never re-run;
  * the profile's own 1800 s SIGKILL watchdog, plus an OUTER subprocess timeout with
    the child's exit status captured and returned (codex 21445);
  * identity checks before the claim: runner, profile script and memsub source hashes;
    the pinned weight files are sha256-checked by the loader;
  * deploy + spawn, idempotent collect, stop-and-verify by spawn-time app id.

    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py plan     # charge bound, no Modal
    .venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py spawn
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py collect   # idempotent
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import modal

APP_NAME = "memsub-m4-sgm-p2p5-profile"
GROUP = "p2p5-l40s-profile-v1"
RUN_ID = "profile-l40s"
PROFILE_SCRIPT = "scripts/sgm-p2p5-local-gpu-timing-profile.py"
LOCAL_OUT = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
MODEL_DIR = "/root/models/qwen3-0.6b-base"
MODEL_REVISION = "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"
GPU, CPU_CORES, MEMORY_GIB = "L40S", 4.0, 32
OUTER_TIMEOUT_S = 1860          # child profile: own 1800 s watchdog armed before model load
FUNCTION_TIMEOUT_S = 2100       # Modal backstop (image already built; startup bounded separately)
CAP_USD = 3.0                   # user-approved profile cap (#gravity 21436 option (a), 21446)
# Modal list rates (https://modal.com/pricing, checked 2026-10-06), preemptible:
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S = 0.000542, 0.0000131, 0.00000222
STARTUP_S, REPLAY_S, IMAGE_BUILD_USD, FIXED_MARGIN_USD = 300, 420, 0.30, 0.25


def _download_pinned_weights():
    from huggingface_hub import snapshot_download
    snapshot_download("Qwen/Qwen3-0.6B-Base", revision=MODEL_REVISION, local_dir=MODEL_DIR,
                      allow_patterns=["config.json", "generation_config.json", "model.safetensors"])


app = modal.App(APP_NAME)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.7.1", index_url="https://download.pytorch.org/whl/cu126")
         .pip_install("transformers==4.55.2", "safetensors==0.5.3", "numpy==2.2.6")
         .run_function(_download_pinned_weights)
         .env({"HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false", "M4_SGM_QWEN3_0P6B_DIR": MODEL_DIR})
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_file(PROFILE_SCRIPT, f"/root/repo/{PROFILE_SCRIPT}"))
artifacts = modal.Volume.from_name("memsub-artifacts")


def file_sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@app.function(image=image, gpu=GPU, cpu=(CPU_CORES, CPU_CORES), memory=(MEMORY_GIB * 1024, MEMORY_GIB * 1024),
              timeout=FUNCTION_TIMEOUT_S, startup_timeout=STARTUP_S, retries=0, scaledown_window=2,
              max_containers=1, single_use_containers=True, volumes={"/artifacts": artifacts})
def run_profile(expected: dict) -> dict:
    sys.path.insert(0, "/root/repo")
    from memsub.sgm.p2d_launch_guard import (EARLY_DEADLINE_S, AllowanceExhausted, AttemptLedger,
                                             ReplayRefused, Watchdog)
    early = Watchdog(EARLY_DEADLINE_S)
    try:   # identity before the claim: a mismatched deploy exits without claiming or profiling
        from memsub.sgm.synthetic_pilot_run import source_tree_sha256
        got = {"runner": file_sha(__file__), "profile_script": file_sha(f"/root/repo/{PROFILE_SCRIPT}"),
               "memsub": source_tree_sha256(Path("/root/repo/memsub"))}
        if got != expected:
            return {"status": "identity_mismatch", "got": got}
        try:   # one attempt only: preemption/replay is refused, never re-run
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
    profile = out / "profile.json"
    return {"status": "done", "child_exit": rc,
            "profile": json.loads(profile.read_text()) if profile.exists() else None}


# ---------------- local side ----------------

def charge_bound() -> dict:
    """Reserve every charged second at list rates; refuse above the approved cap."""
    rate = GPU_USD_S + CPU_CORES * CPU_USD_CORE_S + MEMORY_GIB * MEM_USD_GIB_S
    parts = {"profile_function_usd": FUNCTION_TIMEOUT_S * rate, "startup_usd": STARTUP_S * rate,
             "refused_replay_usd": REPLAY_S * rate, "image_build_usd": IMAGE_BUILD_USD,
             "fixed_margin_usd": FIXED_MARGIN_USD}
    total = sum(parts.values())
    return {**parts, "usd_per_container_hour": rate * 3600, "reserved_total_usd": total, "cap_usd": CAP_USD,
            "admitted": total <= CAP_USD, "gpu": GPU, "preemptible": True}


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
    root = Path(LOCAL_OUT) / GROUP
    root.mkdir(parents=True, exist_ok=False)           # a second spawn refuses here
    prov = {"expected_identity": expected_identity(), "ledger": ledger,
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "deployed_app_id": modal.App.lookup(APP_NAME).app_id}
    (root / "launch_provenance.json").write_text(json.dumps(prov, indent=2))
    call = fn.spawn(prov["expected_identity"]).object_id
    (root / "call.json").write_text(json.dumps({"call_id": call}))
    print("spawned", call)


def collect() -> dict:
    root = Path(LOCAL_OUT) / GROUP
    call = json.loads((root / "call.json").read_text())["call_id"]
    app_id = json.loads((root / "launch_provenance.json").read_text())["deployed_app_id"]
    tu, v1 = (_load("modal-runners/modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py", "topup"),
              _load("modal-runners/modal-m4-sgm-p2d-diagnostics-grid.py", "v1"))
    kind, payload = tu.poll(call)
    report = {"call_id": call, "poll": kind, "result": payload}
    if kind != "pending":                               # terminal: stop and verify the deployed app
        report["final_shutdown"] = tu.shutdown(v1, app_id)
    (root / "collect_status.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({k: v for k, v in report.items() if k != "result"}, default=str), "child_exit",
          (payload or {}).get("child_exit") if isinstance(payload, dict) else payload)
    return report


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).resolve().parents[1])
    {"plan": lambda: print(json.dumps(charge_bound(), indent=2)), "spawn": spawn, "collect": collect}[sys.argv[1]]()
