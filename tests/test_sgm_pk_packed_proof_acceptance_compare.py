"""Amendment PK proof acceptance on a REAL tiny-CPU proof: all six scenarios run through the
slot supervisor (faults on the first admitted start only, as the Modal runner does); the
frozen comparator must PASS it and FAIL every injected defect."""

import copy
import importlib.util
import json
import shutil
from pathlib import Path

import pytest
import torch

from memsub.sgm import packed_slot_epoch_state as es
from memsub.sgm.packed_slot_supervisor import ContainerFault, SlotSupervisor, expand_cells

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
ID = {"memsub": "test", "runner": "test", "env": "cpu"}


def run_scenario(root: Path, name: str) -> None:
    """Exactly the runner's admission semantics: epoch 1 gets the faults; later epochs none."""
    cells_all, sc = expand_cells(TINY), TINY["scenarios"][name]
    cells = {c: cells_all[c] for c in sc["cells"]}
    admitted = []
    for epoch in (1, 2, 3):
        admitted.append(epoch)
        sup = SlotSupervisor(root=root / name, cells=cells, epoch=epoch, admitted=list(admitted), identity=ID,
                             checkpoint_every=TINY["checkpoint_every"], eval_cfg=TINY["eval"], commit=lambda: None,
                             reload=lambda: None, ack_timeout_s=120, proof_capture=True,
                             faults=sc["faults"] if epoch == 1 else None, poll_s=0.01)
        try:
            sup.run()
            return
        except ContainerFault:
            continue
    raise AssertionError(f"{name}: did not finish within 3 starts")


@pytest.fixture(scope="module")
def proof(tmp_path_factory):
    root = tmp_path_factory.mktemp("proof")
    for name in TINY["scenarios"]:
        run_scenario(root, name)
    return root


def test_tiny_proof_passes(proof):
    rep = acc.evaluate(proof, TINY)
    assert rep["pass"], rep.get("failure")
    assert rep["control"]["mode"] == "bitwise"                       # CPU: deterministic
    assert rep["scenarios"]["B"]["resumed_from"] == 4
    assert rep["scenarios"]["D"]["learned-n4-s100"]["failed_persisted_epochs"] == [1, 2]


def _copy(proof, tmp_path):
    dst = tmp_path / "ev"
    shutil.copytree(proof, dst)
    return dst


def _out(ev, scen, cell):
    m, rec = acc.authority(ev / scen / "cells" / cell)
    return ev / scen / rec["outputs"]["attempt"] / "out"


def test_tampered_gradient_fails(proof, tmp_path):
    ev = _copy(proof, tmp_path)
    f = next((es.epoch_dir(ev / "B" / "cells" / "learned-n4-s99", 2) / "attempt-1" / "proof-capture").glob("u*.pt"))
    d = torch.load(f, weights_only=False)
    name = sorted(d["grads"])[0]
    d["grads"][name] = d["grads"][name] * (1 + 1e-3)
    torch.save(d, f)
    rep = acc.evaluate(ev, TINY)
    assert not rep["pass"] and "B/learned-n4-s99.grad" in rep["failure"]


def test_unstable_control_stops(proof, tmp_path):
    ev = _copy(proof, tmp_path)
    f = sorted((es.epoch_dir(ev / "Aprime" / "cells" / "learned-n4-s99", 1) / "attempt-1" / "proof-capture").glob("u*.pt"))[3]
    d = torch.load(f, weights_only=False)
    d["loss"] = d["loss"] * 1.01
    torch.save(d, f)
    rep = acc.evaluate(ev, TINY)
    assert not rep["pass"] and "UNSTABLE" in rep["failure"]


def test_nan_missing_field_and_bad_clock_fail(proof, tmp_path):
    for mutate, needle in [(lambda m: m["final"]["heldout_none"].__setitem__("accuracy", float("nan")), "non-finite"),
                           (lambda m: m.pop("n_queries"), "fields differ"),
                           (lambda m: m.__setitem__("wall_seconds", -1.0), "clock")]:
        ev = _copy(proof, tmp_path / needle.replace(" ", "_"))
        p = _out(ev, "E", "learned-n4-s99") / "metrics.json"
        m = json.loads(p.read_text())
        mutate(m)
        p.write_text(json.dumps(m))
        rep = acc.evaluate(ev, TINY)
        assert not rep["pass"] and needle in rep["failure"], (needle, rep.get("failure"))


def test_relaunched_failed_cell_fails(proof, tmp_path):
    ev = _copy(proof, tmp_path)
    (es.epoch_dir(ev / "D" / "cells" / "learned-n4-s100", 2) / "attempt-1").mkdir(parents=True)
    rep = acc.evaluate(ev, TINY)
    assert not rep["pass"] and "relaunched" in rep["failure"]
