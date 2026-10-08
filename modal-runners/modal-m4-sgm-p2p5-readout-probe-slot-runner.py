"""M4-SGM P2.5 readout-recipe rescue probe (EXPLORATORY) - ONE slot app, 2 packed cells (proposal v0.2 14e2b43).

    .venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py plan|spawn|collect

A NEW entry point (codex 21750 #3). Every binding comes from the pure slot-logic module, loaded BEFORE any Modal
object is built; nothing from the decorated campaign module is imported.
- run_slot (A100-80GB, max_containers=1, single_use_containers, retries 3): at most 4 ADMITTED starts via atomic
  Dict claims. An in-process SIGKILL watchdog fires at the ONE immutable deadline written at spawn. The
  ProbeSlotSupervisor marks a cell COMPLETE only after the path-exact probe validator passes.
- reaper (CPU, every 120 s, in the same app): the shared lifetime-stop logic stops the WHOLE app by its bound id once
  the deadline has passed, or when the app was deployed and never spawned for 1,800 s.
Populations: dev 4242, artifact 9_300_011+s (the P2.5 artifact episodes), train-split 555_001+s. The reserved
readings population is never touched.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import modal

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("probe_slot_logic", _HERE / "modal-m4-sgm-p2p5-readout-probe-slot-logic.py")
L = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L)          # bindings FIRST: every Modal object below is built from L


def _build_environment():
    import subprocess as sp
    sp.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "torch==2.7.1",
            "--index-url", "https://download.pytorch.org/whl/cu126"], check=True)
    sp.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "transformers==4.55.2",
            "safetensors==0.5.3", "numpy==2.2.6", "pytest==8.4.1"], check=True)
    from huggingface_hub import snapshot_download
    snapshot_download("Qwen/Qwen3-0.6B-Base", revision="da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
                      local_dir="/root/models/qwen3-0.6b-base",
                      allow_patterns=["config.json", "generation_config.json", "model.safetensors"])


app = modal.App(L.APP_NAME)
# The run_function builder imports THIS file (its SDK-declared source), which loads the sibling slot logic at import:
# bake the slot logic into a COPY layer BEFORE the builder (codex 21782). The GPU image inherits that layer, so it
# carries no second slot-logic mount. Tested against the SDK's effective build-stage files.
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("huggingface_hub==0.36.2")
         .add_local_file(L.SLOT_LOGIC_FILE, f"/root/{Path(L.SLOT_LOGIC_FILE).name}", copy=True)
         .run_function(_build_environment, timeout=1200, cpu=4.0, memory=8 * 1024)
         .env({"HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false", "M4_SGM_QWEN3_0P6B_DIR": L.MODEL_DIR})
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_dir("configs", "/root/repo/configs")
         .add_local_file(L.LEDGER_FILE, f"/root/repo/{L.LEDGER_FILE}")
         .add_local_file(L.VALIDATOR_FILE, f"/root/repo/{L.VALIDATOR_FILE}")
         .add_local_file(L.LIFETIME_LOGIC_FILE, f"/root/{Path(L.LIFETIME_LOGIC_FILE).name}"))
# the scheduled reaper needs ONLY the shared lifetime logic + the slot logic it is loaded with (no GPU stack)
reaper_image = (modal.Image.debian_slim(python_version="3.12")
                .add_local_file(L.SLOT_LOGIC_FILE, f"/root/{Path(L.SLOT_LOGIC_FILE).name}")
                .add_local_file(L.LIFETIME_LOGIC_FILE, f"/root/{Path(L.LIFETIME_LOGIC_FILE).name}"))
artifacts = modal.Volume.from_name("memsub-artifacts")


def file_sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def lifetime():
    return L.load(Path(L.LIFETIME_LOGIC_FILE).name, "lifetime_logic", root=_HERE)


@app.function(image=reaper_image, schedule=modal.Period(seconds=L.REAPER_PERIOD_S), cpu=0.125, memory=256,
              timeout=110, max_containers=1, retries=0)
def reaper() -> dict:
    """Independent server-side lifetime stop: whole app, BOUND id only (probe decision; shared stop_bound_app)."""
    try:
        self_id = modal.App.lookup(L.APP_NAME).app_id          # read-only lookup, bound write-once by the decision
    except Exception:
        self_id = None
    return L.reap_and_stop(modal.Dict.from_name(L.GUARD_DICT, create_if_missing=True), time.time(), self_id,
                           lifetime().stop_bound_app)


def identity_now(root: str = "/root/repo") -> dict:
    sys.path.insert(0, root)
    import platform
    import torch
    import transformers
    from memsub.sgm.pinned_pretrained_qwen3_backbone import QWEN3_0P6B_BASE
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    return {"runner": file_sha(__file__), "memsub": source_tree_sha256(Path(root) / "memsub"), "slot": L.SLOT,
            "files": {f: file_sha(Path(root) / f) for f in L.BOUND_FILES if not f.startswith("modal-runners/")},
            "slot_logic": file_sha(_HERE / Path(L.SLOT_LOGIC_FILE).name),
            "lifetime_logic": file_sha(_HERE / Path(L.LIFETIME_LOGIC_FILE).name),
            "env": {"python": platform.python_version(), "torch": torch.__version__, "cuda": torch.version.cuda,
                    "transformers": transformers.__version__, "tf32_matmul": torch.backends.cuda.matmul.allow_tf32},
            "model": QWEN3_0P6B_BASE}


@app.function(image=image, gpu=L.GPU, cpu=(L.CPU_CORES, L.CPU_CORES), memory=(L.MEMORY_GIB * 1024, L.MEMORY_GIB * 1024),
              timeout=L.FUNCTION_MAX_S, startup_timeout=300, max_containers=1, single_use_containers=True,
              retries=modal.Retries(max_retries=L.MAX_STARTS - 1, initial_delay=1.0, backoff_coefficient=1.0),
              volumes={"/artifacts": artifacts})
def run_slot(expected: dict) -> dict:
    sys.path.insert(0, "/root/repo")
    from memsub.sgm.p2d_launch_guard import Watchdog
    early = Watchdog(L.EARLY_S)
    try:
        adm = modal.Dict.from_name(L.ADMIT_DICT, create_if_missing=True)
        guard = modal.Dict.from_name(L.GUARD_DICT, create_if_missing=True)
        epoch, why = L.admit(adm, guard, time.time())
        admitted = [n for n in range(1, L.MAX_STARTS + 1) if adm.contains(f"start-{n}")]
        deadline = guard.get("deadline_epoch", None)
    except Exception as e:
        epoch, why, admitted, deadline = None, f"admission error {e!r:.200}", [], None
    finally:
        early.cancel()
    if epoch is None:
        return {"slot": L.SLOT, "status": "admission_refused", "reason": why}
    life = Watchdog(max(1.0, deadline - time.time()))           # SIGKILL at the slot's absolute deadline
    try:
        got = identity_now()
        if {k: got[k] for k in expected} != expected:
            return {"slot": L.SLOT, "status": "identity_mismatch", "epoch": epoch, "got": got}
        pv = L.load(L.VALIDATOR_FILE, "probe_validation", root=Path("/root/repo"))
        cells = L.probe_cells(json.loads(Path("/root/repo", L.GRID_FILE).read_text()))
        registry = json.loads(Path("/root/repo", L.REGISTRY_FILE).read_text())["learned"]
        schema = json.loads(Path("/root/repo", L.SCHEMA_FILE).read_text())["learned"]
        artifacts.reload()
        sup = pv.ProbeSlotSupervisor(root=Path("/artifacts") / L.VOLUME_SUBPATH, cells=cells, epoch=epoch,
                                     admitted=admitted, identity={**got, "runner_expected": expected},
                                     checkpoint_every=L.C, eval_cfg=L.EVAL, commit=artifacts.commit,
                                     reload=artifacts.reload, newer_start=lambda: adm.contains(f"start-{epoch + 1}"),
                                     ack_timeout_s=900, provenance={"container_id": os.environ.get("MODAL_TASK_ID"),
                                                                    "admitted_at": time.time()},
                                     registry=registry, schema=schema)
        res = sup.run()
        artifacts.commit()
        return {"slot": L.SLOT, "status": "slot_done", "epoch": epoch, **res}
    finally:
        life.cancel()


# ---------------- local side ----------------

def expected_identity() -> dict:
    sys.path.insert(0, str(Path.cwd()))
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    return {"runner": file_sha(__file__), "memsub": source_tree_sha256(Path("memsub")), "slot": L.SLOT,
            "files": {f: file_sha(f) for f in L.BOUND_FILES if not f.startswith("modal-runners/")},
            "slot_logic": file_sha(L.SLOT_LOGIC_FILE), "lifetime_logic": file_sha(L.LIFETIME_LOGIC_FILE)}


def spawn() -> None:
    tracked = ["memsub", "scripts", "configs", "modal-runners", L.LEDGER_FILE]
    if subprocess.run(["git", "status", "--porcelain", "--", *tracked], capture_output=True, text=True,
                      check=True).stdout.strip():
        raise SystemExit("refusing to spawn from a dirty tree")
    now = time.time()
    candidate = now + L.deadline_s(json.loads(Path(L.LEDGER_FILE).read_text()))   # ONE immutable deadline
    guard = modal.Dict.from_name(L.GUARD_DICT, create_if_missing=True)
    deployed = modal.App.lookup(L.APP_NAME).app_id
    problem = L.spawn_guard_problem(dict(guard.items()), deployed, now)
    if problem:
        raise SystemExit(f"refusing to spawn: {problem}")
    root = Path(L.LOCAL_OUT) / L.GROUP / L.SLOT
    root.mkdir(parents=True, exist_ok=False)
    prov = {"slot": L.SLOT, "expected_identity": expected_identity(), "spawn_epoch": now, "deadline_epoch": candidate,
            "app_name": L.APP_NAME, "deployed_app_id": deployed,
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()}
    (root / "launch_provenance.json").write_text(json.dumps(prov, indent=2))
    if not (guard.put("app_id", prov["deployed_app_id"], skip_if_exists=True)
            and guard.put("deadline_epoch", prov["deadline_epoch"], skip_if_exists=True)):
        raise SystemExit("guard app id / deadline already set")
    call = modal.Function.from_name(L.APP_NAME, "run_slot").spawn(prov["expected_identity"]).object_id
    (root / "call.json").write_text(json.dumps({"call_id": call}))
    print("spawned", L.SLOT, call)


def poll(call_id: str):
    """('pending'|'expired'|'failed'|'result', payload) - the campaign collector's poll, without its module."""
    from modal.exception import OutputExpiredError
    try:
        return "result", modal.FunctionCall.from_id(call_id).get(timeout=0)
    except OutputExpiredError:
        return "expired", None
    except TimeoutError:                                # builtin: no output yet
        return "pending", None
    except Exception as e:                              # the function raised (incl. watchdog kill)
        return "failed", repr(e)


def _real_collect() -> dict:
    cp = L.load(L.CONTROL_LOGIC_FILE, "cp")
    lt = L.load(L.LIFETIME_LOGIC_FILE, "lifetime_logic")
    pv = L.load(L.VALIDATOR_FILE, "probe_validation")

    def fetch(dest):
        dest.mkdir(parents=True, exist_ok=False)
        g = subprocess.run([sys.executable, "-m", "modal", "volume", "get", "memsub-artifacts", L.VOLUME_SUBPATH,
                            str(dest)], capture_output=True, text=True, timeout=1800)
        return {"returncode": g.returncode, "stderr_tail": g.stderr[-500:]}

    def export(root):
        out = {}
        for key, name in (("guard", L.GUARD_DICT), ("admission", L.ADMIT_DICT)):
            d = dict(modal.Dict.from_name(name).items())
            (root / f"{key}.json").write_text(json.dumps(d, indent=2, default=str))
            out[key] = d
        return out
    report = L.collect(Path(L.LOCAL_OUT) / L.GROUP / L.SLOT, cp=cp, poller=poll, stopper=lt.stop_bound_app,
                       verifier=lambda app_id: cp.verify_stopped(app_id, cp.modal_cli_json), fetch=fetch,
                       export=export, now=time.time(), cells=L.probe_cells(json.loads(Path(L.GRID_FILE).read_text())),
                       registry=json.loads(Path(L.REGISTRY_FILE).read_text())["learned"],
                       schema=json.loads(Path(L.SCHEMA_FILE).read_text())["learned"], validate=pv.validate_probe_outputs)
    print(json.dumps({"slot": L.SLOT, "poll": report["poll"], "final": "final_shutdown" in report}))
    return report


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    {"plan": lambda: print(json.dumps({"slot": L.SLOT, "app": L.APP_NAME,
                                       "deadline_s": L.deadline_s(json.loads(Path(L.LEDGER_FILE).read_text()))})),
     "spawn": spawn, "collect": _real_collect}[sys.argv[1]]()
