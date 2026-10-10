"""Bounded local artifact checks and read-only Modal queries; no workload invocation or campaign writes."""
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
from memsub.sgm.packed_slot_cell_output_validation import strict_json, validate_cell_outputs
from memsub.sgm.packed_slot_supervisor import expand_cells

OUT = Path(__file__).resolve().parent
PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
GROUP = PLAN / "p2p5-qwen3-0p6b-screen-v1"
BASE = json.loads((OUT.parent / "codex-261007-p2p5-pk-21652-launch-verification/launch-verification.json").read_text())
DIAG = json.loads((OUT.parent / "codex-261007-p2p5-pk-21700-schema-diagnosis/schema-diagnosis.json").read_text())
PILOTS = expand_cells(json.loads((ROOT / "configs/m4_sgm_p2p5_grid.json").read_text()))
REGISTRY = json.loads((ROOT / "configs/m4_sgm_p2p5_campaign_registry.json").read_text())["by_arm"]
SCHEMA = json.loads((ROOT / "configs/m4_sgm_p2p5_campaign_output_schema.json").read_text())["by_arm"]
PRICE = json.loads((PLAN / "pk6/priced-estimate-v6.json").read_text())
EVAL = {"final_batches": 16, "final_batch_size": 16, "final_seed_base": 9300011,
        "dev_seed": 4242, "train_eval_seed_base": 555001}
started = datetime.datetime.now(datetime.timezone.utc).isoformat()


def cli(kind):
    r = subprocess.run([sys.executable, "-m", "modal", kind, "list", "--env", "main", "--json"],
                       capture_output=True, text=True, check=True, timeout=60)
    (OUT / f"live-{kind}s.json").write_text(r.stdout)
    return kind, json.loads(r.stdout)


def read_dict(name):
    return dict(modal.Dict.from_name(name, environment_name="main", create_if_missing=False).items())


def inspect_slot(item):
    slot, baseline = item
    prov = baseline["provenance"]
    expected = prov["expected_identity"]
    name, app_id = prov["app_name"], prov["deployed_app_id"]
    guard, adm = read_dict(name + "-guard"), read_dict(name + "-admission")
    admitted = sorted(int(k.split("-")[1]) for k in adm if k.startswith("start-"))
    issues, cells = [], {}
    if admitted != list(range(1, len(admitted) + 1)) or not 1 <= len(admitted) <= 4:
        issues.append(f"invalid admission set {admitted}")
    if guard != baseline["guard"] or registry.get(name) != BASE["registry"][name]:
        issues.append("immutable guard/registry binding changed")
    st = strict_json((GROUP / slot / "collect_status.json").read_text())
    if st.get("final_shutdown", {}).get("status") != "stopped_verified" or st.get("evidence", {}).get("returncode") != 0:
        issues.append("collector did not retain a verified shutdown and successful fetch")
    evidence = ROOT / st["evidence_dir"] / slot
    arm, n = slot.rsplit("-n", 1)
    for cid, pilot in PILOTS.items():
        if pilot["arm"] != arm or pilot["n_bindings"] != int(n):
            continue
        cdir = evidence / "cells" / cid
        dirs = sorted(int(p.name.split("-")[1]) for p in cdir.glob("epoch-*"))
        if any(e not in admitted for e in dirs):
            issues.append(f"{cid}: epoch directory not admitted")
        rec = next(r for e in reversed(dirs) if (r := es.read_record(cdir, e)) is not None)
        walk = es.canonical_walk(rec, max_len=len(admitted))
        if any(r["epoch"] not in admitted or {k: r["identity"].get(k) for k in expected} != expected for r in walk):
            issues.append(f"{cid}: canonical record identity/admission mismatch")
        tail = rec["chain"][-1]
        terminal_ok = tail["step"] == 1500 and es.file_sha256(cdir / f"epoch-{tail['epoch']}" / tail["file"]) == tail["sha256"]
        if not terminal_ok:
            issues.append(f"{cid}: terminal checkpoint not step1500 with matching payload hash")
        state_file = cdir / f"epoch-{rec['epoch']}" / "state.json"
        result = {"state": rec["state"], "epoch": rec["epoch"], "canonical_epochs": [r["epoch"] for r in walk],
                  "state_sha256": es.file_sha256(state_file), "terminal_checkpoint": tail,
                  "terminal_checkpoint_verified": terminal_ok}
        if rec["state"] == es.COMPLETE:
            out = evidence / rec["outputs"]["attempt"] / "out"
            done_path = out.parent / "done.json"
            done = strict_json(done_path.read_text())["outputs"]
            if done != rec["outputs"]["files"]:
                issues.append(f"{cid}: done.json differs from canonical COMPLETE outputs pointer")
            problem = validate_cell_outputs(out, rec["outputs"]["files"], pilot, EVAL,
                                            expected["memsub"], REGISTRY[arm], SCHEMA[arm])
            result.update(validation=problem or "valid", outputs=done, done_sha256=es.file_sha256(done_path))
            if problem:
                issues.append(f"{cid}: output validation {problem}")
        elif cid == "learned-n32-s1" and rec["state"] == es.FAILED:
            previous = DIAG["cells"][cid]
            attempt = state_file.parent / "attempt-1"
            hashes = {name: es.file_sha256(attempt / "out" / name) for name in previous["output_hashes"]}
            unchanged = (result["state_sha256"] == previous["state_sha256"]
                         and es.file_sha256(attempt / "done.json") == previous["done_sha256"]
                         and hashes == previous["output_hashes"])
            result.update(reason=rec["reason"], failure_evidence_unchanged=unchanged,
                          original_gate="blocked", validation="FAILED retained")
            if not unchanged:
                issues.append(f"{cid}: previously diagnosed FAILED evidence changed")
        else:
            issues.append(f"{cid}: unexpected terminal state {rec['state']}")
        cells[cid] = result
    rows = [r for r in live["app"] if r["app_id"] == app_id]
    containers = [r for r in live["container"] if r["app_id"] == app_id]
    stopped = all(r["state"] == "stopped" and str(r["tasks"]) == "0" for r in rows) and not containers
    if not stopped:
        issues.append("bound slot app not stopped/unlisted with zero tasks/containers")
    return slot, {"admitted": admitted, "guard": guard, "app_rows": rows, "containers": containers,
                  "stopped_verified": stopped, "cells": cells, "issues": issues}


with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    live = dict(pool.map(cli, ("app", "container", "dict")))
control = read_dict("m4-sgm-p2p5-pk-campaign-control-guard-r2")
registry = read_dict("m4-sgm-p2p5-pk-campaign-control-registry-r2")
issues, slots = [], {}
if any(control.get(k) != BASE["control"].get(k) for k in ("app_id", "deadline_epoch", "price_sha256")):
    issues.append("controller binding changed")
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for slot, result in pool.map(inspect_slot, BASE["slots"].items()):
        slots[slot] = result
        issues.extend(f"{slot}: {s}" for s in result["issues"])
all_cells = {cid: c for s in slots.values() for cid, c in s["cells"].items()}
complete = sorted(k for k, c in all_cells.items() if c["state"] == "COMPLETE" and c["validation"] == "valid")
failed = sorted(k for k, c in all_cells.items() if c["state"] == "FAILED")
if len(complete) != 17 or failed != ["learned-n32-s1"]:
    issues.append("unexpected final 17 COMPLETE / 1 FAILED tally")
readings = {"apps": [r for r in live["app"] if r["app_id"] == "ap-MvPw7JVom3vnRTxVVyzldN"],
            "containers": [r for r in live["container"] if r["app_id"] == "ap-MvPw7JVom3vnRTxVVyzldN"],
            "guard_admission_names": [r for r in live["dict"] if r["name"].startswith("memsub-m4-sgm-p2p5-pk-campaign-readings-")]}
if readings["containers"] or readings["guard_admission_names"] or any(str(r["tasks"]) != "0" for r in readings["apps"]):
    issues.append("readings became active")
latest = control["deadline_epoch"] - PRICE["readings"]["reserve_life_s"] - 1800
result = {"status": "PASS" if not issues else "REVIEW", "started_utc": started,
          "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "issues": issues,
          "slots": slots, "complete_cells": complete, "failed_cells": failed, "control": control,
          "registry": registry, "readings": readings,
          "latest_readings_candidate_utc": datetime.datetime.fromtimestamp(latest, datetime.timezone.utc).isoformat(),
          "original_readings_gate": "blocked", "billing_reconciliation": "not performed in this audit",
          "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
          "tracked_diff": subprocess.check_output(["git", "diff", "HEAD", "--"], text=True), "remote_mutations": 0}
(OUT / "terminal-verification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"status": result["status"], "completed_utc": result["completed_utc"], "issues": issues,
                  "validated_complete_cells": len(complete), "failed_cells": failed,
                  "stopped_verified_slots": sum(s["stopped_verified"] for s in slots.values()),
                  "admissions": {s: r["admitted"] for s, r in slots.items()},
                  "latest_readings_candidate_utc": result["latest_readings_candidate_utc"], "readings": readings}))
