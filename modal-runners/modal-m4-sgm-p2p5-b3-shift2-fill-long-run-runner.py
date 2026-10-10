"""M4-SGM P2.5 B3 runner: B2 recipe + feature_shift=2 (proposal v0.3, plans/261010-0256-…/; branch
m4-sgm-occupied-fill-v1). DERIVED from the audited B2 resume runner
(modal-m4-sgm-p2p5-b2-occupied-fill-resume-runner.py; diff the two). Helpers marked "verbatim B2" are
byte-identical (a test compares them). Changes vs the B2 resume runner:
  * FRESH campaign: new app/Dict/Volume; start-1 needs an EMPTY run dir; ONE immutable campaign deadline
    (spawn + CAMPAIGN_S) written once under DEADLINE_KEY; nothing inherited from B2's resume amendment;
  * <= MAX_STARTS = 3 TOTAL admitted starts (initial + <= 2 resumptions). A resumption happens ONLY through
    Modal's own function retries after a platform interruption (preemption / container loss); a later start
    resumes from the Volume resume.pt (or, if interrupted before the first checkpoint, restarts from scratch
    with the prior partial archived). Whether Modal retries a SPAWNED call after a preemption is UNVERIFIED
    (B2 never exercised it): a preemption may simply end the campaign; any manual re-spawn needs a NEW approval;
  * every non-interruption outcome (completed, deadline, run-side failure, refusal, worker exception) writes a
    write-once TERMINAL marker in the start Dict; a start that sees it refuses at entry (no failure retry);
  * cleanup stops the DEPLOYED app with `modal app stop --yes <bound id>` (B2's missing --yes; codex 22287);
  * HOST-INDEPENDENT: training (deploy + one spawn). The child timeout (deadline - END_MARGIN_S) may let the
    worker return normally; the worker SIGKILL at the deadline cannot return normally (the call then ends in
    error). Call completion does NOT by itself establish zero containers or zero compute charges: scaledown,
    refusal and recovery tails are accounted in the ledger and must be verified.
    PC-DEPENDENT: `watch` / `cleanup-verify`: stop + separately verify (app stopped/unlisted, zero tasks, zero
    containers). An idle deployed app with zero containers is distinct from, and NOT, stopped_verified.

    .venv/bin/python <this file> precheck                 # read-only: fresh Dict/Volume, bound memsub
    .venv/bin/python -m modal deploy <this file>
    .venv/bin/python <this file> spawn <new local out>     # re-check, record app id, write the deadline, spawn ONE call
    .venv/bin/python <this file> watch <out>               # call returned / deadline + grace -> cleanup-verify
    .venv/bin/python <this file> status <out>              # read-only call state
    .venv/bin/python <this file> collect <out>             # fetch the Volume run dir (no resume.pt)
    .venv/bin/python <this file> cleanup-verify <out>      # stop (un-deploy) the app with --yes, verify
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

DEPLOY_APP = "memsub-m4-sgm-p2p5-b3-shift2-fill-long"
START_DICT = "m4-sgm-p2p5-b3-shift2-fill-long-starts-v1"
VOLUME_NAME = "memsub-m4-sgm-p2p5-b3-shift2-fill-long-v1"
RUN_DIR = "/vol/b3-run-v1"
RUN_REL = "b3-run-v1"                                            # RUN_DIR inside the Volume
DEADLINE_KEY, TERMINAL_KEY = "campaign-deadline", "terminal"
EXPECT_MEMSUB_SHA256 = "d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532"   # = B2's tree (no memsub edit)
BASE_IMAGE_ID = "im-A7BXMB8v1cVYRvC9pMqZ3i"      # B2's pinned dev-GPU image
EXPECT_VERSIONS = {"torch": "2.7.1+cu126", "transformers": "4.55.2"}
GPU, CPU_CORES, MEMORY_GIB = "L40S", 4.0, 32
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S = 0.000542, 0.0000131, 0.00000222   # modal.com/pricing
CPU_OVERUSE_MARGIN = 1.25
ARMS = ("B3",)
CAMPAIGN_S = 23400               # immutable campaign deadline = spawn time + 6.5 h
FUNCTION_S, STARTUP_S = CAMPAIGN_S, 300
MAX_STARTS, MIN_START_S, END_MARGIN_S, COMMIT_EVERY_S = 3, 900, 120, 60
WATCH_POLL_S = 60.0              # watch poll interval: the backstop can be noticed up to one poll late (ledger)
CLEANUP_S, CAP_USD, BUILD_ALLOWANCE_USD = 300, 17.0, 0.10
INPUT_MANIFEST = "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"
SCRIPT = "scripts/sgm-p2p5-b3-shift2-fill-long-run-train.py"
STAGE_A_SCRIPT = "scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py"     # imported by SCRIPT (bands, binding)
CONTROL_LOGIC_FILE = "modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py"


def ledger() -> dict:
    """Conditional reservation in USD against the cap (proposal v0.3 §2, window amended in the package audit):
    max_containers=1, so billed container-seconds <= wall time until the app is stopped, i.e. the campaign
    (spawn -> deadline) + the watch backstop grace (deadline + END_MARGIN_S) + one watch poll of lag (WATCH_POLL_S)
    + the full cleanup budget, which cleanup_verify still receives after a late poll (codex 22521)."""
    rate = GPU_USD_S + CPU_OVERUSE_MARGIN * CPU_CORES * CPU_USD_CORE_S + MEMORY_GIB * MEM_USD_GIB_S
    window = CAMPAIGN_S + END_MARGIN_S + WATCH_POLL_S + CLEANUP_S
    compute = window * rate
    total = compute + BUILD_ALLOWANCE_USD
    return {"rate_usd_s": rate, "cpu_overuse_margin": CPU_OVERUSE_MARGIN, "campaign_s": CAMPAIGN_S,
            "watch_grace_s": END_MARGIN_S, "cleanup_s": CLEANUP_S, "window_s": window, "compute_reservation_usd": compute, "build_allowance_usd": BUILD_ALLOWANCE_USD,
            "reservation_usd": total, "cap_usd": CAP_USD, "headroom_usd": CAP_USD - total,
            "assumptions": [f"<= {CPU_OVERUSE_MARGIN * CPU_CORES:g} billed CPU cores (Modal CPU limits are soft)",
                            f"<= {window} aggregate billed container-seconds across ALL starts and container "
                            "attempts incl. startup/refusal/retry/crash-reschedule tails (max_containers=1 + the "
                            "PC-dependent watch stopping the app by deadline + grace + one poll + cleanup; status-call, network and stop tails beyond that are NOT covered)",
                            f"memory billed at <= {MEMORY_GIB} GiB",
                            "the deployed app is stopped within the cleanup window", "rates unchanged",
                            "storage/transfer small and unpriced"],
            "unenforced": "CPU overuse beyond the margin; billing tails; a PC-down period delays cleanup-verify: "
                          "zero-container idle is guaranteed only on a healthy completed path; a crashing deployed "
                          "container may be rescheduled indefinitely (Modal retries guide), so a crash loop while "
                          "the PC is down is NOT bounded by this reservation"}


app = modal.App(DEPLOY_APP)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
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


def deadline_killer(target: str, seconds: float) -> subprocess.Popen:       # verbatim B2
    """Independent sleeper in its own session: SIGKILL `target` ("<pid>" or "-<pgid>" for a whole
    process group; dash syntax) after `seconds`. It survives a hung caller."""
    return subprocess.Popen(["/bin/sh", "-c", f"sleep {max(seconds, 0.0):.3f}; kill -KILL {target}"],
                            start_new_session=True)


def kill_group(killpg, pid: int) -> None:                                    # verbatim B2
    """SIGKILL a process group; a group that already exited (exit race) is fine."""
    try:
        killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def cancel_killer(proc) -> None:                                             # verbatim B2
    if proc is not None:
        if proc.poll() is None:
            kill_group(os.killpg, proc.pid)          # the sleeper's sh AND its sleep (race-safe)
        proc.wait()


def supervise_child(child, deadline: float, child_s: float, t0: float, *, killer=None, commit=None,
                    killpg=os.killpg, clock=time.time) -> tuple:                # verbatim B2
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


def campaign_dir_problem(run: Path, key: str, want: dict) -> str | None:     # verbatim B2
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


def claim_start(starts, info: dict) -> str | None:                           # verbatim B2
    """Atomically claim the first free start-k (k = 1..MAX_STARTS); None when all are used."""
    for k in range(1, MAX_STARTS + 1):
        if starts.put(f"start-{k}", info, skip_if_exists=True):
            return f"start-{k}"
    return None


def safe_commit() -> int:                                                    # verbatim B2
    """Commit the Volume; a failure is counted, never raised (raising would orphan the trainer)."""
    try:
        volume.commit()
        return 0
    except Exception:
        return 1


def campaign_identity(deadline) -> dict:
    return {"app": DEPLOY_APP, "start_dict": START_DICT, "volume": VOLUME_NAME, "deadline": deadline}


def mark_terminal(starts, key, reason: str) -> str | None:
    """Write-once terminal marker: no later start may train (no failure retry). NEVER raises: a failed write is
    RETURNED for the caller to report, because an exception leaving the worker would trigger Modal's function
    retries = a forbidden run-side retry (codex 22515)."""
    try:
        starts.put(TERMINAL_KEY, {"start": key, "reason": reason, "t": time.time()}, skip_if_exists=True)
        return None
    except Exception as e:
        return f"{type(e).__name__}: {str(e)[:200]}"


def start_problem(key, starts_get, deadline: float, run: Path) -> str | None:
    """Why this start must refuse (None = train). Needs the reloaded Volume."""
    if key is None:
        return f"all {MAX_STARTS} starts already used"
    if starts_get(DEADLINE_KEY) != deadline:
        return "campaign deadline missing or differs from the write-once one"
    return campaign_dir_problem(run, key, campaign_identity(deadline))


@app.function(image=image, gpu=GPU, cpu=(CPU_CORES, CPU_CORES), memory=(MEMORY_GIB * 1024, MEMORY_GIB * 1024),
              timeout=FUNCTION_S, startup_timeout=STARTUP_S, max_containers=1, scaledown_window=2,
              retries=modal.Retries(max_retries=MAX_STARTS - 1, initial_delay=1.0, backoff_coefficient=1.0),
              volumes={"/vol": volume})
def run_b3_remote(deadline: float) -> dict:
    return worker(deadline)


def worker(deadline: float, starts=None, vol=None, versions=_versions_ok, popen=subprocess.Popen,
           supervise=None, clock=time.time) -> dict:
    """One admitted start. Every non-interruption outcome marks the campaign TERMINAL (incl. exceptions).
    NOTHING escapes as an exception (codex 22515): the watchdog, the Dict lookup and every later step run inside
    the guarded block; body exceptions become a returned refusal; a failed terminal write is reported in
    `terminal_write_errors` instead of raised. An escaping exception would trigger Modal's function retries."""
    if deadline - clock() <= END_MARGIN_S:
        return {"refused": "campaign deadline passed or within the end margin at worker entry"}
    ctx = {"starts": starts, "key": None, "terminal_write_errors": []}
    worker_guard = None
    try:
        worker_guard = deadline_killer(str(os.getpid()), deadline - clock())     # before any blocking setup
        ctx["starts"] = ctx["starts"] or modal.Dict.from_name(START_DICT)
        res = _admitted_start(deadline, ctx, vol or volume, versions, popen, supervise, clock)
    except Exception as e:                                       # a worker exception is run-side: never retried
        res = {"refused": f"worker exception {type(e).__name__}", "start": ctx["key"]}
        _terminal(ctx, f"worker exception {type(e).__name__}: {str(e)[:200]}")
    finally:
        try:
            cancel_killer(worker_guard)
        except Exception as e:                                   # reported below, never raised
            ctx["guard_cancel_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    if ctx["terminal_write_errors"]:
        res["terminal_write_errors"] = ctx["terminal_write_errors"]
    if "guard_cancel_error" in ctx:
        res["guard_cancel_error"] = ctx["guard_cancel_error"]
    return res


def _terminal(ctx: dict, reason: str) -> None:
    """mark_terminal for the current start; a failed write (or no Dict at all) is recorded, never raised."""
    err = mark_terminal(ctx["starts"], ctx["key"], reason) if ctx["starts"] is not None else "no start Dict"
    if err:
        ctx["terminal_write_errors"].append(err)


def _admitted_start(deadline: float, ctx: dict, vol, versions, popen, supervise, clock) -> dict:
    """The body of `worker` (may raise; `worker` contains it). ctx["key"] is set as soon as a start is claimed."""
    starts = ctx["starts"]
    if starts.get(TERMINAL_KEY) is not None:
        return {"refused": f"campaign is terminal: {starts.get(TERMINAL_KEY)}"}
    ctx["key"] = key = claim_start(starts, {"task": os.environ.get("MODAL_TASK_ID"), "t": clock(), "runner": "b3-v0.1"})
    if key is None:
        _terminal(ctx, "start budget exhausted")
        return {"refused": f"all {MAX_STARTS} starts already used"}
    ver = versions()
    if not ver["ok"]:
        _terminal(ctx, f"pinned versions differ: {ver['got']}")
        return {"refused": f"pinned versions differ: {ver['got']}", "start": key}
    vol.reload()                                                 # see the latest committed checkpoint
    run, arm = Path(RUN_DIR), ARMS[0]
    problem = start_problem(key, starts.get, deadline, run)
    if problem:
        _terminal(ctx, problem)
        return {"refused": problem, "start": key}
    if safe_commit():
        _terminal(ctx, "initial Volume commit failed")
        return {"refused": "initial Volume commit failed (fail closed before any training)", "start": key}
    remaining = deadline - clock()                               # RE-READ after setup, immediately before the child
    if remaining < MIN_START_S:
        _terminal(ctx, "too little time left to start")
        return {"refused": f"only {remaining:.0f}s left after setup (< {MIN_START_S})", "start": key}
    child_s = remaining - END_MARGIN_S
    cmd = [sys.executable, SCRIPT, "--manifest", INPUT_MANIFEST, "--out", str(run / arm)]
    t0 = clock()
    with open(run / f"{arm}.{key}.stdout.txt", "w") as so, open(run / f"{arm}.{key}.stderr.txt", "w") as se:
        child = popen(cmd, cwd="/root/repo", stdout=so, stderr=se, start_new_session=True)
        rc, commit_errors = (supervise or supervise_child)(child, deadline, child_s, t0)
    commit_errors += safe_commit()
    _terminal(ctx, "completed" if rc == 0 else ("deadline" if rc == "timeout" else f"run-side failure rc {rc}"))
    return {"returncode": rc, "start": key, "volume_commit_errors": commit_errors, "wall_s": clock() - t0,
            "child_timeout_s": child_s, "versions": ver["got"], "cmd": cmd}


def set_campaign_deadline(starts, now: float) -> float:
    """Write the ONE campaign deadline; refuse if this Dict already has one (fresh campaign only)."""
    deadline = now + CAMPAIGN_S
    if not starts.put(DEADLINE_KEY, deadline, skip_if_exists=True):
        raise SystemExit(f"{START_DICT} already holds {DEADLINE_KEY}: refusing (not a fresh campaign)")
    return deadline


def local_memsub_sha256() -> str:                                            # verbatim B2
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
    """The arm finished cleanly with a valid result."""
    if "refused" in res:
        return False, f"{arm}: refused: {res['refused']}"
    if res.get("returncode") != 0:
        return False, f"{arm}: child returncode {res.get('returncode')}"
    f = dest / arm / "b3_result.json"
    if not f.exists():
        return False, f"{arm}: no b3_result.json"
    r = json.loads(f.read_text())
    if r.get("status") != "valid":
        return False, f"{arm}: INVALID ({r.get('why')})"
    return True, f"{arm}: valid, memory_used {r['memory_used']}, band {r['band_at_end']}"


def precheck_problem(dict_keys: list, run_files: set) -> str | None:
    """Fresh campaign only: the start Dict must be empty and the Volume run dir must not exist."""
    if dict_keys:
        return f"start Dict {START_DICT} is not empty ({sorted(dict_keys)[:5]}): refusing"
    if run_files:
        return f"Volume {VOLUME_NAME}:{RUN_REL} is not empty: refusing"
    return None


def _volume_files(vol) -> list:
    """(path inside RUN_REL, entry) for every FILE in the Volume run dir. ONLY an established "absent" signal
    (Modal NotFoundError / FileNotFoundError) means no files; any other listing error (timeout, permission, ...)
    PROPAGATES so that precheck and collect fail closed (codex 22515)."""
    try:
        entries = vol.listdir(RUN_REL, recursive=True)
    except (modal.exception.NotFoundError, FileNotFoundError):     # run dir absent on a fresh Volume
        return []
    return [(e.path.lstrip("/").removeprefix(RUN_REL + "/"), e) for e in entries
            if e.type == modal.volume.FileEntryType.FILE]


def precheck(starts=None, vol=None) -> str | None:
    starts, vol = starts or modal.Dict.from_name(START_DICT, create_if_missing=True), vol or volume
    if local_memsub_sha256() != EXPECT_MEMSUB_SHA256:
        return "local memsub differs from the bound sha (wrong checkout)"
    try:
        run_files = {p for p, _ in _volume_files(vol)}
    except Exception as e:                           # fail closed: an unreadable Volume is NOT a fresh one
        return f"Volume {VOLUME_NAME}:{RUN_REL} listing failed ({type(e).__name__}: {str(e)[:200]}): refusing"
    return precheck_problem(list(starts.keys()), run_files)


def deployed_app_id(modal_json) -> str:
    rows = [r for r in modal_json(["app", "list"]) if r.get("description") == DEPLOY_APP and r.get("state") == "deployed"]
    if len(rows) != 1:
        raise SystemExit(f"expected exactly one deployed {DEPLOY_APP}, found {len(rows)}")
    return rows[0]["app_id"]


def _control_logic():
    spec = importlib.util.spec_from_file_location("cp", Path(__file__).resolve().parents[1] / CONTROL_LOGIC_FILE)
    cp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cp)
    return cp


def spawn(out: Path, starts=None, vol=None, fn=None, modal_json=None, clock=time.time) -> dict:
    """Re-check (fresh), record the deployed app id, write the ONE campaign deadline, spawn ONE call."""
    out.mkdir(parents=True, exist_ok=False)
    meta = {"runner": "b3-v0.1", "ledger": ledger(), "started": clock(), "outcome": "precheck"}

    def save():
        (out / "run.json").write_text(json.dumps(meta, indent=2))
    save()
    starts = starts or modal.Dict.from_name(START_DICT, create_if_missing=True)
    problem = precheck(starts, vol)
    if problem:
        meta["outcome"] = f"refused: {problem}"
        save()
        raise SystemExit(meta["outcome"])
    meta.update(app_id=deployed_app_id(modal_json or _control_logic().modal_cli_json), outcome="app recorded")
    save()
    meta.update(deadline=set_campaign_deadline(starts, clock()), outcome="deadline set")
    save()
    fn = fn or modal.Function.from_name(DEPLOY_APP, "run_b3_remote")
    meta.update(call_id=fn.spawn(meta["deadline"]).object_id, outcome="spawned", spawned=clock())
    save()
    return meta


def call_state(call_id: str, from_id=None) -> tuple:                         # verbatim B2
    """("done", result) only when the call RETURNED; ("running", None); ("unknown", why) on any other error."""
    from_id = from_id or modal.FunctionCall.from_id
    try:
        res = from_id(call_id).get(timeout=0)
    except TimeoutError:
        return "running", None
    except Exception as e:
        return "unknown", f"{type(e).__name__}: {str(e)[:300]}"
    return ("done", res) if isinstance(res, dict) else ("unknown", "non-dict result")


def watch(out: Path, poll_s: float = WATCH_POLL_S, grace_s: float = END_MARGIN_S, state=call_state, cleanup=None,
          clock=time.time, sleep=time.sleep) -> dict:
    """Stop + verify the deployed app once the call returned, or at the campaign deadline + grace_s (backstop).
    An unknown state never triggers an early stop."""
    meta = json.loads((out / "run.json").read_text())
    while True:
        st, info = state(meta["call_id"])
        if st == "done":
            (out / "call_result.json").write_text(json.dumps(info, indent=2, default=str))
            reason = "call returned"
            break
        if clock() >= meta["deadline"] + grace_s:
            reason = f"campaign deadline + {grace_s:.0f}s passed (last state {st}: {info})"
            break
        sleep(poll_s)
    (out / "watch.json").write_text(json.dumps({"reason": reason, "t": clock()}, indent=2))
    return (cleanup or cleanup_verify)(out)


def collect(out: Path, vol=None) -> dict:
    """Fetch the Volume run dir (everything but resume.pt) to <out>/volume and gate the result. The gate needs
    the arm's b3_result.json fetched IN THIS CALL: a listing error or a missing result is ok=False, never a
    pass on local files left by an earlier collect (codex 22515)."""
    vol, n, fetched = vol or volume, 0, set()
    try:
        files = _volume_files(vol)
    except Exception as e:
        rec = {"files": 0, "ok": False, "why": f"Volume listing failed: {type(e).__name__}: {str(e)[:200]}"}
        (out / "collect.json").write_text(json.dumps(rec, indent=2))
        return rec
    for rel, e in files:
        if rel.endswith(("resume.pt", "resume.pt.tmp")):
            continue
        f = out / "volume" / RUN_REL / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"".join(vol.read_file(e.path)))
        n, _ = n + 1, fetched.add(rel)
    res_file = out / "call_result.json"
    res = json.loads(res_file.read_text()) if res_file.exists() else {"returncode": "call result not recorded"}
    ok, why = gate_ok(ARMS[0], out / "volume" / RUN_REL, res)
    if f"{ARMS[0]}/b3_result.json" not in fetched:
        ok, why = False, f"{ARMS[0]}/b3_result.json not fetched from the Volume in this collect ({why})"
    rec = {"files": n, "ok": ok, "why": why}
    (out / "collect.json").write_text(json.dumps(rec, indent=2))
    return rec


def cleanup_verify(out: Path, budget_s: float = CLEANUP_S, wait_s: float = 20.0, cp=None,
                   run=subprocess.run, sleep=time.sleep, clock=time.monotonic) -> dict:
    """Stop the recorded DEPLOYED app id with `modal app stop --yes <id>` (non-interactive; B2 aborted without
    --yes), then require verify_stopped (stopped, zero tasks, zero containers), re-checking because task
    counts lag. All CLI calls and waits share ONE budget of `budget_s` seconds; each call gets
    min(60, time left). Not verified by then -> "shutdown_unresolved". Writes cleanup.json; returns it.
    The re-check loop is ALSO capped at MAX_CHECKS = budget_s // wait_s + 2 iterations, so a `sleep` that does not
    wait (a test fake, a regression) cannot spin and grow `checks` without bound (2026-10-10 local OOM, M4 run)."""
    end = clock() + budget_s
    max_checks = int(budget_s // max(wait_s, 1.0)) + 2

    def left() -> float:
        return end - clock()

    def cli(args: list, check: bool):
        t = min(60.0, left())
        if t <= 1.0:
            raise TimeoutError("cleanup budget exhausted")
        return run([sys.executable, "-m", "modal", *args], capture_output=True, text=True, timeout=t, check=check)

    def modal_json(args: list) -> list:
        return json.loads(cli([*args, "--json"], True).stdout)

    cp = cp or _control_logic()
    try:
        app_id = json.loads((out / "run.json").read_text()).get("app_id")
    except (OSError, ValueError):
        app_id = None
    out.mkdir(parents=True, exist_ok=True)
    rec = {"app_id": app_id, "budget_s": budget_s, "checks": []}
    if not (isinstance(app_id, str) and app_id.startswith("ap-")):
        rec["status"] = "unresolved: no app id recorded"
    else:
        try:
            r = cli(["app", "stop", "--yes", app_id], False)
            rec["stop"] = {"returncode": r.returncode, "stderr_tail": (r.stderr or "")[-300:]}
        except Exception as e:
            rec["stop"] = {"error": repr(e)[:300]}
        while True:
            v = cp.verify_stopped(app_id, modal_json)
            rec["checks"].append(v)
            if v.get("verified") is True or left() <= wait_s + 1.0 or len(rec["checks"]) >= max_checks:
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
    if cmd == "spawn" and len(args) == 1:
        m = spawn(Path(args[0]))
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
    raise SystemExit("usage: <runner> precheck | spawn|watch|status|collect|cleanup-verify <out dir>")
