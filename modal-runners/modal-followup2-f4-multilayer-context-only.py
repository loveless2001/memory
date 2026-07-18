"""FOLLOWUP2 F4 — multi-layer context-only re-forward (harder F2 null test).

Same 5,090-item test subsample and context-only readout as the F1/F2 run
(compact context, NO question, newline sentinel at the last context token),
but captures the residual at layers {10,15,20,25,30,36} instead of layer 30
only. Feeds F4's per-layer linear sweep + MLP + concat-of-layers probes.

Outputs per slice under /artifacts/probe/:
  followup2-f4-slice-<i>.npz
    item_ids [N], residual [N,6,2560] fp16 (layer order 10,15,20,25,30,36),
    y [N] int8, domain [N]

Usage:
  modal run --detach ...::run --slice-idx K --n-slices 4 --frac 0.55
"""

import hashlib
import json

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
CTX, RECENT_RAW, SINKS = 4096, 1024, 4
TAG = "single-t1024-T8k"
LAYERS = [10, 15, 20, 25, 30, 36]

app = modal.App("memsub-followup2-f4")
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


def _bucket(iid):
    doc = iid[4:].rsplit("_", 2)[0]
    return int(hashlib.sha256(doc.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def _sub(iid):
    doc = iid[4:].rsplit("_", 2)[0]
    return int(hashlib.sha256(("f1f2:" + doc).encode()).hexdigest()[:8],
               16) / 0xFFFFFFFF   # identical selection to the F1/F2 run


@app.function(image=image, gpu="H100", volumes=VOLUMES, timeout=43200,
              memory=65536)
def run(slice_idx: int, n_slices: int, frac: float = 0.55,
        limit: int = 0) -> dict:
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch
    from memsub.compactor import StillAmortizedKVCompactor
    from memsub.compactor.still_amortized_kv_compactor import (
        compact_prefix_keep_recent)
    from memsub.reference_config import build_runtime

    runtime = build_runtime(reference=True)
    model, tok = runtime.model, runtime.tokenizer
    comp = StillAmortizedKVCompactor.load(
        f"/artifacts/compactor-checkpoints/{TAG}/compactor.safetensors",
        model.config, device=runtime.device).to(model.dtype)
    for lyr in model.model.layers:
        lyr.self_attn.config._attn_implementation = "sdpa"
    model.config._attn_implementation = "sdpa"

    with open("/artifacts/probe/capture-manifest.json") as f:
        manifest = json.load(f)
    items = [m for m in manifest
             if _bucket(m["item_id"]) >= 0.7 and _sub(m["item_id"]) < frac]
    items = sorted(items, key=lambda r: (r["domain"], r["doc_id"],
                                         r["item_id"]))
    items = [m for n, m in enumerate(items) if n % n_slices == slice_idx]
    if limit:
        items = items[:limit]
    needed = {m["doc_id"] for m in items}
    texts = {}
    for domain in DOMAINS:
        with open(f"/artifacts/corpus/{domain}.jsonl") as f:
            for line in f:
                rec = json.loads(line)
                if rec["doc_id"] in needed:
                    texts[rec["doc_id"]] = rec["text"]

    name = f"slice-{slice_idx:02d}"
    npz_path = f"/artifacts/probe/followup2-f4-{name}.npz"
    state_path = f"/artifacts/probe/followup2-f4-{name}.state.json"
    ids_out, res_out, y_out, dom_out, done = [], [], [], [], 0
    if os.path.exists(state_path):
        done = json.load(open(state_path))["done"]
        try:
            z = np.load(npz_path, allow_pickle=True)
            ids_out = list(z["item_ids"]); res_out = list(z["residual"])
            y_out = list(z["y"]); dom_out = list(z["domain"])
        except Exception:
            done = 0; ids_out, res_out, y_out, dom_out = [], [], [], []

    nl_id = tok.encode("\n", add_special_tokens=False)[-1]

    def save():
        np.savez_compressed(
            npz_path, item_ids=np.array(ids_out),
            residual=np.stack(res_out).astype(np.float16) if res_out
            else np.zeros(0),
            y=np.array(y_out, dtype=np.int8), domain=np.array(dom_out))
        json.dump({"done": done}, open(state_path, "w"))
        artifacts.commit()

    doc_cache = {}
    for n, row in enumerate(items):
        if n < done:
            continue
        if row["doc_id"] not in doc_cache:
            doc_cache.clear()
            doc_cache[row["doc_id"]] = tok.encode(
                texts[row["doc_id"]], add_special_tokens=False)
        toks = doc_cache[row["doc_id"]]
        chunk_start = int(row["item_id"].split("_")[-2])
        ctx_start = max(0, min(chunk_start - row["chunk_rel_start"],
                               len(toks) - CTX))
        ctx_ids = toks[ctx_start:ctx_start + CTX]
        cache, _ = runtime.prefill(ctx_ids)
        with torch.inference_mode():
            cc = compact_prefix_keep_recent(comp, cache, RECENT_RAW, depth=1)
            work = cc.clone_detached()
            wphys = work.physical_length
            start = work.next_logical_position
            out = model(
                input_ids=torch.tensor([[nl_id]], device=runtime.device),
                attention_mask=torch.ones((1, wphys + 1), dtype=torch.long,
                                          device=runtime.device),
                position_ids=torch.tensor([[start]], device=runtime.device),
                past_key_values=work,
                cache_position=torch.tensor([wphys], device=runtime.device),
                use_cache=True, output_hidden_states=True)
            res = np.stack([out.hidden_states[li][0, -1].float().cpu().numpy()
                            for li in LAYERS]).astype(np.float16)  # [6,2560]
        ids_out.append(row["item_id"]); res_out.append(res)
        y_out.append(int(row["y"])); dom_out.append(row["domain"])
        done = n + 1
        del cache, cc, work
        if done % 200 == 0 or done == len(items):
            save()
            print(f"{name} {done}/{len(items)}", flush=True)
    save()
    return {"name": name, "items": len(ids_out)}


@app.local_entrypoint()
def main(slice_idx: int = 0, n_slices: int = 1, frac: float = 0.55,
         limit: int = 0):
    print(run.remote(slice_idx, n_slices, frac, limit))
