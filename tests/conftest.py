"""Shared fixtures.

Two configurations selected by MEMSUB_REFERENCE=1:
  * local (default): tiny random-weight Qwen3-config model on CPU + real Qwen
    tokenizer — exercises every logic path including position/RoPE math;
  * reference: Qwen/Qwen3-4B-Instruct-2507 bf16 on GPU (run via Modal) —
    the BUILD.md Appendix B.1 acceptance configuration.
"""

from __future__ import annotations

import os

import pytest
import torch

REFERENCE = os.environ.get("MEMSUB_REFERENCE") == "1"
REFERENCE_MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
TOKENIZER_ID = REFERENCE_MODEL_ID  # same tokenizer family for tiny config

# A deterministic natural-text corpus, tiled to any length.
CORPUS_PARAGRAPH = (
    "The archive keeps every span of the conversation in content-addressed "
    "storage. Summaries are produced by the base model and indexed with "
    "embedding shadows so the selector can find them later. Position "
    "metadata distinguishes logical thread positions from physical cache "
    "slots, and the rotary offset is stored explicitly with the checkpoint. "
    "Attention sinks occupy the first four positions and are never evicted. ")


def corpus_token_ids(tokenizer, n_tokens: int) -> list[int]:
    ids = tokenizer.encode(CORPUS_PARAGRAPH, add_special_tokens=False)
    reps = (n_tokens // len(ids)) + 1
    return (ids * reps)[:n_tokens]


def build_tiny_runtime():
    from transformers import AutoModelForCausalLM, AutoTokenizer, Qwen3Config
    from memsub.runtime import HFModelRuntime

    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_ID)
    config = Qwen3Config(
        vocab_size=151936, hidden_size=64, intermediate_size=128,
        num_hidden_layers=4, num_attention_heads=4, num_key_value_heads=2,
        head_dim=16, max_position_embeddings=32768, tie_word_embeddings=True,
    )
    torch.manual_seed(0)
    model = AutoModelForCausalLM.from_config(config).to(torch.float32)
    return HFModelRuntime(model, tokenizer, model_id="tiny-qwen3-random-v1",
                          device="cpu", quantization="float32")


def build_reference_runtime():
    from memsub.runtime import HFModelRuntime
    return HFModelRuntime.load(REFERENCE_MODEL_ID, device="cuda",
                               dtype="bfloat16", attention_impl="sdpa")


@pytest.fixture(scope="session")
def runtime():
    return build_reference_runtime() if REFERENCE else build_tiny_runtime()


@pytest.fixture(scope="session")
def summarizer(runtime):
    if REFERENCE:
        from memsub.compilers import BaseModelSummarizer
        return BaseModelSummarizer(runtime)
    from memsub.compilers import StubTruncationSummarizer
    return StubTruncationSummarizer()


@pytest.fixture(scope="session")
def embedder():
    if REFERENCE:
        from memsub.compilers import Qwen3ShadowEmbedder
        return Qwen3ShadowEmbedder(device="cuda")
    from memsub.compilers import HashStubEmbedder
    return HashStubEmbedder()


@pytest.fixture()
def substrate(tmp_path, runtime, summarizer, embedder):
    from memsub.substrate_facade import SubstrateFacade
    return SubstrateFacade(tmp_path / "store", runtime, summarizer, embedder,
                           max_span_tokens=64 if not REFERENCE else 2048)


# Comparison tolerances: fp32 CPU is effectively exact; bf16 GPU kernels are
# nondeterministic — GT1 compares top-k token sets + max prob delta (BUILD.md).
GT1_TOP_K = 5
GT1_MAX_PROB_DELTA = 0.03 if REFERENCE else 1e-4
