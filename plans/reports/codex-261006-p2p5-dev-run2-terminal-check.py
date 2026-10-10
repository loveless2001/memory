"""Validate committed dev parity artifacts and independently read terminal Modal state."""
import ast
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
BASE = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/dev-gpu"
RUN = BASE / "parity-qwen-gpu-v1"
APP = "ap-E2KdNOH6Vb0qjnJTVdKz4U"
RUN1 = "ap-UUv74AxrTl2LhmY6g128Jk"
OUT = ROOT / "plans/reports/codex-261006-p2p5-dev-run2-terminal-check.json"


def cli(*args):
    p = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "modal", *args, "--json"],
                       cwd=ROOT, capture_output=True, text=True, check=True, timeout=45)
    return json.loads(p.stdout)


def executable_ast(blob):
    tree = ast.parse(blob)
    tree.body.pop(0)
    return ast.dump(tree, include_attributes=False)


def main():
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "read_only_remote": True,
              "app_id": APP, "no_historical_artifact_mutation": True}
    meta = json.loads((RUN / "run.json").read_text())
    data = json.loads((RUN / "result/parity.json").read_text())
    assert meta["app_id"] == APP and meta["returncode"] == 0 and meta["outcome"] == "ok"
    assert meta["script"] == "scripts/sgm-p2p5-sgm-path-speedup-parity-check.py"
    assert meta["args"] == "--ref-tree dev-gpu-inputs/memsub-ref-2fda0d4 --suite qwen-gpu"
    assert 0 < meta["wall_s"] <= meta["client_wall_s"] < 1200
    assert data["suite"] == "qwen-gpu" and data["rtol"] == 1e-5 and data["pass"] is True
    assert data["ref_memsub_sha256"] == "048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6"
    assert data["cand_memsub_sha256"] == "b87a767baac578d94a6f778560f4fb451fd60679cca48412218adaac74f74085"
    expected = [("learned", 16, 0, 140), ("learned", 16, 40, 140), ("oracle", 4, 40, 108),
                ("single_cell", 4, 40, 108), ("random_fixed", 4, 40, 108), ("memory_off", 4, 40, 52)]
    assert len(data["cases"]) == len(expected)
    cases = []
    stdout_rows = [json.loads(line) for line in (RUN / "stdout.txt").read_text().splitlines()
                   if line.startswith("{")]
    assert len(stdout_rows) == 6 and (RUN / "stdout.txt").read_text().splitlines()[-1] == "PASS"
    for case, printed, (arm, batch, filler, comparisons) in zip(data["cases"], stdout_rows, expected):
        cfg = case["config"]
        assert (cfg["arm"], cfg["batch"], cfg["filler_len_schedule"]) == (arm, batch, [[0, filler]])
        assert cfg["backbone"] == "qwen3-0.6b-base" and cfg["device"] == "cuda"
        assert cfg["readout"] == "residual_head" and cfg["n_bindings"] == 32
        assert cfg["steps"] == 2 and cfg["seed"] == 99 and cfg["filler_len"] == 40
        assert cfg["eval_every"] == 10**9
        assert case["pass"] is True and case["bitwise"] is True
        assert case["n_problems"] == 0 and case["problems"] == []
        assert case["max_rel"] == 0 and case["max_abs"] == 0
        assert case["n_compared"] == comparisons and case["dev_predictions_identical"] is True
        assert case["dev_float_fields_differing"] == {}
        assert all(math.isfinite(case[k]) and case[k] > 0 for k in ("ref_train_s", "cand_train_s"))
        for k, v in printed.items():
            if k in case:
                assert v == case[k], k
        assert printed["arm"] == arm
        cases.append({"arm": arm, "batch": batch, "train_filler_len": filler,
            "steps": 2, "seed": 99, "n_compared": comparisons,
            "checked_tensor_equality_reported": True,
            "ref_train_s": case["ref_train_s"], "cand_train_s": case["cand_train_s"],
            "dev_aggregate_ref_over_candidate_ratio": case["ref_train_s"] / case["cand_train_s"]})
    assert data["self_test_perturbation_detected"] is True and data["self_test"]["pass"] is False
    assert math.isfinite(data["self_test"]["max_rel"]) and data["self_test"]["max_rel"] > data["rtol"]
    assert data["isolation"]["ok"] is True and data["isolation"]["leaks"] == []
    ref_files, cand_files = data["isolation"]["ref_modules"], data["isolation"]["cand_modules"]
    assert ref_files and cand_files
    assert all(str(f).startswith("/tmp/memsub-ref-") and "/memsub_ref/" in str(f) for f in ref_files.values())
    assert all(str(f).startswith("/root/repo/memsub/") for f in cand_files.values())
    report.update(run_manifest=meta, cases=cases, total_compared_tensor_rows=sum(c["n_compared"] for c in cases),
                  self_test=data["self_test"], isolation={"ok": True, "leaks": [],
                    "reference_module_count": len(ref_files), "candidate_module_count": len(cand_files)})
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "c17cfcc", str(BASE.relative_to(ROOT))],
                                    cwd=ROOT, text=True).splitlines()
    paths = [p for p in paths if "parity-qwen-gpu-v1" in p]
    assert len(paths) == 8
    report["artifact_binding"] = []
    for rel in paths:
        frozen = subprocess.check_output(["git", "show", "c17cfcc:" + rel], cwd=ROOT)
        assert frozen == (ROOT / rel).read_bytes(), rel
        report["artifact_binding"].append({"path": rel, "sha256": hashlib.sha256(frozen).hexdigest(),
                                           "matches_commit": "c17cfcc"})
    console = (BASE / "parity-qwen-gpu-v1.console.log").read_text()
    assert [line for line in console.splitlines() if line.startswith("EXIT_STATUS=")] == ["EXIT_STATUS=0"]
    report["console_has_building_image_line"] = "Building image" in console
    rel = "scripts/sgm-p2p5-sgm-path-speedup-parity-check.py"
    frozen = subprocess.check_output(["git", "show", "1306f26:" + rel], cwd=ROOT)
    current = (ROOT / rel).read_bytes()
    assert executable_ast(frozen) == executable_ast(current)
    report["checker_source_binding"] = {"launched_identity": "1306f26",
        "frozen_sha256": hashlib.sha256(frozen).hexdigest(), "documentation_sha256": hashlib.sha256(current).hexdigest(),
        "same_executable_ast_excluding_module_docstring": True}
    with ThreadPoolExecutor(max_workers=2) as pool:
        app_future, container_future = pool.submit(cli, "app", "list"), pool.submit(cli, "container", "list")
        apps, containers = app_future.result(), container_future.result()
    assert all("app_id" in r and "state" in r and "tasks" in r for r in apps)
    assert all("app_id" in r for r in containers)
    report["scoped_apps_terminal"] = {}
    for app_id in (APP, RUN1):
        matching_apps = [r for r in apps if r["app_id"] == app_id]
        matching_containers = [r for r in containers if r["app_id"] == app_id]
        lifecycle = dataclasses.asdict(get_app_lifecycle(app_id))
        assert matching_apps and all(r["state"].lower() == "stopped" and int(r["tasks"]) == 0 for r in matching_apps)
        assert not matching_containers and lifecycle["stopped_at"] is not None
        report["scoped_apps_terminal"][app_id] = {"app_rows": matching_apps,
            "matching_containers": matching_containers, "lifecycle": lifecycle}
    rows = modal.Workspace.from_context().billing.report(start=datetime(2026, 10, 6, tzinfo=timezone.utc),
        end=datetime(2026, 10, 7, tzinfo=timezone.utc), resolution="h")
    report["billing_rows"] = [dataclasses.asdict(r) for r in rows if r.object_id in (APP, RUN1)]
    totals = {app_id: sum((r.cost for r in rows if r.object_id == app_id), Decimal(0)) for app_id in (APP, RUN1)}
    report["reported_app_usage_usd"] = {app_id: str(cost) for app_id, cost in totals.items()}
    report["reported_scoped_app_usage_total_usd"] = str(sum(totals.values(), Decimal(0)))
    report["booked_reserves_usd"] = {"run1": 1.55, "run2": 1.18, "total": 2.73, "envelope": 3.0}
    report["limits"] = [
        "Accept complete bounded six-case checked-tensor/prediction parity from the frozen audited checker and its report; raw tensors were not saved for a second offline gradient/weight comparison.",
        "Two training updates at seed99 and N32 per case do not establish all-run or mathematical equivalence. Controls use batch4; learned uses batch16.",
        "Direct correction tensors, training telemetry and dev numeric metrics other than accuracy were not pass-gated. GPU checkpoint/resume and campaign integration are unverified.",
        "Aggregate train_s includes model build, first-update warmup and CPU loss/gradient capture; reference always precedes candidate. It is not registered per-update retiming or an estimate of full-campaign cost.",
        "No Building image log line supports apparent cache reuse, but does not prove settled zero build charge. App-only reported billing is a snapshot; retain reserves.",
        "Shutdown is verified for these two option-A apps only; no claim about every workspace machine.",
        "No new paid work, registered retiming, concurrency experiment, budget increase or automatic retry is authorized by this audit."]
    report["accepted_bounded_gpu_parity"] = True
    report["terminal_verified"] = True
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    OUT.write_text(json.dumps(report, indent=2, default=str, allow_nan=False) + "\n")
    print(json.dumps({k: report[k] for k in ("accepted_bounded_gpu_parity", "terminal_verified",
        "total_compared_tensor_rows", "reported_app_usage_usd", "reported_scoped_app_usage_total_usd",
        "finished_at_utc")}, indent=2))


if __name__ == "__main__":
    main()
