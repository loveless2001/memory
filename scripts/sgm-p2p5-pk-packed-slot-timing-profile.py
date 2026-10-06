"""P2.5 Amendment PK §PK5 item T: packed (k = 2) timing for every slot type × phase.

    python scripts/sgm-p2p5-pk-packed-slot-timing-profile.py --out <dir> [--smoke-cpu]

Matrix from configs/m4_sgm_p2p5_packed_proof_grid.json "timing": 9 slot types (arm, N) × phases
{1: filler 0, 2: filler 40} = 18 configs, in order. Per config: k = 2 worker processes (seeds
99/100, threads 2) run the real `train()` for 2 warmup + 4 measured updates with the barrier
after the final warmup; then each worker times one dev-shaped eval batch (heldout, filler 40,
batch 16, intervention none) and one artifact-shaped batch (bank_derange; memory_off: none),
and the REAL terminal checkpoint (codex 21567 #4): captured by train()'s own on_checkpoint hook at
step == steps (after the last measured update, outside the throughput window; with the trained
AdamW moments), timed through torch.save + sha256, with its byte size and optimizer-state count.
The measurement, validation, fixed-work rate, sampler and cleanup are the AUDITED packing-test
functions (scripts/sgm-p2p5-gpu-packing-concurrent-training-throughput-test.py, imported
unchanged; only its MEASURED count is set to 4 here). The first failed config stops the matrix
(no ledger). DEV timing only: no accuracy is read; populations are the proof-only 8_800_000.
"""

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location(
    "packing", ROOT / "scripts/sgm-p2p5-gpu-packing-concurrent-training-throughput-test.py")
pk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pk)
GRID = json.loads((ROOT / "configs/m4_sgm_p2p5_packed_proof_grid.json").read_text())
T = GRID["timing"]
pk.WARMUP, pk.MEASURED = T["warmup"], T["measured"]          # 2 + 4 (the packing test used 2 + 6)
pk.THREADS = T["threads"]
DEV_POP = GRID["eval"]["dev_seed"]
WALL_S = 2200                  # inside the runner's 2280 s child bound / 2400 s function timeout


def worker(arm: str, n: int, phase: int, rank: int, k: int, barrier: Path, out: Path, parent: int,
           smoke: bool) -> None:
    pk.arm_parent_death(parent)
    import hashlib
    import io
    import torch
    from memsub.sgm.synthetic_pilot import PilotConfig, train
    from memsub.sgm.synthetic_pilot_evaluation import evaluate
    torch.set_num_threads(pk.THREADS)
    base = {**GRID["base"], "arm": arm, "n_bindings": n, "seed": pk.SEED0 + rank, "steps": pk.WARMUP + pk.MEASURED,
            "eval_every": 10 ** 9, "filler_len_schedule": [[0, int(T["phases"][str(phase)])]]}
    if smoke:
        base.update(backbone="tiny", device="cpu", n_bindings=4, batch=2)
    pcfg = PilotConfig(**base)
    rows = []

    def on_update(update: int, seconds: float) -> None:
        rows.append({"update": update, "seconds": seconds, "t_end": time.time()})
        if update == pk.WARMUP - 1:
            (barrier / f"ready-{rank}").touch()
            t0 = time.monotonic()
            while len(list(barrier.glob("ready-*"))) < k:
                if time.monotonic() - t0 > pk.BARRIER_S:
                    raise TimeoutError("barrier timeout")
                time.sleep(0.02)
            rows[-1]["barrier_release"] = time.time()
    ckpt = {}

    def on_checkpoint(step: int, state: dict) -> None:            # terminal generation only
        t0 = time.monotonic()
        buf = io.BytesIO()
        torch.save(state, buf)
        ckpt.update(step=step, sha=hashlib.sha256(buf.getvalue()).hexdigest(), bytes=buf.getbuffer().nbytes,
                    seconds=time.monotonic() - t0, optimizer_states=len(state["optimizer"]["state"]))
    res = train(pcfg, log=lambda _r: None, on_update=on_update, checkpoint_every=pcfg.steps,
                on_checkpoint=on_checkpoint)
    if ckpt.get("step") != pcfg.steps:
        raise RuntimeError("terminal checkpoint was not captured")
    measured = [r for r in rows if r["update"] >= pk.WARMUP]
    sync = (lambda: torch.cuda.synchronize()) if not smoke else (lambda: None)

    def timed_eval(intervention: str) -> float:
        sync()
        t0 = time.monotonic()
        evaluate(res["backend"], res["head"], pcfg.task_spec(), pcfg.arm, pcfg.readout, split="heldout", batches=1,
                 batch_size=pcfg.batch, seed=DEV_POP, intervention=intervention, filler_writes=pcfg.filler_writes)
        sync()
        return time.monotonic() - t0
    dev_s = timed_eval("none")
    art_s = timed_eval("none" if arm == "memory_off" else "bank_derange")
    out.write_text(json.dumps({"phase": phase, "rank": rank, "k": k, "seed": pk.SEED0 + rank, "arm": arm, "n": n,
                               "updates": rows,
                               "mean_measured_s": sum(r["seconds"] for r in measured) / len(measured),
                               "measured_start": rows[pk.WARMUP - 1]["barrier_release"],
                               "measured_end": measured[-1]["t_end"],
                               "peak_allocated_bytes": 0 if smoke else torch.cuda.max_memory_allocated(),
                               "dev_eval_batch_s": dev_s, "artifact_eval_batch_s": art_s,
                               "checkpoint_serialize_s": ckpt["seconds"], "checkpoint_bytes": ckpt["bytes"],
                               "checkpoint_optimizer_states": ckpt["optimizer_states"],
                               "checkpoint_sha256": ckpt["sha"]}))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        a = sys.argv
        worker(a[2], int(a[3]), int(a[4]), int(a[5]), int(a[6]), Path(a[7]), Path(a[8]), int(a[9]),
               smoke=a[10:] == ["smoke"])
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--smoke-cpu", action="store_true")
    args = ap.parse_args()
    from memsub.sgm.p2d_launch_guard import Watchdog
    watchdog = Watchdog(WALL_S)
    report, sampler = {"status": "running", "configs": [], "timing_spec": T}, None
    try:
        args.out.mkdir(parents=True, exist_ok=False)
        import torch
        from memsub.sgm.synthetic_pilot_run import source_tree_sha256
        report.update(gpu="smoke-cpu" if args.smoke_cpu else torch.cuda.get_device_name(0),
                      memsub_source_sha256=source_tree_sha256(ROOT / "memsub"),
                      packing_helpers_sha256=__import__("hashlib").sha256(Path(pk.__file__).read_bytes()).hexdigest())
        csv_path = args.out / "gpu-util.csv"
        if not args.smoke_cpu:
            sampler = subprocess.Popen(["nvidia-smi", f"--query-gpu={pk.QUERY}", "--format=csv,noheader,nounits",
                                        f"--loop-ms={pk.LOOP_MS}", f"--filename={csv_path}"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for arm, n in T["slot_types"]:
            for phase in sorted(int(p) for p in T["phases"]):
                def cmd(ph, r, k, d, smoke, arm=arm, n=n):
                    return [sys.executable, "-u", str(Path(__file__).resolve()), "--worker", arm, str(n), str(ph),
                            str(r), str(k), str(d / "barrier"), str(d / f"worker-{r}.json"),
                            str(__import__("os").getpid())] + (["smoke"] if smoke else [])
                res = pk.run_test(phase, T["k"], args.out / f"{arm}-n{n}", smoke=args.smoke_cpu, cmd=cmd)
                res.update(arm=arm, n=n)
                if res["status"] == "ok":
                    res["eval_and_checkpoint"] = [{k: w[k] for k in ("dev_eval_batch_s", "artifact_eval_batch_s",
                                                                     "checkpoint_serialize_s", "checkpoint_bytes",
                                                                     "checkpoint_optimizer_states")}
                                                  for w in res["workers"]]
                    res["gpu"] = pk.gpu_util(csv_path, res["fixed_work_span"]) if csv_path.exists() else None
                report["configs"].append(res)
                (args.out / "timing.json").write_text(json.dumps(report, indent=2))
                print(json.dumps({x: res.get(x) for x in ("arm", "n", "phase", "status", "problem",
                                                          "per_worker_mean_s", "fixed_work_updates_per_s")}),
                      flush=True)
                if res["status"] != "ok":
                    report["status"] = f"stopped: {arm} N{n} P{phase} failed"
                    raise StopIteration
        report["status"] = "complete"
    except StopIteration:
        pass
    except Exception as e:
        report["status"] = f"error: {type(e).__name__}: {str(e)[:300]}"
    finally:
        report["sampler_stop"] = pk.stop_sampler(sampler)
        watchdog.cancel()
    if args.out.exists():
        (args.out / "timing.json").write_text(json.dumps(report, indent=2))
    print(report["status"], flush=True)
    sys.exit(0 if report["status"] == "complete" else 1)


if __name__ == "__main__":
    main()
