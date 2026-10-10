"""P2.5 new-path correctness on the pinned frozen Qwen3-0.6B-Base (prereg v0.2
`3bf8737` § Implementation checks), CPU, tiny episodes. Skipped when the
pinned snapshot is not present locally.

OPT-IN integration test (codex 22677): it loads the real pinned model and needs > 3.5 GB RAM, so it is skipped by
default. Run it on purpose, memory-capped:
  M4_RUN_PINNED_QWEN_TESTS=1 systemd-run --user --scope -p MemoryMax=5200M -p MemorySwapMax=0 \
    .venv/bin/python -m pytest tests/test_sgm_p2p5_pretrained_qwen_residual_readout_path.py
(2026-10-10, merged mvp 2a16280: 7 passed in 40 s under that cap; record in
plans/reports/claude-261010-1605-m4-sgm-side-branch-merge-test-impact/.)"""

from __future__ import annotations

import os

import pytest
import torch

from memsub.sgm.backend import SourceRef
from memsub.sgm.pinned_pretrained_qwen3_backbone import P2P5_SGM_DEFAULTS, QWEN3_0P6B_BASE, snapshot_dir, verify_files
from memsub.sgm.synthetic_binding_task import sample_batch
from memsub.sgm.synthetic_pilot import PilotConfig, build
from memsub.sgm.synthetic_pilot_evaluation import evaluate, ingest, query_logits

pytestmark = [
    pytest.mark.skipif(os.environ.get("M4_RUN_PINNED_QWEN_TESTS") != "1",
                       reason="opt-in pinned-Qwen integration test (> 3.5 GB RAM): set M4_RUN_PINNED_QWEN_TESTS=1"),
    pytest.mark.skipif(not (snapshot_dir() / "model.safetensors").exists(),
                       reason="pinned Qwen3-0.6B-Base snapshot absent"),
]


def _cfg(**over):
    return PilotConfig(**{"backbone": "qwen3-0.6b-base", "readout": "residual_head", "n_bindings": 4,
                          "filler_len": 2, "batch": 2, **over})


@pytest.fixture(scope="module")
def learned():
    return build(_cfg(arm="learned"))


def test_pinned_files_and_geometry(learned):
    assert verify_files(snapshot_dir()) == QWEN3_0P6B_BASE["files"]
    runtime, _backend, head = learned
    c = runtime.cfg
    assert c.selected_layers == P2P5_SGM_DEFAULTS["selected_layers"] and c.resolved["num_hidden_layers"] == 28
    assert (c.memory_heads, c.key_dim, c.value_dim, c.feature_shift) == (4, 32, 32, 1)
    assert head.in_features == 1024 and head.out_features == 64
    assert _cfg(arm="learned").result_label() == "frozen-qwen3-0.6b-base+residual-head"
    assert _cfg(arm="oracle").result_label().endswith("+DIAGNOSTIC-oracle-address")


def test_backbone_is_frozen_and_never_optimized(learned):
    runtime, _backend, head = learned
    assert all(not p.requires_grad for p in runtime.backbone.parameters())
    backbone_ids = {id(p) for p in runtime.backbone.parameters()}
    trained = [p for p in list(runtime.adapters.parameters()) + list(head.parameters()) if p.requires_grad]
    assert trained and not backbone_ids & {id(p) for p in trained}


def test_disabled_sgm_matches_the_plain_pretrained_forward():
    runtime, backend, _head = build(_cfg(arm="memory_off", sgm={"local_recent_tokens": 64}))
    ids = torch.tensor([[151643, 198, 220, 271, 10001, 3005, 10002, 3010, 20001, 20002, 10001]])
    with torch.no_grad():
        state = backend.ingest_source(backend.new_state(1), ids[:, :-1], SourceRef("eq"), enabled=False)
        got = backend.evaluate_query(state, ids[:, -1:], enabled=False, detach=True, logits=False,
                                     final_hidden=True)["final_hidden"]
        ref = runtime.backbone.model(ids).last_hidden_state[:, -1].float()
    torch.testing.assert_close(got, ref, rtol=1e-4, atol=1e-4)


def test_output_path_gradients_reach_every_adapter_including_layer_27(learned):
    runtime, backend, head = learned
    p = _cfg(arm="learned")
    batch = sample_batch(p.task_spec(), "train", 2, torch.Generator().manual_seed(5))
    state = ingest(backend, batch, "learned", None, True, p.n_bindings)
    logits, _ = query_logits(backend, head, state, batch, 0, "learned", "residual_head", detach=False)
    runtime.adapters.zero_grad(set_to_none=True)
    torch.nn.functional.cross_entropy(logits, batch.labels[:, 0]).backward()
    for layer, adapter in runtime.adapters.items():
        for name, params in adapter.param_groups().items():
            norm = sum(float(q.grad.norm()) for q in params if q.grad is not None)
            assert norm > 0, f"no gradient reached L{layer}/{name}"
    assert head.weight.grad is not None and float(head.weight.grad.norm()) > 0


def test_memory_off_trains_only_its_head_on_the_local_only_residual():
    p = _cfg(arm="memory_off")
    runtime, backend, head = build(p)
    batch = sample_batch(p.task_spec(), "train", 2, torch.Generator().manual_seed(6))
    state = ingest(backend, batch, "memory_off", None, True, p.n_bindings)
    assert all(len(b) == 0 for b in state.banks.cells.values())       # SGM disabled during ingest
    logits, _ = query_logits(backend, head, state, batch, 0, "memory_off", "residual_head", detach=False)
    torch.nn.functional.cross_entropy(logits, batch.labels[:, 0]).backward()
    assert float(head.weight.grad.norm()) > 0
    assert all(q.grad is None for q in runtime.adapters.parameters())


def test_causality_and_query_snapshot_independence(learned):
    _runtime, backend, head = learned
    p = _cfg(arm="learned")
    a = sample_batch(p.task_spec(), "heldout", 2, torch.Generator().manual_seed(7))
    changed = a.source.clone()
    changed[:, 5:] = 20500                                       # perturb only positions >= 5
    with torch.no_grad():
        tr_a, tr_c = [], []
        full = backend.ingest_source(backend.new_state(2), a.source, SourceRef("a"), traces=tr_a)
        backend.ingest_source(backend.new_state(2), changed, SourceRef("c"), traces=tr_c)
        for t in range(a.source.shape[1]):                       # steps before 5 cannot see the future
            same = all(torch.equal(tr_a[t][k][l], tr_c[t][k][l])
                       for k in ("beta_projected", "write_coords") for l in tr_a[t][k])
            if t < 5:
                assert same, f"step {t} changed by a future token"
        assert any(not torch.equal(tr_a[t]["beta_projected"][l], tr_c[t]["beta_projected"][l])
                   for t in range(5, a.source.shape[1]) for l in tr_a[t]["beta_projected"])
        q1_alone, _ = query_logits(backend, head, full.detached(), a, 1, "learned", "residual_head", detach=True)
        state = full.detached()
        query_logits(backend, head, state, a, 0, "learned", "residual_head", detach=True)
        q1_after, _ = query_logits(backend, head, state, a, 1, "learned", "residual_head", detach=True)
    torch.testing.assert_close(q1_after, q1_alone, rtol=0, atol=0)


def test_evaluation_replay_is_identical(learned):
    _runtime, backend, head = learned
    p = _cfg(arm="learned")
    rows = [[], []]
    for r in rows:
        evaluate(backend, head, p.task_spec(), "learned", "residual_head", split="heldout", batches=1,
                 batch_size=2, seed=777_000, per_example=r)
    assert rows[0] == rows[1] and len(rows[0]) == 2 * p.n_queries
