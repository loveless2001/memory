"""Recovery/validation CLI seed selection (codex 21323): P2G grids validate
training artifacts on `artifact_eval_seed_base`, never the reserved readings
seed; legacy P2D (`final_seed_base`) and v2 (default) behaviour is unchanged."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("recover_cli", ROOT / "scripts" / "sgm-recover-and-validate-grid-artifacts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("grid_file,want", [
    ("configs/m4_sgm_p2g_grid.json", 9_300_011),      # P2G: artifact seed, not reserved 9_400_011
    ("configs/m4_sgm_p2d_grid.json", 9_300_011),      # P2D legacy key
    ("configs/m4_sgm_p2d_topup_grid.json", 9_300_011),
])
def test_committed_grids_select_their_training_eval_seed(grid_file, want):
    assert _mod().training_eval_seed_base(json.loads((ROOT / grid_file).read_text())) == want


def test_v2_default_and_conflict():
    mod = _mod()
    assert mod.training_eval_seed_base({"blocks": []}) == mod.FINAL_SEED_BASE == 9_100_003
    assert mod.training_eval_seed_base({"artifact_eval_seed_base": 7, "final_seed_base": 7}) == 7
    with pytest.raises(SystemExit, match="conflicting"):
        mod.training_eval_seed_base({"artifact_eval_seed_base": 7, "final_seed_base": 8})


def test_cli_passes_the_artifact_seed_into_validate(tmp_path, monkeypatch):
    mod = _mod()
    root = tmp_path / "p2g-selective-write-v1"
    root.mkdir()
    (root / "grid.json").write_text((ROOT / "configs" / "m4_sgm_p2g_grid.json").read_text())
    (root / "launch_provenance.json").write_text(json.dumps({"git_head": "x"}))
    seen = []
    monkeypatch.setattr(mod, "registered_cells", lambda grid, runner: {"gateclosed-learned-n16-s0": {"seed": 0}})
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(mod, "validate", lambda dest, rid, pilot, launch, src, base: seen.append(base) or "stop")
    monkeypatch.setattr(sys, "argv", ["x", "--group", root.name, "--local", str(tmp_path), "--source-sha", "s"])
    mod.main()
    assert seen == [9_300_011]
    report = json.loads((root / "artifact_validation.json").read_text())
    assert report["cells"]["gateclosed-learned-n16-s0"] == {"status": "incomplete", "reason": "stop"}


P2D = ROOT / "plans/261005-0210-m4-sgm-p0-p2/runs/p2d-diagnostics-v1"
P2D_SOURCE = "d4effd0c5132057093d013d4e117bf131db9b4819fbc02d45fb1bc9b06a48b60"


@pytest.mark.skipif(not (P2D / "launch_provenance.json").exists(), reason="local P2D run evidence absent")
def test_known_good_p2d_cell_passes_with_selected_seed_and_fails_with_old_default():
    mod = _mod()
    grid = json.loads((ROOT / "configs" / "m4_sgm_p2d_grid.json").read_text())
    launch = json.loads((P2D / "launch_provenance.json").read_text())
    rid = "filleroff-learned-n16-s0"
    pilot = mod.registered_cells(grid, ROOT / "modal-runners" / "modal-m4-sgm-p2d-diagnostics-grid.py")[rid]
    cell = P2D / "status-audit" / "volume-mirror" / rid
    assert mod.validate(cell, rid, pilot, launch, P2D_SOURCE, mod.training_eval_seed_base(grid)) is None
    assert "final_eval_seed" in mod.validate(cell, rid, pilot, launch, P2D_SOURCE, mod.FINAL_SEED_BASE)
