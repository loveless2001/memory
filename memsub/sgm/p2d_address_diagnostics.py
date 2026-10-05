"""P2D address diagnostics (descriptive; M4-SGM.md § P2D Step 1).

Geometry uses the ACTUAL quadratic B-spline supports, not a distance proxy:
two addresses "intersect" when their positive-weight 3x3 stencils share a
cell, and their SPATIAL coupling is sum_c w_a(c) * w_b(c). This is only the
spatial factor of read gain: for the delta rule a write changes a fixed query
read by beta (q.k) sum_c w_read(c) w_write(c) [v - S_c^T k], so content
alignment, beta and cell residuals also matter. Euclidean distance
is kept as a separate descriptive metric. All results are per layer/head.

The direct filler test holds the final query's q and read stencil fixed and
reads the bank as it was BEFORE vs AFTER the tail filler was written. It
measures the net effect of tail-filler writes on bank reads / task-head
outputs conditional on that query representation. It does not show that every
error is overwritten content, nor does it include effects mediated through the
query's own representation or the source KV.
"""

from __future__ import annotations

import torch

from .delta_memory import read_memory
from .interpolation import stencil_2d


def stencil_relation(a: torch.Tensor, b: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Coords a, b [..., 2] (broadcastable) -> (intersects bool, coupling float)."""
    ia, wa = stencil_2d(a)
    ib, wb = stencil_2d(b)
    same = (ia.unsqueeze(-2) == ib.unsqueeze(-3)).all(-1)               # [..., 9, 9]
    pos = (wa > 0).unsqueeze(-1) & (wb > 0).unsqueeze(-2)
    coupling = (same * wa.unsqueeze(-1) * wb.unsqueeze(-2)).sum((-1, -2))
    return (same & pos).any(-1).any(-1), coupling


def _per_head(x: torch.Tensor, reduce: str) -> list[float]:
    """x [..., H] -> one value per head (mean or median over the rest)."""
    flat = x.reshape(-1, x.shape[-1]).float()
    return (flat.mean(0) if reduce == "mean" else flat.median(0).values).tolist()


def episode_geometry(write_coords: torch.Tensor, val_pos: list[int], fill_pos: list[int],
                     read_coords: torch.Tensor, query_binding: torch.Tensor) -> dict:
    """write_coords [B, T, H, 2] (source steps), read_coords [B, Q, H, 2],
    query_binding [B, Q] (binding index of each query). Per-head metrics."""
    wv = write_coords[:, val_pos]                                        # [B, N, H, 2]
    n = wv.shape[1]
    hit, coup = stencil_relation(wv.unsqueeze(2), wv.unsqueeze(1))       # [B, N, N, H]
    off = ~torch.eye(n, dtype=torch.bool)[None, :, :, None].expand_as(hit)
    wf = write_coords[:, fill_pos]                                       # [B, F, H, 2]
    f_hit, f_coup = stencil_relation(wf.unsqueeze(2), wv.unsqueeze(1))  # [B, F, N, H]
    bound = torch.gather(wv, 1, query_binding[..., None, None].expand(-1, -1, *wv.shape[2:]))
    a_hit, a_coup = stencil_relation(read_coords, bound)                 # [B, Q, H]
    dist = (read_coords - bound).norm(dim=-1)
    return {
        "align_distance_median": _per_head(dist, "median"),
        "align_within_1_cell": _per_head(dist < 1, "mean"),
        "align_stencil_intersects": _per_head(a_hit, "mean"),
        "align_spatial_coupling_mean": _per_head(a_coup, "mean"),
        "binding_pair_intersect_rate": _per_head(hit[off].view(-1, hit.shape[-1]), "mean"),
        "binding_pair_spatial_coupling_mean": _per_head(coup[off].view(-1, coup.shape[-1]), "mean"),
        "filler_hits_any_binding": _per_head(f_hit.any(2), "mean"),
        "filler_max_spatial_coupling_mean": _per_head(f_coup.max(2).values, "mean"),
    }


def fixed_query_read(banks, layer: int, q: torch.Tensor, coords: torch.Tensor) -> torch.Tensor:
    """Read a bank snapshot with a FIXED query vector and read address.
    q [B, H, dk], coords [B, H, 2] -> reads [B, H, dv]."""
    idx, w = stencil_2d(coords)
    cells, _ = banks.gather(layer, idx)
    return read_memory(cells, w, q)
