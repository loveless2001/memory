"""Independent v2 artifact, progress, sampled utilization and cost arithmetic audit."""
import csv
import hashlib
import importlib.util
import json
import math
import os
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
EVID = BASE / "p2p5-l40s-profile-v2"
VOLUME = EVID / "volume-evidence/p2p5-l40s-profile-v2"
PROFILE = VOLUME / "profile-l40s/profile.json"
RUNNER = "modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile-v2-after-speedup.py"
OUT = ROOT / "plans/reports/codex-261006-p2p5-v2-4e22bae-results-checks.json"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read(path):
    return json.loads(path.read_text())


def frozen_files(commit, paths):
    hashes = {}
    for rel in paths:
        raw = (ROOT / rel).read_bytes()
        assert raw == subprocess.check_output(["git", "show", f"{commit}:{rel}"]), rel
        hashes[rel] = hashlib.sha256(raw).hexdigest()
    return hashes


def main():
    os.chdir(ROOT)
    changed = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "4e22bae"], text=True).splitlines()
    hashes = frozen_files("4e22bae", changed)
    launch_changed = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "9d1cfba"], text=True).splitlines()
    launch_hashes = frozen_files("9d1cfba", launch_changed)
    original_rel = str((BASE / "p2p5-l40s-profile-v1").relative_to(ROOT))
    protected = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "2fda0d4", original_rel], text=True).splitlines()
    protected += [str((BASE / "prereg.md").relative_to(ROOT)), "configs/m4_sgm_p2p5_grid.json"]
    protected_hashes = frozen_files("2fda0d4", protected)
    run = load(ROOT / RUNNER, "codex_v2_terminal_runner")
    prov, profile, collect = read(EVID / "launch_provenance.json"), read(PROFILE), read(EVID / "collect_status.json")
    first = read(EVID / "collect_status.first-terminal-shutdown-unresolved.json")
    exit_record = read(VOLUME / "profile-l40s.exit.json")
    progress = [json.loads(s) for s in (PROFILE.parent / "progress.jsonl").read_text().splitlines()]
    assert run.expected_identity() == prov["expected_identity"]
    assert prov["expected_identity"] == {
        "runner":"31e16ed24118c40f60da0341a99016e5db55ece3eb02b2083414a74f25df4f87",
        "profile_script":"b5b0746a40afbd7c9feb2bcf7aa6967189903673829cf2a8d4a2afc25237a08c",
        "reaper_logic":"32bb3a3a38bf375e4c9107e4b3d7dc4c6392076cb5ba55f7c599fab644329e6c",
        "memsub":"b87a767baac578d94a6f778560f4fb451fd60679cca48412218adaac74f74085"}
    assert profile["contract"] == "full-gradient token-serial, fp32, TF32 off, batch 16, N32, seed 99"
    assert profile["environment"]["torch"] == "2.7.1+cu126" and profile["environment"]["tf32_matmul"] is False
    assert prov["git_head"] == "8db8520c3428b4e2a08a37f8b9b4a8efc32113a4"
    assert hashlib.sha256(PROFILE.read_bytes()).hexdigest() == "ff2a7a437a3a1ae43d8c720522ff97e130650d82b2035d6c69efbc95083f862b"
    assert exit_record["child_exit"] == 0 and exit_record["stderr_tail"] == ""
    assert collect["result"]["profile"] == first["result"]["profile"] == profile
    assert collect["poll"] == "result" and collect["result"]["status"] == "profiled"
    usable, reason = run.profile_usable(profile, 0, prov["expected_identity"]["memsub"])
    assert usable and collect["usable"] and collect["usable_reason"] == reason
    assert collect["final_shutdown"]["status"] == "stopped_verified"
    assert first["final_shutdown"]["status"] == "shutdown_unresolved"
    assert first["final_shutdown"]["verification"]["verified"] is False
    assert read(EVID / "independent-stop-verify.json")["verify_stopped"] == {
        "app_state": "stopped", "app_containers": 0, "verified": True}
    assert Counter(r["stage"] for r in progress) == {"start":1,"config_start":4,"update_done":40,"dev_eval_done":4,"end":1}
    assert all(a["t"] <= b["t"] for a,b in zip(progress,progress[1:]))
    assert progress[-1]["status"] == "complete"
    assert 0 < profile["wall_s"] < 1800
    assert abs(progress[-1]["t"] - progress[0]["t"] - profile["wall_s"]) < 1
    assert prov["spawn_epoch"] < progress[0]["t"] < progress[-1]["t"] < prov["deadline_epoch"]
    sampler = exit_record["gpu_sampler"]
    assert sampler["returncode"] == 0 and sampler["status"] == "exited" and sampler["steps"] == ["terminate"]
    assert sampler["loop_ms"] == 500 and sampler["tz_name"] == "UTC" and sampler["utc_offset_s"] == 0
    assert sampler["query"] == "timestamp,utilization.gpu,utilization.memory,memory.used"
    samples = []
    for row in csv.reader((VOLUME / "profile-l40s.gpu-util.csv").read_text().splitlines()):
        assert len(row) == 4, row
        t = datetime.strptime(row[0].strip(), "%Y/%m/%d %H:%M:%S.%f").replace(tzinfo=timezone.utc).timestamp()
        gpu, mem, used = [float(s.strip()) for s in row[1:]]
        assert all(math.isfinite(v) for v in (t,gpu,mem,used))
        assert 0 <= gpu <= 100 and 0 <= mem <= 100 and used >= 0
        samples.append((t,gpu,mem,used))
    assert len(samples) == 698 and all(a[0] < b[0] for a,b in zip(samples,samples[1:]))
    assert sampler["start_epoch"] <= samples[0][0] < samples[-1][0] <= sampler["end_epoch"]
    old = read(BASE / "p2p5-l40s-profile-v1/volume-evidence/p2p5-l40s-profile-v1/profile-l40s/profile.json")
    old_cfg = {(c["arm"],c["phase"]):c for c in old["configs"]}
    recomputed, expected_stages = [], ["start"]
    for cfg in profile["configs"]:
        key = (cfg["arm"],cfg["phase"])
        rows = [r for r in progress if (r.get("arm"),r.get("phase")) == key]
        assert [r["stage"] for r in rows] == ["config_start"] + ["update_done"]*10 + ["dev_eval_done"]
        updates = rows[1:11]
        assert [r["update"] for r in updates] == list(range(10))
        assert [r["seconds"] for r in updates] == cfg["warmup_s"] + cfg["measured_s"]
        assert max(r["peak_allocated_bytes"] for r in updates) == cfg["peak_train_memory_bytes"]
        assert rows[-1]["seconds"] == cfg["dev_eval_batch_s"]
        mean = statistics.fmean(cfg["measured_s"])
        assert math.isclose(mean,cfg["mean_measured_s_per_update"],abs_tol=1e-12)
        assert 0 < cfg["peak_train_memory_bytes"] <= cfg["peak_memory_bytes"] < profile["environment"]["gpu_total_bytes"]
        intervals = [(r["t"]-r["seconds"],r["t"]) for r in updates[2:]]
        measured = [s for s in samples if any(a<=s[0]<=b for a,b in intervals)]
        dev = rows[-1]
        dev_samples = [s for s in samples if dev["t"]-dev["seconds"]<=s[0]<=dev["t"]]
        assert measured and dev_samples
        recomputed.append({"arm":key[0],"phase":key[1],"mean_update_s":mean,
            "range_update_s":[min(cfg["measured_s"]),max(cfg["measured_s"])],
            "v1_over_v2_update_ratio":old_cfg[key]["mean_measured_s_per_update"]/mean,
            "peak_allocated_GB":cfg["peak_memory_bytes"]/1e9,
            "peak_allocated_identical_to_v1":cfg["peak_memory_bytes"]==old_cfg[key]["peak_memory_bytes"],
            "dev_batch_s":cfg["dev_eval_batch_s"],"measured_sample_count":len(measured),
            "measured_gpu_util_percent_mean":statistics.fmean(s[1] for s in measured),
            "measured_nvml_used_MiB_max":max(s[3] for s in measured),
            "dev_sample_count":len(dev_samples),"dev_gpu_util_percent_mean":statistics.fmean(s[1] for s in dev_samples)})
        expected_stages += ["config_start"] + ["update_done"]*10 + ["dev_eval_done"]
    assert [r["stage"] for r in progress] == expected_stages + ["end"]
    assert not any(s in json.dumps(profile).lower() for s in ("accuracy","train_acc","predictions"))
    led = load(ROOT / "scripts/sgm-p2p5-campaign-ledger-from-l40s-profile.py", "codex_v2_ledger")
    led.PROFILE, led.RUNNER = PROFILE, RUNNER
    led.ARTIFACT_EVAL_BATCHES, led.ARTIFACT_EVAL_BATCHES_MEMORY_OFF = 52, 20
    saved = read(EVID / "campaign-ledger-from-profile-v2-52-20.json")
    assert led.ledger() == saved
    grid = read(ROOT / "configs/m4_sgm_p2p5_grid.json")
    base = grid["base"]
    assert base["filler_len_schedule"] == [[0,0],[1000,40]] and base["steps"] == 1500
    assert base["n_queries"] == 4 and base["eval_every"] == 100 and base["eval_batches"] == 4
    universe = [(b["override"]["arm"],n,s) for b in grid["blocks"] for n in b["n_bindings"] for s in b["seeds"]]
    assert len(universe) == len(set(universe)) == 18
    assert Counter(a for a,n,s in universe) == {"learned":4,"single_cell":4,"random_fixed":4,"memory_off":4,"oracle":2}
    cfgs = {(c["arm"],c["phase"]):c for c in profile["configs"]}
    rate = .000542 + 4*.0000131 + 32*.00000222
    independent = {}
    for basis,factor in (("bound",1.4),("estimate",1.0)):
        times, reading_compute = [], 0.0
        for arm,n,s in universe:
            timing_arm = "memory_off" if arm == "memory_off" else "learned"
            a,b = cfgs[(timing_arm,1)],cfgs[(timing_arm,2)]
            scale0,scale40 = ((2*n+8)/72,(2*n+48)/112) if basis=="estimate" else (1,1)
            training = 1000*statistics.fmean(a["measured_s"])*scale0 + 500*statistics.fmean(b["measured_s"])*scale40
            evaluation = max(a["dev_eval_batch_s"],b["dev_eval_batch_s"])*scale40
            wall = training + (64+(20 if arm=="memory_off" else 52))*evaluation + 300
            times.append(wall*factor+(240 if basis=="bound" else 0))
            for population in ([32,16] if arm=="oracle" else [n]):
                scale = (2*population+48)/112 if basis=="estimate" else 1
                reading_compute += (16 if arm=="memory_off" else 48)*max(a["dev_eval_batch_s"],b["dev_eval_batch_s"])*scale
        reading_time = (reading_compute*1.1+300)*factor
        reaper = math.ceil(max(round(t,1) for t in times)/120+2)*110*(.125*.0000131+.25*.00000222)
        total = sum(times)*rate + reading_time*rate + .168384 + reaper + (5 if basis=="bound" else 0)
        assert math.isclose(total,saved["bases"][basis]["total_usd"],abs_tol=1e-10)
        assert math.isclose(sum(times)/3600,saved["bases"][basis]["cell_gpu_hours"],abs_tol=1e-10)
        independent[basis] = {"total_usd":total,"cell_gpu_hours":sum(times)/3600,
            "longest_cell_life_h":max(round(t,1) for t in times)/3600,"readings_s":reading_time}
    led.PROFILE = BASE / "p2p5-l40s-profile-v1/volume-evidence/p2p5-l40s-profile-v1/profile-l40s/profile.json"
    led.RUNNER = "modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py"
    old_at_52_20 = {k:v["total_usd"] for k,v in led.ledger()["bases"].items()}
    led.ARTIFACT_EVAL_BATCHES = led.ARTIFACT_EVAL_BATCHES_MEMORY_OFF = 16
    assert led.ledger() == read(BASE / "p2p5-l40s-profile-v1/campaign-ledger-from-profile.json")
    live = read(ROOT / "plans/reports/codex-261006-p2p5-v2-4e22bae-live-terminal.json")
    assert live["shutdown_verified"] and live["app_id"] == prov["deployed_app_id"]
    cadence = [b[0]-a[0] for a,b in zip(samples,samples[1:])]
    report = {"checked_at_utc":datetime.now(timezone.utc).isoformat(),"evidence_commit":"4e22bae",
        "commit_files_byte_matched":len(changed),"consumed_file_sha256":hashes,
        "launch_commit_files_byte_matched":len(launch_changed),"launch_file_sha256":launch_hashes,
        "protected_v1_and_protocol_files_unchanged":protected_hashes,
        "identity_matches_frozen_launch":True,"profile_usable":usable,"usable_reason":reason,
        "profile_wall_s":profile["wall_s"],"all_40_update_and_4_dev_rows_reconcile":True,
        "recomputed_configs":recomputed,"sampler_exit":sampler,
        "sampler_rows":len(samples),"sampler_cadence_s":{"min":min(cadence),"mean":statistics.fmean(cadence),"max":max(cadence)},
        "first_terminal_shutdown":first["final_shutdown"],"final_collector_shutdown":collect["final_shutdown"],
        "first_unresolved_cause_not_determined_from_retained_fields":True,
        "live_shutdown_verified":True,"reported_app_usage_usd":live["reported_app_usage_usd"],
        "ledger_reexecution_matches_saved_output":True,"independent_ledger_arithmetic":independent,
        "v1_52_20_comparable_totals_usd":old_at_52_20,"original_v1_16_16_ledger_reproduced":True,
        "timing_profile_accepted":True,"campaign_or_packing_cleared":False,"paid_work_performed":False,
        "limits":["Eight measured updates per config at N32, seed99; separate v1/v2 runs, v2 adds sampler with unmeasured overhead.",
            "NVML GPU utilization samples are descriptive; no demonstrated CPU cause, SM occupancy or concurrency headroom. Windows inferred from completion timestamp minus recorded duration.",
            "The ledger uses proxies for controls/N16, assumes startup, eval, build and one-reaper topology; 1.4x plus margins is not a validated future execution bound.",
            "Resume verified only on CPU; GPU and actual campaign-consumer integration remain unverified. No preemption retries priced.",
            "Billing is an app-only snapshot; retain $2.3844246 reservation in the separate $3 envelope."]}
    OUT.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:report[k] for k in ("timing_profile_accepted","live_shutdown_verified","commit_files_byte_matched",
        "recomputed_configs","independent_ledger_arithmetic","v1_52_20_comparable_totals_usd")},indent=2))


if __name__ == "__main__":
    main()
