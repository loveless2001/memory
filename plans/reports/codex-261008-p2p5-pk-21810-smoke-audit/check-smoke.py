"""Independent retained-smoke audit: CPU construction/read-only checks; no forward pass or remote action."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PLAN = ROOT / "plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe"
SMOKE = PLAN / "smoke"
RUN = SMOKE / "run-20261008T0511Z"
CELL = "smoke-taskhead-learned-n32-s7"
CDIR = RUN / "slot/cells" / CELL
ATT = CDIR / "epoch-1/attempt-1"
sys.path.insert(0, str(ROOT))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read(p):
    return json.loads(p.read_text())


hashes = {}
for manifest, count in [("SHA256SUMS-smoke.txt", 24), ("SHA256SUMS-smoke-excluded-binaries-not-in-git.txt", 3)]:
    entries = [line.split(maxsplit=1) for line in (SMOKE / manifest).read_text().splitlines()]
    assert len(entries) == count
    for expected, rel in entries:
        actual = sha(SMOKE / rel)
        assert actual == expected, rel
        hashes[rel] = actual

launch = read(SMOKE / "run-20261008T0511Z.launch-identity.json")
assert launch["git_head"] == "30e2b3ecd879f883263b9852b2a89b37c2f61682"
assert launch["tracked_dirty"] == "" and Path(launch["cwd"]) == ROOT
assert launch["argv"] == ["timeout", "--signal=KILL", "3600", ".venv-gpu/bin/python",
                          "scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py", "--out", str(RUN.relative_to(ROOT))]
assert all(sha(ROOT / rel) == h for rel, h in launch["files_sha256"].items())
assert not subprocess.check_output(["git", "diff", "30e2b3e", "HEAD", "--", "memsub", "scripts", "configs",
                                    "modal-runners", "tests"], cwd=ROOT)
for line in (PLAN / "implementation-r2/SHA256SUMS-implementation-package-r2.txt").read_text().splitlines():
    h, rel = line.split(maxsplit=1)
    assert sha(ROOT / rel) == h

import torch
torch.set_num_threads(2)
from memsub.sgm import packed_slot_epoch_state as es
from memsub.sgm.pinned_pretrained_qwen3_backbone import verify_files
from memsub.sgm.synthetic_pilot import PilotConfig, build
from memsub.sgm.synthetic_pilot_run import source_tree_sha256
from safetensors.torch import load_file

L = load("modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-logic.py", "audit_smoke_logic")
PV = load(L.VALIDATOR_FILE, "audit_smoke_validation")
SM = load("scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py", "audit_smoke_definition")
pilot = SM.smoke_pilot(L)
summary = read(RUN / "smoke-summary.json")
args = read(ATT / "worker-args.json")
assert summary["pilot"] == args["pilot_config"] == pilot
assert summary["eval"] == args["eval"] == SM.SMOKE_EVAL
assert summary["cell"] == args["cell"] == CELL and summary["state"] == "COMPLETE"
assert pilot["seed"] == 7 and pilot["batch"] == 2 and pilot["steps"] == 20 and pilot["device"] == "cuda"
assert args["resume_file"] is None and args["resume_step"] == 0 and args["checkpoint_every"] == 10
assert args["epoch"] == args["attempt"] == 1 and args["proof_capture"] is False and args["fault"] is None
assert len(list(CDIR.glob("epoch-*"))) == len(list((CDIR / "epoch-1").glob("attempt-*"))) == 1
memsub = source_tree_sha256(ROOT / "memsub")
assert memsub == launch["memsub_tree_sha256"]
rec = es.read_record(CDIR, 1)
assert rec["state"] == "COMPLETE" and rec["recovery"] == "fresh" and rec.get("reason") is None
assert rec["history"] == [] and rec["unacknowledged_epochs"] == [] and len(es.canonical_walk(rec, 1)) == 1
assert rec["identity"]["memsub"] == memsub and rec["steps"] == 20
assert [(x["g"], x["step"]) for x in rec["chain"]] == [(1, 10), (2, 20)]
assert es.verify_chain(CDIR, rec["chain"]) is None
done = read(ATT / "done.json")["outputs"]
assert done == rec["outputs"]["files"] and len(done) == 7
assert RUN / "slot" / rec["outputs"]["attempt"] == ATT
registry = read(ROOT / L.REGISTRY_FILE)["learned"]
schema = read(ROOT / L.SCHEMA_FILE)["learned"]
problem = PV.validate_probe_outputs(ATT / "out", done, pilot, SM.SMOKE_EVAL, memsub, registry, schema)
assert problem is None, problem
updates = [json.loads(line) for line in (ATT / "physical-updates.jsonl").read_text().splitlines()]
assert [r["update"] for r in updates] == list(range(20))
assert rec["physical"] == {"last_observed_update": 19, "observed_updates": 20, "resume_step": 0}
for link in rec["chain"]:
    req = read(ATT / "requests" / f"req-{link['g']}.json")
    assert req == {k: link[k] for k in ("g", "step", "file", "sha256")}
    assert (ATT / "requests" / f"ack-{link['g']}").is_file()

times = dict(line.split("=", 1) for line in (SMOKE / "run-20261008T0511Z.exit.txt").read_text().splitlines())
start = datetime.fromisoformat(times["start_utc"])
end = datetime.fromisoformat(times["end_utc"])
elapsed = (end - start).total_seconds()
assert times["EXIT_STATUS"] == "0" and 0 < summary["wall_s"] <= elapsed < 3600
assert start.timestamp() <= updates[0]["t_end"] < updates[-1]["t_end"] <= end.timestamp()
tele = [json.loads(line) for line in (ATT / "out/routing_telemetry.jsonl").read_text().splitlines()]
tr = [r for r in tele if "loss" in r]
metrics = read(ATT / "out/metrics.json")
assert [r["step"] for r in tr] == [0, 10]
nulls = []
for r in tr + [metrics["train_last"]]:
    keys = sorted(k for k, v in r["grad_norm"].items() if v is None)
    assert keys == ["L27/alpha", "L27/out_proj"]
    assert all(v is not None for v in r["update_norm"].values())
    assert all(r["update_norm"][k] == 0 for k in keys)
    nulls.append({"step": r["step"], "grad_null_keys": keys, "update_null_keys": []})

# Construction only: independently establish the exact optimizer name/index order.
os.environ["M4_SGM_QWEN3_0P6B_DIR"] = launch["model_snapshot"]
model_hashes = verify_files(Path(launch["model_snapshot"]))
runtime, backend, head = build(PilotConfig(**{**pilot, "device": "cpu"}))
named = [(f"adapters.{n}", p) for n, p in runtime.adapters.named_parameters() if p.requires_grad]
named += [(f"head.{n}", p) for n, p in head.named_parameters() if p.requires_grad]
assert len(named) == 46
assert {n: list(p.shape) for n, p in named} == registry["grad_names_shapes"]
coverage, checkpoints = {}, {}
for link in rec["chain"]:
    ck = torch.load(CDIR / "epoch-1" / link["file"], map_location="cpu", weights_only=True)
    assert ck["format"] == "m4-sgm-train-resume-v1" and ck["step"] == link["step"]
    assert ck["pilot_config"] == pilot and len(ck["cuda_rng"]) == 1
    groups = ck["optimizer"]["param_groups"]
    assert len(groups) == 1 and groups[0]["params"] == list(range(46))
    states = ck["optimizer"]["state"]
    assert len(states) == 44
    counts = {}
    for i, (name, parameter) in enumerate(named):
        s = states.get(i)
        if s is None:
            counts[name] = 0
        else:
            assert list(s["exp_avg"].shape) == list(s["exp_avg_sq"].shape) == list(parameter.shape)
            assert torch.isfinite(s["exp_avg"]).all() and torch.isfinite(s["exp_avg_sq"]).all()
            counts[name] = int(s["step"].item())
    checkpoints[link["file"]] = ck
    coverage[link["file"]] = {"shapes_match_build_order": True, "max_step": max(counts.values()),
                              "never_stepped": sorted(n for n, s in counts.items() if s == 0),
                              "partially_stepped": {n: s for n, s in counts.items() if 0 < s < link["step"]}}
saved = read(SMOKE / "run-20261008T0511Z.optimizer-step-coverage.json")
assert saved["n_params"] == 46 and all(saved[k] == v for k, v in coverage.items())
last = checkpoints["gen-2-step20.pt"]
trained = load_file(str(ATT / "out/trained_parameters.safetensors"))
checkpoint_tensors = {f"adapters.{n}": v for n, v in last["adapters"].items()}
checkpoint_tensors.update({f"head.{n}": v for n, v in last["head"].items()})
assert set(trained) == set(checkpoint_tensors)
assert all(torch.equal(v, checkpoint_tensors[n]) for n, v in trained.items())

# Current local cleanup state; historical t+4 process output was described, not saved raw.
processes = []
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == os.getpid():
        continue
    try:
        argv = proc.joinpath("cmdline").read_bytes().split(b"\0")
    except OSError:
        continue
    if any(x.endswith(b"/sgm-p2p5-readout-probe-local-gpu-smoke.py") or x == b"memsub.sgm.packed_slot_worker" for x in argv):
        processes.append({"pid": int(proc.name), "argv": [x.decode(errors="replace") for x in argv if x]})
assert not processes, processes
gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader"], text=True).strip()
apps = subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"], text=True).strip()
assert gpu.endswith(", 0 MiB") and apps == ""
result = {"audited_at_utc": datetime.now(timezone.utc).isoformat(),
          "package_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
          "metadata_hashes_verified": 24, "binary_hashes_verified": 3, "hashes": hashes,
          "source_bindings_match_cleared_r2": True, "probe_output_validator_problem": problem,
          "cell_state": rec["state"], "recovery": rec["recovery"], "physical_updates": 20,
          "script_wall_s": summary["wall_s"], "outer_elapsed_utc_s": elapsed, "exit_status": 0,
          "model_hashes": model_hashes, "logged_null_paths": nulls, "optimizer_coverage": coverage,
          "optimizer_order": [{"index": i, "name": n, "shape": list(p.shape)} for i, (n, p) in enumerate(named)],
          "checkpoint_cuda_rng_devices": [len(c["cuda_rng"]) for c in checkpoints.values()],
          "terminal_checkpoint_equals_trained_tensors": True,
          "current_cleanup": {"matching_processes": processes, "gpu": gpu, "compute_apps": apps},
          "historical_process_snapshot_limit": "The t+4 group and immediate cleanup descriptions have no separate raw snapshot in the package; the audited guard and successful argv provide indirect group evidence.",
          "pretrained_forward_passes_by_audit": 0, "gpu_runs_or_remote_actions_by_audit": 0,
          "scientific_learning_claim": False}
(OUT / "smoke-check-evidence.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k not in ("hashes", "optimizer_order")}, indent=2))
