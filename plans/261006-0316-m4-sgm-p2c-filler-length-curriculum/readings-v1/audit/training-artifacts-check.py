"""Read-only P2C artifact audit. Does not construct or evaluate any model."""
from datetime import datetime, timezone
import hashlib
import json
import math
import statistics
from pathlib import Path

import modal
import torch
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "plans/261005-0210-m4-sgm-p0-p2/runs/p2c-filler-curriculum-v1"
MIRROR = RUNS.with_name(RUNS.name + "-volume-mirror")
REQUIRED = ("run_manifest.json", "metrics.json", "per_example_results.jsonl",
            "split_manifest.json", "routing_telemetry.jsonl", "report.md", "trained_parameters.safetensors")
FIELDS = {"batch": int, "episode": int, "episode_hash": str, "query": int,
          "key": int, "label": int, "pred": int, "correct": bool, "intervention": str}
IVS = {"none", "bank_derange", "coord_shuffle", "read_offset", "query_off"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


launch = read(RUNS / "launch_provenance.json")
grid = read(RUNS / "grid.json")
cleared = read(ROOT / "plans/reports/codex-261006-p2c-approved-launch-clearance.json")
calls, collect = read(RUNS / "calls.json"), read(RUNS / "collect_status.json")
validation = read(RUNS / "artifact_validation.json")
spawn = read(ROOT / "plans/reports/codex-261006-p2c-spawn-verification.json")
assert launch["git_head"] == cleared["commit"] and launch["ledger"] == cleared["ledger"]
assert calls == spawn["calls"] and len(calls) == len(set(calls.values())) == 4
assert grid == read(ROOT / launch["grid_file"])
assert launch["artifact_eval_seed_base"] == 9300011 and launch["readings_seed_base_reserved"] == 9500011
assert launch["ledger"]["cap_usd"] == 12 and launch["nonpreemptible"] is True
assert validation["launch"] == launch and validation["source_sha"] == launch["memsub_source_sha256"]
assert collect["terminal"] is True and collect["untracked"] == [] and collect["consume_status"] == "complete"
assert collect["final_shutdown"]["app_id"] == launch["deployed_app_id"]
assert collect["final_shutdown"]["status"] == "stopped_verified"
assert collect["final_shutdown"]["verification"]["verified"] is True
assert collect["final_shutdown"]["verification"]["app_containers"] == 0
pilots = {f"{block['tag']}-{grid['base']['arm']}-n{n}-s{s}":
          {**grid["base"], **block["override"], "n_bindings": n, "seed": s}
          for block in grid["blocks"] for n in block["n_bindings"] for s in block["seeds"]}
assert set(pilots) == set(calls) == set(collect["cells"]) == set(validation["cells"])
out = {"group": RUNS.name, "app_id": launch["deployed_app_id"], "approval_message_id": 21398,
       "source_sha256": launch["memsub_source_sha256"], "launch_sha256": sha(RUNS / "launch_provenance.json"),
       "cells": {}, "saved_shutdown": collect["final_shutdown"]}
for rid, pilot in pilots.items():
    cell, local = MIRROR / rid, RUNS / rid
    assert all((cell / name).is_file() for name in REQUIRED), rid
    man, met, split = read(cell / "run_manifest.json"), read(cell / "metrics.json"), read(cell / "split_manifest.json")
    assert validation["cells"][rid] == {"status": "stream_ok", "reason": None}
    assert collect["cells"][rid] == {"call_id": calls[rid], "poll": "result", "status": "done"}
    assert man["pilot_config"] == pilot and man["attempt"] == 1 and man["run_id"] == rid and man["modal_group"] == RUNS.name
    assert all(man[k] == v for k, v in launch.items() if k != "ledger"), rid
    assert met["steps"] == pilot["steps"] == 1500 and pilot["checkpoint_steps"] == []
    assert pilot["filler_len_schedule"] == [[0, 0], [1000, 40]] and pilot["filler_writes"] is True
    assert all(met[k] == pilot[k] for k in ("arm", "readout", "n_queries", "n_bindings", "seed"))
    assert met["result_label"] == man["result_label"] == "tiny-random-lm+taskhead+DIAGNOSTIC-filler-len-schedule"
    assert man["checkpoint_parameters_sha256"] == {} and met["checkpoints"] == {}
    assert split["seeds"] == {"train": pilot["seed"], "dev_eval": 4242, "final_eval": 9300011 + pilot["seed"]}
    assert man["final_eval_seed"] == split["seeds"]["final_eval"] != 9500011 + pilot["seed"]
    assert man["trained_parameters_sha256"] == sha(cell / "trained_parameters.safetensors")
    assert man["cell_timeout_s"] == launch["ledger"]["cell_timeouts_s"][rid]
    assert math.isfinite(man["wall_seconds"]) and 0 < man["wall_seconds"] < man["cell_timeout_s"]
    assert man["wall_seconds"] == met["wall_seconds"]
    assert man["state_horizon_tokens"] == man["gradient_horizon_tokens"] == 4 + 2 * pilot["n_bindings"] + 40
    local_met = read(local / "metrics.json")
    # run_pilot adds this checksum to its return AFTER writing volume metrics.
    # The streamed copy therefore has one verified extension to the persisted payload.
    assert local_met.pop("run_manifest_sha256") == sha(cell / "run_manifest.json")
    assert local_met == met
    assert (local / "per_example_results.jsonl").read_bytes() == (cell / "per_example_results.jsonl").read_bytes()
    rows = [json.loads(line) for line in (cell / "per_example_results.jsonl").read_text().splitlines()]
    assert len(rows) == 5120 and met["final_episodes"] == 256
    episodes, targets = {}, {}
    for r in rows:
        assert set(r) == set(FIELDS) and all(type(r[k]) is t for k, t in FIELDS.items())
        assert 0 <= r["pred"] < 64 and 0 <= r["label"] < 64 and r["correct"] == (r["pred"] == r["label"])
        ep = r["batch"], r["episode"], r["episode_hash"]
        queries = episodes.setdefault(r["intervention"], {}).setdefault(ep, {})
        assert r["query"] not in queries
        queries[r["query"]] = r["correct"]
        key, target = (*ep, r["query"]), (r["key"], r["label"])
        assert targets.get(key, target) == target
        targets[key] = target
    assert set(episodes) == IVS
    for iv, eps in episodes.items():
        assert len(eps) == 256 and set(eps) == set(episodes["none"])
        assert all(set(q) == {0, 1, 2, 3} for q in eps.values())
        scores = [sum(q.values()) / 4 for q in eps.values()]
        f = met["final"][f"heldout_{iv}"]
        assert f["correct"] == sum(sum(q.values()) for q in eps.values()) and f["total"] == 1024
        assert f["accuracy"] == statistics.mean(scores)
        hw = 1.96 * statistics.stdev(scores) / math.sqrt(256)
        assert math.isclose(hw, f["accuracy_ci95_halfwidth_episode"], rel_tol=0, abs_tol=1e-12)
    telemetry = [json.loads(l) for l in (cell / "routing_telemetry.jsonl").read_text().splitlines()]
    assert [r["step"] for r in telemetry if "eval" in r] == list(range(0, 1501, 100))
    assert [r["step"] for r in telemetry if "loss" in r] == list(range(0, 1500, 10))
    assert all(math.isfinite(r["loss"]) for r in telemetry if "loss" in r)
    assert all(0 <= r["eval"]["accuracy"] <= 1 for r in telemetry if "eval" in r)
    tensors = load_file(str(cell / "trained_parameters.safetensors"))
    assert tensors and all(bool(torch.isfinite(t).all()) for t in tensors.values())
    out["cells"][rid] = {"attempt": 1, "source_seed": man["final_eval_seed"], "steps": 1500,
        "wall_seconds": man["wall_seconds"], "timeout_s": man["cell_timeout_s"],
        "file_sha256": {name: sha(cell / name) for name in REQUIRED},
        "published_rows_checked": 5120, "local_mirror_equal_under_return_contract": True,
        "streamed_manifest_checksum_verified": True, "parameters_finite": True,
        "descriptive_published_seed_accuracy": {iv: met["final"][f"heldout_{iv}"]["accuracy"]
                                                 for iv in ("none", "bank_derange", "read_offset")}}
claims = modal.Dict.from_name("m4-sgm-p2c-filler-curriculum-v1-attempts")
out["claims"] = {rid: {"attempt1": claims.get(rid + "#attempt1", False),
                       "replay1": claims.get(rid + "#replay1", None)} for rid in pilots}
out["halt"] = claims.get("__halt__", None)
assert out["halt"] is None and all(v == {"attempt1": True, "replay1": None} for v in out["claims"].values())
out.update({"pass": True, "all_four_stream_ok": True, "no_failed_or_untracked_calls": True,
            "published_artifact_population_only": True, "registered_readings_status": "RUNNING; results audit pending",
            "auditor_checkpoint_evaluations": 0, "auditor_training_calls": 0,
            "checked_at_utc": datetime.now(timezone.utc).isoformat()})
path = Path(__file__).with_name("codex-261006-p2c-training-artifacts-audit.json")
path.write_text(json.dumps(out, indent=2) + "\n")
print("PASS", path.name, sha(path))
