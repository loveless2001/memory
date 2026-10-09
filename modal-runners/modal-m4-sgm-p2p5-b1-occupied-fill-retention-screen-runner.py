"""M4-SGM P2.5 B1 occupied-fill retention screen runner (ONE arm, 100 updates; branch
m4-sgm-occupied-fill-v1). DERIVED from the frozen Stage A runner v0.4
(modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py; diff the two): same
server-side controls, new app/Dict/script identities, one arm, shorter campaign, and a local
memsub source-hash binding (the variant source, not the frozen campaign's 2eee4228).

ONE ephemeral `modal run` (NOT --detach) under an outer local `timeout`. The local entrypoint
refuses unless the local memsub tree hashes to EXPECT_MEMSUB_SHA256, writes ONE immutable
campaign deadline, then calls the remote arm function ONCE (no continuation, no retry). After the
client exits, `python <this file> cleanup-verify <out>` stops the app by its recorded id and
verifies it stopped with zero containers (PK control-logic verify_stopped, reused unchanged).
Server-side controls (codex 21987, 21999):
  * image = an EXISTING image by id: the dev-GPU runner's pinned stack plus Qwen weights, so no
    image is constructed; the repo files are runtime mounts;
  * one L40S with CPU/RAM tuples, retries=0, max_containers=1 (no overlap), scaledown_window=2,
    startup_timeout STARTUP_S, Modal function timeout FUNCTION_S;
  * entry: refuse if the immutable deadline is already within END_MARGIN_S; otherwise ARM an
    independent whole-worker deadline killer (own-session sleeper, SIGKILL of this worker at the
    absolute deadline) BEFORE any blocking setup, cancelled in finally;
  * restart accounting: atomic Dict.put(arm, ..., skip_if_exists=True); a second start refuses;
  * the Dict's deadline must equal the one passed; pinned versions are checked;
  * remaining time is RE-READ immediately before the child launches; < MIN_ARM_S refuses. The
    child runs in its own session with timeout min(CHILD_S, remaining - END_MARGIN_S), plus its
    own absolute group killer, so neither the worker nor the child outlives the deadline.
Charge reservation (ledger()): GPU-container seconds <= client lifetime OUTER_S (from the first
call) + STOP_ALLOWANCE_S, because max_containers=1 serializes containers and the ephemeral app
stops when the client exits. No arm work can run past the deadline (server-side). After it only
entry refusals and bounded startups can occur, until the client exits. App-stop latency after
client exit is the one unenforced term; cleanup-verify checks it. CPU is priced with a 25%
overuse margin (CPU limits are soft).

    timeout --signal=TERM --kill-after=30s <OUTER_S - 30> .venv/bin/python -m modal run \
        modal-runners/modal-m4-sgm-p2p5-b1-occupied-fill-retention-screen-runner.py --out <new local dir>
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-b1-occupied-fill-retention-screen-runner.py cleanup-verify <out dir>
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

APP_NAME = "memsub-m4-sgm-p2p5-b1-occupied-fill"
START_DICT = "m4-sgm-p2p5-b1-occupied-fill-starts-v1"
EXPECT_MEMSUB_SHA256 = "d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532"   # branch @ 1b01245
BASE_IMAGE_ID = "im-A7BXMB8v1cVYRvC9pMqZ3i"      # dev-GPU runner image (hotspot-l40s-v1.console.log:155)
EXPECT_VERSIONS = {"torch": "2.7.1+cu126", "transformers": "4.55.2"}
GPU, CPU_CORES, MEMORY_GIB = "L40S", 4.0, 32
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S = 0.000542, 0.0000131, 0.00000222   # modal.com/pricing
CPU_OVERUSE_MARGIN = 1.25
ARMS = ("B1",)
CAMPAIGN_S = 2400                # immutable deadline = first-call time + CAMPAIGN_S (A0 child: 642 s)
FUNCTION_S, CHILD_S, STARTUP_S = 1560, 1500, 300
MIN_ARM_S, END_MARGIN_S = 600, 90
CLIENT_TAIL_S, STOP_ALLOWANCE_S, CAP_USD = 240, 300, 2.5
OUTER_S = CAMPAIGN_S + CLIENT_TAIL_S
INPUT_MANIFEST = "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"
SCRIPT = "scripts/sgm-p2p5-b1-occupied-fill-retention-screen-train.py"
STAGE_A_SCRIPT = "scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py"     # imported by SCRIPT (classify)
CONTROL_LOGIC_FILE = "modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py"


def ledger() -> dict:
    """Charge reservation in USD; the only unenforced term is the app-stop latency allowance."""
    rate = GPU_USD_S + CPU_OVERUSE_MARGIN * CPU_CORES * CPU_USD_CORE_S + MEMORY_GIB * MEM_USD_GIB_S
    gpu_s = OUTER_S + STOP_ALLOWANCE_S
    bound = gpu_s * rate
    return {"rate_usd_s": rate, "cpu_overuse_margin": CPU_OVERUSE_MARGIN, "outer_s": OUTER_S,
            "stop_allowance_s": STOP_ALLOWANCE_S, "image_construction_usd": 0.0, "reservation_usd": bound,
            "cap_usd": CAP_USD, "unenforced": "app-stop latency after client exit (cleanup-verify checks it)"}


app = modal.App(APP_NAME)
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


@app.function(image=image, gpu=GPU, cpu=(CPU_CORES, CPU_CORES), memory=(MEMORY_GIB * 1024, MEMORY_GIB * 1024),
              timeout=FUNCTION_S, startup_timeout=STARTUP_S, retries=0, max_containers=1, scaledown_window=2)
def run_arm_remote(arm: str, deadline: float) -> dict:
    if deadline - time.time() <= END_MARGIN_S:
        return {"refused": "campaign deadline passed or within the end margin at worker entry"}
    worker_guard = deadline_killer(str(os.getpid()), deadline - time.time())   # before any blocking setup
    try:
        starts = modal.Dict.from_name(START_DICT, create_if_missing=True)
        if not starts.put(arm, {"task": os.environ.get("MODAL_TASK_ID"), "t": time.time()}, skip_if_exists=True):
            return {"refused": f"arm {arm} already started once", "existing": starts.get(arm)}
        if starts.get("deadline") != deadline:
            return {"refused": "campaign deadline missing or differs from the immutable one"}
        ver = _versions_ok()
        if not ver["ok"]:
            return {"refused": f"pinned versions differ: {ver['got']}"}
        remaining = deadline - time.time()          # RE-READ after setup, immediately before the child
        if remaining < MIN_ARM_S:
            return {"refused": f"only {remaining:.0f}s to the campaign deadline (< {MIN_ARM_S})"}
        child_s = min(CHILD_S, remaining - END_MARGIN_S)
        out = Path(tempfile.mkdtemp(prefix=f"b1-{arm}-"))               # fresh per call (warm containers)
        cmd = [sys.executable, SCRIPT, "--manifest", INPUT_MANIFEST, "--out", str(out / arm)]
        t0 = time.time()
        child = subprocess.Popen(cmd, cwd="/root/repo", stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 start_new_session=True)
        child_guard = deadline_killer(f"-{child.pid}", deadline - time.time())   # the child's own group
        try:
            stdout, stderr = child.communicate(timeout=child_s)
            rc = child.returncode
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            stdout, stderr = child.communicate()
            rc = "timeout"
        finally:
            cancel_killer(child_guard)
        (out / f"{arm}.stdout.txt").write_text(stdout or "")
        (out / f"{arm}.stderr.txt").write_text(stderr or "")
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(out, arcname=".")
        return {"returncode": rc, "wall_s": time.time() - t0, "child_timeout_s": child_s, "versions": ver["got"],
                "cmd": cmd, "tar": buf.getvalue()}
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
    f = dest / arm / "b1_result.json"
    if not f.exists():
        return False, f"{arm}: no b1_result.json"
    r = json.loads(f.read_text())
    if r.get("status") != "valid":
        return False, f"{arm}: INVALID ({r.get('why')})"
    return True, f"{arm}: valid, band {r['band_at_100']}"


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
            res = run_arm_remote.remote(arm, meta["deadline"])
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


def cleanup_verify(out: Path, attempts: int = 4, wait_s: float = 20.0, cp=None, stopper=None, sleep=time.sleep) -> dict:
    """After the client exits: stop the recorded app id (bounded CLI call; an already-stopped ephemeral app is
    fine), then require verify_stopped (app stopped, zero tasks, zero containers), re-checking a few times
    because task counts lag. Writes cleanup.json; returns it."""
    if cp is None:
        spec = importlib.util.spec_from_file_location("cp", Path(__file__).resolve().parents[1] / CONTROL_LOGIC_FILE)
        cp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cp)
    try:
        app_id = json.loads((out / "run.json").read_text()).get("app_id")
    except (OSError, ValueError):
        app_id = None                                  # the client failed before the entrypoint wrote run.json
    out.mkdir(parents=True, exist_ok=True)
    rec = {"app_id": app_id, "checks": []}
    if not (isinstance(app_id, str) and app_id.startswith("ap-")):
        rec["status"] = "unresolved: no app id recorded"
    else:
        stop = stopper or (lambda a: subprocess.run([sys.executable, "-m", "modal", "app", "stop", a],
                                                    capture_output=True, text=True, timeout=60))
        try:
            r = stop(app_id)
            rec["stop"] = {"returncode": getattr(r, "returncode", None), "stderr_tail": (getattr(r, "stderr", "") or "")[-300:]}
        except Exception as e:
            rec["stop"] = {"error": repr(e)[:300]}
        for i in range(attempts):
            v = cp.verify_stopped(app_id, cp.modal_cli_json)
            rec["checks"].append(v)
            if v.get("verified") is True:
                break
            if i < attempts - 1:
                sleep(wait_s)
        rec["status"] = "stopped_verified" if rec["checks"][-1].get("verified") is True else "shutdown_unresolved"
    (out / "cleanup.json").write_text(json.dumps(rec, indent=2, default=str))
    return rec


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "cleanup-verify":
        r = cleanup_verify(Path(sys.argv[2]))
        print(json.dumps({"app_id": r["app_id"], "status": r["status"]}))
        sys.exit(0 if r["status"] == "stopped_verified" else 1)
    raise SystemExit("usage: <runner> cleanup-verify <out dir>   (training runs only via `modal run`)")
