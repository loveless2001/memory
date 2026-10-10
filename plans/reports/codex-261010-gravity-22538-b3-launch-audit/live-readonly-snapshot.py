"""Read an existing B3 call, Dict and Volume; never create or invoke a worker."""
import datetime
import json
from pathlib import Path
import modal

DEST = Path(__file__).parent
SNAP = DEST / "live-snapshot"
SNAP.mkdir(exist_ok=True)
rec = {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "errors": {}}
try:
    call = modal.FunctionCall.from_id("fc-01M4HWABMJ4SHV1CRX72J7WTMM")
    try:
        rec["call"] = {"state": "returned", "result": call.get(timeout=0)}
    except TimeoutError:
        rec["call"] = {"state": "running"}
except Exception as e:
    rec["errors"]["call"] = f"{type(e).__name__}: {e}"
try:
    starts = modal.Dict.from_name("m4-sgm-p2p5-b3-shift2-fill-long-starts-v1", create_if_missing=False)
    rec["dict"] = dict(starts.items())
except Exception as e:
    rec["errors"]["dict"] = f"{type(e).__name__}: {e}"
try:
    vol = modal.Volume.from_name("memsub-m4-sgm-p2p5-b3-shift2-fill-long-v1", create_if_missing=False)
    files = list(vol.iterdir("b3-run-v1", recursive=True))
    rec["files"] = [{"path": x.path, "size": x.size, "type": str(x.type)} for x in files]
    wanted = {
        "b3-run-v1/campaign.json", "b3-run-v1/B3.starts.jsonl",
        "b3-run-v1/B3/identity.json", "b3-run-v1/B3/routing_telemetry.jsonl",
        "b3-run-v1/B3.start-1.stdout.txt", "b3-run-v1/B3.start-1.stderr.txt",
        "b3-run-v1/B3/b3_result.json",
    }
    rec["fetched"] = []
    for entry in files:
        rel = entry.path.lstrip("/")
        if rel in wanted and entry.size <= 1024 * 1024:
            data = b"".join(vol.read_file(entry.path))
            dest = SNAP / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            rec["fetched"].append({"path": rel, "bytes": len(data)})
except Exception as e:
    rec["errors"]["volume"] = f"{type(e).__name__}: {e}"
rec["utc_done"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
(DEST / "live-snapshot.json").write_text(json.dumps(rec, indent=2, default=str) + "\n")
print(json.dumps(rec, indent=2, default=str))
