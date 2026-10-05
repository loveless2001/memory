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
"""

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


def bind_treatment(rid: str, pilot: dict, args, launch: dict, validator) -> Path:
    """Validate the mirror copy and require local == mirror; return the cell."""
    cell = args.mirror / rid
    reason = validator.validate(cell, rid, pilot, launch, args.source_sha, FINAL_BASE)
    if reason is not None:
        raise SystemExit(f"{rid}: artifact validation failed: {reason}")
    local, mirror = (json.loads((d / "metrics.json").read_text()) for d in (args.runs / rid, cell))
    if any(local.get(k) != mirror.get(k) for k in ("final", "checkpoints")):
        raise SystemExit(f"{rid}: local metrics differ from the validated mirror")
    for f in cell.glob("per_example_results*.jsonl"):
        if not (args.runs / rid / f.name).exists() or sha(args.runs / rid / f.name) != sha(f):
            raise SystemExit(f"{rid}: local {f.name} differs from the validated mirror")
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


def select_treatments(registered: dict, args, launch: dict, validator) -> tuple[dict, dict]:
    """Preflight all cells before any evaluation; partial means missing, not invalid."""
    available, coverage = {}, {}
    for rid, pilot in registered.items():
        reason = validator.validate(args.mirror / rid, rid, pilot, launch, args.source_sha, FINAL_BASE)
        if reason is not None:
            if not args.partial or not reason.startswith("missing ["):
                raise SystemExit(f"{rid}: artifact validation failed: {reason}")
            coverage[rid] = {"status": "incomplete", "reason": reason}
            continue
        available[rid] = bind_treatment(rid, pilot, args, launch, validator)
        coverage[rid] = {"status": "valid_complete", "reason": None}
    return available, coverage


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
    args = ap.parse_args()
    torch.set_num_threads(4)
    validator = script("sgm-recover-and-validate-grid-artifacts")
    launch = json.loads((args.runs / "launch_provenance.json").read_text())
    grid = json.loads((args.runs / "grid.json").read_text())
    registered_grid = ROOT / launch["grid_file"]
    if (sha(registered_grid) != launch["grid_sha256"]
            or json.loads(registered_grid.read_text()) != grid or grid["final_seed_base"] != FINAL_BASE):
        raise SystemExit("registered grid identity/seed mismatch")
    if source_tree_sha256(ROOT / "memsub") != args.source_sha:
        raise SystemExit("analysis runtime differs from the launch source")
    registered = validator.registered_cells(grid, RUNNER)
    available, coverage = select_treatments(registered, args, launch, validator)
    pairs = {(tag, n) for tag, ns in CELLS.items() for n in ns
             if all(f"{tag}-learned-n{n}-s{s}" in available for s in (0, 1))}
    args.out.mkdir(parents=True, exist_ok=False)
    head_rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    report = {"analysis": {"git_head": head_rev, "memsub_source_sha256": source_tree_sha256(ROOT / "memsub"),
                           "readings_sha256": sha(Path(__file__)),
                           "rules_sha256": sha(ROOT / "scripts" / "sgm-p2d-step2-decision-rules.py")},
              "final_seed_base": FINAL_BASE, "dev_seed": DEV_SEED, "launch": launch,
              "grid_snapshot_sha256": sha(args.runs / "grid.json"),
              "report_status": "partial" if len(available) != len(registered) else "complete",
              "partial_mode": args.partial, "coverage": coverage,
              "limits": ["No R3, pretrained-model or scaling claim.",
                         "Missing seed pairs are unevaluable; single seeds are descriptive only.",
                         "Interrupted cells are preserved without replacement or retraining."],
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
                r = {"run_id": rid, "rows_sha256": sha(mc / "per_example_results.jsonl"),
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
