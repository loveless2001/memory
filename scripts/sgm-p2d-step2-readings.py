"""P2D Step 2 registered readings (M4-SGM.md § P2D Step 2 + clarifications 1-4).

    uv run python scripts/sgm-p2d-step2-readings.py \
        --runs plans/261005-0210-m4-sgm-p0-p2/runs/p2d-diagnostics-v1 \
        --mirror plans/261005-0210-m4-sgm-p0-p2/runs/p2d-diagnostics-v1-volume-mirror \
        --v2-mirror plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v2-volume-mirror \
        --source-sha <P2D memsub source sha> --out plans/261005-0210-m4-sgm-p0-p2/p2d/step2

Inputs are bound before use: every treatment cell must pass the P2D artifact
validator against the registered grid/launch/source/seed, and its local rows
and metrics must equal the volume mirror; v2 baseline checkpoints must match
their manifests (1d62903, source a89284ea…) and are re-evaluated with the
frozen code on the fresh set. Baseline rows, raw geometry, provenance and
input hashes are persisted so the readings can be reproduced from disk.
Decision rules: scripts/sgm-p2d-step2-decision-rules.py (fail closed).
Use --partial for an interrupted grid: only complete seed pairs receive
registered readings; single seeds retain saved descriptive results, and
missing cells are explicitly unevaluable. Invalid complete inputs still abort.

Two-group index (Amendment T1; codex 21198/21242): `--add-group RUNS MIRROR`
adds a launched top-up group. Every group is preflighted against ITS OWN
registered grid/launch (and each manifest's `modal_group`) before any
evaluation; a group's cells must be registered cells of the primary grid with
identical configs. Each registered cell is then indexed to exactly one group
holding it valid and complete: duplicates abort, and so do missing cells
outside --partial. Per-cell group/launch/manifest/input hashes are reported;
top-up cells are never relabelled as primary-group cells.
"""

from collections import defaultdict

import argparse
import hashlib
import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.p2d_address_diagnostics import stencil_relation  # noqa: E402
from memsub.sgm.synthetic_pilot_run import source_tree_sha256  # noqa: E402

FINAL_BASE, DEV_SEED, DEV_BATCHES = 9_300_011, 4242, 4
V2_COMMIT = "1d62903e3e093ee625642b5ef4c86b3b6cae6d2b"
V2_SOURCE = "a89284ea8b6fa58c10c61b7095710ced99bcbe7bf4eaf83f1e2c7486c7d900c5"
CELLS = {"filleroff": (16, 64), "long": (16, 32), "addrsup": (32, 64)}
IVS = ("none", "bank_derange", "coord_shuffle", "read_offset", "query_off")
RUNNER = ROOT / "modal-runners" / "modal-m4-sgm-p2d-diagnostics-grid.py"
REGISTERED_GRID = ROOT / "configs" / "m4_sgm_p2d_grid.json"          # the full 12-cell Step 2 grid
REGISTERED_GRID_SHA256 = "f6e625e34e2c7254aaad818440efaa9f6797b6ae835271e204642acde251e1b7"


def script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RULES = script("sgm-p2d-step2-decision-rules")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rows_of(path: Path) -> list:
    return [json.loads(l) for l in path.read_text().splitlines()]


def load_into(pkg: str, pilot: dict, params: Path):
    from safetensors.torch import load_file
    sp = importlib.import_module(f"{pkg}.sgm.synthetic_pilot")
    pcfg = sp.PilotConfig(**pilot)
    runtime, backend, head = sp.build(pcfg)
    t = load_file(str(params))
    runtime.adapters.load_state_dict({k[9:]: v for k, v in t.items() if k.startswith("adapters.")})
    head.load_state_dict({k[5:]: v for k, v in t.items() if k.startswith("head.")})
    return pcfg, backend, head


def bind_treatment(rid: str, pilot: dict, group: dict, validator, source_sha: str) -> Path:
    """Validate the group's mirror copy against ITS launch, require the manifest
    to name this group, and require local == mirror; return the cell."""
    cell = group["mirror"] / rid
    reason = validator.validate(cell, rid, pilot, group["launch"], source_sha, FINAL_BASE)
    if reason is not None:
        raise SystemExit(f"{group['name']}/{rid}: artifact validation failed: {reason}")
    if json.loads((cell / "run_manifest.json").read_text()).get("modal_group") != group["name"]:
        raise SystemExit(f"{group['name']}/{rid}: manifest modal_group is not this group")
    runs = group["runs"]
    local, mirror = (json.loads((d / "metrics.json").read_text()) for d in (runs / rid, cell))
    if any(local.get(k) != mirror.get(k) for k in ("final", "checkpoints")):
        raise SystemExit(f"{group['name']}/{rid}: local metrics differ from the validated mirror")
    for f in cell.glob("per_example_results*.jsonl"):
        if not (runs / rid / f.name).exists() or sha(runs / rid / f.name) != sha(f):
            raise SystemExit(f"{group['name']}/{rid}: local {f.name} differs from the validated mirror")
    return cell


def bind_baseline(v2_mirror: Path, n: int, seed: int) -> tuple[Path, dict]:
    cell = v2_mirror / f"main-learned-n{n}-s{seed}"
    man = json.loads((cell / "run_manifest.json").read_text())
    ok = (man["git_head"] == V2_COMMIT and man["memsub_source_sha256"] == V2_SOURCE
          and man["trained_parameters_sha256"] == sha(cell / "trained_parameters.safetensors"))
    if not ok:
        raise SystemExit(f"{cell.name}: v2 baseline manifest/checkpoint identity mismatch")
    return cell, man


def baseline_rows(cell: Path, man: dict, seed: int) -> list:
    frozen = script("sgm-p2d-address-telemetry-from-saved-runs").load_frozen_memsub()
    if frozen.FROZEN_SOURCE_SHA256 != V2_SOURCE:
        raise SystemExit("frozen package source hash differs from the v2 source")
    pcfg, backend, head = load_into("memsub_frozen", man["pilot_config"], cell / "trained_parameters.safetensors")
    ev = importlib.import_module("memsub_frozen.sgm.synthetic_pilot_evaluation")
    rows: list = []
    for iv in IVS:
        ev.evaluate(backend, head, pcfg.task_spec(), "learned", "taskhead", split="heldout", batches=16,
                    batch_size=16, seed=FINAL_BASE + seed, intervention=iv, per_example=rows)
    return rows


@torch.no_grad()
def dev_geometry(pilot: dict, params: Path, telemetry: dict | None = None) -> dict:
    """Clarification-2 quantities per layer/head on dev 4242 (observer code;
    bitwise-equivalent to 1d62903 on v2 checkpoints, P2D Step 1)."""
    pcfg, backend, head = load_into("memsub", pilot, params)
    from memsub.sgm.synthetic_binding_task import sample_batch
    from memsub.sgm.synthetic_pilot_evaluation import bank_telemetry, beta_by_token_class, ingest
    spec, gen = pcfg.task_spec(), torch.Generator().manual_seed(DEV_SEED)
    layers, N = backend.runtime.cfg.selected_layers, spec.n_bindings
    acc = {l: {"dist": [], "target": [], "other": [], "spread": []} for l in layers}
    banks, projected, effective = [], [], []
    for _ in range(DEV_BATCHES):
        b = sample_batch(spec, "heldout", pcfg.batch, gen)
        tr: list = []
        st = ingest(backend, b, "learned", tr, pcfg.filler_writes, N).detached()
        banks.append(bank_telemetry(st))
        projected.append(beta_by_token_class(tr, N))
        effective.append(beta_by_token_class(tr, N, effective=True))
        keys = b.source[:, 4:4 + 2 * N:2]
        j = torch.stack([(keys == b.query_keys[:, q:q + 1]).float().argmax(1) for q in range(spec.n_queries)], 1)
        reads = {l: [] for l in layers}
        for q in range(spec.n_queries):
            out = backend.evaluate_query(st, b.query_keys[:, q:q + 1], detach=True, logits=False)
            for l in layers:
                reads[l].append(out["trace"]["read_coords"][l][-1])
        for l in layers:
            r = torch.stack(reads[l], 1)                                                    # [B,Q,H,2]
            wv = torch.stack([tr[4 + 2 * i + 1]["write_coords"][l] for i in range(N)], 1)    # [B,N,H,2]
            _, coup = stencil_relation(r.unsqueeze(2), wv.unsqueeze(1))                     # [B,Q,N,H]
            tgt = torch.gather(coup, 2, j[:, :, None, None].expand(-1, -1, 1, coup.shape[-1])).squeeze(2)
            bound = torch.gather(wv, 1, j[..., None, None].expand(-1, -1, *wv.shape[2:]))
            acc[l]["dist"].append((r - bound).norm(dim=-1).reshape(-1, r.shape[2]))
            acc[l]["target"].append(tgt.reshape(-1, r.shape[2]))
            acc[l]["other"].append(((coup.sum(2) - tgt) / (N - 1)).reshape(-1, r.shape[2]))
            acc[l]["spread"].append(r.std(1, unbiased=True).mean(-1))                        # [B,H]
    if telemetry is not None:
        telemetry.update({"episodes": DEV_BATCHES * pcfg.batch,
                          "bank": {k: (max(b[k] for b in banks) if k == "occupancy_max"
                                        else sum(b[k] for b in banks) / len(banks)) for k in banks[0]},
                          "beta_by_token_class": {k: sum(b[k] for b in projected) / len(projected)
                                                 for k in projected[0]},
                          "effective_beta_by_token_class": {k: sum(b[k] for b in effective) / len(effective)
                                                           for k in effective[0]}})
    return {str(l): {"median_distance": torch.cat(a["dist"]).median(0).values.tolist(),
                     "target_coupling": torch.cat(a["target"]).mean(0).tolist(),
                     "other_coupling": torch.cat(a["other"]).mean(0).tolist(),
                     "read_spread": torch.cat(a["spread"]).mean(0).tolist()} for l, a in acc.items()}


def tensors_equal(a: Path, b: Path) -> dict:
    from safetensors.torch import load_file
    if sha(a) == sha(b):
        return {"file_hash_equal": True, "tensors_equal": True, "label": None}
    ta, tb = load_file(str(a)), load_file(str(b))
    same = ta.keys() == tb.keys() and all(torch.equal(ta[k], tb[k]) for k in ta)
    return {"file_hash_equal": False, "tensors_equal": same,
            "label": None if same else "continuity discrepancy (uninvestigated)"}


def load_group(runs: Path, mirror: Path, validator, source_sha: str) -> dict:
    """One launched group with its OWN registered grid and launch, checked before use."""
    launch = json.loads((runs / "launch_provenance.json").read_text())
    grid = json.loads((runs / "grid.json").read_text())
    registered_grid = ROOT / launch["grid_file"]
    if (sha(registered_grid) != launch["grid_sha256"]
            or json.loads(registered_grid.read_text()) != grid or grid["final_seed_base"] != FINAL_BASE):
        raise SystemExit(f"{runs.name}: registered grid identity/seed mismatch")
    if launch.get("memsub_source_sha256", source_sha) != source_sha:
        raise SystemExit(f"{runs.name}: launch memsub source differs from --source-sha")
    return {"name": runs.name, "runs": runs, "mirror": mirror, "launch": launch,
            "launch_provenance_sha256": sha(runs / "launch_provenance.json"),
            "grid_snapshot_sha256": sha(runs / "grid.json"),
            "registered": validator.registered_cells(grid, RUNNER)}


def registered_universe(primary: dict, validator) -> dict:
    """The full registered grid, bound to its file and hash, never to whichever
    group the caller lists first: the primary group must launch exactly it."""
    if sha(REGISTERED_GRID) != REGISTERED_GRID_SHA256:
        raise SystemExit("registered P2D grid file differs from its registered hash")
    universe = validator.registered_cells(json.loads(REGISTERED_GRID.read_text()), RUNNER)
    if primary["launch"]["grid_sha256"] != REGISTERED_GRID_SHA256 or primary["registered"] != universe:
        raise SystemExit(f"primary group {primary['name']} does not launch the full registered grid "
                         f"({len(primary['registered'])} of {len(universe)} cells)")
    return universe


def input_hashes(cell: Path) -> dict:
    """Every consumed per-cell input, including checkpoint rows/weights (long arm)."""
    files = ["run_manifest.json", "metrics.json", "per_example_results.jsonl", "trained_parameters.safetensors",
             *sorted(f.name for f in cell.glob("per_example_results_step*.jsonl")),
             *sorted(f.name for f in cell.glob("trained_parameters_step*.safetensors"))]
    return {f: sha(cell / f) for f in files}


def select_treatments(universe: dict, groups: list, partial: bool, validator,
                      source_sha: str) -> tuple[dict, dict, dict]:
    """Preflight every group's cells before any evaluation, then index each
    registered cell to exactly one valid group. 'missing' = incomplete, never invalid."""
    for key in ("name", "runs", "mirror"):
        if len({str(g[key]) for g in groups}) != len(groups):
            raise SystemExit(f"duplicate group {key}")
    valid, incomplete = defaultdict(list), defaultdict(list)
    for g in groups:
        for rid, pilot in g["registered"].items():
            if universe.get(rid) != pilot:
                raise SystemExit(f"{g['name']}/{rid}: not a registered cell with its registered config")
            reason = validator.validate(g["mirror"] / rid, rid, pilot, g["launch"], source_sha, FINAL_BASE)
            if reason is None:
                valid[rid].append((g, bind_treatment(rid, pilot, g, validator, source_sha)))
            elif reason.startswith("missing ["):
                incomplete[rid].append({"group": g["name"], "reason": reason})
            else:
                raise SystemExit(f"{g['name']}/{rid}: artifact validation failed: {reason}")
    available, coverage, index = {}, {}, {}
    for rid in universe:
        found = valid.get(rid, [])
        if len(found) > 1:
            raise SystemExit(f"{rid}: valid in several groups {[g['name'] for g, _c in found]}")
        if not found:
            if not partial:
                raise SystemExit(f"{rid}: artifact validation failed: no group holds a valid complete cell")
            coverage[rid] = {"status": "incomplete", "group": None, "incomplete_in": incomplete.get(rid, [])}
            continue
        g, cell = found[0]
        available[rid] = cell
        coverage[rid] = {"status": "valid_complete", "group": g["name"], "incomplete_in": incomplete.get(rid, [])}
        man = json.loads((cell / "run_manifest.json").read_text())
        index[rid] = {"group": g["name"], "runs": str(g["runs"]), "mirror": str(g["mirror"]),
                      "launch_git_head": g["launch"]["git_head"], "launch_grid_sha256": g["launch"]["grid_sha256"],
                      "launch_provenance_sha256": g["launch_provenance_sha256"],
                      "manifest_modal_group": man["modal_group"], "manifest_git_head": man["git_head"],
                      "run_manifest_sha256": sha(cell / "run_manifest.json"), "input_sha256": input_hashes(cell)}
    return available, coverage, index


def summarize_cell(tag: str, seeds: dict) -> dict:
    """Never feed empty or single-seed coverage into the registered pair rules."""
    if not set(seeds) <= {"0", "1"}:
        raise SystemExit("unexpected seed coverage")
    if set(seeds) != {"0", "1"}:
        return {"evaluation_status": "descriptive_single_seed" if seeds else "unevaluable",
                "reproducible_gain_vs_v2": None, "alignment_both_seeds": None,
                "memory_use_both_seeds": None,
                "reading": "descriptive only: incomplete seed pair" if seeds
                           else "unevaluable: no completed seed pair"}
    gain = RULES.reproducible({k: v["vs_v2"] for k, v in seeds.items()})
    align = all(v["alignment"]["pass"] for v in seeds.values())
    mem = all(v["memory_use"]["pass"] for v in seeds.values())
    result = {"evaluation_status": "paired", "reproducible_gain_vs_v2": gain,
              "alignment_both_seeds": align, "memory_use_both_seeds": mem}
    if tag == "addrsup":
        result["reading"] = RULES.addrsup_reading(gain, align, mem)
    elif tag == "filleroff":
        result["reading"] = ("supports harm from tail-filler writes for this recipe" if gain
                             else "no registered reproducible filler-off gain")
    else:
        result["reading"] = RULES.long_reading(
            RULES.reproducible({k: v["vs_own_1500"] for k, v in seeds.items()}), gain)
    return result


def main():
    ap = argparse.ArgumentParser()
    for a in ("--runs", "--mirror", "--v2-mirror", "--out"):
        ap.add_argument(a, type=Path, required=True)
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--partial", action="store_true", help="read only complete seed pairs in an interrupted grid")
    ap.add_argument("--add-group", nargs=2, type=Path, action="append", default=[], metavar=("RUNS", "MIRROR"),
                    help="a launched top-up group, validated against its own grid/launch")
    args = ap.parse_args()
    torch.set_num_threads(4)
    validator = script("sgm-recover-and-validate-grid-artifacts")
    if source_tree_sha256(ROOT / "memsub") != args.source_sha:
        raise SystemExit("analysis runtime differs from the launch source")
    groups = [load_group(r, m, validator, args.source_sha) for r, m in [(args.runs, args.mirror), *args.add_group]]
    launch, registered = groups[0]["launch"], registered_universe(groups[0], validator)
    available, coverage, index = select_treatments(registered, groups, args.partial, validator, args.source_sha)
    pairs = {(tag, n) for tag, ns in CELLS.items() for n in ns
             if all(f"{tag}-learned-n{n}-s{s}" in available for s in (0, 1))}
    args.out.mkdir(parents=True, exist_ok=False)
    head_rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    report = {"analysis": {"git_head": head_rev, "memsub_source_sha256": source_tree_sha256(ROOT / "memsub"),
                           "readings_sha256": sha(Path(__file__)),
                           "rules_sha256": sha(ROOT / "scripts" / "sgm-p2d-step2-decision-rules.py")},
              "final_seed_base": FINAL_BASE, "dev_seed": DEV_SEED, "launch": launch,
              "grid_snapshot_sha256": sha(args.runs / "grid.json"),
              "groups": {g["name"]: {"runs": str(g["runs"]), "mirror": str(g["mirror"]), "launch": g["launch"],
                                     "launch_provenance_sha256": g["launch_provenance_sha256"],
                                     "grid_snapshot_sha256": g["grid_snapshot_sha256"],
                                     "cells": sorted(g["registered"])} for g in groups},
              "index": index,
              "report_status": "partial" if len(available) != len(registered) else "complete",
              "partial_mode": args.partial, "coverage": coverage,
              "limits": ["No R3, pretrained-model or scaling claim.",
                         "Missing seed pairs are unevaluable; single seeds are descriptive only.",
                         "The original incomplete v1 artifacts are preserved unchanged; the authorized top-up "
                         "retrained the missing cells in a separate group with its own provenance.",
                         "Each cell is read from the one group indexed for it (see `index`); top-up cells "
                         "keep their own group/manifest and are not relabelled as primary-group cells."],
              "baselines": {}, "arms": {}}
    base_rows, base_geo = {}, {}
    for (n, seed) in sorted({(n, s) for _tag, n in pairs for s in (0, 1)}):
        cell, man = bind_baseline(args.v2_mirror, n, seed)
        print("baseline", f"N{n}-s{seed}", "fresh evaluation", flush=True)
        rows = baseline_rows(cell, man, seed)
        path = args.out / f"baseline-v2-learned-n{n}-s{seed}-fresh-rows.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        base_rows[(n, seed)] = rows
        diagnostics = {}
        base_geo[(n, seed)] = dev_geometry(man["pilot_config"], cell / "trained_parameters.safetensors", diagnostics)
        report["baselines"][f"N{n}-s{seed}"] = {
            "frozen_commit": V2_COMMIT, "frozen_source_sha256": V2_SOURCE,
            "trained_parameters_sha256": man["trained_parameters_sha256"],
            "final_eval_seed": FINAL_BASE + seed, "rows_file": path.name, "rows_sha256": sha(path),
            "geometry": base_geo[(n, seed)], "dev_telemetry": diagnostics}
    for tag, ns in CELLS.items():
        arm = report["arms"][tag] = {}
        for n in ns:
            cell = arm[f"N{n}"] = {"seeds": {}}
            for seed in (0, 1):
                rid = f"{tag}-learned-n{n}-s{seed}"
                if rid not in available:
                    continue
                mc = available[rid]
                treat = rows_of(mc / "per_example_results.jsonl")
                r = {"run_id": rid, "group": index[rid]["group"],
                     "rows_sha256": sha(mc / "per_example_results.jsonl"),
                     "trained_parameters_sha256": sha(mc / "trained_parameters.safetensors"),
                     "run_manifest_sha256": sha(mc / "run_manifest.json"),
                     "metrics_sha256": sha(mc / "metrics.json"),
                     "saved_final": json.loads((mc / "metrics.json").read_text())["final"]}
                if (tag, n) not in pairs:
                    r["evaluation_status"] = "descriptive_single_seed"
                    cell["seeds"][str(seed)] = r
                    continue
                print("treatment", rid, "dev telemetry", flush=True)
                diagnostics = {}
                geo = dev_geometry(registered[rid], mc / "trained_parameters.safetensors", diagnostics)
                r.update({"geometry": geo, "dev_telemetry": diagnostics,
                          "vs_v2": RULES.paired(treat, base_rows[(n, seed)]),
                          "memory_use": RULES.memory_use(treat),
                          "alignment": RULES.alignment_ok(geo, base_geo[(n, seed)]),
                          "final_accuracy": sum(RULES.episode_scores(treat, "none").values()) / RULES.N_EPISODES,
                          "baseline_accuracy": sum(RULES.episode_scores(base_rows[(n, seed)], "none").values()) / RULES.N_EPISODES})
                if tag == "long":
                    r["vs_own_1500"] = RULES.paired(treat, rows_of(mc / "per_example_results_step1500.jsonl"))
                    r["step1500_rows_sha256"] = sha(mc / "per_example_results_step1500.jsonl")
                    r["step1500_parameters_sha256"] = sha(mc / "trained_parameters_step1500.safetensors")
                    r["continuity_1500_vs_v2"] = tensors_equal(
                        mc / "trained_parameters_step1500.safetensors",
                        args.v2_mirror / f"main-learned-n{n}-s{seed}" / "trained_parameters.safetensors")
                cell["seeds"][str(seed)] = r
            cell.update(summarize_cell(tag, cell["seeds"]))
            print(tag, f"N{n}", cell["reading"], flush=True)
    if source_tree_sha256(ROOT / "memsub") != args.source_sha:
        raise SystemExit("analysis runtime changed during evaluation")
    (args.out / "step2-readings.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
