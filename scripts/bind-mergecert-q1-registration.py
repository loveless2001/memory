"""Bind one reviewed MergeCert Q1 extractor result into the local campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from memsub.mergecert_q1_registration import canonical_q1_registration_bytes


LOCAL_REGISTRATION = Path(
    "plans/260728-mergecert-q1/q1-registration.json"
)
REMOTE_REGISTRATION = "/artifacts/mergecert-q1/q1-registration.json"
BINDING_MODULE = Path("memsub/mergecert_q1_registration.py")
SOURCE_PROVENANCE = Path(
    "plans/260728-mergecert-q1/source-provenance.json"
)
BINDING_PATTERN = re.compile(
    r"^Q1_REGISTRATION_SHA256 = "
    r"(?:Q1_REGISTRATION_PENDING|\"[0-9a-f]{64}\")$",
    re.MULTILINE,
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _contains_source_text(value) -> bool:
    if isinstance(value, dict):
        if any(key in {"text", "source_text"} for key in value):
            return True
        return any(_contains_source_text(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_source_text(child) for child in value)
    return False


def _atomic_write(path: Path, value: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(value)
    os.replace(temporary, path)


def bind_registration(input_path: Path, *, root: Path) -> dict:
    """Install one extracted file and update the sole executable hash literal."""

    root = Path(root)
    input_path = Path(input_path)
    raw = input_path.read_bytes()
    registration = json.loads(raw)
    if (
        registration.get("schema") != "mergecert-q1-registration-v1"
        or registration.get("status") != "finalized"
        or not isinstance(
            registration.get("source_registration_sha256"), str
        )
        or len(registration["source_registration_sha256"]) != 64
        or _contains_source_text(registration)
    ):
        raise ValueError(
            "extractor output is not a source-free finalized Q1 registration"
        )
    canonical = canonical_q1_registration_bytes(registration)
    digest = _sha256_bytes(canonical)

    binding_path = root / BINDING_MODULE
    binding_text = binding_path.read_text()
    replacement = f'Q1_REGISTRATION_SHA256 = "{digest}"'
    updated_binding, replacements = BINDING_PATTERN.subn(
        replacement, binding_text
    )
    if replacements != 1:
        raise ValueError("Q1 registration binding does not have one update point")

    provenance_path = root / SOURCE_PROVENANCE
    provenance = json.loads(provenance_path.read_text())
    provenance["q1_registration"] = {
        "path": LOCAL_REGISTRATION.as_posix(),
        "remote_path": REMOTE_REGISTRATION,
        "sha256": digest,
        "status": "finalized and hash-bound",
    }

    target = root / LOCAL_REGISTRATION
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(target, canonical)
    _atomic_write(binding_path, updated_binding.encode())
    _atomic_write(
        provenance_path,
        (
            json.dumps(provenance, indent=1, allow_nan=False) + "\n"
        ).encode(),
    )
    return {"path": target, "sha256": digest}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    result = bind_registration(args.input, root=args.root)
    print(f"{result['sha256']}  {result['path']}")


if __name__ == "__main__":
    main()
