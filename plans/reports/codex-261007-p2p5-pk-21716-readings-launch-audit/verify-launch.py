"""Read-only verification of the approved readings launch; never invokes or changes a workload."""
import concurrent.futures
import dataclasses
import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import modal

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent
PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
LOCAL = PLAN / "p2p5-qwen3-0p6b-screen-v1/readings"
BASE = json.loads((OUT.parent / "codex-261007-p2p5-pk-21710-amendment-audit/remote-audit.json").read_text())
CALL = "fc-01M4BG37XCKFD3A9WRJ91D44MB"
APP = "ap-MvPw7JVom3vnRTxVVyzldN"
NAME = "memsub-m4-sgm-p2p5-pk-campaign-readings"
started = datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cli(kind):
    r = subprocess.run([sys.executable, "-m", "modal", kind, "list", "--env", "main", "--json"],
                       capture_output=True, text=True, check=True, timeout=50)
    (OUT / f"live-{kind}s.json").write_text(r.stdout)
    return kind, json.loads(r.stdout)


def read_dict(name):
    return dict(modal.Dict.from_name(name, environment_name="main", create_if_missing=False).items())


def poll():
    try:
        return {"kind": "result", "payload": modal.FunctionCall.from_id(CALL).get(timeout=0)}
    except TimeoutError:
        return {"kind": "pending"}
    except Exception as e:
        return {"kind": "error", "error": repr(e)}


def volume_evidence(rel):
    volume = modal.Volume.from_name("memsub-artifacts", environment_name="main", create_if_missing=False)
    raw = b"".join(volume.read_file("m4-sgm/p2p5-qwen3-0p6b-screen-v1/learned-n32/" + rel))
    return rel, {"sha256": hashlib.sha256(raw).hexdigest(), "json": json.loads(raw)}


with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    live = dict(pool.map(cli, ("app", "container")))
names = (NAME + "-guard", NAME + "-admission", "m4-sgm-p2p5-pk-campaign-control-guard-r2",
         "m4-sgm-p2p5-pk-campaign-control-registry-r2")
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    dictionaries = dict(zip(names, pool.map(read_dict, names)))
guard, adm, control, registry = (dictionaries[n] for n in names)
spec = json.loads((ROOT / "configs/m4_sgm_p2p5_pk_posthoc_validation_amendment.json").read_text())
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    remote = dict(pool.map(volume_evidence, ("cells/learned-n32-s1/epoch-1/state.json", spec["attempt"] + "/done.json")))

prov = json.loads((LOCAL / "launch_provenance.json").read_text())
call = json.loads((LOCAL / "call.json").read_text())["call_id"]
s = importlib.util.spec_from_file_location("codex_readings_runner", ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py")
runner = importlib.util.module_from_spec(s)
s.loader.exec_module(runner)
cp = runner.load_cp()
identity = runner.expected_identity()
price = json.loads((ROOT / runner.PRICE_FILE).read_text())
candidate_start = prov["deadline_epoch"] - price["readings"]["reserve_life_s"]
app_lookup = modal.App.lookup(NAME, environment_name="main").app_id
control_lookup = modal.App.lookup(runner.CONTROL_APP_NAME, environment_name="main").app_id
apps = [r for r in live["app"] if r["app_id"] == APP]
containers = [r for r in live["container"] if r["app_id"] == APP]
training_ids = {s["guard"]["app_id"] for s in BASE["slots"].values()}
training_apps = [r for r in live["app"] if r["app_id"] in training_ids]
training_containers = [r for r in live["container"] if r["app_id"] in training_ids]
fn = modal.Function.from_name(NAME, "run_readings", environment_name="main")
stats = dataclasses.asdict(fn.get_current_stats())
polled = poll()
now = time.time()
admission_epoch = adm.get("start-1")
latest = control["deadline_epoch"] - price["readings"]["reserve_life_s"] - runner.CONTROL_SLACK_S
cp_problem = cp.binding_problem(control, sha(ROOT / runner.PRICE_FILE), lambda: control_lookup,
    lambda app_id: next((r["state"] for r in live["app"] if r["app_id"] == app_id), "none"),
    prov["deadline_epoch"], runner.CONTROL_SLACK_S)
state = remote["cells/learned-n32-s1/epoch-1/state.json"]
done = remote[spec["attempt"] + "/done.json"]
tracked = ["memsub", "scripts", "configs", "modal-runners", "tests", str(PLAN / "pk-campaign-posthoc-amendment"),
           str(PLAN / "prereg-amendment-posthoc-validation-learned-n32-s1.md")]
dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *tracked], text=True)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
checks = {
    "frozen_launch_provenance": prov["git_head"] == head == "a17cd401c9046b1aa92826c0ecb47914d06270c7"
        and not dirty and prov["expected_identity"] == identity and cp.launch_manifest_problem(ROOT) is None,
    "expected_call_and_app": call == CALL and prov["deployed_app_id"] == APP == app_lookup,
    "guard_exactly_matches_provenance": guard == {"app_id": APP, "deadline_epoch": prov["deadline_epoch"]},
    "exactly_one_admission_within_bound": set(adm) == {"start-1"} and isinstance(admission_epoch, (int, float))
        and not isinstance(admission_epoch, bool) and math.isfinite(admission_epoch)
        and candidate_start <= admission_epoch <= min(now, prov["deadline_epoch"]),
    "controller_unchanged_and_deadline_fits": control == BASE["control"] and cp_problem is None
        and candidate_start <= latest,
    "registry_only_adds_exact_readings_entry": registry == {**BASE["registry"], NAME: guard},
    "all_training_apps_still_stopped": not training_containers
        and all(r["state"] == "stopped" and str(r["tasks"]) == "0" for r in training_apps),
    "readings_app_and_container_bound": len(apps) == 1 and apps[0]["state"] == "deployed" and len(containers) <= 1,
    "call_read_did_not_error": polled["kind"] != "error",
    "original_failed_remote_evidence_retained": state["sha256"] == spec["state_sha256"]
        and state["json"]["state"] == "FAILED" and state["json"]["reason"] == spec["original_reason"]
        and done["sha256"] == spec["done_sha256"] and done["json"]["outputs"] == spec["outputs"],
}
result = {"status": "PASS" if all(checks.values()) else "REVIEW", "checks": checks,
          "started_utc": started, "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "head": head, "tracked_dirty": dirty, "provenance": prov, "call_id": call, "poll": polled,
          "function_id": fn.object_id, "function_stats": stats, "apps": apps, "containers": containers,
          "guard": guard, "admission": adm, "control": control, "registry": registry,
          "candidate_start_utc": datetime.datetime.fromtimestamp(candidate_start, datetime.timezone.utc).isoformat(),
          "readings_deadline_utc": datetime.datetime.fromtimestamp(prov["deadline_epoch"], datetime.timezone.utc).isoformat(),
          "latest_candidate_utc": datetime.datetime.fromtimestamp(latest, datetime.timezone.utc).isoformat(),
          "controller_binding_problem": cp_problem, "failed_remote_evidence": remote,
          "scientific_status": "pending; remote parity, reserved readings and report labels not yet audited",
          "billing_reconciliation": "pending", "remote_mutations": 0}
(OUT / "launch-verification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: result[k] for k in ("status", "checks", "completed_utc", "poll", "function_stats",
                                      "candidate_start_utc", "readings_deadline_utc", "remote_mutations")}))
assert all(checks.values()), checks
