"""P2 synthetic pilot: train SGM adapters on a frozen tiny random Qwen3 —
M4-SGM.md §13 (P0-P2 local work), §8 telemetry, §21 artifacts.

Result labels keep evidence classes apart (SGM-19):
  * "tiny-random-lm+taskhead"  — mechanism only (task head over memory reads);
  * "tiny-random-lm+lm-readout" — frozen random LM head readout;
  * "DIAGNOSTIC-oracle-address" — oracle arm, never a headline score.
None of these are frozen-Qwen (pretrained) results.

Full gradient, token-serial: state horizon == gradient horizon == source
length; fresh episodes every step, so state is always rebuilt under the
current adapter weights (no stale banks/KV across optimizer updates).
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

import torch
from torch import nn

from ..runtime.sgm_model_runtime import SGMModelRuntime
from .backend import SparseGrowingMemoryBackend
from .config import SGMConfig
from .synthetic_binding_task import N_VALUES, BindingTaskSpec, sample_batch
from .synthetic_pilot_evaluation import bank_telemetry, ingest, query_logits

ARMS = ("learned", "single_cell", "random_fixed", "oracle", "memory_off")


@dataclass
class PilotConfig:
    arm: str = "learned"
    readout: str = "taskhead"
    n_bindings: int = 16
    n_queries: int = 4
    filler_len: int = 40
    steps: int = 600
    batch: int = 16
    lr: float = 3e-3
    eval_every: int = 100
    eval_batches: int = 8
    seed: int = 0
    sgm: dict = field(default_factory=dict)  # SGMConfig overrides

    def result_label(self) -> str:
        if self.arm == "oracle":
            return "DIAGNOSTIC-oracle-address"
        return "tiny-random-lm+taskhead" if self.readout == "taskhead" else "tiny-random-lm+lm-readout"

    def task_spec(self) -> BindingTaskSpec:
        return BindingTaskSpec(self.n_bindings, self.n_queries, self.filler_len)


TINY_SGM_DEFAULTS = dict(selected_layers=(1, 3), memory_heads=2, key_dim=8, value_dim=8,
                         address_hidden=32, address_scale=8.0, local_recent_tokens=32,
                         pinned_sink_tokens=4, max_cells_per_bank=2048, feature_shift=2)


def build_tiny_backbone(seed: int = 0):
    """Same geometry as tests/conftest.py tiny model (frozen, random, fp32)."""
    from transformers import AutoModelForCausalLM, Qwen3Config
    config = Qwen3Config(vocab_size=151936, hidden_size=64, intermediate_size=128,
                         num_hidden_layers=4, num_attention_heads=4, num_key_value_heads=2,
                         head_dim=16, max_position_embeddings=32768, tie_word_embeddings=True)
    torch.manual_seed(seed)
    return AutoModelForCausalLM.from_config(config).to(torch.float32)


def build(pcfg: PilotConfig):
    if pcfg.arm not in ARMS:
        raise ValueError(f"unknown arm {pcfg.arm}")
    mode = {"memory_off": "learned"}.get(pcfg.arm, pcfg.arm)
    cfg = SGMConfig(**{**TINY_SGM_DEFAULTS, **pcfg.sgm, "address_mode": mode})
    runtime = SGMModelRuntime(build_tiny_backbone(0), cfg, seed=pcfg.seed)
    c = runtime.cfg
    torch.manual_seed(10_000 + pcfg.seed)
    head = nn.Linear(len(c.selected_layers) * c.memory_heads * c.value_dim, N_VALUES)
    return runtime, SparseGrowingMemoryBackend(runtime), head


def _group_norms(runtime) -> dict[str, float | None]:
    """Per-layer, per-group gradient norms; None = no gradient reached the
    group (e.g. the last layer's out_proj/alpha in the task-head arm)."""
    out: dict[str, float | None] = {}
    for layer, adapter in runtime.adapters.items():
        for name, params in adapter.param_groups().items():
            grads = [p.grad for p in params if p.grad is not None]
            out[f"L{layer}/{name}"] = (sum(float(g.pow(2).sum()) for g in grads) ** 0.5
                                       if grads else None)
    return out


def _snapshot(runtime) -> dict[str, list[torch.Tensor]]:
    return {f"L{l}/{n}": [p.detach().clone() for p in ps]
            for l, a in runtime.adapters.items() for n, ps in a.param_groups().items()}


def train(pcfg: PilotConfig, log=print, evaluate_fn=None) -> dict:
    """Train; returns {"telemetry": [...], "runtime", "backend", "head"}."""
    runtime, backend, head = build(pcfg)
    params = [p for p in list(runtime.adapters.parameters()) + list(head.parameters())
              if p.requires_grad]
    ids_before = [id(p) for p in params]
    opt = torch.optim.AdamW(params, lr=pcfg.lr, weight_decay=0.0)
    spec, gen = pcfg.task_spec(), torch.Generator().manual_seed(pcfg.seed)
    telemetry = []
    for step in range(pcfg.steps + 1):
        if evaluate_fn and step % pcfg.eval_every == 0:
            telemetry.append({"step": step, "eval": evaluate_fn(backend, head, step)})
            log(telemetry[-1])
        if step == pcfg.steps or pcfg.arm == "memory_off":
            continue  # memory_off has no trainable path that sees the bindings
        t0 = time.monotonic()
        batch = sample_batch(spec, "train", pcfg.batch, gen)
        state = ingest(backend, batch, pcfg.arm)          # graph kept into the bank
        loss, hits = 0.0, 0
        for q in range(spec.n_queries):
            logits, _ = query_logits(backend, head, state, batch, q, pcfg.arm,
                                     pcfg.readout, detach=False)
            loss = loss + nn.functional.cross_entropy(logits, batch.labels[:, q])
            hits += int((logits.argmax(-1) == batch.labels[:, q]).sum())
        loss = loss / spec.n_queries
        opt.zero_grad(set_to_none=True)
        loss.backward()
        logging = step % 10 == 0
        before = _snapshot(runtime) if logging else {}
        grads = _group_norms(runtime) if logging else {}
        opt.step()
        if logging:
            after = _snapshot(runtime)
            upd = {k: sum(float((a - b).norm()) for a, b in zip(after[k], before[k]))
                   for k in after}
            row = {"step": step, "loss": float(loss), "train_acc": hits / (pcfg.batch * spec.n_queries),
                   "grad_norm": grads, "update_norm": upd,
                   "alpha": {l: float(torch.sigmoid(a.alpha_logit)) for l, a in runtime.adapters.items()},
                   "sec_per_step": time.monotonic() - t0, **bank_telemetry(state)}
            telemetry.append(row)
            log(row)
    if [id(p) for p in params] != ids_before:
        raise RuntimeError("optimizer parameter identity changed")
    return {"telemetry": telemetry, "runtime": runtime, "backend": backend, "head": head,
            "config": asdict(pcfg), "sgm_config": runtime.cfg.to_json(),
            "policy_id": runtime.cfg.policy_id}
