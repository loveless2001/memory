"""Launch attempt-2 fix mutation checks: each mutation undoes one part of the fix IN PLACE, runs the focused tests
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
CTL = "modal-runners/modal-m4-sgm-p2p5-pk-campaign-control-plane-reaper.py"
TESTS = ["tests/test_sgm_pk_campaign_slot_runner_and_control_app.py",
         "tests/test_sgm_pk_control_plane_reaper_and_manifest_label.py"]
MUTATIONS = {  # name: (file, edits, targeted test)
    "module refusal also fires in the remote image-build container (attempt-1 bug)": (SLOT, [
        ("if SLOT not in SLOTS and modal.is_local():", "if SLOT not in SLOTS:")],
        "test_image_build_container_imports_without_the_slot_env_and_run_fails_closed"),
    "run_slot without the unset-slot fail-closed guard": (SLOT, [
        ('    if SLOT not in SLOTS:                         # fail closed before any admission claim or evidence access\n'
         '        return {"slot": SLOT, "status": "slot_unset"}\n', '')],
        "test_image_build_container_imports_without_the_slot_env_and_run_fails_closed"),
    "controller reuses the attempt-1 (unsuffixed) control Dicts": (CTL, [
        ('"m4-sgm-p2p5-pk-campaign-control-registry-r2"', '"m4-sgm-p2p5-pk-campaign-control-registry"'),
        ('"m4-sgm-p2p5-pk-campaign-control-guard-r2"', '"m4-sgm-p2p5-pk-campaign-control-guard"')],
        "test_slot_runner_horizon_constants_match_the_controller"),
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    results = {}
    for name, (rel, edits, target) in MUTATIONS.items():
        path = ROOT / rel
        original, digest = path.read_bytes(), sha(path)
        try:
            text = original.decode()
            for a, b in edits:
                if a not in text:
                    raise SystemExit(f"{name}: anchor not found in {rel}")
                text = text.replace(a, b)
            path.write_text(text)
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rf", "-p", "no:cacheprovider", *TESTS],
                               cwd=ROOT, capture_output=True, text=True, timeout=900)
            tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
            failed = [ln.split(" ", 1)[1].split(" - ")[0] for ln in r.stdout.splitlines() if ln.startswith("FAILED ")]
            results[name] = {"pytest_rc": r.returncode, "summary": tail, "failed": failed,
                             "caught": any(target in f for f in failed)}
        finally:
            path.write_bytes(original)
            assert sha(path) == digest, f"{rel} not restored"
    print(json.dumps(results, indent=2))
    sys.exit(0 if all(v["caught"] for v in results.values()) else 1)


if __name__ == "__main__":
    main()
