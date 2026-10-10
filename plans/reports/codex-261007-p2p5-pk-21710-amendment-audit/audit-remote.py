"""Read-only pre-clearance Modal state refresh; no deploy/spawn/stop/Dict writes."""
import concurrent.futures
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

import modal

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
BASE = json.loads((OUT.parent / "codex-261007-p2p5-pk-21652-launch-verification/launch-verification.json").read_text())
PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
price = json.loads((PLAN / "pk6/priced-estimate-v6.json").read_text())
started = datetime.datetime.now(datetime.timezone.utc).isoformat()


def cli(kind):
    r = subprocess.run([sys.executable, "-m", "modal", kind, "list", "--env", "main", "--json"],
                       capture_output=True, text=True, check=True, timeout=50)
    (OUT / f"live-{kind}s.json").write_text(r.stdout)
    return kind, json.loads(r.stdout)


def read_dict(name):
    return dict(modal.Dict.from_name(name, environment_name="main", create_if_missing=False).items())


def inspect_slot(item):
    slot, previous = item
    name = previous["provenance"]["app_name"]
    guard = read_dict(name + "-guard")
    adm = read_dict(name + "-admission")
    admitted = sorted(int(k.split("-")[1]) for k in adm if k.startswith("start-"))
    app_id = previous["provenance"]["deployed_app_id"]
    apps = [r for r in live["app"] if r["app_id"] == app_id]
    containers = [r for r in live["container"] if r["app_id"] == app_id]
    valid = (guard == previous["guard"] and registry.get(name) == BASE["registry"][name]
             and 1 <= len(admitted) <= 4 and admitted == list(range(1, len(admitted) + 1))
             and not containers and all(r["state"] == "stopped" and str(r["tasks"]) == "0" for r in apps))
    return slot, {"ok": valid, "admissions": admitted, "guard": guard, "app_rows": apps, "containers": containers}


with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    live = dict(pool.map(cli, ("app", "container", "dict")))
control = read_dict("m4-sgm-p2p5-pk-campaign-control-guard-r2")
registry = read_dict("m4-sgm-p2p5-pk-campaign-control-registry-r2")
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    slots = dict(pool.map(inspect_slot, BASE["slots"].items()))
readings_id = "ap-MvPw7JVom3vnRTxVVyzldN"
readings = {"apps": [r for r in live["app"] if r["app_id"] == readings_id],
            "containers": [r for r in live["container"] if r["app_id"] == readings_id],
            "guard_admission": [r for r in live["dict"] if r["name"].startswith("memsub-m4-sgm-p2p5-pk-campaign-readings-")],
            "local_launch_dir_exists": (PLAN / "p2p5-qwen3-0p6b-screen-v1/readings").exists()}
controller_rows = [r for r in live["app"] if r["app_id"] == control["app_id"]]
latest = control["deadline_epoch"] - price["readings"]["reserve_life_s"] - 1800
now = time.time()
checks = {"all_training_apps_stopped_and_bindings_unchanged": all(s["ok"] for s in slots.values()),
          "registry_still_exactly_original_nine": registry == BASE["registry"],
          "controller_immutable": all(control.get(k) == BASE["control"].get(k)
                                      for k in ("app_id", "deadline_epoch", "price_sha256")),
          "controller_deployed": len(controller_rows) == 1 and controller_rows[0]["state"] == "deployed",
          "readings_unstarted": not readings["containers"] and not readings["guard_admission"]
              and not readings["local_launch_dir_exists"] and len(readings["apps"]) == 1
              and readings["apps"][0]["state"] == "deployed" and str(readings["apps"][0]["tasks"]) == "0",
          "existing_horizon_fits": now <= latest}
result = {"status": "PASS" if all(checks.values()) else "REVIEW", "checks": checks,
          "started_utc": started, "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "slots": slots, "control": control, "registry": registry, "controller_rows": controller_rows,
          "readings": readings, "seconds_until_latest_candidate": latest - now,
          "latest_readings_candidate_utc": datetime.datetime.fromtimestamp(latest, datetime.timezone.utc).isoformat(),
          "remote_mutations": 0, "billing_reconciliation": "not performed"}
(OUT / "remote-audit.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"status": result["status"], "checks": checks, "completed_utc": result["completed_utc"],
                  "seconds_until_latest_candidate": latest - now, "readings": readings}))
assert all(checks.values()), checks
