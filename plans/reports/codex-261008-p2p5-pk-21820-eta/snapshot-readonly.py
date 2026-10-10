"""Read existing Modal objects and tiny committed cell metadata. No collect, stop, spawn, or writes remotely."""
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


def cli(kind):
    argv = [sys.executable, "-m", "modal", kind, "list", "--json"]
    p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=60)
    (OUT / f"live-{kind}-list.json").write_text(p.stdout)
    (OUT / f"live-{kind}-list.stderr").write_text(p.stderr)
    assert p.returncode == 0, (kind, p.stderr)
    rows = json.loads(p.stdout)
    assert isinstance(rows, list)
    return {"argv": argv, "rc": p.returncode, "probe_rows": [r for r in rows if r.get("app_id") == prov["deployed_app_id"]]}


with ThreadPoolExecutor(max_workers=2) as pool:
    inventory = dict(zip(("app", "container"), pool.map(cli, ("app", "container"))))
bound = modal.App.lookup(APP, environment_name="main").app_id
assert bound == prov["deployed_app_id"]
dicts = {k: dict(modal.Dict.from_name(f"{APP}-{k}", create_if_missing=False).items()) for k in ("guard", "admission")}
try:
    result = modal.FunctionCall.from_id(call).get(timeout=0)
    poll = {"state": "result", "result": result}
except TimeoutError:
    poll = {"state": "pending"}
except Exception as e:
    poll = {"state": "exception", "error": repr(e)}
stats = {}
for fn in ("run_slot", "reaper"):
    s = modal.Function.from_name(APP, fn).get_current_stats()
    stats[fn] = {k: getattr(s, k) for k in ("backlog", "num_total_runners", "num_idle_runners") if hasattr(s, k)}

vol = modal.Volume.from_name("memsub-artifacts", create_if_missing=False)
fetched = {}
for cell in ("taskhead-learned-n32-s0", "taskhead-learned-n32-s1"):
    for rel in ("state.json", "attempt-1/worker-args.json"):
        remote = f"{GROUP}/cells/{cell}/epoch-1/{rel}"
        local = OUT / "remote-metadata" / cell / rel
        try:
            data = b"".join(vol.read_file(remote))
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(data)
            fetched[remote] = {"local": str(local.relative_to(OUT)), "bytes": len(data)}
        except Exception as e:
            fetched[remote] = {"error": repr(e)}
snapshot = {"at_utc": datetime.now(timezone.utc).isoformat(), "bound_app_id": bound,
            "modal_version": modal.__version__, "inventory": inventory, "dicts": dicts,
            "call_id": call, "call_poll": poll, "stats": stats, "fetched": fetched,
            "remote_mutations": False}
(OUT / "live-snapshot.json").write_text(json.dumps(snapshot, indent=2, default=str) + "\n")
print(json.dumps(snapshot, indent=2, default=str))
