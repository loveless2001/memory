import pytest

from memsub.fingerprint import CompatibilityFingerprint, FIELDS


def _valid_fingerprint():
    return {
        "model_id": "test-model#cfg=sha256:1234567890abcdef",
        "tokenizer_hash": "sha256:" + "1" * 64,
        "chat_template_hash": "sha256:" + "2" * 64,
        "rope_config_hash": "sha256:" + "3" * 64,
        "sliding_window_config": "none",
        "attention_impl": "sdpa",
        "kv_layout": "gqa",
        "quantization": "bfloat16",
        "adapter_hash": None,
        "runtime_version": "hf-transformers-test+torch-test",
        "compaction_policy_version": "evict-oldest-nonsink-v1",
        "position_policy_version": "pos-v1-preserve-logical-rope",
        "channel_registry_version": "memchan-v1",
        "kernel_numeric_profile_hash": "sha256:" + "4" * 64,
    }


def test_compatibility_fingerprint_accepts_the_registered_live_schema():
    payload = _valid_fingerprint()

    fingerprint = CompatibilityFingerprint.from_dict(payload)

    assert fingerprint.to_dict() == payload
    assert tuple(fingerprint.to_dict()) == FIELDS


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("kernel_numeric_profile_hash", "not-a-hash"),
        ("attention_impl", False),
        ("adapter_hash", 42),
        ("tokenizer_hash", "sha256:" + "A" * 64),
        ("chat_template_hash", "sha256:" + "1" * 63),
        ("rope_config_hash", "1" * 64),
        ("kv_layout", "foreign"),
        ("quantization", "foreign"),
        ("sliding_window_config", "local-zero"),
        ("position_policy_version", "foreign"),
        ("channel_registry_version", "foreign"),
    ),
)
def test_compatibility_fingerprint_rejects_invalid_field_values(field, value):
    payload = _valid_fingerprint()
    payload[field] = value

    with pytest.raises(ValueError, match=field):
        CompatibilityFingerprint.from_dict(payload)


@pytest.mark.parametrize("mutation", ("missing", "extra", "not_dict"))
def test_compatibility_fingerprint_requires_exact_object_fields(mutation):
    payload = _valid_fingerprint()
    if mutation == "missing":
        payload.pop("runtime_version")
    elif mutation == "extra":
        payload["unexpected"] = "field"
    else:
        payload = list(payload.items())

    with pytest.raises(ValueError, match="fields|object"):
        CompatibilityFingerprint.from_dict(payload)


def test_direct_compatibility_fingerprint_construction_is_also_validated():
    payload = _valid_fingerprint()
    payload["adapter_hash"] = 42

    with pytest.raises(ValueError, match="adapter_hash"):
        CompatibilityFingerprint(**payload)
