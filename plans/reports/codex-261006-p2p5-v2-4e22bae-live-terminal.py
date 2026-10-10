"""Read-only terminal verification for the one approved v2 profiling app."""
import dataclasses
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import modal
from modal.experimental import get_app_lifecycle

ROOT = Path(__file__).resolve().parents[2]
APP = "ap-Fs085d1acB4y3NbGlwEz3W"
OUT = ROOT / "plans/reports/codex-261006-p2p5-v2-4e22bae-live-terminal.json"


def cli(*args):
    p = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "modal", *args, "--json"],
                       cwd=ROOT, capture_output=True, text=True, check=True, timeout=45)
    return json.loads(p.stdout)


def main():
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "app_id": APP, "read_only_remote": True, "modal_version": modal.__version__}
    assert modal.__version__ == "1.5.1"
    with ThreadPoolExecutor(max_workers=2) as pool:
        af, cf = pool.submit(cli, "app", "list"), pool.submit(cli, "container", "list")
        apps, containers = af.result(), cf.result()
    assert all("app_id" in a and "state" in a and "tasks" in a for a in apps)
    assert all("app_id" in c for c in containers)
    scoped_apps = [a for a in apps if a["app_id"] == APP]
    scoped_containers = [c for c in containers if c["app_id"] == APP]
    assert scoped_apps and all(a["state"].lower() == "stopped" and int(a["tasks"]) == 0 for a in scoped_apps)
    assert scoped_containers == []
    lifecycle = dataclasses.asdict(get_app_lifecycle(APP))
    assert lifecycle["stopped_at"] is not None
    report.update(app_rows=scoped_apps, container_rows=scoped_containers, lifecycle=lifecycle)
    for name in ("m4-sgm-p2p5-l40s-profile-v2-guard", "m4-sgm-p2p5-l40s-profile-v2-attempts"):
        store = modal.Dict.from_name(name, create_if_missing=False)
        report[name] = dict(store.items())
    guard = report["m4-sgm-p2p5-l40s-profile-v2-guard"]
    assert guard["app_id"] == APP and guard["call_id"] == "fc-01M48WAHVDC6610H89B5B382V9"
    assert "start1" in guard and "start2" not in guard
    assert report["m4-sgm-p2p5-l40s-profile-v2-attempts"] == {"profile-l40s#attempt1": True}
    rows = modal.Workspace.from_context().billing.report(
        start=datetime(2026, 10, 6, tzinfo=timezone.utc),
        end=datetime(2026, 10, 7, tzinfo=timezone.utc), resolution="h")
    scoped = [r for r in rows if r.object_id == APP]
    report["billing_rows"] = [dataclasses.asdict(r) for r in scoped]
    report["reported_app_usage_usd"] = str(sum((r.cost for r in scoped), Decimal(0)))
    report["billing_is_snapshot_not_settled_total"] = True
    report["reserve_retained_usd"] = "2.3844246"
    report["shutdown_verified"] = True
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    OUT.write_text(json.dumps(report, indent=2, default=str, allow_nan=False) + "\n")
    print(json.dumps({k: report[k] for k in ("shutdown_verified", "app_rows",
                      "reported_app_usage_usd", "finished_at_utc")}, indent=2))


if __name__ == "__main__":
    main()
