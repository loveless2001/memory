"""One P2 pilot run with the §21 artifact set.

Emits: run_manifest.json, split_manifest.json, routing_telemetry.jsonl,
per_example_results.jsonl, metrics.json, report.md. Never overwrites an
existing run directory.
"""

from __future__ import annotations

import hashlib
import json
import platform
import time
from dataclasses import asdict
from pathlib import Path

import torch

from .synthetic_binding_task import split_manifest
from .synthetic_pilot import PilotConfig, train
from .synthetic_pilot_evaluation import INTERVENTIONS, evaluate

# Final-eval seed base 777_001 was used by the inspected sanity-v1 runs, so
# its episodes are DEVELOPMENT data; replacement grids use a fresh base.
EVAL_SEED_DEV, EVAL_SEED_FINAL, EVAL_SEED_TRAIN = 4242, 9_100_003, 555_001


def source_tree_sha256(package_root: Path) -> str:
    """Hash of the memsub package actually executed (sorted relative paths +
    bytes, bytecode caches excluded) - binds results to the exact code."""
    h = hashlib.sha256()
    for f in sorted(package_root.rglob("*.py")):
        if "pycache" in f.parent.name:
            continue
        h.update(str(f.relative_to(package_root.parent)).encode() + b"\0")
        h.update(f.read_bytes() + b"\0")
    return h.hexdigest()


def save_trained_parameters(runtime, head, path: Path) -> str:
    """Trained adapters + task head as safetensors; returns file sha256."""
    from safetensors.torch import save_file
    tensors = {f"adapters.{k}": v.detach().contiguous()
               for k, v in runtime.adapters.state_dict().items()}
    tensors.update({f"head.{k}": v.detach().contiguous() for k, v in head.state_dict().items()})
    save_file(tensors, str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _versions() -> dict:
    import transformers
    return {"torch": torch.__version__, "transformers": transformers.__version__,
            "python": platform.python_version(), "host": platform.node(),
            "threads": torch.get_num_threads()}


def run_pilot(pcfg: PilotConfig, out_dir: Path, *, final_batches: int = 16,
              final_batch_size: int = 16, extra_manifest: dict | None = None) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    started = time.time()
    spec = pcfg.task_spec()
    (out_dir / "split_manifest.json").write_text(json.dumps(split_manifest(
        spec, {"train": pcfg.seed, "dev_eval": EVAL_SEED_DEV,
               "final_eval": EVAL_SEED_FINAL + pcfg.seed}), indent=2))
    tele_f = (out_dir / "routing_telemetry.jsonl").open("w")

    def log(row):
        tele_f.write(json.dumps(row, default=float) + "\n"); tele_f.flush()

    def dev_eval(backend, head, step):
        return evaluate(backend, head, spec, pcfg.arm, pcfg.readout, split="heldout",
                        batches=pcfg.eval_batches, batch_size=pcfg.batch, seed=EVAL_SEED_DEV)

    result = train(pcfg, log=log, evaluate_fn=dev_eval)
    backend, head = result["backend"], result["head"]
    manifest = {"experiment": "m4-sgm-v0", "phase": "P2", "mode": "research_only",
                "result_label": pcfg.result_label(), "pilot_config": asdict(pcfg),
                "sgm_config": result["sgm_config"], "policy_id": result["policy_id"],
                "backbone": "tiny-qwen3-random-v1 (frozen, random init seed 0)",
                "ingest": "token_serial_full_gradient", "state_horizon_tokens": spec.source_len(),
                "gradient_horizon_tokens": spec.source_len(), "versions": _versions(),
                "final_eval_seed": EVAL_SEED_FINAL + pcfg.seed,
                "memsub_source_sha256": source_tree_sha256(Path(__file__).resolve().parents[1]),
                "trained_parameters_sha256": save_trained_parameters(
                    result["runtime"], head, out_dir / "trained_parameters.safetensors"),
                **(extra_manifest or {})}
    per_example: list[dict] = []
    metrics = {"result_label": pcfg.result_label(), "arm": pcfg.arm,
               "n_bindings": pcfg.n_bindings, "seed": pcfg.seed, "final": {}}
    interventions = INTERVENTIONS if pcfg.arm != "memory_off" else ("none",)
    for iv in interventions:
        metrics["final"][f"heldout_{iv}"] = evaluate(
            backend, head, spec, pcfg.arm, pcfg.readout, split="heldout",
            batches=final_batches, batch_size=final_batch_size,
            seed=EVAL_SEED_FINAL + pcfg.seed, intervention=iv, per_example=per_example)
    metrics["final"]["train_split_none"] = evaluate(
        backend, head, spec, pcfg.arm, pcfg.readout, split="train",
        batches=max(2, final_batches // 4), batch_size=final_batch_size,
        seed=EVAL_SEED_TRAIN + pcfg.seed)
    train_rows = [r for r in result["telemetry"] if "loss" in r]
    metrics["train_last"] = train_rows[-1] if train_rows else None
    metrics["wall_seconds"] = time.time() - started
    manifest["wall_seconds"] = metrics["wall_seconds"]
    tele_f.close()
    with (out_dir / "per_example_results.jsonl").open("w") as f:
        for row in per_example:
            f.write(json.dumps(row) + "\n")
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    metrics["run_manifest_sha256"] = hashlib.sha256(
        (out_dir / "run_manifest.json").read_bytes()).hexdigest()
    (out_dir / "report.md").write_text(_report(pcfg, metrics))
    metrics["per_example"] = per_example
    return metrics


def _report(pcfg: PilotConfig, m: dict) -> str:
    f = m["final"]
    lines = [f"# M4-SGM P2 pilot run — {pcfg.arm}, N={pcfg.n_bindings}, seed={pcfg.seed}", "",
             f"Label: **{m['result_label']}** — mechanism evidence on a frozen RANDOM tiny "
             "backbone; not a pretrained/frozen-Qwen result.", "",
             "| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |",
             "|---|---|---|---|---|"]
    for name, r in f.items():
        if r is None:
            lines.append(f"| {name} | n/a | | | |")
            continue
        lines.append(f"| {name} | {r['accuracy']:.3f} ({r['correct']}/{r['total']}) | "
                     f"{r['accuracy_ci95_halfwidth_episode']:.3f} | "
                     f"{r['effective_cells_mean']:.1f} | {r['query_empty_read_weight']} |")
    lines += ["", f"Chance = {1 / 64:.4f}. Wall seconds: {m['wall_seconds']:.0f}.", ""]
    return "\n".join(lines)
