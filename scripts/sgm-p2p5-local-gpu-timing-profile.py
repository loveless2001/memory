"""P2.5 bounded local GPU timing/fit profile (prereg v0.2 `3bf8737` § Profile).

    .venv-gpu/bin/python scripts/sgm-p2p5-local-gpu-timing-profile.py \
        --out plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/profile-local

Matrix (4 configs, enumerated, fixed): {learned, memory_off} x N32 x
{phase 1 = filler_len 0, phase 2 = filler_len 40}; batch 16; the registered
full-gradient token-serial contract (no no_grad, detach, checkpointing, bf16,
quantization, offload, chunking or batch cut); training-stream seed 99 (never
0/1, never the artifact or reserved populations). Per config: 2 warmup + 8
measured complete forward/backward/optimizer updates, then one timed
full-filler dev batch (seed 4242). 40 updates total, 30-minute wall bound
from the first model load. The first OOM or error STOPS the profile and is
reported. Accuracy is never computed into the output.

Hard deadline (codex 21438/21439): an independent SIGKILL watchdog (the cleared
P2D guard `Watchdog`) is armed BEFORE the first model load for the whole
30-minute budget, so the bound holds inside a configuration too. Progress is
appended per completed update/stage to `progress.jsonl` (fsynced), so an OOM,
error or kill leaves a record of the last completed update. Launch it under an
outer `timeout` as well and record the exit status beside the output.
"""

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.p2d_launch_guard import Watchdog  # noqa: E402
from memsub.sgm.synthetic_pilot import PilotConfig, train  # noqa: E402
from memsub.sgm.synthetic_pilot_evaluation import evaluate  # noqa: E402
from memsub.sgm.synthetic_pilot_run import source_tree_sha256  # noqa: E402

CONFIGS = [(arm, phase) for arm in ("learned", "memory_off") for phase in (1, 2)]
WARMUP, MEASURED, WALL_LIMIT_S, PROFILE_SEED, DEV_SEED = 2, 8, 30 * 60, 99, 4242


PROGRESS: Path | None = None


def progress(event: dict) -> None:
    """Append one fsynced progress record (survives OOM/error/kill)."""
    with open(PROGRESS, "a") as f:
        f.write(json.dumps({"t": time.time(), **event}) + "\n")
        f.flush()
        import os
        os.fsync(f.fileno())


def profile_config(arm: str, phase: int) -> dict:
    pcfg = PilotConfig(arm=arm, readout="residual_head", backbone="qwen3-0.6b-base", device="cuda",
                       n_bindings=32, batch=16, lr=3e-3, steps=WARMUP + MEASURED, seed=PROFILE_SEED,
                       eval_every=10 ** 9, filler_len_schedule=((0, 0 if phase == 1 else 40),))
    times: list = []
    torch.cuda.reset_peak_memory_stats()
    progress({"stage": "config_start", "arm": arm, "phase": phase})

    def on_update(update: int, seconds: float) -> None:
        times.append(seconds)
        progress({"stage": "update_done", "arm": arm, "phase": phase, "update": update, "seconds": seconds,
                  "peak_allocated_bytes": torch.cuda.max_memory_allocated()})
    result = train(pcfg, log=lambda _row: None, on_update=on_update)
    train_peak = torch.cuda.max_memory_allocated()
    torch.cuda.synchronize()
    t0 = time.monotonic()
    evaluate(result["backend"], result["head"], pcfg.task_spec(), arm, "residual_head", split="heldout",
             batches=1, batch_size=16, seed=DEV_SEED)          # returned metrics deliberately discarded
    torch.cuda.synchronize()
    eval_s = time.monotonic() - t0
    progress({"stage": "dev_eval_done", "arm": arm, "phase": phase, "seconds": eval_s})
    measured = times[WARMUP:]
    return {"arm": arm, "phase": phase, "train_filler_len": 0 if phase == 1 else 40, "updates": len(times),
            "warmup_s": times[:WARMUP], "measured_s": measured,
            "mean_measured_s_per_update": sum(measured) / len(measured),
            "peak_train_memory_bytes": train_peak, "dev_eval_batch_s": eval_s,
            "peak_memory_bytes": torch.cuda.max_memory_allocated()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable in this environment")
    args.out.mkdir(parents=True, exist_ok=False)
    global PROGRESS
    PROGRESS = args.out / "progress.jsonl"
    watchdog = Watchdog(WALL_LIMIT_S)          # hard total deadline, armed before any model load
    progress({"stage": "start", "wall_limit_s": WALL_LIMIT_S})
    report = {"environment": {"python": platform.python_version(), "torch": torch.__version__,
                              "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(0),
                              "gpu_total_bytes": torch.cuda.get_device_properties(0).total_memory,
                              "tf32_matmul": torch.backends.cuda.matmul.allow_tf32},
              "memsub_source_sha256": source_tree_sha256(ROOT / "memsub"),
              "contract": "full-gradient token-serial, fp32, TF32 off, batch 16, N32, seed 99",
              "configs": [], "status": "running"}
    started = time.monotonic()
    for arm, phase in CONFIGS:
        if time.monotonic() - started > WALL_LIMIT_S:
            report["status"] = "stopped: 30-minute wall bound reached"
            break
        try:
            report["configs"].append(profile_config(arm, phase))
            print("profiled", arm, f"phase{phase}", report["configs"][-1]["mean_measured_s_per_update"], flush=True)
        except torch.cuda.OutOfMemoryError as e:
            report["status"] = f"stopped: OOM at {arm} phase {phase}"
            report["error"] = str(e)[:500]
            break
        except Exception as e:                                  # first error stops the profile
            report["status"] = f"stopped: error at {arm} phase {phase}"
            report["error"] = repr(e)[:500]
            break
        finally:
            torch.cuda.empty_cache()
    else:
        report["status"] = "complete"
    report["wall_s"] = time.monotonic() - started
    (args.out / "profile.json").write_text(json.dumps(report, indent=2))
    progress({"stage": "end", "status": report["status"]})
    watchdog.cancel()
    print(report["status"])
    sys.exit(0 if report["status"] == "complete" else 1)


if __name__ == "__main__":
    main()
