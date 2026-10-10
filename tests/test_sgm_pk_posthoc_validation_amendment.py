"""Post-hoc validation amendment for learned-n32-s1 (user 21710, option B; codex 21701/21703/21712): the original gate
still reports the campaign unavailable; the amended gate accepts ONLY the spec cell, ONLY its listed null grad_norm
leaves, with every other original check kept; the readings label the whole campaign and both N "post-hoc amended"
and keep the original reading. Real-evidence tests use the locally fetched campaign copy (skipped if absent;
M4_PK_EVIDENCE_REPO points a private-copy run at the main checkout). Mutations work on private copies only."""

import importlib.util
import json
import os
import random
import shutil
from pathlib import Path

import pytest
from conftest import pk_current_memsub_manifest

ROOT = Path(__file__).resolve().parents[1]
PLAN = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
EVID = Path(os.environ.get("M4_PK_EVIDENCE_REPO", ROOT)) / PLAN / "p2p5-qwen3-0p6b-screen-v1"
needs_evidence = pytest.mark.skipif(not (EVID / "learned-n32/volume-evidence/collect-1").is_dir(),
                                    reason="local campaign evidence not fetched")


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rd = _load("scripts/sgm-p2p5-pk-campaign-readings.py", "rd_posthoc")
AMD = rd.AMD
SPEC = AMD.load_spec()
ORIGINAL_GATE = "learned-n32-s1: state FAILED"


def frozen():
    grid, registry, schema = (json.loads(p.read_text()) for p in (rd.GRID, rd.REGISTRY, rd.SCHEMA))
    return grid, registry, schema


def check(slot: Path, spec=SPEC, rec=None, registry=None):
    grid, frozen_registry, schema = frozen()
    registry = registry or frozen_registry["by_arm"]["learned"]          # per-arm registry
    from memsub.sgm.packed_slot_supervisor import expand_cells
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    pilot = expand_cells(grid)["learned-n32-s1"]
    rec = rec or json.loads((slot / "cells/learned-n32-s1/epoch-1/state.json").read_text())
    return AMD.amended_cell_problem(slot, rec, pilot, rd.EVAL, source_tree_sha256(ROOT / "memsub"),
                                    registry, schema["by_arm"]["learned"], spec)


def _edit_telemetry(out: Path, fn) -> None:
    rows = [json.loads(x) for x in (out / "routing_telemetry.jsonl").read_text().splitlines()]
    for r in rows:
        fn(r)
    (out / "routing_telemetry.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def _schema_problem(out: Path, spec=SPEC):
    grid, _registry, schema = frozen()
    from memsub.sgm.packed_slot_supervisor import expand_cells
    return AMD.amended_schema_problem(out, expand_cells(grid)["learned-n32-s1"], schema["by_arm"]["learned"], spec)


@needs_evidence
@pytest.mark.parametrize("kind", ["update_norm_null", "extra_grad_null", "missing_listed_null", "eval_row_null",
                                  "unlisted_layer_key"])
def test_exception_is_limited_to_the_listed_grad_norm_leaves(tmp_path, kind):
    out = tmp_path / "schema-out"                                   # telemetry only: no terminal checkpoint needed
    shutil.copytree(EVID / "learned-n32/volume-evidence/collect-1/learned-n32/cells/learned-n32-s1/epoch-1/attempt-1/out", out)
    assert _schema_problem(out) is None
    spec = SPEC

    def edit(r):
        if "loss" in r and r["step"] == 50 and kind == "update_norm_null":
            r["update_norm"]["L20/k_proj"] = None                    # update_norm gets NO exception (codex 21701)
        if "loss" in r and r["step"] == 70 and kind == "extra_grad_null":
            r["grad_norm"]["L6/k_proj"] = None
        if "loss" in r and r["step"] == 50 and kind == "missing_listed_null":
            r["grad_norm"]["L20/k_proj"] = 0.5
        if "eval" in r and r["step"] == 0 and kind == "eval_row_null":
            r["eval"] = None
        if "loss" in r and r["step"] == 50 and kind == "unlisted_layer_key":
            r["grad_norm"]["L21/k_proj"] = None                      # not a selected layer / frozen leaf
    _edit_telemetry(out, edit)
    if kind == "unlisted_layer_key":
        spec = {**SPEC, "nullable_leaves": [*SPEC["nullable_leaves"], [50, "L21/k_proj"]]}
    problem = _schema_problem(out, spec)
    assert problem is not None
    if kind in ("extra_grad_null", "missing_listed_null"):
        assert problem == "null grad_norm leaves differ from the spec list"
    elif kind == "unlisted_layer_key":
        assert problem == "spec leaf L21/k_proj is not a frozen numeric grad_norm leaf"
    else:
        assert problem.startswith("amended output schema")


def test_spec_binds_the_diagnosed_hashes_and_51_grad_norm_leaves_only():
    assert SPEC["cell"] == "learned-n32-s1" and SPEC["slot"] == "learned-n32" and SPEC["label"] == "post-hoc amended"
    assert SPEC["state_sha256"].startswith("d4996651") and SPEC["done_sha256"].startswith("33a3dafb")
    assert len(SPEC["outputs"]) == 7 and SPEC["terminal_checkpoint"]["step"] == 1500
    assert len(SPEC["nullable_leaves"]) == 51 and len({s for s, _k in SPEC["nullable_leaves"]}) == 17
    assert {k for _s, k in SPEC["nullable_leaves"]} == {"L20/k_proj", "L20/value", "L20/beta"}
    assert AMD.NULLABLE_FIELD == "grad_norm" and "nullable_field" not in SPEC         # the field is fixed in code


# ---------------- readings labels (fakes for binding / evaluation; real decision rules) ----------------

def rows_for(p: float, ivs: tuple, seed: int) -> list:
    rng, rows = random.Random(seed), []
    for iv in ivs:
        for b in range(16):
            for e in range(16):
                for q in range(4):
                    label, ok = (b * 16 + e + q) % 64, rng.random() < (p if iv == "none" else 0.02)
                    rows.append({"batch": b, "episode": e, "episode_hash": f"h{b}-{e}", "query": q, "key": q,
                                 "label": label, "pred": label if ok else (label + 1) % 64, "correct": ok,
                                 "intervention": iv})
    return rows


def run_readings(monkeypatch, tmp_path, amended_problem=None):
    monkeypatch.setattr(rd, "MANIFEST", pk_current_memsub_manifest(tmp_path / "current-memsub-manifest.json"))
    pilots = rd.expand_cells(json.loads(rd.GRID.read_text()))
    (tmp_path / "trained_parameters.safetensors").write_bytes(b"ckpt")
    binds = []

    def fake_bind(*a):
        amendment = a[6] if len(a) > 6 else None
        binds.append(amendment)
        if amendment is None:
            return {c: tmp_path for c in pilots if c != "learned-n32-s1"}, ORIGINAL_GATE
        return {c: tmp_path for c in pilots}, amended_problem
    monkeypatch.setattr(rd, "bind_cells", fake_bind)
    monkeypatch.setattr(rd, "parity", lambda *a, **k: None)

    def fake_reserved(cid, out, pilot, n, ivs, dest):
        p = {"oracle": 0.9, "learned": 0.9}.get(pilot["arm"], 0.1)
        rows = rows_for(p, ivs, hash((cid, n)) % 1000)
        return rows, {"rows_sha256": "x", "accuracy_none": sum(rd.P2D.episode_scores(rows, "none").values()) / rd.P2D.N_EPISODES}
    monkeypatch.setattr(rd, "reserved_rows", fake_reserved)
    return rd.readings(tmp_path, {}, rd.current_identity(), tmp_path / "out"), binds


def test_readings_label_the_campaign_and_both_n_and_keep_the_original_reading(monkeypatch, tmp_path):
    rep, binds = run_readings(monkeypatch, tmp_path)
    assert binds[0] is None and binds[1] == SPEC                                  # original gate first, then amended
    assert rep["campaign_label"] == "post-hoc amended" and rep["end_binding"] == "verified"
    pa = rep["posthoc_amendment"]
    assert pa["original_gate"] == ORIGINAL_GATE and pa["spec_sha256"] == AMD.sha(rd.AMENDMENT)
    for n in ("32", "16"):
        v = rep["n"][n]
        assert v["label"] == "post-hoc amended" and v["reading"] == f"SCREEN PASS at N{n}"
        assert v["original_reading"] == f"unavailable: {ORIGINAL_GATE}"
    saved = json.loads((tmp_path / "out/readings.json").read_text())
    assert saved["campaign_label"] == "post-hoc amended" and saved["n"]["32"]["original_reading"].startswith("unavailable")


def test_failed_amended_binding_keeps_every_reading_unavailable_and_labelled(monkeypatch, tmp_path):
    rep, _binds = run_readings(monkeypatch, tmp_path, amended_problem="learned-n32-s1: post-hoc amendment: x")
    for n in ("32", "16"):
        assert rep["n"][n]["reading"] == "unavailable: learned-n32-s1: post-hoc amendment: x"
        assert rep["n"][n]["label"] == "post-hoc amended"
    assert rep["unavailable"].startswith("learned-n32-s1")


# ---------------- runner gate (local spawn precondition) ----------------

def _runner(monkeypatch):
    monkeypatch.chdir(ROOT)
    return _load("modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py", "rr_posthoc")


def test_runner_accepts_only_the_spec_cell_with_the_original_reason(monkeypatch, tmp_path):
    r = _runner(monkeypatch)
    ok = {"state": "COMPLETE", "validation": "valid"}
    failed = {"state": "FAILED", "reason": SPEC["original_reason"]}
    for s in r.SLOTS:
        (tmp_path / s).mkdir()
        cells = {f"{s}-s0": ok, f"{s}-s1": failed if s == "learned-n32" else ok}
        (tmp_path / s / "collect_status.json").write_text(json.dumps(
            {"final_shutdown": {"status": "stopped_verified"}, "cells": cells}))
    assert "learned-n32" in r.slots_ready(tmp_path)                               # original gate: refused
    assert r.slots_ready(tmp_path, SPEC) is None                                 # amended: accepted
    for bad in ({"state": "FAILED", "reason": "output validation: other"}, {"state": "LOST"}):
        st = json.loads((tmp_path / "learned-n32/collect_status.json").read_text())
        st["cells"]["learned-n32-s1"] = bad
        (tmp_path / "learned-n32/collect_status.json").write_text(json.dumps(st))
        assert "learned-n32" in r.slots_ready(tmp_path, SPEC)
    st["cells"]["learned-n32-s1"] = failed
    (tmp_path / "learned-n32/collect_status.json").write_text(json.dumps(st))
    st2 = json.loads((tmp_path / "oracle-n32/collect_status.json").read_text())
    st2["cells"]["oracle-n32-s0"] = failed                                       # any other FAILED cell blocks
    (tmp_path / "oracle-n32/collect_status.json").write_text(json.dumps(st2))
    assert "oracle-n32" in r.slots_ready(tmp_path, SPEC)


def test_runner_amendment_gate_requires_the_sha_bound_amended_valid_record(monkeypatch, tmp_path):
    r = _runner(monkeypatch)
    spec, problem = r.amendment_gate(ROOT)
    assert problem is None and spec == SPEC
    for rel in (r.AMENDMENT_SPEC, r.AMENDMENT_RECORD):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tmp_path / rel)
    assert r.amendment_gate(tmp_path)[1] is None
    rec = json.loads((tmp_path / r.AMENDMENT_RECORD).read_text())
    for bad in ({**rec, "result": "rejected: x"}, {**rec, "spec_sha256": "0" * 64}, {**rec, "cell": "learned-n32-s0"}):
        (tmp_path / r.AMENDMENT_RECORD).write_text(json.dumps(bad))
        assert r.amendment_gate(tmp_path)[0] is None
    (tmp_path / r.AMENDMENT_RECORD).unlink()
    assert "unreadable" in r.amendment_gate(tmp_path)[1]
