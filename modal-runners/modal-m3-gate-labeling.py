"""M3 gate labeling on Modal (GATE.md §3; spec §17.5).

Per item i: y_i(f) = 1 iff answer under the f-compacted context differs from
the answer under the raw source span (eq_policy_v1). One 4096-token context
prefill per item (placement randomized by item hash so the chunk's position
in the window — and hence eviction exposure under the oldest-nonsink policy —
varies naturally); per fraction, clone + evict the oldest non-sink window.
Items whose span survived are kept as natural y=0 rows (GATE.md §3).

Usage:
  modal run --detach modal-runners/modal-m3-gate-labeling.py::launch_labeling
  modal run modal-runners/modal-m3-gate-labeling.py::merge_labels
  modal run modal-runners/modal-m3-gate-labeling.py::compute_embeddings
"""

import hashlib
import json

import modal

GPU = "H100"
PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
FRACTIONS = (0.25, 0.40)
CTX_TOKENS = 4096
CHUNK_TOKENS = 1024

app = modal.App("memsub-m3-gate")

gpu_image = (
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


def _stable_rng(item_id: str):
    import random
    seed = int.from_bytes(hashlib.sha256(item_id.encode()).digest()[:4], "big")
    return random.Random(seed)


@app.function(image=gpu_image, gpu=GPU, volumes=VOLUMES, timeout=43200,
              memory=32768)
def label_domain_slice(domain: str, slice_idx: int, n_slices: int) -> dict:
    """Resume-safe labeling worker: one slice of one domain's items."""
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    from memsub.certification import McqItem, eq_policy_v1
    from memsub.reference_config import build_runtime

    os.makedirs(f"/artifacts/corpus-gate-labels/{domain}", exist_ok=True)
    state_path = (f"/artifacts/corpus-gate-labels/{domain}/"
                  f"slice-{slice_idx:02d}.state.json")
    state = {"done": 0, "rows": []}
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)

    with open("/artifacts/corpus-mcq-full/all-items.json") as f:
        items = [McqItem(**d) for d in json.load(f)
                 if d["doc_id"].startswith(domain + "/")]
    items = [it for n, it in enumerate(sorted(items, key=lambda i: i.doc_id))
             if n % n_slices == slice_idx]
    texts = {}
    with open(f"/artifacts/corpus/{domain}.jsonl") as f:
        for line in f:
            rec = json.loads(line)
            texts[rec["doc_id"]] = rec["text"]

    runtime = build_runtime(reference=True)
    tok = runtime.tokenizer
    doc_ids_cache: dict[str, list[int]] = {}

    for n, item in enumerate(items):
        if n < state["done"]:
            continue
        if item.doc_id not in doc_ids_cache:
            doc_ids_cache.clear()  # keep at most one tokenized doc in RAM
            doc_ids_cache[item.doc_id] = tok.encode(
                texts[item.doc_id], add_special_tokens=False)
        ids = doc_ids_cache[item.doc_id]
        rng = _stable_rng(item.item_id)
        offset = rng.randrange(0, CTX_TOKENS - CHUNK_TOKENS + 1)
        ctx_start = max(0, min(item.chunk_token_start - offset,
                               len(ids) - CTX_TOKENS))
        ctx_ids = ids[ctx_start:ctx_start + CTX_TOKENS]
        chunk_rel = item.chunk_token_start - ctx_start
        chunk_text = tok.decode(
            ids[item.chunk_token_start:item.chunk_token_start + CHUNK_TOKENS])

        cache, _ = runtime.prefill(ctx_ids)
        pred_raw = runtime.answer_letter(chunk_text, item.question, item.options)
        row = {
            "item_id": item.item_id, "doc_id": item.doc_id, "domain": domain,
            "question": item.question, "options": item.options,
            "gold": item.gold_letter, "pred_raw": pred_raw,
            "raw_correct": eq_policy_v1(pred_raw, item.gold_letter),
            "pointwise_heuristic": any(
                o.strip().lower() in chunk_text.lower()
                for i, o in enumerate(item.options)
                if "ABCD"[i] == item.gold_letter),
            "chunk_rel_start": chunk_rel, "ctx_len": len(ctx_ids),
            "chunk_gloss": chunk_text[:800],
            "ctx_tail_gloss": tok.decode(ctx_ids[-128:])[:500],
        }
        for f in FRACTIONS:
            evict_n = int(len(ctx_ids) * f)
            cc = cache.clone_detached()
            cc.evict_logical_range(4, 4 + evict_n)
            pred_c = runtime.answer_letter("", item.question, item.options,
                                           cache=cc)
            lo, hi = 4, 4 + evict_n
            ov = max(0, min(hi, chunk_rel + CHUNK_TOKENS) - max(lo, chunk_rel))
            key = f"{f:.2f}"
            row[f"pred_compact_{key}"] = pred_c
            row[f"y_{key}"] = int(not eq_policy_v1(pred_c, pred_raw))
            row[f"overlap_{key}"] = round(ov / CHUNK_TOKENS, 4)
            row[f"evicted_{key}"] = int(ov / CHUNK_TOKENS > 0.5)
        del cache
        state["rows"].append(row)
        state["done"] = n + 1
        if (n + 1) % 200 == 0 or n + 1 == len(items):
            with open(state_path, "w") as fh:
                json.dump(state, fh)
            artifacts.commit()
            print(f"{domain}[{slice_idx}] {n + 1}/{len(items)}")
    with open(state_path, "w") as fh:
        json.dump(state, fh)
    artifacts.commit()
    return {"domain": domain, "slice": slice_idx, "rows": len(state["rows"])}


@app.function(image=gpu_image, volumes={"/artifacts": artifacts}, timeout=3600,
              memory=32768)
def merge_labels() -> dict:
    import glob
    counts, out = {}, []
    for path in sorted(glob.glob(
            "/artifacts/corpus-gate-labels/*/slice-*.state.json")):
        domain = path.split("/")[-2]
        with open(path) as f:
            rows = json.load(f)["rows"]
        counts[domain] = counts.get(domain, 0) + len(rows)
        out.extend(rows)
    with open("/artifacts/corpus-gate-labels/all-labels.json", "w") as f:
        json.dump(out, f)
    artifacts.commit()
    pos = {f"{f:.2f}": sum(r[f"y_{f:.2f}"] for r in out) / max(len(out), 1)
           for f in FRACTIONS}
    return {"total": len(out), "positive_rate": pos, **counts}


@app.function(image=gpu_image, gpu=GPU, volumes=VOLUMES, timeout=14400,
              memory=65536)
def compute_embeddings(batch_size: int = 64) -> dict:
    """shadow-v1 embeddings: q_emb(question + ctx-tail gloss), b_emb(chunk
    gloss = raw-indexer extractive gloss). Order aligned with all-labels."""
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    from memsub.compilers import Qwen3ShadowEmbedder

    with open("/artifacts/corpus-gate-labels/all-labels.json") as f:
        rows = json.load(f)
    embedder = Qwen3ShadowEmbedder(device="cuda", dtype="bfloat16")

    def embed_all(texts):
        out = []
        for i in range(0, len(texts), batch_size):
            out.append(embedder.embed(texts[i:i + batch_size]))
            if i % (batch_size * 50) == 0:
                print(f"embedded {i}/{len(texts)}")
        return np.concatenate(out).astype(np.float32)

    q_emb = embed_all([r["question"] + " || recent: " + r["ctx_tail_gloss"]
                       for r in rows])
    b_emb = embed_all([r["chunk_gloss"] for r in rows])
    np.savez_compressed("/artifacts/corpus-gate-labels/embeddings.npz",
                        q_emb=q_emb, b_emb=b_emb,
                        item_ids=np.array([r["item_id"] for r in rows]))
    artifacts.commit()
    return {"rows": len(rows), "dim": int(q_emb.shape[1])}


@app.local_entrypoint()
def launch_labeling(slices_per_domain: int = 3):
    handles = []
    for domain in DOMAINS:
        for s in range(slices_per_domain):
            handles.append(label_domain_slice.spawn(domain, s, slices_per_domain))
    print(f"spawned {len(handles)} labeling workers")
