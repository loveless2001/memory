"""Bounded LOCAL Qwen smoke for the readout probe (proposal v0.2 §8.6). Run it ONLY after the codex implementation
review.

One smoke cell (taskhead learned N32, the probe cell config with seed 7, batch 2, 20 updates, filler schedule
[[0, 0], [10, 40]], C = 10) goes through the REAL ProbeSlotSupervisor -> packed_slot_worker -> path-exact validator,
with the frozen probe registry and schema.
- Namespace and populations are its own: train seed 7, dev 777_001, final 777_100 + 7, train-split 777_200 + 7. The
  probe cells and their populations are never used.
- Batch 2: the local RTX 3060 Laptop has 6 GB, and the batch-16 N32 profile ran out of memory. The smoke checks the
  output contract on the real Qwen graph, not timing.
- Bounds (codex 21783/21786): exactly 20 updates.
  - OUTER, hard: the ONLY launch form is the command below. GNU timeout (not --foreground) puts itself and this
    process in a NEW process group and SIGKILLs the WHOLE group at 3,600 s from launch: interpreter, imports,
    workers (the supervisor spawns them without a new session; they also carry PR_SET_PDEATHSIG) and cleanup.
  - Before any import, output directory or model load, the script checks that its parent is exactly that timeout with
    this exact argv and that it shares the timeout's process group. It refuses otherwise.
  - INNER: a SIGKILL Watchdog of 3,540 s, armed before any heavy import or model load. It fires BEFORE the outer
    bound, so its out-of-group sleeper never outlives the group.
- Partial evidence is kept. There is NO automatic retry, and an OOM or error is reported as-is.

    timeout --signal=KILL 3600 .venv-gpu/bin/python scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py --out <new dir>
"""

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTER_BOUND = ("timeout", "--signal=KILL", "3600")   # the ONE launch form; its group KILL covers the whole tree
INNER_S, CELL = 3540, "smoke-taskhead-learned-n32-s7"
SMOKE_EVAL = {"final_batches": 1, "final_batch_size": 4, "final_seed_base": 777_100, "dev_seed": 777_001,
              "train_eval_seed_base": 777_200}
SMOKE_OVERRIDE = {"seed": 7, "batch": 2, "steps": 20, "eval_every": 10, "eval_batches": 1,
                  "filler_len_schedule": [[0, 0], [10, 40]]}


def outer_bound_problem() -> str | None:
    """None iff the parent is `timeout --signal=KILL 3600 <this exact argv>` and this process is in its group."""
    try:
        parent = [x.decode() for x in Path(f"/proc/{os.getppid()}/cmdline").read_bytes().split(b"\0")[:-1]]
    except OSError as e:
        return f"parent command line unreadable: {e!r}"
    if (not parent or Path(parent[0]).name != OUTER_BOUND[0] or tuple(parent[1:3]) != OUTER_BOUND[1:]
            or parent[3:] != list(sys.orig_argv)):
        return f"launch ONLY as `{' '.join(OUTER_BOUND)} <python> <this script> --out <new dir>`; parent argv {parent}"
    if os.getpgid(0) != os.getppid():
        return "not in the outer timeout's process group"
    return None


def load(rel: str, name: str):
    s = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def smoke_pilot(L) -> dict:
    cell = L.probe_cells(json.loads((ROOT / L.GRID_FILE).read_text()))["taskhead-learned-n32-s0"]
    pilot = {**cell, **SMOKE_OVERRIDE}
    if pilot["seed"] in (0, 1) or SMOKE_EVAL["final_seed_base"] == L.EVAL["final_seed_base"]:
        raise SystemExit("smoke must not use the probe seeds or populations")
    return pilot


def observed_nulls(out: Path) -> dict:
    tele = [json.loads(x) for x in (out / "routing_telemetry.jsonl").read_text().splitlines()]
    tr = [r for r in tele if "loss" in r]
    return {"grad_null_keys": sorted({k for r in tr for k, v in r["grad_norm"].items() if v is None}),
            "update_null_keys": sorted({k for r in tr for k, v in r["update_norm"].items() if v is None}),
            "logged_rows": len(tr)}


def main():
    problem = outer_bound_problem()                             # FIRST: before any import, output dir or model load
    if problem:
        raise SystemExit(f"refusing the smoke: {problem}")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)                  # own namespace; never reused
    t0 = time.time()
    sys.path.insert(0, str(ROOT))
    from memsub.sgm.p2d_launch_guard import Watchdog           # stdlib-only module
    wd = Watchdog(INNER_S)                                      # BEFORE torch and any model load
    try:
        from memsub.sgm.synthetic_pilot_run import source_tree_sha256
        L = load("modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-logic.py", "slot_logic")
        PV = load(L.VALIDATOR_FILE, "probe_validation")
        pilot = smoke_pilot(L)
        registry = json.loads((ROOT / L.REGISTRY_FILE).read_text())["learned"]
        schema = json.loads((ROOT / L.SCHEMA_FILE).read_text())["learned"]
        sup = PV.ProbeSlotSupervisor(root=a.out / "slot", cells={CELL: pilot}, epoch=1, admitted=[1],
                                     identity={"memsub": source_tree_sha256(ROOT / "memsub")}, checkpoint_every=10,
                                     eval_cfg=SMOKE_EVAL, commit=lambda: None, reload=lambda: None,
                                     registry=registry, schema=schema)
        summary = {"cell": CELL, "pilot": pilot, "eval": SMOKE_EVAL, "result": sup.run()}
        rec = sup.records.get(CELL, {})
        summary.update(state=rec.get("state"), reason=rec.get("reason"))
        out = sup.attempt_dir(CELL) / "out"
        if (out / "routing_telemetry.jsonl").exists():
            summary["telemetry"] = observed_nulls(out)
    except BaseException as e:                                  # reported as-is; no retry
        summary = {"cell": CELL, "error": repr(e)[:2000]}
    finally:
        wd.cancel()
    summary["wall_s"] = time.time() - t0
    (a.out / "smoke-summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps({k: summary.get(k) for k in ("state", "reason", "telemetry", "error", "wall_s")}, default=str))
    sys.exit(0 if summary.get("state") == "COMPLETE" else 1)


if __name__ == "__main__":
    main()
