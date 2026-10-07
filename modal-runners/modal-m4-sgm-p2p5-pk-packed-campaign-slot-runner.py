"""M4-SGM P2.5 Amendment PK — CAMPAIGN slot runner: ONE app per slot (codex 21596 per-slot envelope).

    M4_PK_SLOT=learned-n32 .venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py
    M4_PK_SLOT=learned-n32 .venv/bin/python modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py plan|spawn|collect

The slot id is fixed at deploy time (env, baked into the image env) and selects: the app name, the guard /
admission Dicts, the artifact root and the slot's two registered cells (PK1 pairing: same arm + N, seeds 0+1).
Each app: one GPU function (A100-80GB, max_containers=1, single_use_containers, platform retries 3 → at most 4
ADMITTED starts via atomic Dict claims), an absolute deadline written ONCE at spawn (never reset) = the slot's
PK6 reserve life; every start arms an in-process SIGKILL watchdog at that deadline. The whole-app stop past the
deadline is done by the separate control-plane reaper app (one schedule for all apps), which receives this
app's bound id + deadline at spawn (write-once registry). Registered populations: dev 4242, artifact
9_300_011+s, train-split 555_001+s; the reserved readings population is never touched here.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import modal

GRID_FILE = "configs/m4_sgm_p2p5_grid.json"
REGISTRY_FILE, SCHEMA_FILE = "configs/m4_sgm_p2p5_campaign_registry.json", "configs/m4_sgm_p2p5_campaign_output_schema.json"
PRICE_FILE = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk6/priced-estimate-v5.json"
CONTROL_REGISTRY_DICT = "m4-sgm-p2p5-pk-campaign-control-registry"
CONTROL_GUARD_DICT = "m4-sgm-p2p5-pk-campaign-control-guard"
CONTROL_APP_NAME = "memsub-m4-sgm-p2p5-pk-campaign-control"
VALIDATION_SETUP_S, CONTROL_SLACK_S = 3600, 1800          # must equal the control app's (tested)
GROUP, LOCAL_OUT = "p2p5-qwen3-0p6b-screen-v1", "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
MODEL_DIR, MODEL_REVISION = "/root/models/qwen3-0.6b-base", "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"
GPU, CPU_CORES, MEMORY_GIB, MAX_STARTS, C, EARLY_S = "A100-80GB", 8.0, 64, 4, 50, 120
FUNCTION_MAX_S = 86400                                     # Modal per-call timeout ceiling
EVAL = {"final_batches": 16, "final_batch_size": 16, "final_seed_base": 9_300_011, "dev_seed": 4242,
        "train_eval_seed_base": 555_001}
SLOT = os.environ.get("M4_PK_SLOT", "")
SLOTS = ("learned-n16", "learned-n32", "single_cell-n16", "single_cell-n32", "random_fixed-n16", "random_fixed-n32",
         "oracle-n32", "memory_off-n16", "memory_off-n32")
if SLOT not in SLOTS:
    raise SystemExit(f"M4_PK_SLOT must be one of {SLOTS}, got {SLOT!r}")
APP_NAME = f"memsub-m4-sgm-p2p5-pk-campaign-{SLOT.replace('_', '')}"
GUARD_DICT, ADMIT_DICT = f"{APP_NAME}-guard", f"{APP_NAME}-admission"


def _build_environment():
    import subprocess as sp
    sp.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "torch==2.7.1",
            "--index-url", "https://download.pytorch.org/whl/cu126"], check=True)
    sp.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "transformers==4.55.2",
            "safetensors==0.5.3", "numpy==2.2.6", "pytest==8.4.1"], check=True)
    from huggingface_hub import snapshot_download
    snapshot_download("Qwen/Qwen3-0.6B-Base", revision=MODEL_REVISION, local_dir=MODEL_DIR,
                      allow_patterns=["config.json", "generation_config.json", "model.safetensors"])


app = modal.App(APP_NAME)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("huggingface_hub==0.36.2")
         .run_function(_build_environment, timeout=1200, cpu=4.0, memory=8 * 1024)
         .env({"HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false", "M4_SGM_QWEN3_0P6B_DIR": MODEL_DIR,
               "M4_PK_SLOT": SLOT})
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_dir("configs", "/root/repo/configs")
         .add_local_file(PRICE_FILE, f"/root/repo/{PRICE_FILE}"))
artifacts = modal.Volume.from_name("memsub-artifacts")


def file_sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def slot_cells(grid: dict) -> dict:
    for root in ("/root/repo", str(Path(__file__).resolve().parents[1])):      # container / local checkout
        if root not in sys.path:
            sys.path.insert(0, root)
    from memsub.sgm.packed_slot_supervisor import expand_cells
    arm, n = SLOT.rsplit("-n", 1)
    cells = {c: p for c, p in expand_cells(grid).items() if p["arm"] == arm and p["n_bindings"] == int(n)}
    if sorted(p["seed"] for p in cells.values()) != [0, 1]:
        raise SystemExit(f"slot {SLOT}: registered pairing differs from seeds 0+1")
    return cells


def slot_deadline_s() -> float:
    """This slot's charged lifetime = its PK6 reserve life (seconds), from the bound price file."""
    price = json.loads(Path(PRICE_FILE).read_text())
    return float(price["slots"][SLOT]["reserve_life_s"])


def admit(adm, guard, now: float) -> tuple[int | None, str | None]:
    import math
    deadline = guard.get("deadline_epoch", None)
    if not (isinstance(deadline, (int, float)) and not isinstance(deadline, bool) and math.isfinite(deadline)
            and deadline > 0) or now > deadline:                     # finite positive only (codex 21600 #4)
        return None, "past the slot deadline (or deadline unset / non-finite)"
    for n in range(1, MAX_STARTS + 1):
        if adm.put(f"start-{n}", now, skip_if_exists=True):
            return n, None
    return None, "start allowance exhausted"


def identity_now(root: str = "/root/repo") -> dict:
    sys.path.insert(0, root)
    import platform
    import torch
    import transformers
    from memsub.sgm.pinned_pretrained_qwen3_backbone import QWEN3_0P6B_BASE
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    return {"runner": file_sha(__file__), "memsub": source_tree_sha256(Path(root) / "memsub"), "slot": SLOT,
            "grid": file_sha(Path(root) / GRID_FILE), "registry": file_sha(Path(root) / REGISTRY_FILE),
            "schema": file_sha(Path(root) / SCHEMA_FILE), "price": file_sha(Path(root) / PRICE_FILE),
            "env": {"python": platform.python_version(), "torch": torch.__version__, "cuda": torch.version.cuda,
                    "transformers": transformers.__version__, "tf32_matmul": torch.backends.cuda.matmul.allow_tf32},
            "model": QWEN3_0P6B_BASE}


@app.function(image=image, gpu=GPU, cpu=(CPU_CORES, CPU_CORES), memory=(MEMORY_GIB * 1024, MEMORY_GIB * 1024),
              timeout=FUNCTION_MAX_S, startup_timeout=300, max_containers=1, single_use_containers=True,
              retries=modal.Retries(max_retries=MAX_STARTS - 1, initial_delay=1.0, backoff_coefficient=1.0),
              volumes={"/artifacts": artifacts})
def run_slot(expected: dict) -> dict:
    sys.path.insert(0, "/root/repo")
    from memsub.sgm.p2d_launch_guard import Watchdog
    early = Watchdog(EARLY_S)
    try:
        adm = modal.Dict.from_name(ADMIT_DICT, create_if_missing=True)
        guard = modal.Dict.from_name(GUARD_DICT, create_if_missing=True)
        epoch, why = admit(adm, guard, time.time())
        admitted = [n for n in range(1, MAX_STARTS + 1) if adm.contains(f"start-{n}")]
        deadline = guard.get("deadline_epoch", None)
    except Exception as e:
        epoch, why, admitted, deadline = None, f"admission error {e!r:.200}", [], None
    finally:
        early.cancel()
    if epoch is None:
        return {"slot": SLOT, "status": "admission_refused", "reason": why}
    life = Watchdog(max(1.0, deadline - time.time()))           # SIGKILL at the slot's absolute deadline
    try:
        got = identity_now()
        if {k: got[k] for k in expected} != expected:
            return {"slot": SLOT, "status": "identity_mismatch", "epoch": epoch, "got": got}
        from memsub.sgm.packed_slot_supervisor import SlotSupervisor
        grid = json.loads(Path("/root/repo", GRID_FILE).read_text())
        cells = slot_cells(grid)
        arm = next(iter(cells.values()))["arm"]
        registry = json.loads(Path("/root/repo", REGISTRY_FILE).read_text())["by_arm"][arm]
        schema = json.loads(Path("/root/repo", SCHEMA_FILE).read_text())["by_arm"][arm]
        artifacts.reload()
        sup = SlotSupervisor(root=Path("/artifacts/m4-sgm") / GROUP / SLOT, cells=cells, epoch=epoch,
                             admitted=admitted, identity={**got, "runner_expected": expected}, checkpoint_every=C,
                             eval_cfg=EVAL, commit=artifacts.commit, reload=artifacts.reload,
                             newer_start=lambda: adm.contains(f"start-{epoch + 1}"), ack_timeout_s=900,
                             provenance={"container_id": os.environ.get("MODAL_TASK_ID"), "admitted_at": time.time()},
                             registry=registry, schema=schema)
        res = sup.run()
        artifacts.commit()
        return {"slot": SLOT, "status": "slot_done", "epoch": epoch, **res}
    finally:
        life.cancel()


# ---------------- local side ----------------

def expected_identity() -> dict:
    sys.path.insert(0, str(Path.cwd()))
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    return {"runner": file_sha(__file__), "memsub": source_tree_sha256(Path("memsub")), "slot": SLOT,
            "grid": file_sha(GRID_FILE), "registry": file_sha(REGISTRY_FILE), "schema": file_sha(SCHEMA_FILE),
            "price": file_sha(PRICE_FILE)}


def controller_preflight(cp, control: dict, now_deadline: float, live_id, live_state) -> str | None:
    """None iff the control plane is completely bound and live (codex 21604 #3): write-once app id + finite
    deadline + price sha in its guard; the live controller app id equals the bound id and is not stopped; the
    price sha equals this runner's bound price; this slot's deadline leaves the validation/readings/slack window
    before the controller deadline. Read-only; runs before any slot state is consumed."""
    import hashlib
    if not (isinstance(control.get("app_id"), str) and control["app_id"] and cp.finite_pos(control.get("deadline_epoch"))
            and isinstance(control.get("price_sha256"), str)):
        return f"controller binding incomplete: {sorted(control)}"
    if control["price_sha256"] != hashlib.sha256(Path(PRICE_FILE).read_bytes()).hexdigest():
        return "controller was armed for a different price/horizon file"
    try:
        if live_id() != control["app_id"]:
            return "live controller app id differs from the bound id"
        if str(live_state(control["app_id"])).lower() in ("stopped", "stopping", "none", ""):
            return "controller app is not running"
    except Exception as e:
        return f"controller lookup failed: {e!r:.120}"
    readings = json.loads(Path(PRICE_FILE).read_text())["readings"]["reserve_life_s"]
    if now_deadline > control["deadline_epoch"] - VALIDATION_SETUP_S - readings - CONTROL_SLACK_S:
        return "slot deadline beyond the controller horizon"
    return None


def app_state(app_id: str) -> str:
    rows = json.loads(subprocess.run([sys.executable, "-m", "modal", "app", "list", "--json"], check=True,
                                     capture_output=True, text=True, timeout=30).stdout)
    mine = [r for r in rows if r.get("app_id") == app_id]
    return str(mine[0].get("state")) if mine else "none"


def spawn() -> None:
    tracked = ["memsub", __file__, GRID_FILE, REGISTRY_FILE, SCHEMA_FILE, PRICE_FILE]
    if subprocess.run(["git", "status", "--porcelain", "--", *tracked], capture_output=True, text=True,
                      check=True).stdout.strip():
        raise SystemExit("refusing to spawn from a dirty tree")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cp", Path(__file__).with_name("modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py"))
    cp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cp)
    now = time.time()
    candidate = now + slot_deadline_s()            # ONE immutable deadline for preflight/provenance/guard/register
    control = dict(modal.Dict.from_name(CONTROL_GUARD_DICT).items())          # READ-ONLY preflights first
    problem = controller_preflight(cp, control, now_deadline=candidate,
                                   live_id=lambda: modal.App.lookup(CONTROL_APP_NAME).app_id,
                                   live_state=lambda app_id: app_state(app_id))
    if problem:
        raise SystemExit(f"controller preflight failed: {problem}")
    guard = modal.Dict.from_name(GUARD_DICT, create_if_missing=True)
    if len(guard.keys()):
        raise SystemExit("guard Dict already used: this slot was spawned before")
    root = Path(LOCAL_OUT) / GROUP / SLOT
    root.mkdir(parents=True, exist_ok=False)
    prov = {"slot": SLOT, "expected_identity": expected_identity(), "spawn_epoch": now,
            "deadline_epoch": candidate, "app_name": APP_NAME,
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "deployed_app_id": modal.App.lookup(APP_NAME).app_id}
    (root / "launch_provenance.json").write_text(json.dumps(prov, indent=2))
    if not (guard.put("app_id", prov["deployed_app_id"], skip_if_exists=True)
            and guard.put("deadline_epoch", prov["deadline_epoch"], skip_if_exists=True)):
        raise SystemExit("guard app id / deadline already set")
    if not cp.register(modal.Dict.from_name(CONTROL_REGISTRY_DICT, create_if_missing=True), APP_NAME,
                       prov["deployed_app_id"], prov["deadline_epoch"], horizon=control["deadline_epoch"]):
        raise SystemExit("slot already registered with the control-plane reaper")
    call = modal.Function.from_name(APP_NAME, "run_slot").spawn(prov["expected_identity"]).object_id
    (root / "call.json").write_text(json.dumps({"call_id": call}))
    print("spawned", SLOT, call)


COLLECT_GRACE_S = 300


def cell_report(cell_dir: Path, pilot: dict, admitted: list[int], memsub_sha: str, registry: dict, schema: dict,
                terminal: bool, validate=None) -> dict:
    """Authoritative state of one cell from the fetched evidence: the highest ADMITTED epoch with an acknowledged
    record, its canonical snapshot chain, and (COMPLETE) the shared per-cell output validation. A cell that is
    not terminal when its slot is terminal / past deadline is reported LOST (never resumed, never relabelled)."""
    from memsub.sgm import packed_slot_epoch_state as es
    from memsub.sgm.packed_slot_cell_output_validation import validate_cell_outputs
    validate = validate or validate_cell_outputs
    epochs = sorted(int(p.name.split("-")[1]) for p in cell_dir.glob("epoch-*")) if cell_dir.exists() else []
    if any(m not in admitted for m in epochs):
        return {"state": "INVALID", "problem": f"epoch dirs {epochs} not all admitted {admitted}"}
    rec = next((r for m in reversed(epochs) if (r := es.read_record(cell_dir, m)) is not None), None)
    if rec is None:
        return {"state": "LOST" if terminal else "NOT_STARTED", "problem": "no acknowledged record"}
    try:
        walk = es.canonical_walk(rec, max_len=len(admitted))
    except ValueError as e:
        return {"state": "INVALID", "problem": str(e)}
    out = {"state": rec["state"], "epoch": rec["epoch"], "epochs": [w["epoch"] for w in walk],
           "reason": rec.get("reason")}
    if rec["state"] == es.COMPLETE:
        problem = validate(cell_dir.parents[1] / rec["outputs"]["attempt"] / "out", rec["outputs"]["files"], pilot,
                           EVAL, memsub_sha, registry, schema)
        out["validation"] = problem or "valid"
    elif rec["state"] not in (es.FAILED, es.LOST) and terminal:
        out.update(state="LOST", problem=f"not terminal ({rec['state']}) when the slot ended")
    return out


def collect(poller=None, stopper=None, verifier=None, fetch=None, export=None, now=None, validate=None) -> dict:
    """Idempotent. Stops + verifies THIS slot's app by its spawn-time bound id when the call is terminal, untracked
    or past the deadline (+grace); then pulls the slot's volume evidence, exports its guard/admission Dicts and
    reports every cell (COMPLETE validated / FAILED / LOST / INVALID). Without launch provenance it refuses:
    there is no bound id, and a name-only stop is never allowed."""
    root = Path(LOCAL_OUT) / GROUP / SLOT
    try:
        prov = json.loads((root / "launch_provenance.json").read_text())
    except (OSError, ValueError):
        raise SystemExit(f"{SLOT}: no launch provenance: refusing (no bound app id; no name-only stop)")
    try:
        call = json.loads((root / "call.json").read_text())["call_id"]
    except (OSError, ValueError, KeyError):
        call = None
    kind, payload = (poller(call) if call else ("untracked", None))
    past = (now if now is not None else time.time()) > prov["deadline_epoch"] + COLLECT_GRACE_S
    report = {"slot": SLOT, "call_id": call, "poll": kind, "result": payload, "past_deadline": past}
    if kind not in ("pending", "untracked") or past or call is None:
        sd = {"app_id": prov["deployed_app_id"]}
        try:
            stopper(APP_NAME, prov["deployed_app_id"])
        except Exception as e:
            sd["stop_error"] = repr(e)[:200]
        try:
            sd["verified"] = bool(verifier(APP_NAME, prov["deployed_app_id"]))
        except Exception as e:
            sd["verified"], sd["verify_error"] = False, repr(e)[:200]
        sd["status"] = "stopped_verified" if sd["verified"] else "shutdown_unresolved"
        report["final_shutdown"] = sd
        report["evidence"] = fetch(root)
        dicts = export(root)
        report["dicts"] = {k: (len(v) if isinstance(v, dict) else v) for k, v in dicts.items()}
        admitted = sorted(int(k.split("-")[1]) for k in (dicts.get("admission") or {}) if k.startswith("start-"))
        reg = json.loads(Path(REGISTRY_FILE).read_text())["by_arm"]
        sch = json.loads(Path(SCHEMA_FILE).read_text())["by_arm"]
        ev = root / "volume-evidence" / SLOT / "cells"
        report["cells"] = {c: cell_report(ev / c, p, admitted, prov["expected_identity"]["memsub"], reg[p["arm"]],
                                          sch[p["arm"]], terminal=True, validate=validate)
                           for c, p in slot_cells(json.loads(Path(GRID_FILE).read_text())).items()}
    tmp = root / "collect_status.json.tmp"
    tmp.write_text(json.dumps(report, indent=2, default=str))
    os.replace(tmp, root / "collect_status.json")
    print(json.dumps({"slot": SLOT, "poll": kind, "final": "final_shutdown" in report}))
    return report


def _real_collect():
    import importlib.util
    here = Path(__file__).resolve().parent

    def load(name, mod):
        spec = importlib.util.spec_from_file_location(mod, here / name)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    tu = load("modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py", "topup")
    shared = load("modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py", "shared")

    def verifier(name, app_id):
        return app_state(app_id).lower() in ("stopped", "none")

    def fetch(root):
        dest = root / "volume-evidence"
        dest.mkdir(exist_ok=True)
        g = subprocess.run([sys.executable, "-m", "modal", "volume", "get", "--force", "memsub-artifacts",
                            f"m4-sgm/{GROUP}/{SLOT}", str(dest)], capture_output=True, text=True, timeout=1800)
        return {"returncode": g.returncode, "stderr_tail": g.stderr[-500:]}

    def export(root):
        out = {}
        for key, name in (("guard", GUARD_DICT), ("admission", ADMIT_DICT)):
            d = dict(modal.Dict.from_name(name).items())
            (root / f"{key}.json").write_text(json.dumps(d, indent=2, default=str))
            out[key] = d
        return out
    return collect(poller=tu.poll, stopper=lambda n, i: shared.stop_bound_app(n, i, "main"), verifier=verifier,
                   fetch=fetch, export=export)


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    {"plan": lambda: print(json.dumps({"slot": SLOT, "app": APP_NAME, "deadline_s": slot_deadline_s()})),
     "spawn": spawn, "collect": _real_collect}[sys.argv[1]]()
