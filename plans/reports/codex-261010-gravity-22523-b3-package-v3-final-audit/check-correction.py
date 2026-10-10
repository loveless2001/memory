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
                  "tests/test_sgm_p2p5_b3_shift2_fill_long_run.py::test_ledger_matches_proposal_v03"])
assert rc == 0
T = sys.modules["test_sgm_p2p5_b3_shift2_fill_long_run"]
R = T.R
assert R.ledger()["window_s"] == 23880
assert abs(R.ledger()["reservation_usd"] - 16.3035352) < 1e-9
assert abs(R.ledger()["headroom_usd"] - 0.6964648) < 1e-9

with tempfile.TemporaryDirectory(prefix="b3-watch-final-") as tmp:
    out = Path(tmp)
    (out / "run.json").write_text(json.dumps({"call_id": "fc-fake", "deadline": 23400}))
    clock = [23400 + R.END_MARGIN_S - 1]
    timing = {}

    def cleanup(out):
        timing["cleanup_started_at"] = clock[0]
        clock[0] += R.CLEANUP_S
        return {"status": "shutdown_unresolved"}

    R.watch(out, state=lambda cid: ("unknown", "fake"), cleanup=cleanup, clock=lambda: clock[0],
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    timing["cleanup_budget_end"] = clock[0]
    timing["ledger_window_seconds"] = R.ledger()["window_s"]
    assert timing["cleanup_budget_end"] <= timing["ledger_window_seconds"]

harness = TREE / "plans/261010-0256-m4-sgm-p2p5-b3-feature-shift2-fill-long-run/implementation/b3-mutation-checks.py"
nodes = [n for n in ast.parse(harness.read_text()).body if
         (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {"RUN", "TRAIN", "MUTANTS"} for t in n.targets))
         or (isinstance(n, ast.FunctionDef) and n.name == "classify")]
ns = {"re": re}
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), "<v5 pins only>", "exec"), ns)
evidence = json.loads(harness.with_name("b3-mutation-checks-v5.json").read_text())
assert len(evidence) == 20 and evidence[0]["baseline"].startswith("42 passed")
for spec, row in zip(ns["MUTANTS"], evidence[1:]):
    name, rel, old, new, expected = spec
    assert row["mutant"] == name and row["status"] == "CAUGHT" and row["rc"] == 1
    assert set(row["expected"]) == expected and set(row["failed"]) <= expected
    assert (TREE / rel).read_text().count(old) == 1

cg_path = next(line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines()
               if line.startswith("0::"))
cg = Path("/sys/fs/cgroup") / cg_path.lstrip("/")
result = {"affected_test_exit_code": int(rc), "late_poll_probe": timing,
          "v5_exact_id_records_consistent": 19, "ledger": R.ledger(), "cgroup": cg_path,
          "memory_max": (cg / "memory.max").read_text().strip(),
          "memory_swap_max": (cg / "memory.swap.max").read_text().strip()}
(REPORT / "independent-results.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
