"""P2.5 Amendment PK — frozen analysis/launch dependency manifest (codex 21617 R2; prereg R5 start/end binding).

    .venv/bin/python scripts/sgm-p2p5-pk-campaign-analysis-dependency-manifest.py --out <new json>

The manifest is NON-circular: it lists the bytes the campaign consumes and is itself bound by its own sha256 (passed
by the launcher as `expected["manifest"]`, recorded in the readings report and the package index); it never lists
its own hash.
  - `analysis`: every script module the readings script reaches (closure over loaded script modules, so a transitive
    observer / decision-rule dependency cannot change silently) + grid, frozen registry/schema, prereg, amendment.
    Verified INSIDE the readings run before any population access and again at the end.
  - `launch`: runners, control plane, shared stop logic, priced ledger and the execution docs; verified by every
    local spawn against the clean tree.
  - `memsub_source_sha256`: the memsub tree hash.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
FORMAT = "m4-sgm-p2p5-pk-campaign-analysis-manifest-v1"
PLAN = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
ANALYSIS_INPUTS = ("configs/m4_sgm_p2p5_grid.json", "configs/m4_sgm_p2p5_campaign_registry.json",
                   "configs/m4_sgm_p2p5_campaign_output_schema.json", f"{PLAN}/prereg.md",
                   "configs/m4_sgm_p2p5_pk_posthoc_validation_amendment.json",
                   f"{PLAN}/prereg-amendment-pk-packed-a100-resume.md")
LAUNCH_INPUTS = ("modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py",
                 "modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py",
                 "modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py",
                 "modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py",
                 "modal-runners/modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py",
                 "modal-runners/modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py",
                 f"{PLAN}/pk6/priced-estimate-v6.json", f"{PLAN}/pk-campaign-execution-supplement.md",
                 f"{PLAN}/pk-campaign-source-bridge-manifest-label.md",
                 f"{PLAN}/prereg-amendment-posthoc-validation-learned-n32-s1.md",
                 f"{PLAN}/pk-campaign-posthoc-amendment/learned-n32-s1-revalidation-record.json")


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def script_closure(modules, root: Path = ROOT) -> set[str]:
    """Repo-relative paths of every script module reachable from `modules` through module-valued attributes
    (the dynamically loaded observer / decision-rule chain stores each loaded module as an attribute)."""
    scripts, seen, stack, out = (root / "scripts").resolve(), set(), list(modules), set()
    while stack:
        m = stack.pop()
        f = getattr(m, "__file__", None)
        if not f or id(m) in seen or Path(f).resolve().parent != scripts:
            continue
        seen.add(id(m))
        out.add(Path(f).resolve().relative_to(root.resolve()).as_posix())
        stack.extend(v for v in vars(m).values() if isinstance(v, ModuleType))
    return out


def manifest_problem(root: Path, manifest: dict, memsub_sha: str, sections=("analysis",), closure=None) -> str | None:
    """None iff every listed file in `sections` exists with its frozen sha256, memsub matches and (if given) the
    reached script closure equals the frozen script set exactly (no unlisted or missing dependency)."""
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        return "dependency manifest: wrong format"
    if manifest.get("memsub_source_sha256") != memsub_sha:
        return "dependency manifest: memsub source differs"
    for sec in sections:
        for rel, want in sorted((manifest.get(sec) or {}).items()):
            p = root / rel
            if not p.is_file() or sha(p) != want:
                return f"dependency manifest: {sec} file {rel} missing or changed"
    if closure is not None:
        frozen = {k for k in manifest["analysis"] if k.startswith("scripts/")}
        if closure != frozen:
            return f"dependency manifest: script closure differs: {sorted(closure ^ frozen)}"
    return None


def freeze(root: Path = ROOT) -> dict:
    """Closure from a FRESH interpreter importing the readings script exactly as the readings run does."""
    probe = ("import importlib.util, json, sys; sys.path.insert(0, sys.argv[1]);"
             "s = importlib.util.spec_from_file_location('rd', sys.argv[1] + '/scripts/sgm-p2p5-pk-campaign-readings.py');"
             "m = importlib.util.module_from_spec(s); s.loader.exec_module(m);"
             "print(json.dumps(sorted(m.analysis_closure())))")
    closure = json.loads(subprocess.run([sys.executable, "-c", probe, str(root)], check=True, capture_output=True,
                                        text=True, cwd=root).stdout)
    sys.path.insert(0, str(root))
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    return {"format": FORMAT, "memsub_source_sha256": source_tree_sha256(root / "memsub"),
            "analysis": {rel: sha(root / rel) for rel in sorted([*closure, *ANALYSIS_INPUTS])},
            "launch": {rel: sha(root / rel) for rel in sorted(LAUNCH_INPUTS)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"refusing to overwrite {a.out}")
    a.out.write_text(json.dumps(freeze(), indent=2, sort_keys=True) + "\n")
    print(sha(a.out))


if __name__ == "__main__":
    main()
