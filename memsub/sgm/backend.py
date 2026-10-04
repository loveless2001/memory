"""SparseGrowingMemoryBackend — session orchestration, M4-SGM.md §6, §7, §9.

Transaction boundary (agreed #gravity 21060/21064): one `ingest_source`
call is atomic. It runs on a graph-preserving fork; any failure (capacity
overflow at any token/layer/head, non-finite state) discards the fork, so
the caller's committed bank, recent KV and source cursor are unchanged.

Write policy: persistent writes happen only inside `ingest_source` for a
SourceRef of kind "authorized_source". `evaluate_query` runs on a scratch
fork with writes hard-disabled and returns no state, so questions, options,
targets and generated text can never become persistent writes (SGM-08).
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from ..runtime.sgm_model_runtime import SGMModelRuntime
from .session_state import SGMSessionState

AUTHORIZED_SOURCE = "authorized_source"


@dataclass(frozen=True)
class SourceRef:
    span_id: str
    kind: str = AUTHORIZED_SOURCE


class SparseGrowingMemoryBackend:
    def __init__(self, runtime: SGMModelRuntime):
        self.runtime = runtime

    @property
    def policy_id(self) -> str:
        return self.runtime.cfg.policy_id

    def new_state(self, batch: int = 1) -> SGMSessionState:
        return self.runtime.new_state(batch)

    def ingest_source(self, state: SGMSessionState, token_ids: torch.Tensor,
                      source: SourceRef, *, enabled: bool = True,
                      oracle_addresses: torch.Tensor | None = None,
                      traces: list | None = None) -> SGMSessionState:
        """Token-serial ingest of token_ids [B, T]; returns the new committed
        state. `state` itself is never modified. oracle_addresses [B, T, 2]
        only for the diagnostic oracle arm (read = write = token's address).
        `traces` (optional) collects each token step's telemetry trace."""
        if source.kind != AUTHORIZED_SOURCE:
            raise PermissionError(f"persistent writes need an authorized source, got {source.kind!r}")
        state.check_valid(self.policy_id, state.redaction_generation)
        work = state.fork()
        for t in range(token_ids.shape[1]):
            oracle = None
            if enabled and oracle_addresses is not None:
                a = oracle_addresses[:, t:t + 1]
                oracle = {"read": a, "write": a}
            out = self.runtime.step(work, token_ids[:, t:t + 1], write=enabled,
                                    enabled=enabled, oracle=oracle)
            if traces is not None:
                traces.append(out["trace"])
        work.source_refs = state.source_refs + (source.span_id,)
        return work

    def evaluate_query(self, state: SGMSessionState, prompt_ids: torch.Tensor, *,
                       enabled: bool = True, oracle_addresses: torch.Tensor | None = None,
                       detach: bool = False) -> dict:
        """Read-only query from the pre-query snapshot. detach=True for
        evaluation; training queries keep the graph into the bank and KV."""
        state.check_valid(self.policy_id, state.redaction_generation)
        scratch = state.detached() if detach else state.fork()
        oracle = None
        if enabled and oracle_addresses is not None:
            oracle = {"read": oracle_addresses, "write": oracle_addresses}
        return self.runtime.step(scratch, prompt_ids, write=False, enabled=enabled,
                                 oracle=oracle, logits=True)
