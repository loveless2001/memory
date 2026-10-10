"""CPU-only independent checks of the frozen proof/production runner.

All Modal, deployment, lifecycle and stop calls are replaced. The SDK's local
FunctionSpec is inspected without hydration. No remote operation occurs.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import modal
import modal.experimental as experimental
from modal._utils.async_utils import synchronizer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
FILES = {
    "profile": ("modal-m4-sgm-p2p5-l40s-timing-profile.py", "5af72fd1e9a0f4b9a0f38e0b0a376b27d08d3b547a7cf0026b0bd7fb2ed67c42"),
    "logic": ("modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py", "fe4825a80d1b3f77b76338c9fe1d2e2af81ed6f2acaba7f3f8e9d66d571198ed"),
    "proof": ("modal-m4-sgm-p2p5-reaper-self-stop-proof.py", "31e83604c564847e6b335d350d216938a61329196338d94b92899200001416a2"),
}


def load(label):
    filename, expected = FILES[label]
    path = ROOT / "modal-runners" / filename
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    # Register the module as Modal's CLI does: inspect.getmodule then recognizes
    # a file-defined function. The supplied tests omit this registration.
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)
    return mod


class Store(dict):
    failing_key = None

    def put(self, key, value, skip_if_exists=False):
        if key == self.failing_key:
            raise RuntimeError("fixture: failed binding RPC")
        if skip_if_exists and key in self:
            return False
        self[key] = value
        return True


def image_files(image, seen=None):
    """Read only local deferred mounts and image dependency closures."""
    seen = seen if seen is not None else set()
    if id(image) in seen:
        return []
    seen.add(id(image))
    out = []
    for mount in getattr(image, "_deferred_mounts", ()):
        for entry in getattr(mount, "_entries", ()):
            if hasattr(entry, "remote_path"):
                out.append(str(entry.remote_path))
    deps = image._deps() if image._deps else []
    for dep in deps:
        for entry in getattr(dep, "_entries", ()):
            if hasattr(entry, "remote_path"):
                out.append(str(entry.remote_path))
        if hasattr(dep, "_deferred_mounts"):
            out.extend(image_files(dep, seen))
    return out


def proof_case(proof, label):
    store, local_stops, clock = Store(), [], [1000.0]
    if label == "binding_failure":
        store.failing_key = "deadline_epoch"

    def fake_subprocess(cmd, **kwargs):
        if cmd[:2] == ["git", "status"]:
            return SimpleNamespace(stdout="", stderr="", returncode=0)
        if cmd[:2] == ["git", "rev-parse"]:
            return SimpleNamespace(stdout="fixture-head\n", stderr="", returncode=0)
        if "deploy" in cmd:
            if label == "deploy_timeout":
                raise subprocess.TimeoutExpired(cmd, proof.DEPLOY_TIMEOUT_S, output="fixture deployment accepted before CLI timeout")
            return SimpleNamespace(stdout="fixture deployed ap-proof-fixture\n", stderr="", returncode=0)
        if "stop" in cmd:
            local_stops.append(cmd[-1])
            return SimpleNamespace(stdout="", stderr="", returncode=0)
        if "app" in cmd and "list" in cmd:
            return SimpleNamespace(stdout=json.dumps([{"app_id": "ap-proof-fixture", "state": "stopped", "tasks": 0}]),
                                   stderr="", returncode=0)
        if "container" in cmd and "list" in cmd:
            return SimpleNamespace(stdout="[]", stderr="", returncode=0)
        raise AssertionError(cmd)

    def lifecycle(app_id):
        if label == "observer_failure":
            raise RuntimeError("fixture: observer RPC failed")
        # An explicitly unrelated stop BEFORE the reaper deadline, with no
        # server-side reaper evidence, must not prove reaper credentials.
        return SimpleNamespace(stopped_at=datetime.fromtimestamp(1010, timezone.utc),
                               stopped_by="fixture unrelated actor")

    with tempfile.TemporaryDirectory(prefix=f"codex-p2p5-8f4a27f-{label}-") as tmp:
        root = Path(tmp) / "proof"
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(proof, "LOCAL_OUT", str(root)))
            stack.enter_context(patch.object(proof.modal.Dict, "from_name", lambda *a, **k: store))
            stack.enter_context(patch.object(proof.modal.App, "lookup", lambda *a, **k: SimpleNamespace(app_id="ap-proof-fixture")))
            stack.enter_context(patch.object(proof.subprocess, "run", fake_subprocess))
            stack.enter_context(patch.object(experimental, "get_app_lifecycle", lifecycle))
            stack.enter_context(patch.object(proof.time, "time", lambda: clock[0]))
            stack.enter_context(patch.object(proof.time, "sleep", lambda n: clock.__setitem__(0, clock[0] + n)))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            try:
                result, error = proof.prove(), None
            except (Exception, SystemExit) as e:
                result, error = None, f"{type(e).__name__}: {e}"
        prov = json.loads((root / "proof_provenance.json").read_text())
        facts = {"error": error, "local_stops": local_stops,
                 "report_retained": (root / "proof_report.json").exists(),
                 "deploy_log_retained": (root / "deploy.log").exists(),
                 "provenance_has_app_id": "app_id" in prov,
                 "guard_has_app_id": "app_id" in store, "guard_has_deadline": "deadline_epoch" in store}
        if label == "premature_unrelated_stop":
            assert result and result["result"].startswith("PASS")
            assert result["reaper_fired"] is None and not local_stops
            facts.update(result=result["result"], reaper_fired=result["reaper_fired"],
                         deadline_epoch=result["deadline_epoch"], observed=result["observed"])
        else:
            assert error and not local_stops and not facts["report_retained"]
        return facts


def main():
    profile, logic, proof = load("profile"), load("logic"), load("proof")
    reaper = synchronizer._translate_in(profile.reaper)
    proof_reaper = synchronizer._translate_in(proof.reaper)
    production_files = image_files(reaper._spec.image)
    proof_files = image_files(proof_reaper._spec.image)
    assert f"/root/{profile.LOGIC_FILE}" not in production_files
    assert f"/root/{proof.LOGIC_FILE}" in proof_files
    order = []
    d = Store(deadline_epoch=10, app_id="ap-fixture", call_id="fc-fixture")
    logic.reap_and_stop(d, 11, "fixture-app", lambda *a: order.append("stop"),
                       lambda c: order.append("cancel"))
    assert order == ["stop", "cancel"]
    assert profile.child_timeout_s(1000, 219) == 691

    old_path = ROOT / "plans/reports/codex-261006-p2p5-4f9a25c-runner-checks.py"
    spec = importlib.util.spec_from_file_location("previous_audit_utilities", old_path)
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    source = profile.expected_identity()["memsub"]
    good = previous.profile_fixture(profile, source)
    assert profile.profile_usable(good, 0, source)[0]
    corrected = {}
    mutations = {
        "wrong_torch": lambda p: p["environment"].__setitem__("torch", "2.7.1+cpu"),
        "wrong_cuda": lambda p: p["environment"].__setitem__("cuda", "incorrect-CUDA-fixture"),
        "wrong_gpu": lambda p: p["environment"].__setitem__("gpu", "NVIDIA A10"),
        "missing_contract": lambda p: p.pop("contract"),
        "wrong_contract": lambda p: p.__setitem__("contract", "bf16 detached-source fixture"),
        "wrong_filler": lambda p: p["configs"][1].__setitem__("train_filler_len", 0),
    }
    for label, mutate in mutations.items():
        bad = copy.deepcopy(good)
        mutate(bad)
        ok, reason = profile.profile_usable(bad, 0, source)
        assert not ok
        corrected[label] = reason

    cases = {label: proof_case(proof, label) for label in
             ("deploy_timeout", "binding_failure", "observer_failure", "premature_unrelated_stop")}
    for label, (filename, expected) in FILES.items():
        assert hashlib.sha256((ROOT / "modal-runners" / filename).read_bytes()).hexdigest() == expected
    print(json.dumps({"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                     "reviewed_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                     "hashes": {label: sha for label, (_file, sha) in FILES.items()},
                     "production_reaper_image_local_files": production_files,
                     "proof_reaper_image_local_files": proof_files,
                     "profile_reaper_entrypoint_mounts": [str(m) for m in reaper._spec.mounts],
                     "stop_before_optional_cancel": True, "recomputed_child_timeout_s": 691,
                     "r3_corrected": corrected, "proof_control_flow_cases": cases,
                     "profile_reservation": profile.charge_bound(), "proof_reservation": proof.charge_bound(),
                     "combined_reservation_usd": profile.charge_bound()["reserved_total_usd"] + proof.charge_bound()["reserved_usd"],
                     "real_modal_calls": False, "paid_work": False,
                     "clearance": "R3 closed; fix proof cleanup/false PASS and production reaper mount before paid proof"}, indent=2))


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    main()
