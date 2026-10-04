"""P2 pilot evaluation, causal interventions and routing telemetry —
M4-SGM.md §8, §16.

Main controls re-ingest the source under each arm's policy (separate runs).
The interventions here are labelled DIAGNOSTICS on a trained model:
  * shuffle      — permute cell contents among coordinates after ingest;
  * read_offset  — shift every query read address by +3 cells;
  * query_off    — memory disabled at query time only (ingest influence on
                   recent KV remains; not a memory-off control).
"""

from __future__ import annotations

import math

import torch

from .backend import SourceRef, SparseGrowingMemoryBackend
from .synthetic_binding_task import VALUE_BASE, N_VALUES, BindingTaskSpec, sample_batch

INTERVENTIONS = ("none", "shuffle", "read_offset", "query_off")


def query_logits(backend, head, state, batch, q: int, arm: str, readout: str,
                 detach: bool, query_enabled: bool = True):
    """Logits over the N_VALUES classes for query q, plus the raw trace."""
    enabled = arm != "memory_off" and query_enabled
    oracle = batch.oracle_query[:, q:q + 1] if arm == "oracle" and enabled else None
    out = backend.evaluate_query(state, batch.query_keys[:, q:q + 1], enabled=enabled,
                                 oracle_addresses=oracle, detach=detach)
    if readout == "lm":
        return out["logits"][:, VALUE_BASE:VALUE_BASE + N_VALUES], out["trace"]
    layers = backend.runtime.cfg.selected_layers
    if not enabled:
        c = backend.runtime.cfg
        feats = torch.zeros(batch.source.shape[0], len(layers) * c.memory_heads * c.value_dim)
    else:
        feats = torch.cat([out["reads"][l][:, -1].flatten(1) for l in layers], dim=-1)
    return head(feats), out["trace"]


def ingest(backend: SparseGrowingMemoryBackend, batch, arm: str):
    state = backend.new_state(batch.source.shape[0])
    oracle = batch.oracle_source if arm == "oracle" else None
    return backend.ingest_source(state, batch.source, SourceRef("synthetic-episode"),
                                 enabled=arm != "memory_off", oracle_addresses=oracle)


def _shuffle_banks(state, gen: torch.Generator) -> None:
    for key, bank in state.banks.cells.items():
        coords, cells = list(bank.keys()), list(bank.values())
        perm = torch.randperm(len(cells), generator=gen).tolist()
        state.banks.cells[key] = {c: cells[j] for c, j in zip(coords, perm)}


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


@torch.no_grad()
def evaluate(backend, head, spec: BindingTaskSpec, arm: str, readout: str, *,
             split: str, batches: int, batch_size: int, seed: int,
             intervention: str = "none", per_example: list | None = None) -> dict:
    gen = torch.Generator().manual_seed(seed)
    correct = total = 0
    empty, coords, tele, episode_acc = [], [], [], []
    rt = backend.runtime
    for bi in range(batches):
        batch = sample_batch(spec, split, batch_size, gen)
        state = ingest(backend, batch, arm).detached()
        tele.append(bank_telemetry(state))
        if intervention == "shuffle":
            _shuffle_banks(state, gen)
        rt.diag_read_offset = 3.0 if intervention == "read_offset" else 0.0
        ep_hits = torch.zeros(batch_size)
        try:
            for q in range(spec.n_queries):
                logits, trace = query_logits(backend, head, state, batch, q, arm, readout,
                                             detach=True,
                                             query_enabled=intervention != "query_off")
                pred = logits.argmax(-1)
                hit = pred == batch.labels[:, q]
                correct += int(hit.sum()); total += hit.numel()
                ep_hits += hit.float()
                empty += trace["empty_read_weight"]
                for l, cs in trace["read_coords"].items():
                    coords.append(cs[-1].reshape(-1, 2))
                if per_example is not None:
                    for b in range(hit.numel()):
                        per_example.append({"batch": bi, "episode": b, "query": q,
                                            "key": int(batch.query_keys[b, q]),
                                            "label": int(batch.labels[b, q]),
                                            "pred": int(pred[b]), "correct": bool(hit[b]),
                                            "intervention": intervention})
        finally:
            rt.diag_read_offset = 0.0
        episode_acc += (ep_hits / spec.n_queries).tolist()
    spread = float(torch.cat(coords).std(0).mean()) if coords else 0.0
    out = {"accuracy": correct / total, "correct": correct, "total": total,
           "chance": 1.0 / N_VALUES,
           "query_empty_read_weight": sum(empty) / len(empty) if empty else None,
           "query_read_address_std_cells": spread if coords else None}
    out.update({k: sum(t[k] for t in tele) / len(tele) for k in tele[0]})
    # Episode-level (not per-query) normal interval: queries share a source.
    ep = torch.tensor(episode_acc, dtype=torch.float64)
    out["episodes"] = len(episode_acc)
    out["accuracy_ci95_halfwidth_episode"] = float(1.96 * ep.std() / math.sqrt(len(ep)))
    return out
