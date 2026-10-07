"""P2.5 Amendment PK §PK6 — priced estimate / reservation for the packed 18-cell campaign (pure arithmetic).

    .venv/bin/python scripts/sgm-p2p5-pk6-packed-campaign-priced-estimate.py --out <new json>

Inputs (all hash-recorded): the AUDITED proof timing (A100-80GB, k = 2, 2 warmup + 4 measured, seeds 99/100;
fab5c67 / codex 21585), its measured volume-commit times, and the registered 18-cell grid. Nothing is taken from
the earlier packing test or the L40S profiles.

Per slot (PK1: 2 cells, same arm/N, seeds 0+1), per-worker s/update = k / PRIMARY fixed-work rate:
  training      = 1000 x s(P1) + 500 x s(P2)
  dev evals     = 16 evals x 4 batches x dev-batch s
  artifact      = 84 / 68 / 20 batches x artifact-batch s
  checkpoints   = both cells' 30 generations x (serialize s + bytes / WRITE_MB_S)
  commits       = 67 (66 actual successful-start calls; conservative) x the max measured commit s
  startup       = 300 s
ESTIMATE = sum of slot lives + readings at the hard-tuple rate.
READINGS (v6, codex 21617 R6) itemised from the final reader: bind/validation of 18 cells, 18 parity loads + one
           artifact batch each, 20 reserved populations (oracle N32 + N16 transfer and every memory arm on 3
           interventions per prereg; memory_off 'none' only) each loaded once, 16 x 4 dev-batch gate telemetry,
           start/end checkpoint re-hash, startup, + 10% unattributed per-row work (row text/hash/writes, rules).
RESERVE  = PER-APP LIFECYCLE ENVELOPE: 9 slot apps (deadline = life x 1.4 + 3 restarts x (startup + reload + 51 P2
           updates + one complete final evaluation)) + 1 readings app (ONE admitted start: life x 1.4), each charged
           its whole lifetime + control period + stop latency at the 2x CPU/RAM basis; ONE control-plane reaper
           schedule (each tick billed timeout + startup at the 2x basis); image per app incl. the controller;
           $5 margin. The single-app line is illustrative only (no reaper line).
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
# v3 (codex 21594): explicit I/O + lifecycle allowances (assumptions, stated in the output)
WRITE_MB_S = 50.0            # atomic tmp + fsync + rename of a generation on the volume mount (assumed floor)
EXTRA_COMMITS_PER_CELL = 3   # inheritance ack, outputs-before-COMPLETE, COMPLETE publication
EXTRA_COMMITS_PER_SLOT = 1   # final commit after the supervisor returns
RELOAD_S = 30.0              # checkpoint + generation load on a resumed start (allowance)
READ_LOAD_S = 30.0           # readings: checkpoint build/load per population AND per parity cell (allowance)
BIND_S = 30.0                # readings: per-cell record walk + output hashing + row/metric validation (allowance)
TICK_S, TICK_STARTUP_S = 110, 30   # controller tick: function timeout + container startup allowance
N_APPS = 10                  # 9 slot apps + 1 readings app, each its own guard/deadline (+ one control app)
N_IMAGES = N_APPS + 1        # v6: the controller image is charged too (one build per app, no cache assumed)
CONTROL_SLACK_S = 1800       # v4: ONE control-plane reaper schedule
SPAWN_OFFSET_S, VALIDATION_SETUP_S, CONTROL_FALLBACK_S = 1800, 3600, 1800   # v5 (codex 21600 #1/#3) horizon
READ_BATCHES, READ_INTERVENTIONS, UNATTRIBUTED, IMAGE_USD, MARGIN_USD = 16, 3, 0.10, 0.168384, 5.0
TELEMETRY_DEV_BATCHES = 4    # gate telemetry per memory-arm population (dev population 4 x 16)
V5 = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk6/priced-estimate-v5.json"


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
    steps, (switch, _filler) = base["steps"], base["filler_len_schedule"][1]   # [[0, 0], [1000, 40]] -> switch 1000
    if (switch, steps - switch) != (1000, 500):                                  # v1 bug (codex 21591): switch was 40
        raise SystemExit(f"curriculum split {switch}/{steps - switch} != registered 1000/500")
    evals = steps // base["eval_every"] + 1
    gens = len([s for s in range(1, steps) if s % C == 0]) + 1
    commit = max(ex["commit_s"])
    k = t["timing_spec"]["k"]
    cfg = {(c["arm"], c["n"], c["phase"]): c for c in t["configs"]}
    slots = {}
    for cid, pilot in expand_cells(grid).items():
        key = (pilot["arm"], pilot["n_bindings"])
        p1, p2 = cfg[(*key, 1)], cfg[(*key, 2)]
        ec = p1["eval_and_checkpoint"] + p2["eval_and_checkpoint"]
        # PRIMARY fixed-work rate (codex 21594): per-worker s/update = k / fixed-work updates per s
        s1, s2 = k / p1["fixed_work_updates_per_s"], k / p2["fixed_work_updates_per_s"]
        ckpt_mb = max(e["checkpoint_bytes"] for e in ec) / 1e6
        dev, art = max(e["dev_eval_batch_s"] for e in ec), max(e["artifact_eval_batch_s"] for e in ec)
        ser = max(e["checkpoint_serialize_s"] for e in ec)
        n_art = len(applicable_interventions(pilot["arm"])) * 16 + 4
        commits = 2 * gens + 2 * EXTRA_COMMITS_PER_CELL + EXTRA_COMMITS_PER_SLOT     # all on the critical path
        parts = {"training_s": switch * s1 + (steps - switch) * s2, "dev_evals_s": evals * base["eval_batches"] * dev,
                 "artifact_eval_s": n_art * art,
                 "checkpoint_write_s": 2 * gens * (ser + ckpt_mb / WRITE_MB_S),      # both cells, serialised
                 "commits_s": commits * commit, "startup_s": STARTUP_S}
        life = sum(parts.values())
        restart = STARTUP_S + RELOAD_S + (C + 1) * s2 + n_art * art + base["eval_batches"] * dev
        reserve_life = life * FACTOR + RESTARTS * restart
        slot = f"{pilot['arm']}-n{pilot['n_bindings']}"
        slots.setdefault(slot, {"cells": [], **{kk: round(v, 1) for kk, v in parts.items()}, "life_s": round(life, 1),
                                "commits_per_slot": commits,
                                "restart_allowance_s": round(restart, 1), "reserve_life_s": round(reserve_life, 1),
                                "artifact_batches": n_art, "s_per_update_p1_p2": [s1, s2],
                                "dev_batch_s": dev, "artifact_batch_s": art})["cells"].append(cid)
    if len(slots) != 9 or any(len(v["cells"]) != 2 for v in slots.values()):
        raise SystemExit("slot pairing differs from PK1 (9 slots x 2 cells)")
    # readings (v6 itemised, codex 21617 R6): one run, one container, the order of the final reader
    def batch_s(arm, n, key):          # oracle N16 transfer runs the N32-trained checkpoint on the N16 population
        return max(e[key] for ph in (1, 2) for e in cfg[(arm, 32 if arm == "oracle" else n, ph)]["eval_and_checkpoint"])
    cells = expand_cells(grid)
    pops = [(p["arm"], pn) for p in cells.values() for pn in ([32, 16] if p["arm"] == "oracle" else [p["n_bindings"]])]
    ckpt_mb = max(e["checkpoint_bytes"] for c in t["configs"] for e in c["eval_and_checkpoint"]) / 1e6
    rd_parts = {
        "bind_validation_s": len(cells) * BIND_S,
        "parity_s": sum(READ_LOAD_S + batch_s(p["arm"], p["n_bindings"], "artifact_eval_batch_s") for p in cells.values()),
        "reserved_load_s": len(pops) * READ_LOAD_S,
        "reserved_eval_s": sum(READ_BATCHES * (1 if arm == "memory_off" else READ_INTERVENTIONS)
                               * batch_s(arm, n, "artifact_eval_batch_s") for arm, n in pops),
        "gate_telemetry_s": sum(TELEMETRY_DEV_BATCHES * batch_s(arm, n, "dev_eval_batch_s")
                                for arm, n in pops if arm != "memory_off"),
        "checkpoint_rehash_s": 2 * len(cells) * ckpt_mb / WRITE_MB_S,
        "startup_s": STARTUP_S}
    rd_parts["unattributed_s"] = UNATTRIBUTED * sum(v for k, v in rd_parts.items() if k != "startup_s")
    readings_s = sum(rd_parts.values())
    counts = {"checkpoint_builds": len(cells) + len(pops), "parity_cells": len(cells), "reserved_populations": len(pops),
              "telemetry_dev_batches": TELEMETRY_DEV_BATCHES * sum(arm != "memory_off" for arm, _n in pops)}
    est_s = sum(v["life_s"] for v in slots.values())
    res_s = sum(v["reserve_life_s"] for v in slots.values())
    longest = max(v["reserve_life_s"] for v in slots.values())
    tail = REAPER_PERIOD_S + STOP_LATENCY_S
    readings_life = readings_s * FACTOR                # ONE admitted start, retries 0: no restart allowance
    # v5: the controller covers the COMPLETE sequential horizon + its finite fallback window
    control_life = (SPAWN_OFFSET_S + longest + VALIDATION_SETUP_S + readings_life + CONTROL_SLACK_S
                    + CONTROL_FALLBACK_S + tail)
    reaper = (control_life / REAPER_PERIOD_S * (TICK_S + TICK_STARTUP_S)
              * 2 * (0.125 * CPU_USD_CORE_S + 0.25 * MEM_USD_GIB_S))      # v6: 2x requested basis, startup charged
    import subprocess
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    out = {
        "inputs": {"proof_timing_sha256": sha(PROOF / "timing/timing.json"), "proof_exit_sha256": sha(PROOF / "timing.exit.json"),
                   "grid_sha256": sha(GRID), "script_sha256": sha(Path(__file__)), "gpu": t["gpu"],
                   "memsub_source_sha256": source_tree_sha256(ROOT / "memsub"),
                   "prereg_sha256": sha(ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/prereg.md"),
                   "amendment_sha256": sha(ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/prereg-amendment-pk-packed-a100-resume.md"),
                   "accepted_proof": {"commit": "fab5c67", "acceptance_sha256": sha(PROOF.parents[1] / "acceptance.json"),
                                      "audit": "codex 21585"},
                   "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                              cwd=ROOT).stdout.strip()},
        "supersedes": {"v5_sha256": sha(V5), "why": "codex 21617 R6: itemised readings workload of the final reader, "
                       "controller image + 2x tick basis; v5 bytes preserved"},
        "envelope_design": ("per-app lifecycle envelope: 9 slot apps (max_containers=1, <= 4 admitted starts each, "
                            "one immutable guard deadline = that slot's reserve life) + 1 readings app (max_containers=1, "
                            "ONE admitted start, retries 0, deadline = the readings reserve life); every app is stopped "
                            "by its bound id at its own deadline by ONE control-plane reaper app (a single 120 s schedule) "
                            "whose own armed deadline covers the whole sequential horizon + a finite fallback. "
                            "Implemented: slot runner, readings runner, control-plane reaper (Gate-3 package)."),
        "slots": slots,
        "readings": {"life_s": round(readings_s, 1), "reserve_life_s": round(readings_life, 1), "admitted_starts": 1,
                     "population_units": len(pops), "items_s": {k: round(v, 1) for k, v in rd_parts.items()},
                     "counts": counts},
        "control_plane": {"schedules": 1, "period_s": REAPER_PERIOD_S, "life_s": round(control_life, 1),
                          "tick_billed_s": TICK_S + TICK_STARTUP_S, "requested": {"cpu": 0.125, "memory_gib": 0.25},
                          "billing_basis": "2x requested"},
        "estimate": {"slot_gpu_hours": est_s / 3600, "readings_gpu_hours": readings_s / 3600,
                     "usd": (est_s + readings_s) * rate(1.0), "wall_h_slots_parallel": max(v["life_s"] for v in slots.values()) / 3600,
                     "wall_h_end_to_end": (max(v["life_s"] for v in slots.values()) + readings_s) / 3600},
        "planning_reserve_per_app_envelope": {
            "slot_apps_usd": (res_s + 9 * tail) * rate(2.0),
            "readings_app_usd": (readings_life + tail) * rate(2.0),
            "image_usd": IMAGE_USD * N_IMAGES, "reaper_usd": reaper, "margin_usd": MARGIN_USD},
        "single_app_lifecycle_for_comparison_usd": 9 * (longest + tail) * rate(2.0)
                                                   + (readings_s * FACTOR + tail) * rate(2.0) + IMAGE_USD + MARGIN_USD,
        "margin_covers": "billing rounding and unmodelled small I/O (log/telemetry writes); NOT restarts, commits, "
                         "evaluation repeats or lifetimes, which are charged explicitly above (no double counting)",
        "assumptions": [
            "timings = audited proof T (one A100-80GB host, k = 2, 2 warmup + 4 measured updates per config); host variation not modelled",
            "per-worker s/update = k / PRIMARY fixed-work rate; dev/artifact batch = the max measured for that arm/N",
            f"generation write {WRITE_MB_S} MB/s incl. fsync (assumed); all {EXTRA_COMMITS_PER_CELL} extra commits per cell + 1 per slot and every generation commit serialised on the critical path at the max measured commit",
            f"resumed start reload {RELOAD_S} s; readings checkpoint build/load {READ_LOAD_S} s per population and per parity cell; bind/validation {BIND_S} s per cell",
            f"readings itemised from the final reader: {len(cells)} parity + {len(pops)} reserved checkpoint builds, {counts['telemetry_dev_batches']} telemetry dev batches, start/end checkpoint re-hash at {WRITE_MB_S} MB/s, + {UNATTRIBUTED:.0%} unattributed per-row work",
            "oracle reserved populations (N32 and the N16 transfer) use 3 interventions (prereg: memory arms); the interface reads 'none'",
            f"images: one {IMAGE_USD} USD build per app ({N_IMAGES} incl. the controller), no cross-app cache assumed",
            f"controller: each 120 s tick billed {TICK_S} s timeout + {TICK_STARTUP_S} s startup at 2x its requested 0.125 CPU / 0.25 GiB; actual use above the request is billed by Modal and is not bounded here",
            "any comparison with the preserved single-L40S model is arithmetic across differently scoped models, not a measured matched-host saving",
            "readings app: ONE admitted start, retries 0, fails closed on crash re-entry (no restart allowance)",
            "one control-plane reaper schedule stops every app at its own absolute deadline (+ period + stop latency)",
            "at most 3 restarts per slot (4 admitted starts), each replaying <= 50 + 1 P2 updates and one full final evaluation",
            "deadline factor 1.4 on every slot life and on the itemised readings life",
            "CPU/RAM on the audited 2x basis for the reserve; hard tuples for the estimate; list prices modal.com 2026-10-06; nominal reaper period / stop latency",
            "9 slots run concurrently (A100-80GB availability / queueing not modelled); readings afterwards on one container",
            "preemption rate unknown: the reserve covers 3 restarts per slot, not more",
            "Modal timeouts exclude startup and allow some execution overrun; nominal stop latency",
            "CONDITIONAL planning reserve under these assumptions: not a price guarantee, not a platform cash ceiling, not an unconditional worst case"]}
    out["planning_reserve_per_app_envelope"]["total_usd"] = sum(out["planning_reserve_per_app_envelope"].values())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2))
    print(json.dumps({"estimate_usd": round(out["estimate"]["usd"], 2),
                      "estimate_gpu_h": round(out["estimate"]["slot_gpu_hours"] + out["estimate"]["readings_gpu_hours"], 1),
                      "wall_h_end_to_end": round(out["estimate"]["wall_h_end_to_end"], 2),
                      "reserve_per_app_envelope_usd": round(out["planning_reserve_per_app_envelope"]["total_usd"], 2),
                      "single_app_lifecycle_usd": round(out["single_app_lifecycle_for_comparison_usd"], 2)}))


if __name__ == "__main__":
    main()
