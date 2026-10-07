"""P2.5 registered readings for the packed campaign (prereg v0.2 `3bf8737`; Amendment PK). Run EXACTLY ONCE.

    python scripts/sgm-p2p5-pk-campaign-readings.py --evidence-root <m4-sgm/p2p5-qwen3-0p6b-screen-v1> \
        --admitted <admitted.json> --expected <expected_identity.json> --out <new dir>

Order (prereg "Order inside the one readings run"; fail closed, write-once output):
  1. BIND all 18 registered cells from the evidence root: authoritative record (admitted epochs, canonical
     snapshot chain), state COMPLETE and the shared per-cell output validation with the frozen campaign
     registry/schema. Any failure -> "unavailable: <reason>" at every N; the reserved population is NOT touched.
  2. PARITY: for every cell, the first artifact batch (intervention none, 9_300_011+s) is re-evaluated on this
     host and must be byte-equal to the cell's own rows; failure -> unavailable, reserved population untouched.
  3. ORACLE INTERFACE: oracle N32 s0/s1 on the reserved N32 population, then the SAME checkpoints on the N16
     population (transfer diagnostic); interface_ok per N (>= 0.50 both seeds).
  4. Only for an N whose interface passed: learned / single_cell / random_fixed (none, bank_derange, read_offset)
     and memory_off (none) on that N's reserved population 9_600_011+s; an N whose interface failed keeps its
     other reserved corners unevaluated.
  5. Per N: control labels (all-control conjunction), memory use (learned, both seeds), read-address use,
     the ordered reading table (sgm-p2p5-decision-rules.py). Descriptive: accuracies, 16-head gate telemetry.
"""

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm import packed_slot_epoch_state as es  # noqa: E402
from memsub.sgm.packed_slot_cell_output_validation import validate_cell_outputs  # noqa: E402
from memsub.sgm.packed_slot_supervisor import expand_cells  # noqa: E402
from memsub.sgm.synthetic_pilot_evaluation import evaluate  # noqa: E402
from memsub.sgm.synthetic_pilot_run import source_tree_sha256  # noqa: E402

GRID = ROOT / "configs/m4_sgm_p2p5_grid.json"
REGISTRY, SCHEMA = ROOT / "configs/m4_sgm_p2p5_campaign_registry.json", ROOT / "configs/m4_sgm_p2p5_campaign_output_schema.json"
EVAL = {"final_batches": 16, "final_batch_size": 16, "final_seed_base": 9_300_011, "dev_seed": 4242,
        "train_eval_seed_base": 555_001}
READINGS_BASE = 9_600_011


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


POBS, DR = _load("sgm-p2p5-pretrained-observer"), _load("sgm-p2p5-decision-rules")
P2D = POBS.RULES.P2D


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def slot_of(pilot: dict) -> str:
    return f"{pilot['arm']}-n{pilot['n_bindings']}"


def bind_cells(root: Path, admitted: dict, memsub: str, grid: dict, registry: dict, schema: dict) -> tuple[dict, str | None]:
    """{cell: out_dir} for all 18 registered cells, or (partial, first problem)."""
    cells, problem = {}, None
    for cid, pilot in sorted(expand_cells(grid).items()):
        cdir, adm = root / slot_of(pilot) / "cells" / cid, admitted.get(slot_of(pilot), [])
        try:
            epochs = sorted(int(p.name.split("-")[1]) for p in cdir.glob("epoch-*"))
            if not epochs or any(m not in adm for m in epochs):
                raise ValueError(f"epochs {epochs} not all admitted {adm}")
            rec = next(r for m in reversed(epochs) if (r := es.read_record(cdir, m)) is not None)
            es.canonical_walk(rec, max_len=len(adm))
            if rec["state"] != es.COMPLETE:
                raise ValueError(f"state {rec['state']}")
            out = root / slot_of(pilot) / rec["outputs"]["attempt"] / "out"
            bad = validate_cell_outputs(out, rec["outputs"]["files"], pilot, EVAL, memsub,
                                        registry["by_arm"][pilot["arm"]], schema["by_arm"][pilot["arm"]])
            if bad:
                raise ValueError(bad)
            cells[cid] = out
        except (StopIteration, ValueError, KeyError, OSError) as e:
            problem = problem or f"{cid}: {str(e)[:200] or type(e).__name__}"
    return cells, problem


def parity(cells: dict, pilots: dict) -> str | None:
    """First artifact batch (none) re-evaluated here must be byte-equal to each cell's own rows."""
    for cid, out in sorted(cells.items()):
        pilot = pilots[cid]
        pcfg, backend, head = POBS.load_checkpoint(pilot, out / "trained_parameters.safetensors")
        rows: list = []
        evaluate(backend, head, pcfg.task_spec(), pcfg.arm, pcfg.readout, split="heldout", batches=1,
                 batch_size=EVAL["final_batch_size"], seed=EVAL["final_seed_base"] + pilot["seed"], intervention="none",
                 per_example=rows, filler_writes=pcfg.filler_writes)
        own = [json.loads(x) for x in (out / "per_example_results.jsonl").read_text().splitlines()]
        own = [r for r in own if r["intervention"] == "none" and r["batch"] == 0]
        if POBS.rows_text(rows) != POBS.rows_text(own):
            return f"parity: {cid} first artifact batch differs on this host"
    return None


def reserved_rows(cid: str, out: Path, pilot: dict, n: int, ivs: tuple, dest: Path) -> tuple[list, dict]:
    pcfg, backend, head = POBS.load_checkpoint({**pilot, "n_bindings": n}, out / "trained_parameters.safetensors")
    rows = POBS.eval_rows(backend, head, pcfg, READINGS_BASE + pilot["seed"], ivs, pcfg.filler_writes)
    path = dest / f"rows-{cid}-on-n{n}.jsonl"
    path.write_text(POBS.rows_text(rows))
    return rows, {"rows_sha256": sha(path), "accuracy_none": sum(P2D.episode_scores(rows, "none").values()) / P2D.N_EPISODES,
                  "gate_telemetry_descriptive": POBS.gate_telemetry(backend, pcfg)}


def current_identity() -> dict:
    return {"memsub": source_tree_sha256(ROOT / "memsub"), "grid": sha(GRID), "registry": sha(REGISTRY),
            "schema": sha(SCHEMA), "script": sha(Path(__file__))}


def readings(root: Path, admitted: dict, expected: dict, out: Path) -> dict:
    grid, registry, schema = (json.loads(p.read_text()) for p in (GRID, REGISTRY, SCHEMA))
    pilots = expand_cells(grid)
    identity = current_identity()
    out.mkdir(parents=True, exist_ok=False)                   # exactly once
    report = {"identity": identity, "readings_seed_base": READINGS_BASE, "n": {}}
    mismatch = [k for k in expected if identity.get(k) != expected[k]]
    cells, problem = ({}, f"identity differs: {mismatch}") if mismatch else bind_cells(root, admitted, identity["memsub"],
                                                                                       grid, registry, schema)
    problem = problem or parity(cells, pilots)
    if problem:                                               # reserved population untouched
        report["n"] = {str(n): {"reading": DR.screen_reading(n, problem, None, None, None)} for n in (16, 32)}
        report["unavailable"] = problem
    else:
        oracle = {s: f"oracle-n32-s{s}" for s in (0, 1)}
        for n in (32, 16):                                    # oracle interface first (N16 = transfer diagnostic)
            res = {"corners": {}}
            acc = {}
            for s, cid in oracle.items():
                _r, info = reserved_rows(cid, cells[cid], pilots[cid], n, ("none",), out)
                res["corners"][f"{cid}-on-n{n}"], acc[s] = info, float(info["accuracy_none"])
            res["interface"] = DR.interface_ok(acc)
            if res["interface"]:
                rows = {}
                for arm in ("learned", "single_cell", "random_fixed", "memory_off"):
                    for s in (0, 1):
                        cid = next(c for c, p in pilots.items() if (p["arm"], p["n_bindings"], p["seed"]) == (arm, n, s))
                        ivs = ("none",) if arm == "memory_off" else POBS.FINAL_IVS
                        rows[(arm, s)], res["corners"][cid] = reserved_rows(cid, cells[cid], pilots[cid], n, ivs, out)
                per_control = {c: {s: P2D.paired(rows[("learned", s)], rows[(c, s)]) for s in (0, 1)} for c in DR.CONTROLS}
                labels = DR.control_labels(per_control)
                mem = all(P2D.memory_use(rows[("learned", s)])["pass"] for s in (0, 1))
                res.update(per_control=per_control, labels=labels, memory_use=mem,
                           read_address=DR.read_address_use({s: P2D.paired(rows[("learned", s)], rows[("learned", s)],
                                                                           "none", "read_offset") for s in (0, 1)}),
                           reading=DR.screen_reading(n, None, True, labels, mem))
            else:
                res["reading"] = DR.screen_reading(n, None, False, None, None)
            report["n"][str(n)] = res
    if current_identity() != identity:
        raise SystemExit("sources changed during readings")
    (out / "readings.json").write_text(json.dumps(report, indent=2, default=str))
    return report


def main():
    ap = argparse.ArgumentParser()
    for a in ("--evidence-root", "--admitted", "--expected", "--out"):
        ap.add_argument(a, type=Path, required=True)
    a = ap.parse_args()
    torch.set_num_threads(4)
    rep = readings(a.evidence_root, json.loads(a.admitted.read_text()), json.loads(a.expected.read_text()), a.out)
    print(json.dumps({n: v["reading"] for n, v in rep["n"].items()}))


if __name__ == "__main__":
    main()
