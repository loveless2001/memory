"""Training objective (COMPACTOR.md §2.2): forward KL, full-context teacher
to compact-cache student, answer-side tokens only, top-200 teacher support
with the gold token forced into support; prompt and padding masked.
"""

from __future__ import annotations

import torch

TOP_SUPPORT = 200


def forward_kl_on_answer(teacher_logits: torch.Tensor,
                         student_logits: torch.Tensor,
                         answer_mask: torch.Tensor,
                         gold_ids: torch.Tensor,
                         legacy_multiset_support: bool = False) -> torch.Tensor:
    """KL(teacher || student) per answer position, averaged over unmasked
    positions.

    teacher_logits/student_logits: [S, V] aligned positions;
    answer_mask: [S] bool (True on answer-side positions);
    gold_ids: [S] target token at each position (forced into support).

    legacy_multiset_support reproduces the pre-f214c0f objective (gold
    concatenated into support unconditionally, duplicating it when already
    top-k). Only for controlled replications of checkpoints shipped under
    that variant (PREPROBE.md E1); never for new production training."""
    t = teacher_logits[answer_mask].float()
    s = student_logits[answer_mask].float()
    gold = gold_ids[answer_mask]
    top = torch.topk(t, TOP_SUPPORT, dim=-1).indices           # [N, 200]
    if legacy_multiset_support:
        support = torch.cat([top, gold[:, None]], dim=-1)      # [N, 201]
        t_sup = torch.gather(t, 1, support)
        s_sup = torch.gather(s, 1, support)
        log_p = torch.log_softmax(t_sup, dim=-1)
        log_q = torch.log_softmax(s_sup, dim=-1)
        return (log_p.exp() * (log_p - log_q)).sum(-1).mean()
    # Force gold into support WITHOUT duplicating it: concatenating gold
    # unconditionally puts the same vocab id in the support twice whenever
    # gold is already top-k, turning both softmaxes into multiset
    # distributions that overweight gold. Instead, replace the
    # lowest-ranked support entry with gold only on rows where gold is
    # missing (keeps a fixed [N, 200] shape for gather).
    support = top.clone()
    missing = ~(top == gold[:, None]).any(dim=-1)
    support[missing, -1] = gold[missing]
    t_sup = torch.gather(t, 1, support)
    s_sup = torch.gather(s, 1, support)
    log_p = torch.log_softmax(t_sup, dim=-1)
    log_q = torch.log_softmax(s_sup, dim=-1)
    kl = (log_p.exp() * (log_p - log_q)).sum(-1)
    return kl.mean()
