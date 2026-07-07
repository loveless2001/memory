"""B.3 corpus pipeline on Modal (spec B.3; BUILD.md data step, human-triggered).

Assembles a real 4-domain long-document corpus into the memsub-artifacts
volume, then runs the pilot MCQ pipeline over it in parallel (one GPU worker
per domain) and certifies eviction per domain (spec 13.4).

Domains (all ungated, parquet-readable):
  financial   eloukas/edgar-corpus (SEC 10-K filings, parquet branch)
  legal       HFforLegal/case-law (US court opinions)
  code        codeparrot/github-code-clean (permissive-license source files)
  literature  sedthh/gutenberg_english (books)

Usage:
  modal run modal-runners/modal-b3-corpus-pipeline.py::assemble_corpus
  modal run modal-runners/modal-b3-corpus-pipeline.py::generate_and_certify
"""

import json
import subprocess

import modal

GPU = "H100"
PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]

app = modal.App("memsub-b3-corpus")

cpu_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("pyarrow>=17", "huggingface_hub>=0.34")
)
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

# Shards are discovered from the hub (some datasets hash-suffix their file
# names); n_shards caps how many parquet files are read per domain — sized so
# a full assembly lands near the spec's ~1B total tokens.
SOURCES = {
    "financial": {"repo": "eloukas/edgar-corpus", "revision": "refs/convert/parquet",
                  "prefix": "full/partial-train/", "n_shards": 16},
    "legal": {"repo": "HFforLegal/case-law", "revision": "refs/convert/parquet",
              "prefix": "default/partial-us/", "n_shards": 10},
    "code": {"repo": "codeparrot/github-code-clean", "revision": None,
             "prefix": "data/train-", "n_shards": 32},
    "literature": {"repo": "sedthh/gutenberg_english", "revision": None,
                   "prefix": "data/train-", "n_shards": 12},
}


def _shard_paths(api, spec) -> list[str]:
    files = api.list_repo_files(spec["repo"], repo_type="dataset",
                                revision=spec["revision"])
    rev = f"@{spec['revision']}" if spec["revision"] else ""
    return [f"datasets/{spec['repo']}{rev}/{f}"
            for f in sorted(files)
            if f.startswith(spec["prefix"]) and f.endswith(".parquet")
            ][:spec["n_shards"]]
MIN_CHARS = 24_000     # ~6k tokens: docs must dwarf the 1k-token chunk size
MAX_CHARS = 200_000    # bound memory per doc
DOCS_PER_DOMAIN = 2000


def _extract(domain: str, row: dict):
    if domain == "financial":
        parts = [v for k, v in sorted(row.items())
                 if k.startswith("section_") and isinstance(v, str)]
        return "\n\n".join(p for p in parts if p)
    if domain == "legal":
        return row.get("document")
    if domain == "code":
        return row.get("code")
    return row.get("TEXT")


@app.function(image=cpu_image, volumes={"/artifacts": artifacts}, timeout=7200,
              memory=16384)
def assemble_corpus(docs_per_domain: int = DOCS_PER_DOMAIN) -> dict:
    import os
    import pyarrow.parquet as pq_mod
    from huggingface_hub import HfApi, HfFileSystem

    fs = HfFileSystem()
    api = HfApi()
    os.makedirs("/artifacts/corpus", exist_ok=True)
    manifest = {}
    for domain, spec in SOURCES.items():
        kept, total_chars = 0, 0
        out_path = f"/artifacts/corpus/{domain}.jsonl"
        with open(out_path, "w") as out:
            for path in _shard_paths(api, spec):
                if kept >= docs_per_domain:
                    break
                try:
                    with fs.open(path, "rb") as f:
                        table = pq_mod.ParquetFile(f)
                        for batch in table.iter_batches(batch_size=256):
                            for row in batch.to_pylist():
                                text = _extract(domain, row)
                                if not text or len(text) < MIN_CHARS:
                                    continue
                                text = text[:MAX_CHARS]
                                out.write(json.dumps({
                                    "doc_id": f"{domain}/{kept:05d}",
                                    "domain": domain,
                                    "source": path.split("@")[0],
                                    "n_chars": len(text),
                                    "text": text}) + "\n")
                                kept += 1
                                total_chars += len(text)
                                if kept >= docs_per_domain:
                                    break
                            if kept >= docs_per_domain:
                                break
                except Exception as exc:  # missing shard index etc.
                    print(f"{domain}: shard {path} skipped: {exc}")
        manifest[domain] = {"docs": kept, "chars": total_chars,
                            "est_tokens": total_chars // 4}
        print(domain, manifest[domain])
    with open("/artifacts/corpus/manifest.json", "w") as f:
        json.dump(manifest, f, indent=1)
    artifacts.commit()
    return manifest


@app.function(image=gpu_image, gpu=GPU, volumes=VOLUMES, timeout=14400)
def generate_domain_items(domain: str, target_items: int) -> dict:
    """One GPU worker: MCQ items (filters a+b) over one domain's corpus."""
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    from memsub.certification import PilotMcqPipeline
    from memsub.reference_config import build_runtime

    os.makedirs("/artifacts/corpus-mcq", exist_ok=True)
    docs = {}
    with open(f"/artifacts/corpus/{domain}.jsonl") as f:
        for line in f:
            rec = json.loads(line)
            docs[rec["doc_id"]] = rec["text"]
    runtime = build_runtime(reference=True)
    pipeline = PilotMcqPipeline(runtime, chunk_tokens=1024, seed=hash(domain) % 1000)
    items = pipeline.generate(docs, target_items=target_items, per_doc=1)
    PilotMcqPipeline.save(items, f"/artifacts/corpus-mcq/{domain}.json")
    artifacts.commit()
    hf_cache.commit()
    return {"domain": domain, "kept": len(items)}


@app.function(image=gpu_image, gpu=GPU, volumes=VOLUMES, timeout=43200,
              memory=32768)
def generate_domain_slice(domain: str, slice_idx: int, n_slices: int,
                          target_items: int, pass_idx: int = 0) -> dict:
    """Full-scale worker: one slice of one domain's docs, resume-safe.

    Progress (group cursor + kept items) persists to the volume after every
    doc group, so a preempted/restarted worker resumes instead of redoing or
    duplicating work."""
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    from memsub.certification import McqItem, PilotMcqPipeline
    from memsub.reference_config import build_runtime

    os.makedirs(f"/artifacts/corpus-mcq-full/{domain}", exist_ok=True)
    tag = f"-p{pass_idx}" if pass_idx else ""
    state_path = (f"/artifacts/corpus-mcq-full/{domain}/"
                  f"slice-{slice_idx:02d}{tag}.state.json")
    state = {"next_group": 0, "items": []}
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)

    doc_list = []
    with open(f"/artifacts/corpus/{domain}.jsonl") as f:
        for n, line in enumerate(f):
            if n % n_slices == slice_idx:
                rec = json.loads(line)
                doc_list.append((rec["doc_id"], rec["text"]))

    runtime = build_runtime(reference=True)
    GROUP_DOCS = 100
    groups = [doc_list[i:i + GROUP_DOCS] for i in range(0, len(doc_list), GROUP_DOCS)]
    for g in range(state["next_group"], len(groups)):
        if len(state["items"]) >= target_items:
            break
        pipeline = PilotMcqPipeline(runtime, chunk_tokens=1024,
                                    seed=(hash(domain) + pass_idx * 7_777_777
                                          + slice_idx * 1000 + g) % 10**6)
        remaining = target_items - len(state["items"])
        got = pipeline.generate(dict(groups[g]),
                                target_items=min(remaining, 4 * GROUP_DOCS),
                                per_doc=4)
        state["items"].extend(i.__dict__ for i in got)
        state["next_group"] = g + 1
        with open(state_path, "w") as f:
            json.dump(state, f)
        artifacts.commit()
        print(f"{domain}[{slice_idx}] group {g + 1}/{len(groups)}: "
              f"{len(state['items'])}/{target_items} kept")
    return {"domain": domain, "slice": slice_idx, "kept": len(state["items"])}


@app.function(image=cpu_image, volumes={"/artifacts": artifacts}, timeout=3600)
def merge_full_items() -> dict:
    import glob
    import os
    counts, merged = {}, []
    for path in sorted(glob.glob("/artifacts/corpus-mcq-full/*/slice-*.state.json")):
        domain = path.split("/")[-2]
        with open(path) as f:
            items = json.load(f)["items"]
        counts[domain] = counts.get(domain, 0) + len(items)
        merged.extend(items)
    os.makedirs("/artifacts/corpus-mcq-full", exist_ok=True)
    with open("/artifacts/corpus-mcq-full/all-items.json", "w") as f:
        json.dump(merged, f)
    with open("/artifacts/corpus-mcq-full/counts.json", "w") as f:
        json.dump(counts, f, indent=1)
    artifacts.commit()
    return {"total": len(merged), **counts}


@app.function(image=gpu_image, gpu=GPU, volumes=VOLUMES, timeout=14400,
              memory=32768)
def certify_domain(domain: str, evict_fraction: float = 0.4,
                   contexts: int = 3, use_full_set: bool = False) -> list[dict]:
    """Offline certification (spec 13.4) over sampled contexts of one domain,
    using that domain's verified MCQ items as probes. use_full_set draws
    probes from the merged full-scale item set instead of the 2k test set."""
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    from memsub.certification import McqItem, OfflineCertificationHarness, PilotMcqPipeline
    from memsub.reference_config import build_runtime

    out_dir = "/artifacts/corpus-certification" + ("-full" if use_full_set else "")
    os.makedirs(out_dir, exist_ok=True)
    if use_full_set:
        with open("/artifacts/corpus-mcq-full/all-items.json") as f:
            items = [McqItem(**d) for d in json.load(f)
                     if d["doc_id"].startswith(domain + "/")]
    else:
        items = PilotMcqPipeline.load(f"/artifacts/corpus-mcq/{domain}.json")
    texts = {}
    with open(f"/artifacts/corpus/{domain}.jsonl") as f:
        for line in f:
            rec = json.loads(line)
            texts[rec["doc_id"]] = rec["text"]
    runtime = build_runtime(reference=True)
    harness = OfflineCertificationHarness(runtime)
    tok = runtime.tokenizer
    by_doc = {}
    for it in items:
        by_doc.setdefault(it.doc_id, []).append(it)

    reports = []
    for doc_id, doc_items in list(by_doc.items()):
        if len(reports) >= contexts:
            break
        anchor = doc_items[0]
        ids = tok.encode(texts[doc_id], add_special_tokens=False)
        ctx_start = max(0, anchor.chunk_token_start - 1024)
        ctx_ids = ids[ctx_start:ctx_start + 4096]
        span = int(len(ctx_ids) * evict_fraction)
        lo = max(4, min(anchor.chunk_token_start - ctx_start, len(ctx_ids) - span))
        needles = [i for i in doc_items
                   if lo <= i.chunk_token_start - ctx_start < lo + span] or [anchor]
        aggs = [i for i in doc_items if i not in needles][:8]
        report = harness.certify(
            context_text=tok.decode(ctx_ids),
            evict_logical_range=(lo, lo + span),
            mcq_items=aggs, needle_items=needles[:8])
        reports.append(report.to_dict())
    with open(f"{out_dir}/{domain}-evict{evict_fraction:.2f}.json", "w") as f:
        json.dump(reports, f, indent=1)
    artifacts.commit()
    return reports


@app.local_entrypoint()
def generate_and_certify(target_items: int = 2000):
    per_domain = target_items // len(SOURCES)
    gen = list(generate_domain_items.starmap(
        [(d, per_domain) for d in SOURCES]))
    print("generation:", gen)
    certs = list(certify_domain.map(list(SOURCES)))
    for domain_reports in certs:
        for r in domain_reports:
            print(r["certification_id"],
                  "kl=", r["aggregation_axis"]["mean_kl"],
                  "lost=", r["pointwise_axis"]["lost_fact_incident_rate"])


@app.local_entrypoint()
def full_run_launch(target_items: int = 100000, slices_per_domain: int = 8):
    """Fire-and-forget launcher for the full-scale run (use with --detach).
    Workers persist progress to the volume; finalize separately."""
    per_slice = target_items // (len(SOURCES) * slices_per_domain)
    handles = []
    for domain in SOURCES:
        for s in range(slices_per_domain):
            handles.append(generate_domain_slice.spawn(
                domain, s, slices_per_domain, per_slice))
    print(f"spawned {len(handles)} workers, {per_slice} items each")
    for h in handles:
        print(h.object_id)


@app.local_entrypoint()
def top_up_launch(target_total: int = 100000, pass_idx: int = 1):
    """Second-pass workers (fresh chunk seeds) sized to each domain's
    shortfall vs target_total/4. Use with --detach."""
    import math
    counts = merge_full_items.remote()
    per_domain_target = target_total // len(SOURCES)
    handles = []
    for domain in SOURCES:
        shortfall = per_domain_target - counts.get(domain, 0)
        if shortfall <= 0:
            print(f"{domain}: complete ({counts.get(domain)})")
            continue
        n = min(8, math.ceil(shortfall / 2600))  # ~2600 kept/worker fits timeout
        per_slice = math.ceil(shortfall / n)
        for s in range(n):
            handles.append(generate_domain_slice.spawn(
                domain, s, 8, per_slice, pass_idx))
        print(f"{domain}: shortfall {shortfall} -> {n} workers x {per_slice}")
    print(f"spawned {len(handles)} top-up workers")


@app.local_entrypoint()
def full_run_finalize(contexts: int = 5):
    """Merge slice outputs and certify per domain over the FULL item set at
    two eviction fractions (spec 13.4: certify per configuration)."""
    print("merge:", merge_full_items.remote())
    jobs = [(d, frac, contexts, True)
            for d in SOURCES for frac in (0.25, 0.40)]
    for domain_reports in certify_domain.starmap(jobs):
        for r in domain_reports:
            print(r["certification_id"],
                  "kl=", r["aggregation_axis"]["mean_kl"],
                  "lost=", r["pointwise_axis"]["lost_fact_incident_rate"])
