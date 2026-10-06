"""M4-SGM P2.5 Amendment PK §PK5 — PROOF runner (real slot supervisor / resume consumer on A100-80GB).

DEV proof only (seeds 99/100, proof populations 8_800_*; configs/m4_sgm_p2p5_packed_proof_grid.json).
Needs its own user approval of the reservation printed by `plan`; nothing here is a campaign cell.

    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-pk-packed-slot-proof-runner.py plan
    .venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2p5-pk-packed-slot-proof-runner.py
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-pk-packed-slot-proof-runner.py spawn
    .venv/bin/python modal-runners/modal-m4-sgm-p2p5-pk-packed-slot-proof-runner.py collect   # idempotent

Lifecycle (as the accepted v1/v2 profile runners): one deploy, one spawn of 7 unit calls (6 scenario
slots + timing) into ONE GPU function with max_containers=1 (codex 21567 #1): at most one A100
container exists at any time, units run serially, platform retries re-queue. App-level deadline in a
guard Dict; an in-app scheduled reaper stops the WHOLE app past the deadline (shared stop-first
logic); local collect stops + verifies by app id and exports the admission/guard Dicts. The charge
bound is therefore 1 container x (app lifetime + reaper period + stop latency): pre-admission crash
loops, refused starts, startups and teardown all fall inside it.
Admission (PK3): every container start of a scenario atomically claims `<scenario>-start-<n>`
(n <= MAX_STARTS[scenario]) in the admission Dict; none left or past the deadline -> the call
returns (completes) without work. Faults apply to admitted start 1 only; a ContainerFault is
re-raised as an ordinary exception so the platform retry policy restarts the container into
admission (B/C/D: 2 starts = fault + resume; A/A'/E: 1 start — an interruption fails the proof).
"""

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import modal

APP_NAME, GROUP = "memsub-m4-sgm-p2p5-pk-proof", "p2p5-pk-proof-v1"
GRID_FILE = "configs/m4_sgm_p2p5_packed_proof_grid.json"
REGISTRY_FILE = "configs/m4_sgm_p2p5_packed_proof_registry.json"
SCHEMA_FILE = "configs/m4_sgm_p2p5_packed_proof_output_schema.json"
COMPARATOR = "scripts/sgm-p2p5-pk-packed-proof-acceptance-compare.py"
TIMING_SCRIPT = "scripts/sgm-p2p5-pk-packed-slot-timing-profile.py"
PACKING_HELPERS = "scripts/sgm-p2p5-gpu-packing-concurrent-training-throughput-test.py"
LOGIC_FILE = "modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py"
LOCAL_OUT = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
MODEL_DIR, MODEL_REVISION = "/root/models/qwen3-0.6b-base", "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"
GPU, CPU_CORES, MEMORY_GIB = "A100-80GB", 8.0, 64
MAX_STARTS = {"A": 1, "Aprime": 1, "E": 1, "B": 2, "C": 2, "D": 2}
UNIT_TIMEOUT_S, STARTUP_TIMEOUT_S = 2400, 300          # one function serves slot units and the timing unit
EXPECTED_WALL_S = 78 * 60                                # serial: 9 slot starts ~5.5 min + timing ~28.5 min
OVERALL_S, REAPER_PERIOD_S, STOP_LATENCY_S, ABANDON_S, EARLY_S = 6600, 120, 120, 1800, 120   # ~1.4x expected
GUARD_DICT, ADMIT_DICT = "m4-sgm-p2p5-pk-proof-v1-guard", "m4-sgm-p2p5-pk-proof-v1-admission"
GPU_USD_S, CPU_USD_CORE_S, MEM_USD_GIB_S = 0.000694, 0.0000131, 0.00000222    # modal.com/pricing 2026-10-06
CPU_RAM_BASIS, IMAGE_RESERVE_USD, FIXED_MARGIN_USD = 2.0, 0.168384, 0.25
ENVIRONMENT = "main"
ACK_TIMEOUT_S = 300


def _build_environment():
    """Same pinned stack and weights as the P2.5 profile / dev runners."""
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
         .env({"HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false", "M4_SGM_QWEN3_0P6B_DIR": MODEL_DIR})
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_dir("scripts", "/root/repo/scripts", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_dir("configs", "/root/repo/configs")
         .add_local_file(f"modal-runners/{LOGIC_FILE}", f"/root/{LOGIC_FILE}"))
reaper_image = modal.Image.debian_slim(python_version="3.12").add_local_file(f"modal-runners/{LOGIC_FILE}",
                                                                             f"/root/{LOGIC_FILE}")
artifacts = modal.Volume.from_name("memsub-artifacts")
RESOURCES = dict(gpu=GPU, cpu=(CPU_CORES, CPU_CORES), memory=(MEMORY_GIB * 1024, MEMORY_GIB * 1024),
                 volumes={"/artifacts": artifacts})


def file_sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


_LOGIC = None


def logic():
    global _LOGIC
    if _LOGIC is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("pk_reaper_logic", Path(__file__).with_name(LOGIC_FILE))
        _LOGIC = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_LOGIC)
    return _LOGIC


def admit(adm, guard, scenario: str, now: float, cap: int) -> tuple[int | None, str | None]:
    """(epoch, None) for an admitted start, else (None, reason). Pure on Dict-like stores."""
    deadline = guard.get("deadline_epoch", None)
    if not isinstance(deadline, (int, float)) or now > deadline:
        return None, "past the overall deadline (or deadline unset)"
    for n in range(1, cap + 1):
        if adm.put(f"{scenario}-start-{n}", now, skip_if_exists=True):
            return n, None
    return None, "start allowance exhausted"


def identity_now(root: str = "/root/repo") -> dict:
    sys.path.insert(0, root)
    import torch
    import transformers
    from memsub.sgm.pinned_pretrained_qwen3_backbone import QWEN3_0P6B_BASE
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    import platform
    return {"runner": file_sha(__file__), "memsub": source_tree_sha256(Path(root) / "memsub"),
            "grid": file_sha(Path(root) / GRID_FILE),
            "timing_script": file_sha(Path(root) / TIMING_SCRIPT),
            "packing_helpers": file_sha(Path(root) / PACKING_HELPERS),
            "registry": file_sha(Path(root) / REGISTRY_FILE), "comparator": file_sha(Path(root) / COMPARATOR),
            "schema": file_sha(Path(root) / SCHEMA_FILE),
            "reaper_logic": file_sha(Path(__file__).with_name(LOGIC_FILE)),
            "env": {"python": platform.python_version(), "torch": torch.__version__, "cuda": torch.version.cuda,
                    "transformers": transformers.__version__, "tf32_matmul": torch.backends.cuda.matmul.allow_tf32},
            "model": QWEN3_0P6B_BASE}


@app.function(image=reaper_image, schedule=modal.Period(seconds=REAPER_PERIOD_S), cpu=0.125, memory=256,
              timeout=110, max_containers=1, retries=0)
def reaper() -> dict:
    return logic().reap_and_stop(modal.Dict.from_name(GUARD_DICT, create_if_missing=True), time.time(), APP_NAME,
                                 lambda name, app_id: logic().stop_bound_app(name, app_id, ENVIRONMENT),
                                 None, ABANDON_S)


@app.function(image=image, timeout=UNIT_TIMEOUT_S, startup_timeout=STARTUP_TIMEOUT_S, max_containers=1,
              single_use_containers=True,          # a restart is always a FRESH container (codex 21553 #4)
              retries=modal.Retries(max_retries=1, initial_delay=1.0, backoff_coefficient=1.0), **RESOURCES)
def run_unit(unit: str, expected: dict) -> dict:
    """One proof unit: a scenario slot start (A, Aprime, B, C, D, E) or the timing profile."""
    return _timing(expected) if unit == "timing" else _slot(unit, expected)


def _admitted_start(unit: str, cap: int):
    sys.path.insert(0, "/root/repo")
    from memsub.sgm.p2d_launch_guard import Watchdog
    early = Watchdog(EARLY_S)
    try:
        adm = modal.Dict.from_name(ADMIT_DICT, create_if_missing=True)
        guard = modal.Dict.from_name(GUARD_DICT, create_if_missing=True)
        epoch, why = admit(adm, guard, unit, time.time(), cap)
        admitted = [n for n in range(1, cap + 1) if adm.contains(f"{unit}-start-{n}")]
    except Exception as e:
        adm, epoch, why, admitted = None, None, f"admission error {e!r:.200}", []
    finally:
        early.cancel()
    return adm, epoch, why, admitted


def _slot(scenario: str, expected: dict) -> dict:
    adm, epoch, why, admitted = _admitted_start(scenario, MAX_STARTS[scenario])
    if epoch is None:
        return {"unit": scenario, "status": "admission_refused", "reason": why}
    got = identity_now()
    if {k: got[k] for k in expected} != expected:
        return {"unit": scenario, "status": "identity_mismatch", "epoch": epoch, "got": got}
    from memsub.sgm.packed_slot_supervisor import ContainerFault, SlotSupervisor, expand_cells
    grid = json.loads(Path("/root/repo", GRID_FILE).read_text())
    registry = json.loads(Path("/root/repo", REGISTRY_FILE).read_text())
    schema = json.loads(Path("/root/repo", SCHEMA_FILE).read_text())
    spec, cells_all = grid["scenarios"][scenario], expand_cells(grid)
    cells = {c: cells_all[c] for c in spec["cells"]}
    arms = {p["arm"] for p in cells.values()}
    if len(arms) != 1:
        return {"unit": scenario, "status": "refused", "reason": "a slot holds one arm"}
    arm = arms.pop()
    artifacts.reload()
    sup = SlotSupervisor(root=Path("/artifacts/m4-sgm") / GROUP / scenario, cells=cells, epoch=epoch,
                         admitted=admitted, identity={**got, "runner_expected": expected},
                         checkpoint_every=grid["checkpoint_every"], eval_cfg=grid["eval"],
                         commit=artifacts.commit, reload=artifacts.reload,
                         newer_start=lambda: adm.contains(f"{scenario}-start-{epoch + 1}"),
                         ack_timeout_s=ACK_TIMEOUT_S, proof_capture=True,
                         faults=spec["faults"] if epoch == 1 else None,
                         provenance={"container_id": os.environ.get("MODAL_TASK_ID"), "admitted_at": time.time()},
                         registry=registry["by_arm"][arm], schema=schema["by_arm"][arm])
    try:
        res = sup.run()
    except ContainerFault as e:                                  # proof fault -> platform restart (fresh container)
        artifacts.commit()
        raise RuntimeError(f"proof container fault {e.code} (scenario {scenario}, epoch {epoch})")
    artifacts.commit()
    return {"unit": scenario, "status": "slot_done", "epoch": epoch, **res}


def _timing(expected: dict) -> dict:
    _adm, epoch, why, _admitted = _admitted_start("timing", 1)
    if epoch is None:
        return {"unit": "timing", "status": "admission_refused", "reason": why}
    got = identity_now()
    if {k: got[k] for k in expected} != expected:
        return {"unit": "timing", "status": "identity_mismatch", "got": got}
    out = Path("/artifacts/m4-sgm") / GROUP / "timing"
    try:
        proc = subprocess.run([sys.executable, "-u", f"/root/repo/{TIMING_SCRIPT}", "--out", str(out)],
                              cwd="/root/repo", capture_output=True, text=True, timeout=UNIT_TIMEOUT_S - 120)
        rc, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        rc, stdout, stderr = "outer_timeout", str(e.stdout or ""), str(e.stderr or "")
    commit_s, nbytes = [], None
    if rc == 0:                                                   # commit cost of one REAL generation size
        nbytes = max(w["checkpoint_bytes"] for c in json.loads((out / "timing.json").read_text())["configs"]
                     for w in c["eval_and_checkpoint"])
        for i in range(3):
            (out / f"commit-probe-{i}.bin").write_bytes(os.urandom(nbytes))
            t0 = time.monotonic()
            artifacts.commit()
            commit_s.append(time.monotonic() - t0)
    (out.parent / "timing.exit.json").write_text(json.dumps({"child_exit": rc, "commit_s": commit_s,
                                                             "commit_probe_bytes": nbytes,
                                                             "stdout_tail": stdout[-4000:],
                                                             "stderr_tail": stderr[-4000:]}, indent=2))
    artifacts.commit()
    return {"unit": "timing", "status": "timed" if rc == 0 else "timing_failed", "child_exit": rc,
            "commit_s": commit_s}


# ---------------- local side ----------------

def rate(basis: float) -> float:
    return GPU_USD_S + basis * (CPU_CORES * CPU_USD_CORE_S + MEMORY_GIB * MEM_USD_GIB_S)


def charge_bound() -> dict:
    """TRUE lifecycle bound under the whole-app reaper (codex 21564/21567 #1): one GPU container at a
    time (max_containers=1 on the only GPU function) for at most the app lifetime + one reaper period +
    stop latency, at A100-80GB list price + CPU/RAM on the 2x basis; plus reaper ticks (until the app
    stop, or the abandoned-deploy stop), the image-build reserve and a fixed margin. Assumptions, not a
    platform cash ceiling: reaper period/stop latency are nominal scheduling allowances; CPU/RAM billing
    beyond the 2x basis is not covered; list prices as checked."""
    life_s = OVERALL_S + REAPER_PERIOD_S + STOP_LATENCY_S
    reaper_ticks = math.ceil((ABANDON_S + life_s) / REAPER_PERIOD_S)
    parts = {"gpu_container_lifetime_usd": life_s * rate(CPU_RAM_BASIS),
             "reaper_usd": reaper_ticks * 110 * (0.125 * CPU_USD_CORE_S + 0.25 * MEM_USD_GIB_S),
             "image_reserve_usd": IMAGE_RESERVE_USD, "fixed_margin_usd": FIXED_MARGIN_USD}
    return {**parts, "reserved_total_usd": sum(parts.values()),
            "expected_usd_hard_tuples": EXPECTED_WALL_S * rate(1.0),
            "expected_usd_2x_basis": EXPECTED_WALL_S * rate(CPU_RAM_BASIS),
            "max_concurrent_gpu_containers": 1, "app_lifetime_s": OVERALL_S, "expected_serial_wall_s": EXPECTED_WALL_S,
            "max_starts": MAX_STARTS, "unit_timeout_s": UNIT_TIMEOUT_S, "startup_timeout_s": STARTUP_TIMEOUT_S,
            "usd_per_container_hour_2x": rate(CPU_RAM_BASIS) * 3600,
            "assumptions": ["the in-app reaper stops the whole app within one period + stop latency of the deadline",
                            "CPU/RAM requests charged at 2x (audited conservative basis); not a platform cash ceiling",
                            "list prices modal.com/pricing 2026-10-06",
                            "expected wall: 9 slot starts x ~5.5 min + timing ~28.5 min (packing/profile timings)"]}


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def expected_identity() -> dict:
    sys.path.insert(0, str(Path.cwd()))
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    return {"runner": file_sha(__file__), "memsub": source_tree_sha256(Path("memsub")), "grid": file_sha(GRID_FILE),
            "timing_script": file_sha(TIMING_SCRIPT), "packing_helpers": file_sha(PACKING_HELPERS),
            "registry": file_sha(REGISTRY_FILE), "comparator": file_sha(COMPARATOR), "schema": file_sha(SCHEMA_FILE),
            "reaper_logic": file_sha(Path(__file__).with_name(LOGIC_FILE))}


def spawn() -> None:
    tracked = ["memsub", __file__, GRID_FILE, REGISTRY_FILE, SCHEMA_FILE, COMPARATOR, TIMING_SCRIPT, PACKING_HELPERS,
               f"modal-runners/{LOGIC_FILE}"]
    if subprocess.run(["git", "status", "--porcelain", "--", *tracked], capture_output=True, text=True,
                      check=True).stdout.strip():
        raise SystemExit("refusing to spawn from a dirty tree")
    guard = modal.Dict.from_name(GUARD_DICT, create_if_missing=True)
    if set(guard.keys()) - {"first_tick"}:
        raise SystemExit("guard Dict already used: the proof was spawned before")
    root = Path(LOCAL_OUT) / GROUP
    root.mkdir(parents=True, exist_ok=False)
    now = time.time()
    prov = {"expected_identity": expected_identity(), "ledger": charge_bound(), "spawn_epoch": now,
            "deadline_epoch": now + OVERALL_S, "runner_sha256": file_sha(__file__),
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "deployed_app_id": modal.App.lookup(APP_NAME).app_id}
    atomic_write(root / "launch_provenance.json", json.dumps(prov, indent=2))
    if not (guard.put("app_id", prov["deployed_app_id"], skip_if_exists=True)
            and guard.put("deadline_epoch", prov["deadline_epoch"], skip_if_exists=True)):
        raise SystemExit("guard app id / deadline already set")
    grid = json.loads(Path(GRID_FILE).read_text())
    unit_fn = modal.Function.from_name(APP_NAME, "run_unit")
    calls = {u: unit_fn.spawn(u, prov["expected_identity"]).object_id for u in [*grid["scenarios"], "timing"]}
    atomic_write(root / "calls.json", json.dumps(calls, indent=2))
    print("spawned", json.dumps(calls))


def collect(poller=None, stopper=None, fetch=None, now=None, export=None) -> dict:
    """Idempotent: polls every call; when all are terminal OR the deadline passed, stops + verifies
    the app by its spawn-time id and pulls the volume evidence."""
    import importlib.util

    def load(path, name):
        spec = importlib.util.spec_from_file_location(name, Path(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    root = Path(LOCAL_OUT) / GROUP
    prov = json.loads((root / "launch_provenance.json").read_text())
    if poller is None or stopper is None:          # real Modal helpers (shared poll / stop + verify)
        here = Path(__file__).resolve().parent
        tu = load(here / "modal-m4-sgm-p2d-topup-nonpreemptible-spawn.py", "topup")
        v1 = load(here / "modal-m4-sgm-p2d-diagnostics-grid.py", "v1")
        poller, stopper = poller or tu.poll, stopper or (lambda app_id: tu.shutdown(v1, app_id))
    try:
        calls = json.loads((root / "calls.json").read_text())
    except (OSError, ValueError):
        calls = {}
    polls = {k: poller(c) for k, c in calls.items()}
    past = (now or time.time()) > prov["deadline_epoch"] + 300
    report = {"polls": {k: {"kind": v[0], "payload": v[1]} for k, v in polls.items()}, "past_deadline": past}
    if (calls and all(v[0] != "pending" for v in polls.values())) or past or not calls:
        report["final_shutdown"] = stopper(prov["deployed_app_id"])
        report["evidence"] = (fetch or fetch_evidence)(root)
        report["dicts"] = (export or export_dicts)(root)
    atomic_write(root / "collect_status.json", json.dumps(report, indent=2, default=str))
    print(json.dumps({k: (v["kind"] if isinstance(v, dict) else v) for k, v in report["polls"].items()}),
          "final" if "final_shutdown" in report else "pending")
    return report


def export_dicts(root: Path) -> dict:
    """Admission + guard Dict contents (the comparator's admission binding)."""
    out = {}
    for name, fname in ((ADMIT_DICT, "admission.json"), (GUARD_DICT, "guard.json")):
        try:
            d = dict(modal.Dict.from_name(name).items())
            atomic_write(root / fname, json.dumps(d, indent=2, default=str))
            out[fname] = len(d)
        except Exception as e:
            out[fname] = f"export error {e!r:.200}"
    return out


def fetch_evidence(root: Path) -> dict:
    dest = root / "volume-evidence"
    dest.mkdir(exist_ok=True)
    got = subprocess.run([sys.executable, "-m", "modal", "volume", "get", "--force", "memsub-artifacts",
                          f"m4-sgm/{GROUP}", str(dest)], capture_output=True, text=True, timeout=900)
    return {"returncode": got.returncode, "stderr_tail": got.stderr[-500:]}


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    {"plan": lambda: print(json.dumps(charge_bound(), indent=2)), "spawn": spawn, "collect": collect}[sys.argv[1]]()
