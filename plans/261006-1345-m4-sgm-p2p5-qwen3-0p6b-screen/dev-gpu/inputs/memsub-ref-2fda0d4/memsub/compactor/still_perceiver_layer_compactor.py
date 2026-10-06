"""One-layer Still-class Perceiver compactor (COMPACTOR.md §2.1 constants).

Per transformer layer: a per-KV-head bank of t learned latent queries (H
banks) with linear projections SHARED across heads. Input X = [K_unrotated;
V] per head (T x 2d). B=2 blocks, pre-norm, cross-attention in every block,
latent self-attention, NO FFN, RMSNorm, QK-norm (L2 after projection),
logit scale d_l (not 1/sqrt), nc = ns = 1 heads. Compactor-internal RoPE
base 10; latent positions evenly spaced over the compacted range.

Identity-style init (GT11 contract): value/output path is block-diagonal
identity (v-path bypasses the pre-norm so values pass through exactly),
refinement (block-2 and self-attention) output projections zeroed, and the
Q/K pathway is position-dominated: content projections start at zero and a
learned additive vector, rotated by the internal RoPE, makes attention a
kernel peaked at matching positions. With t = T this reproduces the input
KV up to attention-kernel leakage, which the d_l logit scale makes
negligible.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from .rope_rotation_helpers import apply_rotation, rope_cos_sin

INTERNAL_ROPE_BASE = 10.0


class _QKNormCrossAttention(nn.Module):
    """Single-head attention with QK L2-norm and logit scale d_l."""

    def __init__(self, d_l: int, zero_output: bool):
        super().__init__()
        self.d_l = d_l
        self.q_proj = nn.Linear(d_l, d_l, bias=False)
        self.k_proj = nn.Linear(d_l, d_l, bias=False)
        self.v_proj = nn.Linear(d_l, d_l, bias=False)
        self.o_proj = nn.Linear(d_l, d_l, bias=False)
        # position-dominated Q/K pathway: additive anchors, zeroed content
        self.q_anchor = nn.Parameter(torch.ones(d_l) / d_l**0.5)
        self.k_anchor = nn.Parameter(torch.ones(d_l) / d_l**0.5)
        nn.init.zeros_(self.q_proj.weight)
        nn.init.zeros_(self.k_proj.weight)
        if zero_output:
            nn.init.zeros_(self.o_proj.weight)
        else:
            nn.init.eye_(self.o_proj.weight)

    def forward(self, z_normed, kv_normed, kv_values, q_cos, q_sin, k_cos, k_sin):
        """z_normed [B*, t, d_l] queries; kv_normed keys' source [B*, S, d_l];
        kv_values [B*, S, d_l] (identity path — may be un-normed input)."""
        q = apply_rotation(self.q_proj(z_normed) + self.q_anchor, q_cos, q_sin)
        k = apply_rotation(self.k_proj(kv_normed) + self.k_anchor, k_cos, k_sin)
        q = torch.nn.functional.normalize(q, dim=-1)
        k = torch.nn.functional.normalize(k, dim=-1)
        attn = torch.softmax(q @ k.transpose(-1, -2) * self.d_l, dim=-1)
        return self.o_proj(attn @ self.v_proj(kv_values))


class StillPerceiverLayerCompactor(nn.Module):
    def __init__(self, n_kv_heads: int, head_dim: int, t_latents: int,
                 n_blocks: int = 2):
        super().__init__()
        self.h = n_kv_heads
        self.d = head_dim
        self.d_l = 2 * head_dim          # REQUIRED by identity-style init
        self.t = t_latents
        # per-KV-head latent bank, shared projections across heads
        self.latents = nn.Parameter(torch.zeros(self.h, t_latents, self.d_l))
        self.z_norms = nn.ModuleList(nn.RMSNorm(self.d_l) for _ in range(n_blocks))
        self.x_norms = nn.ModuleList(nn.RMSNorm(self.d_l) for _ in range(n_blocks))
        self.cross = nn.ModuleList(
            _QKNormCrossAttention(self.d_l, zero_output=(b > 0))
            for b in range(n_blocks))
        self.self_norms = nn.ModuleList(nn.RMSNorm(self.d_l) for _ in range(n_blocks))
        self.selfattn = nn.ModuleList(
            _QKNormCrossAttention(self.d_l, zero_output=True)
            for _ in range(n_blocks))
        # block 1 value path exact identity
        nn.init.eye_(self.cross[0].v_proj.weight)
        for b in range(1, n_blocks):
            nn.init.eye_(self.cross[b].v_proj.weight)
        # output heads shared across heads within the layer:
        # block-diagonal identity — key head selects the K half, value head
        # selects the V half of Z = [K_unrot; V].
        self.w_key = nn.Linear(self.d_l, self.d, bias=False)
        self.w_val = nn.Linear(self.d_l, self.d, bias=False)
        with torch.no_grad():
            self.w_key.weight.zero_()
            self.w_key.weight[:, :self.d] = torch.eye(self.d)
            self.w_val.weight.zero_()
            self.w_val.weight[:, self.d:] = torch.eye(self.d)

    def forward(self, k_unrot: torch.Tensor, v: torch.Tensor,
                input_positions: torch.Tensor, latent_positions: torch.Tensor,
                ) -> tuple[torch.Tensor, torch.Tensor]:
        """k_unrot, v: [B, H, T, d] (keys already un-rotated).
        Returns (c_k_unrot, c_v): [B, H, t, d] — caller re-rotates c_k."""
        bsz = k_unrot.shape[0]
        x = torch.cat([k_unrot, v], dim=-1)              # [B, H, T, 2d]
        x = x.reshape(bsz * self.h, -1, self.d_l)
        z = self.latents.unsqueeze(0).expand(bsz, -1, -1, -1) \
            .reshape(bsz * self.h, self.t, self.d_l)

        dt, dev = x.dtype, x.device
        q_cos, q_sin = rope_cos_sin(latent_positions, self.d_l,
                                    INTERNAL_ROPE_BASE, dt, dev)
        k_cos, k_sin = rope_cos_sin(input_positions, self.d_l,
                                    INTERNAL_ROPE_BASE, dt, dev)
        for blk in range(len(self.cross)):
            # pre-norm on the K pathway; the value pathway sees raw x so the
            # identity init passes values through exactly (GT11)
            z = z + self.cross[blk](self.z_norms[blk](z),
                                    self.x_norms[blk](x), x,
                                    q_cos, q_sin, k_cos, k_sin)
            zn = self.self_norms[blk](z)
            z = z + self.selfattn[blk](zn, zn, z, q_cos, q_sin, q_cos, q_sin)

        z = z.reshape(bsz, self.h, self.t, self.d_l)
        return self.w_key(z), self.w_val(z)
