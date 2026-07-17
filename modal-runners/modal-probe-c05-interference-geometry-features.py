"""PROBE arm c0.5: interference-geometry features, corpus-only (no trial
forward pass through the base model). Per E2-sample item, over the
COMPACTED region [4, 3072) of its GT16-protocol context:

  regex candidates of the item's fact type (numbers / dates / code
  symbols / capitalized entities) -> siblings = candidate values with the
  same surface class as the gold answer, value != answer:
    n_siblings          count in compacted region
    n_exact_answer      exact answer occurrences in region
    sibling_density     siblings within +-1000 chars of the needle span
    nearest_ngram_sim   max char-trigram Jaccard(sibling, answer)
  shadow-embedding key distinctiveness (Qwen3-Embedding-0.6B on the
  64-token windows around the needle and its 8 nearest siblings):
    key_distinct        1 - max cos(needle window, sibling windows)
    mean_sibling_cos    mean cos over those windows

Writes /artifacts/probe/c05-features.state.json (resumable).

Usage:
  modal run --detach modal-runners/modal-probe-c05-interference-geometry-features.py --slice-idx 0 --n-slices 4
"""

import json
import re

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
CTX = 4096
RECENT_RAW = 1024
SINKS = 4

app = modal.App("memsub-probe-c05")
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
DOMAINS = ("financial", "legal", "code", "literature")

PATTERNS = {
    "number": r"\$?\d[\d,]*(?:\.\d+)?%?",
    "date": (r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})|(?:(?:January|February|"
             r"March|April|May|June|July|August|September|October|November|"
             r"December)\s+\d{1,2},?\s+\d{4})|(?:\b(?:19|20)\d{2}\b)"),
    "code symbol": r"[A-Za-z_][A-Za-z0-9_\.\:]{3,}",
    "name/entity": r"(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})",
    "common phrase": r"[A-Za-z]{4,}(?:\s+[A-Za-z]{4,}){0,3}",
}


def trigram_jaccard(a: str, b: str) -> float:
    ta = {a[i:i + 3] for i in range(max(len(a) - 2, 1))}
    tb = {b[i:i + 3] for i in range(max(len(b) - 2, 1))}
    return len(ta & tb) / max(len(ta | tb), 1)


@app.function(image=image, gpu="L4", volumes=VOLUMES, timeout=43200,
              memory=32768)
def extract_features(slice_idx: int, n_slices: int) -> dict:
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    from transformers import AutoTokenizer

    from memsub.compilers import Qwen3ShadowEmbedder

    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B-Instruct-2507")
    emb = Qwen3ShadowEmbedder(device="cuda", dtype="bfloat16")

    with open("/artifacts/probe/capture-manifest.json") as f:
        manifest = json.load(f)
    with open("/artifacts/preprobe/fact-types.state.json") as f:
        ftypes = json.load(f)["types"]
    items = [m for n, m in enumerate(
        sorted(manifest, key=lambda r: (r["domain"], r["doc_id"],
                                        r["item_id"])))
        if n % n_slices == slice_idx]

    needed = {m["doc_id"] for m in items}
    texts = {}
    for domain in DOMAINS:
        with open(f"/artifacts/corpus/{domain}.jsonl") as f:
            for line in f:
                rec = json.loads(line)
                if rec["doc_id"] in needed:
                    texts[rec["doc_id"]] = rec["text"]

    state_path = f"/artifacts/probe/c05-features-slice-{slice_idx:02d}.state.json"
    state = {"done": 0, "rows": []}
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)

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
        ctx_start = max(0, min(chunk_start - row["chunk_rel_start"],
                               len(ids) - CTX))
        ctx_ids = ids[ctx_start:ctx_start + CTX]
        chunk_rel = chunk_start - ctx_start

        region_ids = ctx_ids[SINKS:CTX - RECENT_RAW]
        region = tok.decode(region_ids)
        # needle char span inside the region (token-proportional estimate)
        lo_t = max(0, chunk_rel - SINKS)
        hi_t = min(len(region_ids), chunk_rel + 1024 - SINKS)
        lo_c = int(len(region) * lo_t / max(len(region_ids), 1))
        hi_c = int(len(region) * hi_t / max(len(region_ids), 1))

        ftype = ftypes.get(row["item_id"], "common phrase")
        ans = row["options"][ord(row["gold"].strip()[0]) - 65].strip()
        cands = [(m.group(0), m.start()) for m in
                 re.finditer(PATTERNS[ftype], region)]
        sibs = [(v, p) for v, p in cands if v.strip() != ans]
        n_exact = sum(1 for v, _ in cands if v.strip() == ans)
        near = [(v, p) for v, p in sibs
                if lo_c - 1000 <= p <= hi_c + 1000]
        ngram_sims = sorted((trigram_jaccard(v, ans) for v, _ in sibs),
                            reverse=True)

        # embedding windows: needle window + up to 8 nearest siblings
        mid = (lo_c + hi_c) // 2
        # locate answer inside needle span if possible for a tighter window
        apos = region.find(ans, lo_c, hi_c)
        center = apos if apos >= 0 else mid
        win = region[max(0, center - 200):center + 200]
        sib_sorted = sorted(near or sibs,
                            key=lambda vp: abs(vp[1] - center))[:8]
        key_distinct, mean_cos = 1.0, 0.0
        if sib_sorted and win.strip():
            wins = [win] + [region[max(0, p - 200):p + 200]
                            for _, p in sib_sorted]
            vecs = emb.embed(wins)
            cos = vecs[1:] @ vecs[0]
            key_distinct = float(1 - cos.max())
            mean_cos = float(cos.mean())

        state["rows"].append({
            "item_id": row["item_id"], "y": row["y"],
            "n_siblings": len(sibs), "n_exact_answer": n_exact,
            "sibling_density": len(near),
            "nearest_ngram_sim": round(ngram_sims[0], 4) if ngram_sims else 0.0,
            "top5_ngram_sim_mean": round(float(np.mean(ngram_sims[:5])), 4)
            if ngram_sims else 0.0,
            "key_distinct": round(key_distinct, 4),
            "mean_sibling_cos": round(mean_cos, 4),
            "ans_found_in_region": int(apos >= 0)})
        state["done"] = n + 1
        if (n + 1) % 500 == 0 or n + 1 == len(items):
            with open(state_path, "w") as f:
                json.dump(state, f)
            artifacts.commit()
            print(f"c05[{slice_idx}] {n + 1}/{len(items)}", flush=True)
    with open(state_path, "w") as f:
        json.dump(state, f)
    artifacts.commit()
    return {"slice": slice_idx, "rows": len(state["rows"])}


@app.local_entrypoint()
def main(slice_idx: int, n_slices: int):
    print(extract_features.remote(slice_idx, n_slices))
