"""Amendment PK supervisor + workers, end to end on the tiny CPU backbone (real subprocess
workers, real run_pilot, injected container faults). Outputs of an interrupted-and-resumed
slot must equal the uninterrupted slot bitwise on the scientific files (CPU)."""

import json

import pytest

from memsub.sgm import packed_slot_epoch_state as es
from memsub.sgm.packed_slot_supervisor import ContainerFault, SlotSupervisor

BASE = dict(arm="learned", readout="residual_head", backbone="tiny", device="cpu", n_bindings=4, filler_len=4,
            n_queries=4, steps=6, batch=2, lr=3e-3, eval_every=3, eval_batches=1, sgm={}, filler_writes=True,
            aux_address_lambda=0.0, checkpoint_steps=[], beta_bias_init=None, filler_len_schedule=[[0, 0], [3, 4]])
CELLS = {"learned-n4-s99": {**BASE, "seed": 99}, "learned-n4-s100": {**BASE, "seed": 100}}
EVAL = dict(final_batches=1, final_batch_size=2, final_seed_base=8_800_011, dev_seed=8_800_000,
            train_eval_seed_base=8_800_021)
ID = {"memsub": "test", "runner": "test", "env": "cpu"}
A, B = "learned-n4-s99", "learned-n4-s100"


def slot(root, epoch, admitted, faults=None, newer=lambda: False):
    return SlotSupervisor(root=root, cells=CELLS, epoch=epoch, admitted=admitted, identity=ID, checkpoint_every=2,
                          eval_cfg=EVAL, commit=lambda: None, reload=lambda: None, newer_start=newer,
                          ack_timeout_s=120, faults=faults, poll_s=0.01)


def outputs(root, cell):
    """Scientific files of the authoritative COMPLETE attempt (timing fields stripped)."""
    m = max(int(p.name.split("-")[1]) for p in (root / "cells" / cell).glob("epoch-*"))
    rec = es.read_record(root / "cells" / cell, m)
    assert rec["state"] == es.COMPLETE
    out = root / rec["outputs"]["attempt"] / "out"

    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if k not in ("sec_per_step", "wall_seconds")}
        return [strip(v) for v in x] if isinstance(x, list) else x
    return {"params": (out / "trained_parameters.safetensors").read_bytes(),
            "rows": (out / "per_example_results.jsonl").read_text(),
            "metrics": strip(json.loads((out / "metrics.json").read_text())),
            "telemetry": [strip(json.loads(r)) for r in (out / "routing_telemetry.jsonl").read_text().splitlines()]}


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    root = tmp_path_factory.mktemp("ref")
    assert slot(root, 1, [1]).run()["states"] == {A: es.COMPLETE, B: es.COMPLETE}
    return {c: outputs(root, c) for c in CELLS}


def test_container_loss_after_ack_resumes_bitwise(tmp_path, reference):
    with pytest.raises(ContainerFault):
        slot(tmp_path, 1, [1], faults={"after_ack": {"cell": A, "step": 4}}).run()
    r2 = slot(tmp_path, 2, [1, 2]).run()
    assert r2["states"] == {A: es.COMPLETE, B: es.COMPLETE}
    rec = es.read_record(tmp_path / "cells" / A, 2)
    assert rec["recovery"] == "resume" and rec["physical"]["resume_step"] == 4
    assert [link["step"] for link in rec["chain"]] == [2, 4, 6]
    for c in CELLS:
        assert outputs(tmp_path, c) == reference[c], c


def test_fault_during_eval_phase_recovers_eval_only_without_updates(tmp_path, reference):
    with pytest.raises(ContainerFault):
        slot(tmp_path, 1, [1], faults={"during_eval": {"cell": A}}).run()
    assert es.read_record(tmp_path / "cells" / A, 1)["state"] == es.TRAINED
    slot(tmp_path, 2, [1, 2]).run()
    rec = es.read_record(tmp_path / "cells" / A, 2)
    assert rec["recovery"] == "eval_only" and rec["physical"]["observed_updates"] == 0
    assert outputs(tmp_path, A) == reference[A]
    assert (es.epoch_dir(tmp_path / "cells" / A, 1) / "attempt-1").exists()      # partial attempt preserved


def test_failed_worker_stays_failed_and_cotenant_resumes(tmp_path, reference):
    with pytest.raises(ContainerFault):
        slot(tmp_path, 1, [1], faults={"worker_exit": {B: {"exit_at_update": 1}},
                                       "after_ack": {"cell": A, "step": 4, "require_terminal": [B]}}).run()
    rec_b = es.read_record(tmp_path / "cells" / B, 1)
    assert rec_b["state"] == es.FAILED and "worker exit 3" in rec_b["reason"]
    r2 = slot(tmp_path, 2, [1, 2]).run()
    assert r2["states"] == {A: es.COMPLETE, B: es.FAILED}
    assert not (es.epoch_dir(tmp_path / "cells" / B, 2) / "attempt-1").exists()   # never relaunched
    assert outputs(tmp_path, A) == reference[A]


def test_superseded_start_stops_and_writes_nothing_more(tmp_path):
    calls = {"n": 0}

    def newer():
        calls["n"] += 1
        return calls["n"] > 1                                 # a newer start appears after the first publish
    res = slot(tmp_path, 1, [1], newer=newer).run()
    assert res["status"] == "superseded"
    chains = [len(es.read_record(tmp_path / "cells" / c, 1)["chain"]) for c in CELLS]
    assert sum(chains) == 1                                   # exactly one generation was published
