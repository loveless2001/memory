"""Exact local/remote source binding, excluding generated results and caches."""

import hashlib


def source_manifest(root, remote=False):
    names = ["CONTEXT-GATE.md", "pyproject.toml", "memsub/fingerprint.py", "memsub/hashing.py"]
    names += [str(p.relative_to(root)) for p in sorted((root / "experiments/context_gate").glob("*.py"))]
    names += ["experiments/context_gate/config.json"]
    out = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
    runner = root / ("modal-context-gate.py" if remote else "modal-runners/modal-context-gate.py")
    out["modal-runners/modal-context-gate.py"] = hashlib.sha256(runner.read_bytes()).hexdigest()
    return out
