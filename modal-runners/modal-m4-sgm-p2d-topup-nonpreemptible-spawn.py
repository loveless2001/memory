"""M4-SGM P2D Step 2 TOP-UP (user option b, #gravity 21178/21180): the 6
registered cells lost in p2d-diagnostics-v1, rerun with their registered
configs (asserted equal to the v1 grid) and the same fresh seed base.

Two changes vs the v1 launcher, both about survival, none about training:
  * NON-PREEMPTIBLE CPU (`nonpreemptible=True`, 3x CPU/memory list price):
    v1 lost 3 cells to preemption + the 1-attempt rule;
  * DEPLOYED app + `.spawn()`: in-flight calls no longer depend on the local
    client (v1 lost 3 cells when the launch host died). A re-runnable
    collector pulls results; the volume stays the canonical evidence.
memsub is untouched (source d4effd0c…); the v1 runner/grid are reused as-is.

    .venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py
    .venv/bin/python modal-runners/modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py spawn
    .venv/bin/python modal-runners/modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py collect   # idempotent
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import modal

APP_NAME = "memsub-m4-sgm-p2d-topup"
GROUP = "p2d-diagnostics-v1-topup"
GRID = "configs/m4_sgm_p2d_topup_grid.json"
V1_GRID = "configs/m4_sgm_p2d_grid.json"
V1_RUNNER = "modal-runners/modal-m4-sgm-p2d-diagnostics-grid.py"
V2_RUNS = "plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v2"
LOCAL_OUT = "plans/261005-0210-m4-sgm-p0-p2/runs"
SOURCE_SHA = "d4effd0c5132057093d013d4e117bf131db9b4819fbc02d45fb1bc9b06a48b60"   # v1 memsub
NONPREEMPTIBLE_PRICE_MULTIPLIER = 3.0       # Modal docs: 3x list price for CPU and memory
TOPUP_CAP_USD = 27.0                        # user-approved B1 cap (#gravity 21193)
MAX_CELL_TIMEOUT_S = 8 * 3600               # backstop only; per-cell watchdog is the real bound
TOPUP_IDS = frozenset({"filleroff-learned-n64-s1", "long-learned-n16-s0", "long-learned-n16-s1",
                       "long-learned-n32-s0", "long-learned-n32-s1", "addrsup-learned-n64-s0"})

app = modal.App(APP_NAME)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.7.1", index_url="https://download.pytorch.org/whl/cpu")
         .pip_install("transformers==4.55.2", "safetensors==0.5.3", "numpy==2.2.6")
         .env({"HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"]))
artifacts = modal.Volume.from_name("memsub-artifacts")


def file_sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@app.function(image=image, cpu=(4.0, 4.0), memory=(8192, 8192), timeout=MAX_CELL_TIMEOUT_S,
              startup_timeout=300, retries=0, scaledown_window=2, max_containers=6,
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
        if got != {"runner": runner_sha, "memsub": SOURCE_SHA}:
            return {"run_id": run_id, "status": "identity_mismatch", "reason": got}
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
    """Verbatim from the v1 runner (same artifacts, manifest fields, commit)."""
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

def v1_runner():
    import importlib.util
    spec = importlib.util.spec_from_file_location("p2d_v1_runner", Path(V1_RUNNER))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def atomic_write(path: Path, text: str) -> None:
    """Write-then-rename: an interruption never leaves truncated JSON."""
    import os
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def nonpreemptible_ledger(ledger_1x: dict, cap) -> dict:
    """Scale every rate-based reservation by the non-preemptible multiplier;
    image build and the fixed margin are flat. Refuses a missing or exceeded cap."""
    m = NONPREEMPTIBLE_PRICE_MULTIPLIER
    rate_based = ("train_timeouts_usd", "startup_teardown_usd", "replay_allowance_usd", "cpu_overuse_margin_usd")
    flat = ("image_build_usd", "fixed_margin_usd")
    scaled = {**{k: ledger_1x[k] * m for k in rate_based}, **{k: ledger_1x[k] for k in flat}}
    out = {"cells": ledger_1x["cells"], "price_multiplier": m,
           "usd_per_container_hour": ledger_1x["usd_per_container_hour"] * m, **scaled}
    out["reserved_total_usd"] = sum(scaled.values())
    out["cap_usd"] = cap
    out["admitted"] = cap is not None and out["reserved_total_usd"] <= cap
    out["cell_timeouts_s"] = ledger_1x["cell_timeouts_s"]
    return out


def plan_topup(cap=TOPUP_CAP_USD) -> tuple[list, dict, dict]:
    """Cells (asserted identical to the v1 registered configs), ledger, provenance."""
    v1 = v1_runner()
    registered = {rid: pilot for rid, _t, pilot in v1.expand(json.loads(Path(V1_GRID).read_text()))}
    topup_grid, v1_grid = (json.loads(Path(g).read_text()) for g in (GRID, V1_GRID))
    if topup_grid["final_seed_base"] != v1_grid["final_seed_base"]:
        raise ValueError("top-up final_seed_base differs from v1")
    cells, ledger_1x, provenance = v1.plan(Path(GRID), Path(V2_RUNS))   # 1x ledger, $15 v1 cap
    ids = [rid for rid, _p, _t in cells]
    if len(ids) != len(TOPUP_IDS) or set(ids) != TOPUP_IDS:
        raise ValueError(f"top-up must be exactly the 6 authorized cells, got {sorted(ids)}")
    for rid, pilot, _t in cells:
        if registered.get(rid) != pilot:
            raise ValueError(f"{rid}: pilot config differs from the v1 registered cell")
    ledger = nonpreemptible_ledger(ledger_1x, cap)
    if not ledger["admitted"]:
        raise ValueError(f"not admitted: reserved ${ledger['reserved_total_usd']:.2f} vs cap {cap}")
    provenance.update({"v1_grid_sha256": file_sha(V1_GRID), "runner_sha256": file_sha(__file__),
                       "deployed_app": APP_NAME, "nonpreemptible": True, "memsub_source_sha256": SOURCE_SHA})
    return cells, ledger, provenance


def spawn() -> None:
    tracked = ["memsub", V1_RUNNER, __file__, GRID, V1_GRID]
    if subprocess.run(["git", "status", "--porcelain", "--", *tracked],
                      capture_output=True, text=True, check=True).stdout.strip():
        raise SystemExit("refusing to spawn from a dirty tree")
    cells, ledger, provenance = plan_topup()
    provenance["git_head"] = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                            text=True, check=True).stdout.strip()
    fn = modal.Function.from_name(APP_NAME, "run_cell")
    fn.hydrate()                                       # fails before any local state is written
    provenance["deployed_app_id"] = modal.App.lookup(APP_NAME).app_id   # stop/verify target
    root = Path(LOCAL_OUT) / GROUP
    root.mkdir(parents=True, exist_ok=False)           # a second spawn refuses here
    atomic_write(root / "grid.json", Path(GRID).read_text())
    atomic_write(root / "launch_provenance.json", json.dumps({**provenance, "ledger": ledger}, indent=2))
    seed_base = json.loads(Path(GRID).read_text())["final_seed_base"]
    calls = {}
    atomic_write(root / "calls.json", "{}")
    for rid, pilot, t in cells:   # a crash here leaves later cells UNTRACKED; see collect()
        calls[rid] = fn.spawn(GROUP, rid, pilot, provenance, t, seed_base,
                              provenance["runner_sha256"]).object_id
        atomic_write(root / "calls.json", json.dumps(calls, indent=2))   # after every spawn
        print("spawned", rid, calls[rid])


def poll(call_id: str):
    """('pending'|'expired'|'failed'|'result', payload)."""
    from modal.exception import OutputExpiredError
    try:
        return "result", modal.FunctionCall.from_id(call_id).get(timeout=0)
    except OutputExpiredError:
        return "expired", None
    except TimeoutError:                                # builtin: no output yet
        return "pending", None
    except Exception as e:                              # the function raised (incl. watchdog kill)
        return "failed", repr(e)


def shutdown(v1, app_id: str) -> dict:
    """Stop the deployed app by its spawn-time ID and VERIFY zero containers."""
    evidence = {"app_id": app_id}
    try:
        v1.stop_app(app_id)
    except Exception as e:                              # e.g. already stopped: still verify
        evidence["stop_error"] = repr(e)
    try:
        evidence["verification"] = v1.verify_stopped(app_id)
    except Exception as e:
        evidence["verify_error"] = repr(e)
    ok = evidence.get("verification", {}).get("verified", False)
    evidence["status"] = "stopped_verified" if ok else "shutdown_unresolved"
    return evidence


def lookup_claims(run_ids) -> dict:
    """run_id -> whether attempt 1 was claimed (i.e. a container started it)."""
    try:
        d = modal.Dict.from_name(f"m4-sgm-{GROUP}-attempts")
        return {rid: bool(d.get(f"{rid}#attempt1", False)) for rid in run_ids}
    except Exception as e:                              # no Dict yet = nothing claimed
        return {rid: f"lookup failed: {e!r}" for rid in run_ids}


UNTRACKED_RECOVERY = (
    "untracked = registered cell with no saved call ID (spawn interrupted, or the host died "
    "between server acceptance and persistence). Never respawned automatically and the app is "
    "never auto-stopped while any cell is untracked. Evidence: `claimed` (attempts Dict) and "
    "the volume dir m4-sgm/<group>/<run_id>, validated from the volume like any cell. A claimed "
    "cell is running/ran: wait, then validate. An unclaimed cell after the startup window is "
    "reported to codex/user; any respawn is a reviewed decision (a duplicate of an accepted "
    "call is replay-refused by the claim rule).")


def collect(poller=poll, claims=lookup_claims) -> dict:
    """Write finished cells exactly as v1 `consume` does (which stops + verifies on
    allowance exhaustion). Coverage is bound to the SAVED registered grid: the app
    is stopped only when all 6 registered cells are tracked AND terminal."""
    v1, root = v1_runner(), Path(LOCAL_OUT) / GROUP
    expected = [rid for rid, _t, _p in v1.expand(json.loads((root / "grid.json").read_text()))]
    if len(expected) != len(TOPUP_IDS) or set(expected) != TOPUP_IDS:
        raise SystemExit(f"saved grid is not the authorized 6-cell top-up: {sorted(expected)}")
    calls_path = root / "calls.json"
    calls = json.loads(calls_path.read_text()) if calls_path.exists() else {}
    if set(calls) - TOPUP_IDS:
        raise SystemExit(f"calls.json has unregistered cells: {sorted(set(calls) - TOPUP_IDS)}")
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
        report["untracked_recovery"] = UNTRACKED_RECOVERY
    if terminal and status == "complete":
        report["final_shutdown"] = shutdown(v1, app_id)
    atomic_write(root / "collect_status.json", json.dumps(report, indent=2, default=str))
    print(json.dumps({k: v for k, v in report.items() if k not in ("cells", "untracked_recovery")},
                     default=str), {rid: s.get("status", s["poll"]) for rid, s in states.items()})
    return report


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).resolve().parents[1])     # all paths above are repo-relative
    {"spawn": spawn, "collect": collect}[sys.argv[1]]()
