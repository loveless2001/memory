"""P2.5 Amendment PK §PK5 proof ACCEPTANCE (frozen schema; codex 21556 #3, 21558).

    python scripts/sgm-p2p5-pk-packed-proof-acceptance-compare.py --evidence <dir> --out <acceptance.json>

<evidence>/<scenario>/cells/<cell>/epoch-<m>/... as written by the slot supervisor (fetched from the
volume). Per cell: the AUTHORITATIVE record (highest epoch with an acknowledged record) and its
inheritance walk; the logical-update chain = updates [resume_step_i, resume_step_{i+1}) from each
training epoch's proof capture (eval-only epochs add none); exactly `steps` logical updates.
Scientific scope: per-logical-update loss; gradients by the full expected name list (+ shapes);
final trained tensors; metrics.json fields; per-example rows; telemetry rows. Clocks
(sec_per_step, wall_seconds) are excluded from equivalence but must be finite and >= 0.
N/A (None) must match exactly; missing/extra fields, shape mismatches and NaN/inf FAIL.
Control first: A' vs A bitwise -> every candidate bitwise; else A' must pass the tolerance
|x - x_A| <= max(1e-5 * max|x_A|, 1e-8) with identical rows, else UNSTABLE (proof stops).
Scenario checks: B resume at step 4 in a later epoch; C eval-only epoch with zero physical
updates and partial artifact-eval progress retained; D co-tenant FAILED (worker exit 3) inherited
as FAILED and never relaunched; E alone.
Revision (codex 21567): BEFORE any pairwise check every run is validated on its own — the canonical
chain from immutable predecessor snapshots (acyclic, <= admitted starts), every generation file
present with its bound sha, every epoch admitted (exported admission record), the record identity
== the launch's expected identity, GPU mode: real and distinct container ids per epoch, the shared
per-cell output validation (required outputs, strict JSON, populations, row/key/telemetry counts,
FROZEN name/shape registry), and per-update gradients against the frozen registry (joint omissions
fail). The T timing evidence (18 configs, eval/serialize/commit timings and sizes) gates the whole
proof.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm import packed_slot_epoch_state as es  # noqa: E402

CLOCKS = ("sec_per_step", "wall_seconds")
RTOL, ATOL = 1e-5, 1e-8


class Fail(Exception):
    pass


def authority(cell_dir: Path, admitted: list[int]) -> tuple[int, dict]:
    """Highest ADMITTED epoch with an acknowledged record; an epoch dir that was never
    admitted is a binding failure."""
    epochs = sorted(int(p.name.split("-")[1]) for p in cell_dir.glob("epoch-*"))
    if any(m not in admitted for m in epochs):
        raise Fail(f"{cell_dir.name}: epoch dirs {epochs} not all admitted {admitted}")
    for m in reversed(epochs):
        rec = es.read_record(cell_dir, m)
        if rec is not None:
            return m, rec
    raise Fail(f"{cell_dir.name}: no acknowledged record")


def bound_walk(cell_dir: Path, rec: dict, admitted: list[int], expected: dict | None, gpu: bool) -> list[dict]:
    """Canonical chain (snapshots), identity, admission, provenance and generation bindings."""
    try:
        walk = es.canonical_walk(rec, max_len=len(admitted))
    except ValueError as e:
        raise Fail(f"{cell_dir.name}: {e}")
    for r in walk:
        if r["epoch"] not in admitted:
            raise Fail(f"{cell_dir.name}: epoch {r['epoch']} in the chain was not admitted")
        if expected is not None and (r["identity"].get("runner_expected") != expected
                                     or {k: r["identity"].get(k) for k in expected} != expected):
            raise Fail(f"{cell_dir.name}: epoch {r['epoch']} identity differs from the launch identity")
    if gpu:
        ids = [(r.get("provenance") or {}).get("container_id") for r in walk]
        if any(not (isinstance(i, str) and i) for i in ids) or len(set(ids)) != len(ids):
            raise Fail(f"{cell_dir.name}: container ids {ids} not real and distinct per epoch")
    problem = es.verify_chain(cell_dir, rec["chain"])
    if problem:
        raise Fail(f"{cell_dir.name}: {problem}")
    for prev, r in zip(walk, walk[1:]):                 # each resume starts at the inherited chain end
        inherited = prev["chain"][-1]["step"] if prev["chain"] else 0
        if r["physical"]["resume_step"] != inherited:
            raise Fail(f"{cell_dir.name}: epoch {r['epoch']} resume step {r['physical']['resume_step']} != {inherited}")
    return walk


def logical_chain(cell_dir: Path, walk: list[dict], steps: int, grad_reg: dict) -> list[dict]:
    starts = [r["physical"]["resume_step"] for r in walk] + [steps]
    chain = []
    for r, lo, hi in zip(walk, starts, starts[1:]):
        cap = es.epoch_dir(cell_dir, r["epoch"]) / "attempt-1" / "proof-capture"
        for u in range(lo, hi):
            f = cap / f"u{u:05d}.pt"
            if not f.exists():
                raise Fail(f"{cell_dir.name}: logical update {u} missing in epoch {r['epoch']}")
            d = torch.load(f, map_location="cpu", weights_only=False)
            got = {n: list(g.shape) for n, g in d["grads"].items()}
            if got != grad_reg:                          # frozen registry: joint omissions fail
                raise Fail(f"{cell_dir.name}: u{u} gradient names/shapes differ from the frozen registry")
            chain.append(d)
    if [c["update"] for c in chain] != list(range(steps)):
        raise Fail(f"{cell_dir.name}: logical updates {[c['update'] for c in chain]} != 0..{steps - 1}")
    return chain


def load_cell(scen_dir: Path, cell: str, pilot: dict, grid: dict, registry: dict, admitted: list[int],
              expected: dict | None, gpu: bool) -> dict:
    from safetensors.torch import load_file
    from memsub.sgm.packed_slot_cell_output_validation import validate_cell_outputs
    cdir = scen_dir / "cells" / cell
    m, rec = authority(cdir, admitted)
    walk = bound_walk(cdir, rec, admitted, expected, gpu)
    out = {"epoch": m, "record": rec, "walk": walk}
    if rec["state"] != es.COMPLETE:
        return out
    reg = registry["by_arm"][pilot["arm"]]
    att = scen_dir / rec["outputs"]["attempt"]
    o = att / "out"
    memsub = (expected or rec["identity"])["memsub"]
    problem = validate_cell_outputs(o, rec["outputs"]["files"], pilot, grid["eval"], memsub, reg)
    if problem:
        raise Fail(f"{cell}: output validation: {problem}")
    out.update(chain=logical_chain(cdir, walk, pilot["steps"], reg["grad_names_shapes"]),
               weights=load_file(str(o / "trained_parameters.safetensors")),
               metrics=json.loads((o / "metrics.json").read_text()),
               rows=[json.loads(x) for x in (o / "per_example_results.jsonl").read_text().splitlines()],
               telemetry=[json.loads(x) for x in (o / "routing_telemetry.jsonl").read_text().splitlines()])
    return out


def validate_timing(tdir: Path, spec: dict) -> dict:
    """T gate: complete status, all 18 configs ok in order, finite positive eval/serialize/commit
    timings and byte sizes for every rank/seed, child exit 0 with 3 commit probes."""
    try:
        t = json.loads((tdir / "timing" / "timing.json").read_text())
        ex = json.loads((tdir / "timing.exit.json").read_text())
    except (OSError, ValueError) as e:
        raise Fail(f"timing evidence missing: {e!r:.120}")
    want = [(a, n, p) for a, n in spec["slot_types"] for p in sorted(int(x) for x in spec["phases"])]
    got = [(c.get("arm"), c.get("n"), c.get("phase")) for c in t.get("configs", [])]
    if t.get("status") != "complete" or [tuple(x) for x in got] != [(a, n, p) for a, n, p in want]:
        raise Fail(f"timing incomplete: status {t.get('status')}, {len(got)}/{len(want)} configs")
    pos = lambda v: isinstance(v, (int, float)) and math.isfinite(v) and v > 0       # noqa: E731
    for c in t["configs"]:
        if c.get("status") != "ok" or not pos(c.get("fixed_work_updates_per_s")):
            raise Fail(f"timing {c.get('arm')} N{c.get('n')} P{c.get('phase')}: not ok")
        if sorted(w["seed"] for w in c["workers"]) != list(spec["seeds"]):
            raise Fail(f"timing {c['arm']} N{c['n']} P{c['phase']}: seeds differ")
        for w in c["eval_and_checkpoint"]:
            if not all(pos(w.get(k)) for k in ("dev_eval_batch_s", "artifact_eval_batch_s",
                                               "checkpoint_serialize_s", "checkpoint_bytes", "checkpoint_optimizer_states")):
                raise Fail(f"timing {c['arm']} N{c['n']} P{c['phase']}: eval/checkpoint fields not finite positive")
    if ex.get("child_exit") != 0 or len(ex.get("commit_s", [])) != 3 or not all(pos(x) for x in ex["commit_s"]):
        raise Fail("timing child exit / commit probes invalid")
    return {"configs": len(t["configs"]), "commit_s": ex["commit_s"]}


def check_clocks(x, where: str) -> None:
    if isinstance(x, dict):
        for k, v in x.items():
            if k in CLOCKS:
                if not (isinstance(v, (int, float)) and math.isfinite(v) and v >= 0):
                    raise Fail(f"{where}.{k}: clock not finite/non-negative")
            else:
                check_clocks(v, f"{where}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            check_clocks(v, f"{where}[{i}]")


class Cmp:
    def __init__(self, bitwise: bool):
        self.bitwise, self.max_rel, self.all_equal = bitwise, 0.0, True

    def tensor(self, a: torch.Tensor, b: torch.Tensor, where: str) -> None:
        if a.shape != b.shape or a.dtype != b.dtype:
            raise Fail(f"{where}: shape/dtype {tuple(a.shape)}/{a.dtype} vs {tuple(b.shape)}/{b.dtype}")
        a64, b64 = a.double(), b.double()
        if not (torch.isfinite(a64).all() and torch.isfinite(b64).all()):
            raise Fail(f"{where}: non-finite")
        if torch.equal(a64, b64):
            return
        self.all_equal = False
        d = float((a64 - b64).abs().max())
        scale = float(a64.abs().max()) if a64.numel() else 0.0
        self.max_rel = max(self.max_rel, d / scale if scale else float("inf"))
        if self.bitwise or d > max(RTOL * scale, ATOL):
            raise Fail(f"{where}: differs (max abs {d:.3g}, bitwise required: {self.bitwise})")

    def value(self, a, b, where: str) -> None:
        if isinstance(a, dict) or isinstance(b, dict):
            if not (isinstance(a, dict) and isinstance(b, dict)):
                raise Fail(f"{where}: type differs")
            ka, kb = set(a) - set(CLOCKS), set(b) - set(CLOCKS)
            if ka != kb:
                raise Fail(f"{where}: fields differ {sorted(ka ^ kb)}")
            for k in sorted(ka):
                self.value(a[k], b[k], f"{where}.{k}")
        elif isinstance(a, list) or isinstance(b, list):
            if not (isinstance(a, list) and isinstance(b, list)) or len(a) != len(b):
                raise Fail(f"{where}: list length/type differs")
            for i, (x, y) in enumerate(zip(a, b)):
                self.value(x, y, f"{where}[{i}]")
        elif a is None or b is None or isinstance(a, (str, bool)) or isinstance(b, (str, bool)):
            if a != b or type(a) is not type(b):
                raise Fail(f"{where}: {a!r} != {b!r}")
        elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if not (math.isfinite(a) and math.isfinite(b)):
                raise Fail(f"{where}: non-finite")
            if a != b:
                self.all_equal = False
                if self.bitwise or abs(a - b) > max(RTOL * abs(a), ATOL):
                    raise Fail(f"{where}: {a} != {b}")
        else:
            raise Fail(f"{where}: unsupported type {type(a).__name__}")


def compare(ref: dict, cand: dict, bitwise: bool, cell: str) -> dict:
    c = Cmp(bitwise)
    names = sorted(ref["chain"][0]["grads"])
    if not names or any(not (n.startswith("adapters.") or n.startswith("head.")) for n in names):
        raise Fail(f"{cell}: unexpected gradient names (backbone must never appear)")
    for u, (ra, cb) in enumerate(zip(ref["chain"], cand["chain"])):
        c.tensor(ra["loss"], cb["loss"], f"{cell}.loss[u{u}]")
        if sorted(ra["grads"]) != names or sorted(cb["grads"]) != names:
            raise Fail(f"{cell}: u{u} gradient name set differs from the expected list")
        for n in names:
            c.tensor(ra["grads"][n], cb["grads"][n], f"{cell}.grad[u{u}].{n}")
    if sorted(ref["weights"]) != sorted(cand["weights"]):
        raise Fail(f"{cell}: final weight names differ")
    for n in sorted(ref["weights"]):
        c.tensor(ref["weights"][n], cand["weights"][n], f"{cell}.final.{n}")
    for side in (ref, cand):
        check_clocks(side["metrics"], f"{cell}.metrics")
        check_clocks(side["telemetry"], f"{cell}.telemetry")
    c.value(ref["metrics"], cand["metrics"], f"{cell}.metrics")
    c.value(ref["telemetry"], cand["telemetry"], f"{cell}.telemetry")
    if ref["rows"] != cand["rows"]:
        raise Fail(f"{cell}: per-example rows differ")
    return {"bitwise": c.all_equal, "max_rel": c.max_rel}


def evaluate(evidence: Path, grid: dict, registry: dict, admission: dict, expected: dict | None,
             gpu: bool, require_timing: bool = True) -> dict:
    from memsub.sgm.packed_slot_supervisor import expand_cells
    scen, pilots = grid["scenarios"], expand_cells(grid)
    rep = {"scenarios": {}, "pass": False}
    try:
        if not isinstance(registry.get("by_arm"), dict):
            raise Fail("registry malformed")
        cells = {}
        for s, spec in scen.items():
            admitted = sorted(int(k.rsplit("-", 1)[1]) for k in admission if k.startswith(f"{s}-start-"))
            if not admitted:
                raise Fail(f"{s}: no admitted start recorded")
            cells[s] = {c: load_cell(evidence / s, c, pilots[c], grid, registry, admitted, expected, gpu)
                        for c in spec["cells"]}
        for s, cs in cells.items():
            for c, d in cs.items():
                if not (s == "D" and c in (scen["D"]["faults"]["worker_exit"])) and d["record"]["state"] != es.COMPLETE:
                    raise Fail(f"{s}/{c}: state {d['record']['state']}")
        ctrl = {}
        for c in scen["A"]["cells"]:                    # control first
            try:
                ctrl[c] = compare(cells["A"][c], cells["Aprime"][c], True, f"Aprime/{c}")
            except Fail:
                try:
                    ctrl[c] = compare(cells["A"][c], cells["Aprime"][c], False, f"Aprime/{c}")
                except Fail as e:
                    raise Fail(f"control UNSTABLE (A' fails the tolerance rule): {e}")
        bitwise = all(v["bitwise"] for v in ctrl.values())
        rep["control"] = {"mode": "bitwise" if bitwise else "tolerance", "cells": ctrl}
        for s in ("B", "C", "D", "E"):
            out = {}
            for c, d in cells[s].items():
                if s == "D" and c in scen["D"]["faults"]["worker_exit"]:
                    out[c] = _check_failed_persistence(evidence / s / "cells" / c, d)
                    continue
                out[c] = compare(cells["A"][c], d, bitwise, f"{s}/{c}")
            out.update(_scenario_checks(s, cells[s], scen[s], evidence))
            rep["scenarios"][s] = out
        if require_timing:
            rep["timing"] = validate_timing(evidence, grid["timing"])
        rep["pass"] = True
    except Fail as e:
        rep["failure"] = str(e)
    return rep


def _check_failed_persistence(cell_dir: Path, d: dict) -> dict:
    recs = d["walk"]
    if d["record"]["state"] != es.FAILED or "worker exit 3" not in d["record"].get("reason", ""):
        raise Fail(f"D/{cell_dir.name}: expected FAILED (worker exit 3), got {d['record']['state']}")
    if len(recs) < 2 or recs[0]["state"] != es.FAILED:
        raise Fail(f"D/{cell_dir.name}: FAILED was not acknowledged before the restart")
    for r in recs[1:]:
        if (es.epoch_dir(cell_dir, r["epoch"]) / "attempt-1").exists():
            raise Fail(f"D/{cell_dir.name}: relaunched in epoch {r['epoch']}")
    return {"failed_persisted_epochs": [r["epoch"] for r in recs]}


def _scenario_checks(s: str, cs: dict, spec: dict, evidence: Path) -> dict:
    if s == "B":
        c = spec["faults"]["after_ack"]["cell"]
        last = cs[c]["walk"][-1]
        if len(cs[c]["walk"]) < 2 or last["physical"]["resume_step"] != spec["faults"]["after_ack"]["step"]:
            raise Fail(f"B/{c}: not resumed from the step-{spec['faults']['after_ack']['step']} generation")
        return {"resumed_from": last["physical"]["resume_step"], "epochs": [r["epoch"] for r in cs[c]["walk"]]}
    if s == "C":
        c = spec["faults"]["during_eval"]["cell"]
        last = cs[c]["walk"][-1]
        if last["recovery"] != "eval_only" or last["physical"]["observed_updates"] != 0:
            raise Fail(f"C/{c}: eval-only recovery with zero updates not shown")
        first = cs[c]["walk"][0]
        prog = es.epoch_dir(evidence / "C" / "cells" / c, first["epoch"]) / "attempt-1" / "artifact-eval-progress.jsonl"
        rows = [json.loads(x) for x in prog.read_text().splitlines()] if prog.exists() else []
        if not rows or (es.epoch_dir(evidence / "C" / "cells" / c, first["epoch"]) / "attempt-1" / "done.json").exists():
            raise Fail(f"C/{c}: no retained partial artifact-eval work inside the interrupted attempt")
        return {"eval_only_epoch": last["epoch"], "interrupted_artifact_units": len(rows)}
    if s == "D":
        c = spec["faults"]["after_ack"]["cell"]
        if len(cs[c]["walk"]) < 2:
            raise Fail(f"D/{c}: no restart observed")
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--grid", type=Path, default=ROOT / "configs/m4_sgm_p2p5_packed_proof_grid.json")
    ap.add_argument("--registry", type=Path, default=ROOT / "configs/m4_sgm_p2p5_packed_proof_registry.json")
    ap.add_argument("--admission", type=Path, required=True, help="exported admission Dict (JSON)")
    ap.add_argument("--provenance", type=Path, required=True, help="launch_provenance.json (expected identity)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    grid, registry = json.loads(a.grid.read_text()), json.loads(a.registry.read_text())
    import hashlib
    if registry["grid_sha256"] != hashlib.sha256(a.grid.read_bytes()).hexdigest():
        raise SystemExit("registry was frozen for a different grid")
    rep = evaluate(a.evidence, grid, registry, json.loads(a.admission.read_text()),
                   json.loads(a.provenance.read_text())["expected_identity"], gpu=True)
    rep["comparator_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.out.write_text(json.dumps(rep, indent=2, default=str))
    print("PASS" if rep["pass"] else f"FAIL: {rep.get('failure')}")
    sys.exit(0 if rep["pass"] else 1)


if __name__ == "__main__":
    main()
