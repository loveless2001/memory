"""Independent final all-app shutdown refresh; only read-only CLI/Dict calls."""
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import modal

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
export_path = PLAN / "pk-campaign-launch/attempt-2/98-stop-controller-r2-bound-verified.json"
export = json.loads(export_path.read_text())
launch = json.loads((OUT.parent / "codex-261007-p2p5-pk-21716-readings-launch-audit/launch-verification.json").read_text())
ids = {v["app_id"] for v in launch["registry"].values()} | {launch["control"]["app_id"], "ap-eqwdT119XvSoBJC1I2kDqC"}


def cli(kind):
    r = subprocess.run([sys.executable, "-m", "modal", kind, "list", "--env", "main", "--json"],
                       check=True, capture_output=True, text=True, timeout=50)
    (OUT / f"final-live-{kind}s.json").write_text(r.stdout)
    return kind, json.loads(r.stdout)


def read_dict(name):
    return dict(modal.Dict.from_name(name, environment_name="main", create_if_missing=False).items())


with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    live = dict(pool.map(cli, ("app", "container")))
names = ("m4-sgm-p2p5-pk-campaign-control-guard-r2", "m4-sgm-p2p5-pk-campaign-control-registry-r2",
         "m4-sgm-p2p5-pk-campaign-control-guard-r2-ticks")
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    guard, registry, ticks = list(pool.map(read_dict, names))
app_rows = [r for r in live["app"] if r["app_id"] in ids]
containers = [r for r in live["container"] if r["app_id"] in ids]
checks = {"all12_campaign_apps_stopped_or_unlisted": len(ids) == 12 and not containers
              and all(r["state"] == "stopped" and str(r["tasks"]) == "0" for r in app_rows),
          "guard_and_registry_unchanged": guard == export["guard"] == launch["control"]
              and registry == export["registry"] == launch["registry"],
          "exported_ticks_retained": all(ticks.get(k) == v for k, v in export["ticks"].items())
              and len(ticks) >= export["ticks_count"],
          "owner_bound_stop_verified": export["verification"]["app_id"] == guard["app_id"]
              and export["verification"]["verified"] is True
              and hashlib.sha256(export_path.read_bytes()).hexdigest().startswith("0c68fd0f")}
result = {"status": "PASS" if all(checks.values()) else "REVIEW", "checks": checks,
          "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "campaign_app_ids": sorted(ids),
          "campaign_app_rows": app_rows, "campaign_containers": containers,
          "control": guard, "registry": registry, "ticks_count": len(ticks), "exported_ticks_count": export["ticks_count"],
          "owner_stop_evidence_sha256": hashlib.sha256(export_path.read_bytes()).hexdigest(),
          "remote_mutations": 0, "billing_status": "preliminary app-attributed arithmetic verified; final reconciliation pending"}
(OUT / "all-stopped-check.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: result[k] for k in ("status", "checks", "completed_utc", "ticks_count", "campaign_app_rows", "campaign_containers")}))
assert all(checks.values()), checks
