"""PROBE unified capture (PROBE.md P0 + c1/c2/c3a shared capture).

Per manifest item, deployment-shaped under instance A (single-t1024-T8k):
  1. GT16-protocol context rebuild -> sdpa prefill
  2. compact (depth 1, recent 1024 raw) with block-1 cross-attention
     capture inside the compactor -> c3a collision features (reduced
     in-place, never materialized across layers)
  3. answer trial pass (eager) with output_attentions+hidden_states ->
     p1/c1 per-head attention stats at last prompt token; c2 residual
     vector per layer
  4. three greedy decode steps with attentions -> stats per step
  5. p2 self-check forward (sdpa): "does the context contain the
     information needed?" Yes/No letter-argmax -> insufficiency score

Physical layout after compaction: [4 sinks][1024 latents][1024 recent];
answer prompt appends after. Attention regions indexed accordingly.

Outputs per slice under /artifacts/probe/:
  capture-<name>-slice-<i>.state.json   small per-item fields + resume
  capture-<name>-slice-<i>.npz          attn_stats [N,4,36,32,6] fp16,
                                        hidden [N,37,2560] fp16,
                                        c3a [N,36,8,4] fp16, item_ids

Usage (pilot first per GT19, then full):
  modal run --detach ...::run_capture --subset pilot --slice-idx 0 --n-slices 1
  modal run --detach ...::run_capture --subset rest --slice-idx K --n-slices 8
"""

import json

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
CTX = 4096
RECENT_RAW = 1024
SINKS = 4
T_LAT = 1024
TAG = "single-t1024-T8k"

app = modal.App("memsub-probe-capture")
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


@app.function(image=image, gpu="H100", volumes=VOLUMES, timeout=43200,
              memory=65536)
def run_capture(subset: str, slice_idx: int, n_slices: int,
                light: bool = False, tag: str = TAG,
                manifest_path: str = "", out_prefix: str = "capture",
                lever: str = "none") -> dict:
    """light=True (post-GT19 trim): skip decode-step attentions (c1
    demoted) and the c3a compactor hook (cross-attn shown content-blind
    on the pilot — delta position kernel, zero variance). attn_stats
    then has a single step [1, 36, 32, 6]."""
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

    # ---- compactor cross-attention capture: patch block-1 forward --------
    class C3aContext:
        needle_idx: torch.Tensor | None = None   # source indices (S-space)
        results: list = []                       # per-layer [8, 4] tensors
        active = False

    _orig_forward = spc._QKNormCrossAttention.forward

    def capturing_forward(self, z_normed, kv_normed, kv_values,
                          q_cos, q_sin, k_cos, k_sin):
        q = apply_rotation(self.q_proj(z_normed) + self.q_anchor, q_cos, q_sin)
        k = apply_rotation(self.k_proj(kv_normed) + self.k_anchor, k_cos, k_sin)
        q = F.normalize(q, dim=-1)
        k = F.normalize(k, dim=-1)
        attn = torch.softmax(q @ k.transpose(-1, -2) * self.d_l, dim=-1)
        if C3aContext.active and getattr(self, "_c3a_block1", False) \
                and C3aContext.needle_idx is not None:
            a = attn                                   # [8, t, S]
            nid = C3aContext.needle_idx
            needle_mass_per_latent = a[:, :, nid].sum(-1)      # [8, t]
            total_mass_per_latent = a.sum(-1)                  # [8, t] (=1)
            w_src = a.sum(1)                                   # [8, S]
            share = w_src[:, nid].sum(-1) / w_src.sum(-1)      # [8]
            share_ratio = share / (len(nid) / a.shape[-1])
            lstar = needle_mass_per_latent.argmax(-1)          # [8]
            arange = torch.arange(a.shape[0], device=a.device)
            row = a[arange, lstar]                             # [8, S]
            purity = row[:, nid].sum(-1) / row.sum(-1)
            p = row / row.sum(-1, keepdim=True)
            ent = -(p * (p + 1e-12).log()).sum(-1) / np.log(a.shape[-1])
            top_needle = needle_mass_per_latent.max(-1).values \
                / total_mass_per_latent.gather(1, lstar[:, None])[:, 0]
            C3aContext.results.append(
                torch.stack([share_ratio, purity, ent, top_needle], -1)
                .to(torch.float16).cpu())                      # [8, 4]
        return self.o_proj(attn @ self.v_proj(kv_values))

    spc._QKNormCrossAttention.forward = capturing_forward

    runtime = build_runtime(reference=True)
    model, tok = runtime.model, runtime.tokenizer
    comp = StillAmortizedKVCompactor.load(
        f"/artifacts/compactor-checkpoints/{tag}/compactor.safetensors",
        model.config, device=runtime.device).to(model.dtype)
    if lever == "e1_sqrt_scale":
        for _layer in comp.layers:
            for _m in list(_layer.cross) + list(_layer.selfattn):
                _m.d_l = 16                # deployment scale for E1 instances
    for layer in comp.layers:
        layer.cross[0]._c3a_block1 = True

    n_layers = int(model.config.num_hidden_layers)          # 36
    n_heads = int(model.config.num_attention_heads)         # 32
    hidden = int(model.config.hidden_size)                  # 2560

    # eager/sdpa toggle sanity: argmax must agree on a probe forward
    def set_attn(mode):
        model.config._attn_implementation = mode
        for lyr in model.model.layers:
            lyr.self_attn.config._attn_implementation = mode
    probe_ids = tok.encode("The capital of France is", add_special_tokens=False)
    set_attn("sdpa")
    l1 = model(input_ids=torch.tensor([probe_ids], device=runtime.device)
               ).logits[0, -1]
    set_attn("eager")
    l2 = model(input_ids=torch.tensor([probe_ids], device=runtime.device)
               ).logits[0, -1]
    assert int(l1.argmax()) == int(l2.argmax()), "eager/sdpa argmax mismatch"
    set_attn("sdpa")

    src = manifest_path or (
        "/artifacts/probe/multihop-capture-manifest.json" if subset == "mh"
        else "/artifacts/probe/capture-manifest.json")
    with open(src) as f:
        manifest = json.load(f)
    if subset == "pilot":
        items = [m for m in manifest if m["pilot"]]
    elif subset == "rest":
        items = [m for m in manifest if not m["pilot"]]
    else:
        items = manifest
    items = [m for n, m in enumerate(
        sorted(items, key=lambda r: (r["domain"], r["doc_id"], r["item_id"])))
        if n % n_slices == slice_idx]

    needed = {m["doc_id"] for m in items}
    texts = {}
    for domain in DOMAINS:
        with open(f"/artifacts/corpus/{domain}.jsonl") as f:
            for line in f:
                rec = json.loads(line)
                if rec["doc_id"] in needed:
                    texts[rec["doc_id"]] = rec["text"]

    name = f"{subset}-slice-{slice_idx:02d}"
    state_path = f"/artifacts/probe/{out_prefix}-{name}.state.json"
    npz_path = f"/artifacts/probe/{out_prefix}-{name}.npz"
    state = {"done": 0, "rows": []}
    attn_stats, hiddens, c3as, kept_ids = [], [], [], []
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)
        try:
            z = np.load(npz_path)
            attn_stats = list(z["attn_stats"])
            hiddens = list(z["hidden"])
            c3as = list(z["c3a"])
            kept_ids = list(z["item_ids"])
        except Exception as e:      # shard corrupted by mid-write preemption
            print(f"npz unreadable ({e}); restarting slice from 0",
                  flush=True)
            state = {"done": 0, "rows": []}

    yes_id = tok.encode(" Yes", add_special_tokens=False)[-1]
    no_id = tok.encode(" No", add_special_tokens=False)[-1]
    letters = ["A", "B", "C", "D"]
    letter_ids = [tok.encode(" " + l, add_special_tokens=False)[-1]
                  for l in letters]

    def attn_step_stats(attns, row_idx, total_len):
        """attns: tuple of [1, H, P, T]; returns [36, 32, 6] fp16."""
        out = np.empty((n_layers, n_heads, 6), dtype=np.float16)
        lat_lo, lat_hi = SINKS, SINKS + T_LAT
        rec_hi = SINKS + T_LAT + RECENT_RAW
        for li, a in enumerate(attns):
            v = a[0, :, row_idx, :].float()              # [H, T]
            lat = v[:, lat_lo:lat_hi]
            m_lat = lat.sum(-1)
            m_sink = v[:, :SINKS].sum(-1)
            m_rec = v[:, lat_hi:rec_hi].sum(-1)
            p = lat / (m_lat[:, None] + 1e-9)
            ent = -(p * (p + 1e-12).log()).sum(-1) / np.log(T_LAT)
            mx = lat.max(-1).values
            out[li, :, 0] = m_lat.cpu().numpy()
            out[li, :, 1] = m_sink.cpu().numpy()
            out[li, :, 2] = m_rec.cpu().numpy()
            out[li, :, 3] = ent.cpu().numpy()
            out[li, :, 4] = mx.cpu().numpy()
            out[li, :, 5] = (mx / (m_lat + 1e-9)).cpu().numpy()
        return out

    def save_all():
        np.savez_compressed(
            npz_path,
            attn_stats=np.stack(attn_stats) if attn_stats else np.zeros(0),
            hidden=np.stack(hiddens) if hiddens else np.zeros(0),
            c3a=np.stack(c3as) if c3as else np.zeros(0),
            item_ids=np.array(kept_ids))
        with open(state_path, "w") as f:
            json.dump(state, f)
        artifacts.commit()

    os.makedirs("/artifacts/probe", exist_ok=True)
    doc_cache: dict[str, list[int]] = {}
    for n, row in enumerate(items):
        if n < state["done"]:
            continue
        if row["doc_id"] not in doc_cache:
            doc_cache.clear()
            doc_cache[row["doc_id"]] = tok.encode(texts[row["doc_id"]],
                                                  add_special_tokens=False)
        ids = doc_cache[row["doc_id"]]
        chunk_start = int(row["item_id"].split("_")[-2])
        # explicit ctx_start (multihop rows) reproduces the slice builder's
        # unclamped window; GT16 rows keep the clamped formula
        ctx_start = row.get("ctx_start",
                            max(0, min(chunk_start - row["chunk_rel_start"],
                                       len(ids) - CTX)))
        ctx_ids = ids[ctx_start:ctx_start + CTX]
        chunk_rel = chunk_start - ctx_start

        cache, _ = runtime.prefill(ctx_ids)
        # needle indices in compactor source space (logical 4..3071 -> 0..3067)
        lo = max(SINKS, chunk_rel)
        hi = min(CTX - RECENT_RAW, chunk_rel + 1024)
        with torch.inference_mode():
            if hi > lo and not light:
                C3aContext.needle_idx = torch.arange(
                    lo - SINKS, hi - SINKS, device=runtime.device)
            else:
                C3aContext.needle_idx = None
            C3aContext.results = []
            C3aContext.active = not light
            cc = compact_prefix_keep_recent(comp, cache, RECENT_RAW, depth=1)
            C3aContext.active = False
        c3a_item = (torch.stack(C3aContext.results).numpy()
                    if C3aContext.results
                    else np.zeros((n_layers, 8, 4), dtype=np.float16))
        C3aContext.results = []

        # ---- answer trial pass, eager, attentions + hidden states --------
        opts = "\n".join(f"{l}. {o}" for l, o in zip(letters, row["options"]))
        prompt = (f"\n\nQuestion: {row['question']}\n{opts}\n"
                  f"Answer with a single letter.\nAnswer:")
        p_ids = tok.encode(prompt, add_special_tokens=False)
        set_attn("eager")
        work = cc.clone_detached()
        steps_stats = []
        with torch.inference_mode():
            n_p = len(p_ids)
            input_ids = torch.tensor([p_ids], device=runtime.device)
            start = work.next_logical_position
            phys = work.physical_length
            out = model(input_ids=input_ids,
                        attention_mask=torch.ones((1, phys + n_p),
                                                  dtype=torch.long,
                                                  device=runtime.device),
                        position_ids=torch.arange(
                            start, start + n_p,
                            device=runtime.device).unsqueeze(0),
                        past_key_values=work,
                        cache_position=torch.arange(
                            phys, phys + n_p, device=runtime.device),
                        use_cache=True, output_attentions=True,
                        output_hidden_states=True)
            work.note_appended(n_p)
            steps_stats.append(attn_step_stats(out.attentions, n_p - 1,
                                               phys + n_p))
            hid = np.stack([h[0, -1].float().cpu().numpy()
                            for h in out.hidden_states]).astype(np.float16)
            last_logits = out.logits[0, -1].float()
            scores = [float(last_logits[i]) for i in letter_ids]
            pred_trial = letters[scores.index(max(scores))]
            decode_ids = []
            logits = last_logits
            for _ in range(0 if light else 3):
                nxt = int(logits.argmax())
                decode_ids.append(nxt)
                phys = work.physical_length
                start = work.next_logical_position
                out = model(input_ids=torch.tensor([[nxt]],
                                                   device=runtime.device),
                            attention_mask=torch.ones(
                                (1, phys + 1), dtype=torch.long,
                                device=runtime.device),
                            position_ids=torch.tensor(
                                [[start]], device=runtime.device),
                            past_key_values=work,
                            cache_position=torch.tensor(
                                [phys], device=runtime.device),
                            use_cache=True, output_attentions=True)
                work.note_appended(1)
                steps_stats.append(attn_step_stats(out.attentions, 0,
                                                   phys + 1))
                logits = out.logits[0, -1].float()
        set_attn("sdpa")
        del work

        # ---- p2 self-check (sdpa, fresh clone) ---------------------------
        sc_prompt = (f"\n\nQuestion: {row['question']}\n{opts}\n"
                     "Does the context above contain the information needed "
                     "to answer this question? Answer Yes or No.\nAnswer:")
        sc_ids = tok.encode(sc_prompt, add_special_tokens=False)
        sc = cc.clone_detached()
        with torch.inference_mode():
            sc_logits = runtime.forward_extend(sc, sc_ids)[-1]
        two = torch.softmax(torch.tensor(
            [float(sc_logits[yes_id]), float(sc_logits[no_id])]), dim=-1)
        del sc, cc, cache

        attn_stats.append(np.stack(steps_stats))         # [4, 36, 32, 6]
        hiddens.append(hid)                              # [37, 2560]
        c3as.append(c3a_item.astype(np.float16))         # [36, 8, 4]
        kept_ids.append(row["item_id"])
        state["rows"].append({
            "item_id": row["item_id"], "domain": row["domain"],
            "y": row["y"], "in_e1": row["in_e1"], "pilot": row["pilot"],
            "pred_trial": pred_trial, "pred_raw": row["pred_raw"],
            "decode_ids": decode_ids,
            "p2_insufficient": round(float(two[1]), 6)})
        state["done"] = n + 1
        if (n + 1) % 250 == 0 or n + 1 == len(items):
            save_all()
            print(f"{name} {n + 1}/{len(items)}", flush=True)
    save_all()
    spc._QKNormCrossAttention.forward = _orig_forward
    return {"name": name, "items": len(state["rows"])}


@app.local_entrypoint()
def main(subset: str, slice_idx: int, n_slices: int, light: bool = False,
         tag: str = TAG, manifest_path: str = "", out_prefix: str = "capture"):
    print(run_capture.remote(subset, slice_idx, n_slices, light, tag,
                             manifest_path, out_prefix))


@app.local_entrypoint()
def fleet(subset: str, n_slices: int, light: bool, tag: str,
          manifest_path: str, out_prefix: str, lever: str = "none"):
    handles = [run_capture.spawn(subset, k, n_slices, light, tag,
                                 manifest_path, out_prefix, lever)
               for k in range(n_slices)]
    print("spawned", len(handles), "capture slices ->", out_prefix)
