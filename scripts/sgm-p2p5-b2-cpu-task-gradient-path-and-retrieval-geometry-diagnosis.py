"""M4-SGM P2.5 B2 CPU diagnosis ($0; CPU; forward/backward only, NO optimizer step, no training).
User go #gravity 22293; scope 22294/22302 (codex 22297/22301: primary path = task CE -> raw reads ->
stored values/beta; anchor gradients kept separate; None = no graph path vs small measured value).

Conditions (same episodes in every condition: train split, filler 40, fixed data seed):
  init   - B2 PilotConfig (probe s0 recipe + occupied_softmax_fill_v1), seed-0 init
  final  - same config with the B2 step-1500 adapters + head (trained_parameters.safetensors)
  oracle - oracle routing (read = write = the key's cell; "routing forced open"), seed-0 init, spec read
Per condition and batch:
  * gradients of task CE and of the anchor term via SEPARATE autograd.grad calls, per param group
    (layer x group, plus head). Reported: per-batch norm mean, and cross-batch consistency
    ||mean_b g_b|| / mean_b ||g_b|| (1 = same direction every batch; pure noise ~ 1/sqrt(K)).
  * retrieval geometry per (layer, head, query): q(query key) . k(bound value-token write) vs the other
    value-token writes (cosine, rank of the bound one among the N values; chance top1 = 1/N), read vs
    write address distance (learned routing only), pairwise k / v collapse across value tokens, and
    cos(read, v_bound) vs other values.
    python scripts/<this> --out DIR [--conditions init,final,oracle] [--batches 6] [--batch-size 4]
"""

import argparse
import json
import math
import os
import resource
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.synthetic_pilot import PilotConfig, build  # noqa: E402
from memsub.sgm.synthetic_binding_task import SINK_IDS, BindingTaskSpec, sample_batch  # noqa: E402
from memsub.sgm.synthetic_pilot_evaluation import ingest  # noqa: E402
from memsub.sgm.occupied_cell_read_fallback import query_anchor_loss  # noqa: E402

PROBE_MANIFEST = ROOT / "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"
B2_PARAMS = ROOT / "plans/261009-1135-m4-sgm-p2p5-b2-occupied-fill-long-run/b2-resume-v1/volume/b2-run-v1/B2/trained_parameters.safetensors"
FILL = {"read_fallback": "occupied_softmax_fill_v1", "read_fallback_tau": 1.0, "read_fallback_anchor": 0.1}
DATA_SEED, FILLER = 777, 40


def make(cond: str):
    base = json.loads(PROBE_MANIFEST.read_text())["pilot_config"]
    over = {"arm": "oracle", "sgm": {}} if cond == "oracle" else {"sgm": dict(FILL)}
    pcfg = PilotConfig(**{**base, **over, "device": "cpu"})
    runtime, backend, head = build(pcfg)
    if cond == "final":
        from safetensors.torch import load_file
        t = load_file(str(B2_PARAMS))
        runtime.adapters.load_state_dict({k[9:]: v for k, v in t.items() if k.startswith("adapters.")})
        head.load_state_dict({k[5:]: v for k, v in t.items() if k.startswith("head.")})
    groups = {f"L{l}/{n}": ps for l, a in runtime.adapters.items() for n, ps in a.param_groups().items()}
    groups["head"] = list(head.parameters())
    return pcfg, runtime, backend, head, groups


def record_projections(runtime) -> dict:
    """Wrap each adapter's project(): rec[layer] = detached outputs, one entry per step (ingest, then queries)."""
    rec = {}
    for l, a in runtime.adapters.items():
        rec[int(l)] = []
        orig = a.project

        def wrapped(x, _orig=orig, _l=int(l)):
            out = _orig(x)
            rec[_l].append({k: v.detach() for k, v in out.items()})
            return out
        a.project = wrapped
    return rec


def flat(grads):
    got = [g.reshape(-1) for g in grads if g is not None]
    return torch.cat(got) if got else None


def rss_gb() -> float:
    return int(open("/proc/self/statm").read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**30


def geometry(rec, reads, batch, layers, n_bind, T, Q):
    """Per layer: means over (episode, query, head) of retrieval-geometry measures (all detached)."""
    s, out = len(SINK_IDS), {}
    for l in layers:
        m = {k: [] for k in ("cos_qk_bound", "cos_qk_other", "rank_qk", "top1_qk", "dist_bound", "dist_other_median",
                             "rank_addr", "k_pair_cos", "v_pair_cos", "cos_read_vbound", "cos_read_vother",
                             "rank_read_v", "beta_value", "beta_filler", "read_norm")}
        vt = [s + 2 * j + 1 for j in range(n_bind)]
        K = torch.stack([rec[l][t]["k"][:, 0] for t in vt], 1)               # [B, N, H, dk]
        V = F.normalize(torch.stack([rec[l][t]["v"][:, 0] for t in vt], 1), dim=-1)
        B, N, H = K.shape[:3]
        off = ~torch.eye(N, dtype=torch.bool)
        m["k_pair_cos"].append(float(torch.einsum("bnhd,bmhd->bhnm", K, K)[..., off].mean()))
        m["v_pair_cos"].append(float(torch.einsum("bnhd,bmhd->bhnm", V, V)[..., off].mean()))
        m["beta_value"].append(float(torch.stack([rec[l][t]["beta"][:, 0] for t in vt]).mean()))
        m["beta_filler"].append(float(torch.stack([rec[l][t]["beta"][:, 0] for t in range(s + 2 * n_bind, T)]).mean()))
        for q in range(Q):
            qr = rec[l][T + q]
            for b in range(B):
                j = (batch.source[b, s:s + 2 * n_bind:2] == batch.query_keys[b, q]).nonzero()[0, 0].item()
                oth = [i for i in range(N) if i != j]
                for h in range(H):
                    sims = K[b, :, h] @ qr["q"][b, 0, h]
                    m["cos_qk_bound"].append(float(sims[j])); m["cos_qk_other"].append(float(sims[oth].mean()))
                    rk = int((sims > sims[j]).sum()); m["rank_qk"].append(rk); m["top1_qk"].append(float(rk == 0))
                    r = reads[q][l][b, 0, h]
                    m["read_norm"].append(float(r.norm()))
                    rv = V[b, :, h] @ F.normalize(r, dim=0)
                    m["cos_read_vbound"].append(float(rv[j])); m["cos_read_vother"].append(float(rv[oth].mean()))
                    m["rank_read_v"].append(int((rv > rv[j]).sum()))
                    if "a_read" in qr:
                        aw = torch.stack([rec[l][t]["a_write"][b, 0, h] for t in vt])
                        d = (aw - qr["a_read"][b, 0, h]).norm(dim=-1)
                        m["dist_bound"].append(float(d[j])); m["dist_other_median"].append(float(d[oth].median()))
                        m["rank_addr"].append(int((d < d[j]).sum()))
        out[f"L{l}"] = {k: (sum(v) / len(v) if v else None) for k, v in m.items()}
    return out


def run_condition(cond, args, log):
    pcfg, runtime, backend, head, groups = make(cond)
    rec = record_projections(runtime)
    spec = BindingTaskSpec(pcfg.n_bindings, pcfg.n_queries, FILLER)
    gen, layers = torch.Generator().manual_seed(DATA_SEED), runtime.cfg.selected_layers
    names, params = list(groups), [p for ps in groups.values() for p in ps]
    sizes = [len(ps) for ps in groups.values()]
    # running sum + per-batch norms only (full per-batch gradient vectors are not kept: memory, codex 22319)
    G = {kind: {n: {"sum": None, "norms": [], "n_none": 0} for n in names} for kind in ("task", "anchor")}
    geo, losses = [], []
    log(f"{cond} built; {args.batches} batches x batch_size {args.batch_size}; rss {rss_gb():.2f} GB")
    for bi in range(args.batches):
        t0 = time.time()
        for v in rec.values():
            v.clear()
        batch = sample_batch(spec, "train", args.batch_size, gen)
        state = ingest(backend, batch, pcfg.arm, None, True, spec.n_bindings)   # graph kept into the bank
        task, traces, reads, hits = 0.0, [], [], 0
        for q in range(spec.n_queries):       # mirrors query_logits (taskhead branch), keeping the reads
            oracle = batch.oracle_query[:, q:q + 1] if pcfg.arm == "oracle" else None
            out = backend.evaluate_query(state, batch.query_keys[:, q:q + 1], enabled=True,
                                         oracle_addresses=oracle, detach=False, logits=False)
            logits = head(torch.cat([out["reads"][l][:, -1].flatten(1) for l in layers], dim=-1))
            task = task + F.cross_entropy(logits, batch.labels[:, q])
            hits += int((logits.argmax(-1) == batch.labels[:, q]).sum())
            traces.append(out["trace"]); reads.append({l: r.detach() for l, r in out["reads"].items()})
        task = task / spec.n_queries
        anchor = query_anchor_loss(traces) if runtime.cfg.read_fallback_anchor > 0 else None
        for kind, loss in (("task", task), ("anchor", anchor)):
            if loss is None:
                continue
            # keep the graph only when the anchor backward still follows (oracle has no anchor; codex 22319)
            gs = torch.autograd.grad(loss, params, allow_unused=True, retain_graph=kind == "task" and anchor is not None)
            i = 0
            for n, k in zip(names, sizes):
                g, acc = flat(gs[i:i + k]), G[kind][n]; i += k
                if g is None:
                    acc["n_none"] += 1
                    continue
                acc["norms"].append(float(g.norm()))
                acc["sum"] = g.clone() if acc["sum"] is None else acc["sum"] + g
        losses.append({"task_ce": float(task), "anchor": None if anchor is None else float(anchor),
                       "acc": hits / (args.batch_size * spec.n_queries)})
        geo.append(geometry(rec, reads, batch, layers, spec.n_bindings, spec.source_len(), spec.n_queries))
        ce = float(task)
        # release this batch's graph (bank state, losses, traces, last query output) before the next ingest
        del state, task, anchor, traces, out, logits, gs, loss
        log(f"{cond} batch {bi}: ce {ce:.4f} acc {losses[-1]['acc']:.3f} {time.time() - t0:.0f}s "
            f"rss {rss_gb():.2f} GB maxrss {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20:.2f} GB")
    grad = {}
    for kind, per in G.items():
        for n, acc in per.items():
            norms = acc["norms"]
            if not norms and not acc["n_none"]:
                continue                                   # this loss was never computed (anchor off)
            if not norms:
                grad.setdefault(kind, {})[n] = "None (no graph path)"
                continue
            nm = sum(norms) / len(norms)
            grad.setdefault(kind, {})[n] = {"norm_mean": nm, "consistency": float((acc["sum"] / len(norms)).norm()) / max(nm, 1e-30),
                                            "n_batches": len(norms), "n_none": acc["n_none"]}
    geo_mean = {l: {k: (None if geo[0][l][k] is None else sum(g[l][k] for g in geo) / len(geo))
                    for k in geo[0][l]} for l in geo[0]}
    return {"condition": cond, "pilot_config": {k: getattr(pcfg, k) for k in ("arm", "readout", "n_bindings", "sgm")},
            "differences_vs_b2": ("none (B2 config)" if cond == "init" else
                                  "B2 step-1500 weights, sha256 " + __import__("hashlib").sha256(B2_PARAMS.read_bytes()).hexdigest()
                                  if cond == "final" else "arm oracle (perfect read=write cells), read_fallback off, anchor off "
                                  "(SGMConfig rejects fill with oracle routing)"),
            "batches": args.batches, "batch_size": args.batch_size, "filler_len": FILLER, "data_seed": DATA_SEED,
            "consistency_unit": f"per-batch gradient = mean over {args.batch_size} episode(s); ratio over {args.batches} batches",
            "noise_consistency_ref": 1 / math.sqrt(args.batches), "chance_ce": math.log(64),
            "chance_top1": 1 / spec.n_bindings, "losses": losses, "grad": grad, "geometry": geo_mean}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--conditions", default="init,final,oracle")
    ap.add_argument("--batches", type=int, default=6)
    ap.add_argument("--batch-size", type=int, default=4)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    logf = (a.out / "progress.log").open("a")

    def log(msg):
        print(msg, flush=True); logf.write(msg + "\n"); logf.flush()
    for cond in a.conditions.split(","):
        res = run_condition(cond, a, log)
        (a.out / f"{cond}.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
