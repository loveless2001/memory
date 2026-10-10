"""Preserve P2G consumed inputs and audit evidence without changing originals."""
import gzip
import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "plans/261006-0010-m4-sgm-p2g-selective-write-gate/readings-v1"
REPORT = json.loads((BUNDLE / "p2g-readings.json").read_text())
INDEX = json.loads((ROOT / "configs/m4_sgm_p2g_inputs.json").read_text())


def sha(b):
    return hashlib.sha256(b).hexdigest()


sources = {
    "independent-results-check.py": "codex-261006-p2g-results-independent-audit.py",
    "independent-results-check.json": "codex-261006-p2g-results-independent-audit.json",
    "training-artifacts-check.json": "codex-261006-p2g-training-artifacts-audit.json",
    "lifecycle-billing-check.json": "codex-261006-p2g-final-lifecycle-billing-audit.json",
    "approved-launch-clearance.json": "codex-261006-p2g-approved-launch-clearance.json",
    "spawn-verification.json": "codex-261006-p2g-spawn-verification.json",
}
audit = BUNDLE / "audit"
audit.mkdir(exist_ok=False)
for dest, name in sources.items():
    shutil.copyfile(ROOT / "plans/reports" / name, audit / dest)

paths = {BUNDLE / "p2g-readings.json", Path(__file__).resolve()}
paths.update(BUNDLE.glob("rows-*.jsonl"))
paths.update((BUNDLE / "parity").glob("*.jsonl"))
paths.update(ROOT / "plans/reports" / name for name in sources.values())
paths.update(ROOT / p for p in REPORT["observer"]["analysis_sha256"])
paths.update(p for p in (ROOT / "memsub").rglob("*.py") if "pycache" not in p.parent.name)
paths.update(ROOT / p for p in ("configs/m4_sgm_p2g_grid.json", "configs/m4_sgm_p2g_inputs.json",
    "plans/261006-0010-m4-sgm-p2g-selective-write-gate/prereg.md",
    "plans/261006-0010-m4-sgm-p2g-selective-write-gate/readings-v1.log"))
cells = {ROOT / c["cell"] for c in REPORT["p2g_cells"].values()} | {ROOT / c["cell"] for c in INDEX["reused"].values()}
assert len(cells) == 12
required = ("run_manifest.json", "trained_parameters.safetensors", "metrics.json", "per_example_results.jsonl",
            "split_manifest.json", "routing_telemetry.jsonl", "report.md")
for cell in cells:
    paths.update(cell / f for f in required)
for entries in INDEX["parity"].values():
    paths.update(ROOT / e["reference"] for e in entries)
runs = ROOT / "plans/261005-0210-m4-sgm-p0-p2/runs/p2g-selective-write-v1"
paths.update(runs / f for f in ("grid.json", "launch_provenance.json", "calls.json", "collect_status.json", "artifact_validation.json"))
for rid in REPORT["p2g_cells"]:
    paths.update(runs / rid / f for f in ("metrics.json", "per_example_results.jsonl"))
content = {str(p.relative_to(ROOT)): p.read_bytes() for p in sorted(paths)}
manifest = {"report_sha256": sha((BUNDLE / "p2g-readings.json").read_bytes()),
            "observer_commit": REPORT["observer"]["git_head"], "input_cells": 12,
            "files": [{"repo_path": p, "sha256": sha(b), "bytes": len(b)} for p, b in content.items()],
            "replay": "Extract into an isolated checkout containing observer commit 2613ced; run plans/reports/codex-261006-p2g-results-independent-audit.py with the pinned environment. The verifier uses saved reserved-seed rows and development seed 4242 only."}
manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
(BUNDLE / "replay-evidence-manifest.json").write_bytes(manifest_bytes)
archive = BUNDLE / "replay-evidence.tar.gz"
with archive.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as gz, tarfile.open(fileobj=gz, mode="w") as tar:
    for p, b in {**content, "_P2G_REPLAY_MANIFEST.json": manifest_bytes}.items():
        info = tarfile.TarInfo(p)
        info.size = len(b)
        info.mode = 0o644
        info.mtime = 0
        tar.addfile(info, io.BytesIO(b))
with tarfile.open(archive, "r:gz") as tar:
    members = tar.getmembers()
    assert {m.name for m in members} == set(content) | {"_P2G_REPLAY_MANIFEST.json"}
    assert len(members) == len(content) + 1 and all(m.isfile() for m in members)
    for m in members:
        b = tar.extractfile(m).read()
        assert b == (manifest_bytes if m.name == "_P2G_REPLAY_MANIFEST.json" else content[m.name])
for p, b in content.items():
    assert (ROOT / p).read_bytes() == b, f"input drift: {p}"
verification = {"pass": True, "archive_sha256": sha(archive.read_bytes()), "archive_bytes": archive.stat().st_size,
                "file_count": len(content), "input_cells": 12, "all_members_byte_verified": True,
                "all_originals_unchanged": True, "report_sha256": manifest["report_sha256"]}
(audit / "archive-verification.json").write_text(json.dumps(verification, indent=2) + "\n")
print(json.dumps(verification, indent=2))
