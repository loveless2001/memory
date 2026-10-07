"""P2.5 readout probe: PURE slot lifecycle logic and EVERY probe binding (proposal v0.2 §7/§8.3; codex 21750 #3).

The probe runner loads this file by path BEFORE it builds any Modal object, so app, Dicts, image inputs, volume
subpath, deadline and collect targets all come from here, never from the decorated campaign module. Nothing here
imports Modal. Plain functions are reused from the campaign by path: control-plane `provenance_problem`,
`strict_stop` and `verify_stopped`; the epoch-state walk; and the probe validator.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GROUP, SLOT = "p2p5-readout-probe-v1", "taskhead-learned-n32"
APP_NAME = "memsub-m4-sgm-p2p5-readout-probe"
GUARD_DICT, ADMIT_DICT = f"{APP_NAME}-guard", f"{APP_NAME}-admission"
LOCAL_OUT = "plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe"
VOLUME_SUBPATH = f"m4-sgm/{GROUP}/{SLOT}"            # container: /artifacts/<VOLUME_SUBPATH>
GRID_FILE = "configs/m4_sgm_p2p5_readout_probe_grid.json"
REGISTRY_FILE = "configs/m4_sgm_p2p5_readout_probe_registry.json"
SCHEMA_FILE = "configs/m4_sgm_p2p5_readout_probe_output_schema.json"
LEDGER_FILE = f"{LOCAL_OUT}/probe-priced-ledger.json"
VALIDATOR_FILE = "scripts/sgm-p2p5-readout-probe-output-validation.py"
SLOT_LOGIC_FILE = "modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-logic.py"
LIFETIME_LOGIC_FILE = "modal-runners/modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py"
CONTROL_LOGIC_FILE = "modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py"   # pure helpers only
BOUND_FILES = (GRID_FILE, REGISTRY_FILE, SCHEMA_FILE, LEDGER_FILE, VALIDATOR_FILE, SLOT_LOGIC_FILE, LIFETIME_LOGIC_FILE)
MODEL_DIR, MODEL_REVISION = "/root/models/qwen3-0.6b-base", "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"
GPU, CPU_CORES, MEMORY_GIB, MAX_STARTS, C, EARLY_S = "A100-80GB", 8.0, 64, 4, 50, 120
FUNCTION_MAX_S, REAPER_PERIOD_S, ABANDON_S, COLLECT_GRACE_S = 86400, 120, 1800, 300
EVAL = {"final_batches": 16, "final_batch_size": 16, "final_seed_base": 9_300_011, "dev_seed": 4242,
        "train_eval_seed_base": 555_001}
CAMPAIGN_WRITABLE = ("memsub-m4-sgm-p2p5-pk-campaign", "p2p5-qwen3-0p6b-screen-v1", "m4-sgm-p2p5-pk-campaign-control",
                     "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen")   # must never be a probe target (tested)


def load(rel: str, name: str, root: Path = REPO):
    spec = importlib.util.spec_from_file_location(name, Path(root) / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def probe_cells(grid: dict) -> dict:
    """The registered universe: exactly taskhead learned N32 x seeds 0/1."""
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from memsub.sgm.packed_slot_supervisor import expand_cells
    cells = expand_cells(grid)
    ok = (sorted(cells) == ["taskhead-learned-n32-s0", "taskhead-learned-n32-s1"]
          and all(p["arm"] == "learned" and p["readout"] == "taskhead" and p["n_bindings"] == 32 for p in cells.values()))
    if not ok:
        raise SystemExit(f"probe grid expands to {sorted(cells)}, not the 2 registered taskhead cells")
    return cells


def deadline_s(ledger: dict) -> float:
    """The ONE immutable whole-slot lifetime (seconds) from the bound ledger."""
    d = ledger.get("deadline_s")
    if not (isinstance(d, (int, float)) and not isinstance(d, bool) and math.isfinite(d) and d > 0):
        raise SystemExit(f"ledger deadline_s invalid: {d!r}")
    return float(d)


def valid_deadline(x) -> bool:
    """Finite, positive and not a bool (codex 21752: the shared helper accepts NaN / +inf / True)."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def bound_id(x) -> bool:
    return isinstance(x, str) and bool(x.strip())


def admit(adm, guard, now: float) -> tuple[int | None, str | None]:
    """Atomic start claim (<= MAX_STARTS). Refused unless the guard is fully BOUND: a nonempty app id and a valid
    deadline that has not passed (a malformed or interrupted spawn binding never runs the GPU)."""
    deadline = guard.get("deadline_epoch", None)
    if not bound_id(guard.get("app_id", None)):
        return None, "guard has no bound app id"
    if not valid_deadline(deadline) or now > deadline:
        return None, "past the slot deadline (or deadline unset / non-finite)"
    for n in range(1, MAX_STARTS + 1):
        if adm.put(f"start-{n}", now, skip_if_exists=True):
            return n, None
    return None, "start allowance exhausted"


SPAWN_MARGIN_S = 600         # spawn refused within 10 min of the reaper's abandonment stop (no bind/stop race)


def spawn_guard_problem(guard: dict, deployed_id, now: float) -> str | None:
    """Before spawn the guard may hold ONLY the reaper's first_tick / self_app_id (equal to the deployed id), with
    the abandonment stop still >= SPAWN_MARGIN_S away. Anything else means spawned or reaped before: refuse."""
    if not bound_id(deployed_id):
        return "deployed app id unavailable"
    extra = sorted(set(guard) - {"first_tick", "self_app_id"})
    if extra:
        return f"guard Dict already used {extra}: spawned or reaped before"
    if "self_app_id" in guard and guard["self_app_id"] != deployed_id:
        return f"reaper bound {guard['self_app_id']!r}, not the deployed {deployed_id!r}"
    first = guard.get("first_tick")
    if first is not None and (not valid_deadline(first) or now > first + ABANDON_S - SPAWN_MARGIN_S):
        return "too close to (or past) the reaper's abandonment stop: redeploy decision needed"
    return None


def reap_decision(store, now: float, self_app_id) -> tuple[str | None, str | None, str | None]:
    """(stop reason, bound id to stop, problem). The probe's own reaper decision; the shared helper is NOT used for
    deciding (codex 21752). Every stop carries THIS app's bound id, never None:
      * self id: the reaper's read-only lookup, bound write-once in the guard; a later mismatch never stops.
      * guard app id written at spawn: it must equal the bound self id, else never stop (quarantined, unresolved).
      * bound app id + valid deadline: stop once the deadline has passed.
      * no app id, or a missing/malformed deadline (unspawned, interrupted or malformed binding): bounded
        abandonment, i.e. stop ABANDON_S after the first tick."""
    store.put("first_tick", now, skip_if_exists=True)
    if not bound_id(self_app_id):
        return None, None, "own app id unavailable: no stop (next tick retries)"
    store.put("self_app_id", self_app_id, skip_if_exists=True)
    if store.get("self_app_id", None) != self_app_id:
        return None, None, f"bound self id {store.get('self_app_id', None)!r} != {self_app_id!r}: never stop"
    app_id = store.get("app_id", None)
    if app_id is not None and app_id != self_app_id:
        return None, None, f"guard app id {app_id!r} is not this app {self_app_id!r}: never stop"
    deadline = store.get("deadline_epoch", None)
    if app_id is not None and valid_deadline(deadline):
        return ("deadline passed" if now > deadline else None), self_app_id, None
    first = store.get("first_tick", now)
    if not valid_deadline(first):
        return None, None, f"first_tick malformed {first!r}: no stop"
    return ("abandoned or malformed binding" if now > first + ABANDON_S else None), self_app_id, None


def reap_and_stop(store, now: float, self_app_id, stopper) -> dict:
    """The bound-id whole-app stop comes FIRST; evidence writes follow and never delay it. A stop error is recorded,
    and the next tick (function timeout 110 s < 120 s period) tries again."""
    reason, bound, problem = reap_decision(store, now, self_app_id)
    if problem or reason is None:
        return {"stop": False, **({"problem": problem} if problem else {})}
    print(f"M4SGM_PROBE_REAPER_STOP app={APP_NAME} bound={bound} reason={reason} t={now:.0f}", flush=True)
    out = {"stop": True, "reason": reason, "bound": bound}
    try:
        stopper(APP_NAME, bound)
    except Exception as e:
        out["stop_error"] = repr(e)[:300]
    try:
        store.put("reaper_fired", {"t": now, "reason": reason, "bound": bound}, skip_if_exists=True)
    except Exception:
        pass
    return out


def cell_report(cell_dir: Path, pilot: dict, admitted: list[int], memsub_sha: str, registry: dict, schema: dict,
                terminal: bool, validate) -> dict:
    """Authoritative state of one cell from fetched evidence (campaign rule, probe validator): the highest admitted
    epoch with an acknowledged record and its canonical chain; COMPLETE is re-validated; a non-terminal cell at slot
    end is LOST (never resumed or relabelled); malformed evidence is contained per cell as INVALID."""
    from memsub.sgm import packed_slot_epoch_state as es
    try:
        epochs = sorted(int(p.name.split("-")[1]) for p in cell_dir.glob("epoch-*")) if cell_dir.exists() else []
        if any(m not in admitted for m in epochs):
            return {"state": "INVALID", "problem": f"epoch dirs {epochs} not all admitted {admitted}"}
        rec = next((r for m in reversed(epochs) if (r := es.read_record(cell_dir, m)) is not None), None)
        if rec is None:
            return {"state": "LOST" if terminal else "NOT_STARTED", "problem": "no acknowledged record"}
        walk = es.canonical_walk(rec, max_len=len(admitted))
        out = {"state": rec["state"], "epoch": rec["epoch"], "epochs": [w["epoch"] for w in walk],
               "reason": rec.get("reason")}
        if rec["state"] == es.COMPLETE:
            problem = validate(cell_dir.parents[1] / rec["outputs"]["attempt"] / "out", rec["outputs"]["files"], pilot,
                               EVAL, memsub_sha, registry, schema)
            out["validation"] = problem or "valid"
        elif rec["state"] not in (es.FAILED, es.LOST) and terminal:
            out.update(state="LOST", problem=f"not terminal ({rec['state']}) when the slot ended")
        return out
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, OSError) as e:
        return {"state": "INVALID", "problem": f"malformed cell evidence: {e!r:.300}"}


def write_status(root: Path, report: dict) -> None:
    tmp = root / "collect_status.json.tmp"
    tmp.write_text(json.dumps(report, indent=2, default=str))
    os.replace(tmp, root / "collect_status.json")


def collect(root: Path, *, cp, poller, stopper, verifier, fetch, export, now: float, cells: dict, registry: dict,
            schema: dict, validate) -> dict:
    """Idempotent (campaign collect order, probe bindings). Provenance is validated BEFORE any poll or side effect.
    When the call is terminal, untracked or past deadline + grace: stop by the BOUND id, then verify with zero tasks
    and containers, and write that durably BEFORE any evidence handling. Then fetch into a FRESH collect-k dir,
    export the Dicts, and report every cell. A failed fetch or export leaves every cell UNAVAILABLE."""
    try:
        prov = json.loads((root / "launch_provenance.json").read_text())
    except (OSError, ValueError):
        prov = None
    problem = cp.provenance_problem(prov, slot=SLOT)
    if problem:
        raise SystemExit(f"{SLOT}: {problem}: refusing")
    try:
        call = json.loads((root / "call.json").read_text())["call_id"]
    except (OSError, ValueError, KeyError, TypeError):
        call = None
    kind, payload = (poller(call) if call else ("untracked", None))
    past = now > prov["deadline_epoch"] + COLLECT_GRACE_S
    report = {"slot": SLOT, "call_id": call, "poll": kind, "result": payload, "past_deadline": past}
    if kind not in ("pending", "untracked") or past or call is None:
        sd = {"app_id": prov["deployed_app_id"]}
        try:
            cp.strict_stop(stopper, APP_NAME, prov["deployed_app_id"])
        except Exception as e:
            sd["stop_error"] = repr(e)[:300]
        sd["verification"] = verifier(prov["deployed_app_id"])
        sd["status"] = "stopped_verified" if sd["verification"].get("verified") is True else "shutdown_unresolved"
        report["final_shutdown"] = sd
        write_status(root, report)                        # durable BEFORE any evidence handling
        dest = root / "volume-evidence" / f"collect-{1 + len(list((root / 'volume-evidence').glob('collect-*')))}"
        report["evidence"] = fetch(dest)
        try:
            dicts = export(root)
            report["dicts"] = {k: (len(v) if isinstance(v, dict) else v) for k, v in dicts.items()}
        except Exception as e:
            dicts, report["dicts_error"] = None, repr(e)[:300]
        if report["evidence"].get("returncode") != 0 or dicts is None:
            why = "evidence fetch failed this collect" if report["evidence"].get("returncode") != 0 else "Dict export failed"
            report["cells"] = {c: {"state": "UNAVAILABLE", "problem": why} for c in cells}
        else:
            admitted = sorted(int(k.split("-")[1]) for k in (dicts.get("admission") or {}) if k.startswith("start-"))
            report["evidence_dir"] = str(dest)
            report["cells"] = {c: cell_report(dest / SLOT / "cells" / c, p, admitted, prov["expected_identity"]["memsub"],
                                              registry, schema, terminal=True, validate=validate)
                               for c, p in cells.items()}
    write_status(root, report)
    return report
