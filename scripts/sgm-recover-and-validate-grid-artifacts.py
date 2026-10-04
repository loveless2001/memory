"""Mirror an M4-SGM grid group from the Modal volume, validate every cell's
artifacts, and recover complete cells whose return stream failed.

    uv run python scripts/sgm-recover-and-validate-grid-artifacts.py \
        --group p2-load-sweep-v2 --local plans/261005-0210-m4-sgm-p0-p2/runs \
        --source-sha a89284ea...

Per registered cell (expanded from the group's local grid.json), status is:
  stream_ok        local metrics.json returned by the launcher and validated
  recovered        complete on the volume, missing locally -> copied locally
  incomplete       missing files or failed provenance/content checks (reason)
Writes <local>/<group>/artifact_validation.json. Never trains or launches.
Recovery code is outside memsub/, so the frozen experiment source hash is
unaffected.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

REQUIRED = ("run_manifest.json", "metrics.json", "per_example_results.jsonl",
            "split_manifest.json", "routing_telemetry.jsonl", "report.md",
            "trained_parameters.safetensors")
FINAL_SEED_BASE = 9_100_003


def expand(grid: dict) -> list[str]:
    ids = []
    for block in grid["blocks"]:
        for arm in block["arms"]:
            for n in block["n_bindings"]:
                for seed in block["seeds"]:
                    ids.append(f"{block.get('tag', 'main')}-{arm.replace('_', '-')}-n{n}-s{seed}")
    return ids


def validate(cell: Path, run_id: str, launch: dict, source_sha: str) -> str | None:
    """None if complete and consistent, else the first failure reason."""
    missing = [f for f in REQUIRED if not (cell / f).exists()]
    if missing:
        return f"missing {missing}"
    man = json.loads((cell / "run_manifest.json").read_text())
    met = json.loads((cell / "metrics.json").read_text())
    checks = {
        "run_id": man.get("run_id") == run_id,
        "git_head": man.get("git_head") == launch["git_head"],
        "grid_sha256": man.get("grid_sha256") == launch["grid_sha256"],
        "memsub_source_sha256": man.get("memsub_source_sha256") == source_sha,
        "final_eval_seed": man.get("final_eval_seed") == FINAL_SEED_BASE + met.get("seed", -1),
        "trained_parameters_sha256": man.get("trained_parameters_sha256") == hashlib.sha256(
            (cell / "trained_parameters.safetensors").read_bytes()).hexdigest(),
    }
    bad = [k for k, ok in checks.items() if not ok]
    if bad:
        return f"provenance mismatch {bad}"
    rows = (cell / "per_example_results.jsonl").read_text().splitlines()
    evaluated = [k for k, v in met["final"].items() if v and k.startswith("heldout_")]
    expected = len(evaluated) * met["final_episodes"] * met["n_queries"]
    if len(rows) != expected:
        return f"per-example rows {len(rows)} != expected {expected}"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True)
    ap.add_argument("--local", type=Path, required=True)
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--volume", default="memsub-artifacts")
    args = ap.parse_args()
    root = args.local / args.group
    mirror = args.local / f"{args.group}-volume-mirror"
    launch = json.loads((root / "launch_provenance.json").read_text())
    report = {"group": args.group, "launch": launch, "source_sha": args.source_sha, "cells": {}}
    for run_id in expand(json.loads((root / "grid.json").read_text())):
        dest = mirror / run_id
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["modal", "volume", "get", args.volume,
                        f"m4-sgm/{args.group}/{run_id}", str(mirror)],
                       capture_output=True, text=True)
        reason = validate(dest, run_id, launch, args.source_sha)
        local = root / run_id
        if reason is not None:
            status = "incomplete"
        elif (local / "metrics.json").exists():
            same = (json.loads((local / "metrics.json").read_text())["final"]
                    == json.loads((dest / "metrics.json").read_text())["final"])
            status, reason = ("stream_ok", None) if same else (
                "incomplete", "local streamed metrics differ from volume metrics")
        else:
            local.mkdir(parents=True, exist_ok=True)
            for f in ("metrics.json", "per_example_results.jsonl"):
                shutil.copy2(dest / f, local / f)
            (local / "recovered_from_volume.json").write_text(json.dumps(
                {"source": f"{args.volume}:m4-sgm/{args.group}/{run_id}"}, indent=2))
            status = "recovered"
        report["cells"][run_id] = {"status": status, "reason": reason}
        print(f"{run_id}: {status}" + (f" ({reason})" if reason else ""))
    (root / "artifact_validation.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
