"""FULLRECIPE I2 — online kernel-geometry probe, one point per checkpoint.

For a given (tag, step) checkpoint: relabel the FIXED 1k subsample (first
1,000 of the E1 2k sample, sorted (domain, doc_id, item_id) — exact GT16
protocol: deployment shape old-prefix -> t latents + recent 1024 raw,
depth 1, eq_policy_v1) while capturing the F1 kept-kernel (first compactor
layer, block-1 cross-attn argmax) per item. Output feeds the d_min-AUC-vs-
step curve (Q1/Q3 support).

Writes /artifacts/fullrecipe-telemetry/i2-{tag}-step{step}.state.json
       /artifacts/fullrecipe-telemetry/i2-{tag}-step{step}-argmax.npz

Usage:
  modal run --detach modal-runners/modal-fullrecipe-i2-kernel-geometry-per-checkpoint-probe.py \
      --tag fullrecipe-full-t1024-T8k --step 250
  (step 0 -> compactor.safetensors i.e. final/latest)
"""

import json

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
CTX = 4096
RECENT_RAW = 1024
N_SUBSAMPLE = 1000

app = modal.App("memsub-fullrecipe-i2-probe")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "MEMSUB_REFERENCE": "1"})
    .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
    .add_local_dir("memsub", "/root/repo/memsub")
)
hf_cache = modal.Volume.from_name("memsub-hf-cache", create_if_missing=True)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/root/.cache/huggingface": hf_cache, "/artifacts": artifacts}
DOMAINS = ("financial", "legal", "code", "literature")


@app.function(image=image, gpu="H100", volumes=VOLUMES, timeout=14400,
              memory=32768)
def probe_checkpoint(tag: str, step: int = 0) -> dict:
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch
    import torch.nn.functional as F
    from memsub.certification import McqItem, eq_policy_v1
    from memsub.compactor import StillAmortizedKVCompactor
    from memsub.compactor import still_perceiver_layer_compactor as spc
    from memsub.compactor.rope_rotation_helpers import apply_rotation
    from memsub.compactor.still_amortized_kv_compactor import (
        compact_prefix_keep_recent)
    from memsub.reference_config import build_runtime

    ck = (f"/artifacts/compactor-checkpoints/{tag}/compactor.safetensors"
          if step == 0 else
          f"/artifacts/compactor-checkpoints/{tag}/"
          f"compactor-step-{step:05d}.safetensors")
    label = f"{tag}-step{step:05d}" if step else f"{tag}-final"
    os.makedirs("/artifacts/fullrecipe-telemetry", exist_ok=True)
    state_path = f"/artifacts/fullrecipe-telemetry/i2-{label}.state.json"
    state = {"done": 0, "rows": []}
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)

    # ---- F1-style kept-kernel capture (first layer, block-1) --------------
    class KeptCtx:
        argmax = None
        active = False

    def capturing_forward(self, z_normed, kv_normed, kv_values,
                          q_cos, q_sin, k_cos, k_sin):
        q = apply_rotation(self.q_proj(z_normed) + self.q_anchor, q_cos, q_sin)
        k = apply_rotation(self.k_proj(kv_normed) + self.k_anchor, k_cos, k_sin)
        q = F.normalize(q, dim=-1)
        k = F.normalize(k, dim=-1)
        attn = torch.softmax(q @ k.transpose(-1, -2) * self.d_l, dim=-1)
        if KeptCtx.active and getattr(self, "_kept_layer0", False):
            KeptCtx.argmax = attn.argmax(-1).to(torch.int16).cpu()   # [8, t]
            KeptCtx.active = False
        return self.o_proj(attn @ self.v_proj(kv_values))

    spc._QKNormCrossAttention.forward = capturing_forward

    with open("/artifacts/preprobe/e1-sample-items.json") as f:
        sample = json.load(f)
    sample.sort(key=lambda r: (r["domain"], r["doc_id"], r["item_id"]))
    sample = sample[:N_SUBSAMPLE]

    needed = {r["doc_id"] for r in sample}
    texts = {}
    for domain in DOMAINS:
        with open(f"/artifacts/corpus/{domain}.jsonl") as f:
            for line in f:
                rec = json.loads(line)
                if rec["doc_id"] in needed:
                    texts[rec["doc_id"]] = rec["text"]

    runtime = build_runtime(reference=True)
    comp = StillAmortizedKVCompactor.load(
        ck, runtime.model.config, device=runtime.device).to(runtime.model.dtype)
    comp.layers[0].cross[0]._kept_layer0 = True
    tok = runtime.tokenizer
    doc_cache: dict[str, list[int]] = {}
    argmaxes, arg_ids = [], []
    arg_path = f"/artifacts/fullrecipe-telemetry/i2-{label}-argmax.npz"
    if os.path.exists(arg_path):
        z = np.load(arg_path, allow_pickle=True)
        argmaxes = [a for a in z["argmax"]]
        arg_ids = [str(i) for i in z["item_ids"]]

    for n, row in enumerate(sample):
        if n < state["done"]:
            continue
        if row["doc_id"] not in doc_cache:
            doc_cache.clear()
            doc_cache[row["doc_id"]] = tok.encode(texts[row["doc_id"]],
                                                  add_special_tokens=False)
        ids = doc_cache[row["doc_id"]]
        chunk_start = int(row["item_id"].split("_")[-2])
        ctx_start = max(0, min(chunk_start - row["chunk_rel_start"],
                               len(ids) - CTX))
        ctx_ids = ids[ctx_start:ctx_start + CTX]
        chunk_rel = chunk_start - ctx_start
        item = McqItem(row["item_id"], row["doc_id"], chunk_start,
                       chunk_start + 1024, row["question"], row["options"],
                       row["gold"])
        cache, _ = runtime.prefill(ctx_ids)
        KeptCtx.argmax, KeptCtx.active = None, True
        with torch.inference_mode():
            cc = compact_prefix_keep_recent(comp, cache, RECENT_RAW, depth=1)
        pred_c = runtime.answer_letter("", item.question, item.options,
                                       cache=cc)
        lo, hi = 4, len(ctx_ids) - RECENT_RAW
        ov = max(0, min(hi, chunk_rel + 1024) - max(lo, chunk_rel)) / 1024
        state["rows"].append({
            "item_id": row["item_id"], "doc_id": row["doc_id"],
            "domain": row["domain"], "step": step,
            "pred_compact": pred_c,
            "y": int(not eq_policy_v1(pred_c, row["pred_raw"])),
            "chunk_rel": chunk_rel,
            "overlap": round(ov, 4), "evicted": int(ov > 0.5)})
        if KeptCtx.argmax is not None:
            argmaxes.append(KeptCtx.argmax.numpy())
            arg_ids.append(row["item_id"])
        state["done"] = n + 1
        if (n + 1) % 100 == 0 or n + 1 == len(sample):
            with open(state_path, "w") as f:
                json.dump(state, f)
            np.savez_compressed(arg_path,
                                argmax=np.stack(argmaxes).astype(np.int16),
                                item_ids=np.array(arg_ids),
                                S=np.int32(CTX - RECENT_RAW - 4))
            artifacts.commit()
            print(f"i2[{label}] {n + 1}/{len(sample)}", flush=True)
    y_rate = (sum(r["y"] for r in state["rows"])
              / max(len(state["rows"]), 1))
    return {"label": label, "rows": len(state["rows"]), "y_rate": y_rate}


@app.local_entrypoint()
def main(tag: str, step: int = 0):
    print(probe_checkpoint.remote(tag, step))


@app.local_entrypoint()
def sweep(tag: str, steps: str):
    """steps: comma-separated, e.g. '250,500,750,1000,1250,1500'."""
    handles = [probe_checkpoint.spawn(tag, int(s))
               for s in steps.split(",")]
    print("spawned", len(handles), "i2 points")
