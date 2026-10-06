"""Pinned frozen pretrained backbone for P2.5 (prereg v0.2 `3bf8737`).

`Qwen/Qwen3-0.6B-Base` at a fixed revision; every consumed weight/config file is
sha256-checked before loading (local HF cache, or a directory baked into the
Modal image via $M4_SGM_QWEN3_0P6B_DIR). FP32 compute, frozen, TF32 disabled.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import torch

QWEN3_0P6B_BASE = {
    "repo": "Qwen/Qwen3-0.6B-Base",
    "revision": "da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
    "files": {   # sha256 of the consumed files (model.safetensors is stored BF16)
        "config.json": "504a6b58c4271583724e66584b6b7698aea18450209df6b2f7582df0e89cee59",
        "generation_config.json": "8c970692323e3ea0e9b8b0a4dca79388d31226e41f83c9fd6014804280ebf6e8",
        "model.safetensors": "cd2a512003e2f9f3cd3c32a9c3573f820bb28c940f73c57b1ddaa983d9223eba",
    },
}

# P2.5 SGM geometry (spec-proportional to the 4B default [8,17,26,35]/36).
P2P5_SGM_DEFAULTS = dict(selected_layers=(6, 13, 20, 27), memory_heads=4, key_dim=32, value_dim=32,
                         address_hidden=64, address_scale=8.0, local_recent_tokens=32,
                         pinned_sink_tokens=4, max_cells_per_bank=2048, feature_shift=1)


def snapshot_dir(spec: dict = QWEN3_0P6B_BASE) -> Path:
    env = os.environ.get("M4_SGM_QWEN3_0P6B_DIR")
    if env:
        return Path(env)
    cache = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    return cache / f"models--{spec['repo'].replace('/', '--')}" / "snapshots" / spec["revision"]


def verify_files(root: Path, spec: dict = QWEN3_0P6B_BASE) -> dict:
    """sha256 of every bound file; raises on any mismatch or missing file."""
    got = {}
    for name, want in spec["files"].items():
        h = hashlib.sha256()
        with open(Path(root) / name, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 24), b""):
                h.update(chunk)
        got[name] = h.hexdigest()
        if got[name] != want:
            raise ValueError(f"{spec['repo']}@{spec['revision']}: {name} sha256 {got[name]} != {want}")
    return got


def load_frozen_qwen3_0p6b_base(device: str = "cpu"):
    """Hash-verified, frozen, FP32 Qwen3-0.6B-Base on `device` (TF32 off)."""
    from transformers import AutoModelForCausalLM
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    root = snapshot_dir()
    verify_files(root)
    model = AutoModelForCausalLM.from_pretrained(str(root), torch_dtype=torch.float32, local_files_only=True)
    model = model.to(device).eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return model
