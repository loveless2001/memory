"""SGM runtime over a frozen HF Qwen3 backbone — M4-SGM.md §5.4, §6.

Explicit layer loop (no global patches, no state-mutating hooks). At each
selected layer, inside the pinned Qwen3DecoderLayer ordering:

    z = input_layernorm(h); h = h + self_attn(z)
    r = read(bank_before_write, q(z), a_read(z));  h = h + alpha * W_out(r)
    [write: bank <- delta(bank, k(z), v(z), beta(z), a_write(z))]
    h = h + mlp(post_attention_layernorm(h))

`enabled=False` runs the unmodified layer ordering (SGM-01). Positions:
logical for RoPE, physical for the mask (same contract as HFModelRuntime).
Student path is NOT under no_grad/inference_mode: gradients flow through the
frozen backbone into earlier adapters and memory writes (§5.4).
"""

from __future__ import annotations

import uuid

import torch
from torch import nn

from ..sgm.config import SGMConfig
from ..sgm.delta_memory import delta_update, read_memory
from ..sgm.interpolation import single_cell, stencil_2d
from ..sgm.layer_adapter import SGMLayerAdapter
from ..sgm.session_state import SGMSessionState
from ..sgm.sparse_cell_bank import SparseBankSet
from .compacted_prefix_cache import CompactedPrefixCache


class SGMModelRuntime(nn.Module):
    def __init__(self, model, cfg: SGMConfig, seed: int = 0):
        super().__init__()
        self.backbone = model.eval()
        for p in self.backbone.parameters():
            p.requires_grad_(False)
        self.cfg = cfg.resolve(model.config)
        self.adapters = nn.ModuleDict(
            {str(l): SGMLayerAdapter(self.cfg, l, seed) for l in self.cfg.selected_layers})
        self.device = next(model.parameters()).device
        # Diagnostic-only read-address intervention (cells); 0 in every arm.
        self.diag_read_offset = 0.0
        self.runtime_uuid = uuid.uuid4().hex[:16]

    def weights_identity(self) -> str:
        """Ephemeral identity of the live adapter weights: this runtime instance
        plus the summed in-place version counters of its parameters (bumped by
        every optimizer step and by load_state_dict's in-place copy) and the
        identity of the Parameter objects. Live bank/KV state built under
        one identity is rejected under any other (#gravity 21075 P1)."""
        params = list(self.adapters.parameters())
        version = sum(p._version for p in params)          # in-place updates / reloads
        members = hash(tuple(id(p) for p in params)) & 0xFFFFFFFF  # replaced Parameters
        return f"{self.runtime_uuid}:{version}:{members:08x}"

    def new_state(self, batch: int = 1) -> SGMSessionState:
        c = self.cfg
        banks = SparseBankSet(batch, c.selected_layers, c.memory_heads, c.key_dim,
                              c.value_dim, c.max_cells_per_bank, self.device)
        return SGMSessionState(CompactedPrefixCache(c.pinned_sink_tokens), banks, c.policy_id,
                               weights_id=self.weights_identity())

    # -- one forward block ------------------------------------------------------------
    def step(self, state: SGMSessionState, input_ids: torch.Tensor, *, write: bool,
             enabled: bool = True, oracle: dict | None = None,
             logits: bool = False) -> dict:
        """Append input_ids [B, n] to state (mutates it; callers fork for
        transactions). Persistent writes require write=True and n == 1."""
        B, n = input_ids.shape
        if write and n != 1:
            raise ValueError("token-serial ingest: writes take one token per step")
        if enabled and (oracle is not None) != (self.cfg.address_mode == "oracle"):
            raise ValueError("oracle addresses iff address_mode == 'oracle'")
        inner, cache = self.backbone.model, state.recent_kv
        start, phys = cache.next_logical_position, cache.physical_length
        pos = torch.arange(start, start + n, device=self.device).unsqueeze(0).expand(B, n)
        cache_pos = torch.arange(phys, phys + n, device=self.device)
        h = inner.embed_tokens(input_ids)
        rope = inner.rotary_emb(h, pos)
        mask = None
        if n > 1:  # causal among new tokens; every resident slot visible
            mask = torch.zeros(1, 1, n, phys + n, dtype=h.dtype, device=self.device)
            mask[..., phys:] = torch.triu(torch.full((n, n), float("-inf"),
                                                     device=self.device), 1)
        kw = dict(attention_mask=mask, position_ids=pos, past_key_value=cache,
                  use_cache=True, cache_position=cache_pos, position_embeddings=rope)
        reads, trace = {}, {"empty_read_weight": [], "allocated": 0, "read_coords": {}}
        for i, layer in enumerate(inner.layers):
            if enabled and str(i) in self.adapters:
                h = self._sgm_layer(layer, i, h, state, kw, write, oracle, reads, trace)
            else:
                h = layer(h, **kw)
        cache.note_appended(n)
        self._evict(cache)
        out = {"reads": reads, "trace": trace}
        if logits:
            out["logits"] = self.backbone.lm_head(inner.norm(h[:, -1])).float()
        return out

    def _sgm_layer(self, layer, i, h, state, kw, write, oracle, reads, trace):
        residual = h
        z = layer.input_layernorm(h)
        attn, _ = layer.self_attn(hidden_states=z, **kw)
        h = residual + attn
        adapter: SGMLayerAdapter = self.adapters[str(i)]
        x = self._shifted(state, i, z.float())
        p = adapter.project(x)
        r = torch.stack([self._read(state.banks, i, p, t, oracle, trace)
                         for t in range(x.shape[1])], dim=1)       # [B, n, H, dv]
        reads[i] = r
        h = h + adapter.output(r).to(h.dtype)
        # raw projected gate for this step, recorded whether or not it writes
        trace.setdefault("beta_projected", {})[i] = p["beta"][:, -1].detach()   # [B, H]
        if write:
            trace["allocated"] += self._write(state.banks, i, p, oracle, trace)
            trace.setdefault("beta", {})[i] = p["beta"][:, 0].detach()   # [B, H]
        residual = h
        return residual + layer.mlp(layer.post_attention_layernorm(h))

    # -- memory ops ----------------------------------------------------------------------
    def _shifted(self, state, i, z):
        if self.cfg.feature_shift == 1:
            return z
        prev = state.shift_features.get(i, torch.zeros_like(z[:, 0]))
        prevs = torch.cat([prev.unsqueeze(1), z[:, :-1]], dim=1)
        state.shift_features[i] = z[:, -1]
        return torch.cat([z, prevs], dim=-1)

    def _stencil(self, p, kind, t, oracle):
        H = self.cfg.memory_heads
        if self.cfg.address_mode == "oracle":
            coords = oracle[kind][:, t].float().unsqueeze(1).expand(-1, H, 2)
        elif self.cfg.address_mode == "single_cell":
            coords = torch.zeros(p["q"].shape[0], H, 2, device=self.device)
            return single_cell(coords) + (coords,)
        else:
            coords = p["a_" + kind][:, t]
        if kind == "read" and self.diag_read_offset:
            coords = coords + self.diag_read_offset
        return stencil_2d(coords) + (coords,)

    def _read(self, banks: SparseBankSet, i, p, t, oracle, trace):
        idx, w, coords = self._stencil(p, "read", t, oracle)
        trace["read_coords"].setdefault(i, []).append(coords.detach())
        trace.setdefault("read_q", {}).setdefault(i, []).append(p["q"][:, t].detach())  # telemetry
        cells, present = banks.gather(i, idx)
        trace["empty_read_weight"].append(float((w * ~present).sum(-1).mean()))
        return read_memory(cells, w, p["q"][:, t])

    def _write(self, banks: SparseBankSet, i, p, oracle, trace) -> int:
        idx, w, coords = self._stencil(p, "write", 0, oracle)
        trace.setdefault("write_coords", {})[i] = coords.detach()  # telemetry only
        trace.setdefault("write_k", {})[i] = p["k"][:, 0].detach()  # telemetry only
        cells, _ = banks.gather(i, idx)
        new = delta_update(cells, w, p["beta"][:, 0], p["k"][:, 0], p["v"][:, 0].float())
        return banks.scatter(i, idx, new, w)

    def _evict(self, cache: CompactedPrefixCache) -> None:
        """Keep sinks + the most recent local_recent_tokens (step boundary)."""
        end = cache.next_logical_position - self.cfg.local_recent_tokens
        if end > cache.sink_token_count:
            cache.evict_logical_range(cache.sink_token_count, end)
