"""Preserve P2C consumed inputs and audit evidence without changing originals."""
import gzip
import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/readings-v1"
REPORT = json.loads((BUNDLE / "p2c-readings.json").read_text())
INDEX = json.loads((ROOT / "configs/m4_sgm_p2c_inputs.json").read_text())


def sha(b):
    return hashlib.sha256(b).hexdigest()


sources = {
    "independent-results-check.py": "codex-261006-p2c-results-independent-audit.py",
    "independent-results-check.json": "codex-261006-p2c-results-independent-audit.json",
    "training-artifacts-check.json": "codex-261006-p2c-training-artifacts-audit.json",
    "training-artifacts-check.py": "codex-261006-p2c-training-artifacts-independent-check.py",
    "lifecycle-billing-check.json": "codex-261006-p2c-final-lifecycle-billing-audit.json",
    "approved-launch-clearance.json": "codex-261006-p2c-approved-launch-clearance.json",
    "spawn-verification.json": "codex-261006-p2c-spawn-verification.json",
    "spawn-state.json": "codex-261006-p2c-live-spawn-state.json",
    "preflight-r2-independent-check.py": "codex-261006-p2c-preflight-r2-independent-check.py",
    "preflight-r2-independent-check.json": "codex-261006-p2c-preflight-r2-independent-checks.json",
    "final-technical-clearance.md": "codex-261006-p2c-final-technical-clearance.md",
    "implementation-e64266e-audit.md": "codex-261006-p2c-implementation-e64266e-audit.md",
    "implementation-e64266e-checks.json": "codex-261006-p2c-implementation-e64266e-checks.json",
    "implementation-8c3161a-clearance.md": "codex-261006-p2c-implementation-8c3161a-clearance.md",
    "prereg-v02-audit.md": "codex-261006-p2c-prereg-v02-audit.md",
    "approved-cap-plan.json": "codex-261006-p2c-approved-cap-plan.json",
}
assert json.loads((ROOT / "plans/reports" / sources["independent-results-check.json"]).read_text())["pass"] is True
audit = BUNDLE / "audit"
audit.mkdir(exist_ok=False)
for dest, name in sources.items():
    shutil.copyfile(ROOT / "plans/reports" / name, audit / dest)

paths = {BUNDLE / "p2c-readings.json", Path(__file__).resolve()}
paths.update(BUNDLE.glob("rows-*.jsonl"))
paths.update((BUNDLE / "parity").glob("*.jsonl"))
paths.update(ROOT / "plans/reports" / name for name in sources.values())
paths.update(ROOT / p for p in REPORT["observer"]["analysis_sha256"])
paths.update(p for p in (ROOT / "memsub").rglob("*.py") if "pycache" not in p.parent.name)
paths.update(ROOT / p for p in ("configs/m4_sgm_p2c_grid.json", "configs/m4_sgm_p2c_inputs.json",
    "plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/prereg.md",
    "plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/readings-v1.log"))
plan = BUNDLE.parent
paths.update(p for p in (plan / "preflight-r2").rglob("*") if p.is_file())
paths.add(plan / "full-suite-8c3161a.txt")
paths.update(plan / name for name in ("preflight-r2.log", "preflight-r1-aborted.log"))
cells = {ROOT / c["cell"] for c in REPORT["p2c_cells"].values()} | {ROOT / c["cell"] for c in INDEX["reused"].values()}
assert len(cells) == 14
required = ("run_manifest.json", "trained_parameters.safetensors", "metrics.json", "per_example_results.jsonl",
            "split_manifest.json", "routing_telemetry.jsonl", "report.md")
for cell in cells:
    paths.update(cell / f for f in required)
for entries in INDEX["parity"].values():
    paths.update(ROOT / e["reference"] for e in entries)
runs = ROOT / "plans/261005-0210-m4-sgm-p0-p2/runs/p2c-filler-curriculum-v1"
paths.update(runs / f for f in ("grid.json", "launch_provenance.json", "calls.json", "collect_status.json", "artifact_validation.json"))
for rid in REPORT["p2c_cells"]:
    paths.update(runs / rid / f for f in ("metrics.json", "per_example_results.jsonl"))
content = {str(p.relative_to(ROOT)): p.read_bytes() for p in sorted(paths)}
manifest = {"report_sha256": sha((BUNDLE / "p2c-readings.json").read_bytes()),
            "observer_commit": REPORT["observer"]["git_head"], "input_cells": 14,
            "files": [{"repo_path": p, "sha256": sha(b), "bytes": len(b)} for p, b in content.items()],
            "replay": "Extract into an isolated checkout containing observer commit d47fe17; run plans/reports/codex-261006-p2c-results-independent-audit.py with the pinned environment. The verifier uses saved reserved-seed rows and development seed 4242 only."}
manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
(BUNDLE / "replay-evidence-manifest.json").write_bytes(manifest_bytes)
archive = BUNDLE / "replay-evidence.tar.gz"
with archive.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as gz, tarfile.open(fileobj=gz, mode="w") as tar:
    for p, b in {**content, "_P2C_REPLAY_MANIFEST.json": manifest_bytes}.items():
        info = tarfile.TarInfo(p)
        info.size = len(b)
        info.mode = 0o644
        info.mtime = 0
        tar.addfile(info, io.BytesIO(b))
with tarfile.open(archive, "r:gz") as tar:
    members = tar.getmembers()
    assert {m.name for m in members} == set(content) | {"_P2C_REPLAY_MANIFEST.json"}
    assert len(members) == len(content) + 1 and all(m.isfile() for m in members)
    for m in members:
        b = tar.extractfile(m).read()
        assert b == (manifest_bytes if m.name == "_P2C_REPLAY_MANIFEST.json" else content[m.name])
for p, b in content.items():
    assert (ROOT / p).read_bytes() == b, f"input drift: {p}"
verification = {"pass": True, "archive_sha256": sha(archive.read_bytes()), "archive_bytes": archive.stat().st_size,
                "file_count": len(content), "input_cells": 14, "all_members_byte_verified": True,
                "all_originals_unchanged": True, "report_sha256": manifest["report_sha256"]}
(audit / "archive-verification.json").write_text(json.dumps(verification, indent=2) + "\n")
print(json.dumps(verification, indent=2))
