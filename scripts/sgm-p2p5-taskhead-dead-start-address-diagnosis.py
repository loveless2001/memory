"""P2.5 taskhead dead-start address diagnosis (descriptive, $0, local; #gravity 21931-21940).

Question: on the frozen Qwen3-0.6B backbone the readout probe's taskhead stayed
at ln(64) loss for all 1500 updates and its query reads put ~all stencil weight
on absent cells, while the same recipe learned on the tiny random backbone (P2C
N32). For each index entry (saved parameters, or the deterministic initial
reconstruction) this measures, on the DEV population only (heldout split, seed
4242, 4 x 16 episodes, eval filler 40; the reserved 9_600_011+s population is
never touched):

  M1 alignment  SPATIAL only: query read stencil vs the bound key's value-step
                write stencil, via the frozen P2D `episode_geometry` (unchanged).
                Content q.k, beta and stored residuals also govern read gain.
  M2 absence    per head, the stencil weight of each query read on cells ABSENT
                from the bank (never allocated), and the exact fraction of
                reads whose every positive-weight stencil cell is absent. An
                all-absent read is exactly 0, so that read passes no gradient to
                its own read address or to any write of that layer; the head
                bias and other layers' read paths are unaffected. Absent mass is
                not content: allocated cells can hold ~0 values.
  M3 geometry   per head, read / value-write coordinate centroids and spreads
                (cells), the centroid offset, and mean pairwise cosine of query
                q vectors, of value-step k vectors, and cos(q, bound k).
  M4            dev-gradient reach at INITIALIZATION (not the historical first
                training update): per-group gradient norms of the task loss on
                the first 2 dev episodes; None = no gradient reached the group;
                no optimizer step.

Descriptive only: no thresholds and no decision role. ONE invocation runs every
entry of a hash-bound input index in order under one outer bound; any setup or
entry error writes ERROR.txt and stops, keeping partial output:
  timeout --signal=KILL 3600 .venv-gpu/bin/python scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py \
      --index INPUTS_INDEX.json --out NEW_OUT_DIR
"""

import argparse
import gc
import hashlib
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.p2d_address_diagnostics import episode_geometry  # noqa: E402
from memsub.sgm.synthetic_binding_task import EpisodeBatch, sample_batch  # noqa: E402
from memsub.sgm.synthetic_pilot import PilotConfig, _group_norms, build  # noqa: E402
from memsub.sgm.synthetic_pilot_evaluation import bank_telemetry, ingest, query_logits  # noqa: E402
from memsub.sgm.synthetic_pilot_run import source_tree_sha256  # noqa: E402

DEV_SEED, DEV_BATCHES, DEV_BATCH_SIZE, SINKS = 4242, 4, 16, 4   # = training dev-eval population
M4_EPISODES = 2                                                  # backward fits the 6 GB laptop GPU
ENV_KEYS = ("CUDA_VISIBLE_DEVICES", "HF_HOME", "M4_SGM_QWEN3_0P6B_DIR", "PYTHONHASHSEED", "OMP_NUM_THREADS")


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_params(runtime, head, e: dict, pilot: dict) -> dict:
    """'init' keeps the seeded build; .pt = resume checkpoint (its PilotConfig and step must equal the
    manifest's and the index's); .safetensors = final parameters. Strict state-dict loads."""
    if e["params"] == "init":
        return {"kind": "init", "label": "deterministic reconstruction, not a saved observation"}
    p = Path(e["params"])
    if p.suffix == ".pt":
        c = torch.load(p, map_location="cpu", weights_only=False)
        if c["step"] != e["expected_step"]:
            raise ValueError(f"checkpoint step {c['step']} != index {e['expected_step']}")
        if {**c["pilot_config"], "device": pilot["device"]} != pilot:
            raise ValueError("checkpoint PilotConfig differs from the manifest's")
        ad, hd, info = c["adapters"], c["head"], {"kind": "checkpoint", "step": c["step"]}
    else:
        from safetensors.torch import load_file
        t = load_file(str(p))
        ad = {k[9:]: v for k, v in t.items() if k.startswith("adapters.")}
        hd = {k[5:]: v for k, v in t.items() if k.startswith("head.")}
        info = {"kind": "final", "step": pilot["steps"]}
    runtime.adapters.load_state_dict(ad)
    head.load_state_dict(hd)
    return info


def training_dev_eval_check(e: dict, step: int, report: dict) -> dict:
    """Fail-closed: the run's own logged dev eval at this step (same population: heldout, seed 4242,
    4 x 16) must exist, be finite and reproduce our query absent-read weight and bank occupancy."""
    rows = [json.loads(line) for line in Path(e["telemetry"]).read_text().splitlines() if line.strip()]
    evs = [r["eval"] for r in rows if r.get("step") == step and isinstance(r.get("eval"), dict)]
    if len(evs) != 1:
        raise ValueError(f"expected exactly one logged dev eval at step {step}, found {len(evs)}")
    ev = evs[0]
    logged = [ev.get(k) for k in ("query_empty_read_weight", "occupancy_mean", "accuracy")]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in logged):
        raise ValueError(f"malformed or non-finite logged dev eval at step {step}: {logged}")
    ours = [v for lay in report["per_layer_head"].values() for v in lay["query_read_absent_weight_mean"]]
    d_empty = abs(sum(ours) / len(ours) - logged[0])
    d_occ = abs(report["bank"]["occupancy_mean"] - logged[1])
    if not (d_empty <= 1e-4 and d_occ <= 1e-4):
        raise ValueError(f"dev-eval mismatch at step {step}: absent weight {d_empty}, occupancy {d_occ}")
    return {"status": "reproduced", "step": step, "abs_diff_absent_read_weight": d_empty,
            "abs_diff_occupancy_mean": d_occ, "logged_training_dev_accuracy_not_recomputed": logged[2]}


def read_absence(e) -> tuple[torch.Tensor, torch.Tensor]:
    """One EmptyReadWeight record (weights [B, H, 9], present flags) -> per (B, H): stencil weight on
    absent cells, and EXACT 'every positive-weight stencil cell is absent' (no tolerance)."""
    absent = ~torch.tensor(e.present, dtype=torch.bool, device=e.weights.device).view(e.weights.shape)
    return (e.weights * absent).sum(-1).cpu(), (absent | ~(e.weights > 0)).all(-1).cpu()


def mean_pairwise_cos(x: torch.Tensor) -> list[float]:
    """x [n, H, d] unit vectors -> per head mean cosine over distinct pairs."""
    g = torch.einsum("ihd,jhd->hij", x, x)
    n = x.shape[0]
    return ((g.sum((1, 2)) - g.diagonal(dim1=1, dim2=2).sum(-1)) / (n * (n - 1))).tolist()


@torch.no_grad()
def diagnose(backend, pcfg) -> dict:
    spec, gen = pcfg.task_spec(), torch.Generator().manual_seed(DEV_SEED)
    layers = backend.runtime.cfg.selected_layers
    n_bind = SINKS + 2 * spec.n_bindings
    val_pos = [SINKS + 2 * j + 1 for j in range(spec.n_bindings)]
    fill_pos = list(range(n_bind, spec.source_len()))
    geo = {l: [] for l in layers}
    acc = {l: {k: [] for k in ("absent", "all_absent", "rc", "wc", "q", "k", "qk")} for l in layers}
    occ = []
    for _ in range(DEV_BATCHES):
        b = sample_batch(spec, "heldout", DEV_BATCH_SIZE, gen)
        traces: list = []
        post = ingest(backend, b, pcfg.arm, traces, pcfg.filler_writes, spec.n_bindings)
        occ.append(bank_telemetry(post))
        keys = b.source[:, SINKS:n_bind:2]
        q_bind = torch.stack([(keys == b.query_keys[:, q:q + 1]).float().argmax(1)
                              for q in range(spec.n_queries)], 1)                       # [B, Q]
        reads = {l: [] for l in layers}
        qs = {l: [] for l in layers}
        for q in range(spec.n_queries):
            oracle = b.oracle_query[:, q:q + 1] if pcfg.arm == "oracle" else None    # = query_logits wiring
            out = backend.evaluate_query(post, b.query_keys[:, q:q + 1], oracle_addresses=oracle,
                                         detach=True, logits=False)
            tr = out["trace"]
            if len(tr["empty_read_weight"]) != len(layers):
                raise ValueError("expected one read record per SGM layer for a one-token query")
            for i, l in enumerate(layers):
                mass, all_absent = read_absence(tr["empty_read_weight"][i])
                acc[l]["absent"].append(mass)
                acc[l]["all_absent"].append(all_absent)
                reads[l].append(tr["read_coords"][l][-1].cpu())
                qs[l].append(tr["read_q"][l][-1].cpu())
        for l in layers:
            w = torch.stack([traces[t]["write_coords"][l].cpu() for t in range(len(traces))], 1)   # [B,T,H,2]
            k = torch.stack([traces[t]["write_k"][l].cpu() for t in val_pos], 1)                   # [B,N,H,dk]
            rc, qv = torch.stack(reads[l], 1), torch.stack(qs[l], 1)                               # [B,Q,H,*]
            geo[l].append(episode_geometry(w, val_pos, fill_pos, rc, q_bind))
            kb = torch.gather(k, 1, q_bind[..., None, None].expand(-1, -1, *k.shape[2:]))         # [B,Q,H,dk]
            acc[l]["rc"].append(rc.reshape(-1, *rc.shape[2:]))
            acc[l]["wc"].append(w[:, val_pos].reshape(-1, *w.shape[2:]))
            acc[l]["q"].append(qv.reshape(-1, *qv.shape[2:]))
            acc[l]["k"].append(k.reshape(-1, *k.shape[2:]))
            acc[l]["qk"].append((qv * kb).sum(-1).reshape(-1, qv.shape[2]))
    per_layer = {}
    for l in layers:
        g = {k: [sum(x[k][h] for x in geo[l]) / len(geo[l]) for h in range(len(geo[l][0][k]))]
             for k in geo[l][0] if not k.startswith("_")}             # equal-size batches: pooled means
        g["align_distance_median_pooled"] = torch.cat([x["_align_distances"] for x in geo[l]]).median(0).values.tolist()
        rc, wc = torch.cat(acc[l]["rc"]), torch.cat(acc[l]["wc"])        # [n, H, 2]
        per_layer[str(l)] = {
            **g,
            "query_read_absent_weight_mean": torch.cat(acc[l]["absent"]).mean(0).tolist(),
            "query_read_all_positive_cells_absent_fraction": torch.cat(acc[l]["all_absent"]).float().mean(0).tolist(),
            "read_centroid": rc.mean(0).tolist(), "value_write_centroid": wc.mean(0).tolist(),
            "read_spread_cells": rc.std(0).norm(dim=-1).tolist(),
            "value_write_spread_cells": wc.std(0).norm(dim=-1).tolist(),
            "centroid_offset_cells": (rc.mean(0) - wc.mean(0)).norm(dim=-1).tolist(),
            "query_q_mean_pairwise_cos": mean_pairwise_cos(torch.cat(acc[l]["q"])),
            "value_k_mean_pairwise_cos": mean_pairwise_cos(torch.cat(acc[l]["k"])),
            "cos_q_bound_k_mean": torch.cat(acc[l]["qk"]).mean(0).tolist(),
        }
    occ_mean = {k: sum(o[k] for o in occ) / len(occ) for k in ("occupancy_mean", "effective_cells_mean")}
    return {"dev_episodes": DEV_BATCHES * DEV_BATCH_SIZE, "dev_queries": DEV_BATCHES * DEV_BATCH_SIZE * spec.n_queries,
            "bank": occ_mean, "per_layer_head": per_layer}


def grad_reach_at_init(runtime, backend, head, pcfg) -> dict:
    """M4: fresh differentiable ingestion of the first M4_EPISODES dev episodes, queries with
    detach=False (query_logits wiring, oracle included), task loss backward, per-group gradient norms
    (None = no gradient reached the group). Gradients are cleared; no optimizer exists or steps."""
    spec = pcfg.task_spec()
    b = sample_batch(spec, "heldout", DEV_BATCH_SIZE, torch.Generator().manual_seed(DEV_SEED))
    b = EpisodeBatch(*(t[:M4_EPISODES] for t in (b.source, b.query_keys, b.labels, b.oracle_source, b.oracle_query)))
    state = ingest(backend, b, pcfg.arm, None, pcfg.filler_writes, spec.n_bindings)
    loss = 0.0
    for q in range(spec.n_queries):
        logits, _ = query_logits(backend, head, state, b, q, pcfg.arm, pcfg.readout, detach=False)
        loss = loss + torch.nn.functional.cross_entropy(logits, b.labels[:, q].to(logits.device))
    loss = loss / spec.n_queries
    loss.backward()
    heads = [p.grad for p in head.parameters() if p.grad is not None]
    out = {"episodes": M4_EPISODES, "loss": float(loss), "grad_norm": _group_norms(runtime),
           "head_grad_norm": sum(float(g.pow(2).sum()) for g in heads) ** 0.5 if heads else None}
    for prm in list(runtime.adapters.parameters()) + list(head.parameters()):
        prm.grad = None
    return out


def check_runtime(runtime, e: dict) -> None:
    """Intended device and numerics, enforced before any measurement."""
    if runtime.device.type != e["device"]:
        raise ValueError(f"runtime on {runtime.device}, index wants {e['device']}")
    if any(p.dtype != torch.float32 for p in runtime.parameters()):
        raise ValueError("non-fp32 parameters")
    if e["device"] == "cuda" and (torch.backends.cuda.matmul.allow_tf32 or torch.backends.cudnn.allow_tf32):
        raise ValueError("TF32 enabled")


def run_entry(e: dict) -> dict:
    """One index entry: kind 'geometry' (M1-M3 on the dev population) or 'grad_at_init' (M4)."""
    t0 = time.time()
    for key, path in (("manifest_sha256", "manifest"), ("params_sha256", "params"), ("telemetry_sha256", "telemetry")):
        if key in e and sha(Path(e[path])) != e[key]:
            raise ValueError(f"{e['name']}: {path} sha mismatch")
    if e["kind"] not in ("geometry", "grad_at_init") or (e["params"] != "init") != ("params_sha256" in e):
        raise ValueError(f"{e['name']}: malformed index entry")
    pilot = {**json.loads(Path(e["manifest"]).read_text())["pilot_config"], "device": e["device"]}
    pcfg = PilotConfig(**pilot)
    runtime, backend, head = build(pcfg)
    check_runtime(runtime, e)
    params = load_params(runtime, head, e, pilot)
    rep = {"name": e["name"], "kind": e["kind"], "entry": e, "params_info": params, "pilot_config": pilot}
    if e["kind"] == "grad_at_init":
        if params["kind"] != "init":
            raise ValueError(f"{e['name']}: grad_at_init needs init parameters")
        rep["grad_reach_at_init"] = grad_reach_at_init(runtime, backend, head, pcfg)
    else:
        rep.update(diagnose(backend, pcfg))
        rep["training_dev_eval_check"] = training_dev_eval_check(e, params.get("step", 0), rep)
    rep["wall_seconds"] = time.time() - t0
    del runtime, backend, head
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return rep


def check_run_identity(index: dict) -> dict:
    """Bound run-level identity, enforced before any model work."""
    want = index["run"]
    got = {"memsub_source_sha256": source_tree_sha256(ROOT / "memsub"), "torch": torch.__version__}
    import transformers
    got["transformers"] = transformers.__version__
    for k, v in got.items():
        if v != want[k]:
            raise ValueError(f"run identity {k}: {v} != bound {want[k]}")
    if any(e["device"] == "cuda" for e in index["entries"]) and not torch.cuda.is_available():
        raise ValueError("an entry needs cuda but none is available (no CPU fallback)")
    from memsub.sgm.pinned_pretrained_qwen3_backbone import QWEN3_0P6B_BASE, snapshot_dir, verify_files
    got["qwen_revision"] = QWEN3_0P6B_BASE["revision"]
    got["qwen_files_sha256"] = verify_files(snapshot_dir())       # raises on any mismatch
    got["cuda_device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)                       # write-once output directory
    run = {"format": "p2p5-taskhead-dead-start-address-diagnosis-v1",
           "label": "DESCRIPTIVE (dev population; no decision role)", "argv": sys.argv, "pid": os.getpid(),
           "env": {k: os.environ.get(k) for k in ENV_KEYS}, "index": str(a.index), "index_sha256": sha(a.index),
           "script_sha256": sha(Path(__file__)), "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "done": []}
    (a.out / "run.json").write_text(json.dumps(run, indent=1))
    stage = "setup"
    try:
        index = json.loads(a.index.read_text())
        run["identity"] = check_run_identity(index)
        (a.out / "run.json").write_text(json.dumps(run, indent=1))
        for e in index["entries"]:                                   # first error stops; partial output kept
            stage = e["name"]
            rep = run_entry(e)
            (a.out / f"{e['name']}.json").write_text(json.dumps(rep, indent=1))
            run["done"].append({"name": e["name"], "wall_seconds": round(rep["wall_seconds"], 1)})
            (a.out / "run.json").write_text(json.dumps(run, indent=1))
            print(json.dumps(run["done"][-1]), flush=True)
    except BaseException:
        (a.out / "ERROR.txt").write_text(f"stage: {stage}\n{traceback.format_exc()}")
        raise
    run["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (a.out / "run.json").write_text(json.dumps(run, indent=1))


if __name__ == "__main__":
    main()
