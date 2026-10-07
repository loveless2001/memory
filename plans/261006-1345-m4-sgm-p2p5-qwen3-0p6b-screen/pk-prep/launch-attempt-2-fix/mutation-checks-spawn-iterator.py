"""Launch attempt-2 SPAWN-ITERATOR repair mutation checks (modal Dict.keys() generator; codex 21645): each mutation undoes one part of the fix IN PLACE, runs the focused tests
and restores the original bytes (sha256-verified) in `finally`. A check passes iff the mutated runner makes at
least one test FAIL — and the TARGETED test must be among the failures (a mutated runner also breaks the
launch-manifest binding test, which must not be what catches it). Run from the repo root: .venv/bin/python <this file>."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SLOT = "modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py"
READ = "modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py"
MANIFEST = "configs/m4_sgm_p2p5_campaign_analysis_manifest.json"
FREEZE = ("import importlib.util, json, sys; sys.path.insert(0, '.');"
          "s = importlib.util.spec_from_file_location('m', 'scripts/sgm-p2p5-pk-campaign-analysis-dependency-manifest.py');"
          "m = importlib.util.module_from_spec(s); s.loader.exec_module(m);"
          f"open('{MANIFEST}', 'w').write(json.dumps(m.freeze(), indent=2, sort_keys=True) + chr(10))")
TESTS = ["tests/test_sgm_pk_campaign_slot_runner_and_control_app.py",
         "tests/test_sgm_pk_control_plane_reaper_and_manifest_label.py",
         "tests/test_sgm_pk_campaign_readings_runner.py"]
MUTATIONS = {  # name: (file, edits, targeted test)
    "slot spawn back to len(guard.keys()) (attempt-2 spawn bug)": (SLOT, [
        ("    if any(True for _ in guard.keys()):", "    if len(guard.keys()):")],
        "test_spawn_uses_one_immutable_deadline_despite_clock_advance"),
    "slot spawn first-key check (codex 21645: a None key reads as unused)": (SLOT, [
        ("    if any(True for _ in guard.keys()):", "    if next(iter(guard.keys()), None) is not None:")],
        "test_slot_spawn_refuses_any_populated_guard_with_generator_keys[none]"),
    "readings spawn back to len(guard.keys())": (READ, [
        ("    if any(True for _ in guard.keys()):", "    if len(guard.keys()):")],
        "test_spawn_guard_check_handles_modal_generator_keys[empty]"),
    "readings spawn first-key check": (READ, [
        ("    if any(True for _ in guard.keys()):", "    if next(iter(guard.keys()), None) is not None:")],
        "test_spawn_guard_check_handles_modal_generator_keys[none-key]"),
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    results = {}
    for name, (rel, edits, target) in MUTATIONS.items():
        path = ROOT / rel
        original, digest = path.read_bytes(), sha(path)
        mpath = ROOT / MANIFEST
        m_original, m_digest = mpath.read_bytes(), sha(mpath)
        try:
            text = original.decode()
            for a, b in edits:
                if a not in text:
                    raise SystemExit(f"{name}: anchor not found in {rel}")
                text = text.replace(a, b)
            path.write_text(text)
            # re-freeze the launch manifest over the mutated bytes (restored below) so the manifest refusal cannot
            # be what catches the mutation: only the targeted guard-check test may
            subprocess.run([sys.executable, "-c", FREEZE], cwd=ROOT, check=True)
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rf", "-p", "no:cacheprovider", *TESTS],
                               cwd=ROOT, capture_output=True, text=True, timeout=900)
            tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
            failed = [ln.split(" ", 1)[1].split(" - ")[0] for ln in r.stdout.splitlines() if ln.startswith("FAILED ")]
            results[name] = {"pytest_rc": r.returncode, "summary": tail, "failed": failed,
                             "caught": any(target in f for f in failed)}
        finally:
            path.write_bytes(original)
            mpath.write_bytes(m_original)
            assert sha(path) == digest and sha(mpath) == m_digest, f"{rel} / manifest not restored"
    print(json.dumps(results, indent=2))
    sys.exit(0 if all(v["caught"] for v in results.values()) else 1)


if __name__ == "__main__":
    main()
