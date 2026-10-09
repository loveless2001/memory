"""Stage receipts for the previous-key information probe (proposal v0.5; codex 22408/22412).

A stage (s1 | s2 | full) is SUCCESSFUL only if ALL of these hold:
  * `<stage_dir>.exit` reads 0 and `status.json` says COMPLETE (a KILL leaves RUNNING);
  * `run.json` exists and equals result["run"];
  * the frozen schema matches for this mode: episode counts, splits, seeds, threads, n_boot, BLAS env;
    resolved PilotConfig = frozen manifest + device=cpu; SGM layers (6,13,20,27) with feature_shift=1;
    backbone pin = the pinned Qwen3-0.6B-Base spec; a 64-hex initial-adapter content hash;
  * the source hashes are CURRENT: 5 probe files + the controller script + the whole memsub tree;
  * `features.npz` hashes to run["features_sha256"], has exactly the expected arrays and shapes, all finite;
  * the metric keys are exactly the expected set, all values finite and in range; reading.read == (mode == full);
  * s1 only: `admission.json` equals result["admission"]; its parts are finite and >= 0; estimate and wall are
    recomputed; admit == (0 < wall <= 4 h).
Full: valid S1 + S2 with equal initial-adapter hashes; wall = ceil(validated S1 wall).
CLI: --validate s1|s2 --dir D | --validate full --dir D --s1 D1 --s2 D2 | --full-wall --s1 D1 --s2 D2
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.pinned_pretrained_qwen3_backbone import QWEN3_0P6B_BASE  # noqa: E402
from memsub.sgm.synthetic_pilot_run import source_tree_sha256  # noqa: E402

MANIFEST = ROOT / "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"
SOURCES = [ROOT / "scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py",
           ROOT / "scripts/sgm-p2p5-previous-key-probe-ridge-retrieval-readings.py",
           ROOT / "scripts/sgm-p2p5-previous-key-probe-capture-qwen-adapter-inputs.py",
           Path(__file__).resolve(), MANIFEST,
           ROOT / "plans/261010-0107-m4-sgm-qwen-value-token-previous-key-information-probe/run-probe-chain-s1-s2-full.sh"]
MODES = {   # single source of the frozen stage schema (the run script reads it from here)
    "s1": {"fit": ("train", 2, 9_799_011), "ev": ("heldout", 2, 9_799_021), "cv": False, "wall": 1800,
           "seeds": {"perm_fit": 9_799_031, "perm_ev": 9_799_032, "folds": 9_799_041, "boot": 9_799_051}},
    "s2": {"fit": ("train", 4, 9_799_012), "ev": ("heldout", 2, 9_799_022), "cv": True, "wall": 2400,
           "seeds": {"perm_fit": 9_799_031, "perm_ev": 9_799_032, "folds": 9_799_041, "boot": 9_799_051}},
    "full": {"fit": ("train", 96, 9_700_011), "ev": ("heldout", 64, 9_700_021), "cv": True, "wall": None,
             "seeds": {"perm_fit": 9_700_031, "perm_ev": 9_700_032, "folds": 9_700_041, "boot": 9_700_051}},
}
LAYERS, N_BIND, D_MODEL, THREADS, N_BOOT = (6, 13, 20, 27), 32, 1024, 8, 4000
FULL_EPISODES, MARGIN_S = 160, 300.0
SETS = ("V", "V+K", "K", "E_v", "V-shuf")
LABELS = {"INVALID", "NO CALIBRATED LAYER", "CARRIED", "PARTIAL", "WEAK LINEAR RECOVERY UNDER THIS PROBE", "INCONCLUSIVE"}
_spec = importlib.util.spec_from_file_location("pkmath_rx", SOURCES[1])
M = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(M)
require = M.require


def _reject_constant(c):
    raise RuntimeError(f"nonfinite: non-strict JSON constant {c}")


def strict_json(path: Path):
    """Strict JSON: NaN / Infinity are rejected here; overflowing literals (1e999) are caught by _all_finite."""
    return json.loads(Path(path).read_text(), parse_constant=_reject_constant)


def source_shas() -> dict:
    out = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES}
    out["memsub_tree"] = source_tree_sha256(ROOT / "memsub")
    return out


def expected_pilot_config() -> dict:
    return json.loads(json.dumps({**json.loads(MANIFEST.read_text())["pilot_config"], "device": "cpu"}))


def write_status(out: Path, state: str, **extra) -> None:
    tmp = out / "status.json.tmp"
    with open(tmp, "w") as f:
        json.dump({"state": state, **extra}, f, allow_nan=False); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, out / "status.json")


def _all_finite(o) -> bool:
    if isinstance(o, bool) or o is None or isinstance(o, str):
        return True
    if isinstance(o, (int, float)):
        return math.isfinite(o)
    if isinstance(o, dict):
        return all(_all_finite(v) for v in o.values())
    if isinstance(o, (list, tuple)):
        return all(_all_finite(v) for v in o)
    return False


def _check_run(run: dict, mode: str, shas: dict) -> str:
    m = MODES[mode]
    require(run.get("mode") == mode, f"{mode}: run.mode {run.get('mode')!r}")
    require(run.get("fit") == list(m["fit"]) and run.get("ev") == list(m["ev"]), f"{mode}: episode counts/splits/seeds differ")
    require(run.get("seeds") == m["seeds"], f"{mode}: seeds differ")
    require(run.get("threads") == THREADS and run.get("n_boot") == N_BOOT, f"{mode}: threads/n_boot differ")
    require(run.get("blas_env") == {v: str(THREADS) for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
            f"{mode}: BLAS env differs")
    require(run.get("sha256") == shas, f"{mode}: source hashes differ from the current sources")
    ids = run.get("identities") or {}
    require(ids.get("pilot_config_resolved") == expected_pilot_config(), f"{mode}: resolved PilotConfig differs")
    sgm = ids.get("sgm_config_resolved") or {}
    require(list(sgm.get("selected_layers", [])) == list(LAYERS) and sgm.get("feature_shift") == 1, f"{mode}: SGM config differs")
    require(ids.get("backbone_pin") == json.loads(json.dumps(QWEN3_0P6B_BASE)), f"{mode}: backbone pin differs")
    init = ids.get("initial_adapter_params_sha256", "")
    require(isinstance(init, str) and re.fullmatch(r"[0-9a-f]{64}", init) is not None, f"{mode}: initial adapter hash missing")
    return init


def _check_features(path: Path, run: dict, mode: str) -> None:
    require(path.is_file(), f"{mode}: features.npz missing")
    require(hashlib.sha256(path.read_bytes()).hexdigest() == run.get("features_sha256"), f"{mode}: features sha differs from run.json")
    with np.load(path, allow_pickle=False) as z:
        want = {}
        for pre, (_, n, _) in (("fit", MODES[mode]["fit"]), ("ev", MODES[mode]["ev"])):
            want[f"{pre}_key_ids"] = (n, N_BIND); want[f"{pre}_value_ids"] = (n, N_BIND)
            for l in LAYERS:
                want[f"{pre}_zk_L{l}"] = (n, N_BIND, D_MODEL); want[f"{pre}_zv_L{l}"] = (n, N_BIND, D_MODEL)
        require(set(z.files) == set(want), f"{mode}: features arrays differ from the frozen set")
        for k, shape in want.items():
            require(z[k].shape == shape, f"{mode}: {k} shape {z[k].shape} != {shape}")
            require(bool(np.all(np.isfinite(z[k]))), f"{mode}: nonfinite {k}")


def _check_metrics(res: dict, mode: str) -> None:
    want = {f"L{l}/{s}" for l in LAYERS for s in SETS} | {f"L{l}/dVK" for l in LAYERS} | {f"L{l}/dVK_vs_K (descriptive)" for l in LAYERS}
    met = res.get("metrics") or {}
    require(set(met) == want, f"{mode}: metric keys differ from the frozen set")
    require(_all_finite(met) and _all_finite(res.get("timing_s")), f"{mode}: nonfinite value in result")
    for k, v in met.items():
        trip = v.get("top1_point_lo_hi", v.get("point_lo_hi"))
        lo_ok = -1.0 if "dVK" in k else 0.0
        require(isinstance(trip, list) and len(trip) == 3 and all(lo_ok <= x <= 1.0 for x in trip), f"{mode}: {k} out of range")
    rd = res.get("reading") or {}
    require(rd.get("label") in LABELS and rd.get("read") is (mode == "full"), f"{mode}: reading malformed")


def validate_admission(adm: dict) -> float:
    c = adm.get("components") or {}
    parts = [c.get(k) for k in ("capture_s_per_episode", "model_load_s", "fit_s", "boot_s", "output_s")]
    require(all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in parts), "admission parts missing")
    require(_all_finite(adm) and all(x >= 0 for x in parts), "admission parts must be finite and >= 0")
    cap, load, fit, boot, out = parts
    est = load + cap * FULL_EPISODES + fit + boot + out + MARGIN_S
    require(math.isclose(adm.get("estimate_s", -1), est, rel_tol=1e-9, abs_tol=1e-6), "admission estimate does not recompute")
    require(math.isclose(adm.get("wall_s", -1), 2.0 * est, rel_tol=1e-9, abs_tol=1e-6), "admission wall != 2 x estimate")
    require(adm.get("admit") is bool(0 < adm["wall_s"] <= M.WALL_CAP_S), "admission admit flag inconsistent with wall")
    return float(adm["wall_s"])


def validate_receipt(stage_dir: Path, mode: str, shas: dict | None = None) -> dict:
    stage_dir, shas = Path(stage_dir), (shas or source_shas())
    exit_file = Path(str(stage_dir) + ".exit")
    require(exit_file.is_file() and exit_file.read_text().strip() == "0", f"{mode}: exit receipt missing or nonzero")
    status = strict_json(stage_dir / "status.json")
    require(status.get("state") == "COMPLETE", f"{mode}: status {status.get('state')!r}, not COMPLETE")
    res = strict_json(stage_dir / "result.json")
    require((stage_dir / "run.json").is_file() and strict_json(stage_dir / "run.json") == res.get("run"), f"{mode}: run.json missing or differs")
    init = _check_run(res["run"], mode, shas)
    _check_features(stage_dir / "features.npz", res["run"], mode)
    _check_metrics(res, mode)
    out = {"mode": mode, "label": res["reading"]["label"], "initial_adapter_params_sha256": init}
    if mode == "s1":
        adm = strict_json(stage_dir / "admission.json")
        require(adm == res.get("admission"), "s1: admission.json differs from result.json")
        wall = validate_admission(adm)
        require(adm["admit"] is True, "s1: admission did not admit the full run")
        out["wall_s"] = M.validate_wall(wall)
    return out


def full_wall(s1_dir: Path, s2_dir: Path) -> int:
    shas = source_shas()
    s1, s2 = validate_receipt(s1_dir, "s1", shas), validate_receipt(s2_dir, "s2", shas)
    require(s1["initial_adapter_params_sha256"] == s2["initial_adapter_params_sha256"], "s1/s2 initial adapter hashes differ")
    return int(M.validate_wall(math.ceil(s1["wall_s"])))


def validate_full(full_dir: Path, s1_dir: Path, s2_dir: Path) -> dict:
    w = full_wall(s1_dir, s2_dir)
    v = validate_receipt(full_dir, "full")
    s1 = validate_receipt(s1_dir, "s1")
    require(v["initial_adapter_params_sha256"] == s1["initial_adapter_params_sha256"], "full/s1 initial adapter hashes differ")
    require(strict_json(Path(full_dir) / "run.json")["wall_s"] == w, "full: run wall differs from the admitted wall")
    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", choices=("s1", "s2", "full"))
    ap.add_argument("--dir", type=Path)
    ap.add_argument("--full-wall", action="store_true")
    ap.add_argument("--s1", type=Path)
    ap.add_argument("--s2", type=Path)
    a = ap.parse_args()
    try:
        if a.full_wall:
            print(full_wall(a.s1, a.s2))
        elif a.validate == "full":
            print(json.dumps(validate_full(a.dir, a.s1, a.s2)))
        else:
            print(json.dumps(validate_receipt(a.dir, a.validate)))
        return 0
    except (RuntimeError, OSError, KeyError, ValueError, TypeError, AttributeError) as e:
        print(f"RECEIPT INVALID: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
