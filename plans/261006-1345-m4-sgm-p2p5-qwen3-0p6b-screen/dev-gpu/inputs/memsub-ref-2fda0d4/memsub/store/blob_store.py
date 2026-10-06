"""Content-addressed filesystem blob store (spec B.2, B.7).

URIs are "store://blobs/sha256/<aa>/<hex>". Content addressing gives delta
checkpoints and CoW lineage for free: an unchanged KV page hashes to the same
blob and is never rewritten (spec 11.2, 11.5).
"""

from __future__ import annotations

import os
from pathlib import Path

from ..errors import IntegrityError
from ..hashing import hex_of, sha256_bytes

URI_PREFIX = "store://blobs/sha256/"


class BlobStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        (self.root / "blobs" / "sha256").mkdir(parents=True, exist_ok=True)

    def _path_for_hex(self, hex_digest: str) -> Path:
        return self.root / "blobs" / "sha256" / hex_digest[:2] / hex_digest

    def put(self, data: bytes) -> str:
        """Store bytes, return canonical URI. Idempotent."""
        digest = hex_of(sha256_bytes(data))
        path = self._path_for_hex(digest)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp." + str(os.getpid()))
            tmp.write_bytes(data)
            os.replace(tmp, path)  # atomic on same filesystem
        return URI_PREFIX + digest

    def put_text(self, text: str) -> str:
        return self.put(text.encode("utf-8"))

    def has(self, uri: str) -> bool:
        return self.path_for(uri).exists()

    def path_for(self, uri: str) -> Path:
        """Filesystem path backing a URI — used for safetensors mmap loads."""
        if not uri.startswith(URI_PREFIX):
            raise ValueError(f"not a blob store uri: {uri!r}")
        return self._path_for_hex(uri[len(URI_PREFIX):])

    def get(self, uri: str, verify: bool = True) -> bytes:
        data = self.path_for(uri).read_bytes()
        if verify:
            expected = uri[len(URI_PREFIX):]
            actual = hex_of(sha256_bytes(data))
            if actual != expected:
                raise IntegrityError(f"blob {uri} checksum mismatch: {actual}")
        return data

    def get_text(self, uri: str) -> str:
        return self.get(uri).decode("utf-8")
