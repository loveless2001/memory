"""Stage A read-escape blocker screen: train ONE arm for 100 updates (proposal v0.2, EXPLORATORY).

The base is the readout probe's seed-0 PilotConfig, bound by sha256: frozen Qwen3-0.6B-Base,
learned addresses, taskhead, N32, batch 16, curriculum ((0, 0), (1000, 40)), so all 100 updates
are phase 1. Init and the train stream are the probe's. Overrides:
  every arm: steps 100, eval_every 25 (dev evals at 0/25/50/75/100; heldout, seed 4242, 4 x 16)
  A0 baseline: none
  A1: lr 3e-3 -> 3e-4 for ALL trainable parameters (global-rate change, not an isolated
      address-lr or H2 test)
  A2: aux_address_lambda 0.1. This is PRIVILEGED training correspondence supervision
      (binding positions; AddressMLP-only, detached q/k). Diagnostic only. A constant
      address map gives zero aux loss, so a kept A2 does not establish useful
      discrimination or an unsupervised remedy.
Dev-only: no final/intervention/train-split evaluations and no reserved seeds. Writes to --out:
run_manifest.json, routing_telemetry.jsonl, trained_parameters.safetensors and
stage_a_result.json (the pre-specified operational bands on the pooled query absent-read weight;
not learning or capability conditions).

    python scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py --arm A0 --manifest PROBE_S0_MANIFEST --out NEW_DIR
"""

import argparse
import hashlib
import json
import math
import sys
import time
from dataclasses import asdict
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.synthetic_pilot import PilotConfig, train  # noqa: E402
from memsub.sgm.synthetic_pilot_evaluation import evaluate  # noqa: E402
from memsub.sgm.synthetic_pilot_run import _versions, save_trained_parameters, source_tree_sha256  # noqa: E402

PROBE_S0_MANIFEST_SHA256 = "4e89b95adcff68b73fecb2f071c3fe17498c7e62fd1a97ac04f77691b5fc0bb0"   # probe s0 run_manifest.json (copy under the plan inputs/)
DEV_SEED = 4242
STEPS, EVAL_EVERY, EVAL_STEPS = 100, 25, (0, 25, 50, 75, 100)
ESCAPED, KEPT = 0.9, 0.2
ARMS = {"A0": {}, "A1": {"lr": 3e-4}, "A2": {"aux_address_lambda": 0.1}}
BASE_EXPECT = {"arm": "learned", "readout": "taskhead", "n_bindings": 32, "n_queries": 4, "batch": 16,
               "eval_batches": 4, "seed": 0, "lr": 0.003, "aux_address_lambda": 0.0, "filler_writes": True,
               "filler_len": 40, "filler_len_schedule": [[0, 0], [1000, 40]], "backbone": "qwen3-0.6b-base"}
A2_NOTE = ("PRIVILEGED training correspondence supervision via aux_address_lambda=0.1 (binding positions, "
           "AddressMLP-only, detached q/k); diagnostic only; zero for a constant address map")


def classify(rows: list) -> dict:
    """Pooled query absent-read weight (all layers/heads, 64 dev episodes x 4 queries) at each dev eval.
    Missing, duplicate or non-finite endpoint values -> INVALID."""
    evs: dict = {}
    for r in rows:
        if isinstance(r.get("eval"), dict):
            if r["step"] in evs:
                return {"status": "INVALID", "why": f"duplicate dev eval at {r['step']}"}
            evs[r["step"]] = r["eval"].get("query_empty_read_weight")
    if tuple(sorted(evs)) != EVAL_STEPS:
        return {"status": "INVALID", "why": f"dev eval steps {sorted(evs)} != {list(EVAL_STEPS)}"}
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in evs.values()):
        return {"status": "INVALID", "why": "non-finite or missing absent-read weight"}
    end = evs[STEPS]
    band = "escaped" if end >= ESCAPED else "kept" if end <= KEPT else "partial"
    return {"status": "valid", "absent_read_weight_by_step": {str(k): evs[k] for k in EVAL_STEPS},
            "band_at_100": band, "kept_through_100": all(v <= KEPT for v in evs.values()),
            "bands": {"escaped": f">= {ESCAPED}", "kept": f"<= {KEPT}", "partial": "between"}}


def arm_config(base: dict, arm: str, device: str, steps: int = STEPS, eval_every: int = EVAL_EVERY) -> PilotConfig:
    bad = {k: (base.get(k), v) for k, v in BASE_EXPECT.items() if base.get(k) != v}
    if bad:
        raise ValueError(f"base PilotConfig differs from the probe s0 recipe: {bad}")
    return PilotConfig(**{**base, **ARMS[arm], "steps": steps, "eval_every": eval_every, "device": device,
                          "checkpoint_steps": ()})


def run_arm(pcfg: PilotConfig, arm: str, out: Path, extra: dict) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    t0 = time.time()
    spec = pcfg.task_spec()
    tele = (out / "routing_telemetry.jsonl").open("w")

    def log(row):
        tele.write(json.dumps(row, default=float) + "\n")
        tele.flush()

    def dev_eval(backend, head, step):
        return evaluate(backend, head, spec, pcfg.arm, pcfg.readout, split="heldout",
                        batches=pcfg.eval_batches, batch_size=pcfg.batch, seed=DEV_SEED,
                        filler_writes=pcfg.filler_writes)

    res = train(pcfg, log=log, evaluate_fn=dev_eval)
    tele.close()
    result = classify(res["telemetry"])
    manifest = {"experiment": "m4-sgm-p2p5-stage-a-read-escape-blocker", "label": "EXPLORATORY (dev only)",
                "stage_a": {"arm": arm, "overrides": ARMS[arm], **({"supervision": A2_NOTE} if arm == "A2" else {})},
                "pilot_config": asdict(pcfg), "sgm_config": res["sgm_config"], "policy_id": res["policy_id"],
                "dev_seed": DEV_SEED, "versions": _versions(),
                "tf32": {"matmul": torch.backends.cuda.matmul.allow_tf32, "cudnn": torch.backends.cudnn.allow_tf32},
                "memsub_source_sha256": source_tree_sha256(ROOT / "memsub"),
                "trained_parameters_sha256": save_trained_parameters(res["runtime"], res["head"],
                                                                     out / "trained_parameters.safetensors"),
                **extra, "wall_seconds": time.time() - t0}
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, default=float))
    (out / "stage_a_result.json").write_text(json.dumps({"arm": arm, **result}, indent=2))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=sorted(ARMS), required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    got = hashlib.sha256(a.manifest.read_bytes()).hexdigest()
    if got != PROBE_S0_MANIFEST_SHA256:
        raise SystemExit(f"probe manifest sha {got} != bound {PROBE_S0_MANIFEST_SHA256}")
    if not torch.cuda.is_available():
        raise SystemExit("cuda required (no CPU fallback)")
    pcfg = arm_config(json.loads(a.manifest.read_text())["pilot_config"], a.arm, "cuda")
    res = run_arm(pcfg, a.arm, a.out, {"probe_manifest_sha256": got, "argv": sys.argv})
    print(json.dumps({"arm": a.arm, **res}))


if __name__ == "__main__":
    main()
