"""FULLRECIPE P0/C1 — batched teacher rationale pass over the mixture remainder.

Replicates the M3.5 prep protocol EXACTLY (same PROMPT, same ctx-window seed
math from sha256(item_id), greedy, 96 new tokens, eos-stop, eos kept in
trace) but batched via left-padded HF generate. Resume-safe per-slice state
in corpus-fullrecipe/rationales/. Docs are sharded contiguously so the
per-doc tokenization cache holds.

Usage:
  # 200-item quality sample (50/domain), then inspect before scaling:
  modal run modal-runners/modal-fullrecipe-c1-batched-rationale-prep.py::sample
  # batched-vs-unbatched equivalence on already-traced items:
  modal run modal-runners/modal-fullrecipe-c1-batched-rationale-prep.py::overlap_check
  # full remainder pass (resumes past sample rows):
  modal run --detach modal-runners/modal-fullrecipe-c1-batched-rationale-prep.py::launch
  # merge -> triplets-full.json (shuffled) + triplets-mid.json (1/8):
  modal run modal-runners/modal-fullrecipe-c1-batched-rationale-prep.py::merge
"""

import hashlib
import json

import modal

GPU = "H100"
PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
CTX_TOKENS = 8192
RATIONALE_TOKENS = 96
BATCH = 16
N_SLICES = 2          # per domain -> 8 workers total

app = modal.App("memsub-fullrecipe-c1-rationale")
gpu_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .add_local_dir("memsub", "/root/repo/memsub")
)
hf_cache = modal.Volume.from_name("memsub-hf-cache", create_if_missing=True)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/root/.cache/huggingface": hf_cache, "/artifacts": artifacts}
DOMAINS = ("financial", "legal", "code", "literature")

PROMPT = ("\n\nQuestion: {q}\n{opts}\n"
          "Think briefly, then answer with 'ANSWER: <letter>'.\n")


def _ctx_window(item_id: str, chunk_token_start: int, doc_len: int):
    seed = int.from_bytes(hashlib.sha256(item_id.encode()).digest()[:4], "big")
    offset = seed % (CTX_TOKENS - 1024)
    return max(0, min(chunk_token_start - offset, doc_len - CTX_TOKENS))


def _load_model():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B-Instruct-2507")
    model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen3-4B-Instruct-2507", torch_dtype=torch.bfloat16,
        attn_implementation="sdpa").to("cuda").eval()
    if tok.pad_token_id is None or tok.pad_token_id == tok.eos_token_id:
        tok.pad_token = "<|endoftext|>"
    tok.padding_side = "left"
    return model, tok


def _slice_work(domain: str, slice_idx: int, n_slices: int):
    """Remainder items of this domain, sharded by DOC (keeps tokenizer cache
    hot), plus item metadata and doc texts."""
    with open("/artifacts/corpus-fullrecipe/mixture-manifest.json") as f:
        manifest = json.load(f)["items"]
    todo_ids = {m["item_id"] for m in manifest
                if m["domain"] == domain and not m["has_trace"]}
    with open("/artifacts/corpus-mcq-full/all-items.json") as f:
        meta = {i["item_id"]: i for i in json.load(f)
                if i["item_id"] in todo_ids}
    items = sorted(meta.values(), key=lambda i: (i["doc_id"], i["item_id"]))
    docs = sorted({i["doc_id"] for i in items})
    my_docs = {d for n, d in enumerate(docs) if n % n_slices == slice_idx}
    items = [i for i in items if i["doc_id"] in my_docs]
    texts = {}
    with open(f"/artifacts/corpus/{domain}.jsonl") as f:
        for line in f:
            rec = json.loads(line)
            if rec["doc_id"] in my_docs:
                texts[rec["doc_id"]] = rec["text"]
    return items, texts


@app.function(image=gpu_image, gpu=GPU, volumes=VOLUMES, timeout=43200,
              memory=32768, cpu=8)
def prep_slice(domain: str, slice_idx: int, n_slices: int = N_SLICES,
               sample_limit: int = 0) -> dict:
    import os
    import time
    import torch

    os.makedirs("/artifacts/corpus-fullrecipe/rationales", exist_ok=True)
    state_path = (f"/artifacts/corpus-fullrecipe/rationales/"
                  f"{domain}-slice-{slice_idx:02d}.state.json")
    state = {"done": 0, "rows": []}
    if not sample_limit and os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)

    items, texts = _slice_work(domain, slice_idx, n_slices)
    if sample_limit:
        # spread across the slice — the slice HEAD is the block of items the
        # original prep already attempted and dropped for short context
        stride = max(1, len(items) // sample_limit)
        items = items[::stride][:sample_limit]
        state_path = state_path.replace(".state.json", ".sample.json")
    else:
        import glob
        completed_ids = set()
        for prior_path in glob.glob(
                "/artifacts/corpus-fullrecipe/rationales/*.state.json"):
            with open(prior_path) as f:
                completed_ids.update(
                    row["item_id"] for row in json.load(f).get("rows", []))
        current_ids = {item["item_id"] for item in items}
        state["rows"] = [row for row in state["rows"]
                         if row["item_id"] in current_ids]
        items = [item for item in items
                 if item["item_id"] not in completed_ids]
        state["done"] = 0
    if not items:
        return {"domain": domain, "slice": slice_idx, "rows": len(state["rows"]),
                "status": "already-complete"}

    model, tok = _load_model()
    eos = tok.eos_token_id
    doc_tok: dict[str, list[int]] = {}

    def doc_ids(doc_id: str) -> list[int]:
        if doc_id not in doc_tok:
            if len(doc_tok) > 48:
                doc_tok.clear()
            doc_tok[doc_id] = tok.encode(texts[doc_id],
                                         add_special_tokens=False)
        return doc_tok[doc_id]

    t0, gen_count = time.time(), 0
    n = state["done"]
    while n < len(items):
        batch, batch_meta = [], []
        while n < len(items) and len(batch) < BATCH:
            it = items[n]
            n += 1
            ids = doc_ids(it["doc_id"])
            ctx_start = _ctx_window(it["item_id"], it["chunk_token_start"],
                                    len(ids))
            ctx = ids[ctx_start:ctx_start + CTX_TOKENS]
            if len(ctx) < CTX_TOKENS:
                continue                       # short doc: dropped (same as prep)
            opts = "\n".join(f"{l}. {o}"
                             for l, o in zip("ABCD", it["options"]))
            prompt_ids = tok.encode(
                PROMPT.format(q=it["question"], opts=opts),
                add_special_tokens=False)
            batch.append(ctx + prompt_ids)
            batch_meta.append((it, ctx_start, prompt_ids))
        if batch:
            maxlen = max(len(s) for s in batch)
            input_ids = torch.full((len(batch), maxlen), tok.pad_token_id,
                                   dtype=torch.long)
            mask = torch.zeros((len(batch), maxlen), dtype=torch.long)
            for bi, seq in enumerate(batch):
                input_ids[bi, maxlen - len(seq):] = torch.tensor(seq)
                mask[bi, maxlen - len(seq):] = 1
            with torch.inference_mode():
                out = model.generate(
                    input_ids=input_ids.cuda(), attention_mask=mask.cuda(),
                    do_sample=False, max_new_tokens=RATIONALE_TOKENS,
                    eos_token_id=eos, pad_token_id=tok.pad_token_id)
            new = out[:, maxlen:].cpu().tolist()
            for bi, (it, ctx_start, prompt_ids) in enumerate(batch_meta):
                ans = new[bi]
                if eos in ans:                 # keep through first eos
                    ans = ans[:ans.index(eos) + 1]
                state["rows"].append({
                    "item_id": it["item_id"], "doc_id": it["doc_id"],
                    "domain": domain, "ctx_start": ctx_start,
                    "ctx_len": CTX_TOKENS, "prompt_ids": prompt_ids,
                    "answer_ids": ans, "gold": it["gold_letter"]})
                gen_count += 1
        state["done"] = n
        if n % (BATCH * 16) < BATCH or n >= len(items):
            with open(state_path, "w") as f:
                json.dump(state, f)
            artifacts.commit()
            rate = gen_count / max(time.time() - t0, 1)
            print(f"{domain}[{slice_idx}] {n}/{len(items)} "
                  f"({rate:.2f} items/s)", flush=True)
    with open(state_path, "w") as f:
        json.dump(state, f)
    artifacts.commit()
    return {"domain": domain, "slice": slice_idx, "done": state["done"],
            "rows": len(state["rows"])}


@app.function(image=gpu_image, gpu=GPU, volumes=VOLUMES, timeout=7200,
              memory=32768, cpu=8)
def regen_traced_overlap(n_items: int = 24) -> dict:
    """Regenerate already-traced items batched; report letter/token parity
    with the stored unbatched traces (batching-equivalence check)."""
    import torch
    with open("/artifacts/corpus-compactor-train/triplets.json") as f:
        old = json.load(f)
    with open("/artifacts/corpus-mcq-full/all-items.json") as f:
        meta = {i["item_id"]: i for i in json.load(f)}
    picks = [r for k, r in enumerate(old) if k % (len(old) // n_items) == 0][:n_items]
    model, tok = _load_model()
    eos = tok.eos_token_id
    texts = {}
    needed = {r["doc_id"] for r in picks}
    for domain in DOMAINS:
        with open(f"/artifacts/corpus/{domain}.jsonl") as f:
            for line in f:
                rec = json.loads(line)
                if rec["doc_id"] in needed:
                    texts[rec["doc_id"]] = rec["text"]
    results = []
    for i in range(0, len(picks), 8):
        chunk = picks[i:i + 8]
        seqs = []
        for r in chunk:
            ids = tok.encode(texts[r["doc_id"]], add_special_tokens=False)
            seqs.append(ids[r["ctx_start"]:r["ctx_start"] + CTX_TOKENS]
                        + r["prompt_ids"])
        maxlen = max(len(s) for s in seqs)
        input_ids = torch.full((len(seqs), maxlen), tok.pad_token_id,
                               dtype=torch.long)
        mask = torch.zeros((len(seqs), maxlen), dtype=torch.long)
        for bi, seq in enumerate(seqs):
            input_ids[bi, maxlen - len(seq):] = torch.tensor(seq)
            mask[bi, maxlen - len(seq):] = 1
        with torch.inference_mode():
            out = model.generate(
                input_ids=input_ids.cuda(), attention_mask=mask.cuda(),
                do_sample=False, max_new_tokens=RATIONALE_TOKENS,
                eos_token_id=eos, pad_token_id=tok.pad_token_id)
        new = out[:, maxlen:].cpu().tolist()
        for r, ans in zip(chunk, new):
            if eos in ans:
                ans = ans[:ans.index(eos) + 1]
            old_txt = tok.decode(r["answer_ids"])
            new_txt = tok.decode(ans)
            same_prefix = 0
            for a, b in zip(r["answer_ids"], ans):
                if a != b:
                    break
                same_prefix += 1

            def _letter(t):
                return t.rsplit("ANSWER:", 1)[-1].strip()[:1] \
                    if "ANSWER:" in t else None
            results.append({
                "item_id": r["item_id"], "gold": r["gold"],
                "old_letter": _letter(old_txt), "new_letter": _letter(new_txt),
                "prefix_match": same_prefix,
                "old_len": len(r["answer_ids"]), "new_len": len(ans),
                "exact": r["answer_ids"] == ans})
    n_exact = sum(r["exact"] for r in results)
    letter_agree = sum(r["old_letter"] == r["new_letter"] for r in results)
    return {"n": len(results), "exact_trace_match": n_exact,
            "letter_agreement": letter_agree, "rows": results}


@app.function(image=gpu_image, volumes={"/artifacts": artifacts},
              timeout=3600, memory=32768)
def merge() -> dict:
    """Merge M3.5 traces + remainder rationales into the full-recipe training
    file (deterministic shuffle, seed 1234) + the 1/8 mid-scale subset."""
    import glob
    import random
    import sys
    sys.path.insert(0, "/root/repo")
    from memsub.certification import assert_train_eval_disjoint
    with open("/artifacts/corpus-compactor-train/triplets.json") as f:
        rows = json.load(f)
    with open("/artifacts/corpus-fullrecipe/mixture-manifest.json") as f:
        mixture = json.load(f)
    with open(
            "/artifacts/corpus-fullrecipe/certification-holdout-clean-v1.json"
    ) as f:
        holdout = json.load(f)
    keep = {m["item_id"] for m in mixture["items"]}
    rows = [r for r in rows if r["item_id"] in keep]
    for path in sorted(glob.glob(
            "/artifacts/corpus-fullrecipe/rationales/*.state.json")):
        with open(path) as f:
            rows.extend(r for r in json.load(f)["rows"]
                        if r["item_id"] in keep)
    seen = set()
    uniq = []
    for r in rows:
        if r["item_id"] not in seen:
            seen.add(r["item_id"])
            uniq.append(r)
    if not seen <= keep:
        raise ValueError("merged triplets contain items outside the manifest")
    overlap_audit = assert_train_eval_disjoint(uniq, holdout["documents"])
    rng = random.Random(1234)
    rng.shuffle(uniq)
    counts = {}
    for r in uniq:
        counts[r["domain"]] = counts.get(r["domain"], 0) + 1
    mid, per_dom = [], {}
    for r in uniq:                       # first 1/8 per domain, shuffled order
        if per_dom.get(r["domain"], 0) < counts[r["domain"]] // 8:
            mid.append(r)
            per_dom[r["domain"]] = per_dom.get(r["domain"], 0) + 1
    with open("/artifacts/corpus-fullrecipe/triplets-full.json", "w") as f:
        json.dump(uniq, f)
    with open("/artifacts/corpus-fullrecipe/triplets-mid.json", "w") as f:
        json.dump(mid, f)
    blob = json.dumps([r["item_id"] for r in uniq]).encode()
    stats = {"full": len(uniq), "mid": len(mid), "per_domain": counts,
             "mixture_sha256": mixture["sha256"],
             "holdout_sha256": mixture["holdout_sha256"],
             "train_ids_sha256": hashlib.sha256(blob).hexdigest(),
             "overlap_audit": overlap_audit}
    with open("/artifacts/corpus-fullrecipe/train-mixture-stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    artifacts.commit()
    return stats


@app.local_entrypoint()
def sample():
    calls = [prep_slice.spawn(d, 0, N_SLICES, 50) for d in DOMAINS]
    for c in calls:
        print(json.dumps(c.get()))


@app.local_entrypoint()
def overlap_check():
    print(json.dumps(regen_traced_overlap.remote(), indent=2))


@app.local_entrypoint()
def launch():
    handles = [prep_slice.spawn(d, s, N_SLICES)
               for d in DOMAINS for s in range(N_SLICES)]
    print(f"spawned {len(handles)} rationale workers:",
          [h.object_id for h in handles])


@app.local_entrypoint()
def merge_entry():
    print(json.dumps(merge.remote(), indent=2))
