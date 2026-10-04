"""Scientific contracts for the bounded text-memory experiment."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from experiments.context_gate.data import (audit_dataset, build_dataset, build_episode,
                                            canonical, digest, render_messages, retrieve)
from experiments.context_gate.learning import (arm_vectors, choose_threshold, fit_ensemble,
                                                paired_interval, utility_labels)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config():
    return json.loads((ROOT / "experiments/context_gate/config.json").read_text())


def test_dataset_is_reproducible_and_episode_disjoint(config):
    config["episodes"] = {"train": 6, "validation": 3, "calibration": 3, "test": 6, "ood": 3}
    rows = build_dataset(config)
    assert digest(rows) == digest(build_dataset(config))
    assert len(rows) == 63
    assert audit_dataset(rows)["cross_split_archive_overlap"] == 0
    for episode in {r["episode_id"] for r in rows}:
        views = [r for r in rows if r["episode_id"] == episode]
        assert len(views) == 3
        assert len({r["split"] for r in views}) == 1
        assert len({digest(r["archive"]) for r in views}) == 1
        assert len({tuple(r["retrieved_indices"]) for r in views}) == 1
    duplicate = copy.deepcopy(rows[0])
    duplicate["item_id"] += "-leak"
    duplicate["split"] = "test"
    with pytest.raises(AssertionError, match="crosses split"):
        audit_dataset(rows + [duplicate])


def test_hidden_annotations_never_render_and_retrieval_ignores_them():
    row = build_episode("train", 0, 42)[0]
    changed = copy.deepcopy(row)
    for field in ("item_id", "episode_id", "split", "family", "note_policy", "answer"):
        changed[field] = "FORBIDDEN_SENTINEL"
    changed["oracle_indices"] = [10]
    for arm in ("notes", "retrieved", "decision"):
        assert render_messages(row, arm) == render_messages(changed, arm)
        assert "FORBIDDEN_SENTINEL" not in str(render_messages(changed, arm))
    assert retrieve(row["question"], row["archive"]) == row["retrieved_indices"]


def test_oracle_contains_answer_and_latest_update_for_every_family():
    for split in ("train", "ood"):
        for number in range(12):
            for row in build_episode(split, number, 42):
                answer = row["options"]["ABCD".index(row["answer"])]
                evidence = " ".join(row["archive"][i]["text"] for i in row["oracle_indices"])
                assert answer in evidence
                assert len(row["oracle_indices"]) == (3 if row["family"] == "binding" else 2)
                assert len(row["retrieved_indices"]) == 4


def test_labels_distinguish_repair_harm_and_uncertainty():
    np.testing.assert_array_equal(utility_labels([0, 1, 0, 1], [1, 0, 0, 1]), [2, 0, 1, 1])


def test_threshold_prefers_fewer_retrievals_when_no_repair():
    op = choose_threshold(np.array([.1, .3, .7]), np.array([1, 0, 1]), np.array([1, 0, 1]), .05)
    assert op["retrieval_rate"] == 0
    op = choose_threshold(np.array([.1, .3, .7]), np.array([1, 1, 0]), np.array([1, 1, 1]), .05)
    assert op["retrieval_rate"] == pytest.approx(1/3)
    assert op["accuracy"] == 1


def test_costs_charge_initial_gate_and_full_rebuilt_prompt():
    cap = {"correct_notes": np.array([0, 1]), "correct_retrieved": np.array([1, 0]),
           "tokens_notes": np.array([100, 100]), "tokens_retrieved": np.array([160, 160]),
           "tokens_decision": np.array([110, 110]), "seconds_notes": np.ones(2),
           "seconds_retrieved": np.ones(2)*2, "seconds_decision": np.ones(2)*1.1}
    decision = np.array([True, False])
    correct, tokens, _ = arm_vectors("hidden_mlp", decision, cap)
    np.testing.assert_array_equal(correct, [1, 1])
    np.testing.assert_array_equal(tokens, [260, 100])
    _, tokens, _ = arm_vectors("self_raw", decision, cap)
    np.testing.assert_array_equal(tokens, [270, 210])
    _, tokens, _ = arm_vectors("always_retrieve", np.ones(2, dtype=bool), cap)
    np.testing.assert_array_equal(tokens, [160, 160])


def test_bootstrap_clusters_counterfactual_views():
    values = np.repeat([1., -1.], 3)
    groups = np.repeat(["a", "b"], 3)
    interval = paired_interval(values, groups, bootstrap=2000)
    assert interval["clusters"] == 2
    assert interval["estimate"] == 0
    assert interval["ci95"] == [-1., 1.]


def test_training_scaler_and_checkpoint_use_train_only(tmp_path, config):
    rng = np.random.default_rng(20)
    x = rng.normal(size=(120, 4)).astype(np.float32)
    y = np.where(x[:, 0] > .4, 2, np.where(x[:, 0] < -.4, 0, 1)).astype(np.int64)
    splits = np.asarray(["train"]*80 + ["validation"]*20 + ["test"]*20)
    x[-20:] = 100000  # Test feature distribution must not enter the scaler.
    config.update(epochs=5, patience=3)
    torch.set_num_threads(2)
    probabilities, info = fit_ensemble(x, y, splits, config, tmp_path, hidden=8)
    assert probabilities.shape == (120, 3)
    assert info["reload_equivalence"]
    checkpoint = torch.load(tmp_path / "seed-0.pt", weights_only=True)
    np.testing.assert_allclose(checkpoint["mean"].numpy(), x[:80].mean(0), atol=1e-6)
    assert all(s["weight_change_l2"] > 0 for s in info["seeds"])


def test_smoke_stops_on_no_repairs_or_bad_oracle(config):
    from experiments.context_gate.capture import smoke_verdict
    rows = build_dataset(config, smoke=True)
    n = len(rows)
    cap = {"correct_notes": np.ones(n), "correct_retrieved": np.ones(n),
           "correct_oracle": np.zeros(n), "hidden": np.zeros((n, 3)), "retrieved_tokens": np.ones(n)}
    for arm in ("notes", "retrieved", "oracle", "decision"):
        cap[f"format_valid_{arm}"] = np.ones(n)
    verdict = smoke_verdict(rows, cap, 1., config, 10.)
    assert not verdict["pass"]
    assert not verdict["checks"]["at_least_three_repairs"]
    assert not verdict["checks"]["oracle_accuracy_at_least_0_60"]


def test_last_hidden_lm_head_matches_full_forward_with_padding():
    from transformers import Qwen3Config, Qwen3ForCausalLM
    torch.manual_seed(3)
    cfg = Qwen3Config(vocab_size=64, hidden_size=32, intermediate_size=64,
                     num_hidden_layers=3, num_attention_heads=4, num_key_value_heads=2, head_dim=8)
    model = Qwen3ForCausalLM(cfg).eval()
    ids = torch.tensor([[0, 0, 3, 4, 5], [3, 4, 5, 6, 7]])
    mask = torch.tensor([[0, 0, 1, 1, 1], [1, 1, 1, 1, 1]])
    pos = (mask.cumsum(-1)-1).clamp_min(0)
    with torch.inference_mode():
        reference = model(ids, attention_mask=mask, position_ids=pos, use_cache=False).logits[:, -1]
        out = model.model(ids, attention_mask=mask, position_ids=pos, use_cache=False, output_hidden_states=True)
        actual = model.lm_head(out.last_hidden_state[:, -1])
    torch.testing.assert_close(actual, reference)


def test_replay_executes_only_chosen_branch(tmp_path, monkeypatch, config):
    from experiments.context_gate.capture import sequential_replay
    import experiments.context_gate.learning as learning
    rows = build_episode("test", 0, 42)
    config["replay_episodes"] = 1
    policy = {"thresholds": {name: {"threshold": .5} for name in ("confidence", "surface_mlp", "hidden_mlp")}}
    (tmp_path / "frozen-policy.json").write_bytes(canonical(policy))
    # Both trained controllers choose skip.
    monkeypatch.setattr(learning, "load_ensemble", lambda _: lambda x: np.tile([0., 1., 0.], (len(x), 1)))
    np.savez(tmp_path / "controller-scores.npz", **{f"decision_{arm}": np.full(3, arm == "always_retrieve")
             for arm in ("notes_only", "always_retrieve", "self_raw", "confidence", "surface_mlp", "hidden_mlp")})
    class Reader:
        def __init__(self):
            self.calls = []
        def infer(self, batch, arm="notes", hidden=False):
            assert arm != "oracle"
            self.calls.append((batch[0]["item_id"], arm, hidden))
            return {"tokens": np.array([10]), "probs": np.array([[0., 1.]]) if arm == "decision" else np.array([[1., 0., 0., 0.]]),
                    "hidden": np.zeros((1, 2)) if hidden else None}
    reader = Reader()
    monkeypatch.setattr(torch.cuda, "synchronize", lambda: None)
    cap = {"probs_notes": np.tile([1., 0., 0., 0.], (3, 1)), "probs_retrieved": np.tile([1., 0., 0., 0.], (3, 1))}
    result = sequential_replay(reader, rows, cap, config, tmp_path, lambda: None, lambda: None)
    assert sum(arm == "retrieved" for _, arm, _ in reader.calls) == 3
    assert sum(arm == "decision" for _, arm, _ in reader.calls) == 3
    assert result["arms"]["hidden_mlp"]["mean_input_tokens"] == 10
    assert result["arms"]["self_raw"]["mean_input_tokens"] == 20
