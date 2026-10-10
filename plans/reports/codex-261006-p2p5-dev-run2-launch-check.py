"""Read-only verification of the already launched option-A dev parity run."""
import ast
import dataclasses
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import modal
from modal.experimental import get_app_lifecycle

ROOT = Path(__file__).resolve().parents[2]
APP = "ap-E2KdNOH6Vb0qjnJTVdKz4U"
RUNNER = "modal-runners/modal-m4-sgm-p2p5-dev-gpu-test-runner.py"
CHECKER = "scripts/sgm-p2p5-sgm-path-speedup-parity-check.py"
DEST = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/dev-gpu/parity-qwen-gpu-v1"
OUT = ROOT / "plans/reports/codex-261006-p2p5-dev-run2-launch-check.json"


def source_hash(root):
    h = hashlib.sha256()
    for f in sorted(root.rglob("*.py")):
        if "pycache" not in f.parent.name:
            h.update(str(f.relative_to(root.parent)).encode() + b"\0")
            h.update(f.read_bytes() + b"\0")
    return h.hexdigest()


def cli(*args):
    p = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "modal", *args, "--json"],
                       cwd=ROOT, capture_output=True, text=True, check=True, timeout=45)
    return json.loads(p.stdout)


def executable_ast(source):
    tree = ast.parse(source)
    assert isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant)
    assert isinstance(tree.body[0].value.value, str)
    tree.body.pop(0)  # only the module docstring changed
    return ast.dump(tree, include_attributes=False)


def main():
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "read_only_remote": True,
              "app_id": APP, "no_launch_retry_stop_or_result_mutation": True}
    report["run_manifest"] = json.loads((ROOT / DEST / "run.json").read_text())
    assert report["run_manifest"]["app_id"] == APP
    assert report["run_manifest"]["script"] == CHECKER
    assert report["run_manifest"]["args"] == "--ref-tree dev-gpu-inputs/memsub-ref-2fda0d4 --suite qwen-gpu"
    report["candidate_memsub_sha256"] = source_hash(ROOT / "memsub")
    report["reference_memsub_sha256"] = source_hash(ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/dev-gpu/inputs/memsub-ref-2fda0d4/memsub")
    assert report["candidate_memsub_sha256"] == "b87a767baac578d94a6f778560f4fb451fd60679cca48412218adaac74f74085"
    assert report["reference_memsub_sha256"] == "048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6"
    assert hashlib.sha256((ROOT / RUNNER).read_bytes()).hexdigest() == "e7b110ae0f3ce5cdae1470fc146d895cc1c4c035783bea3934b76ca2433df05f"
    frozen = subprocess.run(["git", "show", "1306f26:" + CHECKER], cwd=ROOT,
                            capture_output=True, check=True).stdout
    current = (ROOT / CHECKER).read_bytes()
    assert executable_ast(frozen) == executable_ast(current)
    report["checker_source"] = {"frozen_sha256": hashlib.sha256(frozen).hexdigest(),
        "current_sha256": hashlib.sha256(current).hexdigest(),
        "same_executable_ast_excluding_module_docstring": True,
        "limit": "Local docstring-only correction does not establish which exact script bytes were mounted remotely. Retain original launch identity and distinguish later documentation source."}
    expected = ["timeout", "--kill-after=15s", "1200", ".venv/bin/python", "-m", "modal", "run",
                RUNNER, "--script", CHECKER, "--out", DEST, "--args",
                "--ref-tree dev-gpu-inputs/memsub-ref-2fda0d4 --suite qwen-gpu"]
    matches = []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            args = [a.decode() for a in (d / "cmdline").read_bytes().split(b"\0") if a]
            if args != expected:
                continue
            start_ticks = int((d / "stat").read_text().split()[21])
            age = float(Path("/proc/uptime").read_text().split()[0]) - start_ticks / os.sysconf("SC_CLK_TCK")
            start_epoch = time.time() - age
            matches.append({"pid": int(d.name), "argv": args, "elapsed_s": age,
                "approx_started_at_utc": datetime.fromtimestamp(start_epoch, timezone.utc).isoformat(),
                "approx_SIGTERM_at_utc": datetime.fromtimestamp(start_epoch + 1200, timezone.utc).isoformat(),
                "approx_SIGKILL_escalation_at_utc": datetime.fromtimestamp(start_epoch + 1215, timezone.utc).isoformat()})
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    report["matching_outer_timeout_processes"] = matches
    report["exact_outer_command_verified"] = len(matches) == 1
    apps, containers = cli("app", "list"), cli("container", "list")
    assert all("app_id" in r and "state" in r and "tasks" in r for r in apps)
    assert all("app_id" in r for r in containers)
    report["app_rows"] = [r for r in apps if r["app_id"] == APP]
    report["matching_containers"] = [r for r in containers if r["app_id"] == APP]
    report["lifecycle"] = dataclasses.asdict(get_app_lifecycle(APP))
    rows = modal.Workspace.from_context().billing.report(
        start=datetime(2026, 10, 6, tzinfo=timezone.utc),
        end=datetime(2026, 10, 7, tzinfo=timezone.utc), resolution="h")
    report["billing_rows"] = [dataclasses.asdict(r) for r in rows if r.object_id == APP]
    report["reported_app_usage_usd"] = str(sum((r.cost for r in rows if r.object_id == APP), Decimal(0)))
    report["local_parity_result_exists"] = (ROOT / DEST / "result/parity.json").exists()
    report["booked_reserves_usd"] = {"run1": 1.55, "run2": 1.18, "total": 2.73, "envelope": 3.0}
    report["limits"] = ["Live launch evidence is not a complete or passing GPU parity result.",
        "Reported app usage can lag and excludes unbound image/build objects; reserves remain booked.",
        "1200s is the client timeout, plus kill escalation and disconnect/teardown allowance; no shutdown verified while running.",
        "Parity train_s includes model construction and loss/gradient CPU capture; it is a dev timing signal, not registered retiming or proof of speed-up.",
        "GPU resume, campaign integration, telemetry and dev numeric fields other than accuracy remain unverified."]
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    OUT.write_text(json.dumps(report, indent=2, default=str, allow_nan=False) + "\n")
    print(json.dumps({k: report[k] for k in ("exact_outer_command_verified", "app_rows", "matching_containers",
        "reported_app_usage_usd", "local_parity_result_exists", "finished_at_utc")}, indent=2))


if __name__ == "__main__":
    main()
