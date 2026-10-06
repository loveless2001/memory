"""Synthetic key/value binding episodes for the P2 pilot — M4-SGM.md §13, §14.

Episode layout (token ids only; no tokenizer):
    source = sinks(4) + [key_1, value_1, ..., key_N, value_N] + filler(F)
    queries = Q keys drawn from this episode's bindings; label = value class
Bindings are random per episode, so no parametric shortcut exists: a correct
answer requires reading what this episode wrote. With F >= local window,
every binding is outside recent KV at query time (beyond-window dependency).

Splits are partitioned BEFORE generation: train vs held-out key families and
filler (template) families are disjoint id ranges; values are a shared class
set (labels must be classifiable). `split_manifest()` records the partition
and an actual overlap audit, not only seeds.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import torch

SINK_IDS = (151643, 198, 220, 271)
VALUE_BASE, N_VALUES = 3000, 64
KEY_RANGES = {"train": (10000, 10800), "heldout": (10800, 11000)}
FILLER_RANGES = {"train": (20000, 21000), "heldout": (21000, 22000)}
JUNK_ADDRESS = (-60.0, -60.0)  # oracle arm: non-binding tokens write here


@dataclass(frozen=True)
class BindingTaskSpec:
    n_bindings: int
    n_queries: int
    filler_len: int

    def source_len(self) -> int:
        return len(SINK_IDS) + 2 * self.n_bindings + self.filler_len


@dataclass
class EpisodeBatch:
    source: torch.Tensor          # [B, T] long
    query_keys: torch.Tensor      # [B, Q] long
    labels: torch.Tensor          # [B, Q] long, value class in [0, N_VALUES)
    oracle_source: torch.Tensor   # [B, T, 2] float — diagnostic arm only
    oracle_query: torch.Tensor    # [B, Q, 2] float — diagnostic arm only


def oracle_coordinate(key_id: int) -> tuple[float, float]:
    """Distinct integer cell per key, spaced 3 apart so stencils never overlap."""
    i = key_id - KEY_RANGES["train"][0]
    return float(3 * (i % 40)), float(3 * (i // 40))


def sample_batch(spec: BindingTaskSpec, split: str, batch: int,
                 gen: torch.Generator) -> EpisodeBatch:
    if spec.n_queries > spec.n_bindings:
        raise ValueError("cannot query more keys than bindings")
    k_lo, k_hi = KEY_RANGES[split]
    f_lo, f_hi = FILLER_RANGES[split]
    T = spec.source_len()
    source = torch.empty(batch, T, dtype=torch.long)
    oracle_src = torch.tensor(JUNK_ADDRESS).repeat(batch, T, 1)
    qkeys = torch.empty(batch, spec.n_queries, dtype=torch.long)
    labels = torch.empty(batch, spec.n_queries, dtype=torch.long)
    oracle_q = torch.empty(batch, spec.n_queries, 2)
    s = len(SINK_IDS)
    for b in range(batch):
        keys = k_lo + torch.randperm(k_hi - k_lo, generator=gen)[:spec.n_bindings]
        vals = torch.randint(0, N_VALUES, (spec.n_bindings,), generator=gen)
        source[b, :s] = torch.tensor(SINK_IDS)
        source[b, s:s + 2 * spec.n_bindings:2] = keys
        source[b, s + 1:s + 2 * spec.n_bindings:2] = VALUE_BASE + vals
        source[b, s + 2 * spec.n_bindings:] = torch.randint(
            f_lo, f_hi, (spec.filler_len,), generator=gen)
        for j, key in enumerate(keys.tolist()):  # value token is written at key's cell
            oracle_src[b, s + 2 * j + 1] = torch.tensor(oracle_coordinate(key))
        pick = torch.randperm(spec.n_bindings, generator=gen)[:spec.n_queries]
        qkeys[b], labels[b] = keys[pick], vals[pick]
        oracle_q[b] = torch.tensor([oracle_coordinate(k) for k in keys[pick].tolist()])
    return EpisodeBatch(source, qkeys, labels, oracle_src, oracle_q)


def split_manifest(spec: BindingTaskSpec, seeds: dict[str, int]) -> dict:
    train_k, held_k = (set(range(*KEY_RANGES[s])) for s in ("train", "heldout"))
    train_f, held_f = (set(range(*FILLER_RANGES[s])) for s in ("train", "heldout"))
    return {
        "task": "synthetic_kv_binding_v1",
        "spec": asdict(spec),
        "source_len": spec.source_len(),
        "key_ranges": KEY_RANGES, "filler_ranges": FILLER_RANGES,
        "value_classes": {"base": VALUE_BASE, "n": N_VALUES},
        "sink_ids": list(SINK_IDS),
        "seeds": seeds,
        "overlap_audit": {
            "key_family_overlap": len(train_k & held_k),
            "filler_family_overlap": len(train_f & held_f),
            "key_value_filler_disjoint": not (
                (train_k | held_k) & (train_f | held_f)
                or (train_k | held_k | train_f | held_f)
                & set(range(VALUE_BASE, VALUE_BASE + N_VALUES))),
        },
    }
