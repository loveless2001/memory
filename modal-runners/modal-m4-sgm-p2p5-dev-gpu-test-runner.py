"""M4-SGM P2.5 option A DEV GPU runner (user 21476: "move your testing to modal gpu").

Runs ONE repo script (or pytest) on one Modal L40S and copies its output directory back.
DEV only: hotspot attribution and parity/resume tests at seed 99 / fixtures. Never
registered, artifact or reserved populations, never a campaign cell, no timing claim.
Total option-A dev cap $3 (claude 21477); each run is bounded by itself:
  * EPHEMERAL app (`modal run`, NOT --detach) under an outer local `timeout`: if the
    client dies or times out, Modal stops the app — so a crash-rescheduled container
    cannot outlive the client;
  * remote child under subprocess timeout CHILD_S, Modal function timeout FUNCTION_S,
    max_containers=1, retries=0.
Charge basis per run (reserved in #gravity before launch): client lifetime (outer timeout)
x (L40S + 4 CPU + 32 GiB, hard request=limit tuples) + build + detection/teardown allowance.
Exit status (codex 21482): the local entrypoint exits NONZERO unless the remote child
returned 0; run.json always records the outcome (also failures) before exiting.
Inputs: plans/.../dev-gpu/inputs is mounted read-only at /root/repo/dev-gpu-inputs (the
frozen reference memsub tree for the speed-up parity check).

    timeout --kill-after=15s 1200 .venv/bin/python -m modal run modal-runners/modal-m4-sgm-p2p5-dev-gpu-test-runner.py \
        --script scripts/sgm-p2p5-sgm-path-hotspot-profile.py --out <local dir> [--args "..."]
    (--script pytest --args "tests/test_x.py -q" runs pytest; the out dir then holds its log)
"""

import io
import json
import shlex
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import modal

APP_NAME = "memsub-m4-sgm-p2p5-dev-gpu-test"
MODEL_DIR, MODEL_REVISION = "/root/models/qwen3-0.6b-base", "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"
GPU, CPU_CORES, MEMORY_GIB = "L40S", 4.0, 32
FUNCTION_S, CHILD_S = 1440, 1380
INPUTS_DIR = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/dev-gpu/inputs"
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S = 0.000542, 0.0000131, 0.00000222   # modal.com/pricing
# ONE function execution at FUNCTION_S only — NOT a cumulative bound (restarts, build, teardown excluded;
# codex 21489). The per-run reservation is posted in #gravity before launch.
FUNCTION_ONLY_CHARGE_USD = FUNCTION_S * (GPU_USD_S + CPU_CORES * CPU_USD_CORE_S + MEMORY_GIB * MEM_USD_GIB_S)


def _build_environment():
    """Same pinned stack and weights as the P2.5 L40S profile runner."""
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
         .add_local_dir("tests", "/root/repo/tests", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_dir("configs", "/root/repo/configs")
         .add_local_dir(INPUTS_DIR, "/root/repo/dev-gpu-inputs", ignore=["**/__pycache__/**", "**/*.pyc"]))


@app.function(image=image, gpu=GPU, cpu=(CPU_CORES, CPU_CORES), memory=(MEMORY_GIB * 1024, MEMORY_GIB * 1024),
              timeout=FUNCTION_S, retries=0, max_containers=1)
def run_remote(script: str, args: str) -> dict:
    out = Path("/tmp/dev-out")
    out.mkdir()
    if script == "pytest":
        cmd = [sys.executable, "-m", "pytest", *shlex.split(args)]
    else:
        cmd = [sys.executable, script, "--out", str(out / "result"), *shlex.split(args)]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd="/root/repo", capture_output=True, text=True, timeout=CHILD_S)
        rc, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        rc, stdout, stderr = "timeout", str(e.stdout or ""), str(e.stderr or "")
    (out / "stdout.txt").write_text(stdout)
    (out / "stderr.txt").write_text(stderr)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(out, arcname=".")
    return {"returncode": rc, "wall_s": time.time() - t0, "cmd": cmd, "tar": buf.getvalue()}


@app.local_entrypoint()
def main(script: str, out: str, args: str = ""):
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=False)
    started = time.time()
    meta = {"app_id": app.app_id, "script": script, "args": args, "started": started,
            "function_only_charge_usd": round(FUNCTION_ONLY_CHARGE_USD, 4), "gpu": GPU, "outcome": "started"}
    # "started" left on disk = the client never reached the end (host loss / SIGKILL);
    # the launch wrapper's EXIT_STATUS (124 = outer timeout) is recorded beside it
    (dest / "run.json").write_text(json.dumps(meta, indent=2))

    def on_sigterm(_sig, _frame):                      # outer `timeout` sends SIGTERM first
        raise SystemExit("SIGTERM (outer timeout)")
    signal.signal(signal.SIGTERM, on_sigterm)
    meta["outcome"] = "remote call failed"
    try:
        res = run_remote.remote(script, args)
        with tarfile.open(fileobj=io.BytesIO(res.pop("tar")), mode="r:gz") as tar:
            tar.extractall(dest, filter="data")
        meta.update(res, outcome="ok" if res["returncode"] == 0 else "child failed")
    except BaseException as e:                         # remote error / interrupt: recorded, then fail
        meta["error"] = f"{type(e).__name__}: {str(e)[:500]}"
        raise
    finally:
        meta["client_wall_s"] = time.time() - started
        (dest / "run.json").write_text(json.dumps(meta, indent=2))
        print(json.dumps({k: meta.get(k) for k in ("app_id", "outcome", "returncode", "wall_s", "client_wall_s")}))
    if meta["outcome"] != "ok":
        raise SystemExit(1)
