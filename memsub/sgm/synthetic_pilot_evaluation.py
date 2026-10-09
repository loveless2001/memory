"""P2 pilot evaluation, causal interventions and routing telemetry —
M4-SGM.md §8, §16 (revised after #gravity audit 21074/21075).

Main controls re-ingest the source under each arm's policy (separate runs).
Interventions below are DIAGNOSTICS on a trained model. Every intervention
evaluates the SAME pre-generated episodes (data RNG is never consumed by an
intervention; interventions use their own RNG), so rows pair by episode:
  * bank_derange  — registered memory-use check for every arm: episode b
                    queries episode (b+1) mod B's complete banks;
  * coord_shuffle — permute cell contents among coordinates within a bank
                    (N/A for single_cell: one coordinate per bank);
  * read_offset   — shift every query read address by +3 cells;
  * query_off     — memory disabled at query time only (ingest influence on
                    recent KV remains; not a memory-off control).
"""

from __future__ import annotations

import hashlib
import math

import torch

from .backend import SourceRef, SparseGrowingMemoryBackend
from .occupied_cell_read_fallback import fallback_summary
from .synthetic_binding_task import VALUE_BASE, N_VALUES, BindingTaskSpec, sample_batch

INTERVENTIONS = ("none", "bank_derange", "coord_shuffle", "read_offset", "query_off")
INTERVENTION_RNG_OFFSET = 1_000_003


def query_logits(backend, head, state, batch, q: int, arm: str, readout: str,
                 detach: bool, query_enabled: bool = True):
    """Logits over the N_VALUES classes for query q, plus the raw trace."""
    enabled = arm != "memory_off" and query_enabled
    oracle = batch.oracle_query[:, q:q + 1] if arm == "oracle" and enabled else None
    out = backend.evaluate_query(state, batch.query_keys[:, q:q + 1], enabled=enabled,
                                 oracle_addresses=oracle, detach=detach,
                                 logits=readout == "lm", final_hidden=readout == "residual_head")
    if readout == "lm":
        return out["logits"][:, VALUE_BASE:VALUE_BASE + N_VALUES], out["trace"]
    if readout == "residual_head":   # P2.5: same head for every arm, incl. local-only memory_off
        return head(out["final_hidden"]), out["trace"]
    c = backend.runtime.cfg
    if not enabled:
        feats = torch.zeros(batch.source.shape[0],
                            len(c.selected_layers) * c.memory_heads * c.value_dim,
                            device=backend.runtime.device)
    else:
        feats = torch.cat([out["reads"][l][:, -1].flatten(1) for l in c.selected_layers], dim=-1)
    return head(feats), out["trace"]


def ingest(backend: SparseGrowingMemoryBackend, batch, arm: str, traces: list | None = None,
           filler_writes: bool = True, n_bindings: int | None = None):
    state = backend.new_state(batch.source.shape[0])
    oracle = batch.oracle_source if arm == "oracle" else None
    mask = None
    if not filler_writes:   # P2D learned_filler_off: tail-filler steps never write
        tail = 4 + 2 * n_bindings
        mask = [t < tail for t in range(batch.source.shape[1])]
    return backend.ingest_source(state, batch.source, SourceRef("synthetic-episode"),
                                 enabled=arm != "memory_off", oracle_addresses=oracle,
                                 traces=traces, write_mask=mask)


def episode_hash(batch, b: int) -> str:
    h = hashlib.sha256()
    for t in (batch.source[b], batch.query_keys[b], batch.labels[b]):
        h.update(t.numpy().tobytes())
    return h.hexdigest()[:16]


def beta_by_token_class(traces: list, n_bindings: int, effective: bool = False) -> dict:
    """Mean gate per source-token class (sink / key / value / filler).
    effective=False: raw projected beta (recorded on every step).
    effective=True: the beta actually applied — 0 on skipped-write steps
    (P2D filler_off). Steps without telemetry make the result empty."""
    sums: dict[str, list[float]] = {"sink": [], "key": [], "value": [], "filler": []}
    for t, tr in enumerate(traces):
        if "beta_projected" not in tr:
            return {}
        cls = ("sink" if t < 4 else "filler" if t >= 4 + 2 * n_bindings
               else "key" if (t - 4) % 2 == 0 else "value")
        if effective and "beta" not in tr:
            sums[cls].append(0.0)
            continue
        src = tr["beta"] if effective else tr["beta_projected"]
        sums[cls].append(float(torch.stack(list(src.values())).mean()))
    return {k: sum(v) / len(v) for k, v in sums.items() if v}


def bank_telemetry(state) -> dict:
    """Occupancy and effective cells (exp entropy of cell Frobenius norms)."""
    occ, eff = [], []
    for bank in state.banks.cells.values():
        occ.append(len(bank))
        if bank:
            norms = torch.stack([t.norm() for t in bank.values()]).double()
            p = norms / norms.sum().clamp_min(1e-12)
            eff.append(float(torch.exp(-(p * p.clamp_min(1e-12).log()).sum())))
    return {"occupancy_mean": sum(occ) / len(occ), "occupancy_max": max(occ),
            "effective_cells_mean": sum(eff) / len(eff) if eff else 0.0,
            "neural_bytes": state.banks.neural_bytes()}


def apply_intervention(state, intervention: str, gen: torch.Generator) -> None:
    banks = state.banks
    if intervention == "bank_derange":
        if banks.batch < 2:
            raise ValueError("bank_derange needs >= 2 episodes per batch")
        old = banks.cells
        banks.cells = {(b, l, h): old[((b + 1) % banks.batch, l, h)] for (b, l, h) in old}
    elif intervention == "coord_shuffle":
        for key, bank in banks.cells.items():
            coords, cells = list(bank.keys()), list(bank.values())
            perm = torch.randperm(len(cells), generator=gen).tolist()
            banks.cells[key] = {c: cells[j] for c, j in zip(coords, perm)}


@torch.no_grad()
def evaluate(backend, head, spec: BindingTaskSpec, arm: str, readout: str, *,
             split: str, batches: int, batch_size: int, seed: int,
             intervention: str = "none", per_example: list | None = None,
             filler_writes: bool = True) -> dict | None:
    if intervention == "coord_shuffle" and arm == "single_cell":
        return None  # not applicable: one coordinate per bank
    data_gen = torch.Generator().manual_seed(seed)
    episodes = [sample_batch(spec, split, batch_size, data_gen) for _ in range(batches)]
    rt = backend.runtime
    correct = total = 0
    empty, coords, tele, episode_acc, betas, eff_betas, fill = [], [], [], [], [], [], []
    for bi, batch in enumerate(episodes):
        traces: list = []
        state = ingest(backend, batch, arm, traces, filler_writes, spec.n_bindings).detached()
        tele.append(bank_telemetry(state))
        betas.append(beta_by_token_class(traces, spec.n_bindings))
        eff_betas.append(beta_by_token_class(traces, spec.n_bindings, effective=True))
        iv_gen = torch.Generator().manual_seed(seed + INTERVENTION_RNG_OFFSET + bi)
        apply_intervention(state, intervention, iv_gen)
        rt.diag_read_offset = 3.0 if intervention == "read_offset" else 0.0
        ep_hits = torch.zeros(batch_size)
        try:
            for q in range(spec.n_queries):
                logits, trace = query_logits(backend, head, state, batch, q, arm, readout,
                                             detach=True,
                                             query_enabled=intervention != "query_off")
                pred = logits.argmax(-1).cpu()        # rows are built on CPU (no-op on CPU)
                hit = pred == batch.labels[:, q]
                correct += int(hit.sum()); total += hit.numel()
                ep_hits += hit.float()
                empty += [float(x) for x in trace["empty_read_weight"]]
                fill += trace.get("query_fallback", [])      # read_fallback variant only
                coords += [cs[-1].reshape(-1, 2) for cs in trace["read_coords"].values()]
                if per_example is not None:
                    for b in range(hit.numel()):
                        per_example.append({
                            "batch": bi, "episode": b, "episode_hash": episode_hash(batch, b),
                            "query": q, "key": int(batch.query_keys[b, q]),
                            "label": int(batch.labels[b, q]), "pred": int(pred[b]),
                            "correct": bool(hit[b]), "intervention": intervention})
        finally:
            rt.diag_read_offset = 0.0
        episode_acc += (ep_hits / spec.n_queries).tolist()
    out = {"accuracy": correct / total, "correct": correct, "total": total,
           "chance": 1.0 / N_VALUES,
           "query_empty_read_weight": sum(empty) / len(empty) if empty else None,
           "query_read_address_std_cells": float(torch.cat(coords).std(0).mean()) if coords else None}
    out.update({k: sum(t[k] for t in tele) / len(tele) for k in tele[0]})
    if fill:
        out.update(fallback_summary(fill))
    if betas and betas[0]:
        out["beta_by_token_class"] = {k: sum(b[k] for b in betas) / len(betas) for k in betas[0]}
        out["effective_beta_by_token_class"] = {k: sum(b[k] for b in eff_betas) / len(eff_betas)
                                                for k in eff_betas[0]}
    ep = torch.tensor(episode_acc, dtype=torch.float64)
    out["episodes"] = len(episode_acc)
    out["accuracy_ci95_halfwidth_episode"] = float(1.96 * ep.std() / math.sqrt(len(ep)))
    return out
