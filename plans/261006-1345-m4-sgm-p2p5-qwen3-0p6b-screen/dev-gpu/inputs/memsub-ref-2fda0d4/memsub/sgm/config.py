"""SGM (Sparse Growing Memory) configuration — M4-SGM.md §4.

A frozen, resolved configuration is part of the policy identity: the
`policy_id` hashes every field that changes addressing, update or
integration semantics, so state written under one config can never be
read under another (M4-SGM.md §11).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace

# Versioned algorithm identities (§5). Bump on any semantic change.
STENCIL_VERSION = "quadratic_bspline_3x3_v1"
UPDATE_VERSION = "weighted_delta_v1"
READ_ORDER_VERSION = "read_before_write_v1"
INGEST_VERSION = "token_serial_v1"

ADDRESS_MODES = ("learned", "random_fixed", "single_cell", "oracle")


@dataclass(frozen=True)
class SGMConfig:
    selected_layers: tuple[int, ...]
    memory_heads: int = 4
    key_dim: int = 32
    value_dim: int = 32
    address_hidden: int = 64
    address_scale: float = 8.0
    # Init spread of addresses, in cells (§8 overlapping cold-start neighborhood).
    address_init_spread: float = 1.0
    local_recent_tokens: int = 1024
    pinned_sink_tokens: int = 4
    max_cells_per_bank: int = 1024
    alpha_init_logit: float = -4.0
    out_init_std: float = 0.02
    # 1 = spec default (projections see z_t only). 2 = also see z_{t-1}
    # (causal token shift, as in delta-rule short convolutions). Registered
    # deviation used only where stated; part of the policy identity.
    feature_shift: int = 1
    # Arm identity (§15). "oracle" is a diagnostic arm, never a headline score.
    address_mode: str = "learned"
    stencil: str = STENCIL_VERSION
    update: str = UPDATE_VERSION
    read_order: str = READ_ORDER_VERSION
    ingest: str = INGEST_VERSION
    resolved: dict = field(default_factory=dict, compare=False)

    def __post_init__(self):
        if self.address_mode not in ADDRESS_MODES:
            raise ValueError(f"unknown address_mode {self.address_mode!r}")
        if self.feature_shift not in (1, 2):
            raise ValueError("feature_shift must be 1 or 2")
        if not self.selected_layers or len(set(self.selected_layers)) != len(self.selected_layers):
            raise ValueError("selected_layers must be non-empty and unique")
        if min(self.memory_heads, self.key_dim, self.value_dim,
               self.local_recent_tokens, self.max_cells_per_bank) < 1:
            raise ValueError("dimensions and budgets must be positive")

    # -- resolution against a concrete backbone ---------------------------------
    def resolve(self, model_config) -> "SGMConfig":
        """Validate layers against the backbone and record its geometry."""
        n_layers = int(model_config.num_hidden_layers)
        bad = [l for l in self.selected_layers if not 0 <= l < n_layers]
        if bad:
            raise ValueError(f"selected layers {bad} outside 0..{n_layers - 1}")
        resolved = {
            "hidden_size": int(model_config.hidden_size),
            "num_hidden_layers": n_layers,
            "model_type": str(model_config.model_type),
        }
        return replace(self, selected_layers=tuple(sorted(self.selected_layers)),
                       resolved=resolved)

    @property
    def hidden_size(self) -> int:
        if "hidden_size" not in self.resolved:
            raise ValueError("config not resolved against a backbone")
        return self.resolved["hidden_size"]

    # -- identity ------------------------------------------------------------------
    def to_json(self) -> dict:
        out = asdict(self)
        out["selected_layers"] = list(self.selected_layers)
        return out

    @classmethod
    def from_json(cls, data: dict) -> "SGMConfig":
        data = dict(data)
        data["selected_layers"] = tuple(data["selected_layers"])
        return cls(**data)

    @property
    def policy_id(self) -> str:
        canonical = json.dumps(self.to_json(), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        return f"m4-sgm:{self.address_mode}:sha256:{digest}"
