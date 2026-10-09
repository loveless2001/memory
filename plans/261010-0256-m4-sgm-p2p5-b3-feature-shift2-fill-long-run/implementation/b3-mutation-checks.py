"""B3 mutation checks, v4 (codex 22506/22511; v4 adds the codex 22515 fail-closed/containment guards). Each mutant is applied to a DISPOSABLE copy of the committed HEAD
(`git archive HEAD` into a scratch dir); the shared working tree is never written, so a killed run cannot leave a
mutated source behind (v1 mutated in place and the 2026-10-10 host OOM on M4 left the runner mutated).

Containment: every pytest runs in a `systemd-run --user --scope` with MemoryMax/MemorySwapMax and
`timeout --signal=KILL`, with cwd = the copy (so `memsub` and every ROOT-relative file resolve inside it).

Classification (pytest -x, so at most one failing test):
  CAUGHT      rc 1 and the failing test id (incl. [param]) is one of the mutant's EXPECTED ids
  WRONG_TEST  rc 1 but a different test failed (the guard was not what caught it)
  SURVIVED    rc 0
  KILLED      rc 137/-9 (cgroup OOM or wall timeout)
  INFRA_ERROR anything else (collection error, usage error, systemd failure, ...)
The worktree's B3 files must equal HEAD before the run and be unchanged after it. Child output goes to a file and
only its last TAIL_BYTES are read, so the parent stays small; run the parent itself in a capped scope too."""
import hashlib, json, re, shutil, subprocess, sys, tempfile, time, types
from pathlib import Path
HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
OUT = HERE / "b3-mutation-checks-v4.json"            # v2/v3 evidence is kept as is
MEM_MAX, SWAP_MAX, WALL_S, TAIL_BYTES = "2000M", "0", 300, 256 * 1024
RUN = "modal-runners/modal-m4-sgm-p2p5-b3-shift2-fill-long-run-runner.py"
TRAIN = "scripts/sgm-p2p5-b3-shift2-fill-long-run-train.py"
TESTS = "tests/test_sgm_p2p5_b3_shift2_fill_long_run.py"
# (name, file, original, mutant, expected failing test ids)
MUTANTS = [
    ("M1 terminal check at entry removed", RUN, "    if starts.get(TERMINAL_KEY) is not None:\n", "    if False:\n",
     {"test_worker_marks_terminal_on_every_non_interruption_outcome[0-completed]"}),
    ("M2 no terminal marker on completion", RUN,
     '    _terminal(ctx, "completed" if rc == 0 else ("deadline" if rc == "timeout" else f"run-side failure rc {rc}"))\n', "",
     {"test_worker_marks_terminal_on_every_non_interruption_outcome[0-completed]"}),
    ("M3 worker exception not caught", RUN, "    except Exception as e:                                       # a worker exception is run-side: never retried\n",
     "    except ZeroDivisionError as e:\n", {"test_worker_refusals_and_exceptions_are_terminal[exception]"}),
    ("M4 cleanup stop without --yes", RUN, 'r = cli(["app", "stop", "--yes", app_id], False)', 'r = cli(["app", "stop", app_id], False)',
     {"test_cleanup_uses_yes_and_verifies_a_deployed_app"}),
    ("M5 deadline not write-once", RUN, "    if not starts.put(DEADLINE_KEY, deadline, skip_if_exists=True):", "    if not starts.put(DEADLINE_KEY, deadline):",
     {"test_precheck_and_deadline_are_fresh_and_write_once"}),
    ("M6 feature_shift back to 1", TRAIN, 'SGM_OVERRIDES = {**FILL, "feature_shift": 2}', 'SGM_OVERRIDES = {**FILL, "feature_shift": 1}',
     {"test_config_is_b2_plus_feature_shift2_only"}),
    ("M7 precheck ignores a used Dict", RUN, "    if dict_keys:\n", "    if False:\n",
     {"test_precheck_and_deadline_are_fresh_and_write_once"}),
    ("M8 deadline mismatch accepted", RUN, "    if starts_get(DEADLINE_KEY) != deadline:\n", "    if False:\n",
     {"test_worker_refusals_and_exceptions_are_terminal[deadline_mismatch]"}),
    ("M9 ledger without build allowance", RUN, "    total = compute + BUILD_ALLOWANCE_USD\n", "    total = compute\n",
     {"test_ledger_matches_proposal_v03"}),
    ("M10 versions mismatch not terminal", RUN, '        _terminal(ctx, f"pinned versions differ: {ver[\'got\']}")\n', "",
     {"test_worker_refusals_and_exceptions_are_terminal[versions]"}),
    ("M11 cleanup re-check cap removed", RUN, ' or len(rec["checks"]) >= max_checks:', ":",
     {"test_cleanup_recheck_loop_is_bounded_even_if_sleep_does_not_wait"}),
    ("M12 watchdog + Dict lookup outside the guarded block (22515 bug)", RUN,
     '    worker_guard = None\n    try:\n        worker_guard = deadline_killer(str(os.getpid()), deadline - clock())     # before any blocking setup\n'
     '        ctx["starts"] = ctx["starts"] or modal.Dict.from_name(START_DICT)\n',
     '    worker_guard = deadline_killer(str(os.getpid()), deadline - clock())\n'
     '    ctx["starts"] = ctx["starts"] or modal.Dict.from_name(START_DICT)\n    try:\n',
     {"test_worker_contains_a_failed_dict_lookup_and_cancels_its_watchdog"}),
    ("M13 terminal write failure re-raised (22515 bug)", RUN,
     '        return None\n    except Exception as e:\n        return f"{type(e).__name__}: {str(e)[:200]}"\n',
     '        return None\n    except Exception as e:\n        raise\n',
     {"test_worker_reports_a_failed_terminal_write_instead_of_raising[versions]"}),
    ("M14 any listing error means fresh (22515 bug)", RUN,
     "    except (modal.exception.NotFoundError, FileNotFoundError):     # run dir absent on a fresh Volume\n",
     "    except Exception:\n", {"test_volume_listing_errors_fail_closed_in_precheck_and_collect[exc0]"}),
    ("M15 collect gate ignores what this call fetched (22515 bug)", RUN,
     '    if f"{ARMS[0]}/b3_result.json" not in fetched:\n', "    if False:\n",
     {"test_collect_never_passes_on_stale_local_results"}),
    ("M16 precheck lets a listing error escape", RUN,
     "    except Exception as e:                           # fail closed: an unreadable Volume is NOT a fresh one\n",
     "    except ZeroDivisionError as e:\n", {"test_volume_listing_errors_fail_closed_in_precheck_and_collect[exc0]"}),
    ("M17 ledger window without the watch grace", RUN, "    window = CAMPAIGN_S + END_MARGIN_S + CLEANUP_S\n",
     "    window = CAMPAIGN_S + CLEANUP_S\n", {"test_ledger_matches_proposal_v03"}),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pytest_capped(copy: Path, tag: str):
    cmd = ["systemd-run", "--user", "--scope", "--quiet", f"--unit=b3mut-{tag}-{int(time.time())}",
           "-p", f"MemoryMax={MEM_MAX}", "-p", f"MemorySwapMax={SWAP_MAX}", "timeout", "--signal=KILL", str(WALL_S),
           sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
           "--basetemp", tempfile.mkdtemp(prefix="b3-mut-bt-"), TESTS]
    log = Path(tempfile.mkdtemp(prefix="b3-mut-log-")) / f"{tag}.log"
    with open(log, "wb") as f:
        rc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=copy).returncode
    with open(log, "rb") as f:
        f.seek(max(0, log.stat().st_size - TAIL_BYTES))
        tail = f.read().decode(errors="replace")
    return types.SimpleNamespace(returncode=rc, stdout=tail)


def classify(r, expected: set) -> tuple:
    failed = re.findall(r"^FAILED \S+?::(\S+)", r.stdout, re.M)            # full id, incl. [param]
    if r.returncode == 0:
        return "SURVIVED", failed
    if r.returncode in (137, -9):
        return "KILLED", failed
    if r.returncode == 1 and failed:
        return ("CAUGHT" if set(failed) <= expected else "WRONG_TEST"), failed
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
