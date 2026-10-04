"""M4-SGM grid tooling: explicit attempt selection, identity binding and
artifact validation/recovery (#gravity 21096, 21099). Script modules are
loaded by path (kebab-case names)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT = {"readout": "taskhead", "n_queries": 2, "filler_len": 40, "steps": 1500, "batch": 16,
         "lr": 0.003, "eval_every": 100, "eval_batches": 4, "sgm": {},
         "arm": "learned", "n_bindings": 4, "seed": 0}
LAUNCH = {"git_head": "abc", "grid_sha256": "g" * 64}
SRC = "s" * 64


def _script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cell(root: Path, run_dir: str, arm="learned", n=4, seed=0, acc=0.5):
    d = root / run_dir
    d.mkdir(parents=True)
    (d / "metrics.json").write_text(json.dumps(
        {"arm": arm, "n_bindings": n, "seed": seed, "final": {"heldout_none": {"accuracy": acc}}}))
    return d


# -- attempt selection / identity -------------------------------------------------------
def test_single_attempt_loads_and_retry_without_registry_is_ambiguous(tmp_path):
    load = _script("sgm-p2-grid-summary").load
    _cell(tmp_path, "main-learned-n4-s0")
    runs, problems = load(tmp_path)
    assert list(runs) == [("main", "learned", 4, 0)] and problems == []
    _cell(tmp_path, "main-learned-n4-s0-r1", acc=0.9)
    runs, problems = load(tmp_path)
    assert runs == {} and "AMBIGUOUS" in problems[0]


def test_registry_selects_exactly_one_attempt(tmp_path):
    load = _script("sgm-p2-grid-summary").load
    _cell(tmp_path, "main-learned-n4-s0", acc=0.1)
    _cell(tmp_path, "main-learned-n4-s0-r1", acc=0.9)
    (tmp_path / "attempts.json").write_text(json.dumps(
        {"selected": {"main-learned-n4-s0": "main-learned-n4-s0-r1"}}))
    runs, problems = load(tmp_path)
    assert problems == [] and runs[("main", "learned", 4, 0)]["_attempt"] == "main-learned-n4-s0-r1"
    (tmp_path / "attempts.json").write_text(json.dumps(
        {"selected": {"main-learned-n4-s0": "main-learned-n4-s0-r7"}}))
    runs, problems = load(tmp_path)
    assert runs == {} and "registry selects" in problems[0]


def test_conflicting_claimant_invalidates_the_whole_logical_key(tmp_path):
    load = _script("sgm-p2-grid-summary").load
    _cell(tmp_path, "main-learned-n4-s0")
    _cell(tmp_path, "main-other-name")                 # same learned/N4/s0 metadata
    runs, problems = load(tmp_path)
    assert ("main", "learned", 4, 0) not in runs and len(problems) == 2


def test_folder_metrics_identity_mismatch_is_rejected(tmp_path):
    load = _script("sgm-p2-grid-summary").load
    _cell(tmp_path, "main-learned-n4-s0", arm="oracle", n=64)
    runs, problems = load(tmp_path)
    assert runs == {} and "identity" in problems[0]


# -- artifact validation ------------------------------------------------------------------
def _valid_cell(d: Path, pilot=PILOT, rows=None):
    d.mkdir(parents=True)
    params = b"weights"
    (d / "trained_parameters.safetensors").write_bytes(params)
    (d / "run_manifest.json").write_text(json.dumps({
        "run_id": d.name, "pilot_config": pilot, "git_head": "abc", "grid_sha256": "g" * 64,
        "memsub_source_sha256": SRC, "final_eval_seed": 9_100_003 + pilot["seed"],
        "trained_parameters_sha256": hashlib.sha256(params).hexdigest()}))
    if rows is None:
        rows = [{"batch": 0, "episode": e, "episode_hash": f"h{e}", "query": q, "key": 10,
                 "label": 1, "pred": 1 if q == 0 else 2, "correct": q == 0, "intervention": iv}
                for iv in ("none", "read_offset") for e in range(2) for q in range(2)]
    (d / "per_example_results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    res = {"accuracy": 0.5, "correct": 2, "total": 4}
    (d / "metrics.json").write_text(json.dumps({
        **{k: pilot[k] for k in ("arm", "n_bindings", "seed", "steps", "readout", "n_queries")},
        "final_episodes": 2,
        "final": {"heldout_none": res, "heldout_read_offset": res, "heldout_coord_shuffle": None,
                  "train_split_none": {"accuracy": 1.0}}}))
    for f in ("split_manifest.json", "routing_telemetry.jsonl", "report.md"):
        (d / f).write_text("{}")
    return d


def test_validate_accepts_real_rows_and_binds_the_registered_config(tmp_path):
    mod = _script("sgm-recover-and-validate-grid-artifacts")
    d = _valid_cell(tmp_path / "main-learned-n4-s0")
    assert mod.validate(d, d.name, PILOT, LAUNCH, SRC) is None
    assert "memsub_source_sha256" in mod.validate(d, d.name, PILOT, LAUNCH, "x" * 64)
    wrong = _valid_cell(tmp_path / "x" / "main-learned-n4-s0", pilot={**PILOT, "arm": "oracle", "n_bindings": 64})
    reason = mod.validate(wrong, wrong.name, PILOT, LAUNCH, SRC)
    assert "pilot_config" in reason and "metrics_identity" in reason


def test_validate_rejects_malformed_truncated_or_miscounted_rows(tmp_path):
    mod = _script("sgm-recover-and-validate-grid-artifacts")
    cases = {"empty": "{}\n" * 8, "notjson": "not-json\n" * 8}
    for name, text in cases.items():
        d = _valid_cell(tmp_path / name / "main-learned-n4-s0")
        (d / "per_example_results.jsonl").write_text(text)
        assert mod.validate(d, d.name, PILOT, LAUNCH, SRC) is not None, name
    d = _valid_cell(tmp_path / "trunc" / "main-learned-n4-s0")
    lines = (d / "per_example_results.jsonl").read_text().splitlines()
    (d / "per_example_results.jsonl").write_text("\n".join(lines[:-1]) + "\n")
    assert "queries" in mod.validate(d, d.name, PILOT, LAUNCH, SRC)
    d = _valid_cell(tmp_path / "count" / "main-learned-n4-s0")
    text = (d / "per_example_results.jsonl").read_text().replace('"correct": false', '"correct": true', 1)
    (d / "per_example_results.jsonl").write_text(text)
    assert "metrics" in mod.validate(d, d.name, PILOT, LAUNCH, SRC)


def test_reconcile_recovers_missing_rows_and_whole_cells(tmp_path):
    mod = _script("sgm-recover-and-validate-grid-artifacts")
    vol = _valid_cell(tmp_path / "vol" / "main-learned-n4-s0")
    local = tmp_path / "local" / "main-learned-n4-s0"
    assert mod.reconcile(vol, local) == "recovered"
    assert mod.reconcile(vol, local) == "stream_ok"
    (local / "per_example_results.jsonl").unlink()
    assert mod.reconcile(vol, local) == "rows_recovered"
    assert (local / "per_example_results.jsonl").read_bytes() == (vol / "per_example_results.jsonl").read_bytes()


def test_failed_retrieval_is_not_reported_as_incomplete_execution(tmp_path, monkeypatch):
    mod = _script("sgm-recover-and-validate-grid-artifacts")
    root = tmp_path / "grp"
    root.mkdir()
    (root / "launch_provenance.json").write_text(json.dumps(LAUNCH))
    (root / "grid.json").write_text("{}")
    monkeypatch.setattr(mod, "registered_cells", lambda grid: {"main-learned-n4-s0": PILOT})
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a, 1, stdout="", stderr="volume unavailable"))
    monkeypatch.setattr(sys, "argv", ["x", "--group", "grp", "--local", str(tmp_path), "--source-sha", SRC])
    mod.main()
    cell = json.loads((root / "artifact_validation.json").read_text())["cells"]["main-learned-n4-s0"]
    assert cell == {"status": "retrieval_failed", "reason": "volume unavailable"}
