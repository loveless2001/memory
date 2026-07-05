"""Modal runner: executes the golden suite, milestone smokes, and the B.3
pilot certification on the reference config (Qwen3-4B bf16, single GPU) —
the local workstation cannot hold the model (BUILD.md Appendix B.1/B.7).

Usage:
  modal run modal-runners/modal-reference-golden-test-runner.py::run_golden_tests
  modal run modal-runners/modal-reference-golden-test-runner.py::run_smokes
  modal run modal-runners/modal-reference-golden-test-runner.py::pilot_certification
"""

import subprocess

import modal

GPU = "H100"
PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "pytest==8.3.4", "hf_transfer"]

app = modal.App("memsub-reference")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "MEMSUB_REFERENCE": "1"})
    .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
    .add_local_dir("memsub", "/root/repo/memsub")
    .add_local_dir("tests", "/root/repo/tests")
    .add_local_dir("examples", "/root/repo/examples")
)

hf_cache = modal.Volume.from_name("memsub-hf-cache", create_if_missing=True)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/root/.cache/huggingface": hf_cache, "/artifacts": artifacts}


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd="/root/repo", capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    print(out[-8000:])
    return proc.returncode, out


@app.function(image=image, gpu=GPU, volumes=VOLUMES, timeout=3600)
def run_golden_tests() -> dict:
    code, out = _run(["python", "-m", "pytest", "tests/", "-q", "-rA"])
    hf_cache.commit()
    return {"exit_code": code, "tail": out[-4000:]}


@app.function(image=image, gpu=GPU, volumes=VOLUMES, timeout=3600)
def run_selected_tests(selection: str) -> dict:
    """Run a subset with long tracebacks, e.g. selection='tests/test_x.py::test_y'."""
    code, out = _run(["python", "-m", "pytest", *selection.split(), "-q", "--tb=long"])
    hf_cache.commit()
    return {"exit_code": code, "tail": out[-6000:]}


@app.function(image=image, gpu=GPU, volumes=VOLUMES, timeout=3600)
def run_smokes() -> dict:
    results = {}
    for name in ("m0-text-substrate-smoke.py",
                 "m1-compaction-certification-smoke.py",
                 "m2-delta-checkpoint-resume-smoke.py"):
        code, out = _run(["python", f"examples/{name}"])
        results[name] = {"exit_code": code, "tail": out[-1200:]}
    hf_cache.commit()
    return results


CORPUS_URLS = {  # 4 public-domain long documents, 4 domains (spec B.3)
    "literature-moby-dick": "https://www.gutenberg.org/cache/epub/2701/pg2701.txt",
    "legal-us-constitution-annotated": "https://www.gutenberg.org/cache/epub/5/pg5.txt",
    "economics-wealth-of-nations": "https://www.gutenberg.org/cache/epub/3300/pg3300.txt",
    "science-origin-of-species": "https://www.gutenberg.org/cache/epub/1228/pg1228.txt",
}


@app.function(image=image, gpu=GPU, volumes=VOLUMES, timeout=14400)
def pilot_certification(target_items: int = 200, docs_to_certify: int = 4,
                        evict_fraction: float = 0.4) -> dict:
    """B.3 pilot: generate MCQ items (filters a+b), then run the 13.4 offline
    certification over pilot contexts at the target eviction fraction."""
    import json
    import sys
    import urllib.request
    sys.path.insert(0, "/root/repo")

    from memsub.certification import OfflineCertificationHarness, PilotMcqPipeline
    from memsub.reference_config import build_runtime
    from memsub.certification.offline_certification_harness import make_certification_id

    docs = {}
    for doc_id, url in CORPUS_URLS.items():
        raw = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "ignore")
        docs[doc_id] = raw[8000:8000 + 400_000]  # skip Gutenberg header

    runtime = build_runtime(reference=True)
    pipeline = PilotMcqPipeline(runtime, chunk_tokens=1024, seed=0)
    items = pipeline.generate(docs, target_items=target_items,
                              per_doc=max(2, target_items // len(docs) * 2))
    PilotMcqPipeline.save(items, "/artifacts/pilot-mcq-items.json")
    print(f"pilot items kept after filters: {len(items)}")

    harness = OfflineCertificationHarness(runtime)
    tok = runtime.tokenizer
    reports = []
    for doc_id in list(docs)[:docs_to_certify]:
        doc_items = [i for i in items if i.doc_id == doc_id]
        if not doc_items:
            continue
        anchor = doc_items[0]
        ids = tok.encode(docs[doc_id], add_special_tokens=False)
        ctx_start = max(0, anchor.chunk_token_start - 1024)
        ctx_ids = ids[ctx_start:ctx_start + 4096]
        needle_lo = anchor.chunk_token_start - ctx_start
        needle_hi = min(anchor.chunk_token_end - ctx_start, len(ctx_ids))
        span = int(len(ctx_ids) * evict_fraction)
        lo = max(4, min(needle_lo, len(ctx_ids) - span))
        evict_range = (lo, lo + span)
        needles = [i for i in doc_items
                   if lo <= i.chunk_token_start - ctx_start < lo + span] or [anchor]
        aggs = [i for i in doc_items if i not in needles][:8]
        report = harness.certify(
            context_text=tok.decode(ctx_ids),
            evict_logical_range=evict_range,
            mcq_items=aggs, needle_items=needles[:8])
        reports.append(report.to_dict())
        print(json.dumps(report.to_dict(), indent=1))

    summary = {
        "certification_id": make_certification_id(
            runtime.fingerprint().model_id, "evict-oldest-nonsink-v1", evict_fraction),
        "n_pilot_items": len(items),
        "reports": reports,
    }
    with open("/artifacts/pilot-certification-reports.json", "w") as f:
        json.dump(summary, f, indent=1)
    artifacts.commit()
    hf_cache.commit()
    return {"n_items": len(items), "n_reports": len(reports),
            "lost_fact_rates": [r["pointwise_axis"]["lost_fact_incident_rate"]
                                 for r in reports]}
