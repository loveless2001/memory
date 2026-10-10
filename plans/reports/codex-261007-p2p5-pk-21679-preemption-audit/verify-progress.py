"""Read-only progress audit: bounded admissions, immutable clocks, actual recovery records and final outputs."""
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import modal

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from memsub.sgm import packed_slot_epoch_state as es
from memsub.sgm.packed_slot_cell_output_validation import validate_cell_outputs
from memsub.sgm.packed_slot_supervisor import expand_cells

OUT = Path(__file__).resolve().parent
BASE = json.loads((OUT.parent / "codex-261007-p2p5-pk-21652-launch-verification/launch-verification.json").read_text())
PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
GROUP = "p2p5-qwen3-0p6b-screen-v1"
GRID = expand_cells(json.loads((ROOT / "configs/m4_sgm_p2p5_grid.json").read_text()))
REGISTRY = json.loads((ROOT / "configs/m4_sgm_p2p5_campaign_registry.json").read_text())["by_arm"]
SCHEMA = json.loads((ROOT / "configs/m4_sgm_p2p5_campaign_output_schema.json").read_text())["by_arm"]
EVAL = {"final_batches": 16, "final_batch_size": 16, "final_seed_base": 9300011,
        "dev_seed": 4242, "train_eval_seed_base": 555001}
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
volume = modal.Volume.from_name("memsub-artifacts", environment_name="main", create_if_missing=False)
(OUT / "records").mkdir(exist_ok=True)


def cli(kind):
    r = subprocess.run([sys.executable, "-m", "modal", kind, "list", "--env", "main", "--json"],
                       check=True, capture_output=True, text=True, timeout=60)
    (OUT / f"live-{kind}s.json").write_text(r.stdout)
    return kind, json.loads(r.stdout)


def read_dict(name):
    return dict(modal.Dict.from_name(name, environment_name="main", create_if_missing=False).items())


def read_json(remote, local):
    raw = b"".join(volume.read_file(remote))
    (OUT / "records" / local).write_bytes(raw)
    return json.loads(raw)


def inspect_slot(item):
    slot, original = item
    prov = original["provenance"]
    app_id, app_name = prov["deployed_app_id"], prov["app_name"]
    admission = read_dict(app_name + "-admission")
    guard = read_dict(app_name + "-guard")
    admitted = sorted(int(k.split("-")[1]) for k in admission if k.startswith("start-"))
    issues = []
    if admitted != list(range(1, len(admitted) + 1)) or not 1 <= len(admitted) <= 4:
        issues.append(f"invalid admission set {admitted}")
    if guard.get("app_id") != app_id or guard.get("deadline_epoch") != prov["deadline_epoch"]:
        issues.append("slot guard app/deadline changed")
    if current_registry.get(app_name) != BASE["registry"][app_name]:
        issues.append("registry binding changed")
    arm, n = slot.rsplit("-n", 1)
    cells = {}
    for cell, pilot in GRID.items():
        if pilot["arm"] != arm or pilot["n_bindings"] != int(n):
            continue
        missing = []
        rec = None
        for epoch in reversed(admitted):
            try:
                rec = read_json(f"m4-sgm/{GROUP}/{slot}/cells/{cell}/epoch-{epoch}/state.json", f"{cell}-epoch-{epoch}.json")
            except FileNotFoundError:
                missing.append(epoch)
                continue
            if rec.get("acknowledged") is True:
                break
            rec = None
        if rec is None:
            issues.append(f"{cell}: no acknowledged authority")
            cells[cell] = {"missing_epochs": missing}
            continue
        walk = es.canonical_walk(rec, max_len=len(admitted))
        epochs = [r["epoch"] for r in walk]
        if any(e not in admitted for e in epochs) or rec["cell"] != cell:
            issues.append(f"{cell}: foreign canonical authority")
        expected = prov["expected_identity"]
        if any({k: r["identity"].get(k) for k in expected} != expected for r in walk):
            issues.append(f"{cell}: identity changed in canonical history")
        result = {"state": rec["state"], "authority_epoch": rec["epoch"], "canonical_epochs": epochs,
                  "missing_higher_epochs": missing, "recovery": rec.get("recovery"),
                  "last_acknowledged_step": (es.resume_point(rec) or {}).get("step", 0),
                  "physical": rec.get("physical"), "reason": rec.get("reason")}
        if rec["epoch"] > 1:
            args = read_json(f"m4-sgm/{GROUP}/{slot}/cells/{cell}/epoch-{rec['epoch']}/attempt-1/worker-args.json",
                             f"{cell}-epoch-{rec['epoch']}-worker-args.json")
            previous = rec.get("predecessor_snapshot")
            tail = es.resume_point(previous) if previous else None
            result["worker_resume_step"] = args.get("resume_step")
            result["worker_resume_sha256"] = args.get("resume_sha256")
            if tail and (args.get("resume_step") != tail["step"] or args.get("resume_sha256") != tail["sha256"]
                         or not args.get("resume_file", "").endswith(f"epoch-{tail['epoch']}/{tail['file']}")):
                issues.append(f"{cell}: worker arguments differ from inherited resume point")
        cells[cell] = result
    app_rows = [r for r in live["app"] if r["app_id"] == app_id]
    containers = [r for r in live["container"] if r["app_id"] == app_id]
    try:
        payload = modal.FunctionCall.from_id(original["call_id"]).get(timeout=0)
        poll = {"kind": "result", "payload": payload}
    except TimeoutError:
        poll = {"kind": "pending"}
    except Exception as exc:
        poll = {"kind": "error", "error": repr(exc)}
    final_validation = {}
    if slot.startswith("memory_off"):
        st = json.loads((PLAN / GROUP / slot / "collect_status.json").read_text())
        evidence = ROOT / st["evidence_dir"] / slot
        for cell, pilot in GRID.items():
            if pilot["arm"] != arm or pilot["n_bindings"] != int(n):
                continue
            rec = es.read_record(evidence / "cells" / cell, 1)
            problem = validate_cell_outputs(evidence / rec["outputs"]["attempt"] / "out", rec["outputs"]["files"],
                                            pilot, EVAL, prov["expected_identity"]["memsub"], REGISTRY[arm], SCHEMA[arm])
            final_validation[cell] = problem or "valid"
            if problem or rec["state"] != es.COMPLETE:
                issues.append(f"{cell}: completed-output validation failed: {problem}")
        if not app_rows or any(r["state"] != "stopped" or str(r["tasks"]) != "0" for r in app_rows) or containers:
            issues.append("memory-off shutdown not independently verified")
    return slot, {"admission": admission, "admitted": admitted, "remaining_starts": 4 - len(admitted),
                  "guard": guard, "deadline_utc": datetime.datetime.fromtimestamp(guard["deadline_epoch"], datetime.timezone.utc).isoformat(),
                  "apps": app_rows, "containers": containers, "poll": poll, "cells": cells,
                  "final_output_validation": final_validation, "issues": issues}


with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    live = dict(pool.map(cli, ("app", "container", "dict")))
current_control = read_dict("m4-sgm-p2p5-pk-campaign-control-guard-r2")
current_registry = read_dict("m4-sgm-p2p5-pk-campaign-control-registry-r2")
issues = []
if any(current_control.get(k) != BASE["control"].get(k) for k in ("app_id", "deadline_epoch", "price_sha256")):
    issues.append("controller binding changed")
slots = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for slot, result in pool.map(inspect_slot, BASE["slots"].items()):
        slots[slot] = result
        issues.extend(f"{slot}: {s}" for s in result["issues"])
reading_rows = [r for r in live["app"] if r["app_id"] == "ap-MvPw7JVom3vnRTxVVyzldN"]
reading_containers = [r for r in live["container"] if r["app_id"] == "ap-MvPw7JVom3vnRTxVVyzldN"]
reading_dicts = [r for r in live["dict"] if r["name"].startswith("memsub-m4-sgm-p2p5-pk-campaign-readings-")]
if reading_containers or reading_dicts or any(str(r["tasks"]) != "0" for r in reading_rows):
    issues.append("readings active before all-cell validation")
result = {"status": "PASS" if not issues else "REVIEW", "started_utc": started,
          "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "issues": issues,
          "slots": slots, "control": current_control, "registry": current_registry,
          "readings": {"apps": reading_rows, "containers": reading_containers, "guard_admission_names": reading_dicts},
          "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
          "tracked_diff": subprocess.check_output(["git", "diff", "HEAD", "--"], text=True), "remote_mutations": 0}
(OUT / "progress-verification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"status": result["status"], "completed_utc": result["completed_utc"], "issues": issues,
                  "slots": {s: {"admitted": r["admitted"], "remaining_starts": r["remaining_starts"],
                                 "deadline_utc": r["deadline_utc"], "poll": r["poll"]["kind"],
                                 "containers": len(r["containers"]), "cells": r["cells"],
                                 "validation": r["final_output_validation"]} for s, r in slots.items()}}))
