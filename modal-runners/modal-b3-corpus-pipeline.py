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

# (hub parquet path, extractor) per domain; extractor -> doc text or None
SOURCES = {
    "financial": {
        "shards": ["datasets/eloukas/edgar-corpus@refs/convert/parquet/full/partial-train/000{i}.parquet"],
        "n_shards": 2,
    },
    "legal": {
        "shards": ["datasets/HFforLegal/case-law@refs/convert/parquet/default/partial-us/000{i}.parquet"],
        "n_shards": 2,
    },
    "code": {
        "shards": ["datasets/codeparrot/github-code-clean/data/train-0000{i}-of-00880.parquet"],
        "n_shards": 4,
    },
    "literature": {
        "shards": ["datasets/sedthh/gutenberg_english/data/train-0000{i}-of-00037-f5fce855b93d2d02.parquet"],
        "n_shards": 1,
    },
}
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
    from huggingface_hub import HfFileSystem

    fs = HfFileSystem()
    os.makedirs("/artifacts/corpus", exist_ok=True)
    manifest = {}
    for domain, spec in SOURCES.items():
        kept, total_chars = 0, 0
        out_path = f"/artifacts/corpus/{domain}.jsonl"
        with open(out_path, "w") as out:
            for i in range(spec["n_shards"]):
                if kept >= docs_per_domain:
                    break
                path = spec["shards"][0].format(i=i)
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


@app.function(image=gpu_image, gpu=GPU, volumes=VOLUMES, timeout=7200)
def certify_domain(domain: str, evict_fraction: float = 0.4,
                   contexts: int = 3) -> list[dict]:
    """Offline certification (spec 13.4) over sampled contexts of one domain,
    using that domain's verified MCQ items as probes."""
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    from memsub.certification import OfflineCertificationHarness, PilotMcqPipeline
    from memsub.reference_config import build_runtime

    os.makedirs("/artifacts/corpus-certification", exist_ok=True)
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
    with open(f"/artifacts/corpus-certification/{domain}.json", "w") as f:
        json.dump(reports, f, indent=1)
    artifacts.commit()
    return reports


@app.local_entrypoint()
def generate_and_certify(target_items: int = 2000):
    import os
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
