"""B1 occupied-fill retention screen: train ONE arm for 100 updates (EXPLORATORY, dev only).

Base = Stage A A0 exactly (the readout probe's seed-0 PilotConfig, bound by sha256, checked against
Stage A's BASE_EXPECT; steps 100, eval_every 25, dev evals at 0/25/50/75/100 on heldout seed 4242,
4 x 16). One change: SGM variant occupied_softmax_fill_v1 (tau 1.0, anchor 0.1), see
plans/261009-0945-m4-sgm-p2p5-occupied-cell-read-fallback-spec/spec.md. Lr, init, train stream,
curriculum (all 100 updates in filler-0 phase 1) are A0's.

Bands reuse Stage A's classify() UNCHANGED on query_empty_read_weight, which is the ORIGINAL
stencil's absent mass measured BEFORE any fill. The fill telemetry (fully-absent fraction =
reads carried entirely by the fill, nearest occupied distance, fill support) and dev accuracy are
reported beside the band, never folded into it. Writes to --out: run_manifest.json,
routing_telemetry.jsonl, trained_parameters.safetensors, b1_result.json.

    python scripts/sgm-p2p5-b1-occupied-fill-retention-screen-train.py --manifest PROBE_S0_MANIFEST --out NEW_DIR
"""

import argparse
import hashlib
import importlib.util
import json
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

_spec = importlib.util.spec_from_file_location(
    "stage_a_train", ROOT / "scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py")
STAGE_A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(STAGE_A)          # frozen Stage A: classify(), BASE_EXPECT, bound manifest sha

ARM = "B1"
FILL = {"read_fallback": "occupied_softmax_fill_v1", "read_fallback_tau": 1.0, "read_fallback_anchor": 0.1}
FILL_KEYS = ("query_fully_absent_fraction", "query_without_occupied_fraction",
             "query_nearest_occupied_cells_mean", "query_fill_support_cells_mean")


def arm_config(base: dict, device: str, steps: int = STAGE_A.STEPS, eval_every: int = STAGE_A.EVAL_EVERY) -> PilotConfig:
    """A0's config (Stage A arm_config with no overrides) plus the fill variant in `sgm`."""
    a0 = STAGE_A.arm_config(base, "A0", device, steps, eval_every)
    if a0.sgm:
        raise ValueError(f"probe base already carries SGM overrides {a0.sgm}: not the A0 recipe")
    return PilotConfig(**{**asdict(a0), "sgm": dict(FILL)})


def summarize(rows: list) -> dict:
    """Stage A band on the PRE-fill absence, plus fill telemetry/accuracy by dev step (reported only)."""
    out = {"arm": ARM, **STAGE_A.classify(rows)}
    evs = {r["step"]: r["eval"] for r in rows if isinstance(r.get("eval"), dict)}
    out["fill_by_step"] = {str(s): {k: e.get(k) for k in FILL_KEYS} for s, e in sorted(evs.items())}
    out["dev_accuracy_by_step"] = {str(s): e.get("accuracy") for s, e in sorted(evs.items())}
    out["read_anchor_by_logged_step"] = {str(r["step"]): r.get("read_anchor") for r in rows if "loss" in r}
    out["note"] = ("band = ORIGINAL-stencil absent mass (pre-fill). A high fully-absent fraction with an "
                   "escaped band means the fill carries the reads (lookup changed), not restored routing. "
                   "100 updates is a routing/mechanics gate, not designed to show retrieval.")
    return out


def run_b1(pcfg: PilotConfig, out: Path, extra: dict) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    t0 = time.time()
    spec = pcfg.task_spec()
    tele = (out / "routing_telemetry.jsonl").open("w")

    def log(row):
        tele.write(json.dumps(row, default=float) + "\n")
        tele.flush()

    def dev_eval(backend, head, step):
        return evaluate(backend, head, spec, pcfg.arm, pcfg.readout, split="heldout",
                        batches=pcfg.eval_batches, batch_size=pcfg.batch, seed=STAGE_A.DEV_SEED,
                        filler_writes=pcfg.filler_writes)

    res = train(pcfg, log=log, evaluate_fn=dev_eval)
    tele.close()
    result = summarize(res["telemetry"])
    manifest = {"experiment": "m4-sgm-p2p5-b1-occupied-fill-retention-screen", "label": "EXPLORATORY (dev only)",
                "result_label": pcfg.result_label(), "b1": {"arm": ARM, "base": "Stage A A0", "sgm_overrides": FILL},
                "pilot_config": asdict(pcfg), "sgm_config": res["sgm_config"], "policy_id": res["policy_id"],
                "dev_seed": STAGE_A.DEV_SEED, "versions": _versions(),
                "tf32": {"matmul": torch.backends.cuda.matmul.allow_tf32, "cudnn": torch.backends.cudnn.allow_tf32},
                "memsub_source_sha256": source_tree_sha256(ROOT / "memsub"),
                "trained_parameters_sha256": save_trained_parameters(res["runtime"], res["head"],
                                                                     out / "trained_parameters.safetensors"),
                **extra, "wall_seconds": time.time() - t0}
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, default=float))
    (out / "b1_result.json").write_text(json.dumps(result, indent=2, default=float))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    got = hashlib.sha256(a.manifest.read_bytes()).hexdigest()
    if got != STAGE_A.PROBE_S0_MANIFEST_SHA256:
        raise SystemExit(f"probe manifest sha {got} != bound {STAGE_A.PROBE_S0_MANIFEST_SHA256}")
    if not torch.cuda.is_available():
        raise SystemExit("cuda required (no CPU fallback)")
    pcfg = arm_config(json.loads(a.manifest.read_text())["pilot_config"], "cuda")
    res = run_b1(pcfg, a.out, {"probe_manifest_sha256": got, "argv": sys.argv})
    print(json.dumps({k: res.get(k) for k in ("arm", "status", "band_at_100", "absent_read_weight_by_step")}))


if __name__ == "__main__":
    main()
