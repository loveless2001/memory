"""Price the registered 18-cell P2.5 campaign from the usable L40S timing profile
(prereg v0.2 §Ledger: frozen SKU, deadlines = profiled wall x 1.4, every charge).

Pure arithmetic: reads the profile evidence, the grid and the profile runner's list
prices; touches no Modal API. Two bases, both reported:
  bound    - every N16 cell priced at the MEASURED N32 timing (no N16 measurement exists),
             deadlines x 1.4: the basis a cap would be requested on.
  estimate - N16 scaled by serial step count (4 sinks + 2N + filler + queries), using the
             near-zero intercept the two measured fillers show; no deadline factor.
Preemption is NOT priced: a lost cell is not retried under the current protocol.

    .venv/bin/python scripts/sgm-p2p5-campaign-ledger-from-l40s-profile.py
    (re-pricing, e.g. the v2 re-timing: --profile <profile.json> --out <NEW file> --runner <runner>
     --artifact-eval-batches 52 --artifact-eval-batches-memory-off 20; defaults reproduce the
     original v1 ledger byte for byte, codex 21469/21471: original outputs are preserved)
"""

import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-l40s-profile-v1"
PROFILE = EVID / "volume-evidence/p2p5-l40s-profile-v1/profile-l40s/profile.json"
GRID = ROOT / "configs/m4_sgm_p2p5_grid.json"
OUT = EVID / "campaign-ledger-from-profile.json"

DEADLINE_FACTOR, SINKS, PROFILED_N = 1.4, 4, 32
ARTIFACT_EVAL_BATCHES = 16      # ASSUMPTION: the 18-cell runner is not built yet; 256 episodes like readings
ARTIFACT_EVAL_BATCHES_MEMORY_OFF = 16   # same assumption (overridable: run_pilot reuse = 52 memory / 20 off)
RUNNER = "modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py"
READINGS_BATCHES = 16           # prereg: 16 batches x 16 per (arm, N, seed) population
MEMORY_INTERVENTIONS = 3        # none / bank_derange / read_offset; memory_off: none only
PARITY_ALLOWANCE = 0.10         # ASSUMPTION: legacy/episode parity re-evaluation inside the readings run
FIXED_MARGIN_USD = 5.0


def runner():
    spec = importlib.util.spec_from_file_location("p2p5_prof", ROOT / RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def serial_steps(n: int, filler: int, queries: int) -> int:
    return SINKS + 2 * n + filler + queries


def per_config(profile: dict) -> dict:
    return {(c["arm"], c["train_filler_len"]): c for c in profile["configs"]}


def cell_seconds(cfgs: dict, timing_arm: str, n: int, base: dict, scale: bool, startup_s: float) -> dict:
    """Training (both curriculum phases) + in-run dev evals + artifact eval + startup."""
    (s0, f0), (s1, f1) = base["filler_len_schedule"]
    q, steps, eval_f = base["n_queries"], base["steps"], base["filler_len"]
    k = lambda f: serial_steps(n, f, q) / serial_steps(PROFILED_N, f, q) if scale else 1.0
    phase1_updates, phase2_updates = s1 - s0, steps - s1
    train = (phase1_updates * cfgs[(timing_arm, f0)]["mean_measured_s_per_update"] * k(f0)
             + phase2_updates * cfgs[(timing_arm, f1)]["mean_measured_s_per_update"] * k(f1))
    eval_batch = max(cfgs[(timing_arm, f)]["dev_eval_batch_s"] for f in (f0, f1)) * k(eval_f)
    dev = (steps // base["eval_every"] + 1) * base["eval_batches"] * eval_batch
    art = (ARTIFACT_EVAL_BATCHES_MEMORY_OFF if timing_arm == "memory_off" else ARTIFACT_EVAL_BATCHES) * eval_batch
    return {"train_s": train, "dev_eval_s": dev, "artifact_eval_s": art, "startup_s": startup_s,
            "wall_s": train + dev + art + startup_s, "eval_batch_s": eval_batch}


def cells(grid: dict) -> list:
    return [(b["override"]["arm"], n, s) for b in grid["blocks"] for n in b["n_bindings"] for s in b["seeds"]]


def intercept_check(cfgs: dict, arm: str, base: dict) -> dict:
    """Is s/update linear in serial steps through ~0? (justifies the N16 scaling proxy)"""
    q = base["n_queries"]
    a, b = cfgs[(arm, 0)]["mean_measured_s_per_update"], cfgs[(arm, 40)]["mean_measured_s_per_update"]
    per_step = (b - a) / (serial_steps(PROFILED_N, 40, q) - serial_steps(PROFILED_N, 0, q))
    return {"s_per_serial_step": per_step, "intercept_s": a - per_step * serial_steps(PROFILED_N, 0, q)}


def ledger() -> dict:
    run, profile, grid = runner(), json.loads(PROFILE.read_text()), json.loads(GRID.read_text())
    assert run.profile_usable(profile, 0, profile["memsub_source_sha256"])[0], "profile not usable"
    base, cfgs = grid["base"], per_config(profile)
    rate = run.GPU_USD_S + run.CPU_CORES * run.CPU_USD_CORE_S + run.MEMORY_GIB * run.MEM_USD_GIB_S
    timing_arm = lambda arm: "memory_off" if arm == "memory_off" else "learned"   # PROXY for single_cell/random_fixed/oracle
    out = {"profile_sha256_of_file": __import__("hashlib").sha256(PROFILE.read_bytes()).hexdigest(),
           "usd_per_container_s": rate, "sku": f"{run.GPU} preemptible, {run.CPU_CORES} cores, {run.MEMORY_GIB} GiB",
           "linearity": {a: intercept_check(cfgs, a, base) for a in ("learned", "memory_off")}, "bases": {}}
    for basis, scale, factor in (("bound", False, DEADLINE_FACTOR), ("estimate", True, 1.0)):
        rows, total_s = [], 0.0
        for arm, n, seed in cells(grid):
            c = cell_seconds(cfgs, timing_arm(arm), n, base, scale and n != PROFILED_N, run.STARTUP_S)
            life = c["wall_s"] * factor + (run.REAPER_PERIOD_S + run.STOP_LATENCY_S if factor > 1 else 0)
            rows.append({"cell": f"{arm}-n{n}-s{seed}", **{k: round(v, 1) for k, v in c.items()},
                         "charged_life_s": round(life, 1), "usd": round(life * rate, 2)})
            total_s += life
        # readings: oracle N32 + N16 transfer, every other memory arm at its own N, memory_off 'none' only
        rd = 0.0
        for arm, n, seed in cells(grid):
            pops = [32, 16] if arm == "oracle" else [n]
            for pn in pops:
                eb = cell_seconds(cfgs, timing_arm(arm), pn, base, scale and pn != PROFILED_N, 0)["eval_batch_s"]
                rd += READINGS_BATCHES * (1 if arm == "memory_off" else MEMORY_INTERVENTIONS) * eb
        rd = (rd * (1 + PARITY_ALLOWANCE) + run.STARTUP_S) * factor
        build = run.BUILD_S * run.BUILD_OVERUSE * (run.BUILD_CPU * run.CPU_USD_CORE_S + run.BUILD_GIB * run.MEM_USD_GIB_S)
        reaper = math.ceil(max(r["charged_life_s"] for r in rows) / run.REAPER_PERIOD_S + 2) * 110 * (
            0.125 * run.CPU_USD_CORE_S + 0.25 * run.MEM_USD_GIB_S)
        parts = {"cells_usd": total_s * rate, "readings_usd": rd * rate, "image_build_usd": build,
                 "reaper_usd": reaper, "fixed_margin_usd": FIXED_MARGIN_USD if factor > 1 else 0.0}
        out["bases"][basis] = {"cells": rows, "cell_gpu_hours": total_s / 3600, "readings_s": rd, **parts,
                               "total_usd": sum(parts.values()),
                               "longest_cell_life_h": max(r["charged_life_s"] for r in rows) / 3600}
    out["assumptions"] = [
        "single_cell, random_fixed and oracle are priced at the measured 'learned' timing (not profiled)",
        "bound: N16 at the measured N32 timing; estimate: N16 scaled by serial step count (intercept shown)",
        (f"artifact eval {ARTIFACT_EVAL_BATCHES} batches per cell; parity allowance {PARITY_ALLOWANCE:.0%} of readings"
         if ARTIFACT_EVAL_BATCHES == ARTIFACT_EVAL_BATCHES_MEMORY_OFF else
         f"artifact eval {ARTIFACT_EVAL_BATCHES} batches per memory cell, {ARTIFACT_EVAL_BATCHES_MEMORY_OFF} per "
         f"memory_off cell; parity allowance {PARITY_ALLOWANCE:.0%} of readings"),
        "startup = profile runner STARTUP_S per container; list prices from the profile runner (modal.com 2026-10-06)",
        "preemption not priced: cells run hours on preemptible L40S and a lost cell is not retried",
    ]
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", type=Path, default=PROFILE)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--runner", default=RUNNER)
    ap.add_argument("--artifact-eval-batches", type=int, default=ARTIFACT_EVAL_BATCHES)
    ap.add_argument("--artifact-eval-batches-memory-off", type=int, default=ARTIFACT_EVAL_BATCHES_MEMORY_OFF)
    a = ap.parse_args()
    if a.out.resolve() != OUT.resolve() and a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    PROFILE, OUT, RUNNER = a.profile, a.out, a.runner
    ARTIFACT_EVAL_BATCHES, ARTIFACT_EVAL_BATCHES_MEMORY_OFF = a.artifact_eval_batches, a.artifact_eval_batches_memory_off
    led = ledger()
    OUT.write_text(json.dumps(led, indent=2))
    for b, v in led["bases"].items():
        print(b, f"cells {v['cell_gpu_hours']:.1f} GPU-h  total ${v['total_usd']:.2f}  longest {v['longest_cell_life_h']:.2f} h")
    print(json.dumps(led["linearity"]))
