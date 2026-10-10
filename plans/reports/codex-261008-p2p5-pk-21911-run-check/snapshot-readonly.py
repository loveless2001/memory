"""One read-only Modal snapshot; no remote create, spawn, collect or stop."""
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
APP = "memsub-m4-sgm-p2p5-readout-probe"
GROUP = "m4-sgm/p2p5-readout-probe-v1/taskhead-learned-n32"
LOCAL = ROOT / "plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe/p2p5-readout-probe-v1/taskhead-learned-n32"
prov = json.loads((LOCAL / "launch_provenance.json").read_text())
call = json.loads((LOCAL / "call.json").read_text())["call_id"]
snapshot = {"started_utc": datetime.now(timezone.utc).isoformat(), "modal_version": modal.__version__,
            "expected_app_id": prov["deployed_app_id"], "call_id": call, "remote_mutations": False}

def save():
    (OUT / "live-snapshot.json").write_text(json.dumps(snapshot, indent=2, default=str) + "\n")

def cli(kind):
    argv = [sys.executable, "-m", "modal", kind, "list", "--json"]
    p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=60)
    (OUT / f"live-{kind}-list.json").write_text(p.stdout)
    (OUT / f"live-{kind}-list.stderr").write_text(p.stderr)
    try:
        rows = json.loads(p.stdout)
        selected = [r for r in rows if r.get("app_id") == prov["deployed_app_id"]]
    except Exception as e:
        selected = {"error": repr(e)}
    return {"argv": argv, "rc": p.returncode, "probe_rows": selected}

with ThreadPoolExecutor(max_workers=2) as pool:
    snapshot["inventory"] = dict(zip(("app", "container"), pool.map(cli, ("app", "container"))))
save()
try:
    snapshot["bound_app_id"] = modal.App.lookup(APP, environment_name="main").app_id
except Exception as e:
    snapshot["bound_app_lookup_error"] = repr(e)
snapshot["dicts"] = {}
for key in ("guard", "admission"):
    try:
        snapshot["dicts"][key] = dict(modal.Dict.from_name(f"{APP}-{key}", create_if_missing=False).items())
    except Exception as e:
        snapshot["dicts"][key] = {"error": repr(e)}
save()
try:
    snapshot["call_poll"] = {"state": "result", "result": modal.FunctionCall.from_id(call).get(timeout=0)}
except TimeoutError:
    snapshot["call_poll"] = {"state": "pending"}
except Exception as e:
    snapshot["call_poll"] = {"state": "exception", "error": repr(e)}
snapshot["stats"] = {}
for fn in ("run_slot", "reaper"):
    try:
        s = modal.Function.from_name(APP, fn).get_current_stats()
        snapshot["stats"][fn] = {k: getattr(s, k) for k in ("backlog", "num_total_runners", "num_idle_runners") if hasattr(s, k)}
    except Exception as e:
        snapshot["stats"][fn] = {"error": repr(e)}
save()
vol = modal.Volume.from_name("memsub-artifacts", create_if_missing=False)
snapshot["fetched"] = {}
for cell in ("taskhead-learned-n32-s0", "taskhead-learned-n32-s1"):
    for rel in ("state.json", "attempt-1/worker-args.json", "attempt-1/physical-updates.jsonl"):
        remote = f"{GROUP}/cells/{cell}/epoch-1/{rel}"
        local = OUT / "remote-metadata" / cell / rel
        try:
            data = b"".join(vol.read_file(remote))
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(data)
            snapshot["fetched"][remote] = {"local": str(local.relative_to(OUT)), "bytes": len(data),
                                             "sha256": hashlib.sha256(data).hexdigest()}
        except Exception as e:
            snapshot["fetched"][remote] = {"error": repr(e)}
        save()
snapshot["ended_utc"] = datetime.now(timezone.utc).isoformat()
save()
print(json.dumps({k:v for k,v in snapshot.items() if k != "fetched"}, indent=2, default=str))
