"""B2 occupied-fill long run: the readout probe's seed-0 recipe EXACTLY (1500 updates, curriculum
((0, 0), (1000, 40)), dev evals every 100 on heldout seed 4242, 4 x 16) plus the SGM variant
occupied_softmax_fill_v1 (tau 1.0, anchor 0.1). EXPLORATORY, dev only. The probe s0 run (no variant)
is the paired no-fix reference: same config apart from `sgm`, same init and train stream.

Resumable: a training_state checkpoint is written atomically to OUT/resume.pt every 50 updates (and
the terminal one before the final dev eval), stamped with this run's IDENTITY (campaign, memsub
source, this script, base manifest, PilotConfig). Re-running the same command with the same OUT
resumes from it; any foreign identity or unidentified contents refuse (fail closed). OUT without
resume.pt restarts from scratch. Nothing is deleted: before every (re)start the previous OUT
contents (or, on resume, its telemetry incl. rows after the checkpoint) are archived under the
sibling OUT.archive/start-<n>/, and every start is appended to OUT.starts.jsonl. After training: the paired bank_derange dev eval (same episodes)
and b2_result.json. Writes run_manifest.json and trained_parameters.safetensors at the end.

    python scripts/sgm-p2p5-b2-occupied-fill-long-run-train.py --manifest PROBE_S0_MANIFEST --out DIR
"""

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
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
from memsub.sgm.training_resume_checkpoint import load, save_atomic  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "stage_a_train", ROOT / "scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py")
STAGE_A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(STAGE_A)          # frozen Stage A: BASE_EXPECT, bound probe manifest sha, bands

ARM = "B2"
CAMPAIGN = "m4-sgm-p2p5-b2-occupied-fill-long-v1"
FILL = {"read_fallback": "occupied_softmax_fill_v1", "read_fallback_tau": 1.0, "read_fallback_anchor": 0.1}
STEPS, EVAL_EVERY, CHECKPOINT_EVERY = 1500, 100, 50
DEV_TOTAL = 256                             # eval_batches 4 x batch 16 x n_queries 4
CHANCE_CORRECT = 4                          # 256 x 1/64
# EXPLORATORY operational thresholds (no significance claim: 4 queries share each of 64 episodes)
MEMORY_USED_MIN_CORRECT = 12
MEMORY_USED_MIN_DERANGE_DROP = 6            # paired: correct(none) - correct(bank_derange) >= 6
FILL_KEYS = ("query_fully_absent_fraction", "query_nearest_occupied_cells_mean", "query_fill_support_cells_mean")


def arm_config(base: dict, device: str) -> PilotConfig:
    """The probe s0 PilotConfig unchanged except `sgm` = FILL and the execution device."""
    bad = {k: (base.get(k), v) for k, v in STAGE_A.BASE_EXPECT.items() if base.get(k) != v}
    if bad or (base.get("steps"), base.get("eval_every"), base.get("sgm")) != (STEPS, EVAL_EVERY, {}):
        raise ValueError(f"base PilotConfig is not the probe s0 recipe: {bad or base}")
    return PilotConfig(**{**base, "sgm": dict(FILL), "device": device,
                          "checkpoint_steps": tuple(base.get("checkpoint_steps", ()))})


def _count_ok(ev: dict, total: int) -> bool:
    c, n = ev.get("correct"), ev.get("total")
    return (type(c) is int and type(n) is int and n == total and 0 <= c <= n)


def _weight_ok(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0.0 <= v <= 1.0


def summarize(rows: list, derange: dict | None, total: int = DEV_TOTAL, steps_n: int = STEPS,
              every: int = EVAL_EVERY) -> dict:
    """Pre-registered readout. Memory use needs BOTH the dev gain and the paired bank_derange drop.
    INVALID unless every registered dev eval occurs exactly once with integer counts over the registered
    total, a finite pre-fill weight in [0, 1], and a derange eval over the same total."""
    evs: dict = {}
    for r in rows:
        if isinstance(r.get("eval"), dict):
            if r["step"] in evs:
                return {"arm": ARM, "status": "INVALID", "why": f"duplicate dev eval at {r['step']}"}
            evs[r["step"]] = r["eval"]
    steps = list(range(0, steps_n + 1, every))
    if sorted(evs) != steps:
        return {"arm": ARM, "status": "INVALID", "why": f"dev eval steps {sorted(evs)} != {steps}"}
    if not all(_count_ok(evs[s], total) and _weight_ok(evs[s].get("query_empty_read_weight")) for s in steps):
        return {"arm": ARM, "status": "INVALID", "why": "a dev eval has bad counts/total or absent weight"}
    if not (isinstance(derange, dict) and _count_ok(derange, total)):
        return {"arm": ARM, "status": "INVALID", "why": "bank_derange eval missing or bad counts/total"}
    none_c, der_c = evs[steps_n]["correct"], derange["correct"]
    absent = {str(s): evs[s]["query_empty_read_weight"] for s in steps}
    end = evs[steps_n]["query_empty_read_weight"]
    return {"arm": ARM, "status": "valid",
            "final_correct_none": none_c, "final_correct_bank_derange": der_c, "total": total,
            "memory_used": none_c >= MEMORY_USED_MIN_CORRECT and none_c - der_c >= MEMORY_USED_MIN_DERANGE_DROP,
            "criteria": {"min_correct": MEMORY_USED_MIN_CORRECT, "min_derange_drop": MEMORY_USED_MIN_DERANGE_DROP,
                         "chance_correct": CHANCE_CORRECT, "note": "exploratory operational thresholds"},
            "absent_read_weight_by_step": absent,
            "band_at_end": "escaped" if end >= STAGE_A.ESCAPED else "kept" if end <= STAGE_A.KEPT else "partial",
            "kept_at_every_eval": all(v <= STAGE_A.KEPT for v in absent.values()),
            "dev_correct_by_step": {str(s): evs[s]["correct"] for s in steps},
            "fill_by_step": {str(s): {k: evs[s].get(k) for k in FILL_KEYS} for s in steps}}


def run_identity(pcfg: PilotConfig, probe_manifest_sha256: str | None) -> dict:
    """What a checkpoint/run dir must belong to (fail closed on anything else). JSON-normalized
    (tuples -> lists) so the stored file and the checkpoint stamp compare equal."""
    return json.loads(json.dumps({
        "campaign": CAMPAIGN, "memsub_source_sha256": source_tree_sha256(ROOT / "memsub"),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "probe_manifest_sha256": probe_manifest_sha256, "pilot_config": asdict(pcfg)}))


def prepare_out(out: Path, pcfg: PilotConfig, identity: dict):
    """-> (resume state or None, start number). Archives (never deletes) prior attempt evidence; refuses
    a run dir or checkpoint that is not this run's identity."""
    log = out.with_name(out.name + ".starts.jsonl")
    n = 1 + (len(log.read_text().splitlines()) if log.exists() else 0)
    archive = out.with_name(out.name + ".archive") / f"start-{n}"
    ident_file = out / "identity.json"
    if out.exists() and any(out.iterdir()):
        if not ident_file.exists() or json.loads(ident_file.read_text()) != identity:
            raise SystemExit(f"{out} holds foreign or unidentified contents: refusing")
    ckpt = out / "resume.pt"
    if ckpt.exists():
        state = load(ckpt)
        if state.get("b2_identity") != identity or state["pilot_config"] != asdict(pcfg):
            raise SystemExit("resume.pt belongs to a different run identity: refusing")
        if (out / "routing_telemetry.jsonl").exists():     # rows after the checkpoint are rewritten: keep them
            archive.mkdir(parents=True)
            shutil.copy2(out / "routing_telemetry.jsonl", archive / "routing_telemetry.jsonl")
        return state, n
    if out.exists() and any(out.iterdir()):                # crash before the first checkpoint
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(out), str(archive))
    out.mkdir(parents=True, exist_ok=True)
    ident_file.write_text(json.dumps(identity, indent=1))
    return None, n


def run_b2(pcfg: PilotConfig, out: Path, extra: dict, checkpoint_every: int = CHECKPOINT_EVERY,
           probe_manifest_sha256: str | None = None) -> dict:
    t0 = time.time()
    identity = run_identity(pcfg, probe_manifest_sha256)
    state, n = prepare_out(out, pcfg, identity)
    with out.with_name(out.name + ".starts.jsonl").open("a") as f:
        f.write(json.dumps({"start": n, "t": t0, "resume_step": None if state is None else state["step"]}) + "\n")
    tele = (out / "routing_telemetry.jsonl").open("w")       # rewritten from the checkpoint's rows on resume
    for row in ([] if state is None else state["telemetry"]):
        tele.write(json.dumps(row, default=float) + "\n")

    def log(row):
        tele.write(json.dumps(row, default=float) + "\n")
        tele.flush()

    spec = pcfg.task_spec()

    def dev_eval(backend, head, step, intervention="none"):
        return evaluate(backend, head, spec, pcfg.arm, pcfg.readout, split="heldout", batches=pcfg.eval_batches,
                        batch_size=pcfg.batch, seed=STAGE_A.DEV_SEED, intervention=intervention,
                        filler_writes=pcfg.filler_writes)

    res = train(pcfg, log=log, evaluate_fn=dev_eval, checkpoint_every=checkpoint_every,
                on_checkpoint=lambda step, st: save_atomic({**st, "b2_identity": identity}, out / "resume.pt"),
                resume=state)
    tele.close()
    derange = dev_eval(res["backend"], res["head"], pcfg.steps, "bank_derange")
    (out / "final_bank_derange_eval.json").write_text(json.dumps(derange, indent=2, default=float))
    result = summarize(res["telemetry"], derange)
    manifest = {"experiment": "m4-sgm-p2p5-b2-occupied-fill-long-run", "label": "EXPLORATORY (dev only)",
                "result_label": pcfg.result_label(), "b2": {"arm": ARM, "base": "readout probe s0", "sgm_overrides": FILL},
                "pilot_config": asdict(pcfg), "sgm_config": res["sgm_config"], "policy_id": res["policy_id"],
                "dev_seed": STAGE_A.DEV_SEED, "versions": _versions(),
                "tf32": {"matmul": torch.backends.cuda.matmul.allow_tf32, "cudnn": torch.backends.cudnn.allow_tf32},
                "memsub_source_sha256": source_tree_sha256(ROOT / "memsub"),
                "trained_parameters_sha256": save_trained_parameters(res["runtime"], res["head"],
                                                                     out / "trained_parameters.safetensors"),
                **extra, "wall_seconds_this_start": time.time() - t0}
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, default=float))
    (out / "b2_result.json").write_text(json.dumps(result, indent=2, default=float))
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
    res = run_b2(pcfg, a.out, {"probe_manifest_sha256": got, "argv": sys.argv}, probe_manifest_sha256=got)
    print(json.dumps({k: res.get(k) for k in ("arm", "status", "memory_used", "final_correct_none",
                                              "final_correct_bank_derange", "band_at_end")}))


if __name__ == "__main__":
    main()
