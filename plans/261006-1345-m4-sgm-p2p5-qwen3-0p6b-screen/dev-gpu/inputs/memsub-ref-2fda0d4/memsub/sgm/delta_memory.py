"""Functional read / delta-update kernels — M4-SGM.md §5.3.

Read (state BEFORE the current token's write):
    r = sum_c w_read[c] * S_c^T q
Write, per addressed cell:
    error_c = v - S_c^T k
    S_c'    = S_c + w_write[c] * beta * outer(k, error_c)
Missing cells contribute zero (no renormalisation over occupied cells).
All arithmetic in FP32; non-finite results fail closed.
"""

from __future__ import annotations

import torch

from ..errors import NonFiniteStateError


def read_memory(cells: torch.Tensor, weights: torch.Tensor, q: torch.Tensor) -> torch.Tensor:
    """cells [B,H,9,dk,dv], weights [B,H,9], q [B,H,dk] -> reads [B,H,dv]."""
    return torch.einsum("bhc,bhckv,bhk->bhv", weights, cells, q)


def delta_update(cells: torch.Tensor, weights: torch.Tensor, beta: torch.Tensor,
                 k: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
    """Associative delta rule on each addressed cell (no decay / clipping).

    cells [B,H,9,dk,dv], weights [B,H,9], beta [B,H], k [B,H,dk], v [B,H,dv]
    -> new cells [B,H,9,dk,dv]."""
    pred = torch.einsum("bhckv,bhk->bhcv", cells, k)
    error = v.unsqueeze(2) - pred                              # [B,H,9,dv]
    step = (weights * beta.unsqueeze(-1)).unsqueeze(-1).unsqueeze(-1)
    new = cells + step * k[:, :, None, :, None] * error[:, :, :, None, :]
    if not torch.isfinite(new).all():
        raise NonFiniteStateError("delta update produced non-finite cell state")
    return new
