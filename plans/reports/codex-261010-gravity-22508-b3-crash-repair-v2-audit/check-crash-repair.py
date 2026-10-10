"""Independent stdlib-only checks of the two repaired functions; no repository imports."""
import ast
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs"
runner_text = (INPUTS / "modal-m4-sgm-p2p5-b3-shift2-fill-long-run-runner.py").read_text()
harness_text = (INPUTS / "b3-mutation-checks.py").read_text()


def extracted_function(source, name, namespace):
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, "<extracted " + name + ">", "exec"), namespace)
    return namespace[name]


def cleanup(source):
    return extracted_function(source, "cleanup_verify", dict(Path=Path, CLEANUP_S=300,
        subprocess=subprocess, time=time, sys=sys, json=json))


class FakeCLI:
    def __init__(self):
        self.stopped = False
        self.calls = []

    def __call__(self, argv, **kwargs):
        args = argv[3:]
        self.calls.append(args)
        assert args[:2] == ["app", "stop"]
        self.stopped = "--yes" in args
        return SimpleNamespace(returncode=0 if self.stopped else 1,
                               stderr="" if self.stopped else "Aborted", stdout="")


def run_cleanup(source, verify_after_stop):
    f = cleanup(source)
    cli = FakeCLI()
    calls = []

    def verify(app_id, modal_json):
        calls.append(app_id)
        assert len(calls) <= 50, "independent guard: unbounded cleanup loop"
        return {"app_id": app_id, "verified": bool(verify_after_stop and cli.stopped)}

    with tempfile.TemporaryDirectory(prefix="codex-b3-cleanup-") as tmp:
        p = Path(tmp)
        (p / "run.json").write_text(json.dumps({"app_id": "ap-independent"}))
        rec = f(p, budget_s=300, wait_s=20, run=cli, sleep=lambda s: None,
                clock=lambda: 0, cp=SimpleNamespace(verify_stopped=verify))
    return rec, cli, calls


rec, cli, calls = run_cleanup(runner_text, True)
assert rec["status"] == "stopped_verified" and len(calls) == 1
assert cli.calls == [["app", "stop", "--yes", "ap-independent"]]
rec, _, calls = run_cleanup(runner_text, False)
assert rec["status"] == "shutdown_unresolved" and len(calls) == len(rec["checks"]) == 17

m4_old = 'r = cli(["app", "stop", "--yes", app_id], False)'
assert runner_text.count(m4_old) == 1
m4 = runner_text.replace(m4_old, 'r = cli(["app", "stop", app_id], False)')
rec, cli, calls = run_cleanup(m4, True)
assert rec["status"] == "shutdown_unresolved" and len(calls) == 17 and not cli.stopped

m11_old = ' or len(rec["checks"]) >= max_checks:'
assert runner_text.count(m11_old) == 1
m11 = runner_text.replace(m11_old, ':')
try:
    run_cleanup(m11, False)
except AssertionError as error:
    assert "unbounded cleanup loop" in str(error)
else:
    raise AssertionError("M11 cap removal survived the independent guard")

classify = extracted_function(harness_text, "classify", {"re": re})
cases = [
    (0, "", "SURVIVED"),
    (1, "FAILED tests/t.py::test_expected[param] - AssertionError\n", "CAUGHT"),
    (1, "FAILED tests/t.py::test_other - AssertionError\n", "WRONG_TEST"),
    (1, "systemd launch failed\n", "INFRA_ERROR"),
    (2, "ERROR collecting tests/t.py\n", "INFRA_ERROR"),
    (137, "", "KILLED"),
    (-9, "", "KILLED"),
]
for rc, stdout, expected in cases:
    actual, failed = classify(SimpleNamespace(returncode=rc, stdout=stdout), {"test_expected"})
    assert actual == expected, (rc, expected, actual)

results = json.loads((INPUTS / "b3-mutation-checks-v2.json").read_text())
assert results[0]["baseline"].startswith("32 passed")
assert len(results[1:]) == 11
for row in results[1:]:
    assert row["status"] == "CAUGHT" and row["rc"] == 1
    assert len(row["failed"]) == 1
    assert {f.split("[")[0] for f in row["failed"]} <= set(row["expected"])
assert results[8]["failed"] == ["test_worker_refusals_and_exceptions_are_terminal[deadline_mismatch]"]

cgroup = next(line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines()
              if line.startswith("0::"))
cg = Path("/sys/fs/cgroup") / cgroup.lstrip("/")
mem_max = (cg / "memory.max").read_text().strip()
swap_max = (cg / "memory.swap.max").read_text().strip()
assert mem_max == "268435456" and swap_max == "0", (mem_max, swap_max)
print(json.dumps({"status": "PASS", "cleanup_checks": 4, "classification_cases": len(cases),
                  "retained_mutants_consistent": 11, "cgroup": cgroup,
                  "memory_max_bytes": int(mem_max), "memory_swap_max_bytes": int(swap_max)}))
