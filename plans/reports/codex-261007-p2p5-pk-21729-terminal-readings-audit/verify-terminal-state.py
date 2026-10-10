"""Read-only Modal terminal-state checks and local canonical artifact binding; no invocations or mutations."""
import concurrent.futures
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import modal

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent
PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
GROUP = PLAN / "p2p5-qwen3-0p6b-screen-v1"
LOCAL = GROUP / "readings"
LAUNCH = json.loads((OUT.parent / "codex-261007-p2p5-pk-21716-readings-launch-audit/launch-verification.json").read_text())
TERMINAL = json.loads((OUT.parent / "codex-261007-p2p5-pk-21704-terminal-training-audit/terminal-verification.json").read_text())
APP = "ap-MvPw7JVom3vnRTxVVyzldN"
NAME = "memsub-m4-sgm-p2p5-pk-campaign-readings"
CALL = "fc-01M4BG37XCKFD3A9WRJ91D44MB"
started = datetime.datetime.now(datetime.timezone.utc).isoformat()


def cli(kind):
    r = subprocess.run([sys.executable, "-m", "modal", kind, "list", "--env", "main", "--json"],
                       capture_output=True, text=True, check=True, timeout=50)
    (OUT / f"live-{kind}s.json").write_text(r.stdout)
    return kind, json.loads(r.stdout)


def read_dict(name):
    return dict(modal.Dict.from_name(name, environment_name="main", create_if_missing=False).items())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def stopped(app_id):
    apps = [r for r in live["app"] if r["app_id"] == app_id]
    containers = [r for r in live["container"] if r["app_id"] == app_id]
    return {"verified": not containers and all(r["state"] == "stopped" and str(r["tasks"]) == "0" for r in apps),
            "apps": apps, "containers": containers}


with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    live = dict(pool.map(cli, ("app", "container")))
names = (NAME + "-guard", NAME + "-admission", "m4-sgm-p2p5-pk-campaign-control-guard-r2",
         "m4-sgm-p2p5-pk-campaign-control-registry-r2")
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    dictionaries = list(pool.map(read_dict, names))
guard, admission, control, registry = dictionaries
slots = {slot: stopped(s["guard"]["app_id"]) for slot, s in TERMINAL["slots"].items()}
reading_stop = stopped(APP)
controller = stopped(control["app_id"])
payload = modal.FunctionCall.from_id(CALL).get(timeout=0)
checks = {"all_nine_training_apps_stopped": all(s["verified"] for s in slots.values()),
          "readings_app_stopped": reading_stop["verified"],
          "call_success": payload == {"status": "read", "rc": 0},
          "one_admission_and_bindings_unchanged": guard == LAUNCH["guard"] and admission == LAUNCH["admission"]
              and set(admission) == {"start-1"} and control == LAUNCH["control"] and registry == LAUNCH["registry"]}

# Compare the actual retained remote report and failure evidence with the fetched copies and approved spec.
volume = modal.Volume.from_name("memsub-artifacts", environment_name="main", create_if_missing=False)
prefix = "m4-sgm/p2p5-qwen3-0p6b-screen-v1/"
spec = json.loads((ROOT / "configs/m4_sgm_p2p5_pk_posthoc_validation_amendment.json").read_text())
remote_paths = {"readings-v1/readings.json": LOCAL / "volume-evidence/collect-1/readings-v1/readings.json",
                "readings-v1.exit.json": LOCAL / "volume-evidence/collect-1/readings-v1.exit.json",
                "learned-n32/cells/learned-n32-s1/epoch-1/state.json": GROUP / "learned-n32/volume-evidence/collect-1/learned-n32/cells/learned-n32-s1/epoch-1/state.json",
                "learned-n32/" + spec["attempt"] + "/done.json": GROUP / "learned-n32/volume-evidence/collect-1/learned-n32" / spec["attempt"] / "done.json"}
def remote_hash(item):
    rel, local = item
    raw = b"".join(volume.read_file(prefix + rel))
    digest = hashlib.sha256(raw).hexdigest()
    return rel, {"remote_sha256": digest, "local_sha256": sha(local), "match": digest == sha(local)}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    remote = dict(pool.map(remote_hash, remote_paths.items()))
checks["remote_report_exit_and_failed_evidence_match_collected"] = all(x["match"] for x in remote.values())
checks["original_failed_hashes_match_spec"] = (
    remote["learned-n32/cells/learned-n32-s1/epoch-1/state.json"]["remote_sha256"] == spec["state_sha256"]
    and remote["learned-n32/" + spec["attempt"] + "/done.json"]["remote_sha256"] == spec["done_sha256"])

s = importlib.util.spec_from_file_location("codex_terminal_rd", ROOT / "scripts/sgm-p2p5-pk-campaign-readings.py")
rd = importlib.util.module_from_spec(s)
s.loader.exec_module(rd)
grid, reg, schema = (json.loads(p.read_text()) for p in (rd.GRID, rd.REGISTRY, rd.SCHEMA))
unchanged, admitted = {}, {slot: x["admitted"] for slot, x in TERMINAL["slots"].items()}
with tempfile.TemporaryDirectory(prefix="codex-readings-final-bind-") as d:
    root = Path(d)
    for slot, slot_data in TERMINAL["slots"].items():
        (root / slot).symlink_to(GROUP / slot / "volume-evidence/collect-1" / slot)
        for cid, prev in slot_data["cells"].items():
            cdir = root / slot / "cells" / cid
            tail = prev["terminal_checkpoint"]
            unchanged[cid] = (sha(cdir / f"epoch-{prev['epoch']}" / "state.json") == prev["state_sha256"]
                              and sha(cdir / f"epoch-{tail['epoch']}" / tail["file"]) == tail["sha256"])
    original_cells, original_problem = rd.bind_cells(root, admitted, LAUNCH["provenance"]["expected_identity"]["memsub"], grid, reg, schema)
    amended_cells, amended_problem = rd.bind_cells(root, admitted, LAUNCH["provenance"]["expected_identity"]["memsub"], grid, reg, schema, spec)
checks["original_and_amended_canonical_bindings"] = (len(original_cells) == 17 and original_problem == "learned-n32-s1: state FAILED"
    and len(amended_cells) == 18 and amended_problem is None and all(unchanged.values()))

collect = json.loads((LOCAL / "collect_status.json").read_text())
stop_times = [datetime.datetime.fromisoformat(r["stopped_at"]).timestamp()
              for r in collect["final_shutdown"]["verification"]["app_rows"] if r.get("stopped_at")]
checks["collected_stop_within_readings_deadline"] = bool(stop_times) and max(stop_times) < guard["deadline_epoch"]
tracked = ["memsub", "scripts", "configs", "modal-runners", "tests", str(PLAN / "pk-campaign-posthoc-amendment"),
           str(PLAN / "prereg-amendment-posthoc-validation-learned-n32-s1.md")]
dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *tracked], text=True)
checks["frozen_source_still_clean"] = not dirty and rd.current_identity() == LAUNCH["provenance"]["expected_identity"]
result = {"status": "PASS" if all(checks.values()) else "REVIEW", "checks": checks,
          "started_utc": started, "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "slots": slots, "readings": reading_stop, "controller": controller, "control": control,
          "guard": guard, "admission": admission, "registry": registry, "call_payload": payload,
          "remote_hashes": remote, "all18_states_and_terminal_payloads_unchanged": unchanged,
          "original_bound_count": len(original_cells), "original_gate": original_problem,
          "amended_bound_count": len(amended_cells), "amended_gate": amended_problem,
          "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), "tracked_dirty": dirty,
          "controller_cleanup": "stopped_verified" if controller["verified"] else "still deployed/running; owner cleanup outstanding",
          "billing_reconciliation": "not yet audited", "remote_mutations": 0, "model_evaluations": 0}
(OUT / "terminal-state-check.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: result[k] for k in ("status", "checks", "completed_utc", "controller_cleanup", "controller", "remote_mutations")}))
assert all(checks.values()), checks
