"""HF transformers runtime: prefill, compacted continuation, scoring.

The decode loop passes position_ids = LOGICAL positions (RoPE) and
cache_position = PHYSICAL indices (mask sizing) — the position-decoupling
that makes compacted continuation exact for surviving tokens (spec 12,
B.7 tier (a)). model.generate() is never used; this loop is the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch

from ..fingerprint import CompatibilityFingerprint, compute_fingerprint
from .compacted_prefix_cache import CompactedPrefixCache


@dataclass
class StepLogits:
    token_id: int
    top_ids: list[int]
    top_probs: list[float]


class HFModelRuntime:
    def __init__(self, model, tokenizer, *, model_id: str, device: str,
                 quantization: str, attention_impl: str = "sdpa"):
        self.model = model.eval()
        self.tokenizer = tokenizer
        self.model_id = model_id
        self.device = device
        self.quantization = quantization
        self.attention_impl = attention_impl
        self._fingerprint: Optional[CompatibilityFingerprint] = None

    @classmethod
    def load(cls, model_id: str, *, device: str = "cpu",
             dtype: str = "bfloat16", attention_impl: str = "sdpa") -> "HFModelRuntime":
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=getattr(torch, dtype),
            attn_implementation=attention_impl).to(device)
        return cls(model, tokenizer, model_id=model_id, device=device,
                   quantization=dtype, attention_impl=attention_impl)

    def fingerprint(self) -> CompatibilityFingerprint:
        """Computed once and cached; required before any KV artifact write
        (BUILD.md ground rule 1)."""
        if self._fingerprint is None:
            self._fingerprint = compute_fingerprint(
                self.model.config, self.tokenizer, model_id=self.model_id,
                attention_impl=self.attention_impl,
                quantization=self.quantization, device=self.device)
        return self._fingerprint

    # -- prefill ---------------------------------------------------------------
    @torch.inference_mode()
    def prefill(self, token_ids: list[int]) -> tuple[CompactedPrefixCache, torch.Tensor]:
        """Full prefill of a fresh thread. Returns (cache, last-token logits)."""
        input_ids = torch.tensor([token_ids], dtype=torch.long, device=self.device)
        out = self.model(input_ids=input_ids, use_cache=True)
        cache = CompactedPrefixCache.from_prefill(out.past_key_values, len(token_ids))
        return cache, out.logits[0, -1].float()

    # -- compacted continuation --------------------------------------------------
    @torch.inference_mode()
    def forward_extend(self, cache: CompactedPrefixCache,
                       token_ids: list[int]) -> torch.Tensor:
        """Append token_ids to a (possibly compacted) cache; return logits
        [len(token_ids), vocab]. Positions: logical for RoPE, physical for mask."""
        n = len(token_ids)
        input_ids = torch.tensor([token_ids], dtype=torch.long, device=self.device)
        logical_start = cache.next_logical_position
        position_ids = torch.arange(
            logical_start, logical_start + n, device=self.device).unsqueeze(0)
        phys_start = cache.physical_length
        cache_position = torch.arange(
            phys_start, phys_start + n, device=self.device)
        attention_mask = torch.ones(
            (1, phys_start + n), dtype=torch.long, device=self.device)
        out = self.model(
            input_ids=input_ids, attention_mask=attention_mask,
            position_ids=position_ids, past_key_values=cache,
            cache_position=cache_position, use_cache=True)
        cache.note_appended(n)
        return out.logits[0].float()

    @torch.inference_mode()
    def continue_greedy(self, cache: CompactedPrefixCache, n_tokens: int,
                        first_logits: torch.Tensor, top_k: int = 10,
                        eos_token_id: Optional[int] = None) -> list[StepLogits]:
        """Greedy continuation for n_tokens, recording top-k per step (GT1
        compares top-k token sets + max prob delta, not bitwise)."""
        steps: list[StepLogits] = []
        logits = first_logits
        for _ in range(n_tokens):
            probs = torch.softmax(logits, dim=-1)
            top = torch.topk(probs, top_k)
            token_id = int(top.indices[0])
            steps.append(StepLogits(
                token_id=token_id,
                top_ids=[int(i) for i in top.indices],
                top_probs=[float(p) for p in top.values]))
            if eos_token_id is not None and token_id == eos_token_id:
                break
            logits = self.forward_extend(cache, [token_id])[-1]
        return steps

    # -- text helpers -------------------------------------------------------------
    @torch.inference_mode()
    def generate_text(self, prompt_messages: list[dict], max_new_tokens: int = 256) -> str:
        """Chat-template greedy generation from scratch (summaries, MCQ
        pipeline). Uses the same custom loop for consistency."""
        token_ids = self.tokenizer.apply_chat_template(
            prompt_messages, add_generation_prompt=True, tokenize=True)
        cache, logits = self.prefill(token_ids)
        eos = self.tokenizer.eos_token_id
        steps = self.continue_greedy(cache, max_new_tokens, logits, eos_token_id=eos)
        out_ids = [s.token_id for s in steps]
        if out_ids and out_ids[-1] == eos:
            out_ids = out_ids[:-1]
        return self.tokenizer.decode(out_ids, skip_special_tokens=True).strip()

    @torch.inference_mode()
    def answer_letter(self, context: str, question: str, options: list[str],
                      cache: Optional[CompactedPrefixCache] = None) -> str:
        """Single-letter MCQ answer by argmax over option letters
        (eq_policy_v1 = letter exact match, spec 17.4)."""
        letters = [chr(ord("A") + i) for i in range(len(options))]
        opts = "\n".join(f"{l}. {o}" for l, o in zip(letters, options))
        prompt = (f"{context}\n\nQuestion: {question}\n{opts}\n"
                  f"Answer with a single letter.\nAnswer:")
        ids = self.tokenizer.encode(prompt, add_special_tokens=False)
        if cache is not None:
            work = cache.clone_detached()
            logits = self.forward_extend(work, ids)[-1]
        else:
            _, logits = self.prefill(ids)
        letter_ids = [self.tokenizer.encode(" " + l, add_special_tokens=False)[-1]
                      for l in letters]
        scores = [float(logits[i]) for i in letter_ids]
        return letters[scores.index(max(scores))]
