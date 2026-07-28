"""Immutable binding for the private MergeCert Q1 registration.

Step 1a replaces the pending sentinel with the reviewed registration's
literal SHA-256.  Campaign consumers import this one value so a supplied
registration can never authorize itself.
"""

import hashlib
import json
from pathlib import Path

Q1_REGISTRATION_PENDING = "PENDING_CPU_EXTRACTION"
Q1_REGISTRATION_SHA256 = "6d90677469c5548d0fde863db886e7a6665e25f15c23d351ba07a0ad4db6e2d5"
Q1_MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
Q1_TOKENIZER_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
Q1_TOKENIZER_FILES_SHA256 = {
    "config.json": (
        "5beea1a4a34c62782bfb2f911c606741a3bab8f92d80a118fa053c28af12e8ba"
    ),
    "merges.txt": (
        "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3"
    ),
    "tokenizer.json": (
        "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4"
    ),
    "tokenizer_config.json": (
        "a62ff0a2472a0fa1b8eaabcb57c59b58afa42a22831dc141400b6e0cf2b65ce3"
    ),
    "vocab.json": (
        "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"
    ),
}
Q1_TOKENIZER_ARTIFACT_SHA256 = (
    "709a32d47b81b8466749dac3f8c4718b901bad95c534a486a8ac0b388094f6c9"
)
Q1_REGISTRATION_LOCAL_PATH = (
    "plans/260728-mergecert-q1/q1-registration.json"
)
Q1_REGISTRATION_REMOTE_PATH = (
    "/artifacts/mergecert-q1/q1-registration.json"
)


def canonical_q1_registration_bytes(registration: dict) -> bytes:
    return (
        json.dumps(registration, indent=1, allow_nan=False) + "\n"
    ).encode()


def canonical_q1_registration_sha256(registration: dict) -> str:
    return hashlib.sha256(
        canonical_q1_registration_bytes(registration)
    ).hexdigest()


def _json_sha256(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _strict_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_exact_keys(value, expected: set[str], location: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"Q1 registration schema requires {location} object")
    unknown = set(value) - expected
    missing = expected - set(value)
    if unknown or missing:
        raise ValueError(
            f"Q1 registration schema {location} keys differ: "
            f"unknown={sorted(unknown)}, missing={sorted(missing)}"
        )


def _is_tokenizer_artifact_name(name: str) -> bool:
    return (
        name in {"config.json", "merges.txt", "special_tokens_map.json",
                 "added_tokens.json"}
        or name.startswith("tokenizer")
        or name.startswith("vocab.")
        or name.startswith("chat_template")
    )


def tokenizer_artifact_digests(
    snapshot: str | Path,
    *,
    expected_files_sha256: dict[str, str] = Q1_TOKENIZER_FILES_SHA256,
) -> dict[str, str]:
    """Verify and return the exact reviewed tokenizer artifact set."""

    snapshot = Path(snapshot)
    actual_paths = {
        path.relative_to(snapshot).as_posix(): path
        for path in sorted(snapshot.rglob("*"))
        if path.is_file() and _is_tokenizer_artifact_name(path.name)
    }
    if set(actual_paths) != set(expected_files_sha256):
        raise ValueError(
            "tokenizer artifact file set differs from reviewed manifest"
        )
    actual = {
        name: _sha256_file(actual_paths[name])
        for name in sorted(actual_paths)
    }
    if actual != expected_files_sha256:
        raise ValueError(
            "tokenizer artifact digest differs from reviewed manifest"
        )
    return actual


def resolve_q1_tokenizer_snapshot() -> Path:
    """Resolve only the reviewed tokenizer files from the exact local commit."""

    from huggingface_hub import snapshot_download

    return Path(
        snapshot_download(
            repo_id=Q1_MODEL_ID,
            revision=Q1_TOKENIZER_REVISION,
            local_files_only=True,
            allow_patterns=tuple(Q1_TOKENIZER_FILES_SHA256),
        )
    )


def validate_q1_registration_schema(
    registration: dict,
    *,
    source_registration: dict | None = None,
) -> None:
    """Reject any non-canonical shape, type, provenance, or budget value."""

    top_keys = {
        "schema",
        "status",
        "source_registration_sha256",
        "model_id",
        "tokenizer",
        "source_hashes",
        "population_doc_ids",
        "smoke_doc_ids",
        "all_items_sha256",
        "archive_sha256",
        "documents",
    }
    _require_exact_keys(registration, top_keys, "top-level")
    if (
        registration["schema"] != "mergecert-q1-registration-v1"
        or registration["status"] != "finalized"
        or registration["model_id"] != Q1_MODEL_ID
        or not _is_sha256(registration["source_registration_sha256"])
    ):
        raise ValueError("Q1 registration schema identity is invalid")

    tokenizer = registration["tokenizer"]
    _require_exact_keys(
        tokenizer,
        {"model_id", "revision", "files_sha256", "artifact_sha256"},
        "tokenizer",
    )
    if (
        tokenizer["model_id"] != Q1_MODEL_ID
        or tokenizer["revision"] != Q1_TOKENIZER_REVISION
        or tokenizer["files_sha256"] != Q1_TOKENIZER_FILES_SHA256
        or tokenizer["artifact_sha256"] != Q1_TOKENIZER_ARTIFACT_SHA256
        or _json_sha256(tokenizer["files_sha256"])
        != Q1_TOKENIZER_ARTIFACT_SHA256
    ):
        raise ValueError("Q1 registration tokenizer provenance is invalid")

    source_hashes = registration["source_hashes"]
    _require_exact_keys(
        source_hashes,
        {
            "corpus_manifest_sha256",
            "all_items_sha256",
            "source_document_sha256",
        },
        "source_hashes",
    )
    source_documents = source_hashes["source_document_sha256"]
    if (
        not _is_sha256(source_hashes["corpus_manifest_sha256"])
        or not _is_sha256(source_hashes["all_items_sha256"])
        or not isinstance(source_documents, dict)
        or any(
            not isinstance(doc_id, str) or not _is_sha256(digest)
            for doc_id, digest in source_documents.items()
        )
    ):
        raise ValueError("Q1 registration source hash schema is invalid")

    population = registration["population_doc_ids"]
    smoke = registration["smoke_doc_ids"]
    archives = registration["archive_sha256"]
    if (
        not isinstance(population, list)
        or not population
        or any(not isinstance(doc_id, str) for doc_id in population)
        or len(set(population)) != len(population)
        or not isinstance(smoke, list)
        or any(not isinstance(doc_id, str) for doc_id in smoke)
        or not set(smoke) <= set(population)
        or not _is_sha256(registration["all_items_sha256"])
        or not isinstance(archives, dict)
        or any(
            not isinstance(name, str) or not _is_sha256(digest)
            for name, digest in archives.items()
        )
        or set(source_documents) != set(population)
        or source_hashes["all_items_sha256"]
        != registration["all_items_sha256"]
    ):
        raise ValueError(
            "Q1 registration source hash or population schema is invalid"
        )

    documents = registration["documents"]
    if (
        not isinstance(documents, list)
        or [row.get("doc_id") if isinstance(row, dict) else None
            for row in documents] != population
    ):
        raise ValueError("Q1 registration document population is invalid")
    budget_keys = {
        "requested_evicted_token_count",
        "eviction_source_start",
        "eviction_source_end",
        "physical_before_count",
        "physical_after_count",
        "evicted_token_count",
        "retained_token_count",
        "merge_target_retained",
    }
    for index, document in enumerate(documents):
        _require_exact_keys(
            document,
            {
                "doc_id",
                "context_start",
                "source_context_token_count",
                "model_input_token_count",
                "budgets",
            },
            f"documents[{index}]",
        )
        source_tokens = document["source_context_token_count"]
        model_tokens = document["model_input_token_count"]
        if (
            not _strict_int(document["context_start"])
            or document["context_start"] < 0
            or not _strict_int(source_tokens)
            or source_tokens <= 4
            or not _strict_int(model_tokens)
            or model_tokens <= 4
        ):
            raise ValueError("Q1 registration document counts are invalid")
        budgets = document["budgets"]
        _require_exact_keys(
            budgets, {"0.25", "0.40"}, f"documents[{index}].budgets"
        )
        for ratio_text in ("0.25", "0.40"):
            budget = budgets[ratio_text]
            _require_exact_keys(
                budget,
                budget_keys,
                f"documents[{index}].budgets[{ratio_text}]",
            )
            if any(not _strict_int(budget[key]) for key in budget_keys):
                raise ValueError(
                    "Q1 registration counts have invalid budget types"
                )
            requested = int(source_tokens * float(ratio_text))
            source_start = budget["eviction_source_start"]
            source_end = source_start + requested
            actual_removed = max(
                0,
                min(source_end, model_tokens)
                - min(max(source_start, 0), model_tokens),
            )
            expected = {
                "requested_evicted_token_count": requested,
                "eviction_source_start": source_start,
                "eviction_source_end": source_end,
                "physical_before_count": model_tokens,
                "physical_after_count": model_tokens - actual_removed,
                "evicted_token_count": actual_removed,
                "retained_token_count": model_tokens - actual_removed,
                "merge_target_retained": model_tokens - actual_removed,
            }
            if budget != expected:
                raise ValueError("Q1 registration budget values are invalid")

    if source_registration is not None:
        if (
            population != source_registration.get("population_doc_ids")
            or smoke != source_registration.get("smoke_doc_ids")
            or registration["all_items_sha256"]
            != source_registration.get("all_items_sha256")
            or archives != source_registration.get("archive_sha256")
        ):
            raise ValueError("Q1 registration differs from source evidence")
        for document in documents:
            doc_id = document["doc_id"]
            if (
                document["context_start"]
                != max(
                    0,
                    source_registration["anchor_chunk_token_start"][doc_id]
                    - 1024,
                )
                or any(
                    budget["eviction_source_start"]
                    != source_registration["eviction_source_start"][doc_id]
                    for budget in document["budgets"].values()
                )
            ):
                raise ValueError(
                    "Q1 registration context start or source anchors differ"
                )


def require_q1_registration_binding() -> str:
    if Q1_REGISTRATION_SHA256 == Q1_REGISTRATION_PENDING:
        raise ValueError(
            "Q1 finalized registration binding is pending CPU extraction "
            "and independent review"
        )
    if (
        not isinstance(Q1_REGISTRATION_SHA256, str)
        or len(Q1_REGISTRATION_SHA256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in Q1_REGISTRATION_SHA256
        )
    ):
        raise ValueError("Q1 finalized registration SHA-256 binding is invalid")
    return Q1_REGISTRATION_SHA256
