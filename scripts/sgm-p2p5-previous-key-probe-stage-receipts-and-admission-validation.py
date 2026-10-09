"""Stage receipts for the previous-key information probe (proposal v0.4, codex 22408).

A stage (s1 | s2 | full) is SUCCESSFUL only if all of these hold:
  * the controller's `<stage_dir>.exit` file reads 0;
  * `status.json` says COMPLETE (a KILL leaves RUNNING);
  * `result.json` has the right mode and the CURRENT source hashes;
  * every number in it is finite;
  * for s1, `admission.json` admits with a finite wall in (0, 4 h].
The full run's wall = ceil(validated S1 wall). It is accepted only with a successful S2 receipt too.
CLI (used by the fail-stop controller):
  --validate s1|s2|full --dir D     exit 0 iff the receipt is valid
  --full-wall --s1 D1 --s2 D2       print the admitted integer wall, exit 0; else exit 1
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [ROOT / "scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py",
           ROOT / "scripts/sgm-p2p5-previous-key-probe-ridge-retrieval-readings.py",
           ROOT / "scripts/sgm-p2p5-previous-key-probe-capture-qwen-adapter-inputs.py",
           Path(__file__).resolve(),
           ROOT / "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"]
_spec = importlib.util.spec_from_file_location("pkmath_rx", SOURCES[1])
M = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(M)
require = M.require


def _reject_constant(c):
    raise RuntimeError(f"nonfinite: non-strict JSON constant {c}")


def strict_json(path: Path):
    """Strict JSON: NaN / Infinity / -Infinity are rejected (codex 22409)."""
    return json.loads(Path(path).read_text(), parse_constant=_reject_constant)


def source_shas() -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES}


def write_status(out: Path, state: str, **extra) -> None:
    """Atomic status write (tmp + rename + fsync)."""
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


def validate_receipt(stage_dir: Path, mode: str, shas: dict | None = None) -> dict:
    stage_dir = Path(stage_dir)
    exit_file = Path(str(stage_dir) + ".exit")
    require(exit_file.is_file() and exit_file.read_text().strip() == "0", f"{mode}: exit receipt missing or nonzero")
    status = strict_json(stage_dir / "status.json")
    require(status.get("state") == "COMPLETE", f"{mode}: status {status.get('state')!r}, not COMPLETE")
    res = strict_json(stage_dir / "result.json")
    require(res["run"]["mode"] == mode, f"{mode}: result is for mode {res['run']['mode']!r}")
    require(res["run"]["sha256"] == (shas or source_shas()), f"{mode}: source hashes differ from the current sources")
    require(_all_finite(res["metrics"]) and _all_finite(res["timing_s"]), f"{mode}: nonfinite value in result")
    out = {"mode": mode, "label": res["reading"]["label"]}
    if mode == "s1":
        adm = strict_json(stage_dir / "admission.json")
        require(adm.get("admit") is True, "s1: admission did not admit the full run")
        out["wall_s"] = M.validate_wall(adm["wall_s"])
    return out


def full_wall(s1_dir: Path, s2_dir: Path) -> int:
    shas = source_shas()
    s1 = validate_receipt(s1_dir, "s1", shas)
    validate_receipt(s2_dir, "s2", shas)
    return int(M.validate_wall(math.ceil(s1["wall_s"])))


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
        else:
            print(json.dumps(validate_receipt(a.dir, a.validate)))
        return 0
    except (RuntimeError, OSError, KeyError, ValueError) as e:
        print(f"RECEIPT INVALID: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
