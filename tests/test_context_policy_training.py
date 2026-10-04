import pytest
import torch

from experiments.context_policy.training import supervised_loss


def sample():
    torch.manual_seed(42)
    logits = torch.randn(8, 9, requires_grad=True)
    ids = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7])
    answers = torch.tensor([False, False, False, False, False, False, True, True])
    groups = torch.tensor([-1, -1, 0, 0, -1, 1, -1, -1])
    return logits, ids, answers, groups


def test_answer_control_masks_routes_and_all_source_tokens():
    logits, ids, answers, groups = sample()
    loss, counts = supervised_loss(logits, ids, answers, groups, train_actions=False)
    loss.backward()
    assert counts['answer_tokens'] == 2 and counts['action_tokens'] == 0
    assert logits.grad[5:7].abs().sum() > 0
    assert logits.grad[:5].abs().sum() == 0 and logits.grad[7].abs().sum() == 0


def test_routing_loss_is_message_normalized_and_answer_exposure_matches():
    logits, ids, answers, groups = sample()
    loss, counts = supervised_loss(logits, ids, answers, groups, train_actions=True)
    ce = torch.nn.functional.cross_entropy(logits[:-1], ids[1:], reduction='none')
    expected = ce[5:7].mean() + (ce[1:3].mean() + ce[4]) / 2
    torch.testing.assert_close(loss, expected)
    assert counts['answer_tokens'] == 2 and counts['action_tokens'] == 3
    loss.backward()
    assert logits.grad[0].abs().sum() == 0 and logits.grad[3].abs().sum() == 0


def test_empty_and_overlapping_masks_rejected():
    logits, ids, answers, groups = sample()
    with pytest.raises(ValueError, match='no targets'):
        supervised_loss(logits, ids, torch.zeros_like(answers), groups, False)
    answers[2] = True
    with pytest.raises(ValueError, match='overlap'):
        supervised_loss(logits, ids, answers, groups, True)
