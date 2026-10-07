"""Gate-3 rev2 mutation checks (codex 21617 R1/R3/R4/R5): each mutation undoes one fix IN PLACE, runs the focused
regression tests, and restores the original bytes (verified by sha256) in `finally`. A check passes iff the
mutated code makes at least one test FAIL. Run from the repo root: .venv/bin/python <this file>.
The R1 mutation edits the readings script, which the R2 manifest would refuse on its own; to isolate the ORDER test
it also re-freezes the dependency manifest over the mutated bytes (restored afterwards), so only R1 can catch it."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
LOGIC = "modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py"
SLOT = "modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py"
READ = "scripts/sgm-p2p5-pk-campaign-readings.py"
MANIFEST = "configs/m4_sgm_p2p5_campaign_analysis_manifest.json"
TESTS = ["tests/test_sgm_pk_campaign_collect_hardening_codex_r3_r4_r5.py",
         "tests/test_sgm_pk_campaign_readings_orchestration_fast.py"]
MUTATIONS = {
    "R4 verdict ignores tasks and containers": (LOGIC, [
        (' and str(r.get("tasks")) == "0" for r in mine)', ' for r in mine)'),
        ('    return app_ok and not any(r.get("app_id") == app_id for r in container_rows)', '    return app_ok')]),
    "R3 no bound-id checks": (LOGIC, [
        ('    if not (isinstance(prov.get("deployed_app_id"), str) and prov["deployed_app_id"].strip()):\n'
         '        return "launch provenance has no bound app id (a name-only stop is never allowed)"\n', ''),
        ('    if not (isinstance(app_id, str) and app_id.strip()):\n'
         '        raise ValueError("no bound app id: name-only stop refused")\n', '')]),
    "R5 no fetch gate and no per-cell containment": (SLOT, [
        ('if report["evidence"].get("returncode") != 0 or dicts is None:', 'if dicts is None:'),
        ('    except (ValueError, KeyError, TypeError, IndexError, AttributeError, OSError) as e:\n'
         '        return {"state": "INVALID", "problem": f"malformed cell evidence: {e!r:.300}"}',
         '    except ZeroDivisionError:\n        raise')]),
    "R1 interleaved order (phase 2 inside phase 1)": (READ, [
        ('            res["interface"] = DR.interface_ok(acc)\n            report["n"][str(n)] = res\n',
         '            res["interface"] = DR.interface_ok(acc)\n            report["n"][str(n)] = res\n'
         '            if res["interface"]:\n                read_n(n, res, cells, pilots, out)\n')]),
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    results = {}
    for name, (rel, edits) in MUTATIONS.items():
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
            if rel == READ:                                  # isolate R1 from the R2 manifest refusal
                freeze = ("import importlib.util, json, sys; sys.path.insert(0, '.');"
                          "s = importlib.util.spec_from_file_location('m', 'scripts/sgm-p2p5-pk-campaign-analysis-dependency-manifest.py');"
                          "m = importlib.util.module_from_spec(s); s.loader.exec_module(m);"
                          f"open('{MANIFEST}', 'w').write(json.dumps(m.freeze(), indent=2, sort_keys=True) + chr(10))")
                subprocess.run([sys.executable, "-c", freeze], cwd=ROOT, check=True)
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *TESTS],
                               cwd=ROOT, capture_output=True, text=True, timeout=900)
            tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
            results[name] = {"pytest_rc": r.returncode, "summary": tail, "caught": r.returncode != 0}
        finally:
            path.write_bytes(original)
            mpath.write_bytes(m_original)
            assert sha(path) == digest and sha(mpath) == m_digest, f"{rel} / manifest not restored"
    print(json.dumps(results, indent=2))
    sys.exit(0 if all(v["caught"] for v in results.values()) else 1)


if __name__ == "__main__":
    main()
