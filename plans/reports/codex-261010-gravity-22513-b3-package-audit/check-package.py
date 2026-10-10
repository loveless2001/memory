"""CPU-only package suite plus independent fail-closed fault probes in the private tree."""
import importlib.util
import json
import os
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
faults = {}


class BrokenVolume:
    def __init__(self, exc):
        self.exc = exc

    def listdir(self, *args, **kwargs):
        raise self.exc


for exc in (TimeoutError("listdir timed out"), PermissionError("listdir denied")):
    outcome = R.precheck(starts=SimpleNamespace(keys=lambda: []), vol=BrokenVolume(exc))
    faults[type(exc).__name__ + "_precheck"] = {"returned": outcome,
                                                  "treated_as_empty": outcome is None}
    assert outcome is None, "the source no longer has the reported fail-open behavior"

with tempfile.TemporaryDirectory(prefix="b3-collect-fault-") as tmp:
    out = Path(tmp)
    dest = out / "volume" / R.RUN_REL / "B3"
    dest.mkdir(parents=True)
    (dest / "b3_result.json").write_text(json.dumps({"status": "valid", "memory_used": False,
                                                    "band_at_end": "partial"}))
    (out / "call_result.json").write_text(json.dumps({"returncode": 0}))
    faults["collect_listing_error_with_prior_local_result"] = R.collect(out, vol=BrokenVolume(TimeoutError("list failed")))
    assert faults["collect_listing_error_with_prior_local_result"]["ok"] is True
    assert faults["collect_listing_error_with_prior_local_result"]["files"] == 0

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
try:
    R.worker(10000, starts=None, vol=SimpleNamespace(), clock=lambda: 0)
except RuntimeError as error:
    faults["worker_entry_lookup_failure"] = {"escaped": str(error), "guards_created": len(created),
                                             "guards_canceled": len(canceled)}
else:
    raise AssertionError("lookup failure unexpectedly contained")
assert len(created) == 1 and not canceled


class TerminalWriteFailure(T._Dict):
    def put(self, key, value, skip_if_exists=False):
        if key == R.TERMINAL_KEY:
            raise RuntimeError("simulated terminal Dict write failure")
        return super().put(key, value, skip_if_exists=skip_if_exists)


R.safe_commit = lambda: 0
with tempfile.TemporaryDirectory(prefix="b3-terminal-fault-") as tmp:
    R.RUN_DIR = str(Path(tmp) / "run")
    before = len(canceled)
    try:
        R.worker(10000, starts=TerminalWriteFailure({R.DEADLINE_KEY: 10000}),
                 vol=SimpleNamespace(reload=lambda: None), versions=lambda: {"ok": True, "got": {}},
                 popen=lambda *a, **k: SimpleNamespace(pid=1), supervise=lambda *a, **k: (0, 0),
                 clock=lambda: 0)
    except RuntimeError as error:
        faults["worker_terminal_write_failure"] = {"escaped": str(error),
                                                   "guard_canceled": len(canceled) == before + 1}
    else:
        raise AssertionError("terminal-write failure unexpectedly contained")

cg_path = next(line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines()
               if line.startswith("0::"))
cg = Path("/sys/fs/cgroup") / cg_path.lstrip("/")
result = {"registered_suite_exit_code": int(rc), "faults": faults, "cgroup": cg_path,
          "memory_max": (cg / "memory.max").read_text().strip(),
          "memory_swap_max": (cg / "memory.swap.max").read_text().strip(),
          "guards": "CPU-only, pretrained model loaders, Modal lookup methods and socket connections blocked"}
(REPORT / "independent-results.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
