"""M4-SGM P2C (prereg v0.2 `0c8d358`): 4 training cells in the NEW group
p2c-filler-curriculum-v1 — curriculum N32/N64 s0/s1 (label-free filler-length
schedule for training episodes; filler writes ON everywhere).

Same launch contract as the cleared P2G runner (non-preemptible CPU, deployed
app + `.spawn()`, atomic first-attempt claims, per-cell watchdog, idempotent
collector, stop-and-verify by spawn-time app id, artifact eval on the published
population only). The historical top-up/v1 runners are imported read-only for
their generic helpers and never edited; P2G and older IDs, groups, claims and
caps are untouched.

    .venv/bin/python modal-runners/modal-m4-sgm-p2c-nonpreemptible-spawn.py plan      # dry-run ledger, no Modal
    .venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2c-nonpreemptible-spawn.py
    .venv/bin/python modal-runners/modal-m4-sgm-p2c-nonpreemptible-spawn.py spawn
    .venv/bin/python modal-runners/modal-m4-sgm-p2c-nonpreemptible-spawn.py collect   # idempotent
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import modal

APP_NAME = "memsub-m4-sgm-p2c"
GROUP = "p2c-filler-curriculum-v1"
GRID = "configs/m4_sgm_p2c_grid.json"
INPUTS = "configs/m4_sgm_p2c_inputs.json"
V1_RUNNER = "modal-runners/modal-m4-sgm-p2d-diagnostics-grid.py"
TOPUP_RUNNER = "modal-runners/modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py"
V2_RUNS = "plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v2"
LOCAL_OUT = "plans/261005-0210-m4-sgm-p0-p2/runs"
SOURCE_SHA = "09b05c16459c2caba55cddee651bd232e9de4ac5a87ce5ad11f3f18a8ab6d966"   # P2C memsub (schedule knob)
PROPOSED_CAP_USD = 12.0          # prereg v0.2 request
P2C_CAP_USD = 12.0               # user-approved: #gravity 21398 ("go ahead"), scoped by codex 21400 to four cells
ARM_WALL_FACTOR = {"curriculum": 1.0}   # x own seed-specific v2 wall (prereg v0.2; never longer than v2)
MAX_CELL_TIMEOUT_S = 8 * 3600    # backstop only; per-cell watchdog is the real bound
# Training-artifact eval runs on the PUBLISHED P2D population; the registered
# readings population is reserved until all four cells validate (prereg v0.2).
ARTIFACT_EVAL_SEED_BASE, READINGS_SEED_BASE = 9_300_011, 9_500_011
P2C_IDS = frozenset({"curriculum-learned-n32-s0", "curriculum-learned-n32-s1",
                     "curriculum-learned-n64-s0", "curriculum-learned-n64-s1"})

app = modal.App(APP_NAME)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.7.1", index_url="https://download.pytorch.org/whl/cpu")
         .pip_install("transformers==4.55.2", "safetensors==0.5.3", "numpy==2.2.6")
         .env({"HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"]))
artifacts = modal.Volume.from_name("memsub-artifacts")


def file_sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def artifact_seed_ok(final_seed_base: int) -> bool:
    """Training may only evaluate on the artifact population, never the reserved one."""
    return final_seed_base == ARTIFACT_EVAL_SEED_BASE != READINGS_SEED_BASE


@app.function(image=image, cpu=(4.0, 4.0), memory=(8192, 8192), timeout=MAX_CELL_TIMEOUT_S,
              startup_timeout=300, retries=0, scaledown_window=2, max_containers=4,
              single_use_containers=True, nonpreemptible=True, volumes={"/artifacts": artifacts})
def run_cell(group: str, run_id: str, pilot: dict, provenance: dict, timeout_s: int,
             final_seed_base: int, runner_sha: str) -> dict:
    sys.path.insert(0, "/root/repo")
    from memsub.sgm.p2d_launch_guard import (EARLY_DEADLINE_S, AllowanceExhausted, AttemptLedger,
                                             ReplayRefused, Watchdog)
    early = Watchdog(EARLY_DEADLINE_S)   # bounds the heavy imports, source hashing and claim RPCs
    try:   # identity before the claim: a mismatched deploy exits without claiming or training
        from memsub.sgm.synthetic_pilot_run import source_tree_sha256   # imports torch
        got = {"runner": file_sha(__file__), "memsub": source_tree_sha256(Path("/root/repo/memsub"))}
        if (got != {"runner": runner_sha, "memsub": SOURCE_SHA} or group != GROUP or run_id not in P2C_IDS
                or not artifact_seed_ok(final_seed_base)):
            return {"run_id": run_id, "status": "identity_mismatch",
                    "reason": {**got, "final_seed_base": final_seed_base}}
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
    """Verbatim from the v1/top-up runners (same artifacts, manifest fields, commit)."""
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


# ---------------- local side (never imported in the container path) ----------------

def _load(path: str, name: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, Path(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def v1_runner():
    return _load(V1_RUNNER, "p2d_v1_runner")


def topup_runner():
    return _load(TOPUP_RUNNER, "p2d_topup_runner")


def plan(cap=P2C_CAP_USD) -> tuple[list, dict, dict]:
    """Cells (exactly the 4 registered IDs), timeouts from each cell's own
    seed-specific v2 wall, 3x non-preemptible ledger, provenance. Raises unless
    admitted under `cap` (None = no approved cap = never admitted)."""
    sys.path.insert(0, str(Path.cwd()))
    from memsub.sgm.p2d_launch_guard import TIMEOUT_MULTIPLIER, admission_ledger
    grid = json.loads(Path(GRID).read_text())
    inputs = json.loads(Path(INPUTS).read_text())
    if inputs["new_group"]["grid_sha256"] != file_sha(GRID) or inputs["new_group"]["group"] != GROUP:
        raise ValueError("inputs index does not bind this grid/group")
    seeds = [(d["artifact_eval_seed_base"], d["readings_seed_base"]) for d in (grid, inputs)]
    if "final_seed_base" in grid or any(x != (ARTIFACT_EVAL_SEED_BASE, READINGS_SEED_BASE) for x in seeds) \
            or not artifact_seed_ok(grid["artifact_eval_seed_base"]):
        raise ValueError("grid/inputs must bind artifact 9_300_011 and reserved readings 9_500_011 seeds")
    cells, timeouts = [], {}
    for run_id, tag, pilot in v1_runner().expand(grid):
        wall = json.loads((Path(V2_RUNS) / f"main-learned-n{pilot['n_bindings']}-s{pilot['seed']}"
                           / "metrics.json").read_text())["wall_seconds"]
        timeouts[run_id] = int(TIMEOUT_MULTIPLIER * ARM_WALL_FACTOR[tag] * wall)
        cells.append((run_id, pilot, timeouts[run_id]))
    if set(timeouts) != P2C_IDS or len(cells) != len(P2C_IDS):
        raise ValueError(f"P2C must be exactly the 4 registered cells, got {sorted(timeouts)}")
    if max(timeouts.values()) > MAX_CELL_TIMEOUT_S:
        raise ValueError("a cell timeout exceeds the Modal backstop")
    ledger_1x = admission_ledger(timeouts)                 # 1x reservation under the shared $15 guard
    ledger_1x["cell_timeouts_s"] = timeouts
    ledger = topup_runner().nonpreemptible_ledger(ledger_1x, cap)
    if not ledger["admitted"]:
        raise ValueError(f"not admitted: reserved ${ledger['reserved_total_usd']:.8f} vs cap {cap}")
    provenance = {"grid_file": GRID, "grid_sha256": file_sha(GRID), "inputs_index_sha256": file_sha(INPUTS),
                  "prereg_sha256": inputs["prereg"]["sha256"], "runner_sha256": file_sha(__file__),
                  "deployed_app": APP_NAME, "nonpreemptible": True, "memsub_source_sha256": SOURCE_SHA,
                  "artifact_eval_seed_base": ARTIFACT_EVAL_SEED_BASE, "readings_seed_base_reserved": READINGS_SEED_BASE}
    return cells, ledger, provenance


def dry_run() -> dict:
    """Ledger under the PROPOSED cap; never spawns. Also shows the live cap state."""
    cells, ledger, provenance = plan(cap=PROPOSED_CAP_USD)
    out = {"proposed_cap_usd": PROPOSED_CAP_USD, "approved_cap_usd": P2C_CAP_USD, "ledger": ledger,
           "provenance": provenance, "cells": [{"run_id": r, "timeout_s": t, "pilot": p} for r, p, t in cells]}
    print(json.dumps(out, indent=2))
    return out


def spawn() -> None:
    tracked = ["memsub", V1_RUNNER, TOPUP_RUNNER, __file__, GRID, INPUTS]
    if subprocess.run(["git", "status", "--porcelain", "--", *tracked],
                      capture_output=True, text=True, check=True).stdout.strip():
        raise SystemExit("refusing to spawn from a dirty tree")
    cells, ledger, provenance = plan()                     # raises while no cap is approved
    provenance["git_head"] = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                            text=True, check=True).stdout.strip()
    fn = modal.Function.from_name(APP_NAME, "run_cell")
    fn.hydrate()                                           # fails before any local state is written
    provenance["deployed_app_id"] = modal.App.lookup(APP_NAME).app_id   # stop/verify target
    tu, root = topup_runner(), Path(LOCAL_OUT) / GROUP
    root.mkdir(parents=True, exist_ok=False)               # a second spawn refuses here
    tu.atomic_write(root / "grid.json", Path(GRID).read_text())
    tu.atomic_write(root / "launch_provenance.json", json.dumps({**provenance, "ledger": ledger}, indent=2))
    seed_base = json.loads(Path(GRID).read_text())["artifact_eval_seed_base"]
    if not artifact_seed_ok(seed_base):                    # belt and braces: never the reserved seed
        raise SystemExit(f"refusing training eval seed base {seed_base}")
    calls = {}
    tu.atomic_write(root / "calls.json", "{}")
    for rid, pilot, t in cells:   # a crash here leaves later cells UNTRACKED; see collect()
        calls[rid] = fn.spawn(GROUP, rid, pilot, provenance, t, seed_base,
                              provenance["runner_sha256"]).object_id
        tu.atomic_write(root / "calls.json", json.dumps(calls, indent=2))   # after every spawn
        print("spawned", rid, calls[rid])


def lookup_claims(run_ids) -> dict:
    """run_id -> whether attempt 1 was claimed in THIS group's Dict."""
    try:
        d = modal.Dict.from_name(f"m4-sgm-{GROUP}-attempts")
        return {rid: bool(d.get(f"{rid}#attempt1", False)) for rid in run_ids}
    except Exception as e:                                 # no Dict yet = nothing claimed
        return {rid: f"lookup failed: {e!r}" for rid in run_ids}


def collect(poller=None, claims=lookup_claims) -> dict:
    """As the top-up collector, bound to THIS group's saved grid and the 4 IDs:
    the app is stopped only when all 4 cells are tracked AND terminal."""
    v1, tu, root = v1_runner(), topup_runner(), Path(LOCAL_OUT) / GROUP
    poller = poller or tu.poll
    expected = [rid for rid, _t, _p in v1.expand(json.loads((root / "grid.json").read_text()))]
    if len(expected) != len(P2C_IDS) or set(expected) != P2C_IDS:
        raise SystemExit(f"saved grid is not the registered 4-cell P2C grid: {sorted(expected)}")
    calls_path = root / "calls.json"
    calls = json.loads(calls_path.read_text()) if calls_path.exists() else {}
    if set(calls) - P2C_IDS:
        raise SystemExit(f"calls.json has unregistered cells: {sorted(set(calls) - P2C_IDS)}")
    app_id = json.loads((root / "launch_provenance.json").read_text())["deployed_app_id"]
    untracked = [rid for rid in expected if rid not in calls]
    states = {rid: {"poll": "untracked", "claimed": c} for rid, c in claims(untracked).items()} \
        if untracked else {}
    ready = []
    for rid in expected:
        if rid in untracked:
            continue
        kind, payload = poller(calls[rid])
        states[rid] = {"call_id": calls[rid], "poll": kind}
        if kind == "result":
            states[rid]["status"] = payload["status"]
            ready.append(payload)
        elif kind == "failed":
            states[rid]["error"] = payload
    terminal = not untracked and all(s["poll"] != "pending" for s in states.values())
    status = v1.consume(ready, root, lambda: v1.stop_app(app_id), lambda: v1.verify_stopped(app_id))
    report = {"terminal": terminal, "consume_status": status, "untracked": untracked, "cells": states}
    if untracked:
        report["untracked_recovery"] = tu.UNTRACKED_RECOVERY
    if terminal and status == "complete":
        report["final_shutdown"] = tu.shutdown(v1, app_id)
    tu.atomic_write(root / "collect_status.json", json.dumps(report, indent=2, default=str))
    print(json.dumps({k: v for k, v in report.items() if k not in ("cells", "untracked_recovery")},
                     default=str), {rid: s.get("status", s["poll"]) for rid, s in states.items()})
    return report


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).resolve().parents[1])     # all paths above are repo-relative
    {"plan": dry_run, "spawn": spawn, "collect": collect}[sys.argv[1]]()
