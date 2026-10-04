"""M4-SGM P2 synthetic pilot grid on Modal CPU containers (no GPU).

Each grid cell is one independent run (arm x n_bindings x seed). Artifacts go
to the memsub-artifacts volume under m4-sgm/<group>/<run-id>/ and the metrics
are also returned to the local entrypoint, which writes them to
plans/<plan-dir>/runs/<group>/<run-id>/metrics.json.

    modal run --detach modal-runners/modal-m4-sgm-synthetic-pilot-grid.py \
        --group p2-load-sweep-v1 --grid configs/m4_sgm_p2_grid.json \
        --local-out plans/261005-0210-m4-sgm-p0-p2/runs
"""

import json
from pathlib import Path

import modal

app = modal.App("memsub-m4-sgm-p2-pilot")
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.7.1", index_url="https://download.pytorch.org/whl/cpu")
         .pip_install("transformers==4.55.2", "safetensors==0.5.3", "numpy==2.2.6")
         .env({"HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
         .add_local_dir("memsub", "/root/repo/memsub",
                        ignore=["**/__pycache__/**", "**/*.pyc"]))
artifacts = modal.Volume.from_name("memsub-artifacts")
CPUS = 4


@app.function(image=image, cpu=CPUS, memory=8192, timeout=4 * 3600, retries=0,
              volumes={"/artifacts": artifacts}, max_containers=48)
def run_cell(group: str, run_id: str, pilot: dict) -> dict:
    import re
    import sys

    import torch
    sys.path.insert(0, "/root/repo")
    from memsub.sgm.synthetic_pilot import PilotConfig
    from memsub.sgm.synthetic_pilot_run import run_pilot
    for name in (group, run_id):
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", name) is None:
            raise ValueError(f"invalid id {name!r}")
    torch.set_num_threads(CPUS)
    out = Path("/artifacts/m4-sgm") / group / run_id
    if out.exists():
        raise FileExistsError(f"{out} exists; no automatic retry")
    metrics = run_pilot(PilotConfig(**pilot), out,
                        extra_manifest={"modal_group": group, "run_id": run_id, "cpus": CPUS})
    artifacts.commit()
    return {"run_id": run_id, "metrics": metrics}


def _expand(grid: dict) -> list[tuple[str, dict]]:
    cells = []
    for block in grid["blocks"]:
        for arm in block["arms"]:
            for n in block["n_bindings"]:
                for seed in block["seeds"]:
                    pilot = {**grid["base"], **block.get("override", {}),
                             "arm": arm, "n_bindings": n, "seed": seed}
                    tag = block.get("tag", "main")
                    run_id = f"{tag}-{arm.replace('_', '-')}-n{n}-s{seed}"
                    cells.append((run_id, pilot))
    ids = [c[0] for c in cells]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate run ids in grid")
    return cells


@app.local_entrypoint()
def main(group: str, grid: str, local_out: str):
    spec = json.loads(Path(grid).read_text())
    cells = _expand(spec)
    print(f"launching {len(cells)} runs into m4-sgm/{group}")
    root = Path(local_out) / group
    root.mkdir(parents=True, exist_ok=True)
    (root / "grid.json").write_text(json.dumps(spec, indent=2))
    args = [(group, rid, pilot) for rid, pilot in cells]
    for res in run_cell.starmap(args, return_exceptions=True):
        if isinstance(res, Exception):
            print("RUN FAILED:", repr(res))
            continue
        d = root / res["run_id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "metrics.json").write_text(json.dumps(res["metrics"], indent=2, default=float))
        print("done", res["run_id"], {k: round(v["accuracy"], 3)
                                      for k, v in res["metrics"]["final"].items()})
