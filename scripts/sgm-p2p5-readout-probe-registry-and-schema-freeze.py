"""Freeze the readout probe's parameter registry and PATH-EXACT output schema (proposal v0.2 §8.1), write-once.

Both are DERIVED from frozen campaign files. Neither is read from a probe run, and nothing is added after results:
  * registry = the campaign learned registry with ONLY the head re-shaped to the taskhead input width
    (len(selected_layers) * memory_heads * value_dim = 4 * 4 * 32 = 512). Every adapter parameter stays, including
    the last layer's out_proj/alpha, which get no gradient under the task head (codex 21750 #1).
  * schema   = the campaign learned schema expanded to exact layer keys, with the graph contract applied
    (`contract_schema` in the probe validator).

    .venv/bin/python scripts/sgm-p2p5-readout-probe-registry-and-schema-freeze.py
"""

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.pinned_pretrained_qwen3_backbone import P2P5_SGM_DEFAULTS  # noqa: E402
from memsub.sgm.synthetic_pilot_run import source_tree_sha256  # noqa: E402

GRID = ROOT / "configs/m4_sgm_p2p5_readout_probe_grid.json"
CAMPAIGN_REGISTRY = ROOT / "configs/m4_sgm_p2p5_campaign_registry.json"
CAMPAIGN_SCHEMA = ROOT / "configs/m4_sgm_p2p5_campaign_output_schema.json"
VALIDATOR = ROOT / "scripts/sgm-p2p5-readout-probe-output-validation.py"
REGISTRY_OUT = ROOT / "configs/m4_sgm_p2p5_readout_probe_registry.json"
SCHEMA_OUT = ROOT / "configs/m4_sgm_p2p5_readout_probe_output_schema.json"
RESIDUAL_WIDTH = 1024        # Qwen3-0.6B hidden size = the campaign residual head's input width


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def validator():
    s = importlib.util.spec_from_file_location("probe_validation", VALIDATOR)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def taskhead_width(sgm: dict) -> int:
    c = {**P2P5_SGM_DEFAULTS, **sgm}
    return len(c["selected_layers"]) * c["memory_heads"] * c["value_dim"]


def derive() -> tuple[dict, dict]:
    grid = json.loads(GRID.read_text())
    if grid["base"]["readout"] != "taskhead" or grid["base"]["arm"] != "learned":
        raise SystemExit("probe grid base must be learned + taskhead")
    width = taskhead_width(grid["base"]["sgm"])
    reg = copy.deepcopy(json.loads(CAMPAIGN_REGISTRY.read_text())["by_arm"]["learned"])
    for part in ("grad_names_shapes", "state_names_shapes"):
        if reg[part].get("head.weight") != [64, RESIDUAL_WIDTH] or reg[part].get("head.bias") != [64]:
            raise SystemExit(f"campaign {part} head unexpected: {reg[part].get('head.weight')}")
        reg[part]["head.weight"] = [64, width]
    layers = sorted((str(x) for x in {**P2P5_SGM_DEFAULTS, **grid["base"]["sgm"]}["selected_layers"]), key=int)
    schema = validator().contract_schema(json.loads(CAMPAIGN_SCHEMA.read_text())["by_arm"]["learned"], layers)
    common = {"grid_sha256": sha(GRID), "memsub_source_sha256": source_tree_sha256(ROOT / "memsub")}
    registry = {**common, "derived_from": {"campaign_registry_sha256": sha(CAMPAIGN_REGISTRY),
                                           "change": f"head.weight [64, {width}] (taskhead width)"}, "learned": reg}
    schema_doc = {**common, "derived_from": {"campaign_schema_sha256": sha(CAMPAIGN_SCHEMA),
                                             "validator_sha256": sha(VALIDATOR),
                                             "change": "path-exact layer keys + taskhead None-vs-zero contract"},
                  "selected_layers": layers, "learned": schema}
    return registry, schema_doc


def main():
    for p in (REGISTRY_OUT, SCHEMA_OUT):
        if p.exists():
            raise SystemExit(f"refusing to overwrite {p}")
    registry, schema = derive()
    REGISTRY_OUT.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    SCHEMA_OUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"registry": sha(REGISTRY_OUT), "schema": sha(SCHEMA_OUT)}))


if __name__ == "__main__":
    main()
