"""Readout probe: path-exact validator + taskhead None-vs-zero graph contract (proposal v0.2 §8.1/§8.2; codex 21750).

Tiny CPU backbone only: no Qwen, no forward pass of the pretrained model, no GPU, no Modal.
"""

import copy
import dataclasses
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

import pytest
import torch
import torch.nn.functional as F

from memsub.sgm import packed_slot_cell_output_validation as V
from memsub.sgm import packed_slot_epoch_state as es
from memsub.sgm.packed_slot_supervisor import expand_cells
from memsub.sgm.synthetic_binding_task import sample_batch
from memsub.sgm.synthetic_pilot import PilotConfig, _group_norms, build
from memsub.sgm.synthetic_pilot_evaluation import ingest, query_logits
from memsub.sgm.synthetic_pilot_run import run_pilot, source_tree_sha256

ROOT = Path(__file__).resolve().parents[1]
TINY_LAYERS = ["1", "3"]
TINY_EVAL = {"final_batches": 1, "final_batch_size": 2, "final_seed_base": 777_100, "dev_seed": 777_001,
             "train_eval_seed_base": 777_200}


def load(rel, name):
    s = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


PV = load("scripts/sgm-p2p5-readout-probe-output-validation.py", "probe_validation")
L = load("modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-logic.py", "probe_slot_logic")
CAMPAIGN_SCHEMA = json.loads((ROOT / "configs/m4_sgm_p2p5_campaign_output_schema.json").read_text())["by_arm"]["learned"]


def tiny_pilot(readout: str, seed: int = 0) -> dict:
    base = json.loads((ROOT / "configs/m4_sgm_p2p5_grid.json").read_text())["base"]
    return {**base, "readout": readout, "backbone": "tiny", "device": "cpu", "n_bindings": 4, "batch": 2,
            "steps": 8, "eval_every": 4, "filler_len_schedule": [[0, 0], [4, 40]], "seed": seed}


def run_tiny(readout: str, d: Path) -> tuple[Path, dict]:
    out = d / f"out-{readout}"
    run_pilot(PilotConfig(**tiny_pilot(readout)), out, final_batches=1, final_batch_size=2,
              final_seed_base=TINY_EVAL["final_seed_base"], dev_seed=TINY_EVAL["dev_seed"],
              train_eval_seed_base=TINY_EVAL["train_eval_seed_base"])
    return out, json.loads((out / "run_manifest.json").read_text())["pilot_config"]


@pytest.fixture(scope="module")
def runs():
    with tempfile.TemporaryDirectory() as d:
        yield {r: run_tiny(r, Path(d)) for r in ("taskhead", "residual_head")}


def done_of(out: Path) -> dict:
    return {f: hashlib.sha256((out / f).read_bytes()).hexdigest() for f in V.REQUIRED_OUTPUTS}


def tiny_schema():
    return PV.contract_schema(CAMPAIGN_SCHEMA, TINY_LAYERS)


def train_rows(out: Path) -> list:
    return [json.loads(x) for x in (out / "routing_telemetry.jsonl").read_text().splitlines() if "loss" in json.loads(x)]


# ---- grid and data-stream sameness --------------------------------------------------------------------------------

def test_grid_is_exactly_the_p2p5_learned_n32_cells_with_only_the_readout_changed():
    probe = L.probe_cells(json.loads((ROOT / L.GRID_FILE).read_text()))
    p2p5 = expand_cells(json.loads((ROOT / "configs/m4_sgm_p2p5_grid.json").read_text()))
    for s in (0, 1):
        want = {**p2p5[f"learned-n32-s{s}"], "readout": "taskhead"}
        assert probe[f"taskhead-learned-n32-s{s}"] == want


def test_training_data_stream_does_not_depend_on_the_readout():
    a, b = PilotConfig(**{**tiny_pilot("taskhead"), "n_bindings": 32}), PilotConfig(**{**tiny_pilot("residual_head"), "n_bindings": 32})
    assert a.task_spec() == b.task_spec()
    ga, gb = torch.Generator().manual_seed(0), torch.Generator().manual_seed(0)
    for _ in range(3):
        x, y = sample_batch(a.task_spec(), "train", 16, ga), sample_batch(b.task_spec(), "train", 16, gb)
        assert all(torch.equal(getattr(x, f.name), getattr(y, f.name)) for f in dataclasses.fields(x))


# ---- the graph contract (a)/(b)/(c) ------------------------------------------------------------------------------

def test_contract_a_last_layer_out_proj_alpha_grad_is_none_and_update_norm_is_zero(runs):
    out, _ = runs["taskhead"]
    rows = train_rows(out)
    metrics = json.loads((out / "metrics.json").read_text())
    for r in rows + [metrics["train_last"]]:
        nulls = {k for k, v in r["grad_norm"].items() if v is None}
        assert nulls == {"L3/out_proj", "L3/alpha"}
        assert r["update_norm"]["L3/out_proj"] == 0.0 and r["update_norm"]["L3/alpha"] == 0.0
        assert all(isinstance(v, float) for v in r["update_norm"].values())


def test_residual_head_control_has_no_null_gradients(runs):
    out, _ = runs["residual_head"]
    assert all(v is not None for r in train_rows(out) for v in r["grad_norm"].values())


def _step_group_norms(read_offset: float) -> dict:
    p = PilotConfig(**{**tiny_pilot("taskhead"), "n_bindings": 4})
    runtime, backend, head = build(p)
    batch = sample_batch(p.task_spec(), "train", 2, torch.Generator().manual_seed(0))
    runtime.diag_read_offset = read_offset          # every read (ingest AND query) of this step
    state = ingest(backend, batch, "learned")
    logits, _ = query_logits(backend, head, state, batch, 0, "learned", "taskhead", detach=False)
    F.cross_entropy(logits, batch.labels[:, 0]).backward()
    runtime.diag_read_offset = 0.0
    return _group_norms(runtime)


def test_contract_b_forced_read_miss_leaves_write_path_grads_none_while_read_path_stays_numeric():
    hit, miss = _step_group_norms(0.0), _step_group_norms(1000.0)
    write = [f"L{l}/{g}" for l in TINY_LAYERS for g in PV.NUM_OR_NULL_GROUPS]
    assert any(hit[k] is not None for k in write)               # control: reads reach written cells
    assert all(miss[k] is None for k in write)                  # (b): no read touches a written cell
    for l in TINY_LAYERS:
        assert miss[f"L{l}/q_proj"] is not None and miss[f"L{l}/address_mlp"] is not None   # (c)
    assert miss["L3/out_proj"] is None and miss["L3/alpha"] is None                           # (a)


# ---- schemas -----------------------------------------------------------------------------------------------------

def test_campaign_extractor_cannot_represent_a_taskhead_run(runs):
    with pytest.raises(ValueError, match="inconsistent schemas"):
        V.output_schemas(runs["taskhead"][0], runs["taskhead"][1])


def test_probe_schema_accepts_taskhead_and_rejects_the_residual_control(runs):
    assert PV.schema_problem(runs["taskhead"][0], tiny_schema()) is None
    assert "metrics" in PV.schema_problem(runs["residual_head"][0], tiny_schema())


def test_conforms_unit_cases():
    assert PV.conforms(PV.NUM, PV.NUM_OR_NULL) and PV.conforms(PV.NULL, PV.NUM_OR_NULL)
    assert not PV.conforms(PV.NUM, PV.NULL) and not PV.conforms(PV.NULL, PV.NUM)
    assert not PV.conforms({"str": True}, PV.NUM_OR_NULL)
    assert not PV.conforms({"dict": {"a": PV.NUM}}, {"dict": {"a": PV.NUM, "b": PV.NUM}})
    assert PV.conforms({"list": None}, {"list": None}) and not PV.conforms({"list": PV.NUM}, {"list": None})


def test_contract_schema_shape_and_fail_closed():
    s = tiny_schema()
    for kind, path in PV.GRAD_PATHS:
        node = s[kind]
        for k in path:
            node = node["dict"][k]
        g = node["dict"]
        assert g["L3/out_proj"] == PV.NULL and g["L3/alpha"] == PV.NULL
        assert all(g[f"L{l}/{x}"] == PV.NUM_OR_NULL for l in TINY_LAYERS for x in PV.NUM_OR_NULL_GROUPS)
        assert g["L1/out_proj"] == PV.NUM and g["L1/q_proj"] == PV.NUM and g["L3/address_mlp"] == PV.NUM
    upd = s["telemetry_train_row"]["dict"]["update_norm"]["dict"]
    assert set(map(json.dumps, upd.values())) == {json.dumps(PV.NUM)}
    broken = copy.deepcopy(CAMPAIGN_SCHEMA)
    del broken["telemetry_train_row"]["dict"]["grad_norm"]["dict"]["L{L}/beta"]
    with pytest.raises(ValueError, match="contract leaf"):
        PV.contract_schema(broken, TINY_LAYERS)


def test_tiny_build_registry_keeps_disconnected_parameters_and_head_width():
    reg = V.parameter_registry(tiny_pilot("taskhead"))
    assert "adapters.3.out_proj.weight" in reg["grad_names_shapes"] and "adapters.3.alpha_logit" in reg["grad_names_shapes"]
    assert reg["state_names_shapes"]["head.weight"] == [64, 2 * 2 * 8]     # tiny: 2 layers x 2 heads x d8


# ---- full validator ----------------------------------------------------------------------------------------------

def _validate(out, pilot, registry, schema):
    return PV.validate_probe_outputs(out, done_of(out), pilot, TINY_EVAL, source_tree_sha256(ROOT / "memsub"),
                                     registry, schema)


def _mutated(out: Path, d: Path, edit) -> Path:
    new = d / "mut"
    new.mkdir()
    for f in out.iterdir():
        (new / f.name).write_bytes(f.read_bytes())
    rows = [json.loads(x) for x in (new / "routing_telemetry.jsonl").read_text().splitlines()]
    edit(next(r for r in rows if "loss" in r))
    (new / "routing_telemetry.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return new


@pytest.mark.parametrize("edit,ok", [
    (lambda r: r["grad_norm"].__setitem__("L1/k_proj", None), True),        # (b) number-or-null
    (lambda r: r["grad_norm"].__setitem__("L3/beta", None), True),
    (lambda r: r["grad_norm"].__setitem__("L1/q_proj", None), False),       # (c) numeric only
    (lambda r: r["grad_norm"].__setitem__("L1/out_proj", None), False),     # out_proj below the last layer
    (lambda r: r["grad_norm"].__setitem__("L3/out_proj", 0.5), False),      # (a) required null
    (lambda r: r["update_norm"].__setitem__("L1/k_proj", None), False),     # update_norm never null
    (lambda r: r["update_norm"].__setitem__("L3/alpha", None), False),
])
def test_validator_enforces_the_contract_on_every_training_row(runs, edit, ok):
    out, pilot = runs["taskhead"]
    reg = V.parameter_registry(pilot)
    with tempfile.TemporaryDirectory() as d:
        problem = _validate(_mutated(out, Path(d), edit), pilot, reg, tiny_schema())
    assert (problem is None) == ok, problem


def test_validator_keeps_the_campaign_checks_and_needs_registry_and_schema(runs):
    out, pilot = runs["taskhead"]
    reg = V.parameter_registry(pilot)
    assert _validate(out, pilot, reg, tiny_schema()) is None
    assert "registry and schema" in _validate(out, pilot, None, tiny_schema())
    bad = copy.deepcopy(reg)
    bad["state_names_shapes"]["head.weight"] = [64, 99]
    assert "registry" in _validate(out, pilot, bad, tiny_schema())
    assert "pilot_config" in _validate(out, {**pilot, "lr": 0.1}, reg, tiny_schema())


def test_probe_supervisor_complete_transition_uses_the_probe_validator(monkeypatch, tmp_path):
    sup = PV.ProbeSlotSupervisor(root=tmp_path, cells={"c": {"steps": 8}}, epoch=1, admitted=[1], identity={"memsub": "m"},
                                 checkpoint_every=50, eval_cfg=TINY_EVAL, commit=lambda: None, reload=lambda: None,
                                 registry={}, schema={})
    sup.records["c"] = {"state": es.TRAINED}
    att = sup.attempt_dir("c")
    att.mkdir(parents=True)
    (att / "done.json").write_text(json.dumps({"outputs": {}}))
    seen = {}
    monkeypatch.setattr(PV, "validate_probe_outputs", lambda *a, **k: seen.setdefault("called", "probe-sentinel"))
    monkeypatch.setattr(V, "validate_cell_outputs", lambda *a, **k: pytest.fail("campaign validator used directly"))
    published = []
    monkeypatch.setattr(sup, "publish", lambda cell, mutate: published.append(mutate))
    sup.finish("c", 0)
    rec = {"state": es.TRAINED, "chain": [], "history": []}
    published[-1](rec)
    assert seen["called"] == "probe-sentinel" and rec["state"] == es.FAILED and "probe-sentinel" in rec["reason"]


# ---- end to end: real ProbeSlotSupervisor + subprocess workers (tiny CPU) ---------------------------------------

E2E_BASE = dict(arm="learned", readout="taskhead", backbone="tiny", device="cpu", n_bindings=4, filler_len=4,
                n_queries=4, steps=6, batch=2, lr=3e-3, eval_every=3, eval_batches=1, sgm={}, filler_writes=True,
                aux_address_lambda=0.0, checkpoint_steps=[], beta_bias_init=None, filler_len_schedule=[[0, 0], [3, 4]])
E2E_EVAL = dict(final_batches=1, final_batch_size=2, final_seed_base=8_800_011, dev_seed=8_800_000,
                train_eval_seed_base=8_800_021)


def _e2e(root, cell, pilot, registry):
    sup = PV.ProbeSlotSupervisor(root=root, cells={cell: pilot}, epoch=1, admitted=[1],
                                 identity={"memsub": source_tree_sha256(ROOT / "memsub")}, checkpoint_every=2,
                                 eval_cfg=E2E_EVAL, commit=lambda: None, reload=lambda: None, ack_timeout_s=120,
                                 poll_s=0.01, registry=registry, schema=tiny_schema())
    return sup.run()["states"][cell], es.read_record(root / "cells" / cell, 1)


def test_end_to_end_probe_supervisor_completes_a_taskhead_cell(tmp_path):
    pilot = {**E2E_BASE, "seed": 99}
    state, rec = _e2e(tmp_path, "taskhead-n4-s99", pilot, V.parameter_registry(pilot))
    assert state == es.COMPLETE and rec["state"] == es.COMPLETE


def test_end_to_end_probe_supervisor_refuses_a_residual_cell_at_the_schema_stage(tmp_path):
    pilot = {**E2E_BASE, "readout": "residual_head", "seed": 100}
    state, rec = _e2e(tmp_path, "residual-n4-s100", pilot, V.parameter_registry(pilot))   # registry matches: schema decides
    assert state == es.FAILED and rec["reason"].startswith("output validation: probe schema:")
