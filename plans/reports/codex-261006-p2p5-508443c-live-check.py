"""Read-only shutdown, unconsumed profile and billing verification."""
import dataclasses
import json
import subprocess
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import modal
from modal.experimental import get_app_lifecycle

ROOT = Path(__file__).resolve().parents[2]
APP = "ap-550Raz3HVjefV149OWcrXu"
OBJECTS = {APP, "im-0XrXDp0cVeNVmwutXxnq4E", "im-tZEhGIaVTsgX4GyCjTKvex", "ap-i4m6Qy73vjSs8LVFZza8Z6"}


def cli(*args):
    proc = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "modal", *args, "--json"],
                          capture_output=True, text=True, check=True, timeout=45, cwd=ROOT)
    return json.loads(proc.stdout)


def main():
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "read_only": True,
              "failed_app_id": APP}
    apps = cli("app", "list")
    containers = cli("container", "list")
    matches = [row for row in apps if row["app_id"] == APP]
    matching_containers = [row for row in containers if row["app_id"] == APP]
    report["app_rows"] = matches
    report["matching_containers"] = matching_containers
    report["lifecycle"] = dataclasses.asdict(get_app_lifecycle(APP))
    assert matches and all(row["state"].lower() == "stopped" and int(row["tasks"]) == 0 for row in matches)
    assert not matching_containers
    report["guard_states"] = {}
    for name in ("m4-sgm-p2p5-l40s-profile-v1-guard", "m4-sgm-p2p5-l40s-profile-v1-attempts"):
        try:
            keys = list(modal.Dict.from_name(name, create_if_missing=False).keys())
            report["guard_states"][name] = {"exists": True, "keys": keys}
        except modal.exception.NotFoundError:
            report["guard_states"][name] = {"exists": False}
    report["profile_output_exists"] = (ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-l40s-profile-v1").exists()
    assert not report["profile_output_exists"]
    assert all(not state["exists"] for state in report["guard_states"].values())
    rows = modal.Workspace.from_context().billing.report(start=datetime(2026, 10, 6, tzinfo=timezone.utc),
                                                        end=datetime(2026, 10, 7, tzinfo=timezone.utc), resolution="h")
    report["billing_rows"] = [dataclasses.asdict(row) for row in rows if row.object_id in OBJECTS]
    report["failed_app_and_image_observed_cost_usd"] = str(sum((row.cost for row in rows if row.object_id in OBJECTS - {"ap-i4m6Qy73vjSs8LVFZza8Z6"}), Decimal(0)))
    report["billing_note"] = "Object-filtered reported usage at check time; missing rows are not evidence of settled zero cost. Keep reserves for proof and failed deployment."
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
