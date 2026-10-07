"""P2.5 PK campaign: POST-HOC validation amendment for exactly ONE FAILED cell (user 21710 chose option B; scope
claude 21702, codex 21701/21703/21712). Analysis layer only: memsub, including the frozen validator, is unchanged.

The original record stays FAILED and its bytes are never written; the original prereg outcome (readings
"unavailable" at every N) is kept next to every amended reading. The cell named by the frozen spec
(configs/m4_sgm_p2p5_pk_posthoc_validation_amendment.json) is accepted ONLY if ALL of these hold:
  1. its acknowledged record is FAILED with the exact original reason, and the record bytes, done.json, the seven
     outputs and the terminal checkpoint match the spec's sha256 values;
  2. the ORIGINAL validator with the frozen schema returns exactly the original schema failure;
  3. the ORIGINAL validator without the schema stage returns valid (files, strict JSON, manifests, populations, row
     coverage, metrics, telemetry counts/steps, tensor registry + finiteness, clock);
  4. the null `grad_norm` leaves of the training telemetry are EXACTLY the spec's (step, key) list. `grad_norm` is the
     only field memsub documents as nullable (`_group_norms`: None = no gradient reached the group); update_norm and
     every other field get no exception, and each listed key must be typed "num" by the frozen schema;
  5. with only those leaves typed as numbers (a private copy, used for the schema computation only), the ORIGINAL
     schema functions reproduce the frozen schema exactly, layer coverage included.

    .venv/bin/python scripts/sgm-p2p5-pk-posthoc-validation-amendment.py --slot-root <evidence>/learned-n32 --out <new json>
writes the write-once local re-validation record (refuses to overwrite).
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm import packed_slot_cell_output_validation as V  # noqa: E402
from memsub.sgm import packed_slot_epoch_state as es  # noqa: E402

SPEC = ROOT / "configs/m4_sgm_p2p5_pk_posthoc_validation_amendment.json"
FORMAT = "m4-sgm-p2p5-pk-posthoc-validation-amendment-v1"
LABEL = "post-hoc amended"
NULLABLE_FIELD = "grad_norm"          # the ONLY nullable leaf family (memsub _group_norms); fixed here, not in the spec


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_spec(path: Path = SPEC) -> dict:
    spec = json.loads(Path(path).read_text())
    if spec.get("format") != FORMAT or spec.get("label") != LABEL:
        raise ValueError("post-hoc amendment spec: wrong format or label")
    return spec


def grad_norm_nulls(tele: list) -> list:
    """Sorted [step, key] of every null `grad_norm` leaf in the TRAINING telemetry rows."""
    return sorted([r["step"], k] for r in tele if "loss" in r
                  for k, v in (r.get(NULLABLE_FIELD) or {}).items() if v is None)


def amended_schema_problem(out: Path, pilot: dict, schema: dict, spec: dict) -> str | None:
    """Criteria 4 + 5: exact null set, each listed key typed num by the frozen schema, then the ORIGINAL schema
    functions on a private copy where only the listed leaves are typed as numbers."""
    tele = [V.strict_json(x) for x in (Path(out) / "routing_telemetry.jsonl").read_text().splitlines()]
    allowed = sorted([s, k] for s, k in spec["nullable_leaves"])
    if grad_norm_nulls(tele) != allowed:
        return "null grad_norm leaves differ from the spec list"
    frozen = schema["telemetry_train_row"]["dict"][NULLABLE_FIELD]["dict"]
    for _s, k in allowed:
        m = re.fullmatch(r"L(\d+)/(\w+)", k)
        if not m or m.group(1) not in V.selected_layer_ids(pilot) or frozen.get(f"L{{L}}/{m.group(2)}") != {"num": True}:
            return f"spec leaf {k} is not a frozen numeric grad_norm leaf"
    keep = {(s, k) for s, k in allowed}
    for r in tele:
        if "loss" in r:
            r[NULLABLE_FIELD] = {k: (0.0 if (r["step"], k) in keep else v) for k, v in r[NULLABLE_FIELD].items()}
    with tempfile.TemporaryDirectory() as d:
        shutil.copyfile(Path(out) / "metrics.json", Path(d) / "metrics.json")
        (Path(d) / "routing_telemetry.jsonl").write_text("".join(json.dumps(r) + "\n" for r in tele))
        try:
            got, seen = V.output_schemas(Path(d), pilot)
        except ValueError as e:
            return f"amended output schema: {e}"
    for k in ("metrics", "telemetry_eval_row", "telemetry_train_row"):
        if got[k] != schema[k]:
            return f"amended output schema: {k} differs from the frozen schema"
    return None if seen == V.selected_layer_ids(pilot) else "amended output schema: per-layer keys != selected layers"


def amended_cell_problem(slot_root: Path, rec: dict, pilot: dict, eval_cfg: dict, memsub_sha: str, registry: dict,
                         schema: dict, spec: dict) -> str | None:
    """None iff the record's cell satisfies criteria 1-5 (the caller already checked admitted epochs/chain walk)."""
    slot_root = Path(slot_root)
    cell_dir = slot_root / "cells" / spec["cell"]
    if rec.get("cell") != spec["cell"] or slot_root.name != spec["slot"]:
        return "not the amended cell"
    if rec.get("state") != es.FAILED or rec.get("reason") != spec["original_reason"] or rec.get("epoch") != spec["epoch"]:
        return "record is not the original FAILED record"
    if sha(es.epoch_dir(cell_dir, spec["epoch"]) / "state.json") != spec["state_sha256"]:
        return "FAILED record bytes differ from the spec"
    if not rec.get("chain") or rec["chain"][-1] != spec["terminal_checkpoint"] or \
            es.verify_chain(cell_dir, [spec["terminal_checkpoint"]]) is not None:
        return "terminal checkpoint differs from the spec"
    attempt = Path(slot_root) / spec["attempt"]
    if sha(attempt / "done.json") != spec["done_sha256"]:
        return "done.json differs from the spec"
    outputs = json.loads((attempt / "done.json").read_text()).get("outputs")
    if outputs != spec["outputs"]:
        return "done.json outputs differ from the spec"
    args = (attempt / "out", outputs, pilot, eval_cfg, memsub_sha, registry)
    if V.validate_cell_outputs(*args, schema) != spec["original_validation"]:
        return "original validator result differs from the original failure"
    other = V.validate_cell_outputs(*args, None)
    if other is not None:
        return f"original validator without the schema stage: {other}"
    return amended_schema_problem(attempt / "out", pilot, schema, spec)


def main():
    from memsub.sgm.packed_slot_supervisor import expand_cells
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out} (write-once record)")
    rd = _readings_module()
    spec = load_spec()
    grid, registry, schema = (json.loads(p.read_text()) for p in (rd.GRID, rd.REGISTRY, rd.SCHEMA))
    pilot = expand_cells(grid)[spec["cell"]]
    rec = es.read_record(a.slot_root / "cells" / spec["cell"], spec["epoch"])
    memsub = source_tree_sha256(ROOT / "memsub")
    problem = "no acknowledged record" if rec is None else amended_cell_problem(
        a.slot_root, rec, pilot, rd.EVAL, memsub, registry["by_arm"][pilot["arm"]], schema["by_arm"][pilot["arm"]], spec)
    record = {"format": f"{FORMAT}-revalidation-record", "label": LABEL, "cell": spec["cell"],
              "result": "amended_valid" if problem is None else f"rejected: {problem}",
              "spec_sha256": sha(SPEC), "memsub_source_sha256": memsub,
              "inputs_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in (rd.GRID, rd.REGISTRY, rd.SCHEMA)},
              "evidence": a.slot_root.resolve().relative_to(ROOT).as_posix(),
              "original_state": None if rec is None else rec.get("state"),
              "original_reason": None if rec is None else rec.get("reason"),
              "nullable_leaves": len(spec["nullable_leaves"])}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "x") as f:
        f.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": record["result"], "sha256": sha(a.out)}))
    if problem is not None:
        raise SystemExit(1)


def _readings_module():
    import importlib.util
    s = importlib.util.spec_from_file_location("rd_amd", ROOT / "scripts/sgm-p2p5-pk-campaign-readings.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


if __name__ == "__main__":
    main()
