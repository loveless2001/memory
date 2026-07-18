"""FOLLOWUP2 F5 — sink-head monitor under the EVICTION regime (ladder
generality).

Mirrors F3's 4-head monitor but under contiguous eviction rather than the
trained compactor. Per M3-labeled item at fraction f (evicted-span rows):
  1. GT16/M3 context rebuild -> prefill 4096 ctx (same stable-rng offset as
     the M3 labeling run, so the eviction exposure matches the y label)
  2. clone + evict-oldest-nonsink [4, 4+f*ctx) -> surviving KV
  3. append the answer prompt (question-conditioned, like F3) -> eager
     forward with output_attentions; capture the 4 inventory heads'
     mass on {surviving-memory span, sinks} at the last prompt token

Region semantics (eviction analog of F3's latent/sink split):
  sinks  = physical [0, 4)
  memory = physical [4, ctx_len - evict_n)   (the surviving compacted span)
  (prompt tokens excluded, exactly as F3 excluded them)

Heads: L25/H14, L26/H26, L28/H19, L35/H15  ->  {m_mem, m_sink} = 8 scalars.

Item selection: evicted rows (evicted_{f}=1) at fraction FRAC, stratified by
domain x y, deterministic hash subsample to ~N_TARGET.

Outputs under /artifacts/probe/:
  followup2-f5-eviction-slice-<i>.npz
    item_ids, feats [N,8] fp32 (head-major: 4 heads x {m_mem,m_sink}),
    y [N] int8, domain [N], raw_correct [N] int8

Usage:
  modal run --detach ...::run --slice-idx K --n-slices 4 --frac 0.40
"""

import hashlib
import json

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
CTX_TOKENS, CHUNK_TOKENS, SINKS = 4096, 1024, 4
HEADS = [(25, 14), (26, 26), (28, 19), (35, 15)]
N_TARGET = 5000

app = modal.App("memsub-followup2-f5")
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


def _stable_rng(item_id):
    import random
    seed = int.from_bytes(hashlib.sha256(item_id.encode()).digest()[:4], "big")
    return random.Random(seed)


def _sub_hash(item_id):
    return int(hashlib.sha256(("f5:" + item_id).encode()).hexdigest()[:8],
               16) / 0xFFFFFFFF


@app.function(image=image, gpu="H100", volumes=VOLUMES, timeout=43200,
              memory=65536)
def run(slice_idx: int, n_slices: int, frac: float = 0.40,
        limit: int = 0) -> dict:
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch
    from memsub.reference_config import build_runtime

    key = f"{frac:.2f}"
    runtime = build_runtime(reference=True)
    model, tok = runtime.model, runtime.tokenizer
    n_layers = int(model.config.num_hidden_layers)

    with open("/artifacts/corpus-gate-labels/all-labels.json") as f:
        labels = json.load(f)
    # evicted-span rows at this fraction, stratified subsample by domain x y
    rows = [r for r in labels if r.get(f"evicted_{key}") == 1]
    # deterministic ~N_TARGET subsample (doc-independent item hash)
    thr = min(1.0, N_TARGET / max(len(rows), 1))
    rows = [r for r in rows if _sub_hash(r["item_id"]) < thr]
    rows = sorted(rows, key=lambda r: (r["domain"], r["doc_id"], r["item_id"]))
    rows = [r for n, r in enumerate(rows) if n % n_slices == slice_idx]
    if limit:
        rows = rows[:limit]

    DOMAINS = ("financial", "legal", "code", "literature")
    needed = {r["doc_id"] for r in rows}
    texts = {}
    for domain in DOMAINS:
        with open(f"/artifacts/corpus/{domain}.jsonl") as f:
            for line in f:
                rec = json.loads(line)
                if rec["doc_id"] in needed:
                    texts[rec["doc_id"]] = rec["text"]

    letters = ["A", "B", "C", "D"]

    def set_attn(mode):
        model.config._attn_implementation = mode
        for lyr in model.model.layers:
            lyr.self_attn.config._attn_implementation = mode

    name = f"slice-{slice_idx:02d}"
    npz_path = f"/artifacts/probe/followup2-f5-eviction-{name}.npz"
    state_path = f"/artifacts/probe/followup2-f5-eviction-{name}.state.json"
    ids_out, feat_out, y_out, dom_out, rc_out, done = [], [], [], [], [], 0
    if os.path.exists(state_path):
        done = json.load(open(state_path))["done"]
        try:
            z = np.load(npz_path, allow_pickle=True)
            ids_out = list(z["item_ids"]); feat_out = list(z["feats"])
            y_out = list(z["y"]); dom_out = list(z["domain"])
            rc_out = list(z["raw_correct"])
        except Exception:
            done = 0
            ids_out, feat_out, y_out, dom_out, rc_out = [], [], [], [], []

    def save():
        np.savez_compressed(
            npz_path, item_ids=np.array(ids_out),
            feats=np.stack(feat_out).astype(np.float32) if feat_out
            else np.zeros(0),
            y=np.array(y_out, dtype=np.int8), domain=np.array(dom_out),
            raw_correct=np.array(rc_out, dtype=np.int8))
        json.dump({"done": done}, open(state_path, "w"))
        artifacts.commit()

    doc_cache = {}
    for n, r in enumerate(rows):
        if n < done:
            continue
        if r["doc_id"] not in doc_cache:
            doc_cache.clear()
            doc_cache[r["doc_id"]] = tok.encode(texts[r["doc_id"]],
                                                add_special_tokens=False)
        ids = doc_cache[r["doc_id"]]
        rng = _stable_rng(r["item_id"])
        offset = rng.randrange(0, CTX_TOKENS - CHUNK_TOKENS + 1)
        chunk_start = int(r["item_id"].split("_")[-2])
        ctx_start = max(0, min(chunk_start - offset, len(ids) - CTX_TOKENS))
        ctx_ids = ids[ctx_start:ctx_start + CTX_TOKENS]

        set_attn("sdpa")
        cache, _ = runtime.prefill(ctx_ids)
        evict_n = int(len(ctx_ids) * frac)
        cc = cache.clone_detached()
        cc.evict_logical_range(4, 4 + evict_n)
        mem_hi = len(ctx_ids) - evict_n          # physical end of surviving KV

        opts = "\n".join(f"{l}. {o}" for l, o in zip(letters, r["options"]))
        prompt = (f"\n\nQuestion: {r['question']}\n{opts}\n"
                  "Answer with a single letter.\nAnswer:")
        p_ids = tok.encode(prompt, add_special_tokens=False)
        set_attn("eager")
        work = cc.clone_detached()
        with torch.inference_mode():
            n_p = len(p_ids)
            phys = work.physical_length
            start = work.next_logical_position
            out = model(
                input_ids=torch.tensor([p_ids], device=runtime.device),
                attention_mask=torch.ones((1, phys + n_p), dtype=torch.long,
                                          device=runtime.device),
                position_ids=torch.arange(start, start + n_p,
                                          device=runtime.device).unsqueeze(0),
                past_key_values=work,
                cache_position=torch.arange(phys, phys + n_p,
                                            device=runtime.device),
                use_cache=True, output_attentions=True)
            fv = []
            for (li, hh) in HEADS:
                a = out.attentions[li][0, hh, n_p - 1].float()   # [phys+n_p]
                m_sink = float(a[:SINKS].sum())
                m_mem = float(a[SINKS:mem_hi].sum())
                fv.extend([m_mem, m_sink])
        set_attn("sdpa")

        ids_out.append(r["item_id"]); feat_out.append(fv)
        y_out.append(int(r[f"y_{key}"])); dom_out.append(r["domain"])
        rc_out.append(int(r["raw_correct"]))
        done = n + 1
        del cache, cc, work
        if done % 200 == 0 or done == len(rows):
            save()
            print(f"{name} {done}/{len(rows)}", flush=True)
    save()
    return {"name": name, "items": len(ids_out), "frac": frac}


@app.local_entrypoint()
def main(slice_idx: int = 0, n_slices: int = 1, frac: float = 0.40,
         limit: int = 0):
    print(run.remote(slice_idx, n_slices, frac, limit))
