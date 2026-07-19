"""FULLRECIPE Q1 support — one-shot I1 entropy/kernel snapshot of an
EXISTING checkpoint (instance A, reseed B) on the same fixed 128-item probe
batch the instrumented trainer uses (first 128 rows of ctx-tokens-full.npy).
Makes the collapse-curve endpoints measurement-identical to the mid/full
telemetry points.

Writes /artifacts/fullrecipe-telemetry/snapshot-{tag}/entropy-telemetry.jsonl
       (+ kernel-hist / argmax npz) via the shared telemetry module.

Usage:
  modal run modal-runners/modal-fullrecipe-i1-entropy-snapshot-for-existing-checkpoint.py --tag single-t1024-T8k
"""

import json

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
app = modal.App("memsub-fullrecipe-i1-snapshot")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
    .add_local_file(
        "modal-runners/fullrecipe-entropy-telemetry-capture-module.py",
        "/root/repo/fullrecipe-entropy-telemetry-capture-module.py")
    .add_local_dir("memsub", "/root/repo/memsub")
)
hf_cache = modal.Volume.from_name("memsub-hf-cache", create_if_missing=True)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/root/.cache/huggingface": hf_cache, "/artifacts": artifacts}


class _NoDist:
    """Single-process shim for the telemetry module's reduce calls."""

    @staticmethod
    def all_reduce(t):
        return t


@app.function(image=image, gpu="H100", volumes=VOLUMES, timeout=7200,
              memory=65536)
def snapshot(tag: str, step_label: int = -1) -> dict:
    import importlib.util
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch
    from memsub.compactor import StillAmortizedKVCompactor
    from transformers import AutoModelForCausalLM

    spec = importlib.util.spec_from_file_location(
        "entropy_telemetry",
        "/root/repo/fullrecipe-entropy-telemetry-capture-module.py")
    telemetry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(telemetry)

    model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen3-4B-Instruct-2507", torch_dtype=torch.bfloat16,
        attn_implementation="sdpa").to("cuda").eval()
    model.requires_grad_(False)
    comp = StillAmortizedKVCompactor.load(
        f"/artifacts/compactor-checkpoints/{tag}/compactor.safetensors",
        model.config, device="cuda").to(torch.float32)
    telemetry.install(int(model.config.num_hidden_layers), "cuda")
    telemetry.mark_layers(comp)

    arr = np.load("/artifacts/corpus-fullrecipe/ctx-tokens-full.npy",
                  mmap_mode="r")
    probe_ctx = [arr[g].tolist() for g in range(128)]
    rec = telemetry.probe_pass(
        step_label, model, comp, probe_ctx, "cuda",
        f"/artifacts/fullrecipe-telemetry/snapshot-{tag}", 0, _NoDist,
        save_item_argmax=True)
    artifacts.commit()
    return {"tag": tag,
            "entropy_mean_over_layers": rec["entropy_mean_over_layers"],
            "kept_l0": rec["kept_positions_per_layer"][0]}


@app.local_entrypoint()
def main(tag: str):
    print(json.dumps(snapshot.remote(tag), indent=1))
