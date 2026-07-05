"""Builders for the two supported configurations (BUILD.md Appendix B.1).

reference: Qwen/Qwen3-4B-Instruct-2507 bf16 + Qwen3-Embedding-0.6B (shadow-v1)
           on a 24GB-class GPU — the acceptance configuration (run on Modal).
tiny:      random-weight Qwen3-config model on CPU with stub summarizer and
           hash embedder — logic-path validation on resource-limited machines.
"""

from __future__ import annotations

import os

REFERENCE_MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
REFERENCE_EMBEDDING_MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"


def is_reference() -> bool:
    return os.environ.get("MEMSUB_REFERENCE") == "1"


def build_runtime(reference: bool | None = None):
    from .runtime import HFModelRuntime
    if reference is None:
        reference = is_reference()
    if reference:
        return HFModelRuntime.load(REFERENCE_MODEL_ID, device="cuda",
                                   dtype="bfloat16", attention_impl="sdpa")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, Qwen3Config
    tokenizer = AutoTokenizer.from_pretrained(REFERENCE_MODEL_ID)
    config = Qwen3Config(
        vocab_size=151936, hidden_size=64, intermediate_size=128,
        num_hidden_layers=4, num_attention_heads=4, num_key_value_heads=2,
        head_dim=16, max_position_embeddings=32768, tie_word_embeddings=True)
    torch.manual_seed(0)
    model = AutoModelForCausalLM.from_config(config).to(torch.float32)
    return HFModelRuntime(model, tokenizer, model_id="tiny-qwen3-random-v1",
                          device="cpu", quantization="float32")


def build_summarizer(runtime, reference: bool | None = None):
    if reference is None:
        reference = is_reference()
    if reference:
        from .compilers import BaseModelSummarizer
        return BaseModelSummarizer(runtime)
    from .compilers import StubTruncationSummarizer
    return StubTruncationSummarizer()


def build_embedder(reference: bool | None = None):
    if reference is None:
        reference = is_reference()
    if reference:
        from .compilers import Qwen3ShadowEmbedder
        return Qwen3ShadowEmbedder(REFERENCE_EMBEDDING_MODEL_ID, device="cuda")
    from .compilers import HashStubEmbedder
    return HashStubEmbedder()


def build_substrate(root, reference: bool | None = None):
    from .substrate_facade import SubstrateFacade
    runtime = build_runtime(reference)
    return SubstrateFacade(
        root, runtime, build_summarizer(runtime, reference),
        build_embedder(reference),
        max_span_tokens=2048 if (reference if reference is not None else is_reference()) else 64)
