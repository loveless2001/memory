"""P2.5 Amendment PK §PK6 — priced estimate / reservation for the packed 18-cell campaign (pure arithmetic).

    .venv/bin/python scripts/sgm-p2p5-pk6-packed-campaign-priced-estimate.py --out <new json>

Inputs (all hash-recorded): the AUDITED proof timing (A100-80GB, k = 2, seeds 99/100; fab5c67 / codex 21585),
its measured volume-commit times, and the registered 18-cell grid (configs/m4_sgm_p2p5_grid.json). Nothing is
taken from the earlier packing test or the L40S profiles.

Per slot (PK1: 2 cells, same arm/N, seeds 0+1), from the slower worker of the matching T config:
  training     = 1000 x s/update(P1) + 500 x s/update(P2)          (P2C curriculum, 1500 updates)
  dev evals    = 16 evals x 4 batches x dev-batch s                 (eval_every 100, steps 0..1500)
  artifact     = 84 / 68 / 20 batches x artifact-batch s            (run_pilot as implemented)
  checkpoints  = 30 generations x (serialize s + max commit s)      (C = 50 incl. the terminal one)
  startup      = 300 s (startup_timeout)
ESTIMATE  = sum over slots of life at the hard-tuple rate (A100-80GB + 8 cores + 64 GiB list prices).
RESERVE   = per slot life x 1.4 + 3 restarts x (startup + 50 replayed + 1 in-flight P2 updates + one complete final
            evaluation repeat), at the 2x CPU/RAM basis; + readings (+10% parity) + image + reaper + $5 margin.
LIFECYCLE = 9 concurrent slot containers x the longest slot reserve life (+ reaper period + stop latency), the
            worst case under the whole-app reaper if every slot crash-loops; reported, not the planning basis.
Assumptions are listed in the output; this is a priced estimate, not a price guarantee.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.packed_slot_cell_output_validation import applicable_interventions  # noqa: E402
from memsub.sgm.packed_slot_supervisor import expand_cells  # noqa: E402

PROOF = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-pk-proof-v1/volume-evidence/p2p5-pk-proof-v1"
GRID = ROOT / "configs/m4_sgm_p2p5_grid.json"
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S, CORES, GIB = 0.000694, 0.0000131, 0.00000222, 8, 64   # 2026-10-06
C, RESTARTS, FACTOR, STARTUP_S, REAPER_PERIOD_S, STOP_LATENCY_S = 50, 3, 1.4, 300, 120, 120
READ_BATCHES, READ_INTERVENTIONS, PARITY, IMAGE_USD, MARGIN_USD = 16, 3, 0.10, 0.168384, 5.0


def rate(basis: float) -> float:
    return GPU_USD_S + basis * (CORES * CPU_USD_CORE_S + GIB * MEM_USD_GIB_S)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    t = json.loads((PROOF / "timing/timing.json").read_text())
    ex = json.loads((PROOF / "timing.exit.json").read_text())
    grid = json.loads(GRID.read_text())
    base = grid["base"]
    steps, (_, switch) = base["steps"], base["filler_len_schedule"][1]
    evals = steps // base["eval_every"] + 1
    gens = len([s for s in range(1, steps) if s % C == 0]) + 1
    commit = max(ex["commit_s"])
    cfg = {(c["arm"], c["n"], c["phase"]): c for c in t["configs"]}
    slots = {}
    for cid, pilot in expand_cells(grid).items():
        key = (pilot["arm"], pilot["n_bindings"])
        p1, p2 = cfg[(*key, 1)], cfg[(*key, 2)]
        ec = p1["eval_and_checkpoint"] + p2["eval_and_checkpoint"]
        s1, s2 = max(p1["per_worker_mean_s"]), max(p2["per_worker_mean_s"])
        dev, art = max(e["dev_eval_batch_s"] for e in ec), max(e["artifact_eval_batch_s"] for e in ec)
        ser = max(e["checkpoint_serialize_s"] for e in ec)
        n_art = len(applicable_interventions(pilot["arm"])) * 16 + 4
        parts = {"training_s": switch * s1 + (steps - switch) * s2, "dev_evals_s": evals * base["eval_batches"] * dev,
                 "artifact_eval_s": n_art * art, "checkpoints_s": gens * (ser + commit), "startup_s": STARTUP_S}
        life = sum(parts.values())
        restart = STARTUP_S + (C + 1) * s2 + n_art * art + base["eval_batches"] * dev
        reserve_life = life * FACTOR + RESTARTS * restart
        slot = f"{pilot['arm']}-n{pilot['n_bindings']}"
        slots.setdefault(slot, {"cells": [], **{k: round(v, 1) for k, v in parts.items()}, "life_s": round(life, 1),
                                "restart_allowance_s": round(restart, 1), "reserve_life_s": round(reserve_life, 1),
                                "artifact_batches": n_art, "s_per_update_p1_p2": [s1, s2],
                                "dev_batch_s": dev, "artifact_batch_s": art})["cells"].append(cid)
    if len(slots) != 9 or any(len(v["cells"]) != 2 for v in slots.values()):
        raise SystemExit("slot pairing differs from PK1 (9 slots x 2 cells)")
    # readings: one run, one container (oracle N32 + N16 transfer; memory_off 'none' only)
    rd = 0.0
    for cid, pilot in expand_cells(grid).items():
        arm, n = pilot["arm"], pilot["n_bindings"]
        for pn in ([32, 16] if arm == "oracle" else [n]):
            art = max(e["artifact_eval_batch_s"] for ph in (1, 2) for e in cfg[(arm, 32 if arm == "oracle" else pn, ph)]["eval_and_checkpoint"])
            rd += READ_BATCHES * (1 if arm == "memory_off" else READ_INTERVENTIONS) * art
    readings_s = rd * (1 + PARITY) + STARTUP_S
    est_s = sum(v["life_s"] for v in slots.values())
    res_s = sum(v["reserve_life_s"] for v in slots.values())
    longest = max(v["reserve_life_s"] for v in slots.values())
    reaper = (longest + REAPER_PERIOD_S + STOP_LATENCY_S) / REAPER_PERIOD_S * 110 * (0.125 * CPU_USD_CORE_S + 0.25 * MEM_USD_GIB_S)
    out = {
        "inputs": {"proof_timing_sha256": sha(PROOF / "timing/timing.json"), "proof_exit_sha256": sha(PROOF / "timing.exit.json"),
                   "grid_sha256": sha(GRID), "script_sha256": sha(Path(__file__)), "gpu": t["gpu"]},
        "slots": slots,
        "estimate": {"slot_gpu_hours": est_s / 3600, "readings_gpu_hours": readings_s / 3600,
                     "usd": (est_s + readings_s) * rate(1.0), "wall_h_parallel": max(v["life_s"] for v in slots.values()) / 3600},
        "planning_reserve": {"slots_usd": res_s * rate(2.0), "readings_usd": readings_s * FACTOR * rate(2.0),
                             "image_usd": IMAGE_USD, "reaper_usd": reaper, "margin_usd": MARGIN_USD},
        "lifecycle_bound_if_every_slot_crash_loops_usd": 9 * (longest + REAPER_PERIOD_S + STOP_LATENCY_S) * rate(2.0)
                                                         + readings_s * FACTOR * rate(2.0) + IMAGE_USD + MARGIN_USD,
        "assumptions": [
            "timings = audited proof T (one A100-80GB host, k = 2, 6 measured updates per config); host variation not modelled",
            "slower worker of each pair; dev/artifact batch = the max measured for that arm/N",
            "at most 3 restarts per slot (4 admitted starts), each replaying <= 50 + 1 P2 updates and one full final evaluation",
            "deadline factor 1.4 on every slot life; readings x 1.4 with a 10% parity allowance",
            "CPU/RAM on the audited 2x basis for the reserve; hard tuples for the estimate; list prices modal.com 2026-10-06",
            "9 slots run concurrently (A100-80GB availability / queueing not modelled); readings afterwards on one container",
            "preemption rate unknown: the reserve covers 3 restarts per slot, not more",
            "not a price guarantee and not a platform cash ceiling"]}
    out["planning_reserve"]["total_usd"] = sum(out["planning_reserve"].values())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2))
    print(json.dumps({"estimate_usd": round(out["estimate"]["usd"], 2),
                      "estimate_gpu_h": round(out["estimate"]["slot_gpu_hours"] + out["estimate"]["readings_gpu_hours"], 1),
                      "wall_h": round(out["estimate"]["wall_h_parallel"], 2),
                      "reserve_usd": round(out["planning_reserve"]["total_usd"], 2),
                      "lifecycle_bound_usd": round(out["lifecycle_bound_if_every_slot_crash_loops_usd"], 2)}))


if __name__ == "__main__":
    main()
