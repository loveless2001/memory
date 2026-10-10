"""Independent local build/import regression probes. No hydration or paid work."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from modal._utils.async_utils import synchronizer

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py"
LOGIC = ROOT / "modal-runners/modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py"
EXPECTED_SHA = "6406e6415def0e28ccccbd67c0a424a5c052329c914c49828661bd89cf594e28"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def mounted_paths(image):
    seen, paths = set(), set()

    def visit(obj):
        obj = synchronizer._translate_in(obj)
        if id(obj) in seen:
            return
        seen.add(id(obj))
        for entry in (getattr(obj, "_entries", None) or []):
            remote = getattr(entry, "remote_path", None)
            if remote:
                paths.add(str(remote))
        if callable(getattr(obj, "_deps", None)):
            for dep in obj._deps():
                visit(dep)

    visit(image)
    return sorted(paths)


class Store(dict):
    def put(self, key, value, skip_if_exists=False):
        if skip_if_exists and key in self:
            return False
        self[key] = value
        return True


def main():
    os.chdir(ROOT)
    assert hashlib.sha256(RUNNER.read_bytes()).hexdigest() == EXPECTED_SHA
    with tempfile.TemporaryDirectory(prefix="codex-p2p5-build-") as tmp:
        isolated = Path(tmp) / RUNNER.name
        isolated.write_bytes(subprocess.check_output(["git", "show", f"5b89067:modal-runners/{RUNNER.name}"]))
        try:
            load(isolated, "codex_old_build")
        except FileNotFoundError as error:
            assert Path(error.filename) == isolated.with_name(LOGIC.name)
        else:
            raise AssertionError("old eager import did not reproduce the failure")
        shutil.copyfile(RUNNER, isolated)
        module = load(isolated, "codex_new_build")
        assert module._LOGIC is None
        calls = []
        hub = ModuleType("huggingface_hub")
        hub.snapshot_download = lambda *args, **kwargs: calls.append((args, kwargs))
        with patch("subprocess.run") as pip, patch.dict(sys.modules, {"huggingface_hub": hub}):
            module._build_environment()
        assert pip.call_count == 2 and len(calls) == 1
        assert "torch==2.7.1" in pip.call_args_list[0].args[0]
        assert "transformers==4.55.2" in pip.call_args_list[1].args[0]
        assert calls[0][0] == ("Qwen/Qwen3-0.6B-Base",)
        assert calls[0][1]["revision"] == module.MODEL_REVISION
        assert calls[0][1]["allow_patterns"] == ["config.json", "generation_config.json", "model.safetensors"]
        assert module._LOGIC is None
        try:
            module.reap_decision(Store(), 0)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("runtime missing logic must fail")
        assert module._LOGIC is None
        shutil.copyfile(LOGIC, isolated.with_name(LOGIC.name))
        events = []
        store = Store(app_id="ap-fixture", deadline_epoch=100, call_id="fc-fixture")
        with contextlib.redirect_stdout(io.StringIO()) as marker:
            result = module.reap_and_stop(store, 101, module.APP_NAME,
                                          lambda *args: events.append(("stop", args)),
                                          lambda *args: events.append(("cancel", args)))
        assert result == {"stop": True, "reason": "deadline passed"}
        assert events == [("stop", (module.APP_NAME, "ap-fixture")), ("cancel", ("fc-fixture",))]
        assert "bound=ap-fixture reason=deadline passed" in marker.getvalue()
        assert module.logic() is module._LOGIC and module.ENVIRONMENT == module.logic().ENVIRONMENT
        with patch.object(module.logic(), "stop_bound_app") as stop:
            module.stop_bound_app(module.APP_NAME, "ap-fixture")
            stop.assert_called_once_with(module.APP_NAME, "ap-fixture", "main")

    production = load(RUNNER, "codex_current_profile")
    reaper_spec = synchronizer._translate_in(production.reaper)._spec
    worker_spec = synchronizer._translate_in(production.run_profile)._spec
    reaper_files, worker_files = mounted_paths(reaper_spec.image), mounted_paths(worker_spec.image)
    assert f"/root/{LOGIC.name}" in reaper_files and f"/root/{LOGIC.name}" in worker_files
    assert reaper_spec.gpus is None and not reaper_spec.volumes
    assert reaper_spec.image is synchronizer._translate_in(production.reaper_image)
    identity = production.expected_identity()
    assert identity == {
        "runner": EXPECTED_SHA,
        "reaper_logic": "32bb3a3a38bf375e4c9107e4b3d7dc4c6392076cb5ba55f7c599fab644329e6c",
        "profile_script": "b5b0746a40afbd7c9feb2bcf7aa6967189903673829cf2a8d4a2afc25237a08c",
        "memsub": "048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6",
    }
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "identity": identity,
        "old_eager_import_failure_reproduced": True,
        "isolated_new_import_and_actual_build_function_pass": True,
        "pip_and_download_substituted": True,
        "runtime_missing_logic_fails": True,
        "mounted_logic_lazy_load_cache_and_stop_order_pass": True,
        "production_reaper_files": reaper_files,
        "production_worker_files": worker_files,
        "profile_ledger": production.charge_bound(),
        "remote_calls": False,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
