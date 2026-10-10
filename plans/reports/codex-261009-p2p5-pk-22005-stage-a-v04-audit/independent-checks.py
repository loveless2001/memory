"""Offline review only: hash bindings, unchanged core, and actual shell launch/cleanup flow.

The wrapper is copied into a temporary repository with fake git/timeout/python executables.
No Modal API, model load, CUDA work or paid launch occurs.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
P = Path("plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen")
RUNNER = Path("modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py")
EXPECTED_HEAD = "fe43fc9f07f9f935be7e28950852081b392c6322"


def executable(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(0o755)


def wrapper_case(client_rc, cleanup_rc):
    with tempfile.TemporaryDirectory(prefix="codex-stage-a-wrapper-") as tmp:
        root = Path(tmp)
        (root / P).mkdir(parents=True)
        wrapper = root / P / "launch-stage-a-once.sh"
        shutil.copyfile(ROOT / P / wrapper.name, wrapper)
        executable(root / "bin/git", "#!/bin/sh\ncase \"$1\" in\nstatus) exit 0;;\nrev-parse) echo " + EXPECTED_HEAD + ";;\n*) exit 91;;\nesac\n")
        executable(root / "bin/timeout", "#!/bin/sh\nprintf '%s\\n' \"$@\" > client-argv.txt\nexit " + str(client_rc) + "\n")
        executable(root / ".venv/bin/python", "#!/bin/sh\nprintf '%s\\n' \"$@\" > cleanup-argv.txt\nexit " + str(cleanup_rc) + "\n")
        env = {**os.environ, "PATH": str(root / "bin") + os.pathsep + os.environ["PATH"]}
        result = subprocess.run(["bash", str(wrapper)], env=env, capture_output=True, text=True, timeout=10)
        client_exit = (root / P / "stage-a-run-v1.exit.txt").read_text().split()[0]
        cleanup_exit = (root / P / "stage-a-run-v1.cleanup-exit.txt").read_text().split()[0]
        assert client_exit == str(client_rc) and cleanup_exit == str(cleanup_rc)
        assert (root / "cleanup-argv.txt").read_text().splitlines() == [str(RUNNER), "cleanup-verify", str(P / "stage-a-run-v1")]
        args = (root / "client-argv.txt").read_text().splitlines()
        assert args == ["--signal=TERM", "--kill-after=30s", "4710", ".venv/bin/python", "-m", "modal", "run", str(RUNNER), "--out", str(P / "stage-a-run-v1")]
        launch = (root / P / "stage-a-run-v1.launch.txt").read_text()
        assert EXPECTED_HEAD in launch and "pgid" in launch and "sid" in launch
        before = (root / "client-argv.txt").stat().st_mtime_ns
        second = subprocess.run(["bash", str(wrapper)], env=env, capture_output=True, text=True, timeout=10)
        assert second.returncode == 2 and (root / "client-argv.txt").stat().st_mtime_ns == before
        return {"client_rc": client_rc, "cleanup_rc": cleanup_rc, "both_exit_markers": True,
                "cleanup_runs_after_client_exit": True, "repeat_refused": True, "shell_rc": result.returncode}


checks = {}
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == EXPECTED_HEAD
checks["head"] = head
dirty = subprocess.check_output(["git", "status", "--porcelain", "--", "memsub", "scripts", "modal-runners", str(P / "inputs")], cwd=ROOT, text=True)
assert not dirty, dirty
checks["launch_guard_current_status"] = "clean"
checks["hashes"] = {}
for row in (ROOT / P / "SHA256SUMS-stage-a-package-v0.4.txt").read_text().splitlines():
    sha, rel = row.split(maxsplit=1)
    actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    assert actual == sha, rel
    checks["hashes"][rel] = actual
sys.path.insert(0, str(ROOT))
from memsub.sgm.synthetic_pilot_run import source_tree_sha256
source = source_tree_sha256(ROOT / "memsub")
bound = json.loads((ROOT / P / "inputs/probe-taskhead-learned-n32-s0-run_manifest.json").read_text())["memsub_source_sha256"]
assert source == bound, (source, bound)
checks["memsub_source_sha256"] = source
checks["wrapper_cases"] = [wrapper_case(7, 0), wrapper_case(0, 1)]
with tempfile.TemporaryDirectory(prefix="codex-stage-a-no-id-") as tmp:
    out = Path(tmp) / "missing-entrypoint"
    result = subprocess.run([sys.executable, str(ROOT / RUNNER), "cleanup-verify", str(out)], cwd=ROOT,
                            capture_output=True, text=True, timeout=20)
    rec = json.loads((out / "cleanup.json").read_text())
    assert result.returncode == 1 and rec["status"] == "unresolved: no app id recorded" and not rec["checks"]
    checks["actual_cleanup_cli_missing_id"] = {"returncode": result.returncode, "record": rec}
checks["paid_calls"] = 0
(HERE / "independent-checks.json").write_text(json.dumps(checks, indent=2) + "\n")
print(json.dumps({"ok": True, "hashes_verified": len(checks["hashes"]), "wrapper_cases": len(checks["wrapper_cases"]), "paid_calls": 0}))
