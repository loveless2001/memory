"""Training checkpoint / resume for the SGM pilot (P2.5 option A, user 21472/21474).

A preempted training cell continues from its last checkpoint instead of being lost.
The checkpoint is taken at the START of loop iteration `step` (after exactly `step`
optimizer updates, before that iteration's fixed-endpoint checkpoint / dev eval /
update), so a resumed run re-executes iteration `step` in full and every later
iteration sees the same parameters, optimizer moments, data-generator state and
global RNG state as the uninterrupted run. It carries:
  adapters + head weights, AdamW state, the episode generator state, the global CPU
  (and CUDA) RNG states, the telemetry rows already logged and the fixed-endpoint
  checkpoints already taken, plus the exact PilotConfig (resume refuses any other).
Files are written atomically (tmp + fsync + rename): a crash mid-save leaves the
previous checkpoint intact.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

import torch

FORMAT = "m4-sgm-train-resume-v1"


def training_state(step: int, pcfg, runtime, head, opt, gen: torch.Generator,
                   telemetry: list, checkpoints: dict) -> dict:
    """Snapshot (tensors cloned to CPU) — safe to serialise after training continues."""
    def cpu(sd: dict) -> dict:
        return {k: v.detach().to("cpu", copy=True) for k, v in sd.items()}

    opt_sd = opt.state_dict()
    opt_state = {i: {k: (v.detach().to("cpu", copy=True) if torch.is_tensor(v) else v) for k, v in s.items()}
                 for i, s in opt_sd["state"].items()}
    return {"format": FORMAT, "step": step, "pilot_config": asdict(pcfg),
            "adapters": cpu(runtime.adapters.state_dict()), "head": cpu(head.state_dict()),
            "optimizer": {"state": opt_state, "param_groups": opt_sd["param_groups"]},
            "data_generator": gen.get_state(), "torch_rng": torch.get_rng_state(),
            "cuda_rng": (torch.cuda.get_rng_state_all() if runtime.device.type == "cuda" else None),
            "telemetry": list(telemetry), "checkpoints": dict(checkpoints)}


def restore_training_state(state: dict, pcfg, runtime, head, opt, gen: torch.Generator) -> int:
    """Load `state` into a freshly built run; returns the step to continue from."""
    if state.get("format") != FORMAT:
        raise ValueError(f"not a {FORMAT} checkpoint: {state.get('format')!r}")
    if state["pilot_config"] != asdict(pcfg):
        raise ValueError("checkpoint was taken under a different PilotConfig")
    runtime.adapters.load_state_dict(state["adapters"])
    head.load_state_dict(state["head"])
    opt.load_state_dict(state["optimizer"])
    gen.set_state(state["data_generator"])
    torch.set_rng_state(state["torch_rng"])
    if state["cuda_rng"] is not None:
        torch.cuda.set_rng_state_all(state["cuda_rng"])
    return int(state["step"])


def save_atomic(state: dict, path: Path) -> None:
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        torch.save(state, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load(path: Path) -> dict:
    return torch.load(Path(path), map_location="cpu", weights_only=False)
