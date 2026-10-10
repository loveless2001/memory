"""CPU-only comparison of draft v2 retiming to the accepted v1 machinery."""
import ast
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py"
V2 = ROOT / "modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile-v2-after-speedup.py"
LOGIC = V1.with_name("modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py")
OUT = ROOT / "plans/reports/codex-261006-p2p5-v2-307a159-baseline-check.json"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def functions(path):
    return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(path.read_bytes()).body
            if isinstance(n, ast.FunctionDef)}


class Store(dict):
    def put(self, key, value, skip_if_exists=False):
        if skip_if_exists and key in self:
            return False
        self[key] = value
        return True


def main():
    assert hashlib.sha256(V2.read_bytes()).hexdigest() == "38b5f4b8e14c829aab779f9bee27b045655081b4f9454009b779123faa8a4c1a"
    v1, v2 = load(V1, "accepted_v1"), load(V2, "retiming_v2")
    report = {"remote_calls": False, "paid_work": False, "v2_hash": v2.file_sha(V2),
              "identity": v2.expected_identity(), "ledger": v2.charge_bound()}
    assert report["identity"]["memsub"] == "b87a767baac578d94a6f778560f4fb451fd60679cca48412218adaac74f74085"
    assert v1.file_sha(V1) == "6406e6415def0e28ccccbd67c0a424a5c052329c914c49828661bd89cf594e28"
    assert v2.file_sha(v2.PROFILE_SCRIPT) == "b5b0746a40afbd7c9feb2bcf7aa6967189903673829cf2a8d4a2afc25237a08c"
    assert v2.file_sha(LOGIC) == "32bb3a3a38bf375e4c9107e4b3d7dc4c6392076cb5ba55f7c599fab644329e6c"
    assert v1.charge_bound() == v2.charge_bound()
    assert v1.APP_NAME != v2.APP_NAME and v1.GROUP != v2.GROUP and v1.GUARD_DICT != v2.GUARD_DICT
    report["groups"] = {"v1": v1.GROUP, "v2": v2.GROUP,
        "v2_attempts": f"m4-sgm-{v2.GROUP}-attempts", "v2_guard": v2.GUARD_DICT}
    old, new = functions(V1), functions(V2)
    unchanged = ["_load_logic", "logic", "reap_decision", "reap_and_stop", "stop_bound_app",
                 "_build_environment", "file_sha", "admit", "child_timeout_s", "guard_decision", "reaper",
                 "profile_usable", "charge_bound", "atomic_write", "expected_identity", "_load", "spawn", "collect"]
    assert all(old[n] == new[n] for n in unchanged)
    report["unchanged_function_asts"] = unchanged
    report["function_resource_fields"] = {"gpu_cpu": v2.run_profile.spec.cpu,
        "gpu_memory_mib": v2.run_profile.spec.memory, "reaper_cpu": v2.reaper.spec.cpu,
        "reaper_memory_mib": v2.reaper.spec.memory}
    assert v2.run_profile.spec.cpu == (4.0, 4.0) and v2.run_profile.spec.memory == (32768, 32768)
    assert v2.reaper.spec.cpu == 0.125 and v2.reaper.spec.memory == 256
    helper = load(ROOT / "plans/reports/codex-261006-p2p5-508443c-build-checks.py", "mount_probe")
    report["gpu_mounts"] = helper.mounted_paths(v2.image)
    report["reaper_mounts"] = helper.mounted_paths(v2.reaper_image)
    assert "/root/" + LOGIC.name in report["gpu_mounts"]
    assert "/root/" + LOGIC.name in report["reaper_mounts"]
    assert "/root/repo/" + v2.PROFILE_SCRIPT in report["gpu_mounts"]
    with tempfile.TemporaryDirectory(prefix="codex-v2-build-") as tmp:
        isolated = Path(tmp) / V2.name
        shutil.copyfile(V2, isolated)
        mod = load(isolated, "isolated_v2")
        assert mod._LOGIC is None
        downloads = []
        hub = ModuleType("huggingface_hub")
        hub.snapshot_download = lambda *args, **kwargs: downloads.append((args, kwargs))
        with patch("subprocess.run") as pip, patch.dict(sys.modules, {"huggingface_hub": hub}):
            mod._build_environment()
        assert pip.call_count == 2 and len(downloads) == 1 and mod._LOGIC is None
        assert downloads[0][1]["revision"] == mod.MODEL_REVISION
        try:
            mod.reap_decision(Store(), 0)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("runtime should require shared logic mount")
        shutil.copyfile(LOGIC, isolated.with_name(LOGIC.name))
        events = []
        result = mod.reap_and_stop(Store(deadline_epoch=10.0, app_id="ap-fixture", call_id="fc-fixture"),
            11.0, "fixture-app", lambda name, app_id: events.append(("stop", name, app_id)),
            lambda call: events.append(("cancel", call)))
        assert result["stop"] and events == [("stop", "fixture-app", "ap-fixture"), ("cancel", "fc-fixture")]
    report["isolated_lazy_import_and_mocked_build_passed"] = True
    report["runtime_shared_mount_and_stop_before_cancel_passed"] = True
    report["new_sampler_cleanup_blocker"] = "Actual stop_gpu_sampler propagates kill-race ProcessLookupError; no deploy clearance until repaired."
    OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"baseline_checks_passed": True, "runner_sha256": report["v2_hash"],
                      "reserved_total_usd": report["ledger"]["reserved_total_usd"], "new_sampler_cleanup_blocker": True}))


if __name__ == "__main__":
    main()
