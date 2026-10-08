"""M4-SGM P2.5 Stage A read-escape blocker screen runner (proposal v0.3; user 21977 "modal run", $4 cap).

ONE ephemeral `modal run` (NOT --detach) under an outer local `timeout`. The local entrypoint
writes ONE immutable campaign deadline, then calls the remote arm function in order A0 -> A1 -> A2,
stopping at the first problem:
  * A1/A2 run only if A0 is valid and band_at_100 == "escaped" (the within-setting gate);
  * any remote error, refusal, non-zero child or INVALID result stops the sequence.
Each call's tar is extracted locally before the next call, so earlier arms are kept.
Server-side bounds (codex 21987):
  * image = an EXISTING verified image by id: the dev-GPU runner's pinned stack plus Qwen weights,
    built once on 10-06, so there is no image build. The repo files are runtime mounts;
  * one L40S with hard CPU/RAM tuples, retries=0, max_containers=1 (containers never overlap),
    scaledown_window=2, Modal function timeout FUNCTION_S;
  * restart accounting: first statement = atomic Dict.put(arm, ..., skip_if_exists=True); a second
    start of an arm refuses before any model work;
  * campaign deadline: the remote function refuses unless the Dict's immutable deadline equals the
    one passed and at least MIN_ARM_S remain. The child timeout is min(CHILD_S, remaining -
    END_MARGIN_S), so no arm's work runs past the deadline;
  * pinned versions are checked in the container before the child; a mismatch refuses.
Charge ledger (ledger()): GPU-container seconds <= client lifetime (OUTER_S, from the first call)
+ STOP_ALLOWANCE_S, because max_containers=1 serializes containers and the ephemeral app stops
when the client exits. STOP_ALLOWANCE_S (app-stop latency) is an allowance, not enforced; the gap
to the $4 cap is reported. Image build: none. Max 3 arms x 100 updates.

    timeout --signal=TERM --kill-after=30s <OUTER_S - 30> .venv/bin/python -m modal run \
        modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py --out <new local dir>
"""

import io
import json
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import modal

APP_NAME = "memsub-m4-sgm-p2p5-stage-a-read-escape"
START_DICT = "m4-sgm-p2p5-stage-a-read-escape-starts-v2"
BASE_IMAGE_ID = "im-A7BXMB8v1cVYRvC9pMqZ3i"      # dev-GPU runner image (hotspot-l40s-v1.console.log:155)
EXPECT_VERSIONS = {"torch": "2.7.1+cu126", "transformers": "4.55.2"}
GPU, CPU_CORES, MEMORY_GIB = "L40S", 4.0, 32
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S = 0.000542, 0.0000131, 0.00000222   # modal.com/pricing
ARMS = ("A0", "A1", "A2")
CAMPAIGN_S = 4500                # immutable deadline = first-call time + CAMPAIGN_S
FUNCTION_S, CHILD_S = 1560, 1500
MIN_ARM_S, END_MARGIN_S = 600, 90
CLIENT_TAIL_S, STOP_ALLOWANCE_S, CAP_USD = 240, 300, 4.0
OUTER_S = CAMPAIGN_S + CLIENT_TAIL_S
INPUT_MANIFEST = "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json"
SCRIPT = "scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py"


def ledger() -> dict:
    """All-in upper bound in USD. The only unenforced term is the app-stop latency allowance."""
    rate = GPU_USD_S + CPU_CORES * CPU_USD_CORE_S + MEMORY_GIB * MEM_USD_GIB_S
    gpu_s = OUTER_S + STOP_ALLOWANCE_S
    bound = gpu_s * rate
    return {"rate_usd_s": rate, "outer_s": OUTER_S, "stop_allowance_s": STOP_ALLOWANCE_S, "image_build_usd": 0.0,
            "bound_usd": bound, "cap_usd": CAP_USD,
            "extra_unenforced_seconds_before_cap": (CAP_USD - bound) / rate}


app = modal.App(APP_NAME)
image = (modal.Image.from_id(BASE_IMAGE_ID)
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_file(SCRIPT, f"/root/repo/{SCRIPT}")
         .add_local_file(INPUT_MANIFEST, f"/root/repo/{INPUT_MANIFEST}"))


def _versions_ok() -> dict:
    import torch
    import transformers
    got = {"torch": torch.__version__, "transformers": transformers.__version__}
    return {"ok": got == EXPECT_VERSIONS, "got": got}


@app.function(image=image, gpu=GPU, cpu=(CPU_CORES, CPU_CORES), memory=(MEMORY_GIB * 1024, MEMORY_GIB * 1024),
              timeout=FUNCTION_S, retries=0, max_containers=1, scaledown_window=2)
def run_arm_remote(arm: str, deadline: float) -> dict:
    import os
    starts = modal.Dict.from_name(START_DICT, create_if_missing=True)
    if not starts.put(arm, {"task": os.environ.get("MODAL_TASK_ID"), "t": time.time()}, skip_if_exists=True):
        return {"refused": f"arm {arm} already started once", "existing": starts.get(arm)}
    if starts.get("deadline") != deadline:
        return {"refused": "campaign deadline missing or differs from the immutable one"}
    remaining = deadline - time.time()
    if remaining < MIN_ARM_S:
        return {"refused": f"only {remaining:.0f}s to the campaign deadline (< {MIN_ARM_S})"}
    ver = _versions_ok()
    if not ver["ok"]:
        return {"refused": f"pinned versions differ: {ver['got']}"}
    child_s = min(CHILD_S, remaining - END_MARGIN_S)
    out = Path(tempfile.mkdtemp(prefix=f"stage-a-{arm}-"))          # fresh per call (warm containers)
    cmd = [sys.executable, SCRIPT, "--arm", arm, "--manifest", INPUT_MANIFEST, "--out", str(out / arm)]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd="/root/repo", capture_output=True, text=True, timeout=child_s)
        rc, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        rc, stdout, stderr = "timeout", str(e.stdout or ""), str(e.stderr or "")
    (out / f"{arm}.stdout.txt").write_text(stdout)
    (out / f"{arm}.stderr.txt").write_text(stderr)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(out, arcname=".")
    return {"returncode": rc, "wall_s": time.time() - t0, "child_timeout_s": child_s, "versions": ver["got"],
            "cmd": cmd, "tar": buf.getvalue()}


def set_campaign_deadline(starts, now: float) -> float:
    """Write the ONE immutable deadline; refuse if this Dict already has one (no relaunch on a used Dict)."""
    deadline = now + CAMPAIGN_S
    if not starts.put("deadline", deadline, skip_if_exists=True):
        raise SystemExit(f"{START_DICT} already holds a campaign deadline: refusing to relaunch")
    return deadline


def gate_ok(arm: str, dest: Path, res: dict) -> tuple[bool, str]:
    """Continue only if this arm finished cleanly with a valid result; after A0 also require 'escaped'."""
    if "refused" in res:
        return False, f"{arm}: refused: {res['refused']}"
    if res.get("returncode") != 0:
        return False, f"{arm}: child returncode {res.get('returncode')}"
    f = dest / arm / "stage_a_result.json"
    if not f.exists():
        return False, f"{arm}: no stage_a_result.json"
    r = json.loads(f.read_text())
    if r.get("status") != "valid":
        return False, f"{arm}: INVALID ({r.get('why')})"
    if arm == "A0" and r.get("band_at_100") != "escaped":
        return False, f"A0 did not reproduce the escape (band {r.get('band_at_100')}): stop before A1/A2"
    return True, f"{arm}: valid, band {r['band_at_100']}"


@app.local_entrypoint()
def main(out: str):
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=False)
    meta = {"app_id": app.app_id, "base_image_id": BASE_IMAGE_ID, "arms_planned": list(ARMS), "ledger": ledger(),
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
