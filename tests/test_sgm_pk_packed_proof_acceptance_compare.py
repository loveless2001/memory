"""Amendment PK proof acceptance on a REAL tiny-CPU proof (codex 21567 probes included): all six
scenarios run through the slot supervisor exactly as the runner does (faults on start 1 only);
the frozen comparator must PASS it and FAIL every injected defect, including defects whose
output hashes were re-bound (so the deeper per-run checks, not the hash gate, must catch them)."""

import copy
import importlib.util
import json
import shutil
from pathlib import Path

import pytest
import torch

from memsub.sgm import packed_slot_epoch_state as es
from memsub.sgm.packed_slot_cell_output_validation import parameter_registry
from memsub.sgm.packed_slot_supervisor import ContainerFault, SlotSupervisor, expand_cells
from memsub.sgm.synthetic_pilot_run import source_tree_sha256

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("acc", ROOT / "scripts/sgm-p2p5-pk-packed-proof-acceptance-compare.py")
acc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acc)

GRID = json.loads((ROOT / "configs/m4_sgm_p2p5_packed_proof_grid.json").read_text())
TINY = copy.deepcopy(GRID)
TINY["base"].update(backbone="tiny", device="cpu", batch=2)
TINY["blocks"][0]["n_bindings"] = [4]
TINY["eval"]["final_batch_size"] = 2
for sc in TINY["scenarios"].values():                    # learned-n32-* -> learned-n4-*
    sc["cells"] = [c.replace("n32", "n4") for c in sc["cells"]]
    sc["faults"] = json.loads(json.dumps(sc["faults"]).replace("n32", "n4")) if sc["faults"] else None
EXP = {"memsub": source_tree_sha256(ROOT / "memsub"), "runner": "test-runner"}
ID = {**EXP, "env": "cpu", "runner_expected": EXP}
CELLS = expand_cells(TINY)
REG = {"by_arm": {"learned": parameter_registry(CELLS["learned-n4-s99"])}}


def run_scenario(root: Path, name: str, admission: dict) -> None:
    """The runner's admission semantics: epoch 1 gets the faults; later epochs none."""
    sc = TINY["scenarios"][name]
    cells = {c: CELLS[c] for c in sc["cells"]}
    admitted = []
    for epoch in (1, 2):
        admitted.append(epoch)
        admission[f"{name}-start-{epoch}"] = float(epoch)
        sup = SlotSupervisor(root=root / name, cells=cells, epoch=epoch, admitted=list(admitted), identity=ID,
                             checkpoint_every=TINY["checkpoint_every"], eval_cfg=TINY["eval"], commit=lambda: None,
                             reload=lambda: None, ack_timeout_s=120, proof_capture=True,
                             faults=sc["faults"] if epoch == 1 else None, poll_s=0.01,
                             provenance={"container_id": f"ta-{name}-{epoch}"}, registry=REG["by_arm"]["learned"])
        try:
            sup.run()
            return
        except ContainerFault:
            continue
    raise AssertionError(f"{name}: did not finish within 2 starts")


@pytest.fixture(scope="module")
def proof(tmp_path_factory):
    root, admission = tmp_path_factory.mktemp("proof"), {}
    for name in TINY["scenarios"]:
        run_scenario(root, name, admission)
    (root / "admission.json").write_text(json.dumps(admission))
    return root


def evaluate(ev, gpu=True, expected=EXP, admission=None):
    adm = admission if admission is not None else json.loads((ev / "admission.json").read_text())
    return acc.evaluate(ev, TINY, REG, adm, expected, gpu=gpu, require_timing=False)


def test_tiny_proof_passes_with_all_bindings(proof):
    rep = evaluate(proof)
    assert rep["pass"], rep.get("failure")
    assert rep["control"]["mode"] == "bitwise"
    assert rep["scenarios"]["B"]["resumed_from"] == 4
    assert rep["scenarios"]["C"]["interrupted_artifact_units"] >= 1
    assert rep["scenarios"]["D"]["learned-n4-s100"]["failed_persisted_epochs"] == [1, 2]


def _copy(proof, tmp_path, name="ev"):
    dst = tmp_path / name
    shutil.copytree(proof, dst)
    return dst


def _rebind(ev, scen, cell):
    """Re-hash the COMPLETE attempt's outputs into done.json and the authoritative record."""
    cdir = ev / scen / "cells" / cell
    m, rec = acc.authority(cdir, [1, 2])
    att = ev / scen / rec["outputs"]["attempt"]
    files = {str(p.relative_to(att / "out")): es.file_sha256(p) for p in sorted((att / "out").rglob("*")) if p.is_file()}
    (att / "done.json").write_text(json.dumps({"outputs": files}))
    rec["outputs"]["files"] = files
    es.write_record(cdir, rec)
    return att / "out"


def test_omitted_gradient_name_everywhere_fails(proof, tmp_path):
    ev = _copy(proof, tmp_path)
    victim = sorted(REG["by_arm"]["learned"]["grad_names_shapes"])[0]
    for f in ev.rglob("proof-capture/u*.pt"):                # joint omission across ALL runs
        d = torch.load(f, weights_only=False)
        d["grads"].pop(victim)
        torch.save(d, f)
    rep = evaluate(ev)
    assert not rep["pass"] and "frozen registry" in rep["failure"]


def test_emptied_outputs_with_rebound_hashes_fail(proof, tmp_path):
    ev = _copy(proof, tmp_path)
    for s, sc in TINY["scenarios"].items():
        for c in sc["cells"]:
            if s == "D" and c.endswith("s100"):
                continue
            o = ev / s / acc.authority(ev / s / "cells" / c, [1, 2])[1]["outputs"]["attempt"] / "out"
            for f in ("per_example_results.jsonl", "routing_telemetry.jsonl"):
                (o / f).write_text("")
            _rebind(ev, s, c)
    rep = evaluate(ev)
    assert not rep["pass"] and "output validation" in rep["failure"]


def test_tampered_gradient_fails(proof, tmp_path):
    ev = _copy(proof, tmp_path)
    f = next((es.epoch_dir(ev / "B" / "cells" / "learned-n4-s99", 2) / "attempt-1" / "proof-capture").glob("u*.pt"))
    d = torch.load(f, weights_only=False)
    name = sorted(d["grads"])[0]
    d["grads"][name] = d["grads"][name] * (1 + 1e-3)
    torch.save(d, f)
    rep = evaluate(ev)
    assert not rep["pass"] and "B/learned-n4-s99.grad" in rep["failure"]


def test_unstable_control_stops(proof, tmp_path):
    ev = _copy(proof, tmp_path)
    f = sorted((es.epoch_dir(ev / "Aprime" / "cells" / "learned-n4-s99", 1) / "attempt-1" / "proof-capture").glob("u*.pt"))[3]
    d = torch.load(f, weights_only=False)
    d["loss"] = d["loss"] * 1.01
    torch.save(d, f)
    rep = evaluate(ev)
    assert not rep["pass"] and "UNSTABLE" in rep["failure"]


@pytest.mark.parametrize("mutate, needle", [
    (lambda m: m["final"]["heldout_none"].__setitem__("accuracy", float("nan")), "non-strict JSON"),
    (lambda m: m.pop("n_queries"), "fields differ"),
    (lambda m: m.__setitem__("wall_seconds", -1.0), "clock"),
])
def test_semantic_metric_defects_fail_after_rebinding(proof, tmp_path, mutate, needle):
    ev = _copy(proof, tmp_path)
    o = ev / "E" / acc.authority(ev / "E" / "cells" / "learned-n4-s99", [1])[1]["outputs"]["attempt"] / "out"
    m = json.loads((o / "metrics.json").read_text())
    mutate(m)
    (o / "metrics.json").write_text(json.dumps(m))
    _rebind(ev, "E", "learned-n4-s99")
    rep = evaluate(ev)
    assert not rep["pass"] and needle in rep["failure"], rep.get("failure")


def test_binding_defects_fail(proof, tmp_path):
    ev = _copy(proof, tmp_path, "gen")
    rec = es.read_record(ev / "B" / "cells" / "learned-n4-s99", 2)
    link = rec["chain"][0]
    (es.epoch_dir(ev / "B" / "cells" / "learned-n4-s99", link["epoch"]) / link["file"]).unlink()
    assert "generation file missing" in evaluate(ev)["failure"]
    assert "identity differs" in evaluate(proof, expected={**EXP, "memsub": "wrong"})["failure"]
    adm = json.loads((proof / "admission.json").read_text())
    adm.pop("B-start-2")
    assert "not all admitted" in evaluate(proof, admission=adm)["failure"]


def test_gpu_mode_requires_real_distinct_container_ids(proof, tmp_path):
    ev = _copy(proof, tmp_path)
    cdir = ev / "B" / "cells" / "learned-n4-s99"
    rec = es.read_record(cdir, 2)
    rec["provenance"]["container_id"] = rec["predecessor_snapshot"]["provenance"]["container_id"]   # same container
    es.write_record(cdir, rec)
    rep = evaluate(ev)
    assert not rep["pass"] and "container ids" in rep["failure"]


def test_relaunched_failed_cell_fails(proof, tmp_path):
    ev = _copy(proof, tmp_path)
    (es.epoch_dir(ev / "D" / "cells" / "learned-n4-s100", 2) / "attempt-1").mkdir(parents=True)
    rep = evaluate(ev)
    assert not rep["pass"] and "relaunched" in rep["failure"]
