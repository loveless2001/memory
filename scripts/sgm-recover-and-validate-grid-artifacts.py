"""Mirror an M4-SGM grid group from the Modal volume, validate every cell's
artifacts against its REGISTERED config, and recover complete evidence whose
return stream failed.

    uv run python scripts/sgm-recover-and-validate-grid-artifacts.py \
        --group p2-load-sweep-v2 --local plans/261005-0210-m4-sgm-p0-p2/runs \
        --source-sha a89284ea...

Per registered cell (expanded from the group's grid.json with the launcher's
own `_expand`), status is one of:
  stream_ok         launcher-returned metrics + rows identical to the valid volume copy
  rows_recovered    metrics streamed; per-example rows missing/different -> copied
  recovered         complete on the volume, nothing local -> metrics + rows copied
  incomplete        volume artifacts invalid (reason) — execution evidence problem
  local_mismatch    volume valid but locally streamed metrics disagree (investigate)
  retrieval_failed  `modal volume get` failed (stderr kept) — NOT execution evidence
Writes <local>/<group>/artifact_validation.json. Never trains or launches.
Lives outside memsub/, so the frozen experiment source hash is unaffected.
"""

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

REQUIRED = ("run_manifest.json", "metrics.json", "per_example_results.jsonl",
            "split_manifest.json", "routing_telemetry.jsonl", "report.md",
            "trained_parameters.safetensors")
ROW_FIELDS = {"batch": int, "episode": int, "episode_hash": str, "query": int, "key": int,
              "label": int, "pred": int, "correct": bool, "intervention": str}
FINAL_SEED_BASE = 9_100_003
N_VALUE_CLASSES = 64             # synthetic task label space (synthetic_binding_task.N_VALUES)
RUNNER = Path(__file__).resolve().parents[1] / "modal-runners" / "modal-m4-sgm-synthetic-pilot-grid.py"


def registered_cells(grid: dict, runner_path: Path = RUNNER) -> dict[str, dict]:
    """run_id -> pilot config, via the launcher's own expansion (v2 `_expand`
    -> (id, pilot); P2D `expand` -> (id, tag, pilot))."""
    spec = importlib.util.spec_from_file_location("m4_grid_runner", runner_path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    if hasattr(runner, "expand"):
        return {rid: pilot for rid, _tag, pilot in runner.expand(grid)}
    return dict(runner._expand(grid))


def schema_problem(man, met) -> str | None:
    """Type-check manifest / metrics / final results before any field access."""
    if not isinstance(man, dict):
        return f"run_manifest is {type(man).__name__}, not an object"
    if not isinstance(met, dict):
        return f"metrics is {type(met).__name__}, not an object"
    final = met.get("final")
    if not isinstance(final, dict):
        return f"metrics.final is {type(final).__name__}, not an object"
    for name in ("final_episodes", "n_queries"):
        if type(met.get(name)) is not int or met[name] < 1:
            return f"metrics.{name} is not a positive int"
    for key, r in final.items():
        if r is None and key.startswith("heldout_"):
            continue
        if not isinstance(r, dict):
            return f"final.{key} is {type(r).__name__}, not an object"
        if not key.startswith("heldout_"):
            continue
        acc, correct, total = r.get("accuracy"), r.get("correct"), r.get("total")
        if type(correct) is not int or type(total) is not int or total < 1:
            return f"final.{key}: correct/total are not ints"
        if not isinstance(acc, (int, float)) or isinstance(acc, bool) or not math.isfinite(acc) \
                or not math.isclose(acc, correct / total, rel_tol=0, abs_tol=1e-12):
            return f"final.{key}: accuracy {acc!r} != correct/total {correct}/{total}"
    return None


def validate_rows(rows_text: str, met: dict) -> str | None:
    """Parse every row; check schema, unique complete episode/query coverage
    per intervention, shared episodes, and correct/total vs final metrics."""
    evaluated = {k[len("heldout_"):]: v for k, v in met["final"].items()
                 if k.startswith("heldout_") and v}
    by_iv: dict[str, dict] = defaultdict(dict)
    for i, line in enumerate(rows_text.splitlines()):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            return f"row {i}: invalid JSON ({e.msg})"
        if not isinstance(row, dict) or set(row) != set(ROW_FIELDS) or any(
                type(row[k]) is not t for k, t in ROW_FIELDS.items()):
            return f"row {i}: schema mismatch"
        if row["intervention"] not in evaluated:
            return f"row {i}: unexpected intervention {row['intervention']!r}"
        if not (0 <= row["pred"] < N_VALUE_CLASSES and 0 <= row["label"] < N_VALUE_CLASSES):
            return f"row {i}: pred/label outside 0..{N_VALUE_CLASSES - 1}"
        if row["correct"] != (row["pred"] == row["label"]):
            return f"row {i}: correct flag disagrees with pred == label"
        key = (row["batch"], row["episode"], row["episode_hash"], row["query"])
        if key in by_iv[row["intervention"]]:
            return f"row {i}: duplicate {key}"
        by_iv[row["intervention"]][key] = row["correct"]
    episodes_ref = None
    for iv, result in evaluated.items():
        rows = by_iv.get(iv, {})
        episodes = {k[:3] for k in rows}
        if len(episodes) != met["final_episodes"]:
            return f"{iv}: {len(episodes)} episodes != final_episodes {met['final_episodes']}"
        for ep in episodes:
            if {k[3] for k in rows if k[:3] == ep} != set(range(met["n_queries"])):
                return f"{iv}: episode {ep} lacks queries 0..{met['n_queries'] - 1}"
        if episodes_ref is None:
            episodes_ref = episodes
        elif episodes != episodes_ref:
            return f"{iv}: episodes differ from other interventions"
        if (sum(rows.values()), len(rows)) != (result["correct"], result["total"]):
            return f"{iv}: rows give {sum(rows.values())}/{len(rows)} != metrics {result['correct']}/{result['total']}"
    return None


def validate(cell: Path, run_id: str, pilot: dict, launch: dict, source_sha: str,
             final_seed_base: int = FINAL_SEED_BASE) -> str | None:
    """None if the cell's artifacts are complete, parseable and bound to the
    registered config and launch provenance; else the first failure reason."""
    steps = [str(s) for s in pilot.get("checkpoint_steps", [])]
    required = list(REQUIRED) + [f for s in steps for f in (f"per_example_results_step{s}.jsonl",
                                                             f"trained_parameters_step{s}.safetensors")]
    missing = [f for f in required if not (cell / f).exists()]
    if missing:
        return f"missing {missing}"
    try:
        man = json.loads((cell / "run_manifest.json").read_text())
        met = json.loads((cell / "metrics.json").read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return f"unparseable manifest/metrics ({e})"
    problem = schema_problem(man, met)
    if problem:
        return problem
    checks = {
        "run_id": man.get("run_id") == run_id,
        "pilot_config": man.get("pilot_config") == pilot,
        "metrics_identity": all(met.get(k) == pilot[k] for k in
                                ("arm", "n_bindings", "seed", "steps", "readout", "n_queries")),
        "git_head": man.get("git_head") == launch["git_head"],
        "grid_sha256": man.get("grid_sha256") == launch["grid_sha256"],
        "memsub_source_sha256": man.get("memsub_source_sha256") == source_sha,
        "final_eval_seed": man.get("final_eval_seed") == final_seed_base + pilot["seed"],
        "checkpoint_parameters_sha256": all(
            (man.get("checkpoint_parameters_sha256") or {}).get(s) == hashlib.sha256(
                (cell / f"trained_parameters_step{s}.safetensors").read_bytes()).hexdigest()
            for s in steps),
        "trained_parameters_sha256": man.get("trained_parameters_sha256") == hashlib.sha256(
            (cell / "trained_parameters.safetensors").read_bytes()).hexdigest(),
    }
    bad = [k for k, ok in checks.items() if not ok]
    if bad:
        return f"mismatch {bad}"
    try:
        reason = validate_rows((cell / "per_example_results.jsonl").read_text(), met)
        for s in steps:
            if reason is None:
                ck = (met.get("checkpoints") or {}).get(s)
                problem = schema_problem(man, {**met, "final": ck})
                reason = (f"checkpoint {s}: {problem}" if problem else validate_rows(
                    (cell / f"per_example_results_step{s}.jsonl").read_text(), {**met, "final": ck}))
        return reason
    except (KeyError, TypeError) as e:
        return f"metrics lack fields needed for row validation ({e})"


def reconcile(dest: Path, local: Path) -> str:
    """Bring valid volume evidence into the local run dir; return status."""
    vol_met = json.loads((dest / "metrics.json").read_text())
    if not (local / "metrics.json").exists():
        local.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dest / "metrics.json", local / "metrics.json")
        for f in dest.glob("per_example_results*.jsonl"):
            shutil.copy2(f, local / f.name)
        (local / "recovered_from_volume.json").write_text(json.dumps({"copied": ["metrics", "rows"]}))
        return "recovered"
    local_met = json.loads((local / "metrics.json").read_text())
    for key in ("final", "checkpoints"):      # checkpoint scores too (codex 21141 #1)
        if local_met.get(key) != vol_met.get(key):
            raise ValueError(f"local streamed metrics.{key} differ from the valid volume metrics")
    copied = []
    for f in sorted(p.name for p in dest.glob("per_example_results*.jsonl")):
        if not (local / f).exists() or (local / f).read_bytes() != (dest / f).read_bytes():
            shutil.copy2(dest / f, local / f)
            copied.append(f)
    if not copied:
        return "stream_ok"
    (local / "recovered_from_volume.json").write_text(json.dumps({"copied": copied}))
    return "rows_recovered"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True)
    ap.add_argument("--local", type=Path, required=True)
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--volume", default="memsub-artifacts")
    ap.add_argument("--runner", type=Path, default=RUNNER)
    args = ap.parse_args()
    root = args.local / args.group
    mirror = args.local / f"{args.group}-volume-mirror"
    launch = json.loads((root / "launch_provenance.json").read_text())
    report = {"group": args.group, "launch": launch, "source_sha": args.source_sha, "cells": {}}
    grid = json.loads((root / "grid.json").read_text())
    seed_base = grid.get("final_seed_base", FINAL_SEED_BASE)
    for run_id, pilot in registered_cells(grid, args.runner).items():
        dest = mirror / run_id
        if dest.exists():
            shutil.rmtree(dest)
        mirror.mkdir(parents=True, exist_ok=True)
        got = subprocess.run(["modal", "volume", "get", args.volume,
                              f"m4-sgm/{args.group}/{run_id}", str(mirror)],
                             capture_output=True, text=True)
        if got.returncode != 0:
            status, reason = "retrieval_failed", (got.stderr or got.stdout).strip()[-500:]
        else:
            reason = validate(dest, run_id, pilot, launch, args.source_sha, seed_base)
            status = "incomplete"
            if reason is None:
                try:
                    status = reconcile(dest, root / run_id)
                except ValueError as e:
                    status, reason = "local_mismatch", str(e)
        report["cells"][run_id] = {"status": status, "reason": reason}
        print(f"{run_id}: {status}" + (f" ({reason})" if reason else ""))
    (root / "artifact_validation.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
