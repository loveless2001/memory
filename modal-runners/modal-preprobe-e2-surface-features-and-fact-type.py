"""PREPROBE E2 feature extraction (PREPROBE.md §E2).

Two functions, both writing to memsub-artifacts:/preprobe/:

  surface_pass   CPU. One sweep over the full B.3 corpus with the Qwen
                 tokenizer: (a) corpus token-frequency table, (b) per-item
                 surface features for ALL 98,355 relabeled items —
                 span_len, answer char-offset ratio within the source span,
                 answer-token min/mean corpus log10-frequency.
                 Corpus + tokenizer only; no model.
  fact_type_pass GPU (L4). Cheap prompted pass with Qwen3-4B: classify each
                 E2-sample item's gold answer into {number, name/entity,
                 code symbol, date, common phrase} by letter-argmax
                 (single forward, greedy-deterministic).
                 Reads /artifacts/preprobe/e2-sample-items.json.

Usage:
  modal run --detach modal-runners/modal-preprobe-e2-surface-features-and-fact-type.py::surface_pass
  modal run --detach modal-runners/modal-preprobe-e2-surface-features-and-fact-type.py::fact_type_pass
"""

import json

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
app = modal.App("memsub-preprobe-e2")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)
hf_cache = modal.Volume.from_name("memsub-hf-cache", create_if_missing=True)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/root/.cache/huggingface": hf_cache, "/artifacts": artifacts}
DOMAINS = ("financial", "legal", "code", "literature")
SPAN = 1024  # MCQ source-chunk length in tokens (B.3 pipeline)


def _load_rows():
    import glob
    rows = []
    for path in sorted(glob.glob(
            "/artifacts/compactor-gate-labels/*/slice-*.state.json")):
        with open(path) as f:
            rows.extend(json.JSONDecoder(strict=False).decode(f.read())["rows"])
    return rows


@app.function(image=image, volumes=VOLUMES, timeout=14400, memory=32768,
              cpu=16)
def surface_pass() -> dict:
    import math

    import numpy as np
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B-Instruct-2507")
    rows = _load_rows()
    by_doc: dict[str, list[dict]] = {}
    for r in rows:
        by_doc.setdefault(r["doc_id"], []).append(r)

    counts = np.zeros(len(tok), dtype=np.int64)
    feats: dict[str, dict] = {}

    def flush(batch_ids, batch_texts):
        nonlocal counts
        encs = tok(batch_texts, add_special_tokens=False)["input_ids"]
        for doc_id, ids in zip(batch_ids, encs):
            arr = np.asarray(ids, dtype=np.int64)
            counts += np.bincount(arr, minlength=len(tok))
            for r in by_doc.get(doc_id, ()):
                chunk_abs = int(r["item_id"].split("_")[-2])
                span_ids = ids[chunk_abs:chunk_abs + SPAN]
                span_text = tok.decode(span_ids)
                ans = r["options"][ord(r["gold"].strip().upper()[0]) - 65].strip()
                pos = span_text.find(ans)
                feats[r["item_id"]] = {
                    "span_len": len(span_ids),
                    "ans_found_in_span": int(pos >= 0),
                    "ans_rel_offset": (round(pos / max(len(span_text), 1), 4)
                                       if pos >= 0 else None),
                }

    total_docs = 0
    for domain in DOMAINS:
        batch_ids, batch_texts = [], []
        with open(f"/artifacts/corpus/{domain}.jsonl") as f:
            for line in f:
                rec = json.loads(line)
                batch_ids.append(rec["doc_id"])
                batch_texts.append(rec["text"])
                if len(batch_texts) == 32:
                    flush(batch_ids, batch_texts)
                    total_docs += 32
                    batch_ids, batch_texts = [], []
                    if total_docs % 3200 == 0:
                        print(domain, total_docs, flush=True)
        if batch_texts:
            flush(batch_ids, batch_texts)
            total_docs += len(batch_texts)

    total = int(counts.sum())
    # answer-token rarity for every item (log10 relative frequency, +1 smooth)
    logf = np.log10((counts + 1) / (total + len(tok)))
    for r in rows:
        ans = r["options"][ord(r["gold"].strip().upper()[0]) - 65].strip()
        ids = tok.encode(ans, add_special_tokens=False)
        f_vals = [float(logf[i]) for i in ids] or [0.0]
        feats[r["item_id"]].update(
            ans_n_tokens=len(ids),
            rarity_min=round(min(f_vals), 4),
            rarity_mean=round(sum(f_vals) / len(f_vals), 4))

    import os
    os.makedirs("/artifacts/preprobe", exist_ok=True)
    np.savez_compressed("/artifacts/preprobe/corpus-token-freqs.npz",
                        counts=counts, total=total)
    with open("/artifacts/preprobe/surface-features.json", "w") as f:
        json.dump(feats, f)
    artifacts.commit()
    found = sum(1 for v in feats.values() if v["ans_found_in_span"])
    print(f"docs={total_docs} tokens={total} items={len(feats)} "
          f"ans_found={found}/{len(feats)}")
    return {"docs": total_docs, "corpus_tokens": total, "items": len(feats),
            "ans_found_frac": found / len(feats)}


FACT_TYPES = {"A": "number", "B": "name/entity", "C": "code symbol",
              "D": "date", "E": "common phrase"}
PROMPT = """Classify the TYPE of this quiz answer.

Question: {q}
Answer: {a}

Types:
A. number or quantity
B. name or entity (person, company, place, organization)
C. code symbol or identifier (variable, function, path, hex, technical token)
D. date or time
E. common phrase (ordinary words, none of the above)

Answer with a single letter.
Answer:"""


@app.function(image=image, gpu="L4", volumes=VOLUMES, timeout=14400,
              memory=32768)
def fact_type_pass() -> dict:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B-Instruct-2507")
    model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen3-4B-Instruct-2507", torch_dtype=torch.bfloat16,
        attn_implementation="sdpa").to("cuda").eval()
    with open("/artifacts/preprobe/e2-sample-items.json") as f:
        items = json.load(f)
    letter_ids = [tok.encode(" " + l, add_special_tokens=False)[-1]
                  for l in FACT_TYPES]

    out_path = "/artifacts/preprobe/fact-types.state.json"
    import os
    state = {"done": 0, "types": {}}
    if os.path.exists(out_path):
        with open(out_path) as f:
            state = json.load(f)

    with torch.inference_mode():
        for n, it in enumerate(items):
            if n < state["done"]:
                continue
            prompt = PROMPT.format(q=it["question"][:600], a=it["answer"][:200])
            ids = tok.encode(prompt, add_special_tokens=False)
            logits = model(input_ids=torch.tensor([ids], device="cuda")
                           ).logits[0, -1]
            scores = [float(logits[i]) for i in letter_ids]
            letter = list(FACT_TYPES)[scores.index(max(scores))]
            state["types"][it["item_id"]] = FACT_TYPES[letter]
            state["done"] = n + 1
            if (n + 1) % 1000 == 0 or n + 1 == len(items):
                with open(out_path, "w") as f:
                    json.dump(state, f)
                artifacts.commit()
                print(f"{n + 1}/{len(items)}", flush=True)
    return {"classified": len(state["types"])}
