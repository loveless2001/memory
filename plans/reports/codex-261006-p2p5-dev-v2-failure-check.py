"""CPU-only fixtures of the actual v2 local entrypoint; never invoke Modal remotely."""
import hashlib
import importlib.util
import io
import json
import signal
import sys
import tarfile
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "plans/reports/codex-261006-p2p5-dev-v2-failure-check.json"


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    runner = load("dev_runner_v2", "modal-runners/modal-m4-sgm-p2p5-dev-gpu-test-runner.py")
    spec = runner.run_remote.spec
    report = {"runner_sha256": hashlib.sha256(Path(runner.__file__).read_bytes()).hexdigest(),
              "remote_calls": False, "paid_work": False,
              "function_resource_fields": {"cpu": spec.cpu, "memory_mib": spec.memory}, "fixtures": []}
    assert spec.cpu == (4.0, 4.0) and spec.memory == (32768, 32768)
    runner.app = SimpleNamespace(app_id="fixture-no-remote-app")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz"):
        pass
    with tempfile.TemporaryDirectory(prefix="codex-dev-v2-") as tmp:
        for name in ("success", "rc7", "child_timeout", "remote_exception", "bad_archive", "sigterm"):
            def remote(*_args):
                if name == "remote_exception":
                    raise RuntimeError("fixture remote error")
                if name == "sigterm":
                    signal.raise_signal(signal.SIGTERM)
                return {"returncode": 7 if name == "rc7" else "timeout" if name == "child_timeout" else 0,
                        "wall_s": 1.0, "tar": b"invalid" if name == "bad_archive" else buffer.getvalue()}
            runner.run_remote = SimpleNamespace(remote=remote)
            dest = Path(tmp) / name
            old_signal = signal.getsignal(signal.SIGTERM)
            error = None
            try:
                runner.main(script="fixture.py", out=str(dest))
            except BaseException as exc:
                error = {"type": type(exc).__name__, "text": str(exc)}
            finally:
                signal.signal(signal.SIGTERM, old_signal)
            meta = json.loads((dest / "run.json").read_text())
            assert (error is None) == (name == "success")
            assert meta["outcome"] == ("ok" if name == "success" else
                                       "child failed" if name in ("rc7", "child_timeout") else "remote call failed")
            assert "client_wall_s" in meta
            report["fixtures"].append({"case": name, "error": error, "manifest": meta})
        hotspot = load("dev_hotspot_v2", "scripts/sgm-p2p5-sgm-path-hotspot-profile.py")
        dest = Path(tmp) / "hotspot_failure"
        with patch.object(sys, "argv", [hotspot.__file__, "--out", str(dest)]), \
             patch.object(hotspot.torch.cuda, "is_available", return_value=True), \
             patch.object(hotspot.torch.cuda, "get_device_name", return_value="fixture"), \
             patch.object(hotspot, "Watchdog", return_value=SimpleNamespace(cancel=lambda: None)), \
             patch.object(hotspot, "label", return_value=None), \
             patch.object(hotspot, "timed_backward", return_value=None), \
             patch.object(hotspot, "run_config", side_effect=RuntimeError("fixture first-config error")):
            error = None
            try:
                hotspot.main()
            except SystemExit as exc:
                error = exc.code
        meta = json.loads((dest / "hotspot.json").read_text())
        assert error == 1 and meta["status"].startswith("stopped:") and meta["configs"] == []
        report["hotspot_failure"] = {"exit_code": error, "status": meta["status"]}
        report["hotspot_sha256"] = hashlib.sha256(Path(hotspot.__file__).read_bytes()).hexdigest()
    report["limits"] = ["Fixtures do not verify a real remote failure, container stop, build failure, SIGKILL, or host loss.",
                        "Manifest charge_bound_usd=0.9582 is function-only arithmetic; use channel cumulative reserve instead.",
                        "Use timeout --kill-after=15s for a bounded client termination; the 120s teardown allowance is an assumption."]
    report["run2_reservation_check"] = {"run1_booked_usd": 1.55, "proposed_run2_usd": 1.17,
        "hard_tuple_1320s_resource_plus_0p03_build_plus_0p10_margin_usd": 1320 * (0.000542 + 4 * 0.0000131 + 32 * 0.00000222) + 0.13,
        "optional_2x_cpu_ram_same_basis_usd": 1320 * (0.000542 + 2 * (4 * 0.0000131 + 32 * 0.00000222)) + 0.13,
        "round_up_optional_reserve_usd": 1.18, "total_booked_with_1p18_usd": 2.73,
        "new_build_cost_limit": "0.03 assumes existing cached build layer; no unapproved rebuild/retry."}
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps({"runner_sha256": report["runner_sha256"], "fixtures_passed": len(report["fixtures"]),
                      "hotspot_failure_exit": error, "resource_fields": report["function_resource_fields"]}))


if __name__ == "__main__":
    main()
