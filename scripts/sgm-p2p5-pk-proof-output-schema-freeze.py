"""Freeze the PK proof's metrics / telemetry FIELD schema (codex 21570 #1): derived once from a real
tiny-CPU run_pilot of the proof's learned cell config (same code path, same step/eval shape), with
selected-layer keys normalised ('L6/q_proj' -> 'L{L}/q_proj'); the comparator and the supervisor check
every run against this file and the exact selected-layer set, never against another run.

    .venv/bin/python scripts/sgm-p2p5-pk-proof-output-schema-freeze.py   # writes once
"""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.packed_slot_cell_output_validation import output_schemas  # noqa: E402
from memsub.sgm.packed_slot_supervisor import expand_cells  # noqa: E402
from memsub.sgm.synthetic_pilot import PilotConfig  # noqa: E402
from memsub.sgm.synthetic_pilot_run import run_pilot, source_tree_sha256  # noqa: E402

GRID = ROOT / "configs/m4_sgm_p2p5_packed_proof_grid.json"
OUT = ROOT / "configs/m4_sgm_p2p5_packed_proof_output_schema.json"


def main():
    if OUT.exists():
        raise SystemExit(f"refusing to overwrite {OUT}")
    grid = json.loads(GRID.read_text())
    by_arm = {}
    for cid, pilot in expand_cells(grid).items():
        tiny = {**pilot, "backbone": "tiny", "device": "cpu", "n_bindings": 4, "batch": 2}
        with tempfile.TemporaryDirectory() as d:
            ev = grid["eval"]
            run_pilot(PilotConfig(**tiny), Path(d) / "out", final_batches=ev["final_batches"], final_batch_size=2,
                      final_seed_base=ev["final_seed_base"], dev_seed=ev["dev_seed"],
                      train_eval_seed_base=ev["train_eval_seed_base"])
            schema, _seen = output_schemas(Path(d) / "out", tiny)
        if pilot["arm"] in by_arm and by_arm[pilot["arm"]] != schema:
            raise SystemExit(f"{cid}: schema differs from another {pilot['arm']} cell")
        by_arm[pilot["arm"]] = schema
    OUT.write_text(json.dumps({"grid_sha256": hashlib.sha256(GRID.read_bytes()).hexdigest(),
                               "memsub_source_sha256": source_tree_sha256(ROOT / "memsub"),
                               "derived_from": "tiny-CPU run_pilot of each proof cell config (layer keys normalised)",
                               "by_arm": by_arm}, indent=2, sort_keys=True))
    print(OUT, {k: len(v["metrics"]["dict"]) for k, v in by_arm.items()})


if __name__ == "__main__":
    main()
