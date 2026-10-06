"""Amendment PK per-cell output validation (codex 21567 #2/#3), shared by the slot supervisor
(before publishing COMPLETE) and the proof comparator (every run, before pairwise checks).

A cell's run_pilot output directory is valid only if every REQUIRED file is listed in done.json
with a matching sha256, all JSON is strict (no NaN/inf), the run manifest binds the cell's exact
pilot config / memsub source / artifact seed, the split manifest binds the registered or proof
populations, the per-example rows have the exact expected count and schema, the metrics carry
exactly the expected evaluation keys (single_cell coord_shuffle = None), the telemetry has the
expected number of eval / training rows, and the trained tensors match a FROZEN name/shape
registry with finite values. Nothing is inferred from the run itself.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from .packed_slot_epoch_state import file_sha256
from .synthetic_pilot_evaluation import INTERVENTIONS

REQUIRED_OUTPUTS = ("trained_parameters.safetensors", "metrics.json", "per_example_results.jsonl",
                    "routing_telemetry.jsonl", "run_manifest.json", "split_manifest.json", "report.md")
ROW_KEYS = {"batch", "episode", "episode_hash", "query", "key", "label", "pred", "correct", "intervention"}


def strict_json(text: str):
    def bad(c):
        raise ValueError(f"non-finite constant {c}")
    return json.loads(text, parse_constant=bad)


def applicable_interventions(arm: str) -> tuple[str, ...]:
    if arm == "memory_off":
        return ("none",)
    return tuple(i for i in INTERVENTIONS if not (arm == "single_cell" and i == "coord_shuffle"))


def expected_counts(pilot: dict, eval_cfg: dict) -> dict:
    ivs = applicable_interventions(pilot["arm"])
    steps, every = pilot["steps"], pilot["eval_every"]
    return {"rows": len(ivs) * eval_cfg["final_batches"] * eval_cfg["final_batch_size"] * pilot["n_queries"],
            "final_keys": sorted([f"heldout_{i}" for i in (INTERVENTIONS if pilot["arm"] != "memory_off" else ("none",))]
                                 + ["train_split_none"]),
            "telemetry_eval_rows": steps // every + 1,
            "telemetry_train_rows": len([s for s in range(steps) if s % 10 == 0])}


def parameter_registry(pilot: dict) -> dict:
    """Frozen-registry builder: names/shapes of trainable parameters (gradients) and of the
    saved tensors, from the REAL build of this pilot config (backbone never included)."""
    from .synthetic_pilot import PilotConfig, build
    rt, _backend, head = build(PilotConfig(**pilot))
    grads = {f"adapters.{n}": list(p.shape) for n, p in rt.adapters.named_parameters() if p.requires_grad}
    grads.update({f"head.{n}": list(p.shape) for n, p in head.named_parameters() if p.requires_grad})
    state = {f"adapters.{k}": list(v.shape) for k, v in rt.adapters.state_dict().items()}
    state.update({f"head.{k}": list(v.shape) for k, v in head.state_dict().items()})
    return {"grad_names_shapes": grads, "state_names_shapes": state}


def validate_cell_outputs(out: Path, done_outputs: dict, pilot: dict, eval_cfg: dict, memsub_sha: str,
                          registry: dict | None = None) -> str | None:
    """None = valid; else the first problem."""
    out = Path(out)
    missing = [f for f in REQUIRED_OUTPUTS if f not in done_outputs]
    if missing:
        return f"required outputs missing from done.json: {missing}"
    for f, h in done_outputs.items():
        if not (out / f).is_file() or file_sha256(out / f) != h:
            return f"output {f} missing or sha mismatch"
    try:
        man = strict_json((out / "run_manifest.json").read_text())
        split = strict_json((out / "split_manifest.json").read_text())
        metrics = strict_json((out / "metrics.json").read_text())
        rows = [strict_json(x) for x in (out / "per_example_results.jsonl").read_text().splitlines()]
        tele = [strict_json(x) for x in (out / "routing_telemetry.jsonl").read_text().splitlines()]
    except ValueError as e:
        return f"non-strict JSON: {e}"
    if man.get("pilot_config") != pilot:
        return "run manifest pilot_config differs from the cell config"
    if man.get("memsub_source_sha256") != memsub_sha:
        return "run manifest memsub source differs from the bound source"
    if man.get("final_eval_seed") != eval_cfg["final_seed_base"] + pilot["seed"]:
        return "artifact eval seed differs from the bound population"
    seeds = split.get("seeds", split)
    want = {"train": pilot["seed"], "dev_eval": eval_cfg["dev_seed"],
            "final_eval": eval_cfg["final_seed_base"] + pilot["seed"]}
    if any(seeds.get(k) != v for k, v in want.items()):
        return f"split manifest populations differ: {seeds} vs {want}"
    exp = expected_counts(pilot, eval_cfg)
    if len(rows) != exp["rows"] or any(set(r) != ROW_KEYS for r in rows):
        return f"per-example rows {len(rows)} != {exp['rows']} or schema differs"
    final = metrics.get("final") or {}
    if sorted(final) != exp["final_keys"]:
        return f"metrics final keys {sorted(final)} != {exp['final_keys']}"
    for k, v in final.items():
        na = pilot["arm"] == "single_cell" and k == "heldout_coord_shuffle"
        if na != (v is None):
            return f"metrics final.{k}: N/A mismatch"
    evals = [r for r in tele if "eval" in r]
    trains = [r for r in tele if "loss" in r]
    if (len(evals), len(trains)) != (exp["telemetry_eval_rows"], exp["telemetry_train_rows"]) or len(tele) != len(evals) + len(trains):
        return f"telemetry rows eval/train {len(evals)}/{len(trains)} != {exp['telemetry_eval_rows']}/{exp['telemetry_train_rows']}"
    if registry is not None:
        from safetensors.torch import load_file
        import torch
        t = load_file(str(out / "trained_parameters.safetensors"))
        if {k: list(v.shape) for k, v in t.items()} != registry["state_names_shapes"]:
            return "trained tensors differ from the frozen name/shape registry"
        if not all(bool(torch.isfinite(v).all()) for v in t.values()):
            return "non-finite trained tensor"
    if not (isinstance(metrics.get("wall_seconds"), (int, float)) and math.isfinite(metrics["wall_seconds"])
            and metrics["wall_seconds"] >= 0):
        return "wall_seconds clock not finite/non-negative"
    return None
