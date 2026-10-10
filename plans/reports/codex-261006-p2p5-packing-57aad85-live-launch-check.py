"""Read-only launch verification for the approved single packing run."""
import dataclasses
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import modal
from modal.experimental import get_app_lifecycle

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/dev-gpu"
RUN = BASE / "packing-a100-v1"
OUT = ROOT / "plans/reports/codex-261006-p2p5-packing-57aad85-live-launch-state.json"
APP = "ap-uPN6X6TfZ7Yv9lCaLHAkx7"


def cli(noun):
    p = subprocess.run([str(ROOT/".venv/bin/python"),"-m","modal",noun,"list","--json"],
                       cwd=ROOT,check=True,capture_output=True,text=True,timeout=45)
    return json.loads(p.stdout)


def main():
    report = {"checked_at_utc":datetime.now(timezone.utc).isoformat(),"read_only_remote":True,
              "app_id":APP,"modal_version":modal.__version__}
    assert modal.__version__=="1.5.1"
    meta = json.loads((RUN/"run.json").read_text())
    launch = (BASE/"packing-a100-v1.launch-time.txt").read_text().splitlines()
    assert launch == ["2026-10-06T22:46:12+07:00","57aad8581579c9fd17ba70490e0d817567cedb59"]
    assert meta["app_id"]==APP and meta["gpu"]=="A100-80GB" and meta["args"]==""
    assert meta["script"]=="scripts/sgm-p2p5-gpu-packing-concurrent-training-throughput-test.py"
    hashes={}
    for rel in (meta["script"],"modal-runners/modal-m4-sgm-p2p5-dev-gpu-test-runner.py"):
        raw=(ROOT/rel).read_bytes()
        assert raw==subprocess.check_output(["git","show","57aad85:"+rel],cwd=ROOT)
        hashes[rel]=hashlib.sha256(raw).hexdigest()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a,c=pool.submit(cli,"app"),pool.submit(cli,"container")
        apps,containers=a.result(),c.result()
    assert all("app_id" in r and "state" in r and "tasks" in r for r in apps)
    assert all("app_id" in r for r in containers)
    scoped_apps=[r for r in apps if r["app_id"]==APP]
    scoped_containers=[r for r in containers if r["app_id"]==APP]
    assert len(scoped_apps)==1
    lifecycle=dataclasses.asdict(get_app_lifecycle(APP))
    console=(BASE/"packing-a100-v1.console.log").read_text()
    exits=[s for s in console.splitlines() if s.startswith("EXIT_STATUS=")]
    active=scoped_apps[0]["state"].lower()!="stopped" and int(scoped_apps[0]["tasks"])>0 and bool(scoped_containers)
    report.update(run_manifest=meta,launch_provenance=launch,source_sha256=hashes,
                  app_rows=scoped_apps,container_rows=scoped_containers,lifecycle=lifecycle,
                  active_app_with_task_and_container=active,wrapper_exit_rows=exits,
                  terminal_packing_artifact_exists=(RUN/"result/packing.json").exists(),
                  console_contains_building_image="Building image" in console,
                  reservation_usd="1.98",envelope_usd="2.00",
                  limits=["Active app/task/container is lifecycle evidence, not a throughput result or proof that the child has completed model loading.",
                          "Reservation is retained; no settled billing or additional paid work is inferred.",
                          "No CLI command-line attestation: source, launch provenance, selected GPU manifest and live app state are independently checked."],
                  finished_at_utc=datetime.now(timezone.utc).isoformat())
    OUT.write_text(json.dumps(report,indent=2,default=str)+"\n")
    print(json.dumps({k:report[k] for k in ("active_app_with_task_and_container","app_rows","container_rows",
        "terminal_packing_artifact_exists","wrapper_exit_rows","finished_at_utc")},indent=2))


if __name__=="__main__":
    main()
