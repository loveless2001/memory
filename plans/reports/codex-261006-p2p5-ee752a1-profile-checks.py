"""Read-only audit of the retained P2.5 OOM attempt; no CUDA/model workload.

Run with the unchanged CPU .venv. The deadline probe substitutes a 150 ms
sleep for the entire model workload in a temporary directory. It never runs
training, evaluation, a GPU operation, or a registered population.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.metadata
import importlib.util
import io
import itertools
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from memsub.sgm.synthetic_pilot_run import source_tree_sha256

PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    if sha(ROOT / "scripts/sgm-p2p5-local-gpu-timing-profile.py") != "83ccb450d6ce97fdbec7887deaa6f79ba351626f174a872bd4916af6d1508ca9":
        raise SystemExit("Historical ee752a1 audit: use the reviewed profile source; refusing to probe a later watchdog implementation.")
    before = source_tree_sha256(ROOT / "memsub")
    paths = [PLAN / "prereg.md", PLAN / "profile-local/profile.json", PLAN / "profile-local.log",
             PLAN / "gpu-prep/cpu-cuda-tolerance.json", PLAN / "gpu-prep/full-suite.txt",
             ROOT / "configs/m4_sgm_p2p5_grid.json"]
    paths += [ROOT / "scripts" / f"{name}.py" for name in
              ("sgm-p2p5-local-gpu-timing-profile", "sgm-p2p5-cpu-cuda-tolerance-check",
               "sgm-p2p5-pretrained-observer", "sgm-p2p5-decision-rules")]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    profile = json.loads((PLAN / "profile-local/profile.json").read_text())
    tolerance = json.loads((PLAN / "gpu-prep/cpu-cuda-tolerance.json").read_text())
    assert profile["memsub_source_sha256"] == before
    assert profile["status"] == "stopped: OOM at learned phase 1"
    assert profile["configs"] == [] and 0 < profile["wall_s"] < 1800
    assert "CUDA out of memory" in profile["error"]
    assert all(row["pass"] for row in tolerance.values())
    for row in tolerance.values():
        assert row["max_abs_logit_diff"] < 1e-4
        assert abs(row["loss_cpu"] - row["loss_cuda"]) < 1e-4
        assert abs(row["grad_norm_cpu"] - row["grad_norm_cuda"]) < 1e-4

    grid = json.loads((ROOT / "configs/m4_sgm_p2p5_grid.json").read_text())
    cells = {(b["override"]["arm"], n, s) for b in grid["blocks"]
             for n in b["n_bindings"] for s in b["seeds"]}
    expected = {(arm, n, s) for arm in ("learned", "single_cell", "random_fixed", "memory_off")
                for n in (16, 32) for s in (0, 1)} | {("oracle", 32, s) for s in (0, 1)}
    assert cells == expected and sum(len(b["n_bindings"]) * len(b["seeds"]) for b in grid["blocks"]) == 18
    assert grid["base"]["filler_len_schedule"] == [[0, 0], [1000, 40]]
    assert (grid["artifact_eval_seed_base"], grid["readings_seed_base"]) == (9300011, 9600011)

    rules = load("sgm-p2p5-decision-rules")
    combinations = 0
    for n, unavailable, interface, mem, labels in itertools.product(
            (16, 32), (None, "fixture invalid"), (False, True), (False, True),
            itertools.product(rules.LABELS, repeat=3)):
        result = rules.screen_reading(n, unavailable, interface, dict(zip(rules.CONTROLS, labels)), mem)
        if unavailable is not None:
            assert result.startswith("unavailable:")
        elif not interface:
            assert result.startswith("interface not established")
        elif all(x == rules.P2G.GAIN for x in labels):
            assert result.startswith("SCREEN PASS" if mem else "gain over every control without registered memory use")
        else:
            assert result.startswith("screen not passed")
        combinations += 1
    assert combinations == 1024
    assert rules.interface_ok({"0": 0.5, "1": 0.5})
    assert not rules.interface_ok({"0": 0.499, "1": 1.0})
    rejected = 0
    for malformed in ({"0": 0.5}, {"0": float("nan"), "1": 0.5},
                      {"0": 1.1, "1": 0.5}, {"0": None, "1": 0.5}):
        try:
            rules.interface_ok(malformed)
        except SystemExit:
            rejected += 1
    assert rejected == 4
    observer = load("sgm-p2p5-pretrained-observer")
    assert observer.OBS.REGISTERED_HEADS == frozenset((l, h) for l in (6, 13, 20, 27) for h in range(4))

    runner = load("sgm-p2p5-local-gpu-timing-profile")
    assert runner.CONFIGS == [(a, p) for a in ("learned", "memory_off") for p in (1, 2)]
    assert (runner.WARMUP, runner.MEASURED, runner.WALL_LIMIT_S, runner.PROFILE_SEED, runner.DEV_SEED) == (2, 8, 1800, 99, 4242)

    def delayed_fixture(_arm, _phase):
        time.sleep(0.15)
        return {"mean_measured_s_per_update": 0.15}

    with tempfile.TemporaryDirectory(prefix="p2p5-deadline-audit-") as tmp:
        out = Path(tmp) / "fixture"
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", ["profile-fixture", "--out", str(out)]))
            stack.enter_context(patch.object(runner, "WALL_LIMIT_S", 0.01))
            stack.enter_context(patch.object(runner, "profile_config", delayed_fixture))
            stack.enter_context(patch.object(runner.torch.cuda, "is_available", lambda: True))
            stack.enter_context(patch.object(runner.torch.cuda, "get_device_name", lambda _i: "CPU stub"))
            stack.enter_context(patch.object(runner.torch.cuda, "get_device_properties",
                                            lambda _i: type("Stub", (), {"total_memory": 1})()))
            stack.enter_context(patch.object(runner.torch.cuda, "empty_cache", lambda: None))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            try:
                runner.main()
            except SystemExit as e:
                exit_status = e.code
        deadline = json.loads((out / "profile.json").read_text())
    assert exit_status == 1 and deadline["wall_s"] > 0.15 and len(deadline["configs"]) == 1
    after = source_tree_sha256(ROOT / "memsub")
    assert before == after
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in paths}
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "reviewed_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "memsub_source_sha256_start": before, "memsub_source_sha256_end": after,
        "input_sha256": hashes,
        "cpu_environment": {p: importlib.metadata.version(p) for p in ("torch", "transformers", "safetensors")},
        "retained_oom_artifact_matches_current_source": True,
        "completed_profile_configs": 0, "recorded_wall_s": profile["wall_s"],
        "cuda_tolerance": {"saved_evidence_arithmetic_checked": True, "independent_gpu_rerun": False},
        "grid_cells": len(cells), "reading_table_cases": combinations,
        "malformed_interface_cases_rejected": rejected, "observer_registered_heads": 16,
        "deadline_probe": {"substituted_workload": "CPU sleep only; no model/GPU",
                           "wall_limit_s": 0.01, "observed_wall_s": deadline["wall_s"],
                           "configs_accepted_after_deadline": 1, "hard_deadline_enforced": False},
        "hypothetical_3_to_6_seconds_per_update": {
            "updates": 27000, "training_gpu_hours": [22.5, 45.0],
            "l40s_gpu_only_usd": [43.902, 87.804],
            "l40s_nonpreemptible_gpu_only_usd": [131.706, 263.412],
            "rate_source": "https://modal.com/pricing", "l40s_usd_per_second": 0.000542,
            "measured_estimate": False},
        "paid_profile_clearance": "HOLD: concrete bounded runner and fresh explicit cap approval required",
        "limits": ["No fit/throughput/learning result", "WSL OOM diagnostic is not a reliable physical peak",
                   "Observer/readings/launch protocol not end-to-end certified"]}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
