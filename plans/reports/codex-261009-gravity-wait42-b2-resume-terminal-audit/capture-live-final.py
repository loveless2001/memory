"""Read-only terminal snapshot; no deployment, dispatch, cleanup, evaluation, or remote write."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys

REPORT = Path(__file__).resolve().parent
ROOT = Path("/home/lenovo/projects/memory-occupied-fill-v1-worktree")
PLAN = ROOT / "plans/261009-1135-m4-sgm-p2p5-b2-occupied-fill-long-run"
os.chdir(ROOT)
spec = importlib.util.spec_from_file_location("b2_terminal", ROOT / "modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-resume-runner.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
meta = json.loads((PLAN / "b2-resume-v1/run.json").read_text())
snapshot = {"capture_started": datetime.now(timezone.utc).isoformat(), "launch": meta}
starts = R.modal.Dict.from_name(R.START_DICT)
snapshot["dict"] = {k: starts.get(k) for k in ["deadline", "start-1", "start-2", "start-3", R.RESUME_KEY]}
snapshot["call_state"], snapshot["call_info"] = R.call_state(meta["call_id"])
assert snapshot["call_state"] == "done", snapshot["call_state"]
assert snapshot["call_info"] == json.loads((PLAN / "b2-resume-v1/call_result.json").read_text())
files = []
for entry in R.volume.listdir(R.RUN_REL, recursive=True):
    if entry.type != R.modal.volume.FileEntryType.FILE:
        continue
    rel = entry.path.lstrip("/").removeprefix(R.RUN_REL + "/")
    assert not PurePosixPath(rel).is_absolute() and ".." not in PurePosixPath(rel).parts
    if rel.endswith(".tmp"):
        files.append({"path": rel, "skipped_temporary": True})
        continue
    dest = REPORT / "volume" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with dest.open("xb") as f:
        for chunk in R.volume.read_file(entry.path):
            f.write(chunk)
            h.update(chunk)
    local = PLAN / "b2-resume-v1/volume" / R.RUN_REL / rel
    local_match = local.is_file() and hashlib.sha256(local.read_bytes()).hexdigest() == h.hexdigest()
    if local.exists():
        assert local_match, rel
    files.append({"path": rel, "bytes": dest.stat().st_size, "sha256": h.hexdigest(),
                  "matches_owner_collected_file": local_match if local.exists() else None})
snapshot["files"] = files
snapshot["capture_finished"] = datetime.now(timezone.utc).isoformat()
(REPORT / "live-snapshot.json").write_text(json.dumps(snapshot, indent=2, default=str))
receipts = REPORT / "owner-receipts"
receipts.mkdir()
for source in [
    *sorted(PLAN.glob("b2-resume-v1.*")),
    *sorted((PLAN / "b2-resume-v1").glob("*.json")),
    PLAN / "b2-final-readout.md",
    PLAN / "SHA256SUMS-b2-resume-package-v0.4.txt",
]:
    if source.is_file():
        shutil.copy2(source, receipts / source.name)

billing = subprocess.run([sys.executable, "-m", "modal", "billing", "report", "--for", "today",
                          "--resolution", "h", "--show-resources", "--json"],
                         text=True, capture_output=True, timeout=60)
(REPORT / "billing-hourly-raw.json").write_text(billing.stdout)
(REPORT / "billing-hourly.stderr.txt").write_text(billing.stderr)
(REPORT / "billing-receipt.json").write_text(json.dumps({
    "returncode": billing.returncode, "captured_at": datetime.now(timezone.utc).isoformat(),
    "command": ["modal", "billing", "report", "--for", "today", "--resolution", "h", "--show-resources", "--json"]
}, indent=2))
billing.check_returncode()
print(json.dumps({"call_state": snapshot["call_state"], "call_info": snapshot["call_info"],
                  "dict": snapshot["dict"], "captured_files": len(files),
                  "capture_finished": snapshot["capture_finished"], "billing_returncode": billing.returncode}, indent=2))

