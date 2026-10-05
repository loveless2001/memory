"""P2C registered readings (prereg v0.2 `0c8d358`). Run ONCE, only after all four
p2c-filler-curriculum-v1 cells are collected and validated.

    .venv/bin/python scripts/sgm-p2c-readings.py \
        --runs plans/261005-0210-m4-sgm-p0-p2/runs/p2c-filler-curriculum-v1 \
        --mirror plans/261005-0210-m4-sgm-p0-p2/runs/p2c-filler-curriculum-v1-volume-mirror \
        --out plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/readings-v1

Order (fail closed): observer identity -> reused inputs bound -> P2C group bound
to its committed grid/launch/source/seeds (validator, artifact seed, mirror ==
local) -> parity re-run (STOP on failure) -> reserved-population evaluation of
v2 / reference / curriculum, all E=on, with the common observer -> per-N
readings -> executed identity and consumed cells re-checked.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PRE2C = _load("sgm-p2c-preflight")
PRE = PRE2C.PRE                                    # private P2G-preflight instance bound to P2C constants
OBS, VALIDATOR, CRULES = PRE.OBS, PRE.load_script("sgm-recover-and-validate-grid-artifacts"), _load("sgm-p2c-decision-rules")
RULES = OBS.RULES                                  # one rules instance for every interval/classifier
P2D = RULES.P2D
GROUP, ARTIFACT_BASE, READINGS_BASE = "p2c-filler-curriculum-v1", 9_300_011, 9_500_011
V1_RUNNER = ROOT / "modal-runners" / "modal-m4-sgm-p2d-diagnostics-grid.py"
LIMITS = ["Evidence class tiny-random-lm+taskhead, synthetic; no R3, scaling, pretrained or P3 claim.",
          "Label-free recipe contrast (curriculum vs v2): interference/address learning are possible explanations, "
          "not confirmed or excluded mechanisms; equal updates are not equal token/compute exposure.",
          "filler_len 0 also shortens sources: 'no filler' and 'shorter episodes' are not separated.",
          "Cohorts differ in source/host (v2, P2D, P2G, P2C); the seed-0 prefix discrepancy is unresolved.",
          "Readings are per N; support at both loads requires both per-N SUPPORTS readings.",
          "Dev curves measure transfer to full-filler episodes; descriptive, they select nothing."]


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rel(p: Path) -> str:
    p = Path(p).resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def artifact_seed_problem(cell: Path, man: dict, seed: int) -> str | None:
    split = json.loads((cell / "split_manifest.json").read_text())["seeds"]["final_eval"]
    want, reserved = ARTIFACT_BASE + seed, READINGS_BASE + seed
    if man.get("final_eval_seed") != want or split != want or reserved in (man.get("final_eval_seed"), split):
        return f"training eval seeds manifest={man.get('final_eval_seed')} split={split}, want {want}"
    return None


def load_p2c_group(runs: Path, mirror: Path, source: str) -> tuple[dict, dict]:
    """Bind the launched group to the committed grid; validate all four cells."""
    launch = json.loads((runs / "launch_provenance.json").read_text())
    grid = json.loads((runs / "grid.json").read_text())
    if (launch["grid_sha256"] != sha(PRE.GRID) or grid != json.loads(PRE.GRID.read_text())
            or grid["artifact_eval_seed_base"] != ARTIFACT_BASE or grid["readings_seed_base"] != READINGS_BASE
            or launch["artifact_eval_seed_base"] != ARTIFACT_BASE or launch["memsub_source_sha256"] != source
            or launch["inputs_index_sha256"] != sha(PRE.INPUTS)):
        raise SystemExit("P2C launch does not bind the committed grid/inputs/source/seeds")
    cells = {}
    for rid, pilot in VALIDATOR.registered_cells(grid, V1_RUNNER).items():
        cell = mirror / rid
        reason = VALIDATOR.validate(cell, rid, pilot, launch, source, ARTIFACT_BASE)
        man = json.loads((cell / "run_manifest.json").read_text()) if reason is None else {}
        reason = reason or artifact_seed_problem(cell, man, pilot["seed"])
        if reason is not None:
            raise SystemExit(f"{rid}: artifact validation failed: {reason}")
        if man.get("modal_group") != GROUP:
            raise SystemExit(f"{rid}: manifest modal_group is not {GROUP}")
        local, mirrored = (json.loads((d / "metrics.json").read_text()) for d in (runs / rid, cell))
        if local.get("final") != mirrored.get("final") or sha(runs / rid / "per_example_results.jsonl") != sha(
                cell / "per_example_results.jsonl"):
            raise SystemExit(f"{rid}: local artifacts differ from the validated mirror")
        cells[rid] = (cell, man)
    if len(cells) != 4:
        raise SystemExit(f"P2C needs exactly 4 registered cells, got {sorted(cells)}")
    return launch, cells


def dev_curve(cell: Path) -> list:
    """(update, full-filler dev accuracy) from the run's own telemetry (descriptive)."""
    rows = [json.loads(l) for l in (cell / "routing_telemetry.jsonl").read_text().splitlines()]
    return [[r["step"], r["eval"]["accuracy"]] for r in rows if "eval" in r]


def evaluate_seed(n: int, s: int, models: dict, out: Path) -> dict:
    """v2 / reference / curriculum on the reserved population, all E=on."""
    rows, corners = {}, {}
    for role in ("v2", "reference", "curriculum"):
        cell, man = models[role]
        pcfg, backend, head = OBS.load_checkpoint(man["pilot_config"], cell / "trained_parameters.safetensors")
        print(f"N{n} s{s} {role}", man.get("run_id", cell.name), flush=True)
        r = OBS.eval_rows(backend, head, pcfg, READINGS_BASE + s, OBS.FINAL_IVS, True)
        path = out / f"rows-n{n}-s{s}-{role}.jsonl"
        path.write_text(OBS.rows_text(r))
        rows[role] = r
        corners[role] = {"rows_sha256": sha(path), "source_cell": rel(cell),
                         "accuracy_none": sum(P2D.episode_scores(r, "none").values()) / P2D.N_EPISODES,
                         "memory_use": P2D.memory_use(r),
                         "gate": OBS.gate_summary(OBS.gate_events(backend, pcfg, True), n)}
    cur, v2, ref = rows["curriculum"], rows["v2"], rows["reference"]
    return {"corners": corners, "curriculum_vs_v2": P2D.paired(cur, v2), "reference_vs_v2": P2D.paired(ref, v2),
            "half_reference": RULES.half_oracle(cur, v2, ref),
            "curriculum_dev_curve_descriptive": dev_curve(models["curriculum"][0])}


def read_n(per_seed: dict) -> dict:
    seeds = {str(s): v for s, v in per_seed.items()}
    gain_label = RULES.classify({s: v["curriculum_vs_v2"] for s, v in seeds.items()})
    ref_label = RULES.classify({s: v["reference_vs_v2"] for s, v in seeds.items()})
    mem = all(v["corners"]["curriculum"]["memory_use"]["pass"] for v in seeds.values())
    half = RULES.half_status(ref_label, {s: v["half_reference"] for s, v in seeds.items()})
    return {"flags": {"curriculum_vs_v2": gain_label, "reference_vs_v2": ref_label, "memory_use": mem, "half": half},
            "reading": CRULES.q_reading(gain_label, mem, half)}


def main():
    ap = argparse.ArgumentParser()
    for a in ("--runs", "--mirror", "--out"):
        ap.add_argument(a, type=Path, required=True)
    args = ap.parse_args()
    torch.set_num_threads(4)
    identity = PRE.observer_identity()
    index = json.loads(PRE.INPUTS.read_text())
    bound = PRE.validate_inputs(index)
    launch, p2c = load_p2c_group(args.runs, args.mirror, identity["memsub_source_sha256"])
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "parity").mkdir()
    report = {"observer": identity, "launch": launch, "artifact_eval_seed_base": ARTIFACT_BASE,
              "readings_seed_base": READINGS_BASE, "limits": LIMITS,
              "p2c_cells": {rid: {"cell": rel(c), "run_manifest_sha256": sha(c / "run_manifest.json"),
                                  "trained_parameters_sha256": sha(c / "trained_parameters.safetensors"),
                                  "rows_sha256": sha(c / "per_example_results.jsonl")} for rid, (c, _m) in p2c.items()},
              "parity": PRE.run_parity(index, bound, args.out / "parity")}
    if not report["parity"]["pass"]:
        (args.out / "p2c-readings.json").write_text(json.dumps(report, indent=2))
        raise SystemExit("PARITY FAILED at readings time: no readings")
    report["n"] = {}
    for n in (32, 64):
        per_seed = {}
        for s in (0, 1):
            models = {role: (p2c[t.format(s=s)[4:]] if t.startswith("p2c:") else bound[t.format(s=s)])
                      for role, t in index["corners"][str(n)].items()}
            per_seed[s] = evaluate_seed(n, s, models, args.out)
        report["n"][str(n)] = {"seeds": {str(s): v for s, v in per_seed.items()}, **read_n(per_seed)}
        print(f"N{n}", report["n"][str(n)]["reading"], flush=True)
    report["both_n_support_descriptive"] = all(v["reading"].startswith("SUPPORTS") for v in report["n"].values())
    report["observer_end"] = PRE.finish_identity(identity, index)
    for rid, (c, _m) in p2c.items():
        now = {"run_manifest_sha256": sha(c / "run_manifest.json"),
               "trained_parameters_sha256": sha(c / "trained_parameters.safetensors"),
               "rows_sha256": sha(c / "per_example_results.jsonl")}
        if any(report["p2c_cells"][rid][k] != v for k, v in now.items()):
            raise SystemExit(f"{rid}: P2C evidence changed during readings")
    (args.out / "p2c-readings.json").write_text(json.dumps(report, indent=2, default=str))
    print("READINGS DONE", sha(args.out / "p2c-readings.json"))


if __name__ == "__main__":
    main()
