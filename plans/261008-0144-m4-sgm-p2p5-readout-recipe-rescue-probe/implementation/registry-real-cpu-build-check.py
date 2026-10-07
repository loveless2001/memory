"""Readout probe: compare the DERIVED frozen registry with a REAL CPU build of each probe cell config
(`parameter_registry` = memsub build(): frozen Qwen3-0.6B weights loaded on CPU, adapters + task head constructed).
Construction only: no forward pass, no population, no GPU, no Modal.

    .venv/bin/python <this file> <out json>
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from memsub.sgm.packed_slot_cell_output_validation import parameter_registry  # noqa: E402
from memsub.sgm.packed_slot_supervisor import expand_cells  # noqa: E402

grid_path, reg_path = ROOT / "configs/m4_sgm_p2p5_readout_probe_grid.json", ROOT / "configs/m4_sgm_p2p5_readout_probe_registry.json"
frozen = json.loads(reg_path.read_text())["learned"]
out = {"grid_sha256": hashlib.sha256(grid_path.read_bytes()).hexdigest(),
       "registry_sha256": hashlib.sha256(reg_path.read_bytes()).hexdigest(), "cells": {}}
for cid, pilot in expand_cells(json.loads(grid_path.read_text())).items():
    built = parameter_registry({**pilot, "device": "cpu"})
    out["cells"][cid] = {"equal": built == frozen, "n_state": len(built["state_names_shapes"]),
                         "head": built["state_names_shapes"]["head.weight"]}
out["all_equal"] = all(c["equal"] for c in out["cells"].values())
Path(sys.argv[1]).write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out))
sys.exit(0 if out["all_equal"] else 1)
