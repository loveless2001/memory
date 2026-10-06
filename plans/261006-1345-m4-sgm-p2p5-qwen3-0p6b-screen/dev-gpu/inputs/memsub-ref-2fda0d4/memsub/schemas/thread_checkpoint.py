"""ThreadCheckpoint schema — extracted verbatim from spec 6.2 (BUILD.md 5).

A checkpoint is a cache object (spec 4.6): it accelerates resume, but the
thread is always fully recoverable from the archive without it.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..fingerprint import CompatibilityFingerprint


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class AttentionMetadata:
    attention_mask_format: str = "dense"      # paged | block_sparse | dense
    compaction_map_uri: str = ""
    channel_bias_version: str = "memchan-v1"


@dataclass
class CheckpointPositioning:
    next_logical_position: int
    next_physical_position: int
    rope_state: str = "derived"               # positions derivable from compaction map


@dataclass
class SamplerState:
    rng_seed: int = 0
    temperature: float = 0.0
    top_p: float = 1.0
    reproducibility: str = "best_effort"      # by design (spec 6.2 note)


@dataclass
class FidelityMetadata:
    offline_certification_id: Optional[str] = None
    online_risk_estimate: float = 0.0
    sampled_probe_count: int = 0
    lost_fact_risk_estimate: float = 0.0
    measured_at: str = field(default_factory=_now_iso)


@dataclass
class ThreadCheckpoint:
    checkpoint_id: str
    thread_id: str
    parent_checkpoint_id: Optional[str]
    compatibility_fingerprint: dict
    surviving_token_ids_uri: str
    kv_page_table_uri: str
    memory_block_ids: list[str]
    sink_tokens_retained: list[int]
    attention_metadata: AttentionMetadata
    positioning: CheckpointPositioning
    sampler_state: SamplerState = field(default_factory=SamplerState)
    fidelity_metadata: FidelityMetadata = field(default_factory=FidelityMetadata)
    created_at: str = field(default_factory=_now_iso)

    def fingerprint(self) -> CompatibilityFingerprint:
        return CompatibilityFingerprint.from_dict(self.compatibility_fingerprint)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ThreadCheckpoint":
        d = dict(d)
        d["attention_metadata"] = AttentionMetadata(**d["attention_metadata"])
        d["positioning"] = CheckpointPositioning(**d["positioning"])
        d["sampler_state"] = SamplerState(**d["sampler_state"])
        d["fidelity_metadata"] = FidelityMetadata(**d["fidelity_metadata"])
        return cls(**d)
