"""Multi-hop slice (GATE.md §5; spec §4.7 middle-of-spectrum).

Composes k=2 single-hop items from the SAME document into one question that
requires BOTH facts (options are answer pairs; correct iff both parts right).
Teacher filters mirror B.3: answerable with both chunks in context, not
answerable without. Labels use the same counterfactual protocol: y = answer
under compacted context (first chunk's window evicted) differs from answer
under both raw spans. Each question yields two gate rows: (q, evicted block)
and (q, survived block) — same schema as single-hop, evaluated separately.

Usage:
  modal run --detach modal-runners/modal-m3-multihop-slice-builder.py::build_slice
"""

import json

import modal

GPU = "H100"
PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
MAX_GAP_TOKENS = 1600      # both chunks + margins must fit one 4096 window
CHUNK = 1024

app = modal.App("memsub-m3-multihop")
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


def _compose(a: dict, b: dict) -> dict:
    """Pair two single-hop label rows into one 2-hop MCQ with pair options."""
    golds = (a["options"]["ABCD".index(a["gold"])],
             b["options"]["ABCD".index(b["gold"])])
    wrong_a = next(o for i, o in enumerate(a["options"]) if "ABCD"[i] != a["gold"])
    wrong_b = next(o for i, o in enumerate(b["options"]) if "ABCD"[i] != b["gold"])
    options = [f"{golds[0]} / {golds[1]}",          # gold pair
               f"{golds[0]} / {wrong_b}",           # half-right distractors
               f"{wrong_a} / {golds[1]}",
               f"{wrong_a} / {wrong_b}"]
    order = sorted(range(4), key=lambda i: hash((a["item_id"], i)) % 97)
    gold_letter = "ABCD"[order.index(0)]
    return {
        "question": (f"Answer BOTH parts about this document: "
                     f"(1) {a['question']} (2) {b['question']} "
                     f"Choose the option answering both, format 'answer1 / answer2'."),
        "options": [options[i] for i in order],
        "gold": gold_letter,
    }


@app.function(image=gpu_image, gpu=GPU, volumes=VOLUMES, timeout=14400,
              memory=32768)
def build_slice(target_items: int = 500) -> dict:
    import sys
    sys.path.insert(0, "/root/repo")
    from memsub.certification import eq_policy_v1
    from memsub.reference_config import build_runtime

    with open("/artifacts/corpus-gate-labels/all-labels.json") as f:
        rows = json.load(f)
    # candidate pairs: same doc, both raw-correct pointwise items, chunks
    # disjoint but close enough to share a 4096 window
    by_doc: dict[str, list[dict]] = {}
    for r in rows:
        if r["raw_correct"] and r["pointwise_heuristic"]:
            by_doc.setdefault(r["doc_id"], []).append(r)
    pairs = []
    for doc_id, items in by_doc.items():
        items = sorted(items, key=lambda r: r["chunk_rel_start"])
        for a, b in zip(items, items[1:]):
            gap = abs(a["chunk_start_abs"] - b["chunk_start_abs"]) \
                if "chunk_start_abs" in a else None
            pairs.append((a, b))
    print(f"candidate pairs: {len(pairs)}")

    texts = {}
    for domain in ("financial", "legal", "code", "literature"):
        with open(f"/artifacts/corpus/{domain}.jsonl") as f:
            for line in f:
                rec = json.loads(line)
                texts[rec["doc_id"]] = rec["text"]

    runtime = build_runtime(reference=True)
    tok = runtime.tokenizer
    out = []
    for a, b in pairs:
        if len(out) >= target_items:
            break
        ids = tok.encode(texts[a["doc_id"]], add_special_tokens=False)
        sa = int(a["item_id"].split("_")[-2])  # chunk_token_start encoded in id
        sb = int(b["item_id"].split("_")[-2])
        if sa > sb:
            (a, sa), (b, sb) = (b, sb), (a, sa)
        if sb - sa < CHUNK or sb - sa > CHUNK + MAX_GAP_TOKENS:
            continue
        ctx_start = max(0, sa - 256)
        ctx_ids = ids[ctx_start:ctx_start + 4096]
        if sb + CHUNK > ctx_start + len(ctx_ids):
            continue
        mh = _compose(a, b)
        both_raw = tok.decode(ids[sa:sa + CHUNK]) + "\n...\n" + \
            tok.decode(ids[sb:sb + CHUNK])
        # teacher filters (B.3 style)
        with_ctx = runtime.answer_letter(both_raw, mh["question"], mh["options"])
        if not eq_policy_v1(with_ctx, mh["gold"]):
            continue
        without = runtime.answer_letter("", mh["question"], mh["options"])
        if eq_policy_v1(without, mh["gold"]):
            continue
        # counterfactual label: evict a window covering chunk A only
        cache, _ = runtime.prefill(ctx_ids)
        cc = cache.clone_detached()
        rel_a = sa - ctx_start
        lo = max(4, rel_a)
        cc.evict_logical_range(lo, min(lo + CHUNK, len(ctx_ids)))
        pred_compact = runtime.answer_letter("", mh["question"], mh["options"],
                                             cache=cc)
        out.append({
            "pair": [a["item_id"], b["item_id"]], "doc_id": a["doc_id"],
            "domain": a["domain"], **mh,
            "pred_raw": with_ctx, "pred_compact": pred_compact,
            "y": int(not eq_policy_v1(pred_compact, with_ctx)),
            "evicted_block_gloss": a["chunk_gloss"],
            "survived_block_gloss": b["chunk_gloss"],
            "ctx_tail_gloss": tok.decode(ctx_ids[-128:])[:500],
            "compact_correct": int(eq_policy_v1(pred_compact, mh["gold"])),
        })
        if len(out) % 50 == 0:
            with open("/artifacts/corpus-gate-labels/multihop-slice.json", "w") as f:
                json.dump(out, f)
            artifacts.commit()
            print(f"multihop kept {len(out)}")
    with open("/artifacts/corpus-gate-labels/multihop-slice.json", "w") as f:
        json.dump(out, f)
    artifacts.commit()
    return {"kept": len(out), "positive_rate": sum(r["y"] for r in out) / max(len(out), 1)}
