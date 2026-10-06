"""P2.5 option A step 1 (user 21472/21474/21476): hotspot attribution of the SGM path.

    python scripts/sgm-p2p5-sgm-path-hotspot-profile.py --out <dir>

Runs on a Modal L40S via modal-runners/modal-m4-sgm-p2p5-dev-gpu-test-runner.py (the
laptop run crashed the 6 GB WSL host, user 21476). DEV attribution only: no accuracy,
no registered/artifact/reserved population (training-stream seed 99), no timing claim.
Matrix: learned b16, memory_off b16, learned b2; N32, filler 0 (phase-1 shape). Per
config 1 warmup + 2 measured updates (plain timing, forward/backward split), then one
update under torch.profiler with labelled ranges (monkeypatched wrappers; memsub is
not edited). Reports s/update, labelled-range CPU totals, host syncs, kernel launches,
autograd-node counts and top ops. Watchdog armed before the first model load.
"""

import argparse
import functools
import json
import sys
import time
from collections import Counter
from pathlib import Path

import torch
from torch.profiler import ProfilerActivity, profile, record_function

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.runtime import sgm_model_runtime as rt  # noqa: E402
from memsub.sgm.layer_adapter import SGMLayerAdapter  # noqa: E402
from memsub.sgm.p2d_launch_guard import Watchdog  # noqa: E402
from memsub.sgm.sparse_cell_bank import SparseBankSet  # noqa: E402
from memsub.sgm.synthetic_pilot import PilotConfig, train  # noqa: E402
from memsub.sgm.synthetic_pilot_run import source_tree_sha256  # noqa: E402

CONFIGS = [("learned", 16), ("memory_off", 16), ("learned", 2)]
WARMUP, MEASURED, SEED, WALL_S, TOP = 1, 2, 99, 25 * 60, 30
LABELS = [(SparseBankSet, "gather"), (SparseBankSet, "scatter"), (SGMLayerAdapter, "project"),
          (rt.SGMModelRuntime, "_sgm_layer"), (rt.SGMModelRuntime, "_read"),
          (rt.SGMModelRuntime, "_write"), (rt.SGMModelRuntime, "_evict"), (rt.SGMModelRuntime, "step"),
          (rt, "delta_update"), (rt, "read_memory"), (rt, "stencil_2d")]
PHASE = {"fwd_s": 0.0, "bwd_s": 0.0}


def label(owner, name):
    fn = getattr(owner, name)

    @functools.wraps(fn)
    def wrapped(*a, **k):
        with record_function(f"SGM::{name}"):
            return fn(*a, **k)
    setattr(owner, name, wrapped)


def timed_backward():
    orig = torch.Tensor.backward

    def backward(self, *a, **k):
        torch.cuda.synchronize()
        t0 = time.monotonic()
        with record_function("SGM::backward"):
            orig(self, *a, **k)
        torch.cuda.synchronize()
        PHASE["bwd_s"] = time.monotonic() - t0
    torch.Tensor.backward = backward


def run_config(arm: str, batch: int) -> dict:
    steps = WARMUP + MEASURED + 1
    pcfg = PilotConfig(arm=arm, readout="residual_head", backbone="qwen3-0.6b-base", device="cuda",
                       n_bindings=32, batch=batch, lr=3e-3, steps=steps, seed=SEED,
                       eval_every=10 ** 9, filler_len_schedule=((0, 0),))
    rows, prof_box = [], {}
    torch.cuda.reset_peak_memory_stats()

    def on_update(update: int, seconds: float) -> None:
        rows.append({"s": seconds, "bwd_s": PHASE["bwd_s"]})
        if update == WARMUP + MEASURED - 1:             # the next update is profiled
            prof_box["p"] = profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA])
            prof_box["p"].__enter__()
        elif update == steps - 1:
            torch.cuda.synchronize()
            prof_box["p"].__exit__(None, None, None)
    train(pcfg, log=lambda _row: None, on_update=on_update)
    p = prof_box["p"]
    ev = p.key_averages()
    kernels = sum(e.count for e in ev if e.device_type.name == "CUDA")
    autograd = Counter()
    for e in ev:
        if e.key.startswith("autograd::engine::evaluate_function: "):
            autograd[e.key.split(": ", 1)[1]] += e.count
    by_key = {e.key: e for e in ev}
    ranges = {k: {"count": e.count, "cpu_total_ms": e.cpu_time_total / 1e3}
              for k, e in by_key.items() if k.startswith("SGM::")}
    syncs = {k: by_key[k].count for k in ("aten::_local_scalar_dense", "cudaStreamSynchronize",
                                          "cudaDeviceSynchronize", "aten::item") if k in by_key}
    measured = rows[WARMUP:WARMUP + MEASURED]
    mean = sum(r["s"] for r in measured) / len(measured)
    return {"arm": arm, "batch": batch, "n_bindings": 32, "train_filler_len": 0,
            "measured": measured, "mean_s_per_update": mean,
            "mean_bwd_s": sum(r["bwd_s"] for r in measured) / len(measured),
            "profiled_update_s_with_profiler": rows[-1]["s"],
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "labelled_ranges": ranges, "host_sync_ops": syncs, "cuda_kernels_in_profiled_update": kernels,
            "autograd_nodes_total": sum(autograd.values()),
            "autograd_nodes_top": dict(autograd.most_common(TOP)),
            "top_self_cpu": [{"op": e.key, "count": e.count, "self_cpu_ms": e.self_cpu_time_total / 1e3,
                              "self_cuda_ms": e.self_device_time_total / 1e3}
                             for e in sorted(ev, key=lambda e: e.self_cpu_time_total, reverse=True)[:TOP]],
            "top_self_cuda": [{"op": e.key, "count": e.count, "self_cuda_ms": e.self_device_time_total / 1e3}
                              for e in sorted(ev, key=lambda e: e.self_device_time_total, reverse=True)[:TOP]]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable")
    args.out.mkdir(parents=True, exist_ok=False)
    watchdog = Watchdog(WALL_S)
    try:
        for owner, name in LABELS:
            label(owner, name)
        timed_backward()
        report = {"purpose": "DEV hotspot attribution only (seed 99); not a registered timing",
                  "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
                  "tf32_matmul": torch.backends.cuda.matmul.allow_tf32,
                  "memsub_source_sha256": source_tree_sha256(ROOT / "memsub"), "configs": [], "status": "running"}
        for arm, batch in CONFIGS:
            try:
                report["configs"].append(run_config(arm, batch))
                print(json.dumps({k: report["configs"][-1][k] for k in ("arm", "batch", "mean_s_per_update",
                                                                        "mean_bwd_s")}), flush=True)
            except Exception as e:                     # first OOM/error stops; preserved
                report["status"] = f"stopped: {arm} b{batch}: {type(e).__name__}: {str(e)[:300]}"
                break
            (args.out / "hotspot.json").write_text(json.dumps(report, indent=2))
            torch.cuda.empty_cache()
        else:
            report["status"] = "complete"
        (args.out / "hotspot.json").write_text(json.dumps(report, indent=2))
        print(report["status"], flush=True)
    finally:
        watchdog.cancel()


if __name__ == "__main__":
    main()
