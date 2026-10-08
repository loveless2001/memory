"""Private-copy mutation checks: each mutant (script or runner) must make the focused Stage-A tests FAIL."""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path.cwd()
S, RN = "scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py", "modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py"
TEST = (ROOT / "tests/test_sgm_p2p5_taskhead_read_escape_stage_a.py").read_text()
MUT = {
    "A0 gate ignores escape": (RN, [('if arm == "A0" and r.get("band_at_100") != "escaped":', 'if False:')]),
    "no restart refusal": (RN, [('"t": time.time()}, skip_if_exists=True):', '"t": time.time()}):')]),
    "shared output dir across calls (codex 21987 #1)": (RN, [('out = Path(tempfile.mkdtemp(prefix=f"stage-a-{arm}-"))',
        'out = Path(tempfile.mkdtemp(prefix="x")).parent / "stage-a-shared"; out.mkdir(exist_ok=True)')]),
    "deadline mismatch accepted": (RN, [('if starts.get("deadline") != deadline:', 'if False:')]),
    "remaining sampled at entry, not re-read (codex 21999)": (RN, [
        ("    if deadline - time.time() <= END_MARGIN_S:", "    t_entry = time.time()\n    if deadline - t_entry <= END_MARGIN_S:"),
        ("        remaining = deadline - time.time()          # RE-READ", "        remaining = deadline - t_entry          # RE-READ")]),
    "minimum remaining not enforced": (RN, [("if remaining < MIN_ARM_S:", "if False:")]),
    "child timeout ignores deadline": (RN, [("child_s = min(CHILD_S, remaining - END_MARGIN_S)", "child_s = CHILD_S")]),
    "entry refusal removed": (RN, [("    if deadline - time.time() <= END_MARGIN_S:", "    if False:")]),
    "no worker guard": (RN, [("worker_guard = deadline_killer(str(os.getpid()), deadline - time.time())", "worker_guard = None")]),
    "no child group guard": (RN, [('child_guard = deadline_killer(f"-{child.pid}", deadline - time.time())', "child_guard = None")]),
    "child not in its own session": (RN, [("text=True,\n                                 start_new_session=True)", "text=True)")]),
    "killer cancel is a no-op": (RN, [("os.killpg(proc.pid, signal.SIGKILL)       # the sleeper", "pass  # os.killpg(proc.pid, signal.SIGKILL)       # the sleeper")]),
    "version check skipped": (RN, [('if not ver["ok"]:', "if False:")]),
    "relaunch on used Dict allowed": (RN, [('if not starts.put("deadline", deadline, skip_if_exists=True):', 'if not starts.put("deadline", deadline):')]),
    "cleanup accepts unverified": (RN, [('rec["status"] = "stopped_verified" if rec["checks"][-1].get("verified") is True else "shutdown_unresolved"',
                                         'rec["status"] = "stopped_verified"')]),
    "cleanup does not re-check lagging tasks": (RN, [("for i in range(attempts):", "for i in range(1):")]),
    "missing endpoints accepted": (S, [("    if tuple(sorted(evs)) != EVAL_STEPS:", "    if False:")]),
    "booleans / out-of-range accepted (codex 21987 #3)": (S, [("and not isinstance(v, bool) and math.isfinite(v) and 0.0 <= v <= 1.0", "and math.isfinite(v)")]),
    "A2 supervision dropped": (S, [('"A2": {"aux_address_lambda": 0.1}', '"A2": {}')]),
    "base recipe unchecked": (S, [("    if bad:\n        raise", "    if False:\n        raise")]),
    "kept-through uses endpoint only": (S, [('"kept_through_100": all(v <= KEPT for v in evs.values())', '"kept_through_100": end <= KEPT')]),
}
res = {}
for name, (f, pairs) in MUT.items():
    src = (ROOT / f).read_text()
    for a, b in pairs:
        assert src.count(a) == 1, (name, a)
        src = src.replace(a, b)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for rel in (S, RN, "modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py", "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"):
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, d / rel)
        (d / f).write_text(src)
        (d / "memsub").symlink_to(ROOT / "memsub")
        (d / "tests").mkdir()
        (d / "tests/t.py").write_text(TEST.replace("ROOT = Path(__file__).resolve().parents[1]", f"ROOT = Path({str(d)!r})"))
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", str(d / "tests/t.py")], capture_output=True, text=True, cwd=d)
        res[name] = {"caught": r.returncode != 0, "tail": r.stdout.strip().splitlines()[-1:]}
print(json.dumps(res, indent=1))
sys.exit(0 if all(v["caught"] for v in res.values()) else 1)
