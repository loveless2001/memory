"""P2D Step 1 (local, descriptive): address telemetry for saved P2 runs.

Reloads each v2 run's trained adapters + task head, checks the reload
reproduces that run's last logged dev evaluation exactly, then measures on
DEV episodes (seed 4242; never the final set):
  * alignment  — distance (cells) from a query's read coordinate to the write
                 coordinate of its binding's value token, per layer/head;
  * collisions — fraction of binding pairs whose write stencils overlap
                 (|dx| < 3 and |dy| < 3);
  * filler_hits — fraction of filler writes whose stencil overlaps some
                 binding's write stencil.

    uv run python scripts/sgm-p2d-address-telemetry-from-saved-runs.py \
        --mirror plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v2-volume-mirror \
        --out plans/261005-0210-m4-sgm-p0-p2/p2d/step1-address-telemetry.json
"""

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memsub.sgm.synthetic_binding_task import sample_batch  # noqa: E402
from memsub.sgm.synthetic_pilot import PilotConfig, build  # noqa: E402
from memsub.sgm.synthetic_pilot_evaluation import evaluate, ingest  # noqa: E402
from memsub.sgm.synthetic_pilot_run import EVAL_SEED_DEV  # noqa: E402

ARMS = ("learned", "random_fixed")


def load_run(cell: Path):
    from safetensors.torch import load_file
    man = json.loads((cell / "run_manifest.json").read_text())
    pcfg = PilotConfig(**man["pilot_config"])
    runtime, backend, head = build(pcfg)
    tensors = load_file(str(cell / "trained_parameters.safetensors"))
    runtime.adapters.load_state_dict({k[9:]: v for k, v in tensors.items() if k.startswith("adapters.")})
    head.load_state_dict({k[5:]: v for k, v in tensors.items() if k.startswith("head.")})
    return pcfg, backend, head


def last_dev_eval(cell: Path) -> dict:
    rows = [json.loads(l) for l in (cell / "routing_telemetry.jsonl").read_text().splitlines()]
    return [r for r in rows if "eval" in r][-1]["eval"]


def overlap(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """3x3 stencils around coords a [...,2], b [...,2] share a cell."""
    d = (a - b).abs()
    return (d[..., 0] < 3) & (d[..., 1] < 3)


@torch.no_grad()
def telemetry(pcfg: PilotConfig, backend, batches: int) -> dict:
    spec, gen = pcfg.task_spec(), torch.Generator().manual_seed(EVAL_SEED_DEV)
    layers = backend.runtime.cfg.selected_layers
    align, coll, filler = [], [], []
    for _ in range(batches):
        batch = sample_batch(spec, "heldout", pcfg.batch, gen)
        traces: list = []
        state = ingest(backend, batch, pcfg.arm, traces).detached()
        val_pos = [4 + 2 * j + 1 for j in range(spec.n_bindings)]
        fill_pos = range(4 + 2 * spec.n_bindings, spec.source_len())
        for l in layers:
            w = torch.stack([traces[t]["write_coords"][l] for t in range(len(traces))], 1)  # [B,T,H,2]
            wv = w[:, val_pos]                                                              # [B,N,H,2]
            pair = overlap(wv.unsqueeze(2), wv.unsqueeze(1))                               # [B,N,N,H]
            off_diag = ~torch.eye(spec.n_bindings, dtype=torch.bool)[None, :, :, None]
            coll.append(float(pair[off_diag.expand_as(pair)].float().mean()))
            wf = w[:, list(fill_pos)]
            filler.append(float(overlap(wf.unsqueeze(2), wv.unsqueeze(1)).any(2).float().mean()))
        keys = batch.source[:, 4:4 + 2 * spec.n_bindings:2]                                # [B,N]
        for q in range(spec.n_queries):
            out = backend.evaluate_query(state, batch.query_keys[:, q:q + 1], detach=True, logits=False)
            j = (keys == batch.query_keys[:, q:q + 1]).float().argmax(1)                     # binding index
            for l in layers:
                read = out["trace"]["read_coords"][l][-1]                                   # [B,H,2]
                wrote = torch.stack([traces[val_pos[int(j[b])]]["write_coords"][l][b]
                                     for b in range(len(j))])                               # [B,H,2]
                align.append((read - wrote).norm(dim=-1).flatten())
    a = torch.cat(align)
    return {"alignment_median_cells": float(a.median()), "aligned_within_1_cell": float((a < 1).float().mean()),
            "read_stencil_reaches_write": float((a < 3).float().mean()),
            "binding_pair_collision_rate": sum(coll) / len(coll),
            "filler_write_overlaps_binding": sum(filler) / len(filler)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--batches", type=int, default=4)
    args = ap.parse_args()
    torch.set_num_threads(4)
    results = {}
    for cell in sorted(args.mirror.iterdir()):
        if not cell.name.startswith("main-") or not any(f"-{a.replace('_', '-')}-n" in cell.name for a in ARMS):
            continue
        pcfg, backend, head = load_run(cell)
        logged = last_dev_eval(cell)
        redo = evaluate(backend, head, pcfg.task_spec(), pcfg.arm, pcfg.readout, split="heldout",
                        batches=pcfg.eval_batches, batch_size=pcfg.batch, seed=EVAL_SEED_DEV)
        if (redo["correct"], redo["total"]) != (logged["correct"], logged["total"]):
            raise SystemExit(f"{cell.name}: reload does not reproduce logged dev eval")
        results[cell.name] = {"dev_accuracy": redo["accuracy"], "reload_reproduces_dev_eval": True,
                              **telemetry(pcfg, backend, args.batches)}
        print(cell.name, {k: round(v, 3) if isinstance(v, float) else v for k, v in results[cell.name].items()})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
