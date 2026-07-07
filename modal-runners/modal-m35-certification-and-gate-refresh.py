"""M3.5 certification + gate refresh + WP2 evaluation (COMPACTOR.md §2.4-§3).

Functions (run in order once training checkpoints exist):
  certify_arms      GT13/GT14/GT15 — compactor vs matched-budget eviction,
                    depth arms {1,4}; emits max_certified_depth + policy id
  relabel_slice     §17.5 counterfactual labels with the compactor as C
                    (deployment-shaped: old prefix compacted, recent 25% raw)
  refresh_gate      retrain + A2 decomposition x 3 seeds + recalibration +
                    GT16 end-to-end vs the M3 operating point
  wp2_eval          s1 set-scoring on the 2,000-item multi-hop slice
                    (GT17) + single-hop no-regression (GT18)
"""

import json

import modal

GPU = "H100"
PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
CTX = 4096
RECENT_RAW = 1024          # deployment-shaped: recent 25% stays exact
M3_TAU = 0.4879339294253414
M3_E2E = {"lost": 0.146, "expand": 0.168}

app = modal.App("memsub-m35-eval")
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


def _load_compactor(tag, config, device):
    import sys
    sys.path.insert(0, "/root/repo")
    from memsub.compactor import StillAmortizedKVCompactor
    return StillAmortizedKVCompactor.load(
        f"/artifacts/compactor-checkpoints/{tag}/compactor.safetensors",
        config, device=device)


@app.function(image=image, gpu=GPU, volumes=VOLUMES, timeout=43200,
              memory=65536)
def certify_arms(single_tag: str, iterative_tag: str, t_latents: int) -> dict:
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    import torch
    from memsub.certification import McqItem, OfflineCertificationHarness, PilotMcqPipeline
    from memsub.compactor.still_amortized_kv_compactor import compact_prefix_keep_recent
    from memsub.reference_config import build_runtime

    runtime = build_runtime(reference=True)
    single = _load_compactor(single_tag, runtime.model.config,
                             runtime.device).to(runtime.model.dtype)
    iterative = _load_compactor(iterative_tag, runtime.model.config,
                                runtime.device).to(runtime.model.dtype)
    harness = OfflineCertificationHarness(runtime)
    tok = runtime.tokenizer
    os.makedirs("/artifacts/compactor-certification", exist_ok=True)

    # matched budget: compactor keeps 4 + t + RECENT_RAW slots of CTX;
    # the eviction arm keeps the same count (sinks + recent-most slots)
    keep = 4 + t_latents + RECENT_RAW
    evict_n = CTX - keep

    def compactor_fn(depth):
        def fn(cache):
            with torch.inference_mode():
                comp = single if depth == 1 else iterative
                return compact_prefix_keep_recent(comp, cache, RECENT_RAW,
                                                  depth=depth)
        return fn

    arms = {"eviction-matched": dict(evict_logical_range=(4, 4 + evict_n)),
            "compactor-d1": dict(compaction_fn=compactor_fn(1),
                                 policy_version_override=single.policy_version()),
            "compactor-d4": dict(compaction_fn=compactor_fn(4),
                                 policy_version_override=iterative.policy_version()),
            "control-0": dict(evict_logical_range=(4, 4))}

    items = []
    with open("/artifacts/corpus-mcq-full/all-items.json") as f:
        raw_items = json.load(f)
    texts = {}
    for domain in DOMAINS:
        with open(f"/artifacts/corpus/{domain}.jsonl") as f:
            for line in f:
                rec = json.loads(line)
                texts[rec["doc_id"]] = rec["text"]

    by_doc: dict[str, list] = {}
    for d in raw_items:
        by_doc.setdefault(d["doc_id"], []).append(McqItem(**d))

    results: dict = {a: [] for a in arms}
    per_domain_done = {d: 0 for d in DOMAINS}
    for doc_id, doc_items in by_doc.items():
        domain = doc_id.split("/")[0]
        if per_domain_done[domain] >= 3:
            continue
        anchor = doc_items[0]
        ids = tok.encode(texts[doc_id], add_special_tokens=False)
        ctx_start = max(0, min(anchor.chunk_token_start - 512, len(ids) - CTX))
        ctx_ids = ids[ctx_start:ctx_start + CTX]
        if len(ctx_ids) < CTX:
            continue
        # needles: items whose chunk sits in the COMPACTED region (i.e. not
        # in the recent raw window and not in sinks)
        needles = [i for i in doc_items
                   if 4 <= i.chunk_token_start - ctx_start < CTX - RECENT_RAW - 1024][:8]
        if not needles:
            continue
        aggs = [i for i in doc_items if i not in needles][:8]
        for arm, kw in arms.items():
            rep = harness.certify(
                context_text=tok.decode(ctx_ids),
                evict_logical_range=kw.get("evict_logical_range", (4, 4)),
                mcq_items=aggs, needle_items=needles,
                compaction_fn=kw.get("compaction_fn"),
                policy_version_override=kw.get("policy_version_override"),
                protocol_notes={"arm": arm, "matched_keep_slots": keep})
            results[arm].append(rep.to_dict())
        per_domain_done[domain] += 1
        print(doc_id, {a: results[a][-1]["aggregation_axis"]["mean_kl"]
                       for a in arms})

    def agg(arm, key_path):
        vals = [r for r in results[arm]]
        a, k = key_path
        return sum(r[a][k] for r in vals) / max(len(vals), 1)

    summary = {
        arm: {"mean_kl": agg(arm, ("aggregation_axis", "mean_kl")),
              "acc_delta": agg(arm, ("aggregation_axis", "accuracy_delta")),
              "lost_fact": agg(arm, ("pointwise_axis", "lost_fact_incident_rate")),
              "lost_prior": agg(arm, ("pointwise_axis",
                                      "lost_fact_rate_given_prior_correct"))}
        for arm in arms}
    summary["gt13_ship"] = (
        summary["compactor-d1"]["mean_kl"] < summary["eviction-matched"]["mean_kl"]
        and summary["compactor-d1"]["acc_delta"]
        >= summary["eviction-matched"]["acc_delta"] - 0.02)
    depth_ok = [1] if summary["gt13_ship"] else []
    if summary["compactor-d4"]["mean_kl"] < summary["eviction-matched"]["mean_kl"]:
        depth_ok.append(4)
    summary["gt15_max_certified_depth"] = max(depth_ok, default=0)

    # emit depth + policy version into the shipped checkpoints
    for tag, comp, depth in ((single_tag, single, 1),
                             (iterative_tag, iterative,
                              summary["gt15_max_certified_depth"])):
        comp.max_certified_depth = max(depth, 0)
        comp.save(f"/artifacts/compactor-checkpoints/{tag}/compactor.safetensors")
        summary[f"policy_version_{tag}"] = comp.policy_version()

    with open("/artifacts/compactor-certification/summary.json", "w") as f:
        json.dump({"summary": summary, "reports": results}, f, indent=1,
                  default=float)
    artifacts.commit()
    return summary


@app.function(image=image, gpu=GPU, volumes=VOLUMES, timeout=43200,
              memory=32768)
def relabel_slice(single_tag: str, t_latents: int, domain: str,
                  slice_idx: int, n_slices: int) -> dict:
    """§17.5 counterfactual labels with the compactor as C. Deployment-shaped
    context: old prefix compacted to t latents, recent 25% raw. Items whose
    chunk lies in the raw window are natural y=0 rows."""
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    import torch
    from memsub.certification import McqItem, eq_policy_v1
    from memsub.compactor.still_amortized_kv_compactor import compact_prefix_keep_recent
    from memsub.reference_config import build_runtime

    os.makedirs(f"/artifacts/compactor-gate-labels/{domain}", exist_ok=True)
    state_path = (f"/artifacts/compactor-gate-labels/{domain}/"
                  f"slice-{slice_idx:02d}.state.json")
    state = {"done": 0, "rows": []}
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)

    with open("/artifacts/corpus-gate-labels/all-labels.json") as f:
        base_rows = [r for r in json.load(f) if r["domain"] == domain]
    base_rows = [r for n, r in enumerate(sorted(base_rows,
                                                key=lambda r: r["doc_id"]))
                 if n % n_slices == slice_idx]
    texts = {}
    with open(f"/artifacts/corpus/{domain}.jsonl") as f:
        for line in f:
            rec = json.loads(line)
            texts[rec["doc_id"]] = rec["text"]

    runtime = build_runtime(reference=True)
    comp = _load_compactor(single_tag, runtime.model.config,
                           runtime.device).to(runtime.model.dtype)
    tok = runtime.tokenizer
    doc_cache: dict[str, list[int]] = {}
    reduction = 1 - (4 + t_latents + RECENT_RAW) / CTX
    for n, row in enumerate(base_rows):
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
        new = dict(row)
        new["pred_compact_still"] = pred_c
        new["y_still"] = int(not eq_policy_v1(pred_c, row["pred_raw"]))
        new["overlap_still"] = round(ov, 4)
        new["evicted_still"] = int(ov > 0.5)
        new["fraction_still"] = round(reduction, 4)
        state["rows"].append(new)
        state["done"] = n + 1
        if (n + 1) % 200 == 0 or n + 1 == len(base_rows):
            with open(state_path, "w") as f:
                json.dump(state, f)
            artifacts.commit()
            print(f"{domain}[{slice_idx}] {n + 1}/{len(base_rows)}")
    with open(state_path, "w") as f:
        json.dump(state, f)
    artifacts.commit()
    return {"domain": domain, "slice": slice_idx, "rows": len(state["rows"])}


@app.local_entrypoint()
def launch_relabel(single_tag: str, t_latents: int, slices_per_domain: int = 3):
    for d in DOMAINS:
        for s in range(slices_per_domain):
            relabel_slice.spawn(single_tag, t_latents, d, s, slices_per_domain)
    print("relabel fleet spawned")
