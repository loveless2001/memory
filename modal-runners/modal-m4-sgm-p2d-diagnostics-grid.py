"""M4-SGM P2D Step 2 diagnostics grid on Modal CPU, behind the launch guard
(memsub/sgm/p2d_launch_guard.py). 12 cells; launch refuses unless the
admission ledger fits the $15 cap and the tree is clean.

    modal run --detach modal-runners/modal-m4-sgm-p2d-diagnostics-grid.py \
        --group p2d-diagnostics-v1 --grid configs/m4_sgm_p2d_grid.json \
        --v2-runs plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v2 \
        --local-out plans/261005-0210-m4-sgm-p0-p2/runs
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import modal

app = modal.App("memsub-m4-sgm-p2d")
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.7.1", index_url="https://download.pytorch.org/whl/cpu")
         .pip_install("transformers==4.55.2", "safetensors==0.5.3", "numpy==2.2.6")
         .env({"HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"]))
artifacts = modal.Volume.from_name("memsub-artifacts")
MAX_CELL_TIMEOUT_S = 8 * 3600     # backstop only; per-cell watchdog is the real bound


@app.function(image=image, cpu=(4.0, 4.0), memory=(8192, 8192), timeout=MAX_CELL_TIMEOUT_S,
              startup_timeout=300, retries=0, scaledown_window=2, max_containers=12,
              single_use_containers=True, volumes={"/artifacts": artifacts})
def run_cell(group: str, run_id: str, pilot: dict, provenance: dict, timeout_s: int,
             final_seed_base: int) -> dict:
    import sys
    sys.path.insert(0, "/root/repo")
    from memsub.sgm.p2d_launch_guard import (EARLY_DEADLINE_S, AllowanceExhausted, AttemptLedger,
                                             ReplayRefused, Watchdog)
    early = Watchdog(EARLY_DEADLINE_S)          # bounds imports + claim RPCs before anything else
    try:
        try:   # atomic claim: only attempt 1 of a cell may train
            AttemptLedger(modal.Dict.from_name(f"m4-sgm-{group}-attempts",
                                               create_if_missing=True)).begin(run_id)
        except AllowanceExhausted as e:
            return {"run_id": run_id, "status": "allowance_exhausted", "reason": str(e)}
        except ReplayRefused as e:
            return {"run_id": run_id, "status": "replay_refused", "reason": str(e)}
    finally:
        early.cancel()
    watchdog = Watchdog(timeout_s)
    try:
        return _train_cell(group, run_id, pilot, provenance, timeout_s, final_seed_base)
    finally:
        watchdog.cancel()


def _train_cell(group, run_id, pilot, provenance, timeout_s, final_seed_base) -> dict:
    import re
    import torch
    from memsub.sgm.synthetic_pilot import PilotConfig
    from memsub.sgm.synthetic_pilot_run import run_pilot
    for name in (group, run_id):
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", name) is None:
            raise ValueError(f"invalid id {name!r}")
    torch.set_num_threads(4)
    out = Path("/artifacts/m4-sgm") / group / run_id
    if out.exists():
        raise FileExistsError(f"{out} exists; no automatic retry")
    metrics = run_pilot(PilotConfig(**pilot), out, final_seed_base=final_seed_base,
                        extra_manifest={"modal_group": group, "run_id": run_id, "attempt": 1,
                                        "cell_timeout_s": timeout_s, **provenance})
    artifacts.commit()
    return {"run_id": run_id, "status": "done", "metrics": metrics}


def expand(grid: dict) -> list[tuple[str, str, dict]]:
    cells = []
    for block in grid["blocks"]:
        for n in block["n_bindings"]:
            for seed in block["seeds"]:
                pilot = {**grid["base"], **block.get("override", {}), "n_bindings": n, "seed": seed}
                cells.append((f"{block['tag']}-learned-n{n}-s{seed}", block["tag"], pilot))
    ids = [c[0] for c in cells]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate run ids in grid")      # ledger must reserve every launch
    return cells


def plan(grid_path: Path, v2_runs: Path) -> tuple[list, dict, dict]:
    """(cells with timeouts, admission ledger, provenance) — local, no Modal."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from memsub.sgm.p2d_launch_guard import admission_ledger, cell_timeout_seconds
    grid = json.loads(grid_path.read_text())
    cells, timeouts = [], {}
    for run_id, tag, pilot in expand(grid):
        v2 = json.loads((v2_runs / f"main-learned-n{pilot['n_bindings']}-s{pilot['seed']}"
                         / "metrics.json").read_text())
        timeouts[run_id] = cell_timeout_seconds(tag, v2["wall_seconds"])
        cells.append((run_id, pilot, timeouts[run_id]))
    if max(timeouts.values()) > MAX_CELL_TIMEOUT_S:
        raise ValueError("a cell timeout exceeds the Modal backstop")
    ledger = admission_ledger(timeouts)
    ledger["cell_timeouts_s"] = timeouts
    return cells, ledger, {"grid_file": str(grid_path),
                           "grid_sha256": hashlib.sha256(grid_path.read_bytes()).hexdigest()}


@app.local_entrypoint()
def main(group: str, grid: str, v2_runs: str, local_out: str):
    tracked = ["memsub", "modal-runners/modal-m4-sgm-p2d-diagnostics-grid.py", grid]
    dirty = subprocess.run(["git", "status", "--porcelain", "--", *tracked],
                           capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        raise SystemExit(f"refusing to launch from a dirty tree:\n{dirty}")
    cells, ledger, provenance = plan(Path(grid), Path(v2_runs))   # raises if over the cap
    provenance["git_head"] = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                            text=True, check=True).stdout.strip()
    spec = json.loads(Path(grid).read_text())
    root = Path(local_out) / group
    root.mkdir(parents=True, exist_ok=False)
    (root / "grid.json").write_text(json.dumps(spec, indent=2))
    (root / "launch_provenance.json").write_text(json.dumps({**provenance, "ledger": ledger}, indent=2))
    print("ledger", json.dumps(ledger))
    args = [(group, rid, pilot, provenance, t, spec["final_seed_base"]) for rid, pilot, t in cells]
    results = run_cell.starmap(args, order_outputs=False,        # completion order: prompt HALT
                               return_exceptions=True, wrap_returned_exceptions=False)
    status = consume(results, root, lambda: stop_app(app.app_id), lambda: verify_stopped(app.app_id))
    if status != "complete":
        raise SystemExit(f"launch ended with status {status}; see {root / 'shutdown.json'}")


MODAL_CLI = [sys.executable, "-m", "modal"]   # the launch interpreter's own Modal CLI


def stop_app(app_id: str, timeout_s: int = 120) -> None:
    """Checked, bounded, non-interactive `modal app stop --yes` (raises on
    failure or timeout; newer CLIs otherwise prompt and abort without a TTY)."""
    subprocess.run([*MODAL_CLI, "app", "stop", "--yes", app_id], check=True, timeout=timeout_s,
                   capture_output=True, text=True)


def verify_stopped(app_id: str, timeout_s: int = 120) -> dict:
    """Evidence that the app is stopped with zero running containers."""
    apps = subprocess.run([*MODAL_CLI, "app", "list", "--json"], check=True, timeout=timeout_s,
                          capture_output=True, text=True).stdout
    conts = subprocess.run([*MODAL_CLI, "container", "list", "--json"], check=True, timeout=timeout_s,
                           capture_output=True, text=True).stdout
    app_rows, container_rows = json.loads(apps), json.loads(conts)
    # Modal 1.5.1 converts table headings to snake_case in JSON output.
    # An unknown schema must not turn an existing app into an "unlisted" app.
    for rows in (app_rows, container_rows):
        if not isinstance(rows, list) or any(
                not isinstance(row, dict) or not isinstance(row.get("app_id"), str) for row in rows):
            raise ValueError("Modal CLI JSON must contain lists of rows with an app_id field")
    listed = [a for a in app_rows if a["app_id"] == app_id]
    running = [c for c in container_rows if c["app_id"] == app_id]
    if listed:   # still listed: require an explicit stopped state and zero tasks
        state, tasks = listed[0].get("state"), listed[0].get("tasks")
        stopped = isinstance(state, str) and state.lower() == "stopped" and str(tasks) == "0"
    else:        # `modal app list` drops stopped apps
        state, stopped = "not listed (stopped apps drop out)", True
    return {"app_state": state, "app_containers": len(running), "verified": stopped and not running}


def consume(results, root: Path, stop, verify) -> str:
    """Write each completed cell; on allowance exhaustion stop the app and
    VERIFY shutdown. Returns 'complete', 'halted' or 'shutdown_unresolved'."""
    for res in results:
        if isinstance(res, Exception):
            print("RUN FAILED:", repr(res))
            continue
        if res["status"] == "allowance_exhausted":
            print("ALLOWANCE EXHAUSTED — stopping app:", res)
            evidence = {"trigger": res}
            try:
                stop()
            except Exception as e:                     # e.g. already stopped: still verify
                evidence["stop_error"] = repr(e)
            try:
                evidence["verification"] = verify()
            except Exception as e:                     # surfaced, never swallowed
                evidence["verify_error"] = repr(e)
            ok = evidence.get("verification", {}).get("verified", False)
            evidence["status"] = "halted" if ok else "shutdown_unresolved"
            (root / "shutdown.json").write_text(json.dumps(evidence, indent=2, default=str))
            print("SHUTDOWN", evidence["status"], evidence)
            return evidence["status"]
        if res["status"] != "done":
            print("REPLAY REFUSED:", res)
            continue
        d = root / res["run_id"]
        d.mkdir(parents=True, exist_ok=True)
        rows = res["metrics"].pop("per_example", [])
        (d / "metrics.json").write_text(json.dumps(res["metrics"], indent=2, default=float))
        with (d / "per_example_results.jsonl").open("w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        print("done", res["run_id"], {k: (round(v["accuracy"], 3) if v else None)
                                      for k, v in res["metrics"]["final"].items()})
    return "complete"
