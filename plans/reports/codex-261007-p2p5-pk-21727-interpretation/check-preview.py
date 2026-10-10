"""Saved-artifact arithmetic only. Does not access the reserved readings population or invoke a model."""
import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
GROUP = PLAN / "p2p5-qwen3-0p6b-screen-v1"
preview, saved, hashes = {}, {}, {}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def episodes(rows, iv):
    out = {}
    for r in rows:
        if r["intervention"] != iv:
            continue
        assert r["correct"] == (r["pred"] == r["label"])
        k = (r["batch"], r["episode"], r["episode_hash"])
        assert r["query"] not in out.setdefault(k, {})
        out[k][r["query"]] = float(r["correct"])
    assert len(out) == 256 and all(set(v) == {0, 1, 2, 3} for v in out.values())
    return {k: sum(v.values()) / 4 for k, v in out.items()}


def paired(a, b, iva="none", ivb="none"):
    ea, eb = episodes(a, iva), episodes(b, ivb)
    assert set(ea) == set(eb)
    d = [ea[k] - eb[k] for k in ea]
    diff = statistics.mean(d)
    hw = 1.96 * statistics.stdev(d) / math.sqrt(len(d))
    return {"diff": diff, "lo": diff - hw, "hi": diff + hw, "episodes": len(d)}


for slot in sorted(GROUP.iterdir()):
    evidence = slot / "volume-evidence/collect-1" / slot.name
    if not (evidence / "cells").is_dir():
        continue
    for cell in sorted((evidence / "cells").iterdir()):
        rec = json.loads(sorted(cell.glob("epoch-*/state.json"), key=lambda p: int(p.parent.name.split("-")[1]))[-1].read_text())
        if rec["state"] == "COMPLETE":
            attempt = evidence / rec["outputs"]["attempt"]
        else:
            assert cell.name == "learned-n32-s1" and rec["state"] == "FAILED"
            attempt = cell / "epoch-1/attempt-1"
        done = json.loads((attempt / "done.json").read_text())["outputs"]
        metricpath, rowpath = attempt / "out/metrics.json", attempt / "out/per_example_results.jsonl"
        assert sha(metricpath) == done["metrics.json"] and sha(rowpath) == done["per_example_results.jsonl"]
        met = json.loads(metricpath.read_text())
        rows = [json.loads(line) for line in rowpath.read_text().splitlines()]
        ivs = sorted({r["intervention"] for r in rows})
        counts = {}
        for iv in ivs:
            selected = [r for r in rows if r["intervention"] == iv]
            acc = sum(r["correct"] for r in selected) / len(selected)
            assert len(selected) == 1024 and acc == met["final"]["heldout_" + iv]["accuracy"]
            episodes(rows, iv)
            counts[iv] = {"accuracy": acc, "correct": sum(r["correct"] for r in selected), "total": len(selected)}
        preview[cell.name] = {"arm": met["arm"], "n": met["n_bindings"], "seed": met["seed"],
                              "state": rec["state"], "readout": met["readout"], "counts": counts}
        saved[(met["arm"], met["n_bindings"], met["seed"])] = rows
        hashes[cell.name] = {"metrics": sha(metricpath), "rows": sha(rowpath)}

learned = {}
for n in (16, 32):
    for seed in (0, 1):
        rows = saved[("learned", n, seed)]
        by_iv = {iv: {(r["batch"], r["episode"], r["query"]): r for r in rows if r["intervention"] == iv}
                 for iv in ("none", "bank_derange")}
        equal = sum(r["pred"] == by_iv["bank_derange"][k]["pred"] for k, r in by_iv["none"].items())
        learned[f"n{n}-s{seed}"] = {
            "none_minus_random_fixed": paired(rows, saved[("random_fixed", n, seed)]),
            "none_minus_bank_derange": paired(rows, rows, ivb="bank_derange"),
            "none_minus_read_offset": paired(rows, rows, ivb="read_offset"),
            "bank_derange_identical_predictions": equal,
            "prediction_total": len(by_iv["none"])}

p2c = {}
oldroot = ROOT / "plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/readings-v1"
for seed in (0, 1):
    path = oldroot / f"rows-n32-s{seed}-curriculum.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    e = episodes(rows, "none")
    p2c[str(seed)] = {"accuracy_none": statistics.mean(e.values()), "rows_sha256": sha(path)}

result = {"status": "PASS", "population": "training artifact heldout 9300011+s, not reserved readings 9600011+s",
          "preview": preview, "learned_diagnostics_descriptive": learned,
          "previous_p2c_n32_reserved": p2c, "artifact_hashes": hashes,
          "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "model_invocations": 0, "remote_mutations": 0, "artifact_edits": 0}
(OUT / "preview-check.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"status": result["status"], "cells": len(preview), "learned": learned,
                  "previous_p2c_n32_reserved": p2c, "completed_utc": result["completed_utc"]}))
