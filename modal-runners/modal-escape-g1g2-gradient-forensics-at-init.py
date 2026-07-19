"""ESCAPE P0 — G1/G2 gradient forensics at init (near-dispositive for the
saturation hypothesis, before any training spend).

G1: fresh canonical compactor (seed 1234, t=1024, logit scale d_l=256),
one accumulated forward+backward of the corrected KL over the fixed
128-item probe batch (first 128 rows of triplets-full) → log grad-norm per
parameter group per layer: latents, W_Q(+anchor), W_K(+anchor), W_V, W_O
(block-1 cross), block-2 cross, self-attn, output heads (w_key, w_val).

G2: identical measurement with every attention module's logit scale set to
√d_l = 16 (scale-only attribute swap; weights untouched).

Prediction under the hypothesis: G1 routing groups ≈ 0; G2 wakes them by
orders of magnitude. Writes /artifacts/escape/g1g2-gradient-table.json.

Usage:
  modal run modal-runners/modal-escape-g1g2-gradient-forensics-at-init.py
"""

import json

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
app = modal.App("memsub-escape-g1g2")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
    .add_local_dir("memsub", "/root/repo/memsub")
)
hf_cache = modal.Volume.from_name("memsub-hf-cache", create_if_missing=True)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/root/.cache/huggingface": hf_cache, "/artifacts": artifacts}
N_PROBE = 128


@app.function(image=image, gpu="H100", volumes=VOLUMES, timeout=14400,
              memory=65536)
def forensics() -> dict:
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch
    from memsub.compactor import StillAmortizedKVCompactor
    from memsub.compactor.compactor_training_objective import forward_kl_on_answer
    from memsub.runtime import CompactedPrefixCache
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = "cuda"
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B-Instruct-2507")
    model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen3-4B-Instruct-2507", torch_dtype=torch.bfloat16,
        attn_implementation="sdpa").to(device).eval()
    model.requires_grad_(False)
    torch.manual_seed(1234)
    comp = StillAmortizedKVCompactor(model.config, 1024).to(device,
                                                            torch.float32)

    with open("/artifacts/corpus-fullrecipe/triplets-full.json") as f:
        rows = json.load(f)[:N_PROBE]
    ctx_arr = np.load("/artifacts/corpus-fullrecipe/ctx-tokens-full.npy",
                      mmap_mode="r")

    def student_logits(cache, token_ids):
        n = len(token_ids)
        start = cache.next_logical_position
        phys = cache.physical_length
        out = model(input_ids=torch.tensor([token_ids], device=device),
                    attention_mask=torch.ones((1, phys + n), dtype=torch.long,
                                              device=device),
                    position_ids=torch.arange(start, start + n,
                                              device=device).unsqueeze(0),
                    past_key_values=cache,
                    cache_position=torch.arange(phys, phys + n, device=device),
                    use_cache=True)
        return out.logits[0]

    def accumulate_backward():
        comp.zero_grad(set_to_none=False)
        total = 0.0
        for k, row in enumerate(rows):
            ctx = ctx_arr[k].tolist()
            seq = row["prompt_ids"] + row["answer_ids"]
            with torch.no_grad():
                out = model(input_ids=torch.tensor([ctx], device=device),
                            use_cache=True)
                full = CompactedPrefixCache.from_prefill(out.past_key_values,
                                                         len(ctx))
                t_logits = student_logits(full.clone_detached(), seq)
            s_cache = comp.compact(full)
            s_logits = student_logits(s_cache, seq)
            n_prompt = len(row["prompt_ids"])
            mask = torch.zeros(len(seq), dtype=torch.bool, device=device)
            mask[n_prompt - 1:len(seq) - 1] = True
            gold = torch.tensor(seq[1:] + [tok.eos_token_id], device=device)
            loss = forward_kl_on_answer(t_logits, s_logits, mask,
                                        gold) / N_PROBE
            loss.backward()
            total += float(loss) * N_PROBE
        return total / N_PROBE

    def grad_table():
        groups = {
            "latents": lambda l: [l.latents],
            "cross1_WQ": lambda l: [l.cross[0].q_proj.weight, l.cross[0].q_anchor],
            "cross1_WK": lambda l: [l.cross[0].k_proj.weight, l.cross[0].k_anchor],
            "cross1_WV": lambda l: [l.cross[0].v_proj.weight],
            "cross1_WO": lambda l: [l.cross[0].o_proj.weight],
            "cross2_all": lambda l: list(l.cross[1].parameters()),
            "selfattn_all": lambda l: [p for m in l.selfattn
                                       for p in m.parameters()],
            "out_heads": lambda l: [l.w_key.weight, l.w_val.weight],
        }
        per_layer, agg = [], {g: 0.0 for g in groups}
        for l in comp.layers:
            row = {}
            for g, fn in groups.items():
                sq = sum(float(p.grad.norm()) ** 2 for p in fn(l)
                         if p.grad is not None)
                row[g] = sq ** 0.5
                agg[g] += sq
            per_layer.append(row)
        return {g: v ** 0.5 for g, v in agg.items()}, per_layer

    out = {}
    for label, scale in (("G1_canonical_dl256", None), ("G2_sqrt_dl16", 16)):
        if scale is not None:
            for l in comp.layers:
                for m in list(l.cross) + list(l.selfattn):
                    m.d_l = scale
        loss = accumulate_backward()
        agg, per_layer = grad_table()
        out[label] = {"loss": round(loss, 5),
                      "grad_norm_total_per_group":
                          {g: float(f"{v:.6e}") for g, v in agg.items()},
                      "per_layer": [{g: float(f"{v:.4e}") for g, v in r.items()}
                                    for r in per_layer]}
        print(label, "loss", round(loss, 4),
              {g: f"{v:.3e}" for g, v in agg.items()}, flush=True)
    ratios = {g: (out["G2_sqrt_dl16"]["grad_norm_total_per_group"][g]
                  / max(out["G1_canonical_dl256"]["grad_norm_total_per_group"][g],
                        1e-30))
              for g in out["G1_canonical_dl256"]["grad_norm_total_per_group"]}
    out["G2_over_G1_ratio"] = {g: float(f"{v:.4e}") for g, v in ratios.items()}
    os.makedirs("/artifacts/escape", exist_ok=True)
    with open("/artifacts/escape/g1g2-gradient-table.json", "w") as f:
        json.dump(out, f, indent=1)
    artifacts.commit()
    return {"G1": out["G1_canonical_dl256"]["grad_norm_total_per_group"],
            "G2": out["G2_sqrt_dl16"]["grad_norm_total_per_group"],
            "ratio": out["G2_over_G1_ratio"]}


@app.local_entrypoint()
def main():
    print(json.dumps(forensics.remote(), indent=1))
