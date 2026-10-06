"""Trainable SGM adapter for one selected layer — M4-SGM.md §5.1, §5.4, §8.

From the layer's normalised pre-attention hidden z_t (optionally with the
previous token's z when feature_shift=2):
    q = l2norm(W_q x), k = l2norm(W_k x), v = W_v x, beta = sigmoid(w_beta x + b)
    a_read  = address_scale * AddressMLP(q)
    a_write = address_scale * AddressMLP(k)
AddressMLP (two real outputs, no output squashing) is shared by read and
write addressing and by the layer's heads; q/k projections stay distinct.
Output into the residual stream: sigmoid(alpha_logit) * W_out(concat(reads)).
alpha and W_out start small but nonzero so end-to-end address/write
gradients exist at step 0 (agreed in #gravity 21064-21066).
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn

from .config import SGMConfig


class SGMLayerAdapter(nn.Module):
    def __init__(self, cfg: SGMConfig, layer_idx: int, seed: int = 0):
        super().__init__()
        self.cfg, self.layer_idx = cfg, layer_idx
        H, dk, dv = cfg.memory_heads, cfg.key_dim, cfg.value_dim
        d_in = cfg.hidden_size * cfg.feature_shift
        gen = torch.Generator().manual_seed(seed * 1009 + layer_idx)
        self.q_proj = nn.Linear(d_in, H * dk, bias=False)
        self.k_proj = nn.Linear(d_in, H * dk, bias=False)
        self.v_proj = nn.Linear(d_in, H * dv, bias=False)
        self.beta_proj = nn.Linear(d_in, H)
        self.address_mlp = nn.Sequential(
            nn.Linear(dk, cfg.address_hidden), nn.SiLU(), nn.Linear(cfg.address_hidden, 2))
        self.out_proj = nn.Linear(H * dv, cfg.hidden_size, bias=False)
        self.alpha_logit = nn.Parameter(torch.tensor(float(cfg.alpha_init_logit)))
        with torch.no_grad():
            for lin in (self.q_proj, self.k_proj, self.v_proj, self.beta_proj,
                        self.address_mlp[0], self.address_mlp[2]):
                lin.weight.copy_(torch.randn(lin.weight.shape, generator=gen)
                                 / lin.weight.shape[1] ** 0.5)
                if lin.bias is not None:
                    lin.bias.zero_()
            self.out_proj.weight.copy_(
                torch.randn(self.out_proj.weight.shape, generator=gen) * cfg.out_init_std)
            self._calibrate_address_spread(gen)
        if cfg.address_mode == "random_fixed":
            self.address_mlp.requires_grad_(False)

    @torch.no_grad()
    def _calibrate_address_spread(self, gen: torch.Generator) -> None:
        """Scale the final AddressMLP layer so per-coordinate address std over
        random unit inputs equals address_init_spread cells (§8 cold start).
        Coordinates of distinct inputs differ (nonidentical), but overlap."""
        probe = F.normalize(torch.randn(4096, self.cfg.key_dim, generator=gen), dim=-1)
        out = self.cfg.address_scale * self.address_mlp(probe)
        std = out.std(dim=0).mean().clamp_min(1e-8)
        self.address_mlp[2].weight.mul_(self.cfg.address_init_spread / std)

    def project(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        """x [B, n, d_in] fp32 -> per-token, per-head tensors [B, n, H, ...]."""
        B, n, _ = x.shape
        H, dk, dv = self.cfg.memory_heads, self.cfg.key_dim, self.cfg.value_dim
        q = F.normalize(self.q_proj(x).view(B, n, H, dk), dim=-1)
        k = F.normalize(self.k_proj(x).view(B, n, H, dk), dim=-1)
        out = {
            "q": q, "k": k,
            "v": self.v_proj(x).view(B, n, H, dv),
            "beta": torch.sigmoid(self.beta_proj(x)),
        }
        if self.cfg.address_mode in ("learned", "random_fixed"):
            # random_fixed control: routing receives no gradient at all (LSH-like
            # fixed map of the learned keys); learned: full address gradients.
            fixed = self.cfg.address_mode == "random_fixed"
            q_in, k_in = (q.detach(), k.detach()) if fixed else (q, k)
            out["a_read"] = self.cfg.address_scale * self.address_mlp(q_in)
            out["a_write"] = self.cfg.address_scale * self.address_mlp(k_in)
        return out

    def output(self, reads: torch.Tensor) -> torch.Tensor:
        """reads [B, n, H, dv] -> residual contribution [B, n, hidden]."""
        return torch.sigmoid(self.alpha_logit) * self.out_proj(reads.flatten(-2))

    def param_groups(self) -> dict[str, list[nn.Parameter]]:
        """Named groups for per-group gradient/update telemetry (§8)."""
        return {
            "q_proj": [self.q_proj.weight],
            "k_proj": [self.k_proj.weight],
            "value": [self.v_proj.weight],
            "beta": list(self.beta_proj.parameters()),
            "address_mlp": list(self.address_mlp.parameters()),
            "out_proj": [self.out_proj.weight],
            "alpha": [self.alpha_logit],
        }
