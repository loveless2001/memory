"""Read-only failure isolation; private type markers are never written to campaign artifacts."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from memsub.sgm.packed_slot_cell_output_validation import (
    selected_layer_ids, strict_json, structural_schema, validate_cell_outputs,
)
from memsub.sgm.packed_slot_supervisor import expand_cells

OUT = Path(__file__).resolve().parent
PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
GROUP = PLAN / "p2p5-qwen3-0p6b-screen-v1"
STATUS = json.loads((GROUP / "learned-n32/collect_status.json").read_text())
EVIDENCE = ROOT / STATUS["evidence_dir"] / "learned-n32"
PILOTS = expand_cells(json.loads((ROOT / "configs/m4_sgm_p2p5_grid.json").read_text()))
REGISTRY = json.loads((ROOT / "configs/m4_sgm_p2p5_campaign_registry.json").read_text())["by_arm"]["learned"]
SCHEMA = json.loads((ROOT / "configs/m4_sgm_p2p5_campaign_output_schema.json").read_text())["by_arm"]["learned"]
SOURCE_SHA = "2eee4228124e9d292ed4079476ca276e8ce8f9ac7c8d83d44bcd51333687a19b"
EVAL = {"final_batches": 16, "final_batch_size": 16, "final_seed_base": 9300011,
        "dev_seed": 4242, "train_eval_seed_base": 555001}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


cells = {}
for seed in (0, 1):
    cid = f"learned-n32-s{seed}"
    epoch = EVIDENCE / "cells" / cid / "epoch-1"
    rec = strict_json((epoch / "state.json").read_text())
    attempt = epoch / "attempt-1"
    out = attempt / "out"
    done = strict_json((attempt / "done.json").read_text())["outputs"]
    pilot = PILOTS[cid]
    full = validate_cell_outputs(out, done, pilot, EVAL, SOURCE_SHA, REGISTRY, SCHEMA)
    other_checks = validate_cell_outputs(out, done, pilot, EVAL, SOURCE_SHA, REGISTRY, schema=None)
    rows = [strict_json(ln) for ln in (out / "routing_telemetry.jsonl").read_text().splitlines()]
    layers = selected_layer_ids(pilot)
    issues, nulls, type_only_schemas = [], [], []
    for line, row in enumerate(rows, 1):
        try:
            structural_schema(row, layers, set())
        except ValueError as exc:
            issues.append({"line": line, "step": row["step"], "reason": str(exc)})
        keys = [k for k, v in row.get("grad_norm", {}).items() if v is None]
        if keys:
            nulls.append({"line": line, "step": row["step"], "keys": keys,
                          "update_norm": {k: row["update_norm"][k] for k in keys}})
        # Diagnostic isolation only: replace documented missing-gradient values in a private copy
        # with a numeric type marker, to test whether any OTHER frozen schema difference remains.
        # The copy is never persisted, accepted, evaluated or passed back to the campaign.
        private_row = copy.deepcopy(row)
        for key in keys:
            private_row["grad_norm"][key] = 0.0
        got = structural_schema(private_row, layers, set())
        kind = "telemetry_train_row" if "loss" in row else "telemetry_eval_row"
        type_only_schemas.append(got == SCHEMA[kind])
    metrics = strict_json((out / "metrics.json").read_text())
    last = rec["chain"][-1]
    actual_terminal_hash = sha(epoch / last["file"])
    output_hashes = {name: sha(out / name) for name in done}
    cells[cid] = {
        "state": rec["state"], "reason": rec.get("reason"), "epoch": rec["epoch"],
        "state_sha256": sha(epoch / "state.json"), "done_sha256": sha(attempt / "done.json"),
        "record_has_complete_output_pointer": "outputs" in rec,
        "full_frozen_validator": full or "valid", "all_checks_except_structural_schema": other_checks or "valid",
        "terminal_generation": last, "terminal_generation_hash_matches": actual_terminal_hash == last["sha256"],
        "output_hashes": output_hashes, "output_hashes_match_done": output_hashes == done,
        "telemetry_rows": len(rows), "train_rows": sum("loss" in r for r in rows),
        "schema_failure_rows": issues, "null_gradient_rows": nulls,
        "null_gradient_leaf_count": sum(len(r["keys"]) for r in nulls),
        "null_update_leaf_count": sum(v is None for r in rows for v in r.get("update_norm", {}).values()),
        "otherwise_matches_frozen_telemetry_types": all(type_only_schemas),
        "metrics_schema_matches": structural_schema(metrics, layers, set()) == SCHEMA["metrics"],
    }
    assert cells[cid]["terminal_generation_hash_matches"] and cells[cid]["output_hashes_match_done"]
    assert other_checks is None and all(type_only_schemas) and cells[cid]["metrics_schema_matches"]
assert cells["learned-n32-s0"]["full_frozen_validator"] == "valid"
failed = cells["learned-n32-s1"]
assert failed["state"] == "FAILED" and len(failed["schema_failure_rows"]) == 17 and failed["null_gradient_leaf_count"] == 51
assert all(set(r["keys"]) == {"L20/k_proj", "L20/value", "L20/beta"} for r in failed["null_gradient_rows"])
assert all(all(v == 0 for v in r["update_norm"].values()) for r in failed["null_gradient_rows"])
assert failed["null_update_leaf_count"] == 0
summary = {"diagnosis": "documented nullable gradient diagnostics rejected by frozen homogeneous-layer schema",
           "acceptance": "unchanged: learned-n32-s1 remains FAILED; original all-18-valid readings gate blocked",
           "cells": cells, "tracked_diff": subprocess.check_output(["git", "diff", "HEAD", "--"], text=True),
           "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
           "artifact_edits": 0, "remote_mutations": 0}
(OUT / "schema-diagnosis.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({"diagnosis": summary["diagnosis"], "acceptance": summary["acceptance"],
                  "cells": {k: {f: v[f] for f in ("state", "full_frozen_validator", "all_checks_except_structural_schema",
                             "null_gradient_leaf_count", "null_update_leaf_count", "otherwise_matches_frozen_telemetry_types",
                             "record_has_complete_output_pointer", "state_sha256", "done_sha256")} for k, v in cells.items()}}))
