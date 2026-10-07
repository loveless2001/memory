"""P2.5 packed-campaign readings, end to end on a TINY-CPU mini campaign (all 9 slots / 18 registered cells through
the real slot supervisor, registered 16 x 16 artifact evaluation), then the real exactly-once readings. Slow
(several minutes): runs only with M4_PK_SLOW=1. Also: a missing/invalid cell or a parity mismatch leaves every N
"unavailable" with NO reserved-population rows written."""

import copy
import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

from memsub.sgm import packed_slot_epoch_state as es
from memsub.sgm.packed_slot_cell_output_validation import output_schemas, parameter_registry
from memsub.sgm.packed_slot_supervisor import SlotSupervisor, expand_cells
from memsub.sgm.synthetic_pilot_run import source_tree_sha256

pytestmark = pytest.mark.skipif(os.environ.get("M4_PK_SLOW") != "1", reason="slow tiny campaign (set M4_PK_SLOW=1)")
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rd", ROOT / "scripts/sgm-p2p5-pk-campaign-readings.py")
rd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rd)


def tiny_grid():
    g = json.loads((ROOT / "configs/m4_sgm_p2p5_grid.json").read_text())
    g["base"].update(backbone="tiny", device="cpu", batch=2, steps=6, eval_every=3, eval_batches=1,
                     filler_len_schedule=[[0, 0], [3, 40]])
    return g


@pytest.fixture(scope="module")
def campaign(tmp_path_factory):
    base = tmp_path_factory.mktemp("campaign")
    grid = tiny_grid()
    (base / "grid.json").write_text(json.dumps(grid))
    pilots = expand_cells(grid)
    registry, schema = {"by_arm": {}}, {"by_arm": {}}
    memsub = source_tree_sha256(ROOT / "memsub")
    identity = {"memsub": memsub}
    root = base / "evidence"
    for slot in sorted({f"{p['arm']}-n{p['n_bindings']}" for p in pilots.values()}):
        cells = {c: p for c, p in pilots.items() if f"{p['arm']}-n{p['n_bindings']}" == slot}
        arm = next(iter(cells.values()))["arm"]
        registry["by_arm"].setdefault(arm, parameter_registry(next(iter(cells.values()))))
        SlotSupervisor(root=root / slot, cells=cells, epoch=1, admitted=[1], identity=identity, checkpoint_every=2,
                       eval_cfg=rd.EVAL, commit=lambda: None, reload=lambda: None, ack_timeout_s=300, poll_s=0.02,
                       registry=registry["by_arm"][arm]).run()
        if arm not in schema["by_arm"]:
            rec = es.read_record(root / slot / "cells" / next(iter(cells)), 1)
            schema["by_arm"][arm] = output_schemas(root / slot / rec["outputs"]["attempt"] / "out", cells[next(iter(cells))])[0]
    (base / "registry.json").write_text(json.dumps(registry))
    (base / "schema.json").write_text(json.dumps(schema))
    admitted = {slot: [1] for slot in {f"{p['arm']}-n{p['n_bindings']}" for p in pilots.values()}}
    return base, root, admitted


def _bind(monkeypatch, base):
    from memsub.sgm.synthetic_pilot import TINY_SGM_DEFAULTS
    # the P2.5 observer is pinned to the Qwen 16-head set; the TINY harness rebinds it to the tiny geometry
    monkeypatch.setattr(rd.POBS.OBS, "REGISTERED_HEADS", frozenset(
        (l, h) for l in TINY_SGM_DEFAULTS["selected_layers"] for h in range(TINY_SGM_DEFAULTS["memory_heads"])))
    monkeypatch.setattr(rd, "GRID", base / "grid.json")
    monkeypatch.setattr(rd, "REGISTRY", base / "registry.json")
    monkeypatch.setattr(rd, "SCHEMA", base / "schema.json")


def test_readings_run_exactly_once_and_read_every_n(campaign, monkeypatch, tmp_path):
    base, root, admitted = campaign
    _bind(monkeypatch, base)
    rep = rd.readings(root, admitted, rd.current_identity(), tmp_path / "out")
    assert "unavailable" not in rep and set(rep["n"]) == {"32", "16"}
    for n, v in rep["n"].items():
        assert isinstance(v["interface"], bool) and v["reading"]
        if v["interface"]:
            assert set(v["labels"]) == set(rd.DR.CONTROLS) and isinstance(v["memory_use"], bool)
    assert (tmp_path / "out" / "readings.json").exists()
    with pytest.raises(FileExistsError):                              # exactly once: the output is write-once
        rd.readings(root, admitted, rd.current_identity(), tmp_path / "out")


def test_invalid_cell_or_parity_mismatch_leaves_reserved_population_untouched(campaign, monkeypatch, tmp_path):
    base, root, admitted = campaign
    _bind(monkeypatch, base)
    ev = tmp_path / "ev"
    shutil.copytree(root, ev)
    lost = next((ev / "learned-n32" / "cells").iterdir())
    rec = es.read_record(lost, 1)
    (ev / "learned-n32" / rec["outputs"]["attempt"] / "out" / "metrics.json").unlink()
    rep = rd.readings(ev, admitted, rd.current_identity(), tmp_path / "out1")
    assert rep["unavailable"] and all(v["reading"].startswith("unavailable") for v in rep["n"].values())
    assert not list((tmp_path / "out1").glob("rows-*"))               # reserved population never evaluated

    ev2 = tmp_path / "ev2"
    shutil.copytree(root, ev2)
    cdir = next((ev2 / "oracle-n32" / "cells").iterdir())
    rec = es.read_record(cdir, 1)
    out = ev2 / "oracle-n32" / rec["outputs"]["attempt"] / "out"
    rows = [json.loads(x) for x in (out / "per_example_results.jsonl").read_text().splitlines()]
    rows[0]["pred"] = (rows[0]["pred"] + 1) % 64                      # this host must reproduce batch 0 exactly
    rows[0]["correct"] = rows[0]["pred"] == rows[0]["label"]
    (out / "per_example_results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    m = json.loads((out / "metrics.json").read_text())                 # keep the row/metric reconciliation valid
    f = m["final"]["heldout_none"]
    f["correct"] = sum(r["correct"] for r in rows if r["intervention"] == "none")
    (out / "metrics.json").write_text(json.dumps(m))
    rec2 = copy.deepcopy(rec)
    rec2["outputs"]["files"] = {k: es.file_sha256(out / k) for k in rec["outputs"]["files"]}
    es.write_record(cdir, rec2)
    rep2 = rd.readings(ev2, admitted, rd.current_identity(), tmp_path / "out2")
    assert rep2["unavailable"].startswith("parity") and not list((tmp_path / "out2").glob("rows-*"))
