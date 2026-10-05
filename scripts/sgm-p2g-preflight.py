"""P2G CPU preflights (prereg v0.2 § Gates 1 / § Runtime). No training, no
fresh-seed (9_400_011) evaluation.

    .venv/bin/python scripts/sgm-p2g-preflight.py --out plans/261006-0010-m4-sgm-p2g-selective-write-gate/preflight

1. Inputs: every reused checkpoint and parity reference in
   configs/m4_sgm_p2g_inputs.json is hash- and manifest-bound before use.
2. Parity (STOP on failure): the common observer (P2G memsub) re-evaluates the
   complete legacy files — P-on: v2 N16/N32 E=on vs the committed Step 2
   frozen-observer baselines; P-off: P2D filleroff N16 E=off vs those cells'
   Modal rows — at 9_300_011+s; parsed AND byte equality required.
3. Step-0 gate telemetry (descriptive): untrained gateclosed builds and the
   default v2-recipe builds, dev 4242, E=on.
"""

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.synthetic_pilot import PilotConfig, build  # noqa: E402
from memsub.sgm.synthetic_pilot_run import source_tree_sha256  # noqa: E402

INPUTS = ROOT / "configs" / "m4_sgm_p2g_inputs.json"
GRID = ROOT / "configs" / "m4_sgm_p2g_grid.json"
RUNNER = ROOT / "modal-runners" / "modal-m4-sgm-p2g-nonpreemptible-spawn.py"
ANALYSIS_FILES = ("sgm-p2g-preflight.py", "sgm-p2g-readings.py", "sgm-p2g-decision-rules.py",
                  "sgm-p2g-common-observer-evaluation.py", "sgm-p2d-step2-decision-rules.py")


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OBS = load_script("sgm-p2g-common-observer-evaluation")


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def p2g_source_sha() -> str:
    """The P2G memsub identity the runner binds (parsed, not imported: no Modal)."""
    for line in RUNNER.read_text().splitlines():
        if line.startswith("SOURCE_SHA = "):
            return line.split('"')[1]
    raise SystemExit("runner SOURCE_SHA not found")


def observer_identity() -> dict:
    """Observer snapshot: executed memsub tree, analysis code, inputs, HEAD."""
    src = source_tree_sha256(ROOT / "memsub")
    if src != p2g_source_sha():
        raise SystemExit(f"memsub source {src[:8]} != P2G runner SOURCE_SHA")
    return {"memsub_source_sha256": src, "inputs_index_sha256": sha(INPUTS), "grid_sha256": sha(GRID),
            "analysis_sha256": {f: sha(ROOT / "scripts" / f) for f in ANALYSIS_FILES},
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                       text=True, cwd=ROOT).stdout.strip()}


def validate_inputs(index: dict) -> dict:
    """Bind every reused checkpoint (manifest/params/source/group/config) and
    parity reference to the committed index; returns {key: (cell, manifest)}."""
    if index["new_group"]["grid_sha256"] != sha(GRID):
        raise SystemExit("inputs index does not bind the committed P2G grid")
    bound = {}
    for key, ref in index["reused"].items():
        cell = ROOT / ref["cell"]
        man = json.loads((cell / "run_manifest.json").read_text())
        checks = {"run_manifest_sha256": sha(cell / "run_manifest.json") == ref["run_manifest_sha256"],
                  "params_file": sha(cell / "trained_parameters.safetensors") == ref["trained_parameters_sha256"],
                  "params_manifest": man["trained_parameters_sha256"] == ref["trained_parameters_sha256"],
                  "git_head": man["git_head"] == ref["git_head"],
                  "source": man["memsub_source_sha256"] == ref["memsub_source_sha256"],
                  "pilot_config": man["pilot_config"] == ref["pilot_config"],
                  "group": man.get("modal_group") == ref["group"]}
        if not all(checks.values()):
            raise SystemExit(f"reused {key}: identity mismatch {[k for k, ok in checks.items() if not ok]}")
        bound[key] = (cell, man)
    for kind, entries in index["parity"].items():
        for e in entries:
            if sha(ROOT / e["reference"]) != e["reference_sha256"]:
                raise SystemExit(f"{kind} {e['checkpoint']}: reference file hash mismatch")
    return bound


def run_parity(index: dict, bound: dict, out: Path) -> dict:
    """P-on / P-off; writes produced rows; every check must pass."""
    results = {}
    for kind, entries in index["parity"].items():
        for e in entries:
            cell, man = bound[e["checkpoint"]]
            pcfg, backend, head = OBS.load_checkpoint(man["pilot_config"], cell / "trained_parameters.safetensors")
            print(kind, e["checkpoint"], "evaluating", flush=True)
            rows = OBS.eval_rows(backend, head, pcfg, e["seed"], tuple(e["interventions"]), e["filler_writes"])
            text = OBS.rows_text(rows)
            path = out / f"parity-{kind}-{e['checkpoint']}-rows.jsonl"
            path.write_text(text)
            ref_text = (ROOT / e["reference"]).read_text()
            ref_rows = [json.loads(l) for l in ref_text.splitlines()]
            results[f"{kind}:{e['checkpoint']}"] = {
                "rows": len(rows), "reference_rows": len(ref_rows), "produced_sha256": sha(path),
                "reference_sha256": e["reference_sha256"], "parsed_equal": rows == ref_rows,
                "byte_equal": text == ref_text}
    results["pass"] = all(v["parsed_equal"] and v["byte_equal"] for v in results.values())
    return results


def step0_telemetry(grid: dict) -> dict:
    """Untrained gate builds vs default builds (descriptive; no training)."""
    runner_expand = load_runner_expand()
    out = {}
    for run_id, tag, pilot in runner_expand(grid):
        if tag != "gateclosed":
            continue
        for label, cfg in (("gateclosed", pilot), ("default_v2_recipe", {**pilot, "beta_bias_init": None})):
            pcfg = PilotConfig(**cfg)
            _rt, backend, _head = build(pcfg)
            summary = OBS.gate_summary(OBS.gate_events(backend, pcfg, True), pcfg.n_bindings)
            out[f"{label}-n{pcfg.n_bindings}-s{pcfg.seed}"] = summary
    return out


def load_runner_expand():
    v1 = ROOT / "modal-runners" / "modal-m4-sgm-p2d-diagnostics-grid.py"
    spec = importlib.util.spec_from_file_location("p2d_v1_runner", v1)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.expand


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    torch.set_num_threads(4)
    identity = observer_identity()
    index = json.loads(INPUTS.read_text())
    bound = validate_inputs(index)
    args.out.mkdir(parents=True, exist_ok=False)
    report = {"observer": identity, "inputs_validated": sorted(bound)}
    report["parity"] = run_parity(index, bound, args.out)
    if not report["parity"]["pass"]:
        (args.out / "preflight.json").write_text(json.dumps(report, indent=2))
        raise SystemExit("PARITY FAILED: stop; no fresh-seed use of the common observer")
    report["step0_gate_telemetry"] = step0_telemetry(json.loads(GRID.read_text()))
    if observer_identity()["memsub_source_sha256"] != identity["memsub_source_sha256"]:
        raise SystemExit("memsub changed during preflight")
    (args.out / "preflight.json").write_text(json.dumps(report, indent=2))
    print("PREFLIGHT PASS", sha(args.out / "preflight.json"))


if __name__ == "__main__":
    main()
