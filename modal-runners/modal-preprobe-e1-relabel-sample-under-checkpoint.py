"""PREPROBE E1 relabel: score the fixed 2,000-item sample under a given
compactor checkpoint with the EXACT GT16 labeling protocol
(modal-m35-certification-and-gate-refresh.py::relabel_slice semantics:
same deterministic context reconstruction, deployment shape old-prefix ->
t latents + recent 1024 raw, depth 1, eq_policy_v1, greedy letter-argmax).
H100 like the original A relabel — same GPU class, no cross-arch numeric
drift in the label comparison.

Reads  /artifacts/preprobe/e1-sample-items.json
Writes /artifacts/preprobe/e1-relabel-<out_name>.state.json (resumable)

Usage:
  modal run --detach modal-runners/modal-preprobe-e1-relabel-sample-under-checkpoint.py \
      --tag single-t1024-T8k-seed51234 --out-name B
  modal run --detach modal-runners/modal-preprobe-e1-relabel-sample-under-checkpoint.py \
      --tag single-t512-T8k --out-name C
"""

import json

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
CTX = 4096
RECENT_RAW = 1024

app = modal.App("memsub-preprobe-e1-relabel")
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
              memory=32768)
def relabel_sample(tag: str, out_name: str,
                   lever: str = "none") -> dict:
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    import torch
    from memsub.certification import McqItem, eq_policy_v1
    from memsub.compactor import StillAmortizedKVCompactor
    from memsub.compactor.still_amortized_kv_compactor import (
        compact_prefix_keep_recent)
    from memsub.reference_config import build_runtime

    state_path = f"/artifacts/preprobe/e1-relabel-{out_name}.state.json"
    state = {"done": 0, "rows": []}
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)

    with open("/artifacts/preprobe/e1-sample-items.json") as f:
        sample = json.load(f)
    # original protocol iterates sorted by doc_id within a domain with a
    # single-doc tokenization cache; sorting by (domain, doc_id) preserves
    # that access pattern across the mixed-domain sample
    sample.sort(key=lambda r: (r["domain"], r["doc_id"], r["item_id"]))

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
        f"/artifacts/compactor-checkpoints/{tag}/compactor.safetensors",
        runtime.model.config, device=runtime.device).to(runtime.model.dtype)
    if lever == "e1_sqrt_scale":
        for _layer in comp.layers:
            for _m in list(_layer.cross) + list(_layer.selfattn):
                _m.d_l = 16                # deployment scale for E1 instances
    t_latents = comp.t
    tok = runtime.tokenizer
    doc_cache: dict[str, list[int]] = {}
    reduction = 1 - (4 + t_latents + RECENT_RAW) / CTX
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
        with torch.inference_mode():
            cc = compact_prefix_keep_recent(comp, cache, RECENT_RAW, depth=1)
        pred_c = runtime.answer_letter("", item.question, item.options,
                                       cache=cc)
        lo, hi = 4, len(ctx_ids) - RECENT_RAW
        ov = max(0, min(hi, chunk_rel + 1024) - max(lo, chunk_rel)) / 1024
        state["rows"].append({
            "item_id": row["item_id"], "doc_id": row["doc_id"],
            "domain": row["domain"], "tag": tag,
            "pred_compact": pred_c,
            "y": int(not eq_policy_v1(pred_c, row["pred_raw"])),
            "overlap": round(ov, 4), "evicted": int(ov > 0.5),
            "fraction": round(reduction, 4)})
        state["done"] = n + 1
        if (n + 1) % 100 == 0 or n + 1 == len(sample):
            with open(state_path, "w") as f:
                json.dump(state, f)
            artifacts.commit()
            print(f"{out_name}[{tag}] {n + 1}/{len(sample)}", flush=True)
    with open(state_path, "w") as f:
        json.dump(state, f)
    artifacts.commit()
    return {"tag": tag, "out": out_name, "rows": len(state["rows"]),
            "y_rate": sum(r["y"] for r in state["rows"])
            / max(len(state["rows"]), 1)}


@app.local_entrypoint()
def main(tag: str, out_name: str, lever: str = "none"):
    print(relabel_sample.remote(tag, out_name, lever))
