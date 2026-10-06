"""Quadratic B-spline 3x3 stencil — M4-SGM.md §5.2.

For one coordinate x:
    n = floor(x + 0.5);  f = x - n  (-0.5 <= f < 0.5)
    indices = [n-1, n, n+1]
    weights = [0.5*(0.5-f)^2, 0.75-f^2, 0.5*(0.5+f)^2]

The integer choice n is discrete (no gradient); the weights depend on f and
carry piecewise-smooth (C1) coordinate gradients. The 2D stencil is the outer
product: nine non-negative weights summing to one.
"""

from __future__ import annotations

import torch

_OFFSETS = torch.tensor([-1, 0, 1], dtype=torch.long)


def stencil_1d(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """x [...] -> (indices [..., 3] long, weights [..., 3] same dtype as x)."""
    n = torch.floor(x.detach() + 0.5)
    f = x - n
    w = torch.stack([0.5 * (0.5 - f) ** 2, 0.75 - f ** 2, 0.5 * (0.5 + f) ** 2], dim=-1)
    idx = n.long().unsqueeze(-1) + _OFFSETS.to(x.device)
    return idx, w


def stencil_2d(coords: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """coords [..., 2] -> (indices [..., 9, 2] long, weights [..., 9]).

    Cell c = 3*i + j pairs x-offset i with y-offset j."""
    ix, wx = stencil_1d(coords[..., 0])
    iy, wy = stencil_1d(coords[..., 1])
    shape = ix.shape[:-1]
    idx = torch.stack([ix.unsqueeze(-1).expand(*shape, 3, 3),
                       iy.unsqueeze(-2).expand(*shape, 3, 3)], dim=-1)
    w = wx.unsqueeze(-1) * wy.unsqueeze(-2)
    return idx.reshape(*shape, 9, 2), w.reshape(*shape, 9)


def single_cell(coords: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Fixed single-bank control (§15): every address maps to cell (0, 0)
    with weight one, padded to the 9-slot layout with zero-weight slots that
    never allocate."""
    shape = coords.shape[:-1]
    idx = torch.zeros(*shape, 9, 2, dtype=torch.long, device=coords.device)
    # distinct dummy coordinates for the zero-weight padding slots
    idx[..., 1:, 0] = torch.arange(1, 9, device=coords.device)
    w = torch.zeros(*shape, 9, dtype=coords.dtype, device=coords.device)
    w[..., 0] = 1.0
    return idx, w
