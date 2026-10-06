"""P2.5 option B (user 21528): does packing k concurrent learned-training PROCESSES on one
GPU raise aggregate update throughput? DEV timing only: training-stream seeds 99+rank,
no accuracy, no registered/artifact/reserved population, not a registered timing.

    python scripts/sgm-p2p5-gpu-packing-concurrent-training-throughput-test.py --out <dir>

Fixed matrix, in order (learned arm, residual_head, Qwen3-0.6B, batch 16, N32, full-gradient
token-serial fp32 contract): P2 (train filler 40) k=1, P2 k=2, P1 (filler 0) k=1, P1 k=3.
Each worker is a separate process running the real `train()` for WARMUP + MEASURED
updates; after update 0 it waits at a file barrier until all k workers of its test got
there, so the measured updates overlap. Per worker: measured s/update, update end times,
peak allocation. Per test: overlap window of the measured updates, aggregate throughput
(sum of 1/mean s/update), speed-up vs the k=1 test of the same phase, and the mean
nvidia-smi utilization.gpu (time with >=1 kernel executing; descriptive) inside the window.
Every worker uses torch.set_num_threads(THREADS) so k does not change CPU threading.
The first failed test (OOM, error, barrier timeout) stops the matrix; status records it.
SIGKILL watchdog armed before anything else.
--smoke-cpu: $0 local check of the orchestration only (tiny random backbone on CPU, N4,
batch 2, no nvidia-smi); never a timing.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.p2d_launch_guard import Watchdog  # noqa: E402

TESTS = [(2, 1), (2, 2), (1, 1), (1, 3)]           # (phase, k)
PHASE_FILLER = {1: 0, 2: 40}
WARMUP, MEASURED, THREADS, SEED0 = 2, 6, 2, 99
WALL_S, TEST_TIMEOUT_S, BARRIER_S = 18 * 60, 7 * 60, 240
QUERY, LOOP_MS = "timestamp,utilization.gpu,memory.used", 500


def worker(phase: int, rank: int, k: int, barrier: Path, out: Path, smoke: bool = False) -> None:
    import ctypes
    ctypes.CDLL("libc.so.6").prctl(1, 9)             # PR_SET_PDEATHSIG = SIGKILL: die with the parent
    import torch
    from memsub.sgm.synthetic_pilot import PilotConfig, train
    torch.set_num_threads(THREADS)
    shape = (dict(backbone="tiny", device="cpu", n_bindings=4, batch=2) if smoke else
             dict(backbone="qwen3-0.6b-base", device="cuda", n_bindings=32, batch=16))
    pcfg = PilotConfig(arm="learned", readout="residual_head", lr=3e-3, steps=WARMUP + MEASURED, seed=SEED0 + rank,
                       eval_every=10 ** 9, filler_len_schedule=((0, PHASE_FILLER[phase]),), **shape)
    rows = []

    def on_update(update: int, seconds: float) -> None:
        rows.append({"update": update, "seconds": seconds, "t_end": time.time()})
        if update == 0:                               # barrier: measured updates of all k overlap
            (barrier / f"ready-{rank}").touch()
            t0 = time.monotonic()
            while len(list(barrier.glob("ready-*"))) < k:
                if time.monotonic() - t0 > BARRIER_S:
                    raise TimeoutError("barrier timeout")
                time.sleep(0.05)
            rows[-1]["barrier_release"] = time.time()
    train(pcfg, log=lambda _r: None, on_update=on_update)
    measured = [r for r in rows if r["update"] >= WARMUP]
    out.write_text(json.dumps({"phase": phase, "rank": rank, "k": k, "seed": SEED0 + rank, "updates": rows,
                               "mean_measured_s": sum(r["seconds"] for r in measured) / len(measured),
                               "measured_start": rows[WARMUP - 1]["t_end"], "measured_end": measured[-1]["t_end"],
                               "peak_allocated_bytes": 0 if smoke else torch.cuda.max_memory_allocated()}))


def run_test(phase: int, k: int, out: Path, smoke: bool = False) -> dict:
    d = out / f"p{phase}-k{k}"
    (d / "barrier").mkdir(parents=True)
    procs = [subprocess.Popen([sys.executable, "-u", __file__, "--worker", str(phase), str(r), str(k),
                               str(d / "barrier"), str(d / f"worker-{r}.json")] + (["smoke"] if smoke else []),
                              stdout=open(d / f"worker-{r}.log", "w"), stderr=subprocess.STDOUT, cwd=ROOT)
             for r in range(k)]
    deadline, rcs = time.monotonic() + TEST_TIMEOUT_S, []
    for p in procs:
        try:
            rcs.append(p.wait(timeout=max(1.0, deadline - time.monotonic())))
        except subprocess.TimeoutExpired:
            rcs.append("timeout")
    for p in procs:                                   # nothing outlives its test
        if p.poll() is None:
            p.kill()
            p.wait()
    res = {"phase": phase, "k": k, "worker_exit": rcs}
    if any(rc != 0 for rc in rcs):
        res["status"] = "failed"
        return res
    w = [json.loads((d / f"worker-{r}.json").read_text()) for r in range(k)]
    start, end = max(x["measured_start"] for x in w), min(x["measured_end"] for x in w)
    res.update(status="ok", workers=w, overlap_window=[start, end], overlap_s=end - start,
               per_worker_mean_s=[x["mean_measured_s"] for x in w],
               aggregate_updates_per_s=sum(1.0 / x["mean_measured_s"] for x in w),
               peak_allocated_bytes=[x["peak_allocated_bytes"] for x in w])
    return res


def stop_sampler(sampler) -> str:
    """Contained (same rule as the v2 runner, codex 21506): never raises."""
    if sampler is None:
        return "not started"
    try:
        sampler.terminate()
        sampler.wait(timeout=10)
    except Exception as e:
        try:
            sampler.kill()
            sampler.wait(timeout=5)
        except Exception as e2:
            return f"kill/reap error {e2!r:.120} after {e!r:.120}"
    return f"exited rc {sampler.returncode}"


def gpu_util(csv_path: Path, window: list) -> dict:
    import datetime as dt
    vals = []
    for line in csv_path.read_text().splitlines():
        parts = [x.strip() for x in line.split(",")]
        try:
            ts = dt.datetime.strptime(parts[0], "%Y/%m/%d %H:%M:%S.%f").replace(tzinfo=dt.timezone.utc).timestamp()
            if window[0] <= ts <= window[1]:
                vals.append((float(parts[1]), float(parts[2])))
        except (ValueError, IndexError):
            continue
    return {"samples": len(vals), "mean_util_gpu_pct": sum(v[0] for v in vals) / len(vals) if vals else None,
            "max_memory_used_mib": max((v[1] for v in vals), default=None)}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), Path(sys.argv[5]), Path(sys.argv[6]),
               smoke=sys.argv[7:] == ["smoke"])
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--smoke-cpu", action="store_true")
    args = ap.parse_args()
    watchdog = Watchdog(WALL_S)                      # armed before anything else
    report = {"status": "running"}
    try:
        args.out.mkdir(parents=True, exist_ok=False)
        import torch
        from memsub.sgm.synthetic_pilot_run import source_tree_sha256
        report.update(purpose="DEV packing throughput test (option B); not a registered timing",
                      gpu="smoke-cpu" if args.smoke_cpu else torch.cuda.get_device_name(0), torch=torch.__version__,
                      memsub_source_sha256=source_tree_sha256(ROOT / "memsub"), tests=[],
                      sampler={"query": QUERY, "loop_ms": LOOP_MS, "start_epoch": time.time(),
                               "tz": time.strftime("%Z"), "utc_offset_s": -time.timezone})
        csv_path = args.out / "gpu-util.csv"
        sampler = None if args.smoke_cpu else subprocess.Popen(
            ["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader,nounits", f"--loop-ms={LOOP_MS}",
             f"--filename={csv_path}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for phase, k in TESTS:
                res = run_test(phase, k, args.out, smoke=args.smoke_cpu)
                report["tests"].append(res)
                (args.out / "packing.json").write_text(json.dumps(report, indent=2))
                print(json.dumps({x: res.get(x) for x in ("phase", "k", "status", "per_worker_mean_s",
                                                          "aggregate_updates_per_s")}), flush=True)
                if res["status"] != "ok":
                    report["status"] = f"stopped: P{phase} k={k} failed"
                    break
            else:
                report["status"] = "complete"
        finally:
            report["sampler"]["stop"] = stop_sampler(sampler)
        base = {t["phase"]: t["aggregate_updates_per_s"] for t in report["tests"] if t["status"] == "ok" and t["k"] == 1}
        for t in report["tests"]:
            if t["status"] == "ok":
                t["gpu"] = gpu_util(csv_path, t["overlap_window"]) if csv_path.exists() else None
                if t["phase"] in base:
                    t["speedup_vs_k1"] = t["aggregate_updates_per_s"] / base[t["phase"]]
    except Exception as e:                           # recorded; nonzero exit
        report["status"] = f"error: {type(e).__name__}: {str(e)[:300]}"
    finally:
        watchdog.cancel()
    if args.out.exists():
        (args.out / "packing.json").write_text(json.dumps(report, indent=2))
    print(report["status"], flush=True)
    sys.exit(0 if report["status"] == "complete" else 1)


if __name__ == "__main__":
    main()
