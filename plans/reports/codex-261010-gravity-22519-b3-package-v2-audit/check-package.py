"""Independent guarded CPU suite and verification of the repaired failure paths."""
import ast
import json
import os
import re
import socket
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

REPORT = Path(__file__).resolve().parent
TREE = REPORT / "private-tree"
os.chdir(TREE)
sys.path.insert(0, str(TREE))
os.environ.update(CUDA_VISIBLE_DEVICES="", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                  OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")


def network_guard(*args, **kwargs):
    raise RuntimeError("NETWORK ACCESS ATTEMPTED")


socket.socket.connect = network_guard
socket.socket.connect_ex = network_guard
socket.create_connection = network_guard

import transformers


def model_guard(*args, **kwargs):
    raise RuntimeError("MODEL LOAD ATTEMPTED")


for cls in (transformers.PreTrainedModel, transformers.AutoModelForCausalLM,
            transformers.AutoModel, transformers.AutoConfig):
    cls.from_pretrained = model_guard

import modal


def cloud_guard(*args, **kwargs):
    raise RuntimeError("CLOUD ACCESS ATTEMPTED")


for cls, method in ((modal.Dict, "from_name"), (modal.Function, "from_name"),
                    (modal.FunctionCall, "from_id")):
    setattr(cls, method, cloud_guard)

import pytest

rc = pytest.main(["-q", "-p", "no:cacheprovider", "--basetemp", str(REPORT / "pytest-temp"),
                  "tests/test_sgm_p2p5_b3_shift2_fill_long_run.py"])
assert rc == 0, ("registered suite failed", rc)
T = sys.modules["test_sgm_p2p5_b3_shift2_fill_long_run"]
R = T.R
verified = {}


class BrokenVolume:
    def __init__(self, exc):
        self.exc = exc

    def listdir(self, *args, **kwargs):
        raise self.exc


for exc in (TimeoutError("listdir timed out"), PermissionError("listdir denied"), RuntimeError("service failed")):
    outcome = R.precheck(starts=SimpleNamespace(keys=lambda: []), vol=BrokenVolume(exc))
    assert isinstance(outcome, str) and "listing failed" in outcome and "refusing" in outcome
    verified[type(exc).__name__ + "_precheck"] = outcome
with tempfile.TemporaryDirectory(prefix="b3-collect-fault-") as tmp:
    out = Path(tmp)
    dest = out / "volume" / R.RUN_REL / "B3"
    dest.mkdir(parents=True)
    good = json.dumps({"status": "valid", "memory_used": False, "band_at_end": "partial"}).encode()
    (dest / "b3_result.json").write_bytes(good)
    (out / "call_result.json").write_text(json.dumps({"returncode": 0}))
    for exc in (TimeoutError("list failed"), R.modal.exception.NotFoundError("missing")):
        res = R.collect(out, vol=BrokenVolume(exc))
        assert res["ok"] is False and res["files"] == 0
        verified[type(exc).__name__ + "_stale_collect"] = res
    res = R.collect(out, vol=T._ListVol(files={"B3/b3_result.json": good, "B3/resume.pt": b"unused"}))
    assert res["ok"] is True and res["files"] == 1
    verified["fresh_fetch_collect"] = res

created, canceled = [], []


def fake_guard(*args):
    guard = SimpleNamespace(pid=123)
    created.append(guard)
    return guard


R.deadline_killer = fake_guard
R.cancel_killer = lambda guard: canceled.append(guard)


def lookup_failure(*args, **kwargs):
    raise RuntimeError("simulated Dict lookup failure")


R.modal.Dict.from_name = lookup_failure
res = R.worker(10000, starts=None, vol=SimpleNamespace(), clock=lambda: 0)
assert "refused" in res and res["terminal_write_errors"] == ["no start Dict"]
assert len(created) == len(canceled) == 1
verified["entry_lookup_failure"] = res


class TerminalWriteFailure(T._Dict):
    def put(self, key, value, skip_if_exists=False):
        if key == R.TERMINAL_KEY:
            raise RuntimeError("simulated terminal Dict write failure")
        return super().put(key, value, skip_if_exists=skip_if_exists)


R.safe_commit = lambda: 0
for mode in ("versions", "exception", "completed"):
    def versions():
        if mode == "exception":
            raise RuntimeError("simulated versions failure")
        return {"ok": mode != "versions", "got": {}}
    with tempfile.TemporaryDirectory(prefix="b3-terminal-fault-") as tmp:
        R.RUN_DIR = str(Path(tmp) / "run")
        before = len(canceled)
        res = R.worker(10000, starts=TerminalWriteFailure({R.DEADLINE_KEY: 10000}),
                       vol=SimpleNamespace(reload=lambda: None), versions=versions,
                       popen=lambda *a, **k: SimpleNamespace(pid=1), supervise=lambda *a, **k: (0, 0),
                       clock=lambda: 0)
        assert res["terminal_write_errors"] and len(canceled) == before + 1
        assert (res.get("returncode") == 0) if mode == "completed" else ("refused" in res)
        verified["terminal_write_failure_" + mode] = res

harness = TREE / "plans/261010-0256-m4-sgm-p2p5-b3-feature-shift2-fill-long-run/implementation/b3-mutation-checks.py"
nodes = [n for n in ast.parse(harness.read_text()).body if
         (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {"RUN", "TRAIN", "MUTANTS"} for t in n.targets))
         or (isinstance(n, ast.FunctionDef) and n.name == "classify")]
ns = {"re": re}
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), "<v4 pins only>", "exec"), ns)
evidence = json.loads(harness.with_name("b3-mutation-checks-v4.json").read_text())
assert len(evidence) == 18 and evidence[0]["baseline"].startswith("42 passed")
for spec, row in zip(ns["MUTANTS"], evidence[1:]):
    name, rel, old, new, expected = spec
    assert row["mutant"] == name and row["status"] == "CAUGHT" and row["rc"] == 1
    assert set(row["expected"]) == expected and set(row["failed"]) <= expected
    assert (TREE / rel).read_text().count(old) == 1

# Independent fake-clock accounting: a late poll does not reduce the default cleanup budget.
with tempfile.TemporaryDirectory(prefix="b3-watch-timing-") as tmp:
    out = Path(tmp)
    (out / "run.json").write_text(json.dumps({"call_id": "fc-fake", "deadline": 23400}))
    clock = [23400 + R.END_MARGIN_S - 1]
    timing = {}
    def cleanup(out):
        timing["cleanup_started_at"] = clock[0]
        timing["cleanup_budget_seconds"] = R.CLEANUP_S
        clock[0] += R.CLEANUP_S
        return {"status": "shutdown_unresolved"}
    R.watch(out, state=lambda cid: ("unknown", "fake"), cleanup=cleanup, clock=lambda: clock[0],
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    timing["cleanup_budget_end"] = clock[0]
    timing["ledger_window_seconds"] = R.ledger()["window_s"]
    timing["covered_by_ledger_window"] = clock[0] <= R.ledger()["window_s"]
    assert timing["covered_by_ledger_window"] is False

cg_path = next(line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines()
               if line.startswith("0::"))
cg = Path("/sys/fs/cgroup") / cg_path.lstrip("/")
result = {"registered_suite_exit_code": int(rc), "verified_fixes": verified,
          "v4_exact_id_records_consistent": 17, "watch_budget_probe": timing,
          "cgroup": cg_path, "memory_max": (cg / "memory.max").read_text().strip(),
          "memory_swap_max": (cg / "memory.swap.max").read_text().strip()}
(REPORT / "independent-results.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
