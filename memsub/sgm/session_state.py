"""SGM session state — M4-SGM.md §3, §9.

Holds everything the SGM runtime mutates for one session (or one batch of
independent episodes): bounded recent KV, sparse banks, the token-shift
feature carry, and the source cursor. P2 scope: ephemeral and synthetic —
no durable persistence; `redaction_generation` is carried and checked but
real-archive invalidation (SGM-10/11) is P4 work.

`fork()` is alias-free and graph-preserving (training queries, ingest
transactions); `detached()` is the evaluation snapshot. Neither clones
tensors on the per-token path: cache and cell tensors are never mutated in
place by the SGM runtime, so sharing them between branches is safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import torch

from ..errors import CompatibilityError, RedactionError
from ..runtime.compacted_prefix_cache import CompactedPrefixCache
from .sparse_cell_bank import SparseBankSet


def _fork_cache(cache: CompactedPrefixCache, detach: bool) -> CompactedPrefixCache:
    out = CompactedPrefixCache(cache.sink_token_count)
    for i in range(cache.num_layers):
        k, v = cache.layer_kv(i)
        if k is None:  # layer not yet populated (fresh cache)
            continue
        out.update(k.detach() if detach else k, v.detach() if detach else v, i)
    out.logical_positions = list(cache.logical_positions)
    out.next_logical_position = cache.next_logical_position
    return out


@dataclass
class SGMSessionState:
    recent_kv: CompactedPrefixCache
    banks: SparseBankSet
    policy_id: str
    shift_features: dict[int, torch.Tensor] = field(default_factory=dict)
    source_refs: tuple[str, ...] = ()
    redaction_generation: int = 0
    weights_id: str = ""

    @property
    def source_cursor(self) -> int:
        """Logical tokens ingested so far (positions are never renumbered)."""
        return self.recent_kv.next_logical_position

    def fork(self) -> "SGMSessionState":
        return SGMSessionState(
            recent_kv=_fork_cache(self.recent_kv, detach=False),
            banks=self.banks.fork(), policy_id=self.policy_id,
            shift_features=dict(self.shift_features),
            source_refs=self.source_refs,
            redaction_generation=self.redaction_generation,
            weights_id=self.weights_id)

    def detached(self) -> "SGMSessionState":
        return SGMSessionState(
            recent_kv=_fork_cache(self.recent_kv, detach=True),
            banks=self.banks.detached(), policy_id=self.policy_id,
            shift_features={l: t.detach() for l, t in self.shift_features.items()},
            source_refs=self.source_refs,
            redaction_generation=self.redaction_generation,
            weights_id=self.weights_id)

    def check_valid(self, policy_id: str, redaction_generation: int,
                    weights_id: str) -> None:
        """Fail closed on a policy change, different/updated adapter weights
        (bank AND adapter-influenced recent KV are rejected together), or a
        newer redaction generation."""
        if policy_id != self.policy_id:
            raise CompatibilityError(f"state policy {self.policy_id} != {policy_id}")
        if weights_id != self.weights_id:
            raise CompatibilityError(
                f"state built under adapter weights {self.weights_id}, live {weights_id}")
        if redaction_generation != self.redaction_generation:
            raise RedactionError("state predates the current redaction generation")
