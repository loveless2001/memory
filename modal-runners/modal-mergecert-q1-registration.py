"""CPU-only, read-only extraction of the finalized MergeCert Q1 registry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import modal


MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
RATIOS = (0.25, 0.40)
SINKS = 4
ARCHIVE_ROOT = "/artifacts/corpus-certification-full"
ITEMS_PATH = "/artifacts/corpus-mcq-full/all-items.json"
CORPUS_ROOT = "/artifacts/corpus"
SOURCE_REGISTRY_PATH = "/root/q1-registration-source.json"
LOCAL_SOURCE_REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "plans"
    / "260728-mergecert-q1"
    / "q1-registration-source.json"
)

app = modal.App("mergecert-q1-registration")
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=False)
hf_cache = modal.Volume.from_name("memsub-hf-cache", create_if_missing=False)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("transformers==4.55.2", "tokenizers==0.21.4")
    .env({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    .add_local_file(
        str(LOCAL_SOURCE_REGISTRY),
        remote_path=SOURCE_REGISTRY_PATH,
        copy=True,
    )
)


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def build_document_registration(
    tokenizer,
    *,
    doc_id: str,
    text: str,
    anchor_chunk_token_start: int,
    registered_source_start: int,
) -> dict:
    """Reproduce the original M1 source window and its re-encoded model input."""

    if not all(
        _strict_int(value)
        for value in (anchor_chunk_token_start, registered_source_start)
    ):
        raise ValueError(f"{doc_id}: registration anchors must be strict ints")
    document_ids = tokenizer.encode(text, add_special_tokens=False)
    context_start = max(0, anchor_chunk_token_start - 1024)
    source_ids = document_ids[context_start : context_start + 4096]
    if not source_ids:
        raise ValueError(f"{doc_id}: registered M1 source window is empty")
    model_ids = tokenizer.encode(
        tokenizer.decode(source_ids), add_special_tokens=False
    )
    source_count = len(source_ids)
    model_count = len(model_ids)
    reference_span = int(source_count * 0.25)
    derived_source_start = max(
        SINKS,
        min(
            anchor_chunk_token_start - context_start,
            source_count - reference_span,
        ),
    )
    if derived_source_start != registered_source_start:
        raise ValueError(f"{doc_id}: registered M1 anchor drift")
    budgets = {}
    for ratio in RATIOS:
        requested = int(source_count * ratio)
        source_end = registered_source_start + requested
        actual_removed = max(
            0,
            min(source_end, model_count)
            - min(max(registered_source_start, 0), model_count),
        )
        budgets[f"{ratio:.2f}"] = {
            "requested_evicted_token_count": requested,
            "eviction_source_start": registered_source_start,
            "eviction_source_end": source_end,
            "physical_before_count": model_count,
            "physical_after_count": model_count - actual_removed,
            "evicted_token_count": actual_removed,
            "retained_token_count": model_count - actual_removed,
            "merge_target_retained": model_count - actual_removed,
        }
    return {
        "doc_id": doc_id,
        "context_start": context_start,
        "source_context_token_count": source_count,
        "model_input_token_count": model_count,
        "budgets": budgets,
    }


def _load_source_texts(doc_ids: set[str]) -> dict[str, str]:
    texts = {}
    domains = {doc_id.split("/", 1)[0] for doc_id in doc_ids}
    for domain in sorted(domains):
        with open(f"{CORPUS_ROOT}/{domain}.jsonl") as handle:
            for line in handle:
                row = json.loads(line)
                if row["doc_id"] in doc_ids:
                    texts[row["doc_id"]] = row["text"]
                if len(texts) == len(doc_ids):
                    return texts
    return texts


def extract_registration() -> dict:
    """Read registered private evidence and return a small finalized registry."""

    from transformers import AutoTokenizer

    with open(SOURCE_REGISTRY_PATH) as handle:
        source = json.load(handle)
    if _sha256_file(ITEMS_PATH) != source["all_items_sha256"]:
        raise ValueError("all-items registry hash drift")
    archive_rows = {}
    for name, expected_hash in source["archive_sha256"].items():
        path = f"{ARCHIVE_ROOT}/{name}"
        if _sha256_file(path) != expected_hash:
            raise ValueError(f"{name}: archive hash drift")
        with open(path) as handle:
            archive_rows[name] = json.load(handle)
    for name, rows in archive_rows.items():
        domain = name.split("-", 1)[0]
        expected_docs = [
            doc_id
            for doc_id in source["population_doc_ids"]
            if doc_id.startswith(f"{domain}/")
        ]
        actual_docs = [
            row["eval_protocol"]["context_doc_id"] for row in rows
        ]
        if actual_docs != expected_docs:
            raise ValueError(f"{name}: archive population drift")

    doc_ids = source["population_doc_ids"]
    texts = _load_source_texts(set(doc_ids))
    if set(texts) != set(doc_ids):
        raise ValueError("registered source documents are incomplete")
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID, local_files_only=True
    )
    documents = [
        build_document_registration(
            tokenizer,
            doc_id=doc_id,
            text=texts[doc_id],
            anchor_chunk_token_start=source["anchor_chunk_token_start"][
                doc_id
            ],
            registered_source_start=source["eviction_source_start"][doc_id],
        )
        for doc_id in doc_ids
    ]
    return {
        "schema": "mergecert-q1-registration-v1",
        "status": "finalized",
        "source_registration_sha256": _sha256_file(SOURCE_REGISTRY_PATH),
        "model_id": MODEL_ID,
        "population_doc_ids": doc_ids,
        "smoke_doc_ids": source["smoke_doc_ids"],
        "all_items_sha256": source["all_items_sha256"],
        "archive_sha256": source["archive_sha256"],
        "documents": documents,
    }


@app.function(
    image=image,
    volumes={
        "/artifacts": artifacts,
        "/root/.cache/huggingface": hf_cache,
    },
    timeout=3_600,
    memory=8_192,
)
def extract_q1_registration() -> dict:
    return extract_registration()


@app.local_entrypoint()
def main() -> None:
    print(json.dumps(extract_q1_registration.remote(), indent=1))
