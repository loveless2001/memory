"""Read-only launch binding and first durable-record verification. Never invokes a workload."""
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
from memsub.sgm.packed_slot_supervisor import expand_cells

OUT = Path(__file__).resolve().parent
PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
GROUP = "p2p5-qwen3-0p6b-screen-v1"
CALLS = {
    "learned-n32": ("ap-seAC6uskFnK96xlpe0wLIQ", "fc-01M4AJ8G12DME37XGZYB7417YY"),
    "oracle-n32": ("ap-Q3tBU1VKHFfO7etg4jmeTz", "fc-01M4AJ8RTEMM15GNNSGYK02WWX"),
    "random_fixed-n32": ("ap-ifA2HmtzYE3CNXIcommxBa", "fc-01M4AJ91PVR5JNDFFV2TYATNTM"),
    "single_cell-n32": ("ap-vAEMByn2pbJjoL46iekO9X", "fc-01M4AJ9AD7V34WE5J1Z42A1VS5"),
    "learned-n16": ("ap-ETP6e541BpdsPf11yzZGTe", "fc-01M4AJ9MZXQKC7PBC9GFRZXE83"),
    "random_fixed-n16": ("ap-vaN80Zc8IAet0r37n4bC5q", "fc-01M4AJ9Y6JQH6TF5V2WRHBDD8D"),
    "single_cell-n16": ("ap-RmkZbuerKMTGWBWtoY3E7r", "fc-01M4AJA7BNFA25ZZQPT3RSEHKY"),
    "memory_off-n32": ("ap-8m9pZ6KD77ivuvmSQ1vb5k", "fc-01M4AJAGE86T5P5GB6R90K947B"),
    "memory_off-n16": ("ap-FHeNdce7VkCSVBQWzTRmjk", "fc-01M4AJASPPVFZYB53KP3K3S05C"),
}
started = datetime.datetime.now(datetime.timezone.utc).isoformat()


def cli(kind):
    result = subprocess.run([sys.executable, "-m", "modal", kind, "list", "--env", "main", "--json"],
                            check=True, capture_output=True, text=True, timeout=60)
    (OUT / f"live-{kind}s.json").write_text(result.stdout)
    return kind, json.loads(result.stdout)


def read_dict(name):
    try:
        return dict(modal.Dict.from_name(name, environment_name="main", create_if_missing=False).items())
    except Exception as exc:
        return {"__error__": repr(exc)}


def poll(call_id):
    try:
        return {"kind": "result", "payload": modal.FunctionCall.from_id(call_id).get(timeout=0)}
    except TimeoutError:
        return {"kind": "pending"}
    except Exception as exc:
        return {"kind": "error", "error": repr(exc)}


with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    lists = dict(pool.map(cli, ("app", "container", "dict")))
control = read_dict("m4-sgm-p2p5-pk-campaign-control-guard-r2")
registry = read_dict("m4-sgm-p2p5-pk-campaign-control-registry-r2")
price = json.loads((PLAN / "pk6/priced-estimate-v6.json").read_text())
grid = expand_cells(json.loads((ROOT / "configs/m4_sgm_p2p5_grid.json").read_text()))
volume = modal.Volume.from_name("memsub-artifacts", environment_name="main", create_if_missing=False)
problems, slots, cells = [], {}, {}
if control.get("app_id") != "ap-suOdTgdc8PNSfZ3jbnsesa" or control.get("deadline_epoch") != 1791408417.2529736:
    problems.append("controller binding changed")
if len(registry) != 9:
    problems.append(f"registry does not have 9 entries: {len(registry)}")


def inspect_slot(item):
    slot, (expected_app, expected_call) = item
    app_name = f"memsub-m4-sgm-p2p5-pk-campaign-{slot.replace('_', '')}"
    local = PLAN / GROUP / slot
    prov = json.loads((local / "launch_provenance.json").read_text())
    call = json.loads((local / "call.json").read_text())["call_id"]
    guard, admission = read_dict(app_name + "-guard"), read_dict(app_name + "-admission")
    findings = []
    if prov["deployed_app_id"] != expected_app or call != expected_call or prov["git_head"] != "537ace8bc30a5ec486e521b6adf7ee3c340abf9f":
        findings.append("provenance differs from handoff")
    expected = prov["expected_identity"]
    local_hashes = {"runner": ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py",
                    "grid": ROOT / "configs/m4_sgm_p2p5_grid.json", "price": PLAN / "pk6/priced-estimate-v6.json",
                    "registry": ROOT / "configs/m4_sgm_p2p5_campaign_registry.json",
                    "schema": ROOT / "configs/m4_sgm_p2p5_campaign_output_schema.json"}
    if any(expected[k] != hashlib.sha256(p.read_bytes()).hexdigest() for k, p in local_hashes.items()):
        findings.append("expected file identity differs")
    if expected["memsub"] != "2eee4228124e9d292ed4079476ca276e8ce8f9ac7c8d83d44bcd51333687a19b":
        findings.append("memsub identity differs")
    if guard.get("app_id") != expected_app or guard.get("deadline_epoch") != prov["deadline_epoch"]:
        findings.append("slot guard differs from provenance")
    if registry.get(app_name) != {"app_id": expected_app, "deadline_epoch": prov["deadline_epoch"]}:
        findings.append("registry differs from provenance")
    if abs(prov["deadline_epoch"] - prov["spawn_epoch"] - price["slots"][slot]["reserve_life_s"]) > 1e-5:
        findings.append("slot lifetime differs from frozen ledger")
    required_after = 3600 + price["readings"]["reserve_life_s"] + 1800
    if prov["deadline_epoch"] + required_after > control["deadline_epoch"]:
        findings.append("slot misses controller horizon")
    if set(admission) != {"start-1"}:
        findings.append(f"admission is not exactly start-1: {list(admission)}")
    app_rows = [r for r in lists["app"] if r["app_id"] == expected_app]
    containers = [r for r in lists["container"] if r["app_id"] == expected_app]
    result = {"provenance": prov, "call_id": call, "poll": poll(call), "guard": guard, "admission": admission,
              "apps": app_rows, "containers": containers, "problems": findings}
    records = {}
    arm, n = slot.rsplit("-n", 1)
    for cell, pilot in grid.items():
        if pilot["arm"] != arm or pilot["n_bindings"] != int(n):
            continue
        path = f"m4-sgm/{GROUP}/{slot}/cells/{cell}/epoch-1/state.json"
        try:
            raw = b"".join(volume.read_file(path))
            rec = json.loads(raw)
            (OUT / "records" / f"{cell}.json").write_bytes(raw)
            item = {"state": rec["state"], "epoch": rec["epoch"], "acknowledged": rec.get("acknowledged"),
                    "chain_steps": [r["step"] for r in rec.get("chain", [])], "physical": rec.get("physical"),
                    "reason": rec.get("reason"), "sha256": hashlib.sha256(raw).hexdigest()}
            if not rec.get("acknowledged") or rec["epoch"] != 1 or rec["cell"] != cell:
                findings.append(f"{cell}: malformed first record")
            if {k: rec["identity"].get(k) for k in expected} != expected:
                findings.append(f"{cell}: remote record identity differs")
            if rec["state"] in ("FAILED", "LOST"):
                findings.append(f"{cell}: terminal failure {rec.get('reason')}")
            records[cell] = item
        except Exception as exc:
            records[cell] = {"read_error": repr(exc)}
            findings.append(f"{cell}: no verified first record")
    return slot, result, records


(OUT / "records").mkdir(exist_ok=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for slot, result, records in pool.map(inspect_slot, CALLS.items()):
        slots[slot] = result
        cells.update(records)
        problems.extend(f"{slot}: {p}" for p in result["problems"])
order = sorted(slots, key=lambda s: slots[s]["provenance"]["spawn_epoch"])
if order != list(CALLS):
    problems.append("spawn order differs from fixed longest-first order")
readings = {
    "guard": read_dict("memsub-m4-sgm-p2p5-pk-campaign-readings-guard"),
    "admission": read_dict("memsub-m4-sgm-p2p5-pk-campaign-readings-admission"),
    "apps": [r for r in lists["app"] if r["app_id"] == "ap-MvPw7JVom3vnRTxVVyzldN"],
    "containers": [r for r in lists["container"] if r["app_id"] == "ap-MvPw7JVom3vnRTxVVyzldN"],
}
if readings["containers"] or any(str(r["tasks"]) != "0" for r in readings["apps"]):
    problems.append("readings is active before validation")
result = {"status": "PASS" if not problems else "REVIEW", "started_utc": started,
          "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "problems": problems,
          "control": control, "registry": registry, "slots": slots, "cells": cells, "spawn_order": order,
          "readings": readings, "remote_mutations": 0,
          "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
          "tracked_diff": subprocess.check_output(["git", "diff", "HEAD", "--"], text=True)}
(OUT / "launch-verification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"status": result["status"], "completed_utc": result["completed_utc"], "problems": problems,
                  "slots": {s: {"poll": r["poll"], "admission": list(r["admission"]),
                                  "containers": len(r["containers"])} for s, r in slots.items()}, "cells": cells,
                  "readings": readings}))
