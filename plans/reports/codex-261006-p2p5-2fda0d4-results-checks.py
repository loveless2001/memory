"""Independent terminal artifact/progress and campaign arithmetic audit; no paid work."""
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
COMMIT = "2fda0d42c8566875af355dc97db2fdc3bac743d1"
FOLDER = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
EVID = FOLDER / "p2p5-l40s-profile-v1"
PROFILE = EVID / "volume-evidence/p2p5-l40s-profile-v1/profile-l40s/profile.json"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    os.chdir(ROOT)
    changed = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", COMMIT], text=True).splitlines()
    hashes = {}
    for name in changed:
        path = ROOT / name
        raw = path.read_bytes()
        assert raw == subprocess.check_output(["git", "show", f"{COMMIT}:{name}"])
        hashes[name] = hashlib.sha256(raw).hexdigest()
    runner = load(ROOT / "modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py", "codex_terminal_runner")
    prov = json.loads((EVID / "launch_provenance.json").read_text())
    profile = json.loads(PROFILE.read_text())
    collect = json.loads((EVID / "collect_status.json").read_text())
    exit_record = json.loads((EVID / "volume-evidence/p2p5-l40s-profile-v1/profile-l40s.exit.json").read_text())
    progress = [json.loads(row) for row in (PROFILE.parent / "progress.jsonl").read_text().splitlines()]
    assert runner.expected_identity() == prov["expected_identity"]
    assert prov["expected_identity"] == json.loads((ROOT / "plans/reports/codex-261006-p2p5-508443c-build-checks.json").read_text())["identity"]
    assert exit_record["child_exit"] == 0 and not exit_record["stderr_tail"]
    assert collect["result"]["profile"] == profile
    assert collect["poll"] == "result" and collect["result"]["status"] == "profiled"
    assert collect["result"]["child_exit"] == exit_record["child_exit"]
    usable, reason = runner.profile_usable(profile, exit_record["child_exit"], prov["expected_identity"]["memsub"])
    assert usable and collect["usable"] and collect["usable_reason"] == reason
    assert Counter(row["stage"] for row in progress) == {"start": 1, "config_start": 4, "update_done": 40, "dev_eval_done": 4, "end": 1}
    assert all(a["t"] <= b["t"] for a, b in zip(progress, progress[1:]))
    assert 0 < profile["wall_s"] < 1800 and abs(progress[-1]["t"] - progress[0]["t"] - profile["wall_s"]) < 1
    assert progress[0]["stage"] == "start" and progress[-1]["status"] == "complete"
    expected_stages = ["start"]
    recomputed = []
    for cfg in profile["configs"]:
        rows = [r for r in progress if (r.get("arm"), r.get("phase")) == (cfg["arm"], cfg["phase"])]
        assert [r["stage"] for r in rows] == ["config_start"] + ["update_done"] * 10 + ["dev_eval_done"]
        updates = rows[1:11]
        assert [r["update"] for r in updates] == list(range(10))
        assert [r["seconds"] for r in updates] == cfg["warmup_s"] + cfg["measured_s"]
        assert max(r["peak_allocated_bytes"] for r in updates) == cfg["peak_train_memory_bytes"]
        assert rows[-1]["seconds"] == cfg["dev_eval_batch_s"]
        mean = statistics.fmean(cfg["measured_s"])
        assert math.isclose(mean, cfg["mean_measured_s_per_update"], abs_tol=1e-12)
        assert 0 < cfg["peak_train_memory_bytes"] <= cfg["peak_memory_bytes"] < profile["environment"]["gpu_total_bytes"]
        recomputed.append({"arm": cfg["arm"], "phase": cfg["phase"], "mean_s": mean,
                           "min_measured_s": min(cfg["measured_s"]), "max_measured_s": max(cfg["measured_s"]),
                           "peak_GB_decimal": cfg["peak_memory_bytes"] / 1e9,
                           "peak_GiB": cfg["peak_memory_bytes"] / 2**30,
                           "dev_batch_s": cfg["dev_eval_batch_s"]})
        expected_stages += ["config_start"] + ["update_done"] * 10 + ["dev_eval_done"]
    assert [r["stage"] for r in progress] == expected_stages + ["end"]
    assert not any(word in json.dumps(profile).lower() for word in ("accuracy", "train_acc", "predictions"))
    live = json.loads((ROOT / "plans/reports/codex-261006-p2p5-2fda0d4-live-terminal.json").read_text())
    assert live["shutdown_verified"] and live["app_id"] == prov["deployed_app_id"]
    assert collect["final_shutdown"]["app_id"] == live["app_id"]
    assert collect["final_shutdown"]["status"] == "stopped_verified"
    assert not collect["final_shutdown"]["verification"]["app_containers"]
    assert prov["spawn_epoch"] < progress[0]["t"] < progress[-1]["t"] < prov["deadline_epoch"]

    led_path = ROOT / "scripts/sgm-p2p5-campaign-ledger-from-l40s-profile.py"
    led_module = load(led_path, "codex_campaign_arithmetic")
    saved_ledger = json.loads((EVID / "campaign-ledger-from-profile.json").read_text())
    assert led_module.ledger() == saved_ledger  # no OUT write; original bytes retained
    grid_path = ROOT / "configs/m4_sgm_p2p5_grid.json"
    grid = json.loads(grid_path.read_text())
    universe = [(b["override"]["arm"], n, seed) for b in grid["blocks"] for n in b["n_bindings"] for seed in b["seeds"]]
    assert len(universe) == 18 and len(set(universe)) == 18
    assert Counter(a for a, n, s in universe) == {"learned":4,"single_cell":4,"random_fixed":4,"memory_off":4,"oracle":2}
    prices = {"L40S_per_s": .000542, "CPU_core_per_s": .0000131, "RAM_GiB_per_s": .00000222}
    rate = prices["L40S_per_s"] + 4 * prices["CPU_core_per_s"] + 32 * prices["RAM_GiB_per_s"]
    configs = {(c["arm"],c["phase"]):c for c in profile["configs"]}
    independent = {}
    for basis, factor in (("bound", 1.4), ("estimate", 1.0)):
        times, reading_compute = [], 0.0
        for arm, n, seed in universe:
            proxy = "memory_off" if arm == "memory_off" else "learned"
            first, second = configs[(proxy,1)], configs[(proxy,2)]
            scale0, scale40 = ((2*n+8)/72, (2*n+48)/112) if basis == "estimate" else (1,1)
            train_s = 1000 * statistics.fmean(first["measured_s"]) * scale0 + 500 * statistics.fmean(second["measured_s"]) * scale40
            eval_s = max(first["dev_eval_batch_s"], second["dev_eval_batch_s"]) * scale40
            wall = train_s + (64 + 16) * eval_s + 300
            times.append(wall*factor + (240 if basis == "bound" else 0))
            for population_n in ([32,16] if arm == "oracle" else [n]):
                pop_scale = (2*population_n+48)/112 if basis == "estimate" else 1
                reading_compute += (16 if arm == "memory_off" else 48) * max(first["dev_eval_batch_s"], second["dev_eval_batch_s"]) * pop_scale
        readings = (reading_compute*1.1+300)*factor
        reaper = math.ceil(max(round(t,1) for t in times)/120+2)*110*(.125*.0000131+.25*.00000222)
        total = sum(times)*rate + readings*rate + .168384 + reaper + (5 if basis == "bound" else 0)
        assert math.isclose(total,saved_ledger["bases"][basis]["total_usd"],abs_tol=1e-10)
        assert math.isclose(sum(times)/3600,saved_ledger["bases"][basis]["cell_gpu_hours"],abs_tol=1e-10)
        assert len(saved_ledger["bases"][basis]["cells"]) == 18
        independent[basis] = {"total_usd":total,"cell_gpu_hours":sum(times)/3600,"readings_s":readings}
    for p in [grid_path, FOLDER/"prereg.md", ROOT/"modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py",ROOT/"scripts/sgm-p2p5-local-gpu-timing-profile.py", ROOT/"modal-runners/modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py"]:
        hashes[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    report = {"checked_at_utc":datetime.now(timezone.utc).isoformat(),"evidence_commit":COMMIT,
              "commit_files_byte_matched":len(changed),"consumed_file_sha256":hashes,
              "profile_usable":usable,"usable_reason":reason,"all_40_update_rows_and_4_dev_rows_reconcile":True,
              "profile_wall_s":profile["wall_s"],"recomputed_configs":recomputed,
              "ledger_reexecution_matches_saved_output":True,"independent_ledger_arithmetic":independent,
              "rates_verified_against":"https://modal.com/pricing","prices":prices,
              "profile_accepted":True,"campaign_cap_cleared":False,"paid_work":False,
              "limits":["Only two arms at N32, 8 measured updates each; no long-run or control-arm/N16 timing validation",
                        "Two filler points determine a line; they do not establish linear scaling at N16",
                        "Campaign bound is a planning reserve with proxies, not a measured upper bound",
                        "Campaign artifact eval workload, parity work, reaper lifetime/concurrency, and I/O costs need actual runner binding"]}
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
