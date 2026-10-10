"""Independently validate dev run 1 artifacts and read-only Modal terminal state."""
import dataclasses
import hashlib
import json
import math
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import modal
from modal.experimental import get_app_lifecycle

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "plans/reports/codex-261006-p2p5-dev-run1-terminal-check.json"
RUN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/dev-gpu/hotspot-l40s-v1"
APP = "ap-UUv74AxrTl2LhmY6g128Jk"
REFERENCE = "048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6"


def cli(*args):
    p = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "modal", *args, "--json"],
                       cwd=ROOT, capture_output=True, text=True, check=True, timeout=45)
    rows = json.loads(p.stdout)
    assert isinstance(rows, list)
    return rows


def main():
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "read_only_remote": True,
              "app_id": APP, "historical_artifacts_modified": False}
    meta = json.loads((RUN / "run.json").read_text())
    data = json.loads((RUN / "result/hotspot.json").read_text())
    assert meta["app_id"] == APP and meta["returncode"] == 0
    assert all(math.isfinite(meta[k]) and meta[k] > 0 for k in ("wall_s", "client_wall_s"))
    assert meta["wall_s"] <= meta["client_wall_s"] < 1500
    assert data["status"] == "complete" and data["memsub_source_sha256"] == REFERENCE
    assert data["tf32_matmul"] is False and data["gpu"] == "NVIDIA L40S"
    assert [(c["arm"], c["batch"]) for c in data["configs"]] == [
        ("learned", 16), ("memory_off", 16), ("learned", 2)]
    configs = []
    for c in data["configs"]:
        assert c["n_bindings"] == 32 and c["train_filler_len"] == 0
        assert len(c["measured"]) == 2
        for row in c["measured"]:
            assert all(math.isfinite(row[k]) and row[k] >= 0 for k in ("s", "bwd_s"))
            assert row["bwd_s"] <= row["s"]
        means = {"mean_s_per_update": sum(r["s"] for r in c["measured"]) / 2,
                 "mean_bwd_s": sum(r["bwd_s"] for r in c["measured"]) / 2}
        assert all(math.isclose(v, c[k], rel_tol=1e-12) for k, v in means.items())
        assert math.isfinite(c["profiled_update_s_with_profiler"]) and c["profiled_update_s_with_profiler"] > 0
        assert c["peak_allocated_bytes"] > 0
        configs.append({k: c[k] for k in ("arm", "batch", "mean_s_per_update", "mean_bwd_s",
                        "profiled_update_s_with_profiler", "autograd_nodes_total",
                        "cuda_kernels_in_profiled_update", "host_sync_ops")})
    report["configs"] = configs
    report["artifact_binding"] = []
    for path in sorted(p for p in RUN.rglob("*") if p.is_file()):
        rel = str(path.relative_to(ROOT))
        blob = subprocess.run(["git", "show", "add8142:" + rel], cwd=ROOT, capture_output=True, check=True).stdout
        assert blob == path.read_bytes(), rel
        report["artifact_binding"].append({"path": rel, "sha256": hashlib.sha256(blob).hexdigest(),
                                           "matches_commit": "add8142"})
    report["launched_source_binding"] = {}
    for rel, expected in {
        "modal-runners/modal-m4-sgm-p2p5-dev-gpu-test-runner.py": "52b3da22236527c20319cbbb28958ec936635e7fab1fc2239513944f10a0fe38",
        "scripts/sgm-p2p5-sgm-path-hotspot-profile.py": "c4f6e77e70797a328797c382fa96d69164f04690e45d6d427b05ff44bdc96d82",
    }.items():
        blob = subprocess.run(["git", "show", "19f51b9:" + rel], cwd=ROOT, capture_output=True, check=True).stdout
        assert hashlib.sha256(blob).hexdigest() == expected
        report["launched_source_binding"][rel] = expected
    report["source_binding_limit"] = "Original app was already in flight at review; runner/script hashes bind the reviewed 19f51b9 source, not a remote self-hash. Artifact itself records the reference memsub hash."
    report["completeness_limit"] = "Original hotspot source implies 1 warmup + 2 measured + 1 profiled update per config, but artifact lacks complete update-index rows. No rows reconstructed."
    report["accepted_as_complete_dev_diagnostic"] = True
    report["interpretation_limit"] = "Counts are profiler observations. Zero labelled CPU totals cannot identify critical-path time. Batch-2 learned versus batch-16 memory-off is confounded; no GPU speed-up, registered retiming, learning, or laptop crash-cause claim."
    with ThreadPoolExecutor(max_workers=2) as pool:
        app_future = pool.submit(cli, "app", "list")
        container_future = pool.submit(cli, "container", "list")
        apps, containers = app_future.result(), container_future.result()
    assert all("app_id" in r and "state" in r and "tasks" in r for r in apps)
    assert all("app_id" in r for r in containers)
    report["app_rows"] = [r for r in apps if r["app_id"] == APP]
    report["matching_containers"] = [r for r in containers if r["app_id"] == APP]
    report["lifecycle"] = dataclasses.asdict(get_app_lifecycle(APP))
    assert report["app_rows"] and all(r["state"].lower() == "stopped" and int(r["tasks"]) == 0
                                      for r in report["app_rows"])
    assert not report["matching_containers"] and report["lifecycle"]["stopped_at"] is not None
    rows = modal.Workspace.from_context().billing.report(
        start=datetime(2026, 10, 6, tzinfo=timezone.utc),
        end=datetime(2026, 10, 7, tzinfo=timezone.utc), resolution="h")
    report["billing_rows"] = [dataclasses.asdict(r) for r in rows if r.object_id == APP]
    report["reported_app_usage_usd"] = str(sum((r.cost for r in rows if r.object_id == APP), Decimal(0)))
    report["billing_limit"] = "App-only reported usage snapshot, not final invoice or proof of settled build cost. Full $1.55 run-1 reserve remains booked."
    report["terminal_verified"] = True
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps({k: report[k] for k in ("accepted_as_complete_dev_diagnostic", "terminal_verified",
                                            "reported_app_usage_usd", "finished_at_utc")}))


if __name__ == "__main__":
    main()
