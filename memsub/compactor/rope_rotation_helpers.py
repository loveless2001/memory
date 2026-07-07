"""RoPE rotation helpers for the compactor's RoPE-fix (spec §12 / Still).

Synthesizing mixtures of already-rotated keys mixes content with phase and is
empirically unstable, so the compactor (1) inverse-rotates keys into a
position-free frame, (2) runs its own internal RoPE (base 10), and
(3) re-rotates compact keys at their chosen output positions. All helpers use
the standard rotate_half formulation shared by Qwen3.
"""

from __future__ import annotations

import torch


def rotate_half(x: torch.Tensor) -> torch.Tensor:
    x1, x2 = x.chunk(2, dim=-1)
    return torch.cat((-x2, x1), dim=-1)


def rope_cos_sin(positions: torch.Tensor, dim: int, base: float,
                 dtype: torch.dtype, device) -> tuple[torch.Tensor, torch.Tensor]:
    """cos/sin tables [len(positions), dim] for the given positions."""
    inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2, device=device,
                                            dtype=torch.float32) / dim))
    angles = positions.to(device, torch.float32)[:, None] * inv_freq[None, :]
    emb = torch.cat((angles, angles), dim=-1)
    return emb.cos().to(dtype), emb.sin().to(dtype)


def apply_rotation(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
    """Rotate x [..., S, dim] by per-position cos/sin [S, dim]."""
    return x * cos + rotate_half(x) * sin


def unrotate(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
    """Inverse rotation (R(-p)): cos unchanged, sin negated."""
    return x * cos - rotate_half(x) * sin


def model_rope_cos_sin(config, positions: torch.Tensor, dtype, device):
    """cos/sin under the BASE MODEL's RoPE parameters (for un-/re-rotating
    real cache keys at logical positions)."""
    return rope_cos_sin(positions, int(config.head_dim),
                        float(config.rope_theta), dtype, device)
