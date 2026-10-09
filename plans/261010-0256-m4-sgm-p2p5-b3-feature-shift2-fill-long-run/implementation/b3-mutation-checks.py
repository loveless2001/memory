"""Apply one mutant at a time to a B3 source file, run the B3 CPU tests (own basetemp, cloud sentinels inside
the tests), restore the original bytes. CAUGHT iff the test run fails normally; KILLED (rc 137: cgroup OOM or
wall timeout) is reported separately and is NOT a clean catch.

Crash safety (2026-10-10: the first version OOM-killed the host on mutant M4 and left the runner mutated):
  * each pytest runs in a `systemd-run --user --scope` with MemoryMax/MemorySwapMax and `timeout --signal=KILL`;
  * before mutating, the original bytes go to an on-disk backup + journal; a later start restores any stale
    mutant from them (sha256-checked) before doing anything else;
  * sources are sha256-pinned at start and re-verified at the end; an unmutated baseline must pass first."""
import hashlib, json, os, subprocess, sys, tempfile, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
JOURNAL, BACKUP = HERE / "b3-mutation-in-progress.json", HERE / "b3-mutation-backup.bin"
OUT = HERE / "b3-mutation-checks.json"
MEM_MAX, SWAP_MAX, WALL_S = "2000M", "0", 300
RUN = "modal-runners/modal-m4-sgm-p2p5-b3-shift2-fill-long-run-runner.py"
TRAIN = "scripts/sgm-p2p5-b3-shift2-fill-long-run-train.py"
MUTANTS = [
    ("M1 terminal check at entry removed", RUN, "        if starts.get(TERMINAL_KEY) is not None:\n", "        if False:\n"),
    ("M2 no terminal marker on completion", RUN,
     '        mark_terminal(starts, key, "completed" if rc == 0 else ("deadline" if rc == "timeout" else f"run-side failure rc {rc}"))\n', ""),
    ("M3 worker exception not caught", RUN, "    except Exception as e:                                       # a worker exception is run-side: never retried\n",
     "    except ZeroDivisionError as e:\n"),
    ("M4 cleanup stop without --yes", RUN, 'r = cli(["app", "stop", "--yes", app_id], False)', 'r = cli(["app", "stop", app_id], False)'),
    ("M5 deadline not write-once", RUN, "    if not starts.put(DEADLINE_KEY, deadline, skip_if_exists=True):", "    if not starts.put(DEADLINE_KEY, deadline):"),
    ("M6 feature_shift back to 1", TRAIN, 'SGM_OVERRIDES = {**FILL, "feature_shift": 2}', 'SGM_OVERRIDES = {**FILL, "feature_shift": 1}'),
    ("M7 precheck ignores a used Dict", RUN, "    if dict_keys:\n", "    if False:\n"),
    ("M8 deadline mismatch accepted", RUN, "    if starts_get(DEADLINE_KEY) != deadline:\n", "    if False:\n"),
    ("M9 ledger without build allowance", RUN, "    total = compute + BUILD_ALLOWANCE_USD\n", "    total = compute\n"),
    ("M10 versions mismatch not terminal", RUN, '            mark_terminal(starts, key, f"pinned versions differ: {ver[\'got\']}")\n', ""),
    ("M11 cleanup re-check cap removed", RUN, ' or len(rec["checks"]) >= max_checks:', ":"),
]
TESTS = ["tests/test_sgm_p2p5_b3_shift2_fill_long_run.py"]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_durable(p: Path, data: bytes):
    with open(p, "wb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())


def restore_stale():
    """A previous run was killed mid-mutant: put the backed-up original back, sha256-checked."""
    if not JOURNAL.exists():
        return
    j = json.loads(JOURNAL.read_text()); orig = BACKUP.read_bytes()
    if sha(orig) != j["sha256"]:
        sys.exit(f"STALE BACKUP CORRUPT for {j['path']}; restore by hand")
    write_durable(Path(j["path"]), orig); BACKUP.unlink(); JOURNAL.unlink()
    print(f"restored stale mutant in {j['path']} ({j['mutant']}) from backup")


def pytest_capped(tag: str):
    cmd = ["systemd-run", "--user", "--scope", "--quiet", f"--unit=b3mut-{tag}-{int(time.time())}",
           "-p", f"MemoryMax={MEM_MAX}", "-p", f"MemorySwapMax={SWAP_MAX}", "timeout", "--signal=KILL", str(WALL_S),
           sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
           "--basetemp", tempfile.mkdtemp(prefix="b3-mut-"), *TESTS]
    return subprocess.run(cmd, capture_output=True, text=True)


restore_stale()
pins = {p: sha(Path(p).read_bytes()) for p in (RUN, TRAIN)}
base = pytest_capped("baseline")
if base.returncode != 0:
    sys.exit(f"BASELINE FAILED rc {base.returncode}: {base.stdout.strip().splitlines()[-1:]}")
res = []
for i, (name, path, old, new) in enumerate(MUTANTS, 1):
    p = Path(path); orig = p.read_bytes(); src = orig.decode()
    if src.count(old) != 1:
        res.append({"mutant": name, "status": "PATTERN_NOT_FOUND"}); continue
    write_durable(BACKUP, orig)
    write_durable(JOURNAL, json.dumps({"path": path, "mutant": name, "sha256": sha(orig)}).encode())
    try:
        write_durable(p, src.replace(old, new).encode())
        r = pytest_capped(f"m{i}")
        status = "SURVIVED" if r.returncode == 0 else ("KILLED" if r.returncode in (137, -9) else "CAUGHT")
        res.append({"mutant": name, "status": status, "rc": r.returncode, "tail": r.stdout.strip().splitlines()[-1:]})
    finally:
        write_durable(p, orig); BACKUP.unlink(); JOURNAL.unlink()
    write_durable(OUT, json.dumps(res, indent=1).encode())
bad = [p for p, h in pins.items() if sha(Path(p).read_bytes()) != h]
if bad:
    sys.exit(f"SOURCES CHANGED AFTER RESTORE: {bad}")
print(json.dumps([(x["mutant"], x["status"]) for x in res]))
sys.exit(0 if all(x["status"] == "CAUGHT" for x in res) else 1)
