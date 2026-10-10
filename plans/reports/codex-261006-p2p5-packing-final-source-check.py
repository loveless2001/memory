"""Source/artifact binding and independent arithmetic checks; no paid or remote work."""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import statistics
import subprocess
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
REL = "scripts/sgm-p2p5-gpu-packing-concurrent-training-throughput-test.py"
RUNNER = "modal-runners/modal-m4-sgm-p2p5-dev-gpu-test-runner.py"
OUT = ROOT / "plans/reports/codex-261006-p2p5-packing-final-source-check.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-commit", required=True)
    args = ap.parse_args()
    consumed = {}
    for rel in (REL,RUNNER,"tests/test_sgm_p2p5_gpu_packing_throughput_measurement.py"):
        raw = (ROOT/rel).read_bytes()
        assert raw == subprocess.check_output(["git","show",f"{args.source_commit}:{rel}"],cwd=ROOT),rel
        consumed[rel] = hashlib.sha256(raw).hexdigest()
    assert consumed[RUNNER] == "5c1e287e11465db32cecfe5e9e6682a61994fc897fe750b240dd5ed5348838c1"
    spec = importlib.util.spec_from_file_location("packing_final_check",ROOT/REL)
    pk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pk)
    assert pk.TESTS == [(2,1),(2,2),(1,1),(1,3)]
    assert (pk.WARMUP,pk.MEASURED,pk.THREADS,pk.SEED0,pk.WALL_S,pk.TEST_TIMEOUT_S,pk.BARRIER_S) == (2,6,2,99,1080,420,240)
    from memsub.sgm.synthetic_pilot_run import source_tree_sha256
    memsub_sha = source_tree_sha256(ROOT/"memsub")
    assert memsub_sha == "b87a767baac578d94a6f778560f4fb451fd60679cca48412218adaac74f74085"
    artifact_binding = {}
    for tag,commit in (("v2","bf5c8b3"),("v3",args.source_commit)):
        smoke_rel = str((BASE/f"dev-gpu/packing-smoke-cpu-local-{tag}").relative_to(ROOT))
        frozen_smoke = subprocess.check_output(["git","ls-tree","-r","--name-only",commit,smoke_rel],cwd=ROOT,text=True).splitlines()
        frozen_smoke.append(smoke_rel+".log")
        for rel in frozen_smoke:
            raw = (ROOT/rel).read_bytes()
            assert raw == subprocess.check_output(["git","show",f"{commit}:{rel}"],cwd=ROOT)
            artifact_binding[rel] = hashlib.sha256(raw).hexdigest()
        assert (ROOT/(smoke_rel+".log")).read_text().splitlines()[-1] == "EXIT_STATUS=0"
    smoke_checks = []
    own = ROOT/"plans/reports/codex-261006-p2p5-packing-bf5c8b3-cpu-smoke"
    for folder in (BASE/"dev-gpu/packing-smoke-cpu-local-v2",BASE/"dev-gpu/packing-smoke-cpu-local-v3",own):
        report = json.loads((folder/"packing.json").read_text())
        assert report["status"]=="complete" and report["gpu"]=="smoke-cpu" and report["memsub_source_sha256"]==memsub_sha
        assert [(t["phase"],t["k"]) for t in report["tests"]] == pk.TESTS
        baseline = {}
        checked = []
        for test in report["tests"]:
            phase,k = test["phase"],test["k"]
            assert test["status"]=="ok" and test["worker_exit"]==[0]*k
            assert pk.validate_workers(test["workers"],phase,k) is None
            assert test["overlap_s"]>0
            for rank,w in enumerate(test["workers"]):
                assert w == json.loads((folder/f"p{phase}-k{k}/worker-{rank}.json").read_text())
                assert w["peak_allocated_bytes"]==0
                measured = w["updates"][2:]
                assert math.isclose(w["mean_measured_s"],statistics.fmean(u["seconds"] for u in measured),abs_tol=1e-12)
            start = min(w["measured_start"] for w in test["workers"])
            end = max(w["measured_end"] for w in test["workers"])
            rate = 6*k/(end-start)
            assert test["fixed_work_span"] == [start,end]
            assert math.isclose(rate,test["fixed_work_updates_per_s"],rel_tol=1e-12)
            if k==1:
                baseline[phase]=rate
            assert math.isclose(test["speedup_vs_k1"],rate/baseline[phase],rel_tol=1e-12)
            assert pk.summarize(test["workers"],phase,k)["fixed_work_updates_per_s"]==rate
            checked.append({"phase":phase,"k":k,"valid_worker_count":k,"primary_arithmetic_reconciles":True,
                            "positive_overlap":True})
        smoke_checks.append({"folder":str(folder.relative_to(ROOT)),"status":"complete","checks":checked,
                             "timings_not_evidence_of_gpu_packing":True})
    valid = json.loads((own/"packing.json").read_text())["tests"][0]["workers"]
    negative_checks = []
    for key in ("mean_measured_s","measured_start","measured_end"):
        for bad in (float("nan"),float("inf"),float("-inf")):
            w = copy.deepcopy(valid)
            w[0][key]=bad
            rejection = pk.validate_workers(w,2,1)
            assert rejection is not None,(key,bad)
            negative_checks.append({"field":key,"value":str(bad),"rejection":rejection})
    for rel,sha in json.loads((ROOT/"plans/reports/codex-261006-p2p5-v2-4e22bae-results-checks.json").read_text())["protected_v1_and_protocol_files_unchanged"].items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==sha,rel
    destination = BASE/"dev-gpu/packing-a100-v1"
    assert not destination.exists(),"launch output already exists"
    reservation = 1440*(D('.000694')+2*(8*D('.0000131')+64*D('.00000222')))+D('.168384')+D('.10')
    assert reservation == D('1.97875840')
    report = {"checked_at_utc":datetime.now(timezone.utc).isoformat(),"source_commit":args.source_commit,
        "source_sha256":consumed,"memsub_sha256":memsub_sha,"frozen_smoke_artifact_sha256":artifact_binding,
        "smoke_checks":smoke_checks,"additional_nonfinite_negative_checks":negative_checks,
        "historical_v1_and_protocol_bytes_preserved":True,"fresh_destination":str(destination),
        "reservation_usd":str(reservation),"booked_usd":"1.98","cap_usd":"2.00",
        "paid_or_remote_work_performed":False,"source_and_local_checks_pass":True,
        "limits":["Local CPU smoke verifies orchestration only.","Six measured updates at seeds99+rank do not validate long-run campaign throughput, GPU resume or correctness.",
                  "Start/end timestamps use wall clock; gross discontinuities are rejected by span consistency, but small clock drift can perturb rates.",
                  "Reservation uses stated teardown/resource/build assumptions, not a platform cash ceiling. No operator retry or matrix expansion approved."]}
    OUT.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"source_commit":args.source_commit,"source_and_local_checks_pass":True,
        "independent_cpu_smoke_complete":True,"nonfinite_negative_probes":len(negative_checks),
        "reservation_usd":str(reservation),"fresh_destination":str(destination)},indent=2))


if __name__ == "__main__":
    main()
