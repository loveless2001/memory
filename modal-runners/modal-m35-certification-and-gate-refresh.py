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
def certify_arms(single_tag: str, iterative_tag: str, t_latents: int,
                 out_name: str = "summary", lever: str = "none",
                 docs_per_domain: int = 3) -> dict:
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
    if lever == "e1_sqrt_scale":
        for comp in (single, iterative):
            for _layer in comp.layers:
                for _m in list(_layer.cross) + list(_layer.selfattn):
                    _m.d_l = 16            # deployment scale for E1 instances
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
        if per_domain_done[domain] >= docs_per_domain:
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
    def gt13_pass(arm: str) -> bool:
        # The FULL certification bar (COMPACTOR.md GT13): beat matched-budget
        # eviction on KL AND stay within 0.02 of its accuracy delta. Every
        # candidate depth must clear the same predicate — KL alone would let
        # a depth with better KL but collapsed accuracy into the policy.
        ref = summary["eviction-matched"]
        return (summary[arm]["mean_kl"] < ref["mean_kl"]
                and summary[arm]["acc_delta"] >= ref["acc_delta"] - 0.02)

    # paired (per-document) bootstrap CIs vs the eviction arm — a mean
    # difference whose CI straddles zero is NOT a certification difference,
    # however the point estimates order (added after an n=12 run produced
    # unresolved verdicts on both aggregation axes).
    import numpy as np
    rng = np.random.default_rng(0)

    def paired_ci(arm: str, axis: str, key: str) -> dict:
        a = np.array([r[axis][key] for r in results["eviction-matched"]])
        b = np.array([r[axis][key] for r in results[arm]])
        diff = b - a
        if len(diff) < 2:
            return {"n": int(len(diff))}
        boots = np.array([rng.choice(diff, len(diff), replace=True).mean()
                          for _ in range(20000)])
        lo, hi = np.percentile(boots, [2.5, 97.5])
        return {"n": int(len(diff)), "mean_diff": float(diff.mean()),
                "ci95": [float(lo), float(hi)],
                "excludes_zero": bool(lo > 0 or hi < 0),
                "docs_favoring_arm": int((diff < 0).sum())}

    summary["paired_vs_eviction"] = {
        arm: {"mean_kl": paired_ci(arm, "aggregation_axis", "mean_kl"),
              "acc_delta": paired_ci(arm, "aggregation_axis", "accuracy_delta"),
              "lost_fact": paired_ci(arm, "pointwise_axis",
                                     "lost_fact_incident_rate")}
        for arm in ("compactor-d1", "compactor-d4")}
    summary["n_documents"] = len(results["eviction-matched"])
    summary["gt13_ship"] = gt13_pass("compactor-d1")
    # Certified depth = longest contiguous prefix of depths passing GT13;
    # depth 4 cannot certify past a failing depth 1 (recurrence stacks).
    max_depth = 0
    for depth, arm in ((1, "compactor-d1"), (4, "compactor-d4")):
        if not gt13_pass(arm):
            break
        max_depth = depth
    summary["gt15_max_certified_depth"] = max_depth

    # emit depth + policy version into the shipped checkpoints
    for tag, comp, depth in ((single_tag, single, 1),
                             (iterative_tag, iterative,
                              summary["gt15_max_certified_depth"])):
        comp.max_certified_depth = max(depth, 0)
        comp.save(f"/artifacts/compactor-checkpoints/{tag}/compactor.safetensors")
        summary[f"policy_version_{tag}"] = comp.policy_version()

    with open(f"/artifacts/compactor-certification/{out_name}.json", "w") as f:
        json.dump({"summary": summary, "reports": results}, f, indent=1,
                  default=float)
    artifacts.commit()
    return summary


@app.function(image=image, gpu=GPU, volumes=VOLUMES, timeout=43200,
              memory=32768)
def relabel_slice(single_tag: str, t_latents: int, domain: str,
                  slice_idx: int, n_slices: int,
                  out_base: str = "/artifacts/compactor-gate-labels",
                  lever: str = "none") -> dict:
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

    os.makedirs(f"{out_base}/{domain}", exist_ok=True)
    state_path = (f"{out_base}/{domain}/"
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
    if lever == "e1_sqrt_scale":
        for _layer in comp.layers:
            for _m in list(_layer.cross) + list(_layer.selfattn):
                _m.d_l = 16                # deployment scale for E1 instances
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


@app.function(image=image, gpu="L4", volumes=VOLUMES, timeout=14400,
              memory=65536, cpu=8)
def refresh_gate(labels_base: str = "/artifacts/compactor-gate-labels",
                 out_suffix: str = "still") -> dict:
    """Retrain the gate on compactor labels (GT16 + A2 decomposition redo).
    Embeddings are reused via item_id alignment (glosses unchanged)."""
    import glob
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch
    from memsub.gate import TrainConfig, end_to_end_lost_fact, make_splits, train_gate
    from memsub.gate.dual_encoder_expansion_gate import calibrate_temperature
    from memsub.gate.gate_evaluation_metrics import (
        auc_score, expected_calibration_error, operating_point, threshold_sweep)
    from memsub.gate.label_dataset_splits import GateDataset

    rows = []
    for path in sorted(glob.glob(
            f"{labels_base}/*/slice-*.state.json")):
        with open(path) as f:
            rows.extend(json.load(f)["rows"])
    emb = np.load("/artifacts/corpus-gate-labels/embeddings.npz")
    emb_row = {i: n for n, i in enumerate(emb["item_ids"])}
    rows = [r for r in rows if r["item_id"] in emb_row]
    idx = np.array([emb_row[r["item_id"]] for r in rows])
    gold_ok = np.array([r["pred_compact_still"].strip().upper()[:1]
                        == r["gold"].strip().upper()[:1] for r in rows])
    ds = GateDataset(
        item_id=np.array([r["item_id"] for r in rows]),
        doc_id=np.array([r["doc_id"] for r in rows]),
        domain=np.array([r["domain"] for r in rows]),
        fraction=np.array([r["fraction_still"] for r in rows], dtype=np.float32),
        y=np.array([r["y_still"] for r in rows]),
        overlap=np.array([r["overlap_still"] for r in rows], dtype=np.float32),
        evicted=np.array([r["evicted_still"] for r in rows]),
        pointwise=np.array([int(r["pointwise_heuristic"]) for r in rows]),
        raw_correct=np.array([int(r["raw_correct"]) for r in rows]),
        compact_correct=gold_ok.astype(int),
        q_emb=emb["q_emb"][idx].astype(np.float32),
        b_emb=emb["b_emb"][idx].astype(np.float32))
    splits = make_splits(ds, mode="document")
    test_idx = np.flatnonzero(splits["test"])
    cal_idx = np.flatnonzero(splits["cal"])
    out: dict = {"n_rows": len(ds),
                 "positive_rate": float(ds.y.mean())}

    def variant(kind):
        clone = ds.subset(np.ones(len(ds), dtype=bool))
        if kind == "features_only":
            clone.q_emb = np.zeros_like(ds.q_emb)
            clone.b_emb = np.zeros_like(ds.b_emb)
        elif kind == "embeddings_only":
            clone.fraction = np.zeros_like(ds.fraction)
            clone.overlap = np.zeros_like(ds.overlap)
            clone.evicted = np.zeros_like(ds.evicted)
            clone.domain = np.array(["none"] * len(ds))
        return clone

    ev_test = test_idx[ds.evicted[test_idx] == 1]
    out["a2_still"] = {}
    for kind in ("full", "features_only", "embeddings_only"):
        dvar = variant(kind) if kind != "full" else ds
        aucs = []
        for seed in (0, 1, 2):
            m = train_gate(dvar, splits["train"], TrainConfig(seed=seed),
                           device="cuda").cpu()
            calibrate_temperature(m, dvar, splits["cal"])
            aucs.append(auc_score(m.predict_proba(dvar, ev_test),
                                  ds.y[ev_test]))
            if kind == "full" and seed == 0:
                model = m
        out["a2_still"][kind] = {"evicted_auc_mean": float(np.mean(aucs)),
                                 "sd": float(np.std(aucs))}

    p_cal = model.predict_proba(ds, cal_idx)
    op = operating_point(threshold_sweep(ds, cal_idx, p_cal),
                         target_lost=M3_E2E["lost"],
                         max_expand_rate=M3_E2E["expand"])
    p_test = model.predict_proba(ds, test_idx)
    e2e = end_to_end_lost_fact(ds, test_idx, p_test >= op["threshold"])
    out["gt16"] = {
        "threshold": op["threshold"], **e2e,
        "ece": expected_calibration_error(p_test, ds.y[test_idx]),
        "m3_reference": M3_E2E,
        "pass": bool(
            e2e["lost_fact_rate_evicted_prior_correct"] <= M3_E2E["lost"]
            and e2e["expand_rate_all"] <= M3_E2E["expand"])}

    # Baselines under THIS policy (never/always/oracle/classify): the gate's
    # marginal value must be quoted against the compactor regime's own
    # never-expand, not M3's eviction-regime reference frame.
    from memsub.gate.gate_evaluation_metrics import baseline_decisions
    _, aux_logits = model.predict_logits(ds, test_idx)
    aux_p = 1 / (1 + np.exp(-aux_logits))
    out["gt16_baselines"] = {
        name: end_to_end_lost_fact(ds, test_idx, dec)
        for name, dec in baseline_decisions(ds, test_idx, aux_p).items()}
    never = out["gt16_baselines"]["never_expand"][
        "lost_fact_rate_evicted_prior_correct"]
    out["gt16_marginal_value"] = {
        "never_expand_this_policy": never,
        "gate_reduction_vs_never": 1 - e2e[
            "lost_fact_rate_evicted_prior_correct"] / max(never, 1e-9),
        "m3_eviction_reduction_reference": 1 - 0.146 / 0.520,
    }
    torch.save({"state_dict": model.state_dict(),
                "temperatures": model.temperatures,
                "threshold": op["threshold"]},
               f"/artifacts/gate-eval/gate-checkpoint-{out_suffix}.pt")
    with open(f"/artifacts/gate-eval/gate-refresh-{out_suffix}.json", "w") as f:
        json.dump(out, f, indent=1, default=float)
    artifacts.commit()
    return {k: out[k] for k in ("n_rows", "positive_rate", "a2_still", "gt16")}


@app.function(image=image, gpu="L4", volumes=VOLUMES, timeout=14400,
              memory=32768)
def wp2_eval() -> dict:
    """s1 set-scoring on the expanded multi-hop slice: GT17 + GT18."""
    import sys
    sys.path.insert(0, "/root/repo")
    import numpy as np
    import torch
    from memsub.compilers import Qwen3ShadowEmbedder
    from memsub.gate import DualEncoderExpansionGate, TrainConfig
    from memsub.gate.label_dataset_splits import GateDataset, _doc_bucket
    from memsub.gate.set_scoring_selector import SetScoringSelector, fit_tau_entry

    with open("/artifacts/corpus-gate-labels/multihop-slice.json") as f:
        rows = json.load(f)
    ck = torch.load("/artifacts/gate-eval/gate-checkpoint.pt",
                    weights_only=False)
    emb = Qwen3ShadowEmbedder(device="cuda", dtype="bfloat16")

    def batch(texts, bs=64):
        return np.concatenate([emb.embed(texts[i:i + bs])
                               for i in range(0, len(texts), bs)]).astype(np.float32)

    n = len(rows)
    q = batch([r["question"] + " || recent: " + r["ctx_tail_gloss"]
               for r in rows])
    b_ev = batch([r["evicted_block_gloss"] for r in rows])
    b_sv = batch([r["survived_block_gloss"] for r in rows])

    def gate_scores(bmat, evicted):
        ds = GateDataset(
            item_id=np.array([f"x{i}" for i in range(n)]),
            doc_id=np.array([r["doc_id"] for r in rows]),
            domain=np.array([r["domain"] for r in rows]),
            fraction=np.full(n, 0.25, dtype=np.float32),
            y=np.zeros(n, dtype=int),
            overlap=np.full(n, 1.0 if evicted else 0.0, dtype=np.float32),
            evicted=np.full(n, int(evicted)),
            pointwise=np.ones(n, dtype=int), raw_correct=np.ones(n, dtype=int),
            compact_correct=np.zeros(n, dtype=int), q_emb=q, b_emb=bmat)
        model = DualEncoderExpansionGate(q.shape[1], TrainConfig())
        model.load_state_dict(ck["state_dict"])
        model.temperatures = ck["temperatures"]
        return model.predict_proba(ds, np.arange(n))

    s_ev, s_sv = gate_scores(b_ev, True), gate_scores(b_sv, False)
    buckets = np.array([_doc_bucket(r["doc_id"]) for r in rows])
    train_m, test_m = buckets < 0.7, buckets >= 0.7

    scores = [[float(s_ev[i]), float(s_sv[i])] for i in range(n)]
    needed = [[bool(r["y"]), False] for r in rows]
    fit = fit_tau_entry([scores[i] for i in np.flatnonzero(train_m)],
                        [needed[i] for i in np.flatnonzero(train_m)],
                        target_recall=0.85)
    sel = SetScoringSelector(tau_entry=fit["tau_entry"])

    exp = hit = need = total = lost = q_expanded = 0
    for i in np.flatnonzero(test_m):
        dec = sel.decide(scores[i])
        for e, nd in zip(dec.expand_mask, needed[i]):
            need += nd
            hit += nd and e
            exp += e
            total += 1
        q_expanded += dec.entered
        if rows[i]["y"] and not dec.expand_mask[0]:
            lost += rows[i]["compact_correct"] == 0
    n_test = int(test_m.sum())
    oracle_rate = sum(sum(needed[i]) for i in np.flatnonzero(test_m)) / (2 * n_test)
    out = {
        "fit": fit, "n_test_questions": n_test,
        "recall": hit / max(need, 1),
        "expand_rate_blocks": exp / max(total, 1),
        "oracle_rate_blocks": oracle_rate,
        "expand_over_oracle": (exp / max(total, 1)) / max(oracle_rate, 1e-9),
        "lost_fact_rate": lost / max(sum(bool(rows[i]['y'])
                                         for i in np.flatnonzero(test_m)), 1),
        "m3_reference_expand_over_oracle": 2.33,
    }
    out["gt17_pass_s1"] = (out["expand_over_oracle"] <= 1.3
                           and out["lost_fact_rate"] <= 0.05
                           and out["recall"] >= 0.85)

    # ---- s2: query-conditioned joint head (brief: only if s1 misses) ------
    # Per-block logistic re-scorer trained on the slice's train split:
    # features = [gate score, cosine(q, b), gate-score margin within the
    # query's candidate set]. The margin term is the "joint" signal a
    # per-block gate cannot see.
    import torch as th
    feats, labels, qidx = [], [], []
    for i in range(n):
        margin = s_ev[i] - s_sv[i]
        for score, bmat, nd in ((s_ev[i], b_ev[i], bool(rows[i]["y"])),
                                (s_sv[i], b_sv[i], False)):
            cos = float(np.dot(q[i], bmat)
                        / (np.linalg.norm(q[i]) * np.linalg.norm(bmat) + 1e-9))
            feats.append([float(score), cos, float(margin)])
            labels.append(float(nd))
            qidx.append(i)
    feats = th.tensor(feats); labels = th.tensor(labels)
    tr_rows = th.tensor([bool(train_m[i]) for i in qidx])
    lin = th.nn.Linear(3, 1)
    opt2 = th.optim.AdamW(lin.parameters(), lr=0.05)
    for _ in range(500):
        opt2.zero_grad()
        loss = th.nn.functional.binary_cross_entropy_with_logits(
            lin(feats[tr_rows]).squeeze(-1), labels[tr_rows])
        loss.backward(); opt2.step()
    with th.no_grad():
        p2 = th.sigmoid(lin(feats).squeeze(-1)).numpy()
    p2_by_q = {}
    for k, i in enumerate(qidx):
        p2_by_q.setdefault(i, []).append(p2[k])
    fit2 = fit_tau_entry([p2_by_q[i] for i in np.flatnonzero(train_m)],
                         [needed[i] for i in np.flatnonzero(train_m)],
                         target_recall=0.85)
    sel2 = SetScoringSelector(tau_entry=fit2["tau_entry"])
    exp = hit = need = total = lost = 0
    for i in np.flatnonzero(test_m):
        dec = sel2.decide(p2_by_q[i])
        for e, nd in zip(dec.expand_mask, needed[i]):
            need += nd; hit += nd and e; exp += e; total += 1
        if rows[i]["y"] and not dec.expand_mask[0]:
            lost += rows[i]["compact_correct"] == 0
    out["s2"] = {
        "fit": fit2,
        "recall": hit / max(need, 1),
        "expand_rate_blocks": exp / max(total, 1),
        "expand_over_oracle": (exp / max(total, 1)) / max(oracle_rate, 1e-9),
        "lost_fact_rate": lost / max(sum(bool(rows[i]['y'])
                                         for i in np.flatnonzero(test_m)), 1),
    }
    out["gt17_pass"] = (out["s2"]["expand_over_oracle"] <= 1.3
                        and out["s2"]["lost_fact_rate"] <= 0.05
                        and out["s2"]["recall"] >= 0.85)
    with open("/artifacts/gate-eval/wp2-set-selector-eval.json", "w") as f:
        json.dump(out, f, indent=1, default=float)
    artifacts.commit()
    return out


@app.local_entrypoint()
def certify(single_tag: str, iterative_tag: str, t_latents: int = 1024,
            out_name: str = "summary", lever: str = "none",
            docs_per_domain: int = 3):
    print(json.dumps(certify_arms.remote(single_tag, iterative_tag, t_latents,
                                         out_name, lever, docs_per_domain),
                     indent=1, default=float))


@app.local_entrypoint()
def launch_relabel(single_tag: str, t_latents: int, slices_per_domain: int = 3,
                   out_base: str = "/artifacts/compactor-gate-labels",
                   lever: str = "none"):
    for d in DOMAINS:
        for s in range(slices_per_domain):
            relabel_slice.spawn(single_tag, t_latents, d, s,
                                slices_per_domain, out_base, lever)
    print("relabel fleet spawned")
