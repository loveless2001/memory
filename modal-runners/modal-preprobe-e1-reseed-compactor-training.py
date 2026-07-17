"""PREPROBE E1 instance B: reseed replication of the shipped t=1024
compactor (PREPROBE.md E1). Identical config/data/objective to
single-t1024-T8k — including the pre-f214c0f legacy multiset-KL variant the
shipped checkpoint was trained under — with ONLY the init seed changed
(1234 -> 51234). Adds a save-then-exit watchdog for the known NCCL
teardown zombie (ADDENDUM-M35 unresolved q3): once the final checkpoint +
full loss curve are on disk, the runner grants a grace period then kills
torchrun instead of burning GPU-hours on a hung destroy_process_group.

Usage:
  modal run --detach modal-runners/modal-preprobe-e1-reseed-compactor-training.py
"""

import json
import subprocess
import time

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
app = modal.App("memsub-preprobe-e1-train")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
    .add_local_file("modal-runners/compactor-ddp-training-inner-script.py",
                    "/root/repo/compactor-ddp-training-inner-script.py")
    .add_local_dir("memsub", "/root/repo/memsub")
)
hf_cache = modal.Volume.from_name("memsub-hf-cache", create_if_missing=True)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/root/.cache/huggingface": hf_cache, "/artifacts": artifacts}

TAG = "single-t1024-T8k-seed51234"
STEPS = 1500
HARD_CAP_S = 6.5 * 3600
GRACE_S = 300


@app.function(image=image, gpu="H100:8", volumes=VOLUMES, timeout=28800,
              memory=262144, cpu=32)
def train_reseed() -> dict:
    import os
    out_dir = f"/artifacts/compactor-checkpoints/{TAG}"
    cmd = ["torchrun", "--standalone", "--nproc_per_node=8",
           "/root/repo/compactor-ddp-training-inner-script.py",
           "--t-latents", "1024", "--steps", str(STEPS),
           "--ctx-tokens", "8192", "--lr", "4e-5", "--out-dir", out_dir,
           "--seed", "51234", "--legacy-kl-multiset"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    # stream child output without blocking the watchdog
    import threading
    tail: list[str] = []

    def pump():
        for line in proc.stdout:
            tail.append(line)
            del tail[:-200]
            print(line, end="", flush=True)
    threading.Thread(target=pump, daemon=True).start()

    start = time.time()
    done_since = None
    killed_after_save = False
    while proc.poll() is None:
        time.sleep(60)
        curve_len = 0
        try:
            with open(f"{out_dir}/loss-curve.json") as f:
                curve_len = len(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        saved = (curve_len >= STEPS
                 and os.path.exists(f"{out_dir}/compactor.safetensors"))
        if saved and done_since is None:
            done_since = time.time()
            print(f"[watchdog] final save detected, {GRACE_S}s grace",
                  flush=True)
        if (saved and time.time() - done_since > GRACE_S) \
                or time.time() - start > HARD_CAP_S:
            killed_after_save = saved
            print("[watchdog] killing torchrun "
                  f"(saved={saved})", flush=True)
            proc.kill()
            break
    artifacts.commit()
    curve = []
    try:
        with open(f"{out_dir}/loss-curve.json") as f:
            curve = json.load(f)
    except FileNotFoundError:
        pass
    ok = len(curve) >= STEPS and os.path.exists(
        f"{out_dir}/compactor.safetensors")
    return {"tag": TAG, "ok": ok, "steps_logged": len(curve),
            "final_loss": curve[-1] if curve else None,
            "loss_at_300": curve[299] if len(curve) >= 300 else None,
            "killed_after_save": killed_after_save,
            "wall_s": round(time.time() - start)}
