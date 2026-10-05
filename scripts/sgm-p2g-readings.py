"""P2G registered readings (prereg v0.2 `25fdbc5`). Run ONCE, only after all six
p2g-selective-write-v1 cells are collected and validated.

    .venv/bin/python scripts/sgm-p2g-readings.py \
        --runs plans/261005-0210-m4-sgm-p0-p2/runs/p2g-selective-write-v1 \
        --mirror plans/261005-0210-m4-sgm-p0-p2/runs/p2g-selective-write-v1-volume-mirror \
        --out plans/261006-0010-m4-sgm-p2g-selective-write-gate/readings-v1

Order (fail closed): observer identity -> reused inputs bound -> P2G group
bound to its committed grid/launch/source/seed (validator + mirror == local)
-> parity P-on/P-off re-run (STOP on failure) -> fresh-seed evaluation of
every T x E corner and the gate arm with the common observer -> registered
Q1/Q2 readings (scripts/sgm-p2g-decision-rules.py) -> memsub re-checked.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("p2g_preflight", ROOT / "scripts" / "sgm-p2g-preflight.py")
PRE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PRE)
OBS, VALIDATOR = PRE.OBS, PRE.load_script("sgm-recover-and-validate-grid-artifacts")
RULES = OBS.RULES
P2D = RULES.P2D
GROUP, FINAL_BASE = "p2g-selective-write-v1", 9_400_011
V1_RUNNER = ROOT / "modal-runners" / "modal-m4-sgm-p2d-diagnostics-grid.py"
LIMITS = ["Evidence class tiny-random-lm+taskhead, synthetic; no R3, scaling, pretrained or P3 claim.",
          "Cohorts differ in source/host (v2 1d62903/a89284ea, P2D 31aa4c8/d4effd0c, P2G new source); "
          "same episode hashes make evaluations paired, not training histories identical.",
          "The Step 2 seed-0 prefix (continuity) discrepancy is unresolved and inherited.",
          "Q1 compares the gate recipe to historical v2; Q2 reports registered recipe/setting contrasts, "
          "not a unique causal blocker.",
          "Suppression headline is pooled class-mean filler suppression only; AUROCs are descriptive."]


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rel(p: Path) -> str:
    """Repo-relative path for the report (absolute if outside the repo)."""
    p = Path(p).resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def load_p2g_group(runs: Path, mirror: Path, source: str) -> tuple[dict, dict]:
    """Bind the launched group to the committed grid; validate all six cells."""
    launch = json.loads((runs / "launch_provenance.json").read_text())
    grid = json.loads((runs / "grid.json").read_text())
    if (launch["grid_sha256"] != sha(PRE.GRID) or grid != json.loads(PRE.GRID.read_text())
            or grid["final_seed_base"] != FINAL_BASE or launch["memsub_source_sha256"] != source
            or launch["inputs_index_sha256"] != sha(PRE.INPUTS)):
        raise SystemExit("P2G launch does not bind the committed grid/inputs/source/seed")
    registered = VALIDATOR.registered_cells(grid, V1_RUNNER)
    cells = {}
    for rid, pilot in registered.items():
        cell = mirror / rid
        reason = VALIDATOR.validate(cell, rid, pilot, launch, source, FINAL_BASE)
        if reason is not None:
            raise SystemExit(f"{rid}: artifact validation failed: {reason}")
        man = json.loads((cell / "run_manifest.json").read_text())
        if man.get("modal_group") != GROUP:
            raise SystemExit(f"{rid}: manifest modal_group is not {GROUP}")
        local, mirrored = (json.loads((d / "metrics.json").read_text()) for d in (runs / rid, cell))
        if local.get("final") != mirrored.get("final") or sha(runs / rid / "per_example_results.jsonl") != sha(
                cell / "per_example_results.jsonl"):
            raise SystemExit(f"{rid}: local artifacts differ from the validated mirror")
        cells[rid] = (cell, man)
    return launch, cells


def corner(template: str, s: int, bound: dict, p2g: dict) -> tuple:
    key = template.format(s=s)
    return p2g[key[4:]] if key.startswith("p2g:") else bound[key]


def evaluate_cell(n: int, s: int, models: dict, out: Path) -> dict:
    """Rows + dev gate telemetry for X(T,E) and the gate arm (E=on)."""
    seed, rows, dev, cross = FINAL_BASE + s, {}, {}, {}
    plan = {("on", "on"): ("T_on", True), ("on", "off"): ("T_on", False),
            ("off", "off"): ("T_off", False), ("off", "on"): ("T_off", True), ("gate", "on"): ("gate", True)}
    for (t, e), (role, writes) in plan.items():
        cell, man = models[role]
        pcfg, backend, head = OBS.load_checkpoint(man["pilot_config"], cell / "trained_parameters.safetensors")
        print(f"N{n} s{s} X({t},{e})", man.get("run_id", cell.name), flush=True)
        r = OBS.eval_rows(backend, head, pcfg, seed, OBS.FINAL_IVS, writes)
        path = out / f"rows-n{n}-s{s}-T{t}-E{e}.jsonl"
        path.write_text(OBS.rows_text(r))
        rows[(t, e)] = r
        dev[f"T{t}-E{e}"] = {"rows_sha256": sha(path), "source_cell": rel(cell),
                             "gate": OBS.gate_summary(OBS.gate_events(backend, pcfg, writes), n),
                             "accuracy_none": sum(P2D.episode_scores(r, "none").values()) / P2D.N_EPISODES,
                             "memory_use": P2D.memory_use(r)}
        if man.get("modal_group") == GROUP and pcfg.filler_writes == writes:   # descriptive cross-host check
            modal = [x for x in saved_rows(cell) if x["intervention"] in OBS.FINAL_IVS]
            cross[f"T{t}-E{e}"] = modal == r
    on_on, on_off, off_off, off_on, gate = (rows[k] for k in (("on", "on"), ("on", "off"), ("off", "off"),
                                                                ("off", "on"), ("gate", "on")))
    return {"corners": dev, "cross_host_rows_equal_descriptive": cross,
            "q2": {"C_T|off": P2D.paired(off_off, on_off), "C_T|on": P2D.paired(off_on, on_on),
                   "C_E|Ton": P2D.paired(on_off, on_on), "C_E|Toff": P2D.paired(off_off, off_on),
                   "interaction_descriptive": RULES.interaction(off_off, on_off, off_on, on_on)},
            "q1": {"gate_vs_v2": P2D.paired(gate, on_on), "oracle_vs_v2": P2D.paired(off_off, on_on),
                   "half_oracle": RULES.half_oracle(gate, on_on, off_off),
                   "rho": dev["Tgate-Eon"]["gate"]["rho_pooled_effective"],
                   "memory_use_pass": dev["Tgate-Eon"]["memory_use"]["pass"]}}


def saved_rows(cell: Path) -> list:
    """The training run's own final-eval rows (Modal), for the cross-host check."""
    return [json.loads(l) for l in (cell / "per_example_results.jsonl").read_text().splitlines()]


def read_n(per_seed: dict) -> dict:
    """Registered readings for one N from both seeds' contrasts."""
    seeds = {str(s): v for s, v in per_seed.items()}
    labels = {k: RULES.classify({s: v["q2"][k] for s, v in seeds.items()}) for k in RULES.Q2_KEYS}
    gain_label = RULES.classify({s: v["q1"]["gate_vs_v2"] for s, v in seeds.items()})
    oracle_label = RULES.classify({s: v["q1"]["oracle_vs_v2"] for s, v in seeds.items()})
    sup = all(v["q1"]["rho"] <= RULES.RHO_MAX for v in seeds.values())
    mem = all(v["q1"]["memory_use_pass"] for v in seeds.values())
    half = RULES.half_status(oracle_label, {s: v["q1"]["half_oracle"] for s, v in seeds.items()})
    return {"q2_labels": labels, "q2_reading": RULES.q2_reading(labels),
            "q1_flags": {"gate_vs_v2": gain_label, "oracle_vs_v2": oracle_label, "suppression": sup,
                         "memory_use": mem, "half": half},
            "q1_reading": RULES.q1_reading(gain_label, sup, mem, half)}


def main():
    ap = argparse.ArgumentParser()
    for a in ("--runs", "--mirror", "--out"):
        ap.add_argument(a, type=Path, required=True)
    args = ap.parse_args()
    torch.set_num_threads(4)
    identity = PRE.observer_identity()
    index = json.loads(PRE.INPUTS.read_text())
    bound = PRE.validate_inputs(index)
    launch, p2g = load_p2g_group(args.runs, args.mirror, identity["memsub_source_sha256"])
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "parity").mkdir()
    report = {"observer": identity, "launch": launch, "final_seed_base": FINAL_BASE, "limits": LIMITS,
              "p2g_cells": {rid: {"cell": rel(c), "run_manifest_sha256": sha(c / "run_manifest.json"),
                                  "trained_parameters_sha256": sha(c / "trained_parameters.safetensors"),
                                  "rows_sha256": sha(c / "per_example_results.jsonl")} for rid, (c, _m) in p2g.items()},
              "parity": PRE.run_parity(index, bound, args.out / "parity")}
    if not report["parity"]["pass"]:
        (args.out / "p2g-readings.json").write_text(json.dumps(report, indent=2))
        raise SystemExit("PARITY FAILED at readings time: no readings")
    report["n"] = {}
    for n in (16, 32):
        per_seed = {}
        for s in (0, 1):
            models = {role: corner(t, s, bound, p2g) for role, t in index["corners"][str(n)].items()}
            per_seed[s] = evaluate_cell(n, s, models, args.out)
        report["n"][str(n)] = {"seeds": {str(s): v for s, v in per_seed.items()}, **read_n(per_seed)}
        print(f"N{n}", report["n"][str(n)]["q1_reading"], "|", report["n"][str(n)]["q2_reading"], flush=True)
    if PRE.observer_identity()["memsub_source_sha256"] != identity["memsub_source_sha256"]:
        raise SystemExit("memsub changed during readings")
    (args.out / "p2g-readings.json").write_text(json.dumps(report, indent=2, default=str))
    print("READINGS DONE", sha(args.out / "p2g-readings.json"))


if __name__ == "__main__":
    main()
