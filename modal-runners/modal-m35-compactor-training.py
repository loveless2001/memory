"""M3.5 compactor training on Modal (COMPACTOR.md §2.2).

GT12 sanity run (t=512, T=4k, 350 steps — loss must fall below 0.4 by ~300)
then the sweep t ∈ {128, 512, 1024} @ T=8k, 1500 steps, plus ONE iterative
family at 2k chunking. 8×H100 per run, DDP over compactor params only.

Usage:
  modal run modal-runners/modal-m35-compactor-training.py::gt12_sanity
  modal run --detach modal-runners/modal-m35-compactor-training.py::sweep
"""

import json
import subprocess

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
app = modal.App("memsub-m35-train")
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


def _train(t_latents: int, steps: int, ctx: int, lr: float, iterative: bool,
           tag: str) -> dict:
    out_dir = f"/artifacts/compactor-checkpoints/{tag}"
    cmd = ["torchrun", "--standalone", "--nproc_per_node=8",
           "/root/repo/compactor-ddp-training-inner-script.py",
           "--t-latents", str(t_latents), "--steps", str(steps),
           "--ctx-tokens", str(ctx), "--lr", str(lr), "--out-dir", out_dir]
    if iterative:
        cmd.append("--iterative")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout[-6000:])
    print(proc.stderr[-3000:])
    artifacts.commit()
    curve = []
    try:
        with open(f"{out_dir}/loss-curve.json") as f:
            curve = json.load(f)
    except FileNotFoundError:
        pass
    return {"tag": tag, "exit": proc.returncode,
            "final_loss": curve[-1] if curve else None,
            "loss_at_300": curve[299] if len(curve) >= 300 else None}


@app.function(image=image, gpu="H100:8", volumes=VOLUMES, timeout=14400,
              memory=262144, cpu=32)
def gt12_sanity() -> dict:
    """t=512 / T=4k, 350 steps: loss < 0.4 by ~300 or stop and debug."""
    res = _train(512, 350, 4096, 4e-5, False, "gt12-sanity-t512-T4k")
    res["gt12_pass"] = (res["loss_at_300"] is not None
                        and res["loss_at_300"] < 0.4)
    return res


@app.function(image=image, gpu="H100:8", volumes=VOLUMES, timeout=43200,
              memory=262144, cpu=32)
def train_one(t_latents: int, iterative: bool = False) -> dict:
    tag = (f"iterative-t{t_latents}-c2048" if iterative
           else f"single-t{t_latents}-T8k")
    return _train(t_latents, 1500, 8192, 2e-4 if iterative else 4e-5,
                  iterative, tag)


@app.local_entrypoint()
def sweep():
    handles = [train_one.spawn(t) for t in (128, 512, 1024)]
    print("spawned sweep:", [h.object_id for h in handles])


@app.local_entrypoint()
def iterative():
    h = train_one.spawn(512, True)
    print("spawned iterative:", h.object_id)
