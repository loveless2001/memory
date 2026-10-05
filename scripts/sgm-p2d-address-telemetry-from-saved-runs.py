"""P2D Step 1 (local, descriptive): address telemetry for the 20 saved P2 v2
`learned` / `random_fixed` runs. See M4-SGM.md § P2D Step 1.

Per cell:
  1. Reload trained adapters + head; check sha256s against the manifest.
  2. DEV equivalence (the telemetry set, seed 4242): the frozen-v2 runtime
     (memsub extracted from 1d62903) and the observer runtime, same
     checkpoint, must give bitwise-identical task-head logits and preds on
     every dev query; the aggregate also must equal the run's last logged dev eval.
  3. Separate COMPATIBILITY check on the old final set (9_100_003 + seed):
     replayed preds must equal the saved per-example rows. Not telemetry.
  4. DEV telemetry: per-layer/per-head stencil geometry and the direct
     fixed-final-query filler test (pre- vs post-filler bank reads), with
     paired per-query transitions and read changes.

    uv run python scripts/sgm-p2d-address-telemetry-from-saved-runs.py \
        --mirror plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v2-volume-mirror \
        --out plans/261005-0210-m4-sgm-p0-p2/p2d/step1-address-telemetry.json
"""

import argparse
import hashlib
import importlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memsub.sgm.backend import SourceRef  # noqa: E402
from memsub.sgm.p2d_address_diagnostics import episode_geometry, fixed_query_read  # noqa: E402
from memsub.sgm.synthetic_binding_task import sample_batch  # noqa: E402
from memsub.sgm.synthetic_pilot import PilotConfig, build  # noqa: E402
from memsub.sgm.synthetic_pilot_evaluation import evaluate  # noqa: E402
from memsub.sgm.synthetic_pilot_run import EVAL_SEED_DEV, source_tree_sha256  # noqa: E402

CELLS = [f"main-{arm}-n{n}-s{s}" for arm in ("learned", "random-fixed")
         for n in (4, 8, 16, 32, 64) for s in (0, 1)]
DEV_BATCHES = 4
FROZEN_COMMIT = "1d62903e3e093ee625642b5ef4c86b3b6cae6d2b"


def load_frozen_memsub(commit: str = FROZEN_COMMIT, name: str = "memsub_frozen"):
    """Import memsub exactly as committed at `commit` under another package
    name (memsub uses relative imports internally)."""
    if name in sys.modules:
        return sys.modules[name]
    tmp = Path(tempfile.mkdtemp(prefix="memsub-frozen-"))
    tar = subprocess.run(["git", "archive", commit, "memsub"], capture_output=True, check=True,
                         cwd=Path(__file__).resolve().parents[1]).stdout
    subprocess.run(["tar", "-x", "-C", str(tmp)], input=tar, check=True)
    frozen_sha = source_tree_sha256(tmp / "memsub")     # hashed under its original name
    shutil.move(str(tmp / "memsub"), str(tmp / name))
    sys.path.insert(0, str(tmp))
    mod = importlib.import_module(name)
    mod.FROZEN_COMMIT, mod.FROZEN_SOURCE_SHA256 = commit, frozen_sha
    return mod


def dev_logits(pkg: str, pcfg, tensors: dict):
    """Task-head logits + preds for every dev query under package `pkg`."""
    pilot = importlib.import_module(f"{pkg}.sgm.synthetic_pilot")
    ev = importlib.import_module(f"{pkg}.sgm.synthetic_pilot_evaluation")
    task = importlib.import_module(f"{pkg}.sgm.synthetic_binding_task")
    runtime, backend, head = pilot.build(pilot.PilotConfig(**pcfg.__dict__))
    runtime.adapters.load_state_dict({k[9:]: v for k, v in tensors.items() if k.startswith("adapters.")})
    head.load_state_dict({k[5:]: v for k, v in tensors.items() if k.startswith("head.")})
    gen, out = torch.Generator().manual_seed(EVAL_SEED_DEV), []
    with torch.no_grad():
        for _ in range(pcfg.eval_batches):
            b = task.sample_batch(pcfg.task_spec(), "heldout", pcfg.batch, gen)
            st = ev.ingest(backend, b, pcfg.arm).detached()
            for q in range(pcfg.n_queries):
                logits, _ = ev.query_logits(backend, head, st, b, q, pcfg.arm, pcfg.readout, detach=True)
                out.append((logits, b.labels[:, q]))
    return torch.cat([l for l, _ in out]), torch.cat([y for _, y in out])


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cell(cell: Path):
    from safetensors.torch import load_file
    man = json.loads((cell / "run_manifest.json").read_text())
    if sha(cell / "trained_parameters.safetensors") != man["trained_parameters_sha256"]:
        raise SystemExit(f"{cell.name}: parameter hash mismatch")
    pcfg = PilotConfig(**man["pilot_config"])
    runtime, backend, head = build(pcfg)
    t = load_file(str(cell / "trained_parameters.safetensors"))
    runtime.adapters.load_state_dict({k[9:]: v for k, v in t.items() if k.startswith("adapters.")})
    head.load_state_dict({k[5:]: v for k, v in t.items() if k.startswith("head.")})
    return man, pcfg, backend, head


def dev_equivalence(cell: Path, pcfg) -> dict:
    from safetensors.torch import load_file
    load_frozen_memsub()
    tensors = load_file(str(cell / "trained_parameters.safetensors"))
    frozen, y = dev_logits("memsub_frozen", pcfg, tensors)
    observer, y2 = dev_logits("memsub", pcfg, tensors)
    if not (torch.equal(frozen, observer) and torch.equal(y, y2)):
        raise SystemExit(f"{cell.name}: observer dev logits differ from frozen-v2 runtime")
    correct = int((observer.argmax(-1) == y).sum())
    rows = [json.loads(l) for l in (cell / "routing_telemetry.jsonl").read_text().splitlines()]
    logged = [r for r in rows if "eval" in r][-1]["eval"]
    if (correct, len(y)) != (logged["correct"], logged["total"]):
        raise SystemExit(f"{cell.name}: dev aggregate differs from last logged dev eval")
    return {"dev_queries_bitwise_equal_to_frozen": len(y), "dev_correct": correct}


def compatibility_replay_old_final(cell: Path, man: dict, pcfg, backend, head) -> int:
    rows: list = []
    met = json.loads((cell / "metrics.json").read_text())
    evaluate(backend, head, pcfg.task_spec(), pcfg.arm, pcfg.readout, split="heldout",
             batches=met["final_episodes"] // pcfg.batch, batch_size=pcfg.batch,
             seed=man["final_eval_seed"], per_example=rows)
    saved = [json.loads(l) for l in (cell / "per_example_results.jsonl").read_text().splitlines()]
    key = lambda r: (r["batch"], r["episode"], r["episode_hash"], r["query"], r["pred"])
    if sorted(map(key, rows)) != sorted(key(r) for r in saved if r["intervention"] == "none"):
        raise SystemExit(f"{cell.name}: replay predictions differ from saved rows")
    return len(rows)


@torch.no_grad()
def dev_diagnostics(pcfg, backend, head, dev_correct: int) -> dict:
    spec, gen = pcfg.task_spec(), torch.Generator().manual_seed(EVAL_SEED_DEV)
    layers = backend.runtime.cfg.selected_layers
    n_bind = 4 + 2 * spec.n_bindings
    val_pos = [4 + 2 * j + 1 for j in range(spec.n_bindings)]
    fill_pos = list(range(n_bind, spec.source_len()))
    geo: dict = {l: [] for l in layers}
    hits = {"pre_filler": 0, "post_filler": 0, "actual": 0}
    trans = {"correct_to_wrong": 0, "wrong_to_correct": 0, "both_correct": 0, "both_wrong": 0}
    rel_change: list = []
    total = episodes = 0
    for _ in range(DEV_BATCHES):
        b = sample_batch(spec, "heldout", pcfg.batch, gen)
        traces: list = []
        pre = backend.ingest_source(backend.new_state(pcfg.batch), b.source[:, :n_bind],
                                    SourceRef("bindings"), traces=traces).detached()
        post = backend.ingest_source(pre, b.source[:, n_bind:], SourceRef("filler"),
                                     traces=traces).detached()
        episodes += pcfg.batch
        keys = b.source[:, 4:n_bind:2]
        q_bind = torch.stack([(keys == b.query_keys[:, q:q + 1]).float().argmax(1)
                              for q in range(spec.n_queries)], 1)               # [B, Q]
        reads_q = {l: [] for l in layers}
        for q in range(spec.n_queries):
            out = backend.evaluate_query(post, b.query_keys[:, q:q + 1], detach=True, logits=False)
            feats = {}
            for name, bank in (("pre_filler", pre.banks), ("post_filler", post.banks)):
                feats[name] = torch.cat([fixed_query_read(
                    bank, l, out["trace"]["read_q"][l][-1], out["trace"]["read_coords"][l][-1]
                ).flatten(1) for l in layers], -1)
            feats["actual"] = torch.cat([out["reads"][l][:, -1].flatten(1) for l in layers], -1)
            if not torch.equal(feats["post_filler"], feats["actual"]):
                raise SystemExit("invariant: reconstructed post-filler reads != actual reads")
            ok = {}
            for name, f in feats.items():
                ok[name] = head(f).argmax(-1) == b.labels[:, q]
                hits[name] += int(ok[name].sum())
            pre_ok, post_ok = ok["pre_filler"], ok["post_filler"]
            trans["correct_to_wrong"] += int((pre_ok & ~post_ok).sum())
            trans["wrong_to_correct"] += int((~pre_ok & post_ok).sum())
            trans["both_correct"] += int((pre_ok & post_ok).sum())
            trans["both_wrong"] += int((~pre_ok & ~post_ok).sum())
            d = feats["post_filler"] - feats["pre_filler"]
            rel_change += (d.norm(dim=-1) / feats["pre_filler"].norm(dim=-1).clamp_min(1e-12)).tolist()
            total += b.labels.shape[0]
            for l in layers:
                reads_q[l].append(out["trace"]["read_coords"][l][-1])
        for l in layers:
            w = torch.stack([traces[t]["write_coords"][l] for t in range(len(traces))], 1)
            geo[l].append(episode_geometry(w, val_pos, fill_pos, torch.stack(reads_q[l], 1), q_bind))
    per_layer = {}
    for l in layers:
        agg = {k: [sum(g[k][h] for g in geo[l]) / len(geo[l]) for h in range(len(geo[l][0][k]))]
               for k in geo[l][0] if not k.startswith("_")}   # equal-size batches: pooled means
        pooled = torch.cat([g["_align_distances"] for g in geo[l]])
        agg["align_distance_median_pooled"] = pooled.median(0).values.tolist()
        per_layer[str(l)] = agg
    if sum(trans.values()) != total:
        raise SystemExit("invariant: transitions do not sum to total queries")
    if hits["actual"] != dev_correct:
        raise SystemExit(f"invariant: diagnostic actual correct {hits['actual']} != dev check {dev_correct}")
    rc = torch.tensor(rel_change)
    return {"dev_episodes": episodes, "dev_queries": total,
            "fixed_query_accuracy": {k: v / total for k, v in hits.items()},
            "fixed_query_transitions_pre_to_post": trans,
            "fixed_query_read_relative_change": {"median": float(rc.median()), "mean": float(rc.mean())},
            "geometry_per_layer_head": per_layer}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--smoke-cells", nargs="*", help="TEST ONLY: replace the 20 registered cells")
    args = ap.parse_args()
    torch.set_num_threads(4)
    cells = args.smoke_cells or CELLS
    missing = [c for c in cells if not (args.mirror / c).is_dir()]
    if missing:
        raise SystemExit(f"missing registered cells: {missing}")
    head_rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "memsub", "scripts"],
                                capture_output=True, text=True).stdout.strip())
    report = {"observer": {"git_head": head_rev, "dirty": dirty,
                           "memsub_source_sha256": source_tree_sha256(Path("memsub").resolve())},
              "dev_seed": EVAL_SEED_DEV, "dev_batches": DEV_BATCHES,
              "registered_cells": cells == CELLS, "cells": {}}
    for name in cells:
        cell = args.mirror / name
        man, pcfg, backend, head = load_cell(cell)
        if pcfg.eval_batches != DEV_BATCHES:
            raise SystemExit(f"{name}: eval_batches {pcfg.eval_batches} != DEV_BATCHES")
        equiv = dev_equivalence(cell, pcfg)
        report["cells"][name] = {
            "run_manifest_sha256": sha(cell / "run_manifest.json"),
            "trained_parameters_sha256": man["trained_parameters_sha256"],
            "dev_equivalence": equiv,
            "compatibility_check_old_final_set_rows": compatibility_replay_old_final(
                cell, man, pcfg, backend, head),
            **dev_diagnostics(pcfg, backend, head, equiv["dev_correct"])}
        print(name, report["cells"][name]["fixed_query_accuracy"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
