"""P2D Step 2 arms: filler-off writes, AddressMLP-only auxiliary loss,
continuous checkpoints (M4-SGM.md § P2D Step 2)."""

from __future__ import annotations

import json

import torch

from memsub.sgm.address_supervision import address_pair_loss, bound_value_positions
from memsub.sgm.synthetic_binding_task import sample_batch
from memsub.sgm.synthetic_pilot import PilotConfig, build, train
from memsub.sgm.synthetic_pilot_evaluation import ingest, query_logits
from memsub.sgm.synthetic_pilot_run import run_pilot


def _batch(p, n=2, seed=0):
    return sample_batch(p.task_spec(), "train", n, torch.Generator().manual_seed(seed))


def test_filler_off_skips_tail_writes_but_ingests_every_token():
    p = PilotConfig(arm="learned", n_bindings=4)
    _, backend, _ = build(p)
    b = _batch(p)
    with torch.no_grad():
        off = ingest(backend, b, "learned", filler_writes=False, n_bindings=4)
        from memsub.sgm.backend import SourceRef
        prefix = backend.ingest_source(backend.new_state(2), b.source[:, :12], SourceRef("p"))
    assert off.source_cursor == b.source.shape[1]               # all tokens read/ingested
    assert off.banks.cells.keys() == prefix.banks.cells.keys()
    for key, bank in off.banks.cells.items():                   # tail filler wrote nothing
        assert bank.keys() == prefix.banks.cells[key].keys()
        for c in bank:
            torch.testing.assert_close(bank[c], prefix.banks.cells[key][c], rtol=0, atol=0)


def test_aux_address_loss_reaches_only_address_mlp():
    p = PilotConfig(arm="learned", n_bindings=4, aux_address_lambda=0.1)
    runtime, backend, head = build(p)
    b = _batch(p)
    src: list = []
    state = ingest(backend, b, "learned", src)
    qtr = [query_logits(backend, head, state, b, q, "learned", "taskhead", detach=False)[1]
           for q in range(p.n_queries)]
    aux = address_pair_loss(runtime, src, qtr, bound_value_positions(b.source, b.query_keys, 4))
    assert aux.item() > 0
    aux.backward()
    for layer, adapter in runtime.adapters.items():
        for name, params in adapter.param_groups().items():
            got = [q.grad is not None and q.grad.abs().sum() > 0 for q in params]
            assert any(got) if name == "address_mlp" else not any(got), (layer, name)
        mlp = adapter.address_mlp
        assert mlp[0].weight.grad.abs().sum() > 0 and mlp[2].weight.grad.abs().sum() > 0
        # the final bias cancels in a_r - a_w, so the pair loss gives it exactly zero
        assert float(mlp[2].bias.grad.abs().sum()) == 0.0
    assert all(q.grad is None for q in head.parameters())


def test_bound_value_positions_point_at_the_queried_binding():
    p = PilotConfig(n_bindings=4)
    b = _batch(p, n=3)
    pos = bound_value_positions(b.source, b.query_keys, 4)
    for e in range(3):
        for q in range(p.n_queries):
            assert int(b.source[e, pos[e, q] - 1]) == int(b.query_keys[e, q])


def test_intermediate_checkpoint_equals_a_run_stopped_there():
    long = train(PilotConfig(arm="learned", n_bindings=4, steps=3, batch=2, checkpoint_steps=(2,)), log=lambda r: None)
    short = train(PilotConfig(arm="learned", n_bindings=4, steps=2, batch=2), log=lambda r: None)
    ck = long["checkpoints"][2]
    for k, v in short["runtime"].adapters.state_dict().items():
        torch.testing.assert_close(ck["adapters"][k], v, rtol=0, atol=0)
    for k, v in short["head"].state_dict().items():
        torch.testing.assert_close(ck["head"][k], v, rtol=0, atol=0)


def test_p2d_labels_and_checkpoint_artifacts(tmp_path):
    labels = {PilotConfig().result_label(), PilotConfig(filler_writes=False).result_label(),
              PilotConfig(aux_address_lambda=0.1).result_label(),
              PilotConfig(steps=4500, checkpoint_steps=(1500,)).result_label()}
    assert len(labels) == 4 and sum("DIAGNOSTIC" in l for l in labels) == 3
    p = PilotConfig(arm="learned", n_bindings=4, steps=2, batch=2, eval_every=2, eval_batches=1,
                    checkpoint_steps=(1,))
    m = run_pilot(p, tmp_path / "r", final_batches=1, final_batch_size=2, final_seed_base=9_300_011)
    man = json.loads((tmp_path / "r" / "run_manifest.json").read_text())
    assert man["final_eval_seed"] == 9_300_011 and set(man["checkpoint_parameters_sha256"]) == {"1"}
    assert (tmp_path / "r" / "per_example_results_step1.jsonl").exists()
    assert set(m["checkpoints"]["1"]) >= {"heldout_none", "heldout_bank_derange"}
