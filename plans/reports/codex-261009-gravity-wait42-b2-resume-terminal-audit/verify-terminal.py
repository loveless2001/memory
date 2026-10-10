"""Offline terminal evidence audit: CPU tensor reads only; no model construction, forward or restore."""
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys

import torch
from safetensors.torch import load_file

REPORT = Path(__file__).resolve().parent
ROOT = Path("/home/lenovo/projects/memory-occupied-fill-v1-worktree")
PLAN = ROOT / "plans/261009-1135-m4-sgm-p2p5-b2-occupied-fill-long-run"
OLD = REPORT.parent / "codex-261009-gravity-wait38-b2-manual-stop-audit/volume-evidence-verified/b2-run-v1"
FIRST = REPORT.parent / "codex-261009-gravity-wait41-b2-resume-first-start-audit"
V = REPORT / "volume"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("b2_final_offline", ROOT / "scripts/sgm-p2p5-b2-occupied-fill-long-run-train.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

def read_json(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def normalize(x):
    return json.loads(json.dumps(x, default=float))

package_hashes = {}
for line in (PLAN / "SHA256SUMS-b2-resume-package-v0.4.txt").read_text().splitlines():
    expected, rel = line.split(maxsplit=1)
    if expected == "memsub_source_sha256":
        assert B.source_tree_sha256(ROOT / "memsub") == rel
    else:
        assert sha(ROOT / rel) == expected, rel
        package_hashes[rel] = expected
assert len(package_hashes) == 8

live = read_json(REPORT / "live-snapshot.json")
prior = read_json(FIRST / "live-snapshot.json")
d, meta = live["dict"], live["launch"]
assert live["call_state"] == "done"
call = live["call_info"]
assert call == read_json(REPORT / "owner-receipts/call_result.json")
assert call["returncode"] == 0 and call["start"] == "start-2" and call["volume_commit_errors"] == 0
assert call["versions"] == {"torch": "2.7.1+cu126", "transformers": "4.55.2"}
assert d == prior["dict"]
assert d["start-3"] is None and d["resume-1-deadline"] == meta["deadline"]
assert read_json(V / "campaign.json") == read_json(OLD / "campaign.json")
assert read_json(V / "campaign.json")["deadline"] == d["deadline"]
assert (V / "B2.archive/start-2/routing_telemetry.jsonl").read_bytes() == (OLD / "B2/routing_telemetry.jsonl").read_bytes()
starts = [json.loads(x) for x in (V / "B2.starts.jsonl").read_text().splitlines()]
assert len(starts) == 2 and starts[0]["resume_step"] is None and starts[1]["resume_step"] == 750
probe = ROOT / "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"
cfg = B.arm_config(read_json(probe)["pilot_config"], "cuda")
identity = B.run_identity(cfg, sha(probe))
assert read_json(V / "B2/identity.json") == identity

rows = [json.loads(x) for x in (V / "B2/routing_telemetry.jsonl").read_text().splitlines()]
evals = [r for r in rows if "eval" in r]
trains = [r for r in rows if "loss" in r]
assert [r["step"] for r in evals] == list(range(0, 1501, 100))
assert [r["step"] for r in trains] == list(range(0, 1500, 10))
assert len(rows) == len(evals) + len(trains) == 166
derange = read_json(V / "B2/final_bank_derange_eval.json")
for ev in [r["eval"] for r in evals] + [derange]:
    assert type(ev["correct"]) is int and 0 <= ev["correct"] <= 256
    assert type(ev["total"]) is int and ev["total"] == 256
    assert ev["episodes"] == 64 and ev["chance"] == 1 / 64
    assert ev["accuracy"] == ev["correct"] / 256
    assert B.eval_ok(ev)
    for k in ["query_empty_read_weight", "query_fully_absent_fraction", "query_without_occupied_fraction"]:
        assert isinstance(ev[k], (int, float)) and math.isfinite(ev[k]) and 0 <= ev[k] <= 1
for row in trains:
    for k in ["loss", "read_anchor", "sec_per_step"]:
        assert math.isfinite(row[k])
none_correct, swapped_correct = evals[-1]["eval"]["correct"], derange["correct"]
independent_used = none_correct >= 12 and none_correct - swapped_correct >= 6
classifier = B.summarize(rows, derange)
assert classifier == read_json(V / "B2/b2_result.json")
assert classifier["memory_used"] == independent_used is False
assert none_correct == swapped_correct == 5 and classifier["status"] == "valid"

state = torch.load(V / "B2/resume.pt", map_location="cpu", weights_only=False)
old_state = torch.load(OLD / "B2/resume.pt", map_location="cpu", weights_only=False)
assert sha(OLD / "B2/resume.pt") == "cd1a7e72cbbf4fc2cf92e029395c7e4f78a727d2b6d165b5030bacc1bd753394"
assert state["format"] == "m4-sgm-train-resume-v1" and state["step"] == 1500
assert state["pilot_config"] == asdict(cfg) and state["b2_identity"] == identity
counts = defaultdict(int)
def finite(v, prefix):
    if isinstance(v, torch.Tensor):
        assert v.device.type == "cpu" and torch.isfinite(v).all(), prefix
        counts[prefix.split(".")[0]] += 1
    elif isinstance(v, dict):
        for k, item in v.items():
            finite(item, prefix + "." + str(k))
    elif isinstance(v, (list, tuple)):
        for k, item in enumerate(v):
            finite(item, prefix + "." + str(k))
for key in ["adapters", "head", "optimizer", "data_generator", "torch_rng", "cuda_rng", "checkpoints"]:
    finite(state[key], key)
assert state["data_generator"].numel() and state["torch_rng"].numel() and len(state["cuda_rng"]) == 1
assert rows[:-1] == normalize(state["telemetry"])
assert rows[:len(old_state["telemetry"])] == normalize(old_state["telemetry"])
manifest = read_json(V / "B2/run_manifest.json")
assert manifest["pilot_config"] == normalize(asdict(cfg)) == identity["pilot_config"]
assert manifest["memsub_source_sha256"] == identity["memsub_source_sha256"]
assert manifest["probe_manifest_sha256"] == sha(probe)
assert manifest["trained_parameters_sha256"] == sha(V / "B2/trained_parameters.safetensors")
assert manifest["tf32"] == {"matmul": False, "cudnn": False}
assert manifest["versions"]["torch"] == "2.7.1+cu126"
assert manifest["versions"]["transformers"] == "4.55.2" and manifest["dev_seed"] == 4242
params = {**{"adapters." + k: v for k, v in state["adapters"].items()},
          **{"head." + k: v for k, v in state["head"].items()}}
trained = load_file(str(V / "B2/trained_parameters.safetensors"), device="cpu")
assert params.keys() == trained.keys() and len(params) == 46
assert all(torch.equal(params[k], trained[k]) for k in params)
old_params = {**{"adapters." + k: v for k, v in old_state["adapters"].items()},
              **{"head." + k: v for k, v in old_state["head"].items()}}
changed = sum(not torch.equal(v, old_params[k]) for k, v in params.items())
assert changed > 0
for name in ["B2.start-1.stderr.txt", "B2.start-2.stderr.txt"]:
    assert (V / name).stat().st_size == 0

apps, containers = read_json(REPORT / "app-list.json"), read_json(REPORT / "container-list.json")
assert containers == []
shutdown = {}
for app_id in ["ap-VsAmnu1E7eS5rXLrKD7vXd", meta["app_id"]]:
    mine = [r for r in apps if r["app_id"] == app_id]
    assert all(r["state"] == "stopped" and str(r["tasks"]) == "0" for r in mine)
    shutdown[app_id] = {"status": "stopped_verified", "app_rows": mine, "container_rows": [],
                        "unlisted": not mine}
failed = read_json(REPORT / "owner-receipts/cleanup-attempt1-no-yes-flag.json")
corrected = read_json(REPORT / "owner-receipts/cleanup.json")
assert failed["status"] == "shutdown_unresolved" and failed["stop"]["returncode"] == 1
assert "Rerun with --yes" in failed["stop"]["stderr_tail"]
assert all(not v["verified"] for v in failed["checks"])
assert corrected["status"] == "stopped_verified" and corrected["stop"]["returncode"] == 0
assert corrected["checks"][-1]["verified"] is True
stop_line = next(x for x in (ROOT / "modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-resume-runner.py").read_text().splitlines()
                 if 'cli(["app", "stop", app_id]' in x)
assert "--yes" not in stop_line

raw_billing = read_json(REPORT / "billing-hourly-raw.json")
totals = defaultdict(Decimal)
hours = defaultdict(lambda: defaultdict(Decimal))
resources = defaultdict(lambda: defaultdict(Decimal))
for row in raw_billing:
    obj, cost = row["object_id"], Decimal(row["cost"])
    totals[obj] += cost
    hours[obj][row["interval_start"]] += cost
    resources[obj][row["resource"]] += cost
start1, resume = "ap-VsAmnu1E7eS5rXLrKD7vXd", meta["app_id"]
daily_rows = read_json(REPORT / "billing-daily-raw.json")
daily = defaultdict(Decimal)
for row in daily_rows:
    daily[row["object_id"]] += Decimal(row["cost"])
assert daily[start1] == Decimal("5.69262133"), daily[start1]
assert daily[resume] == Decimal("5.23085059"), daily[resume]
rounding_delta = {k: daily[k] - totals[k] for k in [start1, resume]}
assert all(abs(v) <= Decimal("0.000001") for v in rounding_delta.values())
combined = daily[start1] + daily[resume]
assert combined == Decimal("10.92347192") < Decimal("17")
assert all(h < "2026-10-09T12:00:00" for h in hours[resume])
task_ce = [r["loss"] - .1 * r["read_anchor"] for r in trains]
long_steps = [r["sec_per_step"] for r in trains if r["step"] >= 1000]
short_resumed = [r["sec_per_step"] for r in trains if 750 <= r["step"] < 1000]
result = {
    "verified_at": datetime.now(timezone.utc).isoformat(), "status": "VALID_NEGATIVE",
    "artifact_capture_finished": live["capture_finished"], "package_files_verified": len(package_hashes),
    "call": call, "starts": starts, "start3_unused": True, "deadline_and_start1_preserved": True,
    "archived_original_partial_byte_identical": True, "complete_evals": len(evals),
    "telemetry_rows": len(rows), "train_rows": len(trains), "final_classifier": classifier,
    "checkpoint": {"step": state["step"], "bytes": (V / "B2/resume.pt").stat().st_size,
        "sha256": sha(V / "B2/resume.pt"), "all_tensors_finite": True, "tensor_counts": dict(counts),
        "optimizer_entries": len(state["optimizer"]["state"]),
        "optimizer_update_steps": sorted({int(s["step"]) for s in state["optimizer"]["state"].values()}),
        "checkpoint_telemetry_exact_prefix_before_final_eval": True,
        "changed_parameter_tensors_vs750": changed, "safetensors_match_all_parameters": True,
        "trained_parameters_sha256": sha(V / "B2/trained_parameters.safetensors")},
    "routing": {"final_pre_fill_absent_weight": evals[-1]["eval"]["query_empty_read_weight"],
        "final_fully_absent_fraction": evals[-1]["eval"]["query_fully_absent_fraction"],
        "in_band_eval_steps": [r["step"] for r in evals if r["eval"]["query_empty_read_weight"] <= .2]},
    "training": {"last_task_ce": task_ce[-1], "last10_logged_task_ce_mean": statistics.mean(task_ce[-10:]),
        "ln64": math.log(64), "last_logged_grad_norms": trains[-1]["grad_norm"],
        "median_long_logged_step_s": statistics.median(long_steps),
        "median_resumed_short_logged_step_s": statistics.median(short_resumed)},
    "shutdown": shutdown, "cleanup": {"failed": failed["status"],
        "failed_elapsed_s": failed["elapsed_s"], "corrected": corrected["status"],
        "corrected_elapsed_s": corrected["elapsed_s"], "runner_bug_still_present": True},
    "billing": {"receipt": read_json(REPORT / "billing-receipt.json"),
        "start1_usd": str(daily[start1]), "resume_usd": str(daily[resume]),
        "combined_app_only_usd": str(combined), "cap_usd": "17",
        "hourly_resource_rounding_delta_usd": {k: str(v) for k, v in rounding_delta.items()},
        "arithmetic_difference_usd": str(Decimal("17") - combined),
        "hours": {k: {h: str(v) for h, v in hours[k].items()} for k in [start1, resume]},
        "resources": {k: {r: str(v) for r, v in resources[k].items()} for k in [start1, resume]},
        "no_reported_resume_compute_after11Z": True, "settled_invoice": False,
        "separate_storage_transfer_and_late_backfill_not_certified": True},
    "scientific_boundary": "No demonstrated memory use for this variant, seed and recipe. Equal aggregate counts do not establish identical predictions or logits.",
    "cpu_tensor_reads_only_no_model_forward_restore_or_training": True
}
(REPORT / "terminal-verification.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
