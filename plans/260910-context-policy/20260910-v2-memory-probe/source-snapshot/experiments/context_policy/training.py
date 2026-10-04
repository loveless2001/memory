"""Matched answer exposure and separately normalized routing loss for LoRA SFT.

This module consumes grounded, audited demonstrations. It does not manufacture
action labels from gold answers or permit external test data as training input.
"""

from dataclasses import dataclass

import torch
import torch.nn.functional as F

from .cache_session import parse_assistant_message


@dataclass
class EncodedTrace:
    input_ids: list[int]
    answer_mask: list[bool]
    action_groups: list[int]


def encode_trace(tokenizer, messages, action_supervised, max_tokens=8192):
    """Encode assistant-only targets; every source/tool/private token is masked.

    action_supervised is a boolean per assistant message. False preserves a
    grounded answer target but masks its uncertain action label. Routing groups
    are normalized independently so long marker spellings do not carry more
    weight. Caller must remove any unsupported answer target before encoding.
    """
    full = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
    if len(full) > max_tokens:
        raise ValueError("training trace exceeds context cap; no silent truncation")
    answer_mask = [False] * len(full)
    action_groups = [-1] * len(full)
    assistant_count = sum(m["role"] == "assistant" for m in messages)
    if len(action_supervised) != assistant_count or any(type(x) is not bool for x in action_supervised):
        raise ValueError("one explicit action supervision flag required per assistant")
    group = 0
    for i, message in enumerate(messages):
        if message["role"] != "assistant":
            continue
        action, answer = parse_assistant_message(message["content"])
        before = tokenizer.apply_chat_template(messages[:i], tokenize=True, add_generation_prompt=True)
        through = tokenizer.apply_chat_template(messages[:i+1], tokenize=True, add_generation_prompt=False)
        if full[:len(before)] != before or full[:len(through)] != through:
            raise ValueError("training chat template changed a previously encoded prefix")
        start, end = len(before), len(through)
        if action == "answer":
            # The newline is part of the marker and masked in answer-only SFT.
            marker = tokenizer.encode("ANSWER\n", add_special_tokens=False)
            if full[start:start+len(marker)] != marker:
                raise ValueError("routing marker tokenization is not prefix stable")
            marker_end = start + len(marker)
            answer_mask[marker_end:end] = [True] * (end-marker_end)
        else:
            marker_end = end
        if action_supervised[group]:
            action_groups[start:marker_end] = [group] * (marker_end-start)
        group += 1
    if not any(answer_mask) and not any(g >= 0 for g in action_groups):
        raise ValueError("trace has no supervised targets")
    return EncodedTrace(full, answer_mask, action_groups)


def supervised_loss(logits, token_ids, answer_mask, action_groups, train_actions):
    """Single unpadded trace: next-token answer mean + per-message action mean."""
    if logits.ndim != 2 or token_ids.ndim != 1 or logits.shape[0] != token_ids.shape[0]:
        raise ValueError("expected one unpadded [tokens, vocabulary] trace")
    if answer_mask.shape != token_ids.shape or action_groups.shape != token_ids.shape:
        raise ValueError("loss masks must match token IDs")
    if (answer_mask & (action_groups >= 0)).any():
        raise ValueError("answer and action targets overlap")
    targets = token_ids[1:]
    answer = answer_mask[1:].bool()
    groups = action_groups[1:]
    active = answer | ((groups >= 0) if train_actions else torch.zeros_like(answer))
    if not active.any():
        raise ValueError("no targets for this training arm")
    # Only materialize fp32 cross entropy for supervised positions.
    ce = F.cross_entropy(logits[:-1][active].float(), targets[active], reduction="none")
    active_answer, active_groups = answer[active], groups[active]
    zero = ce.sum() * 0
    answer_loss = ce[active_answer].mean() if active_answer.any() else zero
    per_action = [ce[active_groups == group].mean() for group in active_groups.unique().tolist() if group >= 0]
    action_loss = torch.stack(per_action).mean() if train_actions and per_action else zero
    return answer_loss + action_loss, {"answer_tokens": int(active_answer.sum()),
                                       "action_tokens": int((active_groups >= 0).sum()) if train_actions else 0,
                                       "answer_loss": float(answer_loss.detach()),
                                       "action_loss": float(action_loss.detach())}
