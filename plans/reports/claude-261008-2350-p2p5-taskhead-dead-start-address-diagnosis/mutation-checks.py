"""Private-copy mutation checks: each mutant of the diagnosis script must make the focused tests FAIL."""
import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path.cwd()
SRC = (ROOT / "scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py").read_text()
TEST = (ROOT / "tests/test_sgm_p2p5_taskhead_dead_start_address_diagnosis.py").read_text()
MUTANTS = {
    "oracle query not wired (1b66312 bug)": ('oracle = b.oracle_query[:, q:q + 1] if pcfg.arm == "oracle" else None', "oracle = None"),
    "missing telemetry accepted": ("    if len(evs) != 1:\n        raise", "    if len(evs) > 1:\n        raise"),
    "non-finite accepted": ("math.isfinite(v) for v in logged", "True for v in logged"),
    "tolerance instead of exact absence": ("(absent | ~(e.weights > 0)).all(-1)", "((e.weights * absent).sum(-1) > 1 - 1e-6)"),
    "checkpoint step unchecked": ('if c["step"] != e["expected_step"]:', "if False:"),
    "identity not enforced": ("        if v != want[k]:\n", "        if False:\n"),
}
res = {}
for name, (a, b) in MUTANTS.items():
    assert SRC.count(a) == 1, name
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "scripts").mkdir(); (d / "tests").mkdir()
        (d / "scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py").write_text(SRC.replace(a, b))
        (d / "tests/t.py").write_text(TEST.replace('ROOT = Path(__file__).resolve().parents[1]',
                                                   f'ROOT = Path({str(d)!r})').replace(
            "capture_output=True, text=True, cwd=ROOT)", f"capture_output=True, text=True, cwd={str(ROOT)!r})"))
        (d / "memsub").symlink_to(ROOT / "memsub")
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", str(d / "tests/t.py")], capture_output=True,
                           text=True, cwd=ROOT)
        res[name] = {"caught": r.returncode != 0, "tail": r.stdout.strip().splitlines()[-1:]}
print(json.dumps(res, indent=1))
sys.exit(0 if all(v["caught"] for v in res.values()) else 1)
