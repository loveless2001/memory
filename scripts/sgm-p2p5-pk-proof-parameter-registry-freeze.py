"""Freeze the PK proof's parameter name/shape registry (codex 21567 #2): built from the REAL
construction of every distinct proof cell config (frozen pinned Qwen3-0.6B-Base, CPU), so the
acceptance comparator never derives expected names/shapes from the runs it judges.

    .venv/bin/python scripts/sgm-p2p5-pk-proof-parameter-registry-freeze.py   # writes once
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.packed_slot_cell_output_validation import parameter_registry  # noqa: E402
from memsub.sgm.packed_slot_supervisor import expand_cells  # noqa: E402
from memsub.sgm.synthetic_pilot_run import source_tree_sha256  # noqa: E402

GRID = ROOT / "configs/m4_sgm_p2p5_packed_proof_grid.json"
OUT = ROOT / "configs/m4_sgm_p2p5_packed_proof_registry.json"


def main():
    if OUT.exists():
        raise SystemExit(f"refusing to overwrite {OUT}")
    grid = json.loads(GRID.read_text())
    cells = expand_cells(grid)
    by_arm = {}
    for cid, pilot in cells.items():                  # names/shapes depend on arm/geometry, not the seed
        key = pilot["arm"]
        reg = parameter_registry({**pilot, "device": "cpu"})
        if key in by_arm and by_arm[key] != reg:
            raise SystemExit(f"{cid}: registry differs from another {key} cell")
        by_arm[key] = reg
    OUT.write_text(json.dumps({"grid_sha256": hashlib.sha256(GRID.read_bytes()).hexdigest(),
                               "memsub_source_sha256": source_tree_sha256(ROOT / "memsub"),
                               "by_arm": by_arm}, indent=2, sort_keys=True))
    print(OUT, {k: (len(v["grad_names_shapes"]), len(v["state_names_shapes"])) for k, v in by_arm.items()})


if __name__ == "__main__":
    main()
