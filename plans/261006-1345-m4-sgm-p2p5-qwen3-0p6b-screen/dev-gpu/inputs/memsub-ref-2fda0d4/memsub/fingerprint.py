"""compatibility_fingerprint (spec 4.6): computed before any KV artifact is
written; every artifact write path requires one. Validation is all-or-nothing
and a hard fail — a mismatched artifact is diagnostic-only, never live context.
"""

from __future__ import annotations

import dataclasses
import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from .hashing import sha256_json, sha256_text

# Policy version strings for this MVP (untrained eviction only, BUILD.md 5).
COMPACTION_POLICY_VERSION = "evict-oldest-nonsink-v1"
POSITION_POLICY_VERSION = "pos-v1-preserve-logical-rope"
CHANNEL_REGISTRY_VERSION = "memchan-v1"

FIELDS = (
    "model_id", "tokenizer_hash", "chat_template_hash", "rope_config_hash",
    "sliding_window_config", "attention_impl", "kv_layout", "quantization",
    "adapter_hash", "runtime_version", "compaction_policy_version",
    "position_policy_version", "channel_registry_version",
    "kernel_numeric_profile_hash",
)
HASH_FIELDS = (
    "tokenizer_hash",
    "chat_template_hash",
    "rope_config_hash",
    "kernel_numeric_profile_hash",
)
KV_LAYOUT_VALUES = frozenset(("mha", "gqa", "mqa", "mla_latent"))
QUANTIZATION_VALUES = frozenset(
    ("bf16", "bfloat16", "fp16", "float32", "int8", "gguf-q4_k_m")
)
POSITION_POLICY_VALUES = frozenset(
    ("pos-v1", POSITION_POLICY_VERSION)
)
ATTENTION_IMPL_VALUES = frozenset(("sdpa", "eager", "custom"))
_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SLIDING_WINDOW_PATTERN = re.compile(
    r"(?:local-[1-9][0-9]*|hybrid-[A-Za-z0-9][A-Za-z0-9._+-]*)\Z"
)
_ATTENTION_IMPL_PATTERN = re.compile(
    r"(?:flash-attn|paged-attn)-[A-Za-z0-9][A-Za-z0-9._+-]*\Z"
)


def _require_string(field: str, value: Any) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _require_sha256(field: str, value: Any) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(
            f"{field} must be canonical sha256:<64 lowercase hex>"
        )


@dataclass(frozen=True)
class CompatibilityFingerprint:
    model_id: str
    tokenizer_hash: str
    chat_template_hash: str
    rope_config_hash: str
    sliding_window_config: str
    attention_impl: str
    kv_layout: str
    quantization: str
    adapter_hash: Optional[str]
    runtime_version: str
    compaction_policy_version: str
    position_policy_version: str
    channel_registry_version: str
    kernel_numeric_profile_hash: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        values = self.to_dict()
        for field in (
            "model_id",
            "runtime_version",
            "compaction_policy_version",
        ):
            _require_string(field, values[field])
        for field in HASH_FIELDS:
            _require_sha256(field, values[field])
        if self.adapter_hash is not None:
            _require_sha256("adapter_hash", self.adapter_hash)
        if (
            type(self.sliding_window_config) is not str
            or (
                self.sliding_window_config != "none"
                and _SLIDING_WINDOW_PATTERN.fullmatch(
                    self.sliding_window_config
                )
                is None
            )
        ):
            raise ValueError(
                "sliding_window_config must be none, local-<positive-int>, "
                "or hybrid-<version>"
            )
        if (
            type(self.attention_impl) is not str
            or (
                self.attention_impl not in ATTENTION_IMPL_VALUES
                and _ATTENTION_IMPL_PATTERN.fullmatch(self.attention_impl)
                is None
            )
        ):
            raise ValueError("attention_impl is not a registered backend")
        if (
            type(self.kv_layout) is not str
            or self.kv_layout not in KV_LAYOUT_VALUES
        ):
            raise ValueError("kv_layout is not a registered layout")
        if (
            type(self.quantization) is not str
            or self.quantization not in QUANTIZATION_VALUES
        ):
            raise ValueError("quantization is not a registered value")
        if (
            type(self.position_policy_version) is not str
            or self.position_policy_version not in POSITION_POLICY_VALUES
        ):
            raise ValueError(
                "position_policy_version is not a registered value"
            )
        if (
            type(self.channel_registry_version) is not str
            or self.channel_registry_version != CHANNEL_REGISTRY_VERSION
        ):
            raise ValueError(
                "channel_registry_version is not a registered value"
            )

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CompatibilityFingerprint":
        if type(d) is not dict:
            raise ValueError("compatibility fingerprint must be an object")
        if set(d) != set(FIELDS):
            missing = sorted(set(FIELDS) - set(d))
            extra = sorted(set(d) - set(FIELDS))
            raise ValueError(
                "compatibility fingerprint fields mismatch: "
                f"missing={missing}, extra={extra}"
            )
        return cls(**{field: d[field] for field in FIELDS})

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return sha256_text(self.canonical_json())

    def matches(self, other: "CompatibilityFingerprint") -> bool:
        """All-or-nothing comparison (spec 6.2 note). No partial-match rules
        are registered in this MVP."""
        return self.to_dict() == other.to_dict()


def _rope_config_hash(config: Any) -> str:
    rope = {
        "rope_theta": getattr(config, "rope_theta", None),
        "rope_scaling": getattr(config, "rope_scaling", None),
        "max_position_embeddings": getattr(config, "max_position_embeddings", None),
        "head_dim": getattr(config, "head_dim", None),
        "partial_rotary_factor": getattr(config, "partial_rotary_factor", None),
    }
    return sha256_json(rope)


def _kv_layout(config: Any) -> str:
    n_q = getattr(config, "num_attention_heads", None)
    n_kv = getattr(config, "num_key_value_heads", n_q)
    if n_kv is None or n_q is None or n_kv == n_q:
        return "mha"
    return "mqa" if n_kv == 1 else "gqa"


def _sliding_window_config(config: Any) -> str:
    sw = getattr(config, "sliding_window", None)
    if not sw or not getattr(config, "use_sliding_window", False):
        return "none"
    return f"local-{sw}"


def _tokenizer_hash(tokenizer: Any) -> str:
    # Fast tokenizers serialize the full vocab/merges/normalizer determinism.
    try:
        return sha256_text(tokenizer.backend_tokenizer.to_str())
    except AttributeError:
        return sha256_json({"vocab": tokenizer.get_vocab()})


def kernel_numeric_profile_hash(device: str, dtype: str) -> str:
    """Operational definition per spec 4.6: hash over kernel/library versions,
    dtype + determinism flags, concatenated with a fixed-input forward-pass
    probe output at reduced precision (matmul+softmax chain)."""
    import torch

    env = {
        "torch": torch.__version__,
        "cuda": torch.version.cuda if torch.cuda.is_available() else None,
        "device_name": torch.cuda.get_device_name(0) if device.startswith("cuda") and torch.cuda.is_available() else device,
        "dtype": dtype,
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "tf32_matmul": torch.backends.cuda.matmul.allow_tf32 if torch.cuda.is_available() else None,
    }
    gen = torch.Generator(device="cpu").manual_seed(1234)
    x = torch.randn(8, 32, generator=gen)
    w = torch.randn(32, 32, generator=gen)
    torch_dtype = getattr(torch, dtype, torch.float32)
    dev = device if (not device.startswith("cuda")) or torch.cuda.is_available() else "cpu"
    probe = torch.softmax(x.to(dev, torch_dtype) @ w.to(dev, torch_dtype), dim=-1)
    # Reduced precision: round to 2 decimals so benign kernel noise cancels.
    quantized = [round(v, 2) for v in probe.float().flatten().tolist()]
    return sha256_json({"env": env, "probe": quantized})


def compute_fingerprint(
    config: Any,
    tokenizer: Any,
    *,
    model_id: str,
    attention_impl: str,
    quantization: str,
    device: str,
    adapter_hash: Optional[str] = None,
    compaction_policy_version: str = COMPACTION_POLICY_VERSION,
) -> CompatibilityFingerprint:
    """Compute the fingerprint for the live (model config, tokenizer, runtime).

    Must be called and stored before any KV artifact is written (BUILD.md
    ground rule 1)."""
    import torch
    import transformers

    return CompatibilityFingerprint(
        model_id=f"{model_id}#cfg={sha256_json(json.loads(config.to_json_string()))[:23]}",
        tokenizer_hash=_tokenizer_hash(tokenizer),
        chat_template_hash=sha256_text(getattr(tokenizer, "chat_template", None) or ""),
        rope_config_hash=_rope_config_hash(config),
        sliding_window_config=_sliding_window_config(config),
        attention_impl=attention_impl,
        kv_layout=_kv_layout(config),
        quantization=quantization,
        adapter_hash=adapter_hash,
        runtime_version=f"hf-transformers-{transformers.__version__}+torch-{torch.__version__}",
        compaction_policy_version=compaction_policy_version,
        position_policy_version=POSITION_POLICY_VERSION,
        channel_registry_version=CHANNEL_REGISTRY_VERSION,
        kernel_numeric_profile_hash=kernel_numeric_profile_hash(device, quantization),
    )
