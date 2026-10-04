"""CPU correctness of cache reuse; these tests do not certify a real 4B adapter."""

from dataclasses import replace

import pytest
import torch
from transformers import Qwen3Config, Qwen3ForCausalLM

from experiments.context_policy.cache_session import AppendOnlySession, ReaderIdentity, parse_assistant_message
from experiments.context_policy.preflight import paired_greedy


@pytest.fixture
def model():
    torch.manual_seed(9)
    cfg = Qwen3Config(vocab_size=96, hidden_size=32, intermediate_size=64,
                     num_hidden_layers=3, num_attention_heads=4, num_key_value_heads=2, head_dim=8)
    return Qwen3ForCausalLM(cfg).eval()


@pytest.fixture
def identity():
    return ReaderIdentity("tiny-test-model", "adapter-a", "template-a", "torch-2.7.1-transformers-4.55.2-fp32")


def test_multiple_cached_appends_match_full_transcript(model, identity):
    session = AppendOnlySession(model, identity)
    # Prefix, generated action, tool evidence, and final-answer continuation.
    parts = [[3, 7, 9, 12, 8], [30, 31], [70, 18, 23, 19], [40, 41, 42]]
    full = []
    for suffix in parts:
        old = len(full)
        full.extend(suffix)
        logits, accounting = session.append_transcript(full, identity)
        with torch.inference_mode():
            fresh = model(torch.tensor([full]), use_cache=False).logits[0, old:]
        torch.testing.assert_close(logits, fresh, atol=1e-6, rtol=1e-5)
        assert accounting.fresh_tokens == len(suffix)
        assert accounting.prior_tokens == old
        assert accounting.total_tokens == len(full)
        assert session.cache.get_seq_length() == len(full)
    assert session.fresh_tokens == len(full)
    assert session.fresh_tokens < sum(call.total_tokens for call in session.calls)


def test_changed_prefix_and_adapter_rejected_without_consuming_tokens(model, identity):
    session = AppendOnlySession(model, identity)
    session.append_transcript([3, 4, 5], identity)
    with pytest.raises(ValueError, match="prefix changed"):
        session.append_transcript([3, 8, 5, 6], identity)
    for field in ("model_revision", "adapter_sha256", "tokenizer_template_sha256", "runtime"):
        with pytest.raises(ValueError, match="identity changed"):
            session.append_transcript([3, 4, 5, 6], replace(identity, **{field: "different"}))
    assert session.fresh_tokens == session.cache.get_seq_length() == 3
    session.append_transcript([3, 4, 5, 6], identity)


def test_budget_empty_suffix_and_invalid_ids_fail_before_forward(model, identity):
    session = AppendOnlySession(model, identity, max_tokens=4)
    session.append_transcript([3, 4], identity)
    for ids, message in (([3, 4], "nonempty"), ([3, 4, 5, 6, 7], "budget"), ([3, 4, -1], "integer")):
        with pytest.raises(ValueError, match=message):
            session.append_transcript(ids, identity)
    assert session.fresh_tokens == 2


def test_training_model_rejected(model, identity):
    model.train()
    with pytest.raises(ValueError, match="eval"):
        AppendOnlySession(model, identity).append_transcript([1, 2], identity)


def test_last_logit_only_matches_full_and_live_adapter_changes_rejected(model, identity, monkeypatch):
    session = AppendOnlySession(model, identity, last_logit_only=True)
    logits, _ = session.append_transcript([3, 4, 5], identity)
    with torch.inference_mode():
        full = model(torch.tensor([[3, 4, 5]]), use_cache=False).logits[0, -1:]
    assert logits.shape == full.shape
    torch.testing.assert_close(logits, full)
    monkeypatch.setattr(model, "active_adapters", ["changed"])
    with pytest.raises(ValueError, match="live adapter"):
        session.append_transcript([3, 4, 5, 6], identity)


def test_partial_failure_poisons_session(model, identity, monkeypatch):
    session = AppendOnlySession(model, identity)
    session.append_transcript([3, 4], identity)
    original = model.forward
    def fail_after_update(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("simulated failure after cache mutation")
    monkeypatch.setattr(model, "forward", fail_after_update)
    with pytest.raises(RuntimeError, match="simulated failure"):
        session.append_transcript([3, 4, 5], identity)
    assert session.poisoned
    with pytest.raises(RuntimeError, match="partially updated"):
        session.append_transcript([3, 4, 5, 6], identity)


@pytest.mark.parametrize("message,expected", [("RETRIEVE", ("retrieve", None)),
                                               ("ANSWER\nNot established by the history.", ("answer", "Not established by the history."))])
def test_generated_message_protocol(message, expected):
    assert parse_assistant_message(message) == expected


@pytest.mark.parametrize("message", ["R", "A", "retrieve", "RETRIEVE\nAnd the answer is 5", "ANSWER", "ANSWER\n", "Here is my answer."])
def test_invalid_action_is_not_silently_recovered(message):
    with pytest.raises(ValueError, match="invalid action"):
        parse_assistant_message(message)


def test_paired_greedy_stops_each_branch_at_its_own_eos():
    def logits(token):
        result = torch.zeros(5)
        result[token] = 1
        return result
    calls = []
    def stopped_branch(token):
        raise AssertionError("must not continue after EOS")
    def continuing_branch(token):
        calls.append(token)
        return logits(4)
    cached, full = paired_greedy(logits(4), logits(2), stopped_branch,
                               continuing_branch, 4, lambda: None)
    assert cached == [4] and full == [2, 4] and calls == [2]
