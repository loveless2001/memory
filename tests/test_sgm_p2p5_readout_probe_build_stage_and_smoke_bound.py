"""Readout probe: the runner imports from the files each Modal stage REALLY has (codex 21782/21786), and the local
smoke runs only under its outer process-group KILL bound (codex 21783/21786).

Stage files are read from the pinned SDK's own lazy objects (Modal 1.5.1; no RPC, no build), with the runner imported
the way `modal deploy <file>` imports it:
- builder = its FunctionInfo entrypoint mount + the COPY context mounts of the layers BEFORE it. Deferred
  (final-image) mounts never count for the builder.
- runtime = the function's entrypoint mount + every COPY layer + every deferred mount of its image.
Each set is materialised into an empty root and the runner is imported there in a fresh interpreter, as the container
does (module = file stem, /root on sys.path).
"""

import ast
import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from modal._utils.async_utils import synchronizer
from modal.cli.import_refs import ImportRef, import_file_or_module

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py"
SLOT_LOGIC = "/root/modal-m4-sgm-p2p5-readout-probe-slot-logic.py"
SMOKE = ROOT / "scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py"


@pytest.fixture(scope="module")
def runner():
    saved = list(sys.path)
    try:
        yield import_file_or_module(ImportRef(str(RUNNER), use_module_mode=False))
    finally:
        sys.path[:] = saved
        sys.modules.pop(RUNNER.stem, None)


def layers(img) -> list:
    """Root-first [(kind, obj)]: 'copy' COPY context mount, 'build' run_function, 'mount' deferred mount, 'other'."""
    img, out = synchronizer._translate_in(img), []
    while img is not None:
        nl = inspect.getclosurevars(img._load).nonlocals
        if "base_image" in nl and "mount" in nl:                    # deferred (runtime-only) mount layer
            out.append(("mount", nl["mount"]))
            img = nl["base_image"]
            continue
        fn, ctx = nl.get("build_function"), nl.get("context_mount_function")
        out.append(("build", fn) if fn is not None else ("copy", ctx()) if ctx and ctx() else ("other", None))
        bases = list(nl.get("base_images", {}).values())
        img = bases[0] if bases else None
    return out[::-1]


def entries(mounts) -> dict:
    """remote path -> local source, for file and directory entries only (anything else fails closed)."""
    out = {}
    for m in mounts:
        for e in m._entries:
            local = Path(getattr(e, "local_file", None) or e.local_dir)
            assert type(e).__name__ in ("_MountFile", "_MountDir"), e
            out[str(e.remote_path)] = local if local.is_absolute() else ROOT / local
    return out


def import_from(files: dict, fs: Path) -> subprocess.CompletedProcess:
    for remote, local in files.items():
        dst = fs / remote.lstrip("/")
        dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree(local, dst, ignore=shutil.ignore_patterns("__pycache__")) if local.is_dir()
         else shutil.copyfile(local, dst))
    code = "import importlib, sys; sys.path.insert(0, sys.argv[1]); m = importlib.import_module(sys.argv[2]); print(m.L.SLOT)"
    return subprocess.run([sys.executable, "-I", "-c", code, str(fs / "root"), RUNNER.stem], cwd=fs / "root",
                          capture_output=True, text=True, timeout=300)


def test_builder_stage_imports_from_its_effective_files_only(runner, tmp_path):
    lay = layers(runner.image)
    i = [k for k, _ in lay].index("build")
    fn = lay[i][1]
    assert fn._info.raw_f is runner._build_environment and [k for k, _ in lay].count("build") == 1
    assert "mount" not in [k for k, _ in lay[:i]]                     # nothing deferred can precede a build step
    source = entries(fn._info.get_entrypoint_mount().values())
    assert source == {f"/root/{RUNNER.name}": RUNNER}                  # the SDK-declared builder source
    pre = entries(m for k, m in lay[:i] if k == "copy")
    assert pre == {SLOT_LOGIC: ROOT / "modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-logic.py"}
    final = entries(m for k, m in lay[i:] if k == "mount")
    assert SLOT_LOGIC not in final and not set(final) & set(source)   # final-image mounts never feed the builder
    ok = import_from({**source, **pre}, tmp_path / "builder")
    assert ok.returncode == 0 and ok.stdout.strip() == "taskhead-learned-n32", ok.stderr[-2000:]
    bare = import_from(source, tmp_path / "control")                   # negative control: source only
    assert bare.returncode != 0 and "FileNotFoundError" in bare.stderr and Path(SLOT_LOGIC).name in bare.stderr


@pytest.mark.parametrize("fn_name,img_name", [("run_slot", "image"), ("reaper", "reaper_image")])
def test_runtime_stages_import_from_their_effective_files(runner, tmp_path, fn_name, img_name):
    lay = layers(getattr(runner, img_name))
    info = synchronizer._translate_in(getattr(runner, fn_name))._info
    files = {**entries(m for k, m in lay if k in ("copy", "mount")), **entries(info.get_entrypoint_mount().values())}
    assert SLOT_LOGIC in files and f"/root/{RUNNER.name}" in files
    ok = import_from(files, tmp_path / fn_name)
    assert ok.returncode == 0 and ok.stdout.strip() == "taskhead-learned-n32", ok.stderr[-2000:]


# ---- bounded local smoke: definition and launch boundary (the smoke itself is never run by the tests) -------------

def load(path: Path, name: str):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


SM = load(SMOKE, "probe_smoke_t")
L = load(ROOT / "modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-logic.py", "probe_slot_logic_bs")


def test_smoke_is_exactly_twenty_updates_with_its_own_seed_and_populations():
    cell = L.probe_cells(json.loads((ROOT / L.GRID_FILE).read_text()))["taskhead-learned-n32-s0"]
    p = SM.smoke_pilot(L)
    assert p["steps"] == 20 and p["seed"] == 7 and p["readout"] == "taskhead" and p["n_bindings"] == 32
    assert {k for k in p if p[k] != cell[k]} <= set(SM.SMOKE_OVERRIDE) and len(p) == len(cell)
    assert all(start < p["steps"] for start, _ in p["filler_len_schedule"])
    assert SM.SMOKE_EVAL["final_seed_base"] not in (9_300_011, 9_600_011)
    assert SM.SMOKE_EVAL["dev_seed"] != L.EVAL["dev_seed"]
    assert SM.SMOKE_EVAL["train_eval_seed_base"] != L.EVAL["train_eval_seed_base"]


def test_smoke_launch_form_and_order():
    assert SM.OUTER_BOUND == ("timeout", "--signal=KILL", "3600") and SM.INNER_S < 3600
    cmd = "timeout --signal=KILL 3600 .venv-gpu/bin/python scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py --out"
    assert cmd in SM.__doc__ and "--kill-after" not in SMOKE.read_text()
    body = SMOKE.read_text().split("def main")[1]
    order = ["outer_bound_problem()", "mkdir(parents=True, exist_ok=False)", "Watchdog(INNER_S)",
             "synthetic_pilot_run", "ProbeSlotSupervisor("]
    assert [body.index(x) for x in order] == sorted(body.index(x) for x in order)
    top = [n for n in ast.parse(SMOKE.read_text()).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name for n in top if isinstance(n, ast.Import) for a in n.names} | {n.module for n in top
                                                                                  if isinstance(n, ast.ImportFrom)}
    assert names == {"argparse", "importlib.util", "json", "os", "sys", "time", "pathlib"}   # stdlib only before the check


def _run(argv, **kw):
    return subprocess.run(argv, capture_output=True, text=True, timeout=120, **kw)


CHECK = ("import importlib.util, sys; s = importlib.util.spec_from_file_location('sm', sys.argv[1]); "
         "m = importlib.util.module_from_spec(s); s.loader.exec_module(m); print(repr(m.outer_bound_problem()))")


def test_outer_bound_check_accepts_only_the_exact_timeout_parent():
    py = [sys.executable, "-I", "-c", CHECK, str(SMOKE)]
    assert _run(["timeout", "--signal=KILL", "3600", *py]).stdout.strip() == "None"
    for bad in ([], ["timeout", "--signal=KILL", "3599"], ["timeout", "3600"], ["timeout", "--signal=TERM", "3600"],
                ["timeout", "--foreground", "--signal=KILL", "3600"]):
        out = _run([*bad, *py]).stdout.strip()
        assert out != "None" and ("launch ONLY" in out or "process group" in out), (bad, out)
    left = [sys.executable, "-I", "-c", "import os; os.setpgid(0, 0); " + CHECK, str(SMOKE)]   # exact parent, own group
    assert "process group" in _run(["timeout", "--signal=KILL", "3600", *left]).stdout


def test_smoke_refuses_without_the_bound_before_creating_its_output(tmp_path):
    r = _run([sys.executable, str(SMOKE), "--out", str(tmp_path / "x")], cwd=ROOT)
    assert r.returncode != 0 and "refusing the smoke" in r.stderr and not (tmp_path / "x").exists()


TREE = """import os, subprocess, sys, time
open(sys.argv[1], "a").write(f"{os.getpid()} {os.getpgid(0)}\\n")
if int(sys.argv[2]) > 0:     # spawn like the supervisor spawns workers: plain Popen, no new session
    subprocess.Popen([sys.executable, "-I", "-c", sys.argv[3], sys.argv[1], str(int(sys.argv[2]) - 1), sys.argv[3]])
time.sleep(60)
"""


def _alive(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def test_outer_kill_bound_terminates_the_whole_process_tree(tmp_path):
    """The SAME launch form with a 2 s duration on a harmless 3-deep tree: every process is SIGKILLed with the group."""
    pids = tmp_path / "pids"
    t0 = time.time()
    r = _run([*SM.OUTER_BOUND[:2], "2", sys.executable, "-I", "-c", TREE, str(pids), "2", TREE])
    assert time.time() - t0 < 30 and r.returncode in (-9, 137)
    rows = [tuple(map(int, x.split())) for x in pids.read_text().splitlines()]
    assert len(rows) == 3 and len({g for _, g in rows}) == 1             # one group: the timeout's
    deadline = time.time() + 10
    while any(_alive(p) for p, _ in rows) and time.time() < deadline:
        time.sleep(0.1)
    assert not any(_alive(p) for p, _ in rows)


def test_supervisor_spawns_workers_inside_the_group():
    tree = ast.parse((ROOT / "memsub/sgm/packed_slot_supervisor.py").read_text())
    pops = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and ast.unparse(n.func) == "subprocess.Popen"]
    assert len(pops) == 1
    assert not {k.arg for k in pops[0].keywords} & {"start_new_session", "process_group", "preexec_fn"}
    assert "PR_SET_PDEATHSIG" in (ROOT / "memsub/sgm/packed_slot_worker.py").read_text()
