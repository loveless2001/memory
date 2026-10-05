"""P2C CPU preflights (prereg v0.2 `0c8d358` § Gates 1). No registered cell,
no reserved-seed (9_500_011) evaluation.

    .venv/bin/python scripts/sgm-p2c-preflight.py --out plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/preflight

The cleared P2G preflight functions (identity binding, inputs validation,
parity, end-of-run identity check) are generic over that module's constants
INPUTS / GRID / RUNNER / ANALYSIS_FILES. P2C loads a PRIVATE instance of it and
binds the P2C constants on that instance only, so the closed P2G scripts stay
byte-identical and are reused, not copied.

1. Inputs: reused checkpoints + complete five-intervention parity references
   hash/manifest-bound via configs/m4_sgm_p2c_inputs.json.
2. Parity (STOP on failure), 9_300_011+s, parsed AND byte equal: P-on v2
   N32/N64 E=on; P-off P2D filleroff N16 and P2G filleroff N32 E=off.
3. Schedule smoke (tiny N=4, 4 updates, schedule ((0,0),(2,40))): training
   episodes follow the schedule; every dev/artifact eval stays at filler 40.
"""

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _private_p2g_preflight():
    spec = importlib.util.spec_from_file_location("p2g_preflight_for_p2c", ROOT / "scripts" / "sgm-p2g-preflight.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.INPUTS = ROOT / "configs" / "m4_sgm_p2c_inputs.json"
    mod.GRID = ROOT / "configs" / "m4_sgm_p2c_grid.json"
    mod.RUNNER = ROOT / "modal-runners" / "modal-m4-sgm-p2c-nonpreemptible-spawn.py"
    mod.ANALYSIS_FILES = mod.ANALYSIS_FILES + tuple(f"scripts/{f}" for f in (
        "sgm-p2c-preflight.py", "sgm-p2c-readings.py", "sgm-p2c-decision-rules.py")) + (
        "modal-runners/modal-m4-sgm-p2c-nonpreemptible-spawn.py",)
    return mod


PRE = _private_p2g_preflight()
INPUTS, GRID = PRE.INPUTS, PRE.GRID


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def schedule_smoke(out: Path) -> dict:
    """Tiny end-to-end run_pilot with a scheduled filler length; records the
    filler length of every training batch and every evaluation batch."""
    import memsub.sgm.synthetic_pilot as sp
    import memsub.sgm.synthetic_pilot_evaluation as ev
    from memsub.sgm.synthetic_pilot_run import run_pilot
    seen = {"train": [], "eval": []}
    real_train, real_eval = sp.sample_batch, ev.sample_batch

    def train_spy(spec, split, batch, gen):
        seen["train"].append(spec.filler_len)
        return real_train(spec, split, batch, gen)

    def eval_spy(spec, split, batch, gen):
        seen["eval"].append(spec.filler_len)
        return real_eval(spec, split, batch, gen)
    pcfg = sp.PilotConfig(n_bindings=4, steps=4, eval_every=2, eval_batches=1,
                          filler_len_schedule=((0, 0), (2, 40)))
    sp.sample_batch, ev.sample_batch = train_spy, eval_spy
    try:
        metrics = run_pilot(pcfg, out / "schedule-smoke", final_batches=1, final_batch_size=16,
                            final_seed_base=4242)                  # dev population, never a registered one
    finally:
        sp.sample_batch, ev.sample_batch = real_train, real_eval
    ok = seen["train"] == [0, 0, 40, 40] and set(seen["eval"]) == {40}
    return {"train_filler_lens": seen["train"], "eval_filler_lens": sorted(set(seen["eval"])),
            "result_label": metrics["result_label"], "pass": ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    torch.set_num_threads(4)
    identity = PRE.observer_identity()
    index = json.loads(INPUTS.read_text())
    bound = PRE.validate_inputs(index)
    args.out.mkdir(parents=True, exist_ok=False)
    report = {"observer": identity, "inputs_validated": sorted(bound)}
    report["parity"] = PRE.run_parity(index, bound, args.out)
    if not report["parity"]["pass"]:
        (args.out / "preflight.json").write_text(json.dumps(report, indent=2))
        raise SystemExit("PARITY FAILED: stop; no reserved-seed use of the common observer")
    with tempfile.TemporaryDirectory() as tmp:
        report["schedule_smoke"] = schedule_smoke(Path(tmp))
    if not report["schedule_smoke"]["pass"]:
        (args.out / "preflight.json").write_text(json.dumps(report, indent=2))
        raise SystemExit("SCHEDULE SMOKE FAILED")
    report["observer_end"] = PRE.finish_identity(identity, index)
    (args.out / "preflight.json").write_text(json.dumps(report, indent=2))
    print("PREFLIGHT PASS", sha(args.out / "preflight.json"))


if __name__ == "__main__":
    main()
