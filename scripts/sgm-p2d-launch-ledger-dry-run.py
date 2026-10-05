"""Dry-run the P2D admission ledger locally (no Modal calls).

    uv run python scripts/sgm-p2d-launch-ledger-dry-run.py
"""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "p2d_runner", ROOT / "modal-runners" / "modal-m4-sgm-p2d-diagnostics-grid.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
cells, ledger, prov = runner.plan(ROOT / "configs" / "m4_sgm_p2d_grid.json",
                                  ROOT / "plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v2")
print(json.dumps({"provenance": prov, "ledger": ledger}, indent=2))
