"""P2.5 option B (user 21528): does packing k concurrent learned-training PROCESSES on one
GPU raise aggregate update throughput? DEV timing only: training-stream seeds 99+rank,
no accuracy, no registered/artifact/reserved population, not a registered timing.

    python scripts/sgm-p2p5-gpu-packing-concurrent-training-throughput-test.py --out <dir>

Fixed matrix, in order (learned arm, residual_head, Qwen3-0.6B, batch 16, N32, full-gradient
token-serial fp32 contract): P2 (train filler 40) k=1, P2 k=2, P1 (filler 0) k=1, P1 k=3.
Each worker is a separate process running the real `train()` for WARMUP + MEASURED
updates; after the FINAL warmup update it waits at a file barrier until all k workers of
its test got there, so the measured updates start together (measured start = release).
PRIMARY (codex 21532): fixed-work rate = k x MEASURED complete updates / (latest measured
finish - earliest measured start); speed-up = that rate / the k=1 rate of the same phase.
SECONDARY, labelled estimates only: fractional updates inside the common overlap window
(assumes uniform work within an update) and the sum of reciprocal worker means.
Success needs strictly valid worker records (rank/phase/k/seed/update matrix, finite
positive times, increasing ends, span/mean consistency) and a positive overlap.
nvidia-smi utilization.gpu (time with >=1 kernel executing) over the fixed-work span is
descriptive. Every worker uses torch.set_num_threads(THREADS); workers arm
PR_SET_PDEATHSIG and verify their parent; any started worker is killed in a `finally`.
The first failed test stops the matrix. SIGKILL watchdog armed before anything else.
--smoke-cpu: $0 orchestration check only (tiny backbone on CPU, N4, batch 2, no nvidia-smi).
"""

import argparse
import json
import math
import os
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


def arm_parent_death(expected_ppid: int) -> None:
    """PR_SET_PDEATHSIG=SIGKILL, checked; then close the race with a getppid check."""
    import ctypes
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if libc.prctl(1, 9, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_PDEATHSIG) failed")
    if os.getppid() != expected_ppid:
        raise SystemExit(f"parent {expected_ppid} already gone (ppid {os.getppid()})")


def worker(phase: int, rank: int, k: int, barrier: Path, out: Path, parent: int, smoke: bool) -> None:
    arm_parent_death(parent)
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
        if update == WARMUP - 1:                      # barrier AFTER the final warmup: aligned starts
            (barrier / f"ready-{rank}").touch()
            t0 = time.monotonic()
            while len(list(barrier.glob("ready-*"))) < k:
                if time.monotonic() - t0 > BARRIER_S:
                    raise TimeoutError("barrier timeout")
                time.sleep(0.02)
            rows[-1]["barrier_release"] = time.time()
    train(pcfg, log=lambda _r: None, on_update=on_update)
    measured = [r for r in rows if r["update"] >= WARMUP]
    out.write_text(json.dumps({"phase": phase, "rank": rank, "k": k, "seed": SEED0 + rank, "updates": rows,
                               "mean_measured_s": sum(r["seconds"] for r in measured) / len(measured),
                               "measured_start": rows[WARMUP - 1]["barrier_release"],
                               "measured_end": measured[-1]["t_end"],
                               "peak_allocated_bytes": 0 if smoke else torch.cuda.max_memory_allocated()}))


def validate_workers(w: list, phase: int, k: int) -> str | None:
    """Strict record check; None = valid."""
    if sorted(x["rank"] for x in w) != list(range(k)):
        return "worker ranks differ from 0..k-1"
    for x in w:
        ups, r = x["updates"], x["rank"]
        if x["phase"] != phase or x["k"] != k or x["seed"] != SEED0 + r:
            return f"rank {r}: phase/k/seed mismatch"
        if [u["update"] for u in ups] != list(range(WARMUP + MEASURED)):
            return f"rank {r}: update ids {[u['update'] for u in ups]}"
        if not all(isinstance(u["seconds"], (int, float)) and math.isfinite(u["seconds"]) and u["seconds"] > 0
                   and isinstance(u["t_end"], (int, float)) and math.isfinite(u["t_end"]) for u in ups):
            return f"rank {r}: non-finite or non-positive update timing"
        if any(b["t_end"] <= a["t_end"] for a, b in zip(ups, ups[1:])):
            return f"rank {r}: update end times not increasing"
        fin = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        if not (fin(x["mean_measured_s"]) and x["mean_measured_s"] > 0 and fin(x["measured_start"])
                and fin(x["measured_end"])):                 # codex 21535: NaN compares false below
            return f"rank {r}: non-finite or non-positive mean / measured start / end"
        rel = ups[WARMUP - 1].get("barrier_release")
        if not isinstance(rel, (int, float)) or x["measured_start"] != rel or not rel >= ups[WARMUP - 1]["t_end"]:
            return f"rank {r}: measured start is not the barrier release after the final warmup"
        meas = [u["seconds"] for u in ups[WARMUP:]]
        span = x["measured_end"] - x["measured_start"]
        if x["measured_end"] != ups[-1]["t_end"] or abs(x["mean_measured_s"] - sum(meas) / len(meas)) > 1e-9:
            return f"rank {r}: measured end / mean inconsistent with the update rows"
        if not (0 < sum(meas) <= span + 1e-3 and span - sum(meas) <= max(1.0, 0.1 * span)):
            return f"rank {r}: span {span:.3f}s inconsistent with summed update time {sum(meas):.3f}s"
    return None


def window_updates(workers: list, start: float, end: float) -> float:
    """SECONDARY: fractional measured updates of all workers inside [start, end]."""
    total = 0.0
    for x in workers:
        for u in x["updates"][WARMUP:]:
            a, b = u["t_end"] - u["seconds"], u["t_end"]
            total += max(0.0, min(b, end) - max(a, start)) / (b - a)
    return total


def summarize(w: list, phase: int, k: int) -> dict:
    problem = validate_workers(w, phase, k)
    if problem:
        return {"status": "failed", "problem": problem}
    s_min, s_max = min(x["measured_start"] for x in w), max(x["measured_start"] for x in w)
    e_min, e_max = min(x["measured_end"] for x in w), max(x["measured_end"] for x in w)
    out = {"per_worker_mean_s": [x["mean_measured_s"] for x in w], "workers": w,
           "peak_allocated_bytes": [x["peak_allocated_bytes"] for x in w],
           "fixed_work_span": [s_min, e_max], "overlap_window": [s_max, e_min], "overlap_s": e_min - s_max}
    if not e_min - s_max > 0:
        return {**out, "status": "failed", "problem": f"non-positive overlap {e_min - s_max:.3f}s"}
    return {**out, "status": "ok", "fixed_work_updates_per_s": k * MEASURED / (e_max - s_min),
            "secondary": {"windowed_updates_per_s": window_updates(w, s_max, e_min) / (e_min - s_max),
                          "reciprocal_mean_sum_updates_per_s": sum(1.0 / x["mean_measured_s"] for x in w)}}


def worker_cmd(phase: int, r: int, k: int, d: Path, smoke: bool) -> list:
    return [sys.executable, "-u", str(Path(__file__).resolve()), "--worker", str(phase), str(r), str(k),
            str(d / "barrier"), str(d / f"worker-{r}.json"), str(os.getpid())] + (["smoke"] if smoke else [])


def run_test(phase: int, k: int, out: Path, smoke: bool = False, cmd=worker_cmd) -> dict:
    d = out / f"p{phase}-k{k}"
    (d / "barrier").mkdir(parents=True)
    procs, rcs = [], []
    try:
        for r in range(k):
            with open(d / f"worker-{r}.log", "w") as log:
                procs.append(subprocess.Popen(cmd(phase, r, k, d, smoke), stdout=log, stderr=subprocess.STDOUT,
                                              cwd=ROOT))
        deadline = time.monotonic() + TEST_TIMEOUT_S
        for p in procs:
            try:
                rcs.append(p.wait(timeout=max(0.1, deadline - time.monotonic())))
            except subprocess.TimeoutExpired:
                rcs.append("timeout")
    except Exception as e:                             # launch/wait failure: recorded, cleaned below
        return {"phase": phase, "k": k, "worker_exit": rcs, "status": "failed", "problem": f"launch/wait {e!r:.200}"}
    finally:                                           # nothing started here outlives its test
        for p in procs:
            if p.poll() is None:
                p.kill()
                p.wait()
    res = {"phase": phase, "k": k, "worker_exit": rcs}
    if len(rcs) != k or any(rc != 0 for rc in rcs):
        return {**res, "status": "failed", "problem": "worker exit"}
    try:
        w = [json.loads((d / f"worker-{r}.json").read_text()) for r in range(k)]
        return {**res, **summarize(w, phase, k)}
    except (OSError, ValueError, KeyError, TypeError, IndexError) as e:
        return {**res, "status": "failed", "problem": f"worker records unusable: {e!r:.200}"}


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
        a = sys.argv
        worker(int(a[2]), int(a[3]), int(a[4]), Path(a[5]), Path(a[6]), int(a[7]), smoke=a[8:] == ["smoke"])
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--smoke-cpu", action="store_true")
    args = ap.parse_args()
    watchdog = Watchdog(WALL_S)                      # armed before anything else
    report, sampler = {"status": "running", "tests": []}, None
    try:
        args.out.mkdir(parents=True, exist_ok=False)
        import torch
        from memsub.sgm.synthetic_pilot_run import source_tree_sha256
        report.update(purpose="DEV packing throughput test (option B); not a registered timing",
                      gpu="smoke-cpu" if args.smoke_cpu else torch.cuda.get_device_name(0), torch=torch.__version__,
                      memsub_source_sha256=source_tree_sha256(ROOT / "memsub"),
                      sampler={"query": QUERY, "loop_ms": LOOP_MS, "start_epoch": time.time(),
                               "tz": time.strftime("%Z"), "utc_offset_s": -time.timezone})
        csv_path = args.out / "gpu-util.csv"
        if not args.smoke_cpu:
            sampler = subprocess.Popen(["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader,nounits",
                                        f"--loop-ms={LOOP_MS}", f"--filename={csv_path}"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for phase, k in TESTS:
            res = run_test(phase, k, args.out, smoke=args.smoke_cpu)
            report["tests"].append(res)
            (args.out / "packing.json").write_text(json.dumps(report, indent=2))
            print(json.dumps({x: res.get(x) for x in ("phase", "k", "status", "problem", "per_worker_mean_s",
                                                      "fixed_work_updates_per_s")}), flush=True)
            if res["status"] != "ok":
                report["status"] = f"stopped: P{phase} k={k} failed"
                break
        else:
            report["status"] = "complete"
        report["sampler"]["stop"] = stop_sampler(sampler)
        sampler = None
        base = {t["phase"]: t for t in report["tests"] if t["status"] == "ok" and t["k"] == 1}
        for t in report["tests"]:
            if t["status"] == "ok":
                t["gpu"] = gpu_util(csv_path, t["fixed_work_span"]) if csv_path.exists() else None
                if t["phase"] in base:
                    b = base[t["phase"]]
                    t["speedup_vs_k1"] = t["fixed_work_updates_per_s"] / b["fixed_work_updates_per_s"]
                    t["secondary"]["speedups_vs_k1"] = {
                        key: t["secondary"][key] / b["secondary"][key] for key in
                        ("windowed_updates_per_s", "reciprocal_mean_sum_updates_per_s")}
    except Exception as e:                           # recorded; nonzero exit
        report["status"] = f"error: {type(e).__name__}: {str(e)[:300]}"
    finally:
        if sampler is not None:
            report.setdefault("sampler", {})["stop"] = stop_sampler(sampler)
        watchdog.cancel()
    if args.out.exists():
        (args.out / "packing.json").write_text(json.dumps(report, indent=2))
    print(report["status"], flush=True)
    sys.exit(0 if report["status"] == "complete" else 1)


if __name__ == "__main__":
    main()
