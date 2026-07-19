"""FULLRECIPE I1 — block-1 cross-attention entropy + argmax-kernel telemetry.

Monkeypatches _QKNormCrossAttention.forward with identical math (same trick
as the F1 kept-kernel capture) so that, when TeleState.active, every
layer's BLOCK-1 cross-attention accumulates:
  - row-entropy (nats) sum + histogram per layer  -> mean/p10/p90
  - argmax source-position histogram per layer    -> kept-position sets
  - exact per-item layer-0 argmax [H, t]          -> I2 / Q3 kernels

Source position index i maps to logical position i + n_sinks (4).
Loaded by the inner training script via importlib (kebab-case filename).
"""

import json
import os

import numpy as np
import torch
import torch.nn.functional as F

ENT_BINS, ENT_MAX = 256, 9.2       # ln(8188) = 9.01
POS_BINS = 8192


class TeleState:
    active = False
    ent_sum = None      # [L] float64 cuda
    ent_hist = None     # [L, ENT_BINS] float32 cuda
    pos_hist = None     # [L, POS_BINS] float32 cuda
    row_count = 0       # rows per layer accumulated (same for all layers)
    argmax_l0 = None    # list of [H, t] int16 cpu tensors


def install(n_layers: int, device: str) -> None:
    from memsub.compactor import still_perceiver_layer_compactor as spc
    from memsub.compactor.rope_rotation_helpers import apply_rotation

    def reset():
        TeleState.ent_sum = torch.zeros(n_layers, dtype=torch.float64,
                                        device=device)
        TeleState.ent_hist = torch.zeros(n_layers, ENT_BINS, device=device)
        TeleState.pos_hist = torch.zeros(n_layers, POS_BINS, device=device)
        TeleState.row_count = 0
        TeleState.argmax_l0 = []
    TeleState.reset = staticmethod(reset)
    reset()

    def forward(self, z_normed, kv_normed, kv_values,
                q_cos, q_sin, k_cos, k_sin):
        q = apply_rotation(self.q_proj(z_normed) + self.q_anchor, q_cos, q_sin)
        k = apply_rotation(self.k_proj(kv_normed) + self.k_anchor, k_cos, k_sin)
        q = F.normalize(q, dim=-1)
        k = F.normalize(k, dim=-1)
        # ESCAPE E2 lever: per-layer learned temperature (clamped) overrides
        # the fixed d_l logit scale. Scale is folded into q BEFORE the matmul:
        # multiplying the [., t, S] logits by a grad-requiring scalar would
        # make autograd save the full logit tensor per layer (OOM at t=1024).
        scale = (self._temp_ref.clamp(1.0, 256.0)
                 if getattr(self, "_temp_ref", None) is not None else self.d_l)
        attn = torch.softmax((q * scale) @ k.transpose(-1, -2), dim=-1)
        li = getattr(self, "_tele_layer", None)
        if TeleState.active and li is not None:
            with torch.no_grad():
                p = attn.float()
                ent = -(p * (p + 1e-12).log()).sum(-1)          # [H, t]
                TeleState.ent_sum[li] += ent.sum().double()
                TeleState.ent_hist[li] += torch.histc(
                    ent, ENT_BINS, 0.0, ENT_MAX)
                am = p.argmax(-1)                               # [H, t]
                TeleState.pos_hist[li] += torch.bincount(
                    am.reshape(-1), minlength=POS_BINS).float()
                if li == 0:
                    TeleState.row_count += ent.numel()
                    TeleState.argmax_l0.append(am.to(torch.int16).cpu())
        return self.o_proj(attn @ self.v_proj(kv_values))

    spc._QKNormCrossAttention.forward = forward


def mark_layers(compactor_module) -> None:
    """Tag each layer's block-1 cross-attn so the patched forward can
    attribute stats (self-attn / block-2 modules stay untagged)."""
    for i, layer in enumerate(compactor_module.layers):
        layer.cross[0]._tele_layer = i


def probe_pass(step, model, compactor_module, probe_ctx, device, out_dir,
               rank, dist, save_item_argmax=False) -> dict | None:
    """Run compactor over this rank's probe items with capture on, reduce
    across ranks, and (rank 0) append the telemetry record + kernel hist."""
    from memsub.runtime import CompactedPrefixCache
    TeleState.reset()
    TeleState.active = True
    was_training = compactor_module.training
    compactor_module.eval()
    with torch.no_grad():
        for ctx_ids in probe_ctx:
            out = model(input_ids=torch.tensor([ctx_ids], device=device),
                        use_cache=True)
            full = CompactedPrefixCache.from_prefill(out.past_key_values,
                                                     len(ctx_ids))
            compactor_module.compact(full)
    TeleState.active = False
    if was_training:
        compactor_module.train()

    dist.all_reduce(TeleState.ent_sum)
    dist.all_reduce(TeleState.ent_hist)
    dist.all_reduce(TeleState.pos_hist)
    cnt = torch.tensor([TeleState.row_count], device=device)
    dist.all_reduce(cnt)
    if rank != 0:
        return None

    rows_total = int(cnt.item())
    hist = TeleState.ent_hist.cpu().numpy()
    edges = np.linspace(0.0, ENT_MAX, ENT_BINS + 1)
    mids = (edges[:-1] + edges[1:]) / 2
    layers = []
    for li in range(hist.shape[0]):
        cum = np.cumsum(hist[li])
        tot = max(cum[-1], 1)

        def pct(q):
            return float(mids[np.searchsorted(cum, q * tot)])
        layers.append({
            "mean": float(TeleState.ent_sum[li].item() / max(rows_total, 1)),
            "p10": pct(0.10), "p90": pct(0.90)})
    kept = (TeleState.pos_hist > 0).sum(-1).cpu().numpy()
    rec = {"step": step, "rows_per_layer": rows_total,
           "entropy_mean_over_layers":
               float(np.mean([l["mean"] for l in layers])),
           "kept_positions_per_layer": kept.astype(int).tolist(),
           "layers": layers}
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/entropy-telemetry.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    np.savez_compressed(
        f"{out_dir}/kernel-hist-step{step:05d}.npz",
        pos_hist=TeleState.pos_hist.cpu().numpy().astype(np.uint32))
    if save_item_argmax and TeleState.argmax_l0:
        np.save(f"{out_dir}/argmax-l0-step{step:05d}.npy",
                torch.stack(TeleState.argmax_l0).numpy())
    return rec
