"""B3 mutation checks, v2 (codex 22506). Each mutant is applied to a DISPOSABLE copy of the committed HEAD
(`git archive HEAD` into a scratch dir); the shared working tree is never written, so a killed run cannot leave a
mutated source behind (v1 mutated in place and the 2026-10-10 host OOM on M4 left the runner mutated).

Containment: every pytest runs in a `systemd-run --user --scope` with MemoryMax/MemorySwapMax and
`timeout --signal=KILL`, with cwd = the copy (so `memsub` and every ROOT-relative file resolve inside it).

Classification (pytest -x, so at most one failing test):
  CAUGHT      rc 1 and the failing test is one of the mutant's EXPECTED tests
  WRONG_TEST  rc 1 but a different test failed (the guard was not what caught it)
  SURVIVED    rc 0
  KILLED      rc 137/-9 (cgroup OOM or wall timeout)
  INFRA_ERROR anything else (collection error, usage error, systemd failure, ...)
The worktree's B3 files must equal HEAD before the run and be unchanged after it."""
import hashlib, json, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
OUT = HERE / "b3-mutation-checks-v2.json"
MEM_MAX, SWAP_MAX, WALL_S = "2000M", "0", 300
RUN = "modal-runners/modal-m4-sgm-p2p5-b3-shift2-fill-long-run-runner.py"
TRAIN = "scripts/sgm-p2p5-b3-shift2-fill-long-run-train.py"
TESTS = "tests/test_sgm_p2p5_b3_shift2_fill_long_run.py"
# (name, file, original, mutant, expected failing tests)
MUTANTS = [
    ("M1 terminal check at entry removed", RUN, "        if starts.get(TERMINAL_KEY) is not None:\n", "        if False:\n",
     {"test_worker_marks_terminal_on_every_non_interruption_outcome"}),
    ("M2 no terminal marker on completion", RUN,
     '        mark_terminal(starts, key, "completed" if rc == 0 else ("deadline" if rc == "timeout" else f"run-side failure rc {rc}"))\n', "",
     {"test_worker_marks_terminal_on_every_non_interruption_outcome"}),
    ("M3 worker exception not caught", RUN, "    except Exception as e:                                       # a worker exception is run-side: never retried\n",
     "    except ZeroDivisionError as e:\n", {"test_worker_refusals_and_exceptions_are_terminal"}),
    ("M4 cleanup stop without --yes", RUN, 'r = cli(["app", "stop", "--yes", app_id], False)', 'r = cli(["app", "stop", app_id], False)',
     {"test_cleanup_uses_yes_and_verifies_a_deployed_app"}),
    ("M5 deadline not write-once", RUN, "    if not starts.put(DEADLINE_KEY, deadline, skip_if_exists=True):", "    if not starts.put(DEADLINE_KEY, deadline):",
     {"test_precheck_and_deadline_are_fresh_and_write_once"}),
    ("M6 feature_shift back to 1", TRAIN, 'SGM_OVERRIDES = {**FILL, "feature_shift": 2}', 'SGM_OVERRIDES = {**FILL, "feature_shift": 1}',
     {"test_config_is_b2_plus_feature_shift2_only"}),
    ("M7 precheck ignores a used Dict", RUN, "    if dict_keys:\n", "    if False:\n",
     {"test_precheck_and_deadline_are_fresh_and_write_once"}),
    ("M8 deadline mismatch accepted", RUN, "    if starts_get(DEADLINE_KEY) != deadline:\n", "    if False:\n",
     {"test_worker_refusals_and_exceptions_are_terminal"}),                # its [deadline_mismatch] case
    ("M9 ledger without build allowance", RUN, "    total = compute + BUILD_ALLOWANCE_USD\n", "    total = compute\n",
     {"test_ledger_matches_proposal_v03"}),
    ("M10 versions mismatch not terminal", RUN, '            mark_terminal(starts, key, f"pinned versions differ: {ver[\'got\']}")\n', "",
     {"test_worker_refusals_and_exceptions_are_terminal"}),
    ("M11 cleanup re-check cap removed", RUN, ' or len(rec["checks"]) >= max_checks:', ":",
     {"test_cleanup_recheck_loop_is_bounded_even_if_sleep_does_not_wait"}),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pytest_capped(copy: Path, tag: str):
    cmd = ["systemd-run", "--user", "--scope", "--quiet", f"--unit=b3mut-{tag}-{int(time.time())}",
           "-p", f"MemoryMax={MEM_MAX}", "-p", f"MemorySwapMax={SWAP_MAX}", "timeout", "--signal=KILL", str(WALL_S),
           sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
           "--basetemp", tempfile.mkdtemp(prefix="b3-mut-bt-"), TESTS]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=copy)


def classify(r, expected: set) -> tuple:
    failed = re.findall(r"^FAILED \S+?::(\S+)", r.stdout, re.M)            # full id, incl. [param]
    if r.returncode == 0:
        return "SURVIVED", failed
    if r.returncode in (137, -9):
        return "KILLED", failed
    if r.returncode == 1 and failed:
        return ("CAUGHT" if {f.split("[")[0] for f in failed} <= expected else "WRONG_TEST"), failed
    return "INFRA_ERROR", failed


def main() -> int:
    files = (RUN, TRAIN, TESTS)
    pins = {f: sha(WORKTREE / f) for f in files}
    copy = Path(tempfile.mkdtemp(prefix="b3-mut-tree-"))
    try:
        subprocess.run(f"git -C '{WORKTREE}' archive HEAD | tar -x -C '{copy}'", shell=True, check=True)
        drift = [f for f in files if sha(copy / f) != pins[f]]
        if drift:
            sys.exit(f"WORKTREE != HEAD for {drift}: commit first, mutants run on HEAD")
        base = pytest_capped(copy, "baseline")
        if base.returncode != 0:
            sys.exit(f"BASELINE FAILED rc {base.returncode}: {base.stdout.strip().splitlines()[-3:]}")
        res = [{"baseline": base.stdout.strip().splitlines()[-1]}]
        for i, (name, rel, old, new, expected) in enumerate(MUTANTS, 1):
            p = copy / rel
            orig = p.read_bytes()
            src = orig.decode()
            if src.count(old) != 1:
                res.append({"mutant": name, "status": "PATTERN_NOT_FOUND"})
                continue
            p.write_text(src.replace(old, new))
            r = pytest_capped(copy, f"m{i}")
            p.write_bytes(orig)
            status, failed = classify(r, expected)
            res.append({"mutant": name, "status": status, "rc": r.returncode, "failed": failed,
                        "expected": sorted(expected), "tail": r.stdout.strip().splitlines()[-1:]})
            OUT.write_text(json.dumps(res, indent=1))
    finally:
        shutil.rmtree(copy, ignore_errors=True)
    changed = [f for f in files if sha(WORKTREE / f) != pins[f]]
    if changed:
        sys.exit(f"SHARED SOURCES CHANGED DURING RUN: {changed}")
    print(json.dumps([(x["mutant"], x["status"], x.get("failed")) for x in res[1:]]))
    return 0 if all(x["status"] == "CAUGHT" for x in res[1:]) else 1


if __name__ == "__main__":
    sys.exit(main())
