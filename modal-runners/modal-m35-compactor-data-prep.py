"""M3.5 training-data prep (COMPACTOR.md §2.2): rationale traces.

For a domain-balanced subset of B.3 items, generate the teacher's greedy
rationale + answer letter under FULL 8k context. Training triplets:
(ctx window spec, prompt ids, answer ids = rationale trace). Resume-safe
slices in corpus-compactor-train/.

Usage:
  modal run --detach modal-runners/modal-m35-compactor-data-prep.py::launch_prep
  modal run modal-runners/modal-m35-compactor-data-prep.py::merge_triplets
"""

import hashlib
import json

import modal

GPU = "H100"
PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
CTX_TOKENS = 8192
RATIONALE_TOKENS = 96

app = modal.App("memsub-m35-dataprep")
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

PROMPT = ("\n\nQuestion: {q}\n{opts}\n"
          "Think briefly, then answer with 'ANSWER: <letter>'.\n")


@app.function(image=gpu_image, gpu=GPU, volumes=VOLUMES, timeout=43200,
              memory=32768)
def prep_domain_slice(domain: str, slice_idx: int, n_slices: int,
                      items_per_domain: int = 6000) -> dict:
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    from memsub.certification import McqItem
    from memsub.reference_config import build_runtime

    os.makedirs(f"/artifacts/corpus-compactor-train/{domain}", exist_ok=True)
    state_path = (f"/artifacts/corpus-compactor-train/{domain}/"
                  f"slice-{slice_idx:02d}.state.json")
    state = {"done": 0, "rows": []}
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)

    with open("/artifacts/corpus-mcq-full/all-items.json") as f:
        items = [McqItem(**d) for d in json.load(f)
                 if d["doc_id"].startswith(domain + "/")]
    items = sorted(items, key=lambda i: i.doc_id)[:items_per_domain]
    items = [it for n, it in enumerate(items) if n % n_slices == slice_idx]
    texts = {}
    with open(f"/artifacts/corpus/{domain}.jsonl") as f:
        for line in f:
            rec = json.loads(line)
            texts[rec["doc_id"]] = rec["text"]

    runtime = build_runtime(reference=True)
    tok = runtime.tokenizer
    doc_cache: dict[str, list[int]] = {}
    for n, item in enumerate(items):
        if n < state["done"]:
            continue
        if item.doc_id not in doc_cache:
            doc_cache.clear()
            doc_cache[item.doc_id] = tok.encode(texts[item.doc_id],
                                                add_special_tokens=False)
        ids = doc_cache[item.doc_id]
        seed = int.from_bytes(hashlib.sha256(
            item.item_id.encode()).digest()[:4], "big")
        offset = seed % (CTX_TOKENS - 1024)
        ctx_start = max(0, min(item.chunk_token_start - offset,
                               len(ids) - CTX_TOKENS))
        ctx_ids = ids[ctx_start:ctx_start + CTX_TOKENS]
        if len(ctx_ids) < CTX_TOKENS:
            state["done"] = n + 1
            continue
        opts = "\n".join(f"{l}. {o}" for l, o in zip("ABCD", item.options))
        prompt_ids = tok.encode(PROMPT.format(q=item.question, opts=opts),
                                add_special_tokens=False)
        cache, logits = runtime.prefill(ctx_ids + prompt_ids)
        steps = runtime.continue_greedy(cache, RATIONALE_TOKENS, logits,
                                        eos_token_id=tok.eos_token_id)
        answer_ids = [s.token_id for s in steps]
        state["rows"].append({
            "item_id": item.item_id, "doc_id": item.doc_id, "domain": domain,
            "ctx_start": ctx_start, "ctx_len": CTX_TOKENS,
            "prompt_ids": prompt_ids, "answer_ids": answer_ids,
            "gold": item.gold_letter})
        state["done"] = n + 1
        if (n + 1) % 100 == 0 or n + 1 == len(items):
            with open(state_path, "w") as f:
                json.dump(state, f)
            artifacts.commit()
            print(f"{domain}[{slice_idx}] {n + 1}/{len(items)}")
    with open(state_path, "w") as f:
        json.dump(state, f)
    artifacts.commit()
    return {"domain": domain, "slice": slice_idx, "rows": len(state["rows"])}


@app.function(image=gpu_image, volumes={"/artifacts": artifacts}, timeout=3600,
              memory=32768)
def merge_triplets() -> dict:
    import glob
    out, counts = [], {}
    for path in sorted(glob.glob(
            "/artifacts/corpus-compactor-train/*/slice-*.state.json")):
        domain = path.split("/")[-2]
        with open(path) as f:
            rows = json.load(f)["rows"]
        counts[domain] = counts.get(domain, 0) + len(rows)
        out.extend(rows)
    with open("/artifacts/corpus-compactor-train/triplets.json", "w") as f:
        json.dump(out, f)
    artifacts.commit()
    return {"total": len(out), **counts}


@app.local_entrypoint()
def launch_prep(slices_per_domain: int = 3, items_per_domain: int = 6000):
    handles = []
    for d in DOMAINS:
        for s in range(slices_per_domain):
            handles.append(prep_domain_slice.spawn(d, s, slices_per_domain,
                                                   items_per_domain))
    print(f"spawned {len(handles)} prep workers")
