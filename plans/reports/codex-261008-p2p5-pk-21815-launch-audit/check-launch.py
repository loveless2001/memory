"""Reconcile immutable launch bytes with a captured read-only consumer snapshot. No remote calls."""
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PLAN = ROOT / "plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe"
LAUNCH = PLAN / "launch"
LOCAL = PLAN / "p2p5-readout-probe-v1/taskhead-learned-n32"
COMMIT = "622b17c073d04754c7b9be0a75a74a72ec9427a7"
sys.path.insert(0, str(ROOT))


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(rel, name):
    s = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


L = load("modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-logic.py", "launch_audit_logic")
R = load("modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py", "launch_audit_runner")
CP = load(L.CONTROL_LOGIC_FILE, "launch_audit_control")
from memsub.sgm.pinned_pretrained_qwen3_backbone import QWEN3_0P6B_BASE

prov = read(LOCAL / "launch_provenance.json")
call = read(LOCAL / "call.json")["call_id"]
assert CP.provenance_problem(prov, slot=L.SLOT) is None
assert prov["git_head"] == "eb41ab7e6ff5f3023222855592b5c1a65f9ed8c3"
assert prov["app_name"] == L.APP_NAME and prov["expected_identity"] == R.expected_identity()
assert math.isclose(prov["deadline_epoch"] - prov["spawn_epoch"], 31946.2, rel_tol=0, abs_tol=1e-6)
assert not subprocess.check_output(["git", "diff", "30e2b3e", COMMIT, "--", "memsub", "scripts", "configs", "modal-runners", "tests"], cwd=ROOT)
assert subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT) == b""

retained = {}
for path in sorted(LAUNCH.iterdir()):
    rel = str(path.relative_to(ROOT))
    probe = subprocess.run(["git", "cat-file", "-e", f"{COMMIT}:{rel}"], cwd=ROOT, capture_output=True)
    if probe.returncode != 0:
        continue
    committed = subprocess.check_output(["git", "show", f"{COMMIT}:{rel}"], cwd=ROOT)
    assert path.read_bytes() == committed, rel
    dest = OUT / "launch-package" / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(committed)
    retained[rel] = hashlib.sha256(committed).hexdigest()
for name in ("launch_provenance.json", "call.json"):
    src = LOCAL / name
    committed = subprocess.check_output(["git", "show", f"{COMMIT}:{src.relative_to(ROOT)}"], cwd=ROOT)
    assert committed == src.read_bytes()
    (OUT / name).write_bytes(committed)

exits = {}
for stem in ("02-deploy", "04-spawn"):
    info = dict(line.split("=", 1) for line in (LAUNCH / f"{stem}.exit.txt").read_text().splitlines())
    assert info["EXIT_STATUS"] == "0"
    exits[stem] = info
deploy_text = (LAUNCH / "02-deploy.txt").read_text()
assert "App deployed in 128.587s" in deploy_text and "Traceback" not in deploy_text
assert "Finished image build for im-HVp9ExWA0biZsZzrQa34s2" in deploy_text
assert (LAUNCH / "04-spawn.txt").read_text().strip() == f"spawned {L.SLOT} {call}"
deployed = next(r for r in read(LAUNCH / "03-app-list-after-deploy.json") if r["app_id"] == prov["deployed_app_id"])
assert deployed["description"] == L.APP_NAME and deployed["state"] == "deployed"
assert not any(r["description"] == L.APP_NAME for r in read(LAUNCH / "00-app-list-before-deploy.json"))
early_guard = read(LAUNCH / "05-dicts-after-spawn.json")["guard"]
assert early_guard == {"app_id": prov["deployed_app_id"], "deadline_epoch": prov["deadline_epoch"]}

snap = read(OUT / "live-snapshot.json")
assert snap["bound_app_id"] == prov["deployed_app_id"] and snap["call_id"] == call
guard, adm = snap["dicts"]["guard"], snap["dicts"]["admission"]
assert guard["app_id"] == guard["self_app_id"] == prov["deployed_app_id"]
assert guard["deadline_epoch"] == prov["deadline_epoch"] and set(adm) == {"start-1"}
assert prov["spawn_epoch"] < adm["start-1"] < prov["deadline_epoch"]
assert snap["call_poll"]["state"] == "pending" and snap["stats"]["run_slot"]["num_total_runners"] == 1
assert snap["inventory"]["app"]["probe_rows"][0]["state"] == "deployed"
assert all("error" not in value for value in snap["fetched"].values())
cells = L.probe_cells(read(ROOT / L.GRID_FILE))
cell_checks = {}
for name, pilot in cells.items():
    rec = read(OUT / "remote-metadata" / name / "state.json")
    args = read(OUT / "remote-metadata" / name / "attempt-1/worker-args.json")
    actual = rec["identity"]
    assert {k: actual[k] for k in prov["expected_identity"]} == prov["expected_identity"]
    assert actual["runner_expected"] == prov["expected_identity"] and actual["model"] == QWEN3_0P6B_BASE
    assert actual["env"]["torch"] == "2.7.1+cu126" and actual["env"]["transformers"] == "4.55.2"
    assert actual["env"]["cuda"] == "12.6" and actual["env"]["tf32_matmul"] is False
    assert rec["acknowledged"] is True and rec["epoch"] == 1 and rec["state"] == "STARTED" and rec["recovery"] == "fresh"
    assert args["pilot_config"] == pilot and args["eval"] == L.EVAL and args["checkpoint_every"] == 50
    assert args["cell"] == name and args["epoch"] == args["attempt"] == 1 and args["mode"] == "train"
    assert args["resume_file"] is None and args["resume_step"] == 0 and args["fault"] is None and args["proof_capture"] is False
    assert args["epoch_dir"] == f"/artifacts/{L.VOLUME_SUBPATH}/cells/{name}/epoch-1"
    cell_checks[name] = {"state": rec["state"], "epoch": rec["epoch"], "source_identity_matches": True,
                         "pilot_matches": True, "checkpoint_chain": rec["chain"], "environment": actual["env"]}

# Preserve the active wrapper and a point-in-time log without editing either.
loop = LAUNCH / "collect-loop-until-stopped-verified.sh"
(OUT / "collect-loop-reviewed.sh").write_bytes(loop.read_bytes())
(OUT / "collect-loop-log-snapshot.txt").write_bytes((LAUNCH / "08-collect-loop.log").read_bytes())
assert '"final": true' in loop.read_text()
deadline = datetime.fromtimestamp(prov["deadline_epoch"], timezone.utc)
result = {"verdict": "PASS: launch identity and scope verified; call running/pending",
          "package_commit": COMMIT, "source_commit": prov["git_head"], "app_id": prov["deployed_app_id"], "call_id": call,
          "saved_launch_hashes": retained, "deploy_spawn_exit_records": exits,
          "snapshot_at_utc": snap["at_utc"], "admitted_starts": len(adm), "total_start_allowance": L.MAX_STARTS,
          "deadline_epoch": prov["deadline_epoch"], "deadline_utc": deadline.isoformat(),
          "deadline_bangkok": deadline.astimezone(ZoneInfo("Asia/Bangkok")).isoformat(),
          "immutable_slot_duration_s": 31946.2, "cap_usd": 40.75, "cell_checks": cell_checks,
          "remote_mutations_by_audit": False, "learning_result_available": False, "billing_reconciled": False,
          "snapshot_limit": "The app/container, stats, Dict and volume reads are sequential point-in-time reads, not an atomic snapshot. Empty retained checkpoint chains do not imply zero optimizer updates.",
          "collector_note": "The wrapper exits on final=true (stop attempted), not necessarily stopped_verified. The final shutdown status and zero tasks/containers must be checked explicitly."}
(OUT / "launch-check-evidence.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "saved_launch_hashes"}, indent=2))
