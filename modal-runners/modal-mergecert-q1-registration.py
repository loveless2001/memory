"""CPU-only, read-only extraction of the finalized MergeCert Q1 registry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import modal


MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
TOKENIZER_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
RATIOS = (0.25, 0.40)
SINKS = 4
ARCHIVE_ROOT = "/artifacts/corpus-certification-full"
ITEMS_PATH = "/artifacts/corpus-mcq-full/all-items.json"
CORPUS_ROOT = "/artifacts/corpus"
CORPUS_MANIFEST_PATH = f"{CORPUS_ROOT}/manifest.json"
SOURCE_REGISTRY_PATH = "/root/q1-registration-source.json"
TOKENIZER_ARTIFACT_PATTERNS = (
    "config.json",
    "tokenizer*",
    "special_tokens_map.json",
    "added_tokens.json",
    "vocab.*",
    "merges.txt",
    "chat_template*",
)
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


def _json_sha256(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _is_tokenizer_artifact(path: Path) -> bool:
    name = path.name
    return (
        name.startswith("tokenizer")
        or name in {
            "config.json",
            "special_tokens_map.json",
            "added_tokens.json",
            "merges.txt",
        }
        or name.startswith("vocab.")
        or name.startswith("chat_template")
    )


def _load_tokenizer_with_provenance():
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer

    snapshot = Path(
        snapshot_download(
            repo_id=MODEL_ID,
            revision=TOKENIZER_REVISION,
            local_files_only=True,
            allow_patterns=TOKENIZER_ARTIFACT_PATTERNS,
        )
    )
    files_sha256 = {
        path.relative_to(snapshot).as_posix(): _sha256_file(path)
        for path in sorted(snapshot.rglob("*"))
        if path.is_file() and _is_tokenizer_artifact(path)
    }
    if not files_sha256:
        raise ValueError("tokenizer artifact digest set is incomplete")
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID,
        revision=TOKENIZER_REVISION,
        local_files_only=True,
    )
    return tokenizer, {
        "model_id": MODEL_ID,
        "revision": TOKENIZER_REVISION,
        "files_sha256": files_sha256,
        "artifact_sha256": _json_sha256(files_sha256),
    }


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
                doc_id = row.get("doc_id")
                if doc_id not in doc_ids:
                    continue
                if doc_id in texts:
                    raise ValueError(
                        f"duplicate registered source document row: {doc_id}"
                    )
                if not isinstance(row.get("text"), str):
                    raise ValueError(
                        f"{doc_id}: registered source text is invalid"
                    )
                texts[doc_id] = row["text"]
    missing = sorted(doc_ids - set(texts))
    if missing:
        raise ValueError(
            f"registered source documents are incomplete: {missing[:10]}"
        )
    return texts


def extract_registration() -> dict:
    """Read registered private evidence and return a small finalized registry."""

    with open(SOURCE_REGISTRY_PATH) as handle:
        source = json.load(handle)
    if source.get("tokenizer_revision") != TOKENIZER_REVISION:
        raise ValueError("tokenizer revision differs from source registration")
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
    source_document_sha256 = {
        doc_id: hashlib.sha256(texts[doc_id].encode("utf-8")).hexdigest()
        for doc_id in doc_ids
    }
    if set(source_document_sha256) != set(doc_ids):
        raise ValueError("source-document digest set is incomplete")
    tokenizer, tokenizer_provenance = _load_tokenizer_with_provenance()
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
        "tokenizer": tokenizer_provenance,
        "source_hashes": {
            "corpus_manifest_sha256": _sha256_file(
                CORPUS_MANIFEST_PATH
            ),
            "all_items_sha256": source["all_items_sha256"],
            "source_document_sha256": source_document_sha256,
        },
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
