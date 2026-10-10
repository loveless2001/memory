"""Independent terminal packing arithmetic, source binding and read-only Modal audit."""
import csv
import dataclasses
import hashlib
import importlib.util
import json
import math
import statistics
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import modal
from modal.experimental import get_app_lifecycle

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/dev-gpu"
RUN = BASE / "packing-a100-v1"
APP = "ap-uPN6X6TfZ7Yv9lCaLHAkx7"
COMMIT = "6686215"
OUT = ROOT / "plans/reports/codex-261006-p2p5-packing-6686215-terminal-check.json"


def read(p):
    return json.loads(p.read_text())


def cli(noun):
    p = subprocess.run([str(ROOT/".venv/bin/python"),"-m","modal",noun,"list","--json"],
                       cwd=ROOT,capture_output=True,text=True,check=True,timeout=45)
    return json.loads(p.stdout)


def main():
    report={"checked_at_utc":datetime.now(timezone.utc).isoformat(),"app_id":APP,
            "evidence_commit":COMMIT,"read_only_remote":True,"paid_work":False}
    paths=subprocess.check_output(["git","diff-tree","--no-commit-id","--name-only","-r",COMMIT],cwd=ROOT,text=True).splitlines()
    hashes={}
    for rel in paths:
        raw=(ROOT/rel).read_bytes()
        assert raw==subprocess.check_output(["git","show",f"{COMMIT}:{rel}"],cwd=ROOT),rel
        hashes[rel]=hashlib.sha256(raw).hexdigest()
    assert len(paths)==32
    source={}
    for rel in ("scripts/sgm-p2p5-gpu-packing-concurrent-training-throughput-test.py",
                "modal-runners/modal-m4-sgm-p2p5-dev-gpu-test-runner.py"):
        raw=(ROOT/rel).read_bytes()
        assert raw==subprocess.check_output(["git","show","57aad85:"+rel],cwd=ROOT),rel
        source[rel]=hashlib.sha256(raw).hexdigest()
    spec=importlib.util.spec_from_file_location("packing_terminal",ROOT/"scripts/sgm-p2p5-gpu-packing-concurrent-training-throughput-test.py")
    pk=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pk)
    meta,data=read(RUN/"run.json"),read(RUN/"result/packing.json")
    assert meta["app_id"]==APP and meta["gpu"]=="A100-80GB" and meta["args"]==""
    assert meta["outcome"]=="ok" and meta["returncode"]==0
    assert 0<meta["wall_s"]<=meta["client_wall_s"]<1320
    assert meta["cmd"]==["/usr/local/bin/python",meta["script"],"--out","/tmp/dev-out/result"]
    assert data["status"]=="complete" and data["gpu"]=="NVIDIA A100-SXM4-80GB" and data["torch"]=="2.7.1+cu126"
    assert data["memsub_source_sha256"]=="b87a767baac578d94a6f778560f4fb451fd60679cca48412218adaac74f74085"
    assert (RUN/"stderr.txt").read_text()==""
    console=(BASE/"packing-a100-v1.console.log").read_text()
    assert [s for s in console.splitlines() if s.startswith("EXIT_STATUS=")]==["EXIT_STATUS=0"]
    assert "App completed." in console
    launch=(BASE/"packing-a100-v1.launch-time.txt").read_text().splitlines()
    assert launch==["2026-10-06T22:46:12+07:00","57aad8581579c9fd17ba70490e0d817567cedb59"]
    stdout=(RUN/"stdout.txt").read_text().splitlines()
    assert len(stdout)==5 and stdout[-1]=="complete"
    printed=[json.loads(s) for s in stdout[:-1]]
    assert [(t["phase"],t["k"]) for t in data["tests"]]==[(2,1),(2,2),(1,1),(1,3)]
    sampler=data["sampler"]
    assert sampler["query"]=="timestamp,utilization.gpu,memory.used" and sampler["loop_ms"]==500
    assert sampler["tz"]=="UTC" and sampler["utc_offset_s"]==0 and sampler["stop"]=="exited rc 0"
    samples=[]
    for row in csv.reader((RUN/"result/gpu-util.csv").read_text().splitlines()):
        assert len(row)==3
        t=datetime.strptime(row[0].strip(),"%Y/%m/%d %H:%M:%S.%f").replace(tzinfo=timezone.utc).timestamp()
        gpu,used=map(float,row[1:])
        assert all(math.isfinite(x) for x in (t,gpu,used)) and 0<=gpu<=100 and used>=0
        samples.append((t,gpu,used))
    assert len(samples)==666 and all(a[0]<b[0] for a,b in zip(samples,samples[1:]))
    assert meta["started"]<sampler["start_epoch"]<=samples[0][0]<samples[-1][0]<meta["started"]+meta["client_wall_s"]
    baseline,recomputed={},[]
    previous_end=0
    worker_count,update_count=0,0
    for test,print_row in zip(data["tests"],printed):
        phase,k=test["phase"],test["k"]
        assert test["status"]=="ok" and test["worker_exit"]==[0]*k
        assert pk.validate_workers(test["workers"],phase,k) is None
        assert all(test[key]==value for key,value in print_row.items() if key in test)
        assert print_row["problem"] is None
        means=[]
        for rank,w in enumerate(test["workers"]):
            folder=RUN/f"result/p{phase}-k{k}"
            assert w==read(folder/f"worker-{rank}.json")
            assert (folder/f"worker-{rank}.log").read_text()==""
            assert (folder/f"barrier/ready-{rank}").exists()
            assert (w["phase"],w["rank"],w["k"],w["seed"])==(phase,rank,k,99+rank)
            assert [u["update"] for u in w["updates"]]==list(range(8))
            assert previous_end<w["updates"][0]["t_end"]
            mean=statistics.fmean(u["seconds"] for u in w["updates"][2:])
            assert math.isclose(mean,w["mean_measured_s"],abs_tol=1e-12)
            assert 0<w["peak_allocated_bytes"]<80*2**30
            means.append(mean)
            worker_count+=1
            update_count+=len(w["updates"])
        start=min(w["measured_start"] for w in test["workers"])
        end=max(w["measured_end"] for w in test["workers"])
        overlap_start=max(w["measured_start"] for w in test["workers"])
        overlap_end=min(w["measured_end"] for w in test["workers"])
        assert sampler["start_epoch"]<start<end<samples[-1][0]
        assert overlap_end>overlap_start and test["overlap_window"]==[overlap_start,overlap_end]
        assert test["fixed_work_span"]==[start,end]
        rate=6*k/(end-start)
        assert math.isclose(rate,test["fixed_work_updates_per_s"],rel_tol=1e-12)
        if k==1:
            baseline[phase]=rate
        speedup=rate/baseline[phase]
        assert math.isclose(speedup,test["speedup_vs_k1"],rel_tol=1e-12)
        fractions=0.0
        for w in test["workers"]:
            for u in w["updates"][2:]:
                a,b=u["t_end"]-u["seconds"],u["t_end"]
                fractions+=max(0.0,min(b,overlap_end)-max(a,overlap_start))/(b-a)
        secondary={"windowed_updates_per_s":fractions/(overlap_end-overlap_start),
                   "reciprocal_mean_sum_updates_per_s":sum(1/m for m in means)}
        assert all(math.isclose(v,test["secondary"][key],rel_tol=1e-12) for key,v in secondary.items())
        span_samples=[s for s in samples if start<=s[0]<=end]
        assert len(span_samples)==test["gpu"]["samples"]
        util=statistics.fmean(s[1] for s in span_samples)
        peak=max(s[2] for s in span_samples)
        assert math.isclose(util,test["gpu"]["mean_util_gpu_pct"],abs_tol=1e-12)
        assert peak==test["gpu"]["max_memory_used_mib"]
        recomputed.append({"phase":phase,"k":k,"per_worker_mean_s":means,
            "fixed_work_span_s":end-start,"overlap_s":overlap_end-overlap_start,
            "primary_updates_per_s":rate,"primary_speedup":speedup,
            "descriptive_gpu_util_percent":util,"sample_count":len(span_samples),
            "nvml_peak_memory_used_MiB":peak,
            "peak_allocated_GB_per_worker":[w["peak_allocated_bytes"]/1e9 for w in test["workers"]],
            "worker_mean_slowdown_vs_phase_k1":[m/data["tests"][0 if phase==2 else 2]["per_worker_mean_s"][0] for m in means],
            "training_only_list_price_usd_per_update":(.000694+8*.0000131+64*.00000222)/rate,
            "secondary_reconciles":True})
        previous_end=end
    assert worker_count==7 and update_count==56
    assert recomputed[1]["primary_speedup"]>=1.5
    saved_apps=read(BASE/"packing-a100-v1-app-state.json")
    assert len(saved_apps)==1 and saved_apps[0]["app_id"]==APP and saved_apps[0]["state"]=="stopped" and int(saved_apps[0]["tasks"])==0
    assert read(BASE/"packing-a100-v1-independent-stop-verify.json")["verify_stopped"]=={"app_state":"stopped","app_containers":0,"verified":True}
    with ThreadPoolExecutor(max_workers=2) as pool:
        a,c=pool.submit(cli,"app"),pool.submit(cli,"container")
        apps,containers=a.result(),c.result()
    assert modal.__version__=="1.5.1"
    assert all("app_id" in r and "state" in r and "tasks" in r for r in apps)
    assert all("app_id" in r for r in containers)
    scoped_apps=[r for r in apps if r["app_id"]==APP]
    scoped_containers=[r for r in containers if r["app_id"]==APP]
    assert scoped_apps and all(r["state"].lower()=="stopped" and int(r["tasks"])==0 for r in scoped_apps)
    assert scoped_containers==[]
    lifecycle=dataclasses.asdict(get_app_lifecycle(APP))
    assert lifecycle["stopped_at"] is not None
    rows=modal.Workspace.from_context().billing.report(start=datetime(2026,10,6,tzinfo=timezone.utc),
         end=datetime(2026,10,7,tzinfo=timezone.utc),resolution="h")
    scoped=[r for r in rows if r.object_id==APP]
    total=sum((r.cost for r in scoped),Decimal(0))
    saved_billing=[r for r in read(BASE/"packing-a100-v1-billing-today-hourly.json") if r["object_id"]==APP]
    saved_total=sum((Decimal(r["cost"]) for r in saved_billing),Decimal(0))
    old=read(ROOT/"plans/reports/codex-261006-p2p5-v2-4e22bae-results-checks.json")
    for rel,sha in old["protected_v1_and_protocol_files_unchanged"].items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==sha,rel
    cadence=[b[0]-a[0] for a,b in zip(samples,samples[1:])]
    report.update(commit_files_byte_matched=len(paths),consumed_sha256=hashes,
        launch_source_sha256=source,run_manifest=meta,packing_sha256=hashlib.sha256((RUN/"result/packing.json").read_bytes()).hexdigest(),
        all_7_worker_records_and_56_update_rows_reconcile=True,recomputed_tests=recomputed,
        sampler_rows=len(samples),sampler_cadence_s={"min":min(cadence),"mean":statistics.fmean(cadence),"max":max(cadence)},
        sampler_exit=sampler["stop"],scoped_live_shutdown={"app_rows":scoped_apps,"container_rows":scoped_containers,"lifecycle":lifecycle},
        live_shutdown_verified=True,saved_reported_app_usage_usd=str(saved_total),
        current_reported_app_usage_usd=str(total),current_billing_rows=[dataclasses.asdict(r) for r in scoped],
        console_building_image_line_present="Building image" in console,
        reservation_retained_usd="1.98",separate_envelope_usd="2.00",
        protected_historical_bytes_unchanged=True,accepted_bounded_packing_result=True,
        pre_stated_reading="P2 k2 >=1.5 threshold met; merits a priced design if requested",
        campaign_estimate_validated=False,new_paid_work_cleared=False,
        limits=["Six measured updates per worker, seed99+rank, fixed-order single-host tests; no long-run, repeated-seed or campaign result.",
                "Source binds the FP32 training path; this test saves no tensors for a new gradient/correctness audit. GPU/campaign resume remains unverified.",
                "A100/L40S comparisons also change host, CPU/RAM allocation, thread settings and timing harness. They do not isolate a hardware effect.",
                "NVML kernel-active sampling is descriptive, not spatial occupancy or attribution of remaining time. Endpoints can overlap averaging windows.",
                "Training-only list-price cost/update omits startup, evaluation, control arms, readings, I/O, schedule/repack, build/reaper and failures.",
                "Summed observed P2 memory peaks advise against assuming k3/P2 fits, but that configuration was not tested.",
                "Reported app usage is an unsettled app-only snapshot; no Building image line does not prove settled zero build cost.",
                "Shutdown is verified only for this approved packing app, not every workspace experiment."],
        finished_at_utc=datetime.now(timezone.utc).isoformat())
    OUT.write_text(json.dumps(report,indent=2,default=str,allow_nan=False)+"\n")
    print(json.dumps({k:report[k] for k in ("accepted_bounded_packing_result","live_shutdown_verified",
        "recomputed_tests","current_reported_app_usage_usd","finished_at_utc")},indent=2))


if __name__=="__main__":
    main()
