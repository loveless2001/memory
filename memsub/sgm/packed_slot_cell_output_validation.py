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
import re
from pathlib import Path

from .packed_slot_epoch_state import file_sha256
from .synthetic_pilot_evaluation import INTERVENTIONS

REQUIRED_OUTPUTS = ("trained_parameters.safetensors", "metrics.json", "per_example_results.jsonl",
                    "routing_telemetry.jsonl", "run_manifest.json", "split_manifest.json", "report.md")
ROW_KEYS = {"batch", "episode", "episode_hash", "query", "key", "label", "pred", "correct", "intervention"}


def strict_json(text: str):
    """JSON with every number finite: NaN/Infinity literals AND overflowing literals such as
    1e999 are rejected (codex 21572 #1)."""
    def bad(c):
        raise ValueError(f"non-finite constant {c}")

    def finite_float(x: str) -> float:
        v = float(x)
        if not math.isfinite(v):
            raise ValueError(f"non-finite number literal {x}")
        return v
    return json.loads(text, parse_constant=bad, parse_float=finite_float)


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


def row_coverage(rows: list, pilot: dict, eval_cfg: dict) -> str | None:
    """Exactly one row per intervention x batch x episode x query (no duplicates / gaps); each
    row's correctness == (pred == label); one episode hash per (batch, episode) across every
    intervention (the same population is re-read under each intervention)."""
    want = {(iv, b, e, q) for iv in applicable_interventions(pilot["arm"]) for b in range(eval_cfg["final_batches"])
            for e in range(eval_cfg["final_batch_size"]) for q in range(pilot["n_queries"])}
    got = [(r["intervention"], r["batch"], r["episode"], r["query"]) for r in rows]
    if len(set(got)) != len(got) or set(got) != want:
        return "per-example rows do not cover intervention x batch x episode x query exactly once"
    hashes = {}
    for r in rows:
        if r["correct"] != (r["pred"] == r["label"]):
            return "per-example row correctness differs from pred == label"
        if hashes.setdefault((r["batch"], r["episode"]), r["episode_hash"]) != r["episode_hash"]:
            return "episode hash differs across interventions for one (batch, episode)"
    return None


def selected_layer_ids(pilot: dict) -> set[str]:
    from .synthetic_pilot import TINY_SGM_DEFAULTS
    if pilot["backbone"] == "tiny":
        layers = TINY_SGM_DEFAULTS["selected_layers"]
    else:
        from .pinned_pretrained_qwen3_backbone import P2P5_SGM_DEFAULTS
        layers = P2P5_SGM_DEFAULTS["selected_layers"]
    return {str(x) for x in (pilot.get("sgm") or {}).get("selected_layers", layers)}


def structural_schema(obj, layers: set[str], seen: set) -> dict:
    """Recursive key / type / N-A description; selected-layer keys are normalised ('6' -> '{L}',
    'L6/q_proj' -> 'L{L}/q_proj') and recorded in `seen` (codex 21570 #1: frozen field schema)."""
    if isinstance(obj, dict):
        keys, covered = {}, {}
        for k, v in obj.items():
            nk, m, layer = k, re.match(r"^L(\d+)/(.*)$", k), None
            if k in layers:
                nk, layer = "{L}", k
            elif m and m.group(1) in layers:
                nk, layer = "L{L}/" + m.group(2), m.group(1)
            if layer is not None:
                seen.add(layer)
                covered.setdefault(nk, set()).add(layer)
            sv = structural_schema(v, layers, seen)
            if nk in keys and keys[nk] != sv:
                raise ValueError(f"layer-normalised key {nk} has inconsistent schemas")
            keys[nk] = sv
        for nk, got in covered.items():          # EVERY per-layer field covers EVERY selected layer
            if got != layers:
                raise ValueError(f"per-layer key {nk} covers layers {sorted(got)} != {sorted(layers)}")
        return {"dict": dict(sorted(keys.items()))}
    if isinstance(obj, list):
        items = [structural_schema(x, layers, seen) for x in obj]
        if any(i != items[0] for i in items):
            raise ValueError("heterogeneous list")
        return {"list": items[0] if items else None}
    if obj is None:
        return {"null": True}
    if isinstance(obj, bool):
        return {"bool": True}
    if isinstance(obj, (int, float)):
        return {"num": True}
    if isinstance(obj, str):
        return {"str": True}
    raise ValueError(f"unsupported type {type(obj).__name__}")


def output_schemas(out: Path, pilot: dict) -> tuple[dict, set]:
    """Schemas of metrics.json and of the telemetry eval / train rows of one run."""
    layers, seen = selected_layer_ids(pilot), set()
    metrics = strict_json((out / "metrics.json").read_text())
    tele = [strict_json(x) for x in (out / "routing_telemetry.jsonl").read_text().splitlines()]
    ev = [structural_schema(r, layers, seen) for r in tele if "eval" in r]
    tr = [structural_schema(r, layers, seen) for r in tele if "loss" in r]
    if any(x != ev[0] for x in ev) or any(x != tr[0] for x in tr):
        raise ValueError("telemetry rows of one kind have different schemas")
    return {"metrics": structural_schema(metrics, layers, seen), "telemetry_eval_row": ev[0] if ev else None,
            "telemetry_train_row": tr[0] if tr else None}, seen


def validate_cell_outputs(out: Path, done_outputs: dict, pilot: dict, eval_cfg: dict, memsub_sha: str,
                          registry: dict | None = None, schema: dict | None = None) -> str | None:
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
    problem = row_coverage(rows, pilot, eval_cfg)
    if problem:
        return problem
    final = metrics.get("final") or {}
    if sorted(final) != exp["final_keys"]:
        return f"metrics final keys {sorted(final)} != {exp['final_keys']}"
    for iv in applicable_interventions(pilot["arm"]):          # rows <-> metric counts
        f = final.get(f"heldout_{iv}") or {}
        sel = [r for r in rows if r["intervention"] == iv]
        if f.get("total") != len(sel) or f.get("correct") != sum(r["correct"] for r in sel):
            return f"metrics heldout_{iv} correct/total disagree with the per-example rows"
    for k, v in final.items():
        na = pilot["arm"] == "single_cell" and k == "heldout_coord_shuffle"
        if na != (v is None):
            return f"metrics final.{k}: N/A mismatch"
    evals = [r for r in tele if "eval" in r]
    trains = [r for r in tele if "loss" in r]
    if (len(evals), len(trains)) != (exp["telemetry_eval_rows"], exp["telemetry_train_rows"]) or len(tele) != len(evals) + len(trains):
        return f"telemetry rows eval/train {len(evals)}/{len(trains)} != {exp['telemetry_eval_rows']}/{exp['telemetry_train_rows']}"
    if [r.get("step") for r in evals] != list(range(0, pilot["steps"] + 1, pilot["eval_every"])) or \
            [r.get("step") for r in trains] != [s for s in range(pilot["steps"]) if s % 10 == 0]:
        return "telemetry steps differ from the expected eval / training steps"
    for r in rows:
        if not (all(isinstance(r[k], int) and not isinstance(r[k], bool)
                    for k in ("batch", "episode", "query", "key", "label", "pred"))
                and isinstance(r["correct"], bool) and isinstance(r["episode_hash"], str)
                and isinstance(r["intervention"], str)):
            return "per-example row types differ"
    if schema is not None:                               # frozen field / type / N-A schema
        try:
            got, seen = output_schemas(out, pilot)
        except ValueError as e:
            return f"output schema: {e}"
        for k in ("metrics", "telemetry_eval_row", "telemetry_train_row"):
            if got[k] != schema[k]:
                return f"output schema: {k} differs from the frozen schema"
        if seen != selected_layer_ids(pilot):
            return f"output schema: per-layer keys cover {sorted(seen)} != selected layers"
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
