"""P2D `learned_addr_supervised` auxiliary pair loss (M4-SGM.md § P2D Step 2).

For each training query and its bound value token, at every selected layer
and head:
    a_r = scale * AddressMLP(q_query.detach())
    a_w = scale * AddressMLP(k_value.detach())
    L_aux = lambda * mean_{batch, query, layer, head, coord} (a_r - a_w)^2
q/k come from DETACHED runtime telemetry (`read_q`, `write_k`); the
coordinates are recomputed through the live AddressMLP, so L_aux sends
gradient ONLY into AddressMLP parameters (never q/k/v/beta/out or upstream
features). Training split only; never used at evaluation.
"""

from __future__ import annotations

import torch

SINKS = 4


def bound_value_positions(source: torch.Tensor, query_keys: torch.Tensor, n_bindings: int) -> torch.Tensor:
    """[B, Q] source positions of each query's bound value token."""
    keys = source[:, SINKS:SINKS + 2 * n_bindings:2]                      # [B, N]
    j = (keys.unsqueeze(1) == query_keys.unsqueeze(-1)).float().argmax(-1)  # [B, Q]
    return SINKS + 2 * j + 1


def address_pair_loss(runtime, source_traces: list, query_traces: list,
                      value_pos: torch.Tensor) -> torch.Tensor:
    """source_traces: per source step; query_traces[q]: trace of query q.
    value_pos [B, Q]. Returns the unscaled mean squared coordinate error."""
    scale, errs = runtime.cfg.address_scale, []
    for q, qtrace in enumerate(query_traces):
        for layer in runtime.cfg.selected_layers:
            mlp = runtime.adapters[str(layer)].address_mlp
            q_vec = qtrace["read_q"][layer][-1]                               # [B, H, dk] detached
            k_vec = torch.stack([source_traces[int(value_pos[b, q])]["write_k"][layer][b]
                                 for b in range(value_pos.shape[0])])          # [B, H, dk] detached
            if q_vec.requires_grad or k_vec.requires_grad:
                raise RuntimeError("auxiliary inputs must be detached telemetry")
            errs.append((scale * mlp(q_vec) - scale * mlp(k_vec)).pow(2))     # [B, H, 2]
    return torch.stack(errs).mean()
