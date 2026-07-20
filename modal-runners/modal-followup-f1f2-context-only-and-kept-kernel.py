"""FOLLOWUP F1+F2 GPU run (one forward pass, deployment-shaped, instance A).

Per test-split evicted item, context-only (NO question appended):
  1. GT16-protocol context rebuild -> sdpa prefill (4096 ctx)
  2. compact depth-1 (recent 1024 raw), hooking block-1 cross-attention of
     the FIRST compactor layer -> per-latent argmax SOURCE position per KV
     head  =>  F1 "kept source position" kernel
  3. append ONE newline sentinel, forward with output_hidden_states ->
     layer-30 residual at the last context token  =>  F2 context-only state

No answer pass, no decode, no self-check: this isolates memory-content
readout (F2) and records the fixed position kernel (F1). The compaction is
question-independent, so the kept set and residual are the deployment
context-only quantities.

Item selection: split == test (doc sha256 bucket >= 0.7), non-mh; then a
deterministic doc-level subsample to hit the ~$8 budget (--frac). Sharded
by n % n_slices.

Outputs per slice under /artifacts/probe/:
  followup-f1f2-slice-<i>.npz
    item_ids [N], residual30 [N,2560] fp16, keepcount [N,3068] uint16
      (# of (head,latent) argmaxes landing on each source position, layer-0
       block-1), S [N] int32 (source length), y [N] int8, domain [N]
    (pilot mode --dump-argmax also stores argmax0 [N,8,1024] int16)

Usage:
  # pilot first (structure check), 16 items:
  modal run --detach ...::run --subset test --slice-idx 0 --n-slices 1 \
      --frac 1.0 --limit 16 --dump-argmax
  # scaled subsample (~5000 items across 4 H100):
  modal run --detach ...::run --subset test --slice-idx K --n-slices 4 --frac 0.55
"""

import hashlib
import json

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
CTX = 4096
RECENT_RAW = 1024
SINKS = 4
T_LAT = 1024
S_FULL = CTX - RECENT_RAW - SINKS          # 3068 source positions (full doc)
TAG = "single-t1024-T8k"

app = modal.App("memsub-followup-f1f2")
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


def _bucket(iid: str) -> float:
    doc = iid[4:].rsplit("_", 2)[0]
    return int(hashlib.sha256(doc.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def _doc_subsample_hash(iid: str) -> float:
    # independent of the split bucket: salt the doc id
    doc = iid[4:].rsplit("_", 2)[0]
    return int(hashlib.sha256(("f1f2:" + doc).encode()).hexdigest()[:8],
               16) / 0xFFFFFFFF


@app.function(image=image, gpu="H100", volumes=VOLUMES, timeout=43200,
              memory=65536)
def run(subset: str, slice_idx: int, n_slices: int, frac: float = 0.55,
        limit: int = 0, dump_argmax: bool = False, tag: str = TAG,
        lever: str = "none") -> dict:
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch
    import torch.nn.functional as F
    from memsub.compactor import StillAmortizedKVCompactor
    from memsub.compactor import still_perceiver_layer_compactor as spc
    from memsub.compactor.rope_rotation_helpers import apply_rotation
    from memsub.compactor.still_amortized_kv_compactor import (
        compact_prefix_keep_recent)
    from memsub.reference_config import build_runtime

    # ---- kept-kernel capture: patch block-1 cross-attn forward ------------
    class KeptCtx:
        argmax = None        # [8, t] source positions, first layer only
        active = False

    _orig_forward = spc._QKNormCrossAttention.forward

    def capturing_forward(self, z_normed, kv_normed, kv_values,
                          q_cos, q_sin, k_cos, k_sin):
        q = apply_rotation(self.q_proj(z_normed) + self.q_anchor, q_cos, q_sin)
        k = apply_rotation(self.k_proj(kv_normed) + self.k_anchor, k_cos, k_sin)
        q = F.normalize(q, dim=-1)
        k = F.normalize(k, dim=-1)
        attn = torch.softmax(q @ k.transpose(-1, -2) * self.d_l, dim=-1)
        if KeptCtx.active and getattr(self, "_kept_layer0", False):
            KeptCtx.argmax = attn.argmax(-1).to(torch.int32).cpu()  # [8, t]
            KeptCtx.active = False                                   # first only
        return self.o_proj(attn @ self.v_proj(kv_values))

    spc._QKNormCrossAttention.forward = capturing_forward

    suffix = "" if tag == TAG else f"-{tag}"
    runtime = build_runtime(reference=True)
    model, tok = runtime.model, runtime.tokenizer
    comp = StillAmortizedKVCompactor.load(
        f"/artifacts/compactor-checkpoints/{tag}/compactor.safetensors",
        model.config, device=runtime.device).to(model.dtype)
    if lever == "e1_sqrt_scale":
        for _layer in comp.layers:
            for _m in list(_layer.cross) + list(_layer.selfattn):
                _m.d_l = 16                # deployment scale for E1 instances
    comp.layers[0].cross[0]._kept_layer0 = True    # canonical read-in only

    def set_attn(mode):
        model.config._attn_implementation = mode
        for lyr in model.model.layers:
            lyr.self_attn.config._attn_implementation = mode
    set_attn("sdpa")

    with open("/artifacts/probe/capture-manifest.json") as f:
        manifest = json.load(f)
    # test-split evicted-only, doc-subsampled
    items = [m for m in manifest
             if _bucket(m["item_id"]) >= 0.7
             and _doc_subsample_hash(m["item_id"]) < frac]
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
    npz_path = f"/artifacts/probe/followup-f1f2{suffix}-{name}.npz"
    state_path = f"/artifacts/probe/followup-f1f2{suffix}-{name}.state.json"
    ids_out, res_out, keep_out, S_out, y_out, dom_out, arg_out = (
        [], [], [], [], [], [], [])
    done = 0
    if os.path.exists(state_path):
        with open(state_path) as f:
            done = json.load(f)["done"]
        try:
            z = np.load(npz_path, allow_pickle=True)
            ids_out = list(z["item_ids"]); res_out = list(z["residual30"])
            keep_out = list(z["keepcount"]); S_out = list(z["S"])
            y_out = list(z["y"]); dom_out = list(z["domain"])
            if dump_argmax and "argmax0" in z:
                arg_out = list(z["argmax0"])
        except Exception as e:
            print(f"npz unreadable ({e}); restart", flush=True)
            done = 0
            ids_out, res_out, keep_out, S_out, y_out, dom_out, arg_out = (
                [], [], [], [], [], [], [])

    nl_id = tok.encode("\n", add_special_tokens=False)[-1]
    os.makedirs("/artifacts/probe", exist_ok=True)

    def save():
        obj = dict(
            item_ids=np.array(ids_out),
            residual30=np.stack(res_out).astype(np.float16) if res_out
            else np.zeros(0),
            keepcount=np.stack(keep_out).astype(np.uint16) if keep_out
            else np.zeros(0),
            S=np.array(S_out, dtype=np.int32),
            y=np.array(y_out, dtype=np.int8),
            domain=np.array(dom_out))
        if dump_argmax and arg_out:
            obj["argmax0"] = np.stack(arg_out).astype(np.int16)
        np.savez_compressed(npz_path, **obj)
        with open(state_path, "w") as f:
            json.dump({"done": done}, f)
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
        phys = cache.physical_length
        old_hi = phys - RECENT_RAW           # source = [SINKS, old_hi)
        S = max(0, old_hi - SINKS)
        with torch.inference_mode():
            KeptCtx.argmax = None
            KeptCtx.active = True
            cc = compact_prefix_keep_recent(comp, cache, RECENT_RAW, depth=1)
            KeptCtx.active = False
        am = KeptCtx.argmax                  # [8, T_LAT] source idx in [0,S)
        keepcount = np.zeros(S_FULL, dtype=np.uint16)
        if am is not None:
            flat = am.numpy().reshape(-1)
            flat = flat[(flat >= 0) & (flat < S_FULL)]
            np.add.at(keepcount, flat, 1)

        # ---- context-only readout: newline sentinel, layer-30 residual ----
        work = cc.clone_detached()
        with torch.inference_mode():
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
            res30 = out.hidden_states[30][0, -1].float().cpu().numpy()

        ids_out.append(row["item_id"])
        res_out.append(res30.astype(np.float16))
        keep_out.append(keepcount)
        S_out.append(S)
        y_out.append(int(row["y"]))
        dom_out.append(row["domain"])
        if dump_argmax and am is not None:
            arg_out.append(am.numpy().astype(np.int16))
        done = n + 1
        del cache, cc, work
        if done % 200 == 0 or done == len(items):
            save()
            print(f"{name} {done}/{len(items)}", flush=True)
    save()
    spc._QKNormCrossAttention.forward = _orig_forward
    return {"name": name, "items": len(ids_out)}


@app.local_entrypoint()
def main(subset: str = "test", slice_idx: int = 0, n_slices: int = 1,
         frac: float = 0.55, limit: int = 0, dump_argmax: bool = False,
         tag: str = TAG):
    print(run.remote(subset, slice_idx, n_slices, frac, limit, dump_argmax,
                     tag))


@app.local_entrypoint()
def sweep(tag: str, n_slices: int = 4, frac: float = 0.55,
          lever: str = "none"):
    """FULLRECIPE Q3: same scaled subsample as F1, new checkpoint."""
    handles = [run.spawn("test", k, n_slices, frac, 0, True, tag, lever)
               for k in range(n_slices)]
    print("spawned", len(handles), "f1f2 slices for", tag)
