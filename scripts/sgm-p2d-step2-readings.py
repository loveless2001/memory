"""P2D Step 2 registered readings (M4-SGM.md § P2D Step 2 + clarifications 1-4).

    uv run python scripts/sgm-p2d-step2-readings.py \
        --runs plans/261005-0210-m4-sgm-p0-p2/runs/p2d-diagnostics-v1 \
        --mirror plans/261005-0210-m4-sgm-p0-p2/runs/p2d-diagnostics-v1-volume-mirror \
        --v2-mirror plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v2-volume-mirror \
        --out plans/261005-0210-m4-sgm-p0-p2/p2d/step2-readings.json

Baselines: frozen v2 `learned` checkpoints re-evaluated with the FROZEN code
(1d62903) on the same fresh final set (9_300_011 + seed). Everything fails
closed: misaligned episodes, missing cells or wrong counts abort.
"""

import argparse
import hashlib
import importlib
import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.p2d_address_diagnostics import stencil_relation  # noqa: E402

FINAL_BASE, DEV_SEED, DEV_BATCHES, CEILING = 9_300_011, 4242, 4, 0.04
CELLS = {"filleroff": (16, 64), "long": (16, 32), "addrsup": (32, 64)}
IVS = ("none", "bank_derange", "coord_shuffle", "read_offset", "query_off")


def _obs():
    spec = importlib.util.spec_from_file_location("p2d_obs", ROOT / "scripts" / "sgm-p2d-address-telemetry-from-saved-runs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_into(pkg: str, pilot: dict, params: Path):
    from safetensors.torch import load_file
    sp = importlib.import_module(f"{pkg}.sgm.synthetic_pilot")
    pcfg = sp.PilotConfig(**pilot)
    runtime, backend, head = sp.build(pcfg)
    t = load_file(str(params))
    runtime.adapters.load_state_dict({k[9:]: v for k, v in t.items() if k.startswith("adapters.")})
    head.load_state_dict({k[5:]: v for k, v in t.items() if k.startswith("head.")})
    return pcfg, backend, head


def episode_scores(rows: list, iv: str) -> dict:
    eps = defaultdict(dict)
    for r in rows:
        if r["intervention"] == iv:
            if r["query"] in eps[(r["batch"], r["episode"], r["episode_hash"])]:
                raise SystemExit("duplicate query row")
            eps[(r["batch"], r["episode"], r["episode_hash"])][r["query"]] = r["correct"]
    if len(eps) != 256 or any(set(v) != {0, 1, 2, 3} for v in eps.values()):
        raise SystemExit(f"{iv}: incomplete final rows ({len(eps)} episodes)")
    return {k: sum(v.values()) / 4 for k, v in eps.items()}


def paired(a_rows, b_rows, iv_a="none", iv_b="none") -> dict:
    a, b = episode_scores(a_rows, iv_a), episode_scores(b_rows, iv_b)
    if set(a) != set(b):
        raise SystemExit("paired runs do not share episode hashes")
    d = torch.tensor([a[k] - b[k] for k in a], dtype=torch.float64)
    hw = float(1.96 * d.std() / math.sqrt(len(d)))
    return {"diff": float(d.mean()), "lo": float(d.mean()) - hw, "hi": float(d.mean()) + hw, "n": len(d)}


def baseline_rows(v2_mirror: Path, n: int, seed: int) -> list:
    _obs().load_frozen_memsub()
    cell = v2_mirror / f"main-learned-n{n}-s{seed}"
    pilot = json.loads((cell / "run_manifest.json").read_text())["pilot_config"]
    pcfg, backend, head = load_into("memsub_frozen", pilot, cell / "trained_parameters.safetensors")
    ev = importlib.import_module("memsub_frozen.sgm.synthetic_pilot_evaluation")
    rows: list = []
    for iv in IVS:
        ev.evaluate(backend, head, pcfg.task_spec(), "learned", "taskhead", split="heldout", batches=16,
                    batch_size=16, seed=FINAL_BASE + seed, intervention=iv, per_example=rows)
    return rows


@torch.no_grad()
def dev_geometry(pilot: dict, params: Path) -> dict:
    """Clarification-2 quantities per layer/head on dev 4242, computed with the
    observer code (the frozen 1d62903 code has no write-coordinate trace; the
    observer is bitwise-equivalent on v2 checkpoints, P2D Step 1)."""
    pkg = "memsub"
    pcfg, backend, head = load_into(pkg, pilot, params)
    task = importlib.import_module(f"{pkg}.sgm.synthetic_binding_task")
    ev = importlib.import_module(f"{pkg}.sgm.synthetic_pilot_evaluation")
    spec, gen = pcfg.task_spec(), torch.Generator().manual_seed(DEV_SEED)
    layers, N = backend.runtime.cfg.selected_layers, spec.n_bindings
    acc = {l: defaultdict(list) for l in layers}
    for _ in range(DEV_BATCHES):
        b = task.sample_batch(spec, "heldout", pcfg.batch, gen)
        tr: list = []
        st = ev.ingest(backend, b, "learned", tr, pcfg.filler_writes, N).detached()
        keys = b.source[:, 4:4 + 2 * N:2]
        j = torch.stack([(keys == b.query_keys[:, q:q + 1]).float().argmax(1) for q in range(spec.n_queries)], 1)
        reads = {l: [] for l in layers}
        for q in range(spec.n_queries):
            out = backend.evaluate_query(st, b.query_keys[:, q:q + 1], detach=True)
            for l in layers:
                reads[l].append(out["trace"]["read_coords"][l][-1])
        for l in layers:
            r = torch.stack(reads[l], 1)                                            # [B,Q,H,2]
            wv = torch.stack([tr[4 + 2 * i + 1]["write_coords"][l] for i in range(N)], 1)  # [B,N,H,2]
            _, coup = stencil_relation(r.unsqueeze(2), wv.unsqueeze(1))             # [B,Q,N,H]
            tgt = torch.gather(coup, 2, j[:, :, None, None].expand(-1, -1, 1, coup.shape[-1])).squeeze(2)
            bound = torch.gather(wv, 1, j[..., None, None].expand(-1, -1, *wv.shape[2:]))
            acc[l]["dist"].append((r - bound).norm(dim=-1).reshape(-1, r.shape[2]))
            acc[l]["target"].append(tgt.reshape(-1, r.shape[2]))
            acc[l]["other"].append(((coup.sum(2) - tgt) / (N - 1)).reshape(-1, r.shape[2]))
            acc[l]["spread"].append(r.std(1, unbiased=True).mean(-1))                # [B,H]
    return {str(l): {"median_distance": torch.cat(a["dist"]).median(0).values.tolist(),
                     "target_coupling": torch.cat(a["target"]).mean(0).tolist(),
                     "other_coupling": torch.cat(a["other"]).mean(0).tolist(),
                     "read_spread": torch.cat(a["spread"]).mean(0).tolist()} for l, a in acc.items()}


def alignment_ok(treat: dict, base: dict) -> dict:
    """Clarification 2: per layer, some head satisfies (a)-(d)."""
    per_layer = {}
    for l, g in treat.items():
        heads = [(g["median_distance"][h] < base[l]["median_distance"][h] and g["target_coupling"][h] > 0
                  and g["target_coupling"][h] >= 2 * g["other_coupling"][h] and g["read_spread"][h] >= 1)
                 for h in range(len(g["median_distance"]))]
        per_layer[l] = {"heads_pass": heads, "pass": any(heads)}
    return {"layers": per_layer, "pass": all(v["pass"] for v in per_layer.values())}


def rows_of(path: Path) -> list:
    return [json.loads(l) for l in path.read_text().splitlines()]


def tensors_equal(a: Path, b: Path) -> dict:
    from safetensors.torch import load_file
    ha, hb = (hashlib.sha256(p.read_bytes()).hexdigest() for p in (a, b))
    if ha == hb:
        return {"file_hash_equal": True, "tensors_equal": True}
    ta, tb = load_file(str(a)), load_file(str(b))
    same = ta.keys() == tb.keys() and all(torch.equal(ta[k], tb[k]) for k in ta)
    return {"file_hash_equal": False, "tensors_equal": same,
            "label": None if same else "continuity discrepancy (uninvestigated)"}


def reproducible(per_seed: dict) -> bool:
    return all(r["diff"] >= 0.05 and r["lo"] > 0 for r in per_seed.values())


def memory_use(rows: list) -> dict:
    derange = episode_scores(rows, "bank_derange")
    acc = sum(derange.values()) / len(derange)
    p_der, p_off = paired(rows, rows, "none", "bank_derange"), paired(rows, rows, "none", "read_offset")
    return {"derange_accuracy": acc, "none_minus_derange": p_der, "none_minus_read_offset": p_off,
            "pass": acc <= CEILING and p_der["lo"] > 0 and p_off["lo"] > 0}


def main():
    ap = argparse.ArgumentParser()
    for a in ("--runs", "--mirror", "--v2-mirror", "--out"):
        ap.add_argument(a, type=Path, required=True)
    args = ap.parse_args()
    torch.set_num_threads(4)
    base_cache, report = {}, {"final_seed_base": FINAL_BASE, "dev_seed": DEV_SEED, "arms": {}}
    for tag, ns in CELLS.items():
        arm = report["arms"][tag] = {}
        for n in ns:
            cell = arm[f"N{n}"] = {"seeds": {}}
            for seed in (0, 1):
                rid = f"{tag}-learned-n{n}-s{seed}"
                if (n, seed) not in base_cache:
                    base_cache[(n, seed)] = baseline_rows(args.v2_mirror, n, seed)
                base = base_cache[(n, seed)]
                treat = rows_of(args.runs / rid / "per_example_results.jsonl")
                pilot = json.loads((args.mirror / rid / "run_manifest.json").read_text())["pilot_config"]
                v2cell = args.v2_mirror / f"main-learned-n{n}-s{seed}"
                v2pilot = json.loads((v2cell / "run_manifest.json").read_text())["pilot_config"]
                r = {"vs_v2": paired(treat, base), "memory_use": memory_use(treat),
                     "alignment": alignment_ok(dev_geometry(pilot, args.mirror / rid / "trained_parameters.safetensors"),
                                               dev_geometry(v2pilot, v2cell / "trained_parameters.safetensors"))}
                if tag == "long":
                    r["vs_own_1500"] = paired(treat, rows_of(args.runs / rid / "per_example_results_step1500.jsonl"))
                    r["continuity_1500_vs_v2"] = tensors_equal(args.mirror / rid / "trained_parameters_step1500.safetensors",
                                                               v2cell / "trained_parameters.safetensors")
                cell["seeds"][str(seed)] = r
                print(rid, {k: (round(v["diff"], 3) if isinstance(v, dict) and "diff" in v else None)
                            for k, v in r.items()})
            sd = cell["seeds"]
            gain = reproducible({k: v["vs_v2"] for k, v in sd.items()})
            align = all(v["alignment"]["pass"] for v in sd.values())
            mem = all(v["memory_use"]["pass"] for v in sd.values())
            if tag == "addrsup":
                cell["reading"] = ("SUPPORTS usefulness of this supervised routing-training recipe"
                                   if gain and align and mem else
                                   "alignment improved, accuracy did not: alignment alone insufficient"
                                   if align and not gain else
                                   "probe did not establish the intended alignment; cause unresolved"
                                   if not align else "gain without registered memory-use evidence")
            elif tag == "filleroff":
                cell["reading"] = ("supports harm from tail-filler writes for this recipe" if gain
                                   else "no reproducible filler-off gain")
            else:
                own = reproducible({k: v["vs_own_1500"] for k, v in sd.items()})
                cell["reading"] = {"4500_vs_own_1500": "budget effect" if own else "no reproducible gain",
                                   "4500_vs_v2": "gain" if gain else "no reproducible gain"}
            cell.update({"reproducible_gain_vs_v2": gain, "alignment_both_seeds": align,
                         "memory_use_both_seeds": mem})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
