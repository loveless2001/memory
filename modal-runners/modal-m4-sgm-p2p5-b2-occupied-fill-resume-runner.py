"""M4-SGM P2.5 B2 occupied-fill RESUME runner (v0.4; branch m4-sgm-occupied-fill-v1). DERIVED from the
cleared B2 v0.3 runner (24b1432; diff the two). Start-1 ran under v0.3 (app ap-VsAmnu1E7eS5rXLrKD7vXd)
and was stopped at the user's request (gravity 22196) at update ~770; the Volume holds the update-750
checkpoint. This runner only CONTINUES that campaign (same Dict, Volume, run dir, train script, memsub).
Helpers marked "verbatim v0.3" are byte-identical to the cleared runner (a test compares them).
Changes vs v0.3:
  * HOST-INDEPENDENT: the function is DEPLOYED (DEPLOY_APP) and SPAWNED once, so the call runs without
    the local client (v0.3 was an ephemeral `modal run` that stops with the PC). GPU time is bounded in
    the worker: child timeout at the resume deadline - END_MARGIN_S, worker SIGKILL at the deadline,
    a start entering after the deadline refuses at entry; the function timeout (RESUME_S) is the backstop;
  * a fresh resume deadline (RESUME_S after the spawn), written ONCE under RESUME_KEY in the SAME start
    Dict; the ORIGINAL campaign deadline stays the campaign identity checked against campaign.json;
  * a resume start must be start-2 or start-3 (start-1 belongs to v0.3) and needs the run dir's
    resume.pt (never a fresh campaign); the local precheck refuses unless the Dict/Volume are exactly
    start-1's stopped campaign;
  * the worker returns no tar: results stay on the Volume (`collect` fetches them, without resume.pt);
  * a local `watch` (only while this PC is up) stops + verifies the deployed app once the call returns
    or at the resume deadline + END_MARGIN_S. If the PC is down, the deployed app idles with no
    containers after the call ends; cleanup-verify then runs when the PC is back.
Charge reservation (ledger()): (RESUME_S + STARTUP_S) x rate on top of start-1's provisional spend,
within CAP_USD. CONDITIONAL on the in-worker guards (CPU-tested), Modal scaling the deployed function
to zero after the call, and CPU use within the 25% margin. Modal 1.5.1 drives `.remote()` retries from
the client; whether a SPAWNED call is retried after a preemption is unverified, so a preemption may just
end the call at its last checkpoint (any further start needs a new approval).

    .venv/bin/python <this file> precheck                       # read-only: Dict/Volume = start-1's campaign
    .venv/bin/python -m modal deploy <this file>
    .venv/bin/python <this file> spawn-resume <new local out>    # re-check, set the deadline, spawn ONE call
    .venv/bin/python <this file> watch <out>                     # call returned / deadline -> cleanup-verify
    .venv/bin/python <this file> status <out>                    # read-only call state
    .venv/bin/python <this file> collect <out>                   # fetch the Volume run dir (no resume.pt)
    .venv/bin/python <this file> cleanup-verify <out>            # stop (un-deploy) the app, verify
"""

import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import modal

CAMPAIGN_APP = "memsub-m4-sgm-p2p5-b2-occupied-fill-long"       # start-1 (v0.3) app name: campaign identity
DEPLOY_APP = "memsub-m4-sgm-p2p5-b2-occupied-fill-resume1"
START_DICT = "m4-sgm-p2p5-b2-occupied-fill-long-starts-v1"
VOLUME_NAME = "memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1"
RUN_DIR = "/vol/b2-run-v1"
RUN_REL = "b2-run-v1"                                            # RUN_DIR inside the Volume
RESUME_KEY = "resume-1-deadline"
START1_APP_ID = "ap-VsAmnu1E7eS5rXLrKD7vXd"
START1_PROVISIONAL_USD = 5.69262133    # billing report 05:00-07:00Z rows for START1_APP_ID (CPU+L40S+Memory)
EXPECT_MEMSUB_SHA256 = "d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532"   # branch @ 1b01245
BASE_IMAGE_ID = "im-A7BXMB8v1cVYRvC9pMqZ3i"      # dev-GPU runner image (hotspot-l40s-v1.console.log:155)
EXPECT_VERSIONS = {"torch": "2.7.1+cu126", "transformers": "4.55.2"}
GPU, CPU_CORES, MEMORY_GIB = "L40S", 4.0, 32
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S = 0.000542, 0.0000131, 0.00000222   # modal.com/pricing
CPU_OVERUSE_MARGIN = 1.25
ARMS = ("B2",)
RESUME_S = 14400                 # resume deadline = spawn time + 4 h (projected remaining work ~3.2 h)
FUNCTION_S, STARTUP_S = RESUME_S, 300
MAX_STARTS, MIN_START_S, END_MARGIN_S, COMMIT_EVERY_S = 3, 900, 120, 60
CLEANUP_S, CAP_USD = 300, 17.0
INPUT_MANIFEST = "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"
SCRIPT = "scripts/sgm-p2p5-b2-occupied-fill-long-run-train.py"
STAGE_A_SCRIPT = "scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py"     # imported by SCRIPT (bands, binding)
CONTROL_LOGIC_FILE = "modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py"


def ledger() -> dict:
    """Resume reservation in USD, plus start-1's provisional spend, against the campaign cap."""
    rate = GPU_USD_S + CPU_OVERUSE_MARGIN * CPU_CORES * CPU_USD_CORE_S + MEMORY_GIB * MEM_USD_GIB_S
    bound = (RESUME_S + STARTUP_S) * rate
    return {"rate_usd_s": rate, "cpu_overuse_margin": CPU_OVERUSE_MARGIN, "resume_s": RESUME_S,
            "startup_allowance_s": STARTUP_S, "reservation_usd": bound,
            "start1_provisional_usd": START1_PROVISIONAL_USD, "campaign_bound_usd": START1_PROVISIONAL_USD + bound,
            "cap_usd": CAP_USD, "cleanup_budget_s": CLEANUP_S,
            "assumptions": ["every in-deadline start ends by the resume deadline (child timeout + worker SIGKILL, "
                            "CPU-tested); a start after it refuses at entry within STARTUP_S",
                            "Modal scales the deployed function to zero after the call (scaledown 2 s, no min containers)",
                            f"CPU use <= {CPU_OVERUSE_MARGIN} x {CPU_CORES} cores (Modal CPU limits are soft; "
                            "overuse is billed)"],
            "unenforced": "if the in-worker guards failed, only the per-attempt function timeout (RESUME_S) and the "
                          "local watcher (PC up) stop it; CPU overuse beyond the margin; start-1 billing backfill"}


app = modal.App(DEPLOY_APP)
volume = modal.Volume.from_name(VOLUME_NAME)                    # must exist (start-1 created it)
image = (modal.Image.from_id(BASE_IMAGE_ID)
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_file(SCRIPT, f"/root/repo/{SCRIPT}")
         .add_local_file(STAGE_A_SCRIPT, f"/root/repo/{STAGE_A_SCRIPT}")
         .add_local_file(INPUT_MANIFEST, f"/root/repo/{INPUT_MANIFEST}"))


def _versions_ok() -> dict:
    import torch
    import transformers
    got = {"torch": torch.__version__, "transformers": transformers.__version__}
    return {"ok": got == EXPECT_VERSIONS, "got": got}


def deadline_killer(target: str, seconds: float) -> subprocess.Popen:
    """Independent sleeper in its own session: SIGKILL `target` ("<pid>" or "-<pgid>" for a whole
    process group; dash syntax) after `seconds`. It survives a hung caller."""
    return subprocess.Popen(["/bin/sh", "-c", f"sleep {max(seconds, 0.0):.3f}; kill -KILL {target}"],
                            start_new_session=True)


def kill_group(killpg, pid: int) -> None:
    """SIGKILL a process group; a group that already exited (exit race) is fine."""
    try:
        killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def cancel_killer(proc) -> None:
    if proc is not None:
        if proc.poll() is None:
            kill_group(os.killpg, proc.pid)          # the sleeper's sh AND its sleep (race-safe)
        proc.wait()


def supervise_child(child, deadline: float, child_s: float, t0: float, *, killer=None, commit=None,
                    killpg=os.killpg, clock=time.time) -> tuple:
    """Own `child` from the moment it exists: arm its absolute group killer INSIDE the try, poll it
    (committing the Volume every COMMIT_EVERY_S), kill it at t0 + child_s; on ANY exit path a live
    child group is SIGKILLed and reaped. -> (returncode or "timeout", commit_errors)."""
    killer, commit = killer or deadline_killer, commit or safe_commit
    guard, rc, commit_errors = None, None, 0
    try:
        guard = killer(f"-{child.pid}", deadline - clock())
        while rc is None:
            left = t0 + child_s - clock()
            if left <= 0:
                kill_group(killpg, child.pid)
                child.wait()
                rc = "timeout"
                break
            try:
                rc = child.wait(timeout=min(COMMIT_EVERY_S, left))
            except subprocess.TimeoutExpired:
                commit_errors += commit()        # checkpoints/telemetry survive a preemption
    finally:
        try:
            if child.poll() is None:             # any abnormal exit: never leave a trainer behind
                kill_group(killpg, child.pid)    # tolerates the exit race (ProcessLookupError)
                child.wait()
        finally:
            cancel_killer(guard)                 # unconditional, even if reaping raised
    return rc, commit_errors


def campaign_dir_problem(run: Path, key: str, want: dict) -> str | None:
    """start-1 needs an EMPTY run dir and records `want`; later starts need exactly `want`."""
    camp = run / "campaign.json"
    if key == "start-1":
        if run.exists() and any(run.iterdir()):
            return f"{run} already populated before start-1 (foreign or previous campaign)"
        run.mkdir(parents=True, exist_ok=True)
        camp.write_text(json.dumps(want, indent=1))
        return None
    if not camp.exists() or json.loads(camp.read_text()) != want:
        return f"{run} does not belong to this campaign"
    return None


def claim_start(starts, info: dict) -> str | None:
    """Atomically claim the first free start-k (k = 1..MAX_STARTS); None when all are used."""
    for k in range(1, MAX_STARTS + 1):
        if starts.put(f"start-{k}", info, skip_if_exists=True):
            return f"start-{k}"
    return None


def safe_commit() -> int:
    """Commit the Volume; a failure is counted, never raised (raising would orphan the trainer)."""
    try:
        volume.commit()
        return 0
    except Exception:
        return 1


def campaign_identity(campaign_deadline) -> dict:
    """campaign.json exactly as start-1 (v0.3) wrote it: the ORIGINAL deadline stays the campaign identity."""
    return {"app": CAMPAIGN_APP, "start_dict": START_DICT, "volume": VOLUME_NAME, "deadline": campaign_deadline}


def resume_start_problem(key, starts_get, deadline: float, run: Path, arm: str) -> str | None:
    """Why this RESUME start must refuse (None = train). Needs the reloaded Volume."""
    if key is None:
        return f"all {MAX_STARTS} starts already used"
    if key == "start-1":
        return "claimed start-1: this Dict never ran v0.3's start-1 (the resume runner never starts a campaign)"
    if starts_get(RESUME_KEY) != deadline:
        return "resume deadline missing or differs from the write-once one"
    if starts_get("deadline") is None:
        return "original campaign deadline missing from the start Dict"
    problem = campaign_dir_problem(run, key, campaign_identity(starts_get("deadline")))
    if problem:
        return problem
    if not (run / arm / "resume.pt").exists():
        return f"no {run / arm / 'resume.pt'}: the resume runner never trains from scratch"
    return None


@app.function(image=image, gpu=GPU, cpu=(CPU_CORES, CPU_CORES), memory=(MEMORY_GIB * 1024, MEMORY_GIB * 1024),
              timeout=FUNCTION_S, startup_timeout=STARTUP_S, max_containers=1, scaledown_window=2,
              retries=modal.Retries(max_retries=MAX_STARTS - 1, initial_delay=1.0, backoff_coefficient=1.0),
              volumes={"/vol": volume})
def run_b2_remote(deadline: float) -> dict:
    if deadline - time.time() <= END_MARGIN_S:
        return {"refused": "resume deadline passed or within the end margin at worker entry"}
    worker_guard = deadline_killer(str(os.getpid()), deadline - time.time())   # before any blocking setup
    try:
        starts = modal.Dict.from_name(START_DICT)                # must exist (start-1 created it)
        key = claim_start(starts, {"task": os.environ.get("MODAL_TASK_ID"), "t": time.time(), "runner": "resume-v0.4"})
        if key is None:
            return {"refused": f"all {MAX_STARTS} starts already used"}
        ver = _versions_ok()
        if not ver["ok"]:
            return {"refused": f"pinned versions differ: {ver['got']}", "start": key}
        volume.reload()                                          # see the latest committed checkpoint
        run, arm = Path(RUN_DIR), ARMS[0]
        problem = resume_start_problem(key, starts.get, deadline, run, arm)
        if problem:
            return {"refused": problem, "start": key}
        if safe_commit():                                        # the Volume must be committable before training
            return {"refused": "initial Volume commit failed (fail closed before any training)", "start": key}
        remaining = deadline - time.time()                       # RE-READ after setup, immediately before the child
        if remaining < MIN_START_S:
            return {"refused": f"only {remaining:.0f}s left after setup (< {MIN_START_S})", "start": key}
        child_s = remaining - END_MARGIN_S
        cmd = [sys.executable, SCRIPT, "--manifest", INPUT_MANIFEST, "--out", str(run / arm)]
        t0 = time.time()
        with open(run / f"{arm}.{key}.stdout.txt", "w") as so, open(run / f"{arm}.{key}.stderr.txt", "w") as se:
            child = subprocess.Popen(cmd, cwd="/root/repo", stdout=so, stderr=se, start_new_session=True)
            rc, commit_errors = supervise_child(child, deadline, child_s, t0)
        commit_errors += safe_commit()
        return {"returncode": rc, "start": key, "volume_commit_errors": commit_errors, "wall_s": time.time() - t0,
                "child_timeout_s": child_s, "versions": ver["got"], "cmd": cmd}
    finally:
        cancel_killer(worker_guard)


def set_resume_deadline(starts, now: float) -> float:
    """Write the ONE resume deadline; refuse if this Dict already has one (one resume per package)."""
    deadline = now + RESUME_S
    if not starts.put(RESUME_KEY, deadline, skip_if_exists=True):
        raise SystemExit(f"{START_DICT} already holds {RESUME_KEY}: refusing a second resume")
    return deadline


def local_memsub_sha256() -> str:
    """Hash of the local memsub tree that `add_local_dir` mounts (same rule as source_tree_sha256)."""
    import hashlib
    root, h = Path("memsub"), hashlib.sha256()
    for f in sorted(root.rglob("*.py")):
        if "pycache" in f.parent.name:
            continue
        h.update(str(f.relative_to(root.parent)).encode() + b"\0")
        h.update(f.read_bytes() + b"\0")
    return h.hexdigest()


def gate_ok(arm: str, dest: Path, res: dict) -> tuple[bool, str]:
    """The arm finished cleanly with a valid result (any band; there is no later arm to gate)."""
    if "refused" in res:
        return False, f"{arm}: refused: {res['refused']}"
    if res.get("returncode") != 0:
        return False, f"{arm}: child returncode {res.get('returncode')}"
    f = dest / arm / "b2_result.json"
    if not f.exists():
        return False, f"{arm}: no b2_result.json"
    r = json.loads(f.read_text())
    if r.get("status") != "valid":
        return False, f"{arm}: INVALID ({r.get('why')})"
    return True, f"{arm}: valid, memory_used {r['memory_used']}, band {r['band_at_end']}"


def precheck_problem(starts_get, run_files: set, campaign) -> str | None:
    """Local (before deploy, again before spawn): the Dict/Volume must be exactly start-1's stopped campaign."""
    if starts_get("deadline") is None or starts_get("start-1") is None:
        return "start Dict lacks start-1's campaign deadline or claim"
    for k in ("start-2", "start-3", RESUME_KEY):
        if starts_get(k) is not None:
            return f"start Dict already holds {k}: refusing"
    if campaign != campaign_identity(starts_get("deadline")):
        return "Volume campaign.json does not match the start Dict's campaign"
    if f"{ARMS[0]}/resume.pt" not in run_files:
        return "no resume.pt in the Volume run dir"
    return None


def _volume_files(vol) -> list:
    """(path inside RUN_REL, entry) for every FILE in the Volume run dir."""
    return [(e.path.lstrip("/").removeprefix(RUN_REL + "/"), e) for e in vol.listdir(RUN_REL, recursive=True)
            if e.type == modal.volume.FileEntryType.FILE]


def volume_state(vol) -> tuple:
    files = {p for p, _ in _volume_files(vol)}
    camp = json.loads(b"".join(vol.read_file(f"{RUN_REL}/campaign.json"))) if "campaign.json" in files else None
    return files, camp


def precheck(starts=None, vol=None) -> str | None:
    starts, vol = starts or modal.Dict.from_name(START_DICT), vol or volume
    if local_memsub_sha256() != EXPECT_MEMSUB_SHA256:
        return "local memsub differs from the bound sha (wrong checkout)"
    files, camp = volume_state(vol)
    return precheck_problem(starts.get, files, camp)


def deployed_app_id(modal_json) -> str:
    rows = [r for r in modal_json(["app", "list"]) if r.get("description") == DEPLOY_APP and r.get("state") == "deployed"]
    if len(rows) != 1:
        raise SystemExit(f"expected exactly one deployed {DEPLOY_APP}, found {len(rows)}")
    return rows[0]["app_id"]


def spawn_resume(out: Path, starts=None, vol=None, fn=None, modal_json=None, clock=time.time) -> dict:
    """Re-check, record the deployed app id, write the ONE resume deadline, spawn ONE call; run.json at each step."""
    out.mkdir(parents=True, exist_ok=False)
    meta = {"runner": "b2-resume-v0.4", "ledger": ledger(), "started": clock(), "outcome": "precheck"}

    def save():
        (out / "run.json").write_text(json.dumps(meta, indent=2))
    save()
    starts = starts or modal.Dict.from_name(START_DICT)
    problem = precheck(starts, vol)
    if problem:
        meta["outcome"] = f"refused: {problem}"
        save()
        raise SystemExit(meta["outcome"])
    if modal_json is None:
        spec = importlib.util.spec_from_file_location("cp", Path(__file__).resolve().parents[1] / CONTROL_LOGIC_FILE)
        cp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cp)
        modal_json = cp.modal_cli_json
    meta.update(app_id=deployed_app_id(modal_json), outcome="app recorded")   # cleanup-verify stops this id
    save()
    meta.update(deadline=set_resume_deadline(starts, clock()), outcome="deadline set")
    save()
    fn = fn or modal.Function.from_name(DEPLOY_APP, "run_b2_remote")
    meta.update(call_id=fn.spawn(meta["deadline"]).object_id, outcome="spawned", spawned=clock())
    save()
    return meta


def call_state(call_id: str, from_id=None) -> tuple:
    """("done", result) only when the call RETURNED; ("running", None); ("unknown", why) on any other error."""
    from_id = from_id or modal.FunctionCall.from_id
    try:
        res = from_id(call_id).get(timeout=0)
    except TimeoutError:
        return "running", None
    except Exception as e:
        return "unknown", f"{type(e).__name__}: {str(e)[:300]}"
    return ("done", res) if isinstance(res, dict) else ("unknown", "non-dict result")


def watch(out: Path, poll_s: float = 60.0, grace_s: float = END_MARGIN_S, state=call_state, cleanup=None,
          clock=time.time, sleep=time.sleep) -> dict:
    """Stop + verify the deployed app once the call returned, or at the resume deadline + grace_s (backstop).
    An unknown state never triggers an early stop."""
    meta = json.loads((out / "run.json").read_text())
    while True:
        st, info = state(meta["call_id"])
        if st == "done":
            (out / "call_result.json").write_text(json.dumps(info, indent=2, default=str))
            reason = "call returned"
            break
        if clock() >= meta["deadline"] + grace_s:
            reason = f"resume deadline + {grace_s:.0f}s passed (last state {st}: {info})"
            break
        sleep(poll_s)
    (out / "watch.json").write_text(json.dumps({"reason": reason, "t": clock()}, indent=2))
    return (cleanup or cleanup_verify)(out)


def collect(out: Path, vol=None) -> dict:
    """Fetch the Volume run dir (everything but resume.pt) to <out>/volume and gate the result."""
    vol, n = vol or volume, 0
    for rel, e in _volume_files(vol):
        if rel.endswith(("resume.pt", "resume.pt.tmp")):
            continue
        f = out / "volume" / RUN_REL / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"".join(vol.read_file(e.path)))
        n += 1
    res_file = out / "call_result.json"
    res = json.loads(res_file.read_text()) if res_file.exists() else {"returncode": "call result not recorded"}
    ok, why = gate_ok(ARMS[0], out / "volume" / RUN_REL, res)
    rec = {"files": n, "ok": ok, "why": why}
    (out / "collect.json").write_text(json.dumps(rec, indent=2))
    return rec


def cleanup_verify(out: Path, budget_s: float = CLEANUP_S, wait_s: float = 20.0, cp=None,
                   run=subprocess.run, sleep=time.sleep, clock=time.monotonic) -> dict:
    """After the client exits: stop the recorded app id, then require verify_stopped (app stopped, zero
    tasks, zero containers), re-checking because task counts lag. EVERYTHING (the stop call, each
    app/container list call, the waits) shares ONE overall budget of `budget_s` seconds (= the
    ledger's STOP_ALLOWANCE_S): each Modal CLI call gets timeout min(60, time left) and no call
    starts with <= 1 s left. Not verified by then -> "shutdown_unresolved" (escalate: manual stop;
    billing past this point is the unenforced residual). Writes cleanup.json; returns it."""
    end = clock() + budget_s

    def left() -> float:
        return end - clock()

    def cli(args: list, check: bool):
        t = min(60.0, left())
        if t <= 1.0:
            raise TimeoutError("cleanup budget exhausted")
        return run([sys.executable, "-m", "modal", *args], capture_output=True, text=True, timeout=t, check=check)

    def modal_json(args: list) -> list:
        return json.loads(cli([*args, "--json"], True).stdout)

    if cp is None:
        spec = importlib.util.spec_from_file_location("cp", Path(__file__).resolve().parents[1] / CONTROL_LOGIC_FILE)
        cp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cp)
    try:
        app_id = json.loads((out / "run.json").read_text()).get("app_id")
    except (OSError, ValueError):
        app_id = None                                  # the client failed before the entrypoint wrote run.json
    out.mkdir(parents=True, exist_ok=True)
    rec = {"app_id": app_id, "budget_s": budget_s, "checks": []}
    if not (isinstance(app_id, str) and app_id.startswith("ap-")):
        rec["status"] = "unresolved: no app id recorded"
    else:
        try:
            r = cli(["app", "stop", app_id], False)
            rec["stop"] = {"returncode": r.returncode, "stderr_tail": (r.stderr or "")[-300:]}
        except Exception as e:
            rec["stop"] = {"error": repr(e)[:300]}
        while True:
            v = cp.verify_stopped(app_id, modal_json)       # its CLI errors/timeouts leave it unverified
            rec["checks"].append(v)
            if v.get("verified") is True or left() <= wait_s + 1.0:
                break
            sleep(wait_s)
        rec["status"] = "stopped_verified" if rec["checks"][-1].get("verified") is True else "shutdown_unresolved"
    rec["elapsed_s"] = budget_s - left()
    (out / "cleanup.json").write_text(json.dumps(rec, indent=2, default=str))
    return rec


if __name__ == "__main__":
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    if cmd == "precheck" and not args:
        p = precheck()
        print(json.dumps({"precheck": p or "ok"}))
        sys.exit(1 if p else 0)
    if cmd == "spawn-resume" and len(args) == 1:
        m = spawn_resume(Path(args[0]))
        print(json.dumps({k: m.get(k) for k in ("app_id", "call_id", "deadline", "outcome")}))
        sys.exit(0)
    if cmd == "watch" and len(args) == 1:
        r = watch(Path(args[0]))
        print(json.dumps({"app_id": r["app_id"], "status": r["status"]}))
        sys.exit(0 if r["status"] == "stopped_verified" else 1)
    if cmd == "status" and len(args) == 1:
        st, info = call_state(json.loads((Path(args[0]) / "run.json").read_text())["call_id"])
        print(json.dumps({"state": st, "info": info}, default=str)[:2000])
        sys.exit(0)
    if cmd == "collect" and len(args) == 1:
        r = collect(Path(args[0]))
        print(json.dumps(r))
        sys.exit(0 if r["ok"] else 1)
    if cmd == "cleanup-verify" and len(args) == 1:
        r = cleanup_verify(Path(args[0]))
        print(json.dumps({"app_id": r["app_id"], "status": r["status"]}))
        sys.exit(0 if r["status"] == "stopped_verified" else 1)
    raise SystemExit("usage: <runner> precheck | spawn-resume|watch|status|collect|cleanup-verify <out dir>")
