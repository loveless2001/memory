"""M4-SGM P2.5 B2 occupied-fill LONG run runner (ONE arm, 1500 updates, resumable; branch
m4-sgm-occupied-fill-v1). DERIVED from the cleared B1 runner (v0.2 7e9213a; diff the two), which is
derived from the frozen Stage A runner v0.4. Same image, resources, deadline killers, memsub binding,
bounded cleanup and ledger rule. Changes for a multi-hour run:
  * a Modal Volume (VOLUME_NAME at /vol) holds the run directory; the train script writes an atomic
    resume checkpoint every 50 updates and the worker commits the Volume every COMMIT_EVERY_S while
    the child runs, so a preempted/restarted container RESUMES instead of losing the run;
  * at most MAX_STARTS admitted starts per campaign, each claimed atomically in the start Dict
    (start-1..start-N, put skip_if_exists); Modal retries (MAX_STARTS - 1) re-enter the function, a
    start beyond MAX_STARTS refuses; every start shares the ONE immutable campaign deadline;
  * the child gets min(remaining - END_MARGIN_S) and is polled (stdout/stderr to Volume files, not
    pipes); after it ends the worker commits and returns a tar of the run dir WITHOUT resume.pt.

ONE ephemeral `modal run` (NOT --detach) under an outer local `timeout`. If the local client dies, the
ephemeral app stops; the Volume keeps every committed checkpoint/telemetry row (a relaunch would
need a new approval). After the client exits, `python <this file> cleanup-verify <out>` stops the
app by its recorded id within ONE overall CLEANUP_S budget.
Charge reservation (ledger()): GPU-container seconds <= client lifetime OUTER_S + STOP_ALLOWANCE_S
(max_containers=1 serializes starts; no work runs past the deadline). CONDITIONAL on the app
stopping within the cleanup window and CPU use within the 25% margin (CPU limits are soft). Volume
storage is not priced (small; one run directory).

    timeout --signal=TERM --kill-after=30s <OUTER_S - 30> .venv/bin/python -m modal run \
        modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-long-run-runner.py --out <new local dir>
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-long-run-runner.py cleanup-verify <out dir>
"""

import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import modal

APP_NAME = "memsub-m4-sgm-p2p5-b2-occupied-fill-long"
START_DICT = "m4-sgm-p2p5-b2-occupied-fill-long-starts-v1"
VOLUME_NAME = "memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1"
RUN_DIR = "/vol/b2-run-v1"
EXPECT_MEMSUB_SHA256 = "d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532"   # branch @ 1b01245
BASE_IMAGE_ID = "im-A7BXMB8v1cVYRvC9pMqZ3i"      # dev-GPU runner image (hotspot-l40s-v1.console.log:155)
EXPECT_VERSIONS = {"torch": "2.7.1+cu126", "transformers": "4.55.2"}
GPU, CPU_CORES, MEMORY_GIB = "L40S", 4.0, 32
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S = 0.000542, 0.0000131, 0.00000222   # modal.com/pricing
CPU_OVERUSE_MARGIN = 1.25
ARMS = ("B2",)
CAMPAIGN_S = 23400               # immutable deadline = first-call time + 6.5 h (projected work ~4.4 h)
FUNCTION_S, STARTUP_S = CAMPAIGN_S, 300
MAX_STARTS, MIN_START_S, END_MARGIN_S, COMMIT_EVERY_S = 3, 900, 120, 60
CLIENT_TAIL_S, CLEANUP_S, CAP_USD = 240, 300, 17.0
STOP_ALLOWANCE_S = CLEANUP_S     # ledger stop allowance == the whole bounded cleanup window (codex 22132)
OUTER_S = CAMPAIGN_S + CLIENT_TAIL_S
INPUT_MANIFEST = "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"
SCRIPT = "scripts/sgm-p2p5-b2-occupied-fill-long-run-train.py"
STAGE_A_SCRIPT = "scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py"     # imported by SCRIPT (bands, binding)
CONTROL_LOGIC_FILE = "modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py"


def ledger() -> dict:
    """Charge reservation in USD; the only unenforced term is the app-stop latency allowance."""
    rate = GPU_USD_S + CPU_OVERUSE_MARGIN * CPU_CORES * CPU_USD_CORE_S + MEMORY_GIB * MEM_USD_GIB_S
    gpu_s = OUTER_S + STOP_ALLOWANCE_S
    bound = gpu_s * rate
    return {"rate_usd_s": rate, "cpu_overuse_margin": CPU_OVERUSE_MARGIN, "outer_s": OUTER_S,
            "stop_allowance_s": STOP_ALLOWANCE_S, "image_construction_usd": 0.0, "reservation_usd": bound,
            "cap_usd": CAP_USD, "cleanup_budget_s": CLEANUP_S,
            "assumptions": ["the app stops within CLEANUP_S after the client exits (cleanup-verify checks; "
                            "if unverified: manual stop, and billing past it is NOT covered)",
                            f"CPU use <= {CPU_OVERUSE_MARGIN} x {CPU_CORES} cores (Modal CPU limits are soft; "
                            "overuse is billed)"],
            "unenforced": "app-stop latency after client exit; CPU overuse beyond the margin"}


app = modal.App(APP_NAME)
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


def deadline_killer(target: str, seconds: float) -> subprocess.Popen:
    """Independent sleeper in its own session: SIGKILL `target` ("<pid>" or "-<pgid>" for a whole
    process group; dash syntax) after `seconds`. It survives a hung caller."""
    return subprocess.Popen(["/bin/sh", "-c", f"sleep {max(seconds, 0.0):.3f}; kill -KILL {target}"],
                            start_new_session=True)


def cancel_killer(proc) -> None:
    if proc is not None:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)       # the sleeper's sh AND its sleep
        proc.wait()


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


@app.function(image=image, gpu=GPU, cpu=(CPU_CORES, CPU_CORES), memory=(MEMORY_GIB * 1024, MEMORY_GIB * 1024),
              timeout=FUNCTION_S, startup_timeout=STARTUP_S, max_containers=1, scaledown_window=2,
              retries=modal.Retries(max_retries=MAX_STARTS - 1, initial_delay=1.0, backoff_coefficient=1.0),
              volumes={"/vol": volume})
def run_b2_remote(deadline: float) -> dict:
    if deadline - time.time() <= END_MARGIN_S:
        return {"refused": "campaign deadline passed or within the end margin at worker entry"}
    worker_guard = deadline_killer(str(os.getpid()), deadline - time.time())   # before any blocking setup
    try:
        starts = modal.Dict.from_name(START_DICT, create_if_missing=True)
        key = claim_start(starts, {"task": os.environ.get("MODAL_TASK_ID"), "t": time.time()})
        if key is None:
            return {"refused": f"all {MAX_STARTS} starts already used"}
        if starts.get("deadline") != deadline:
            return {"refused": "campaign deadline missing or differs from the immutable one", "start": key}
        ver = _versions_ok()
        if not ver["ok"]:
            return {"refused": f"pinned versions differ: {ver['got']}", "start": key}
        volume.reload()                                  # see the latest committed checkpoint
        remaining = deadline - time.time()               # RE-READ after setup, immediately before the child
        if remaining < MIN_START_S:
            return {"refused": f"only {remaining:.0f}s to the campaign deadline (< {MIN_START_S})", "start": key}
        child_s = remaining - END_MARGIN_S
        run, arm = Path(RUN_DIR), ARMS[0]
        run.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, SCRIPT, "--manifest", INPUT_MANIFEST, "--out", str(run / arm)]
        t0, rc, commit_errors = time.time(), None, 0
        with open(run / f"{arm}.{key}.stdout.txt", "w") as so, open(run / f"{arm}.{key}.stderr.txt", "w") as se:
            child = subprocess.Popen(cmd, cwd="/root/repo", stdout=so, stderr=se, start_new_session=True)
            child_guard = deadline_killer(f"-{child.pid}", deadline - time.time())   # the child's own group
            try:
                while rc is None:
                    left = t0 + child_s - time.time()
                    if left <= 0:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait()
                        rc = "timeout"
                        break
                    try:
                        rc = child.wait(timeout=min(COMMIT_EVERY_S, left))
                    except subprocess.TimeoutExpired:
                        commit_errors += safe_commit()   # checkpoints/telemetry survive a preemption
            finally:
                if child.poll() is None:                 # any abnormal exit: never leave a trainer behind
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                cancel_killer(child_guard)
        commit_errors += safe_commit()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(run, arcname=".", filter=lambda ti: None if ti.name.endswith(("resume.pt", "resume.pt.tmp")) else ti)
        return {"returncode": rc, "start": key, "volume_commit_errors": commit_errors, "wall_s": time.time() - t0,
                "child_timeout_s": child_s, "versions": ver["got"], "cmd": cmd, "tar": buf.getvalue()}
    finally:
        cancel_killer(worker_guard)


def set_campaign_deadline(starts, now: float) -> float:
    """Write the ONE immutable deadline; refuse if this Dict already has one (no relaunch on a used Dict)."""
    deadline = now + CAMPAIGN_S
    if not starts.put("deadline", deadline, skip_if_exists=True):
        raise SystemExit(f"{START_DICT} already holds a campaign deadline: refusing to relaunch")
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


@app.local_entrypoint()
def main(out: str):
    dest = Path(out)
    got = local_memsub_sha256()
    if got != EXPECT_MEMSUB_SHA256:
        raise SystemExit(f"local memsub sha {got} != bound {EXPECT_MEMSUB_SHA256}: refusing (wrong checkout)")
    dest.mkdir(parents=True, exist_ok=False)
    meta = {"app_id": app.app_id, "memsub_source_sha256": got, "base_image_id": BASE_IMAGE_ID, "arms_planned": list(ARMS), "ledger": ledger(),
            "started": time.time(), "gpu": GPU, "cpu": CPU_CORES, "memory_gib": MEMORY_GIB, "arms": {},
            "outcome": "started"}
    (dest / "run.json").write_text(json.dumps(meta, indent=2))

    def on_sigterm(_sig, _frame):                      # outer `timeout` sends SIGTERM first
        raise SystemExit("SIGTERM (outer timeout)")
    signal.signal(signal.SIGTERM, on_sigterm)
    try:
        meta["deadline"] = set_campaign_deadline(modal.Dict.from_name(START_DICT, create_if_missing=True), time.time())
        (dest / "run.json").write_text(json.dumps(meta, indent=2))
        for arm in ARMS:
            meta["arms"][arm] = {"outcome": "remote call failed", "t_start": time.time()}
            res = run_b2_remote.remote(meta["deadline"])
            tar = res.pop("tar", None)
            if tar is not None:
                with tarfile.open(fileobj=io.BytesIO(tar), mode="r:gz") as t:
                    t.extractall(dest, filter="data")
            ok, why = gate_ok(arm, dest, res)
            meta["arms"][arm].update(res, outcome=why, t_end=time.time())
            (dest / "run.json").write_text(json.dumps(meta, indent=2))
            print(json.dumps({"arm": arm, "ok": ok, "why": why}), flush=True)
            if not ok:
                meta["outcome"] = f"stopped: {why}"
                break
        else:
            meta["outcome"] = "all arms done"
    except BaseException as e:
        meta["outcome"] = f"error: {type(e).__name__}: {str(e)[:500]}"
        raise
    finally:
        meta["client_wall_s"] = time.time() - meta["started"]
        (dest / "run.json").write_text(json.dumps(meta, indent=2))
        print(json.dumps({"app_id": meta["app_id"], "outcome": meta["outcome"],
                          "client_wall_s": round(meta["client_wall_s"], 1)}))
    if meta["outcome"] != "all arms done":
        raise SystemExit(1)


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
    if len(sys.argv) == 3 and sys.argv[1] == "cleanup-verify":
        r = cleanup_verify(Path(sys.argv[2]))
        print(json.dumps({"app_id": r["app_id"], "status": r["status"]}))
        sys.exit(0 if r["status"] == "stopped_verified" else 1)
    raise SystemExit("usage: <runner> cleanup-verify <out dir>   (training runs only via `modal run`)")
