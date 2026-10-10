"""Exercise the full resume worker with CPU fakes; no live Modal calls or real processes."""
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
from unittest.mock import patch

REPORT = Path(__file__).resolve().parent
ROOT = REPORT / "candidate"
os.chdir(ROOT)
spec = importlib.util.spec_from_file_location("audited_resume", ROOT / "modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-resume-runner.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
RAW, SUPERVISE = R.run_b2_remote.get_raw_f(), R.supervise_child


def check(name, *, claims=1, original=400.0, resume=3000.0, marker=400.0, ckpt=b"bound",
          version=True, initial_fail=False, setup_delay=0, initial_delay=0,
          poll_error=False, guard_error=False, now=1000.0, periodic_delay=0):
    events, clock = [], {"t": now}
    data = {"deadline": original, R.RESUME_KEY: resume,
            **{f"start-{k}": {} for k in range(1, claims + 1)}}

    class Starts:
        def get(self, k):
            return data.get(k)

        def put(self, k, v, skip_if_exists=False):
            if skip_if_exists and k in data:
                return False
            data[k] = v
            return True

    class Child:
        pid, rc, waits = 999999991, None, 0

        def poll(self):
            return self.rc

        def wait(self, timeout=None):
            events.append(["wait", timeout])
            if timeout is None:
                self.rc = -9 if self.rc is None else self.rc
                return self.rc
            if poll_error:
                raise RuntimeError("fake poll error")
            self.waits += 1
            if self.waits == 1:
                clock["t"] += timeout
                raise subprocess.TimeoutExpired("fake", timeout)
            self.rc = 0
            return 0

    child = Child()

    class Volume:
        commits = 0

        def reload(self):
            events.append(["reload"])
            clock["t"] += setup_delay

        def commit(self):
            self.commits += 1
            events.append(["commit", self.commits])
            clock["t"] += initial_delay if self.commits == 1 else periodic_delay
            if initial_fail and self.commits == 1:
                raise OSError("fake initial commit error")

    def killer(target, seconds):
        events.append(["arm", target, seconds])
        if guard_error and target.startswith("-"):
            raise OSError("fake child guard error")
        return types.SimpleNamespace(target=target)

    def cancel(g):
        if g is not None:
            events.append(["cancel", g.target])

    def killpg(pid, sig):
        events.append(["kill", pid, int(sig)])
        child.rc = -9

    def popen(*args, **kwargs):
        events.append(["trainer", kwargs.get("start_new_session")])
        return child

    with tempfile.TemporaryDirectory(prefix="codex-b2-resume-cpu-") as td:
        run = Path(td)
        (run / "B2").mkdir()
        (run / "campaign.json").write_text(json.dumps(R.campaign_identity(marker)))
        if ckpt is not None:
            (run / "B2" / "resume.pt").write_bytes(ckpt)
        replacements = {
            "RUN_DIR": str(run), "RESUME_CKPT_SHA256": hashlib.sha256(b"bound").hexdigest(),
            "volume": Volume(), "time": types.SimpleNamespace(time=lambda: clock["t"]),
            "_versions_ok": lambda: {"ok": version, "got": {}},
            "deadline_killer": killer, "cancel_killer": cancel,
            "modal": types.SimpleNamespace(Dict=types.SimpleNamespace(from_name=lambda _: Starts())),
            "subprocess": types.SimpleNamespace(Popen=popen, TimeoutExpired=subprocess.TimeoutExpired),
            "supervise_child": lambda *args: SUPERVISE(*args, killpg=killpg, clock=lambda: clock["t"]),
        }
        with contextlib.ExitStack() as stack:
            for key, value in replacements.items():
                stack.enter_context(patch.object(R, key, value))
            try:
                result, error = RAW(3000.0), None
            except Exception as e:
                result, error = None, f"{type(e).__name__}: {e}"
    spawned = any(e[0] == "trainer" for e in events)
    assert not (spawned and child.rc is None), name
    if events and events[0][0] == "arm":
        assert any(e[0] == "cancel" and e[1] == events[0][1] for e in events), name
    return {"name": name, "result": result, "error": error, "events": events,
            "trainer_spawned": spawned, "child_still_running": spawned and child.rc is None,
            "clock": clock["t"]}


cases = [
    check("start-2 exact checkpoint succeeds"),
    check("start-2 advanced checkpoint refuses", ckpt=b"advanced"),
    check("missing checkpoint refuses", ckpt=None),
    check("resume deadline differs refuses", resume=3001.0),
    check("original deadline missing refuses", original=None),
    check("foreign campaign marker refuses", marker=401.0),
    check("all three starts already used refuses", claims=3),
    check("missing start-1 cannot start a new campaign", claims=0),
    check("pinned versions differ refuses", version=False),
    check("setup leaves less than minimum budget refuses", setup_delay=1200),
    check("initial commit fails before trainer", initial_fail=True),
    check("initial commit leaves too little time refuses", initial_delay=1200),
    check("poll exception reaps child and cancels guards", poll_error=True),
    check("child guard arming failure reaps child", guard_error=True),
    check("deadline already expired refuses before setup", now=3000.0),
    check("start-3 advanced checkpoint allowed", claims=2, ckpt=b"advanced"),
    check("blocking commit consumes remaining time and kills child", periodic_delay=1900),
]
assert cases[0]["result"]["returncode"] == 0 and cases[0]["result"]["start"] == "start-2"
assert all(c["result"].get("refused") and not c["trainer_spawned"] for c in cases[1:12])
assert all(c["error"] and any(e[0] == "kill" for e in c["events"]) for c in cases[12:14])
assert cases[14]["result"]["refused"] and cases[14]["events"] == []
assert cases[15]["result"]["returncode"] == 0 and cases[15]["result"]["start"] == "start-3"
assert cases[16]["result"]["returncode"] == "timeout"
assert all(not c["child_still_running"] for c in cases)
(REPORT / "independent-worker-checks.json").write_text(json.dumps(cases, indent=2))
print(json.dumps({"full_worker_cases_passed": len(cases), "real_remote_calls": 0, "real_processes": 0}))
