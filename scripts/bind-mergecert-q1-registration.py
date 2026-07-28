"""Bind one reviewed MergeCert Q1 extractor result into the local campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from memsub.mergecert_q1_registration import (
    Q1_REGISTRATION_PENDING,
    canonical_q1_registration_bytes,
    validate_q1_registration_schema,
)


LOCAL_REGISTRATION = Path(
    "plans/260728-mergecert-q1/q1-registration.json"
)
REMOTE_REGISTRATION = "/artifacts/mergecert-q1/q1-registration.json"
BINDING_MODULE = Path("memsub/mergecert_q1_registration.py")
SOURCE_PROVENANCE = Path(
    "plans/260728-mergecert-q1/source-provenance.json"
)
BINDING_PENDING_PATTERN = re.compile(
    r"^Q1_REGISTRATION_SHA256 = Q1_REGISTRATION_PENDING$",
    re.MULTILINE,
)
ANY_BINDING_PATTERN = re.compile(
    r"^Q1_REGISTRATION_SHA256 = .+$", re.MULTILINE
)
PENDING_PROVENANCE = {
    "path": LOCAL_REGISTRATION.as_posix(),
    "remote_path": REMOTE_REGISTRATION,
    "sha256": Q1_REGISTRATION_PENDING,
    "status": "pending CPU extraction and independent review",
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _stage_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.q1-bind-stage")


def _stage_bytes(path: Path, value: bytes) -> Path:
    staged = _stage_path(path)
    with staged.open("xb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    return staged


def _replace_staged(staged: Path, target: Path) -> None:
    os.replace(staged, target)


def _cleanup_stages(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def bind_registration(input_path: Path, *, root: Path) -> dict:
    """Install one extracted file and update the sole executable hash literal."""

    root = Path(root)
    input_path = Path(input_path)
    binding_path = root / BINDING_MODULE
    provenance_path = root / SOURCE_PROVENANCE
    source_path = root / (
        "plans/260728-mergecert-q1/q1-registration-source.json"
    )
    target = root / LOCAL_REGISTRATION
    final_paths = (target, provenance_path, binding_path)
    stage_paths = [_stage_path(path) for path in final_paths]

    binding_text = binding_path.read_text()
    provenance = json.loads(provenance_path.read_text())
    binding_assignments = ANY_BINDING_PATTERN.findall(binding_text)
    if (
        target.exists()
        or any(path.exists() for path in stage_paths)
        or binding_assignments
        != ["Q1_REGISTRATION_SHA256 = Q1_REGISTRATION_PENDING"]
        or len(BINDING_PENDING_PATTERN.findall(binding_text)) != 1
        or provenance.get("q1_registration") != PENDING_PROVENANCE
    ):
        raise ValueError(
            "Q1 registration binding is already finalized or inconsistent"
        )

    raw = input_path.read_bytes()
    registration = json.loads(raw)
    canonical = canonical_q1_registration_bytes(registration)
    if raw != canonical:
        raise ValueError("reviewed Q1 registration bytes are not canonical")
    source_raw = source_path.read_bytes()
    source = json.loads(source_raw)
    if (
        _sha256_bytes(source_raw)
        != registration.get("source_registration_sha256")
    ):
        raise ValueError("Q1 registration source hash is inconsistent")
    validate_q1_registration_schema(
        registration, source_registration=source
    )
    digest = _sha256_bytes(raw)

    replacement = f'Q1_REGISTRATION_SHA256 = "{digest}"'
    updated_binding, replacements = BINDING_PENDING_PATTERN.subn(
        replacement, binding_text
    )
    if replacements != 1:
        raise ValueError("Q1 registration binding does not have one update point")

    provenance["q1_registration"] = {
        "path": LOCAL_REGISTRATION.as_posix(),
        "remote_path": REMOTE_REGISTRATION,
        "sha256": digest,
        "status": "finalized and hash-bound",
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    payloads = (
        raw,
        (
            json.dumps(provenance, indent=1, allow_nan=False) + "\n"
        ).encode(),
        updated_binding.encode(),
    )
    staged = []
    try:
        for path, value in zip(final_paths, payloads, strict=True):
            staged.append(_stage_bytes(path, value))
        for staged_path, final_path in zip(
            staged, final_paths, strict=True
        ):
            _replace_staged(staged_path, final_path)
    finally:
        _cleanup_stages(stage_paths)
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
