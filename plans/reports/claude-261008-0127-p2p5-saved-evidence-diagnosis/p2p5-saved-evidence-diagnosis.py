"""P2.5 PK campaign: $0 diagnosis from SAVED evidence only (user 21741, scope claude 21742, codex 21743).

Reads the committed per-cell out/ files (metrics.json, per_example_results.jsonl, routing_telemetry.jsonl) and the
descriptive gate telemetry in the readings report. There are no forward passes, no population generation and no
Modal access. Every consumed file is bound by sha256 in the output. The original and post-hoc amended outcomes are
untouched; this is descriptive diagnosis, not a reading.

    .venv/bin/python <this file> <out json>
"""

import hashlib
import importlib.util
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CAMPAIGN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-qwen3-0p6b-screen-v1"
READINGS = CAMPAIGN / "readings/volume-evidence/collect-1/readings-v1/readings.json"
IVS = ("bank_derange", "coord_shuffle", "read_offset", "query_off")
LAYERS = ("L6", "L13", "L20", "L27")
GROUPS = ("q_proj", "k_proj", "value", "beta", "address_mlp", "out_proj", "alpha")
PHASE2_STEP = 1000          # P2C curriculum: filler 0 before step 1000, 40 after (training-time phases)
INPUTS: dict = {}


def bind(p: Path) -> bytes:
    """Read a consumed file and record its sha256 (every input, incl. imported code, is hash-bound)."""
    data = p.read_bytes()
    INPUTS[str(p.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    return data


def load_json(p: Path):
    return json.loads(bind(p))


def load_jsonl(p: Path) -> list:
    return [json.loads(l) for l in bind(p).decode().splitlines() if l.strip()]


def load_module(rel: str, name: str):
    bind(ROOT / rel)
    s = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def cell_dirs() -> dict:
    """cell id -> its final attempt out/ dir (the latest epoch holding metrics.json)."""
    found = {}
    for m in sorted(CAMPAIGN.glob("*/volume-evidence/collect-1/*/cells/*/epoch-*/attempt-1/out/metrics.json")):
        cell, epoch = m.parts[-5], int(m.parts[-4].split("-")[1])
        if cell not in found or epoch > found[cell][0]:
            found[cell] = (epoch, m.parent)
    return {c: d for c, (_e, d) in sorted(found.items())}


def interventions(rows: list, P2D) -> dict:
    """Per intervention vs none on the SAME saved artifact rows: accuracy, prediction changes, gained/lost
    correct answers, and the episode-paired interval (none - intervention) exactly as P2D `paired`."""
    by = {}
    for r in rows:
        by.setdefault(r["intervention"], {})[(r["batch"], r["episode"], r["episode_hash"], r["query"])] = r
    base, out = by["none"], {"none": {"accuracy": sum(r["correct"] for r in by["none"].values()) / len(by["none"])}}
    for iv in IVS:
        if iv not in by:
            out[iv] = None          # single_cell coord_shuffle: not applicable
            continue
        if set(by[iv]) != set(base):
            raise SystemExit(f"{iv}: rows do not pair with none")
        o = by[iv]
        out[iv] = {"accuracy": sum(r["correct"] for r in o.values()) / len(o),
                   "pred_changed": sum(base[k]["pred"] != o[k]["pred"] for k in base),
                   "gained": sum(o[k]["correct"] and not base[k]["correct"] for k in base),
                   "lost": sum(base[k]["correct"] and not o[k]["correct"] for k in base),
                   "none_minus_iv": P2D.paired(rows, rows, "none", iv)}
    out["pred_top5"] = Counter(r["pred"] for r in base.values()).most_common(5)
    out["pred_distinct"] = len({r["pred"] for r in base.values()})
    return out


def routing(final_none: dict) -> dict:
    keys = ("query_empty_read_weight", "query_read_address_std_cells", "occupancy_mean", "occupancy_max",
            "effective_cells_mean", "beta_by_token_class")
    return {k: final_none.get(k) for k in keys}


def curves(tele: list) -> dict:
    """Dev-eval curve (every 100 steps) and the 150 LOGGED training rows (every 10th of 1500 updates)."""
    ev = [r for r in tele if "eval" in r]
    tr = [r for r in tele if "loss" in r]
    dev = [{"step": r["step"], "acc": r["eval"]["accuracy"], "empty": r["eval"].get("query_empty_read_weight"),
            "eff": r["eval"].get("effective_cells_mean"), "addr_std": r["eval"].get("query_read_address_std_cells"),
            "beta": r["eval"].get("beta_by_token_class")} for r in ev]
    grad = {}
    for L in LAYERS:
        for g in GROUPS:
            k = f"{L}/{g}"
            vals = [r["grad_norm"].get(k, "missing") for r in tr]
            if all(v == "missing" for v in vals):
                continue
            num = [(r["step"], v) for r, v in zip(tr, vals) if isinstance(v, (int, float))]
            upd = [r["update_norm"].get(k) for r in tr]
            grad[k] = {"logged": len(vals), "none": sum(v is None for v in vals),
                       "update_norm_positive": sum(isinstance(u, (int, float)) and u > 0 for u in upd),
                       "zero": sum(v == 0.0 for _s, v in num),
                       "first_none_step": next((r["step"] for r, v in zip(tr, vals) if v is None), None),
                       "median_p1": _median([v for s, v in num if s < PHASE2_STEP]),
                       "median_p2": _median([v for s, v in num if s >= PHASE2_STEP])}
    alpha = {L: [tr[0]["alpha"].get(L[1:]), tr[-1]["alpha"].get(L[1:])] for L in LAYERS}
    return {"dev_eval": dev, "train_logged_rows": len(tr), "train_first_last": [_tr(tr[0]), _tr(tr[-1])],
            "train_acc_p1_p2_mean": [_mean([r["train_acc"] for r in tr if r["step"] < PHASE2_STEP]),
                                     _mean([r["train_acc"] for r in tr if r["step"] >= PHASE2_STEP])],
            "alpha_first_last": alpha, "grad_norm": grad}


def _tr(r):
    return {k: r.get(k) for k in ("step", "loss", "train_acc", "effective_cells_mean", "occupancy_mean")}


def _median(v):
    return statistics.median(v) if v else None


def _mean(v):
    return sum(v) / len(v) if v else None


def gate_telemetry(readings: dict) -> dict:
    """Descriptive write-gate telemetry from the (post-hoc amended) readings report: per corner AUROC of the
    applied gate (binding vs filler) and per-layer mean effective gate for binding vs filler events."""
    out = {}
    for n, v in readings["n"].items():
        for corner, c in v["corners"].items():
            g = c.get("gate_telemetry_descriptive") or {}
            if g.get("status") != "measured":
                out[f"{corner}@N{n}"] = g.get("status")
                continue
            per_layer = {}
            for L in LAYERS:
                hs = [h for k, h in g["per_head"].items() if k.startswith(L + "h")]
                per_layer[L] = {"binding": _mean([h["binding_effective_mean"] for h in hs]),
                                "filler": _mean([h["filler_effective_mean"] for h in hs]),
                                "auroc_mean": _mean([h["auroc_applied"] for h in hs])}
            out[f"{corner}@N{n}"] = {"auroc_mean": g["auroc_mean_defined"], "auroc_min": g["auroc_min_defined"],
                                     "rho": g["rho_pooled_effective"], "per_layer": per_layer}
    return out


def main():
    P2D = load_module("scripts/sgm-p2d-step2-decision-rules.py", "p2d")          # paired intervals (frozen rule)
    EXTRA = load_module("plans/reports/claude-261008-0127-p2p5-saved-evidence-diagnosis/"
                        "p2p5-diagnosis-extra-evidence-checkpoints-p2c-gate-heads.py", "extra")
    cells = {}
    for cell, out in cell_dirs().items():
        m = load_json(out / "metrics.json")
        rows = load_jsonl(out / "per_example_results.jsonl")
        tele = load_jsonl(out / "routing_telemetry.jsonl")
        entry = {"arm": m["arm"], "n": m["n_bindings"], "seed": m["seed"], "out_dir": str(out.relative_to(ROOT)),
                 "train_last": {k: m["train_last"].get(k) for k in ("step", "loss", "train_acc")}}
        if m["arm"] != "memory_off":
            entry["interventions"] = interventions(rows, P2D)
            entry["routing_final_none"] = routing(m["final"]["heldout_none"])
        else:
            entry["interventions"] = {"none": {"accuracy": m["final"]["heldout_none"]["accuracy"]}}
        entry["curves"] = curves(tele)
        cells[cell] = entry
    readings = load_json(READINGS)
    report = {"format": "p2p5-saved-evidence-diagnosis-v2", "scope": "saved evidence only; no forward pass",
              "cells": cells, "gate_telemetry_readings": gate_telemetry(readings),
              "gate_heads_readings": EXTRA.gate_heads(readings),
              "l20_beta_checkpoint_drift": EXTRA.l20_beta_drift(ROOT, bind),
              "p2c_reference": EXTRA.p2c_reference(ROOT, bind)}
    report["inputs_sha256"] = dict(sorted(INPUTS.items()))
    Path(sys.argv[1]).write_text(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({"cells": len(cells), "inputs": len(INPUTS)}))


if __name__ == "__main__":
    main()
