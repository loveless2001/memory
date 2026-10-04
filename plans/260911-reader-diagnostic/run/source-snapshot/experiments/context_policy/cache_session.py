"""Single-sequence append-only cache correctness prototype for transformers 4.55.2.

The caller supplies complete token transcripts and an immutable reader identity.
Tokenization and model/adapter selection are outside this prototype. A changed
prefix or identity fails closed rather than silently rebuilding an expensive cache.
"""

from dataclasses import dataclass

import torch
from transformers import DynamicCache


def adapter_signature(model):
    active = getattr(model, "active_adapters", ())
    if callable(active):
        try:
            active = active()
        except ValueError:  # transformers base model with no loaded adapter
            active = ()
    disabled = tuple((name, module.disable_adapters) for name, module in model.named_modules()
                     if isinstance(getattr(module, "disable_adapters", None), bool))
    return tuple(active or ()), disabled


@dataclass(frozen=True)
class ReaderIdentity:
    model_revision: str
    adapter_sha256: str
    tokenizer_template_sha256: str
    runtime: str


@dataclass(frozen=True)
class AppendAccounting:
    prior_tokens: int
    fresh_tokens: int
    total_tokens: int


class AppendOnlySession:
    def __init__(self, model, identity: ReaderIdentity, max_tokens=8192, last_logit_only=False):
        if max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        self.model = model
        self.identity = identity
        self.max_tokens = max_tokens
        self.last_logit_only = last_logit_only
        self.adapter_signature = adapter_signature(model)
        self.cache = DynamicCache()
        self.token_ids = ()
        self.calls = []
        self.poisoned = False

    @torch.inference_mode()
    def append_transcript(self, full_token_ids, identity: ReaderIdentity):
        if self.poisoned:
            raise RuntimeError("partially updated cache: start a new session")
        if identity != self.identity:
            raise ValueError("reader or adapter identity changed")
        if self.model.training:
            raise ValueError("cache prototype requires model.eval()")
        if adapter_signature(self.model) != self.adapter_signature:
            raise ValueError("live adapter selection changed")
        ids = tuple(full_token_ids)
        if any(type(t) is not int or t < 0 for t in ids):
            raise ValueError("expected nonnegative integer token IDs")
        old = len(self.token_ids)
        if ids[:old] != self.token_ids:
            raise ValueError("cached token prefix changed")
        if len(ids) <= old:
            raise ValueError("append requires a nonempty unseen suffix")
        if len(ids) > self.max_tokens:
            raise ValueError("active context budget exceeded")
        if self.cache.get_seq_length() != old:
            raise RuntimeError("cache length differs from recorded token prefix")
        device = next(self.model.parameters()).device
        positions = torch.arange(old, len(ids), device=device)
        try:
            extra = {"logits_to_keep": 1} if self.last_logit_only else {}
            result = self.model(
                input_ids=torch.tensor([ids[old:]], device=device),
                attention_mask=torch.ones((1, len(ids)), dtype=torch.long, device=device),
                position_ids=positions.unsqueeze(0), cache_position=positions,
                past_key_values=self.cache, use_cache=True, **extra)
            self.cache = result.past_key_values
            if self.cache.get_seq_length() != len(ids):
                raise RuntimeError("model appended an unexpected number of cache positions")
            if not torch.isfinite(result.logits).all():
                raise RuntimeError("nonfinite continuation logits")
        except BaseException:
            self.poisoned = True
            raise
        accounting = AppendAccounting(old, len(ids)-old, len(ids))
        self.calls.append(accounting)
        self.token_ids = ids
        return result.logits[0], accounting

    @property
    def fresh_tokens(self):
        return sum(call.fresh_tokens for call in self.calls)


def parse_assistant_message(text):
    """Strict generated-message protocol; no silent fallback for malformed output."""
    text = text.strip()
    if text == "RETRIEVE":
        return "retrieve", None
    lines = text.splitlines()
    if lines and lines[0] == "ANSWER" and "\n".join(lines[1:]).strip():
        return "answer", "\n".join(lines[1:]).strip()
    raise ValueError("invalid action message")
