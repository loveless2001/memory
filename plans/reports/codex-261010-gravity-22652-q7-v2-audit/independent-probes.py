"""Audit only: every rmtree is blocked or simulated; no candidate changes."""
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import types
from unittest.mock import patch

AUDIT = Path(__file__).resolve().parent
SOURCE = AUDIT.parent / "claude-261010-1600-m4-sgm-q7-mutation-temp-cleanup-receipt/q7-mutation-temp-dirs-cleanup-fail-closed-v2.py"
EXPECTED = "e5fd3a39"
blob = SOURCE.read_bytes()
digest = hashlib.sha256(blob).hexdigest()
assert digest.startswith(EXPECTED), digest
checks, simulated_calls = {}, []


def load(label):
    m = types.ModuleType("q7_audit_" + label)
    m.__file__ = str(SOURCE)
    exec(compile(blob, str(SOURCE), "exec"), m.__dict__)
    m.OUT = AUDIT / label
    m.OUT.mkdir(exist_ok=True)
    return m


def blocked(path):
    raise AssertionError("Real removal is forbidden by this independent audit")


def receipt(m, mode="execute"):
    return json.loads((m.OUT / f"q7-cleanup-v2-{mode}-receipt.json").read_text())


m = load("real-dry-run")
checks["fd-safe rmtree on this host"] = m.shutil.rmtree.avoids_symlink_attacks
with patch.object(m.shutil, "rmtree", blocked), patch.object(sys, "argv", [str(SOURCE)]):
    checks["real dry run succeeds without removal"] = m.main() == 0 and receipt(m, "dry_run")["n_targets"] == 136

m = load("post-preflight-inode-refusal")
orig = m.check_targets


def mutate_pin_after_preflight(inv):
    probs = orig(inv)
    inv[0]["inode"] += 1
    return probs


with patch.object(m, "check_targets", mutate_pin_after_preflight), patch.object(m.shutil, "rmtree", blocked), patch.object(sys, "argv", [str(SOURCE), "--execute", "Q7"]):
    code = m.main()
    rec = receipt(m)
    checks["post-preflight inode mismatch refuses before removal"] = code == 1 and rec["removed"] == [] and "per-root guard" in rec["outcome"]

m = load("post-preflight-live-cwd-refusal")
orig_logs = m.check_retained_logs
first_root = json.loads((m.CODEX / "q7-inventory.json").read_text())[0]["path"]
children = []


def start_cwd_user_after_preflight():
    probs = orig_logs()
    children.append(subprocess.Popen(["sleep", "20"], cwd=first_root))
    return probs


try:
    with patch.object(m, "check_retained_logs", start_cwd_user_after_preflight), patch.object(m.shutil, "rmtree", blocked), patch.object(sys, "argv", [str(SOURCE), "--execute", "Q7"]):
        code = m.main()
        rec = receipt(m)
        checks["post-preflight actual cwd user refuses before removal"] = code == 1 and rec["removed"] == [] and "in use" in rec["outcome"]
finally:
    for child in children:
        child.terminate()
        child.wait(timeout=5)

m = load("simulated-partial-failure")
events, calls = [], []
real_fsync, real_replace = os.fsync, os.replace


def trace_fsync(fd):
    events.append("dir-fsync" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file-fsync")
    return real_fsync(fd)


def trace_replace(src, dst):
    json.loads(Path(src).read_text())
    events.append("replace")
    return real_replace(src, dst)


def simulated_removal(path):
    current = receipt(m)
    assert current["removing"] == path
    assert current["outcome"] == "in progress"
    calls.append(path)
    simulated_calls.append(path)
    if len(calls) == 2:
        raise OSError("independent simulated removal failure; no file was deleted")


with patch.object(m.shutil, "rmtree", simulated_removal), patch.object(m.os, "fsync", trace_fsync), patch.object(m.os, "replace", trace_replace), patch.object(sys, "argv", [str(SOURCE), "--execute", "Q7"]):
    code = m.main()
    rec = receipt(m)
    checks["current path persisted before each simulated removal"] = len(calls) == 2
    checks["partial failure stops with prior completion and current path"] = code == 1 and rec["removed"] == calls[:1] and rec["removing"] == calls[1] and rec["outcome"].startswith("FAILED")
    checks["each receipt uses file fsync replace directory fsync"] = events == ["file-fsync", "replace", "dir-fsync"] * 5

m = load("second-root-guard-refusal")
orig_root, orig_logs = m.check_root, m.check_retained_logs
phase, calls = {"execute": False}, []
original_roots = {e["path"] for e in json.loads((m.CODEX / "q7-inventory.json").read_text())}
guard_roots = []


def mark_execute():
    probs = orig_logs()
    phase["execute"] = True
    return probs


def changed_second_root(e, roots):
    if phase["execute"]:
        guard_roots.append(set(roots))
        if len(guard_roots) == 2:
            e = copy.deepcopy(e)
            e["regular_file_bytes"] += 1
    return orig_root(e, roots)


def virtual_remove(path):
    assert receipt(m)["removing"] == path
    calls.append(path)
    simulated_calls.append(path)


with patch.object(m, "check_retained_logs", mark_execute), patch.object(m, "check_root", changed_second_root), patch.object(m.shutil, "rmtree", virtual_remove), patch.object(sys, "argv", [str(SOURCE), "--execute", "Q7"]):
    code = m.main()
    rec = receipt(m)
    checks["later content mismatch stops before second simulated removal"] = code == 1 and len(calls) == 1 and rec["removed"] == calls and rec["removing"] is None and "contents changed" in rec["outcome"]
    checks["execution guards retain all original candidate roots"] = len(guard_roots) == 2 and all(roots == original_roots for roots in guard_roots)

m = load("atomic-replace-failure")
replace_calls = []


def fail_second_replace(src, dst):
    replace_calls.append(str(dst))
    if len(replace_calls) == 2:
        raise OSError("independent simulated atomic replacement failure")
    return real_replace(src, dst)


with patch.object(m.os, "replace", fail_second_replace), patch.object(m.shutil, "rmtree", blocked), patch.object(sys, "argv", [str(SOURCE), "--execute", "Q7"]):
    try:
        m.main()
        checks["receipt failure stops before removal with previous valid receipt"] = False
    except OSError as ex:
        rec = receipt(m)
        checks["receipt failure stops before removal with previous valid receipt"] = "atomic replacement failure" in str(ex) and rec["removed"] == [] and rec["outcome"] == "in progress"

result = {"script_sha256": digest, "checks": checks, "all_pass": all(checks.values()), "simulated_rmtree_calls": simulated_calls, "actual_rmtree_calls": 0, "candidate_mutations": 0, "note": "execute-mode receipts in this audit are simulations; no Q7 removal occurred"}
(AUDIT / "independent-results.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
assert result["all_pass"], result
