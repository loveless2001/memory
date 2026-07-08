"""The KL training objective must build a SET support, not a multiset:
gold is forced in only when absent from the teacher top-200, never
duplicated (a duplicate vocab id double-counts that token's mass in both
softmaxes and silently overweights gold whenever it is already top-k)."""

import torch

from memsub.compactor.compactor_training_objective import (TOP_SUPPORT,
                                                           forward_kl_on_answer)

V = TOP_SUPPORT + 100  # vocab strictly larger than the support
N = 4


def _rand(seed):
    g = torch.Generator().manual_seed(seed)
    return torch.randn(N, V, generator=g)


def test_gold_already_in_top_k_is_not_double_counted():
    t, s = _rand(0), _rand(1)
    gold = t.argmax(dim=-1)  # gold is the teacher top-1 → already in support
    mask = torch.ones(N, dtype=torch.bool)
    loss = forward_kl_on_answer(t, s, mask, gold)

    # Reference: KL over the plain top-200 support (gold already inside,
    # nothing appended). The old cat([top, gold]) code diverges from this.
    top = torch.topk(t, TOP_SUPPORT, dim=-1).indices
    log_p = torch.log_softmax(t.gather(1, top), dim=-1)
    log_q = torch.log_softmax(s.gather(1, top), dim=-1)
    ref = (log_p.exp() * (log_p - log_q)).sum(-1).mean()
    assert torch.allclose(loss, ref), "gold in top-k must leave support as-is"


def test_gold_outside_top_k_enters_support_exactly_once():
    t, s = _rand(2), _rand(3)
    gold = torch.zeros(N, dtype=torch.long)
    t[:, 0] = t.min() - 1.0  # push gold below rank TOP_SUPPORT
    mask = torch.ones(N, dtype=torch.bool)
    loss = forward_kl_on_answer(t, s, mask, gold)
    assert torch.isfinite(loss)

    # Gold is in the support: moving the student's gold logit moves the loss.
    s_bumped = s.clone()
    s_bumped[:, 0] += 5.0
    assert not torch.isclose(loss, forward_kl_on_answer(t, s_bumped, mask, gold))

    # A token outside top-200 and != gold is NOT in the support: moving its
    # student logit must not move the loss (support stayed width-200 — the
    # lowest-ranked entry was replaced, nothing was appended).
    bottom = torch.topk(t, TOP_SUPPORT, dim=-1).indices  # per-row top ids
    for row in range(N):
        outside = next(i for i in range(1, V)
                       if i not in set(bottom[row].tolist()))
        s_out = s.clone()
        s_out[row, outside] += 5.0
        assert torch.isclose(loss, forward_kl_on_answer(t, s_out, mask, gold))
