"""M4-SGM P2.5 Stage A read-escape blocker screen runner (proposal v0.2; user 21977 "modal run").

ONE ephemeral `modal run` (NOT --detach) under an outer local `timeout`. The local entrypoint calls
the remote arm function in order A0 -> A1 -> A2 and stops at the first problem:
  * after A0, A1/A2 run only if A0 is valid and band_at_100 == "escaped" (the within-setting gate);
  * any remote error, timeout, refused start, non-zero child or INVALID result stops the sequence.
Each call's output tar is extracted locally before the next call, so earlier arms are kept.
Bounds:
  * one L40S with hard CPU/RAM tuples; retries=0; max_containers=1; Modal function timeout
    FUNCTION_S per arm execution (remote whole-worker deadline); child subprocess timeout CHILD_S;
  * restart accounting: first statement of the remote function is an atomic
    Dict.put(arm, ..., skip_if_exists=True) on START_DICT. A rescheduled or second start of the same
    arm finds the key and refuses before any model work (one start per arm, no retries);
  * if the client dies or hits the outer timeout, Modal stops the ephemeral app.
Charge ledger (all-in upper bound; ledger() below):
  outer client lifetime x (GPU + CPU + RAM rates) + worst-case image build + teardown allowance.
Max 3 arms x 100 updates = 300 updates.

    timeout --signal=TERM --kill-after=30s <OUTER_S> .venv/bin/python -m modal run \
        modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py --out <new local dir>
"""

import io
import json
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import modal

APP_NAME = "memsub-m4-sgm-p2p5-stage-a-read-escape"
START_DICT = "m4-sgm-p2p5-stage-a-read-escape-starts-v1"
MODEL_DIR, MODEL_REVISION = "/root/models/qwen3-0.6b-base", "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"
GPU, CPU_CORES, MEMORY_GIB = "L40S", 4.0, 32
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S = 0.000542, 0.0000131, 0.00000222   # modal.com/pricing (codex 21975)
FUNCTION_S, CHILD_S = 1560, 1500
ARMS = ("A0", "A1", "A2")
BUILD_S, TEARDOWN_S, STARTUP_SLACK_S = 1200, 120, 420
OUTER_S = len(ARMS) * FUNCTION_S + STARTUP_SLACK_S
INPUT_MANIFEST = "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"
SCRIPT = "scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py"


def ledger() -> dict:
    """All-in upper bound in USD (rates x durations); expected cost is separate and lower."""
    rate = GPU_USD_S + CPU_CORES * CPU_USD_CORE_S + MEMORY_GIB * MEM_USD_GIB_S
    build = BUILD_S * (4.0 * CPU_USD_CORE_S + 8 * MEM_USD_GIB_S)
    parts = {"client_lifetime_gpu_container": OUTER_S * rate, "image_build_worst": build,
             "teardown_allowance": len(ARMS) * TEARDOWN_S * rate}
    return {"rate_usd_s": rate, "outer_s": OUTER_S, **parts, "bound_usd": sum(parts.values())}


def _build_environment():
    """Same pinned stack and weights as the P2.5 L40S profile / dev-GPU runners (copied, not changed)."""
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
         .run_function(_build_environment, timeout=BUILD_S, cpu=4.0, memory=8 * 1024)
         .env({"HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false", "M4_SGM_QWEN3_0P6B_DIR": MODEL_DIR})
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_file(SCRIPT, f"/root/repo/{SCRIPT}")
         .add_local_file(INPUT_MANIFEST, f"/root/repo/{INPUT_MANIFEST}"))


@app.function(image=image, gpu=GPU, cpu=(CPU_CORES, CPU_CORES), memory=(MEMORY_GIB * 1024, MEMORY_GIB * 1024),
              timeout=FUNCTION_S, retries=0, max_containers=1)
def run_arm_remote(arm: str) -> dict:
    import os
    starts = modal.Dict.from_name(START_DICT, create_if_missing=True)
    first = starts.put(arm, {"task": os.environ.get("MODAL_TASK_ID"), "t": time.time()}, skip_if_exists=True)
    if not first:                                  # restart accounting: never a second start of an arm
        return {"refused": f"arm {arm} already started once", "existing": starts.get(arm)}
    out = Path("/tmp/stage-a-out")
    out.mkdir()
    cmd = [sys.executable, SCRIPT, "--arm", arm, "--manifest", INPUT_MANIFEST, "--out", str(out / arm)]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd="/root/repo", capture_output=True, text=True, timeout=CHILD_S)
        rc, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        rc, stdout, stderr = "timeout", str(e.stdout or ""), str(e.stderr or "")
    (out / f"{arm}.stdout.txt").write_text(stdout)
    (out / f"{arm}.stderr.txt").write_text(stderr)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(out, arcname=".")
    return {"returncode": rc, "wall_s": time.time() - t0, "cmd": cmd, "tar": buf.getvalue()}


def gate_ok(arm: str, dest: Path, res: dict) -> tuple[bool, str]:
    """Continue only if this arm finished cleanly with a valid result; after A0 also require 'escaped'."""
    if "refused" in res:
        return False, f"{arm}: {res['refused']}"
    if res.get("returncode") != 0:
        return False, f"{arm}: child returncode {res.get('returncode')}"
    f = dest / arm / "stage_a_result.json"
    if not f.exists():
        return False, f"{arm}: no stage_a_result.json"
    r = json.loads(f.read_text())
    if r.get("status") != "valid":
        return False, f"{arm}: INVALID ({r.get('why')})"
    if arm == "A0" and r.get("band_at_100") != "escaped":
        return False, f"A0 did not reproduce the escape (band {r.get('band_at_100')}): stop before A1/A2"
    return True, f"{arm}: valid, band {r['band_at_100']}"


@app.local_entrypoint()
def main(out: str):
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=False)
    meta = {"app_id": app.app_id, "arms_planned": list(ARMS), "ledger": ledger(), "started": time.time(),
            "gpu": GPU, "cpu": CPU_CORES, "memory_gib": MEMORY_GIB, "function_s": FUNCTION_S, "arms": {},
            "outcome": "started"}
    (dest / "run.json").write_text(json.dumps(meta, indent=2))

    def on_sigterm(_sig, _frame):                      # outer `timeout` sends SIGTERM first
        raise SystemExit("SIGTERM (outer timeout)")
    signal.signal(signal.SIGTERM, on_sigterm)
    try:
        for arm in ARMS:
            meta["arms"][arm] = {"outcome": "remote call failed", "t_start": time.time()}
            res = run_arm_remote.remote(arm)
            tar = res.pop("tar", None)
            if tar is not None:
                with tarfile.open(fileobj=io.BytesIO(tar), mode="r:gz") as t:
                    t.extractall(dest, filter="data")
            ok, why = gate_ok(arm, dest, res)
            meta["arms"][arm].update(res, outcome=why, t_end=time.time())
            (dest / "run.json").write_text(json.dumps(meta, indent=2))
            print(json.dumps({"arm": arm, "ok": ok, "why": why}), flush=True)
            if not ok:
                meta["outcome"] = f"stopped: {why}"
                break
        else:
            meta["outcome"] = "all arms done"
    except BaseException as e:
        meta["outcome"] = f"error: {type(e).__name__}: {str(e)[:500]}"
        raise
    finally:
        meta["client_wall_s"] = time.time() - meta["started"]
        (dest / "run.json").write_text(json.dumps(meta, indent=2))
        print(json.dumps({"app_id": meta["app_id"], "outcome": meta["outcome"],
                          "client_wall_s": round(meta["client_wall_s"], 1)}))
    if meta["outcome"] != "all arms done":
        raise SystemExit(1)
