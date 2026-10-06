"""Canonical sha256 helpers. Every stored artifact hash uses the
"sha256:<hex>" format from the spec schemas."""

import hashlib
import json
from typing import Any

PREFIX = "sha256:"


def sha256_bytes(data: bytes) -> str:
    return PREFIX + hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_json(obj: Any) -> str:
    """Hash of the canonical JSON serialization (sorted keys, no whitespace)."""
    canon = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_text(canon)


def sha256_file(path: str, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return PREFIX + h.hexdigest()


def hex_of(hash_str: str) -> str:
    """Extract the bare hex digest from a 'sha256:...' string."""
    if not hash_str.startswith(PREFIX):
        raise ValueError(f"not a canonical sha256 hash: {hash_str!r}")
    return hash_str[len(PREFIX):]
