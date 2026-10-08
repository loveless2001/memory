"""Private-copy mutation checks: each mutant (script or runner) must make the focused Stage-A tests FAIL."""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path.cwd()
S, RN = "scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py", "modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py"
TEST = (ROOT / "tests/test_sgm_p2p5_taskhead_read_escape_stage_a.py").read_text()
MUT = {
    "A0 gate ignores escape": (RN, 'if arm == "A0" and r.get("band_at_100") != "escaped":', 'if False:'),
    "no restart refusal": (RN, "    if not first:", "    if False:"),
    "missing endpoints accepted": (S, "    if tuple(sorted(evs)) != EVAL_STEPS:", "    if False:"),
    "A2 supervision dropped": (S, '"A2": {"aux_address_lambda": 0.1}', '"A2": {}'),
    "base recipe unchecked": (S, "    if bad:\n        raise", "    if False:\n        raise"),
    "kept-through uses endpoint only": (S, '"kept_through_100": all(v <= KEPT for v in evs.values())', '"kept_through_100": end <= KEPT'),
}
res = {}
for name, (f, a, b) in MUT.items():
    src = (ROOT / f).read_text()
    assert src.count(a) == 1, name
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for rel in (S, RN, "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"):
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, d / rel)
        (d / f).write_text(src.replace(a, b))
        (d / "memsub").symlink_to(ROOT / "memsub")
        (d / "tests").mkdir()
        (d / "tests/t.py").write_text(TEST.replace("ROOT = Path(__file__).resolve().parents[1]", f"ROOT = Path({str(d)!r})"))
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", str(d / "tests/t.py")], capture_output=True, text=True, cwd=d)
        res[name] = {"caught": r.returncode != 0, "tail": r.stdout.strip().splitlines()[-1:]}
print(json.dumps(res, indent=1))
sys.exit(0 if all(v["caught"] for v in res.values()) else 1)
