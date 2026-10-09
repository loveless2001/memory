"""Occupied-cell query-read fallback `occupied_softmax_fill_v1` (a VARIANT, not the
M4-SGM.md §5.3 spec read; spec: plans/261009-0945-m4-sgm-p2p5-occupied-cell-read-fallback-spec/).

Per bank (batch, layer, head) at a QUERY read, with read address a (cells), 3x3 stencil
weights w_c, presence p_c and the bank's occupied cells j (integer centres c_j, states S_j):
    m      = sum_c w_c p_c                         (original-stencil present mass)
    pi_j   = softmax_j(-|a - c_j|^2 / tau)    (computed as softmax_j((2 a.c_j - |c_j|^2) / tau))
    r      = sum_c w_c S_c^T q  +  (1 - m) * sum_j pi_j S_j^T q
An empty bank adds nothing (r = 0, anchor 0). m = 1 leaves the spec read unchanged; the fill
is continuous in a because B-spline weights vanish at the stencil edge. (1 - m) keeps its
gradient. The softmax over -|a - c|^2 loses the |a|^2 term, so it reweights stored cells
but does not pull a read back toward the bank; that is the anchor's job:
    anchor = (1 - m).detach() * (sqrt(1 + d_min^2) - 1),   d_min = min_j |a - c_j|
(pseudo-Huber: slope <= 1 per cell, gradient toward the nearest occupied cell, whichever
binding it holds). The anchor only enters the training loss (synthetic_pilot.train).
Source-ingestion reads and all writes are untouched; only evaluate_query reads use this.
"""

from __future__ import annotations

import torch

from .sparse_cell_bank import SparseBankSet


def occupied_cells(banks: SparseBankSet, layer: int):
    """-> (centres [B,H,N,2] f32, states [B,H,N,dk,dv], mask [B,H,N] bool), N = max
    occupancy at `layer` (>= 1); padding slots are zero states at (0, 0), mask False."""
    B, H = banks.batch, banks.heads
    items = [list(banks.cells[(b, layer, h)].items()) for b in range(B) for h in range(H)]
    n = max(1, max(len(x) for x in items))
    zero = torch.zeros(banks.key_dim, banks.value_dim, dtype=torch.float32, device=banks.device)
    xy, states, mask = [], [], []
    for bank in items:
        pad = n - len(bank)
        xy += [c for c, _ in bank] + [(0, 0)] * pad
        states += [s for _, s in bank] + [zero] * pad
        mask += [True] * len(bank) + [False] * pad
    banks.counters.cells_read += sum(len(x) for x in items)
    return (torch.tensor(xy, dtype=torch.float32, device=banks.device).view(B, H, n, 2),
            torch.stack(states).view(B, H, n, banks.key_dim, banks.value_dim),
            torch.tensor(mask, dtype=torch.bool, device=banks.device).view(B, H, n))


def fill_read(banks: SparseBankSet, layer: int, a: torch.Tensor, w: torch.Tensor,
              present: list, q: torch.Tensor, tau: float, trace: dict) -> torch.Tensor:
    """a [B,H,2] read address, w [B,H,9] stencil weights, present = host list of the
    gather (B*H*9 flags), q [B,H,dk] -> fill term [B,H,dv] to ADD to the spec read.
    Appends detached telemetry to trace["query_fallback"] and the (attached) anchor
    term [B,H] to trace["query_anchor"]."""
    centres, states, mask = occupied_cells(banks, layer)
    m = (w * torch.tensor(present, dtype=w.dtype, device=w.device).view_as(w)).sum(-1)   # [B,H]
    has = mask.any(-1)                                                                     # [B,H]
    d2 = ((a.unsqueeze(2) - centres) ** 2).sum(-1)                                         # [B,H,N]
    # -|a - c|^2 / tau up to the per-read constant -|a|^2 / tau (softmax-invariant); this
    # form keeps FP32 precision for far reads, where d2 itself is large.
    logits = (2 * (a.unsqueeze(2) * centres).sum(-1) - (centres ** 2).sum(-1)) / tau
    logits = logits.masked_fill(~mask, float("-inf"))
    logits = torch.where(has.unsqueeze(-1), logits, torch.zeros_like(logits))   # empty bank: no NaN
    pi = torch.softmax(logits, dim=-1)
    fill = torch.einsum("bhn,bhnkv,bhk->bhv", pi, states, q)
    d2min = torch.where(has, d2.masked_fill(~mask, float("inf")).min(-1).values, torch.zeros_like(m))
    anchor = (1 - m).detach() * (torch.sqrt(1 + d2min) - 1)                     # 0 for an empty bank
    entropy = -(pi * pi.clamp_min(1e-12).log()).sum(-1)
    trace.setdefault("query_fallback", []).append({
        "present_mass": m.detach(), "has_occupied": has,
        "nearest_cells": d2min.detach().sqrt(), "support_cells": entropy.detach().exp()})
    trace.setdefault("query_anchor", []).append(anchor)
    return ((1 - m) * has).unsqueeze(-1) * fill


def query_anchor_loss(query_traces: list) -> torch.Tensor:
    """Unscaled mean anchor over every query read (queries x layers x batch x heads)."""
    terms = [t for tr in query_traces for t in tr.get("query_anchor", [])]
    if not terms:
        raise RuntimeError("read_fallback_anchor > 0 but no query read recorded an anchor term")
    return torch.stack(terms).mean()


def fallback_summary(rows: list) -> dict:
    """Evaluation telemetry over trace["query_fallback"] rows. The ORIGINAL stencil's
    absent mass stays in query_empty_read_weight (measured before any fill)."""
    cat = lambda k: torch.cat([r[k].flatten() for r in rows])  # noqa: E731
    m, has = cat("present_mass"), cat("has_occupied")
    near, support = cat("nearest_cells")[has], cat("support_cells")[has]
    return {"query_fully_absent_fraction": float((m == 0).double().mean()),
            "query_without_occupied_fraction": float((~has).double().mean()),
            "query_nearest_occupied_cells_mean": float(near.double().mean()) if near.numel() else None,
            "query_fill_support_cells_mean": float(support.double().mean()) if support.numel() else None}
