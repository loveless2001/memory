"""M4-SGM P2 pilot: task splits, labels and an end-to-end smoke (SGM-19)."""

from __future__ import annotations

import json

import torch

from memsub.sgm.synthetic_binding_task import (
    KEY_RANGES, BindingTaskSpec, sample_batch, split_manifest)
from memsub.sgm.synthetic_pilot import PilotConfig
from memsub.sgm.synthetic_pilot_run import run_pilot


def test_split_families_are_disjoint_and_bindings_lie_beyond_the_window():
    spec = BindingTaskSpec(n_bindings=8, n_queries=4, filler_len=40)
    audit = split_manifest(spec, {"train": 0})["overlap_audit"]
    assert audit == {"key_family_overlap": 0, "filler_family_overlap": 0,
                     "key_value_filler_disjoint": True}
    b = sample_batch(spec, "heldout", 3, torch.Generator().manual_seed(0))
    lo, hi = KEY_RANGES["heldout"]
    assert ((b.query_keys >= lo) & (b.query_keys < hi)).all()
    assert b.source.shape[1] - (4 + 2 * 8) == 40 > 32       # filler > recent window
    for e in range(3):                                      # queried keys are in-episode
        assert set(b.query_keys[e].tolist()) <= set(b.source[e].tolist())


def test_sgm19_result_labels_keep_evidence_classes_apart():
    labels = {PilotConfig(arm="oracle").result_label(),
              PilotConfig(arm="learned").result_label(),
              PilotConfig(arm="learned", readout="lm").result_label()}
    assert len(labels) == 3
    assert PilotConfig(arm="oracle").result_label().startswith("DIAGNOSTIC")
    assert all("qwen" not in l.lower() for l in labels)


def test_pilot_run_emits_the_artifact_set(tmp_path):
    p = PilotConfig(arm="oracle", n_bindings=4, steps=2, batch=2, eval_every=2, eval_batches=1)
    m = run_pilot(p, tmp_path / "run", final_batches=1, final_batch_size=2)
    names = {f.name for f in (tmp_path / "run").iterdir()}
    assert names == {"run_manifest.json", "split_manifest.json", "routing_telemetry.jsonl",
                     "per_example_results.jsonl", "metrics.json", "report.md",
                     "trained_parameters.safetensors"}
    manifest = json.loads((tmp_path / "run" / "run_manifest.json").read_text())
    import hashlib
    blob = (tmp_path / "run" / "trained_parameters.safetensors").read_bytes()
    assert manifest["trained_parameters_sha256"] == hashlib.sha256(blob).hexdigest()
    assert len(manifest["memsub_source_sha256"]) == 64 and manifest["final_eval_seed"] == 9_100_003
    assert manifest["result_label"] == "DIAGNOSTIC-oracle-address"
    assert manifest["gradient_horizon_tokens"] == manifest["state_horizon_tokens"]
    assert set(m["final"]) >= {"heldout_none", "heldout_bank_derange", "heldout_coord_shuffle",
                               "heldout_read_offset", "heldout_query_off"}


def _rows(arm, intervention):
    from memsub.sgm.synthetic_pilot import build
    from memsub.sgm.synthetic_pilot_evaluation import evaluate
    p = PilotConfig(arm=arm, n_bindings=4)
    _, backend, head = build(p)
    rows: list = []
    res = evaluate(backend, head, p.task_spec(), arm, "taskhead", split="heldout", batches=2,
                   batch_size=3, seed=11, intervention=intervention, per_example=rows)
    return res, [(r["episode_hash"], r["key"], r["label"]) for r in rows]


def test_every_intervention_sees_identical_episodes():
    _, base = _rows("oracle", "none")
    for iv in ("bank_derange", "coord_shuffle", "read_offset", "query_off"):
        assert _rows("oracle", iv)[1] == base, iv


def test_bank_derange_is_effective_for_single_cell_and_coord_shuffle_is_na():
    import torch
    from memsub.sgm.synthetic_pilot import build
    from memsub.sgm.synthetic_pilot_evaluation import apply_intervention, ingest
    p = PilotConfig(arm="single_cell", n_bindings=4)
    _, backend, _ = build(p)
    batch = sample_batch(p.task_spec(), "train", 3, torch.Generator().manual_seed(0))
    state = ingest(backend, batch, "single_cell").detached()
    before = {k: dict(v) for k, v in state.banks.cells.items()}
    apply_intervention(state, "bank_derange", torch.Generator())
    for (b, l, h), bank in state.banks.cells.items():
        assert bank == before[((b + 1) % 3, l, h)]
        assert not torch.equal(bank[(0, 0)], before[(b, l, h)][(0, 0)])
    assert _rows("single_cell", "coord_shuffle")[0] is None


def test_bank_derange_rejects_singleton_batch():
    import pytest
    import torch
    from memsub.sgm.synthetic_pilot import build
    from memsub.sgm.synthetic_pilot_evaluation import apply_intervention, ingest
    p = PilotConfig(arm="single_cell", n_bindings=4)
    _, backend, _ = build(p)
    batch = sample_batch(p.task_spec(), "train", 1, torch.Generator().manual_seed(0))
    state = ingest(backend, batch, "single_cell").detached()
    with pytest.raises(ValueError):
        apply_intervention(state, "bank_derange", torch.Generator())
