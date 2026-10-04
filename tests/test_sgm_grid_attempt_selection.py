"""M4-SGM grid tooling: explicit attempt selection and artifact validation
(#gravity 21096). Script modules are loaded by path (kebab-case names)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cell(root: Path, run_dir: str, arm="learned", n=4, seed=0, acc=0.5):
    d = root / run_dir
    d.mkdir(parents=True)
    (d / "metrics.json").write_text(json.dumps({
        "arm": arm, "n_bindings": n, "seed": seed, "final": {"heldout_none": {"accuracy": acc}}}))
    return d


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
    assert problems == []
    m = runs[("main", "learned", 4, 0)]
    assert m["_attempt"] == "main-learned-n4-s0-r1" and m["final"]["heldout_none"]["accuracy"] == 0.9
    (tmp_path / "attempts.json").write_text(json.dumps(
        {"selected": {"main-learned-n4-s0": "main-learned-n4-s0-r7"}}))
    runs, problems = load(tmp_path)
    assert runs == {} and "registry selects" in problems[0]


def test_artifact_validation_checks_provenance_and_row_counts(tmp_path):
    mod = _script("sgm-recover-and-validate-grid-artifacts")
    launch = {"git_head": "abc", "grid_sha256": "g" * 64}
    d = tmp_path / "main-learned-n4-s0"
    d.mkdir()
    params = b"weights"
    (d / "trained_parameters.safetensors").write_bytes(params)
    manifest = {"run_id": "main-learned-n4-s0", "git_head": "abc", "grid_sha256": "g" * 64,
                "memsub_source_sha256": "s" * 64, "final_eval_seed": 9_100_003,
                "trained_parameters_sha256": hashlib.sha256(params).hexdigest()}
    (d / "run_manifest.json").write_text(json.dumps(manifest))
    (d / "metrics.json").write_text(json.dumps({
        "seed": 0, "final_episodes": 2, "n_queries": 2,
        "final": {"heldout_none": {"accuracy": 1.0}, "heldout_coord_shuffle": None,
                  "train_split_none": {"accuracy": 1.0}}}))
    for f in ("split_manifest.json", "routing_telemetry.jsonl", "report.md"):
        (d / f).write_text("{}")
    (d / "per_example_results.jsonl").write_text("{}\n" * 4)
    assert mod.validate(d, "main-learned-n4-s0", launch, "s" * 64) is None
    assert "provenance" in mod.validate(d, "main-learned-n4-s0", launch, "x" * 64)
    (d / "per_example_results.jsonl").write_text("{}\n" * 3)
    assert "rows" in mod.validate(d, "main-learned-n4-s0", launch, "s" * 64)
    (d / "report.md").unlink()
    assert "missing" in mod.validate(d, "main-learned-n4-s0", launch, "s" * 64)
