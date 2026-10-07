"""Readout probe READING (proposal v0.2 §5/§6; EXPLORATORY), local CPU only, write-once.

Inputs:
  * the probe collect status and fetched evidence. Both taskhead cells must be COMPLETE, and each is RE-VALIDATED
    here with the path-exact probe validator (the same function as the COMPLETE transition and collection).
  * the saved P2.5 residual-head comparator rows (learned-n32-s0/s1), bound by sha256. The seed-1 file is the
    post-hoc amended cell's output: its sha must equal the amendment spec's bound output hash. That cell's original
    FAILED record is unchanged.
Rules (existing code reused unchanged, bound by sha; no new thresholds):
  * contrast C  = P2G `classify` over the per-seed `P2D.paired(taskhead, residual, "none", "none")`
  * reused bank-dependence criterion B = `P2D.memory_use(taskhead rows)["pass"]` on BOTH seeds
  * reading: unavailable / gain + B / gain without B / not shown. Pairing is by (batch, episode, episode_hash, query);
    if any differs the contrast is unavailable and is never re-paired.

    .venv/bin/python scripts/sgm-p2p5-readout-probe-reading.py --out <probe-reading.json>
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-qwen3-0p6b-screen-v1/learned-n32/volume-evidence/collect-1/learned-n32/cells"
COMPARATOR = {"0": (f"{CAMPAIGN}/learned-n32-s0/epoch-1/attempt-1/out/per_example_results.jsonl",
                    "ec67c4ac4361d5ed621acb072f04062aca091c08e3c1fbe548518396d1d89f5c"),
              "1": (f"{CAMPAIGN}/learned-n32-s1/epoch-1/attempt-1/out/per_example_results.jsonl",
                    "f34311e1f97e3cb6ce54fba90c1271184b2c8812ce39994986d51f2f6c2d1e62")}
AMENDMENT_SPEC = "configs/m4_sgm_p2p5_pk_posthoc_validation_amendment.json"
LABEL = "EXPLORATORY (known artifact population; not a registered screen result)"
GAIN_B = "taskhead recipe improves learned N32; the reused bank-dependence criterion is met (exploratory)"
GAIN_NO_B = "taskhead recipe improves learned N32; the reused bank-dependence criterion is not met (exploratory)"
INPUTS: dict = {}


def bind(p: Path) -> bytes:
    data = Path(p).read_bytes()
    INPUTS[str(Path(p).resolve().relative_to(ROOT.resolve()))] = hashlib.sha256(data).hexdigest()
    return data


def load(rel: str, name: str):
    bind(ROOT / rel)
    s = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def rows_of(p: Path) -> list:
    return [json.loads(x) for x in bind(p).decode().splitlines() if x.strip()]


def pairing_problem(t_rows: list, r_rows: list) -> str | None:
    key = lambda r: (r["batch"], r["episode"], r["episode_hash"], r["query"])  # noqa: E731
    t = {key(r): r["label"] for r in t_rows if r["intervention"] == "none"}
    r = {key(x): x["label"] for x in r_rows if x["intervention"] == "none"}
    if set(t) != set(r):
        return "episode hashes / keys differ from the residual-head comparator"
    if any(t[k] != r[k] for k in t):
        return "labels differ on a paired key"
    return None


def decide(states: dict, t_rows: dict, r_rows: dict, P2D, P2G) -> dict:
    """Pure ordered reading. states: cell -> report ({state, validation}); rows keyed by seed "0"/"1"."""
    out = {"label": LABEL}
    bad = next(((c, s) for c, s in sorted(states.items())
                if not (s.get("state") == "COMPLETE" and s.get("validation") == "valid")), None)
    if bad:
        out["reading"] = f"probe unavailable: {bad[0]}: {bad[1].get('state')} ({bad[1].get('validation') or bad[1].get('problem') or bad[1].get('reason')})"
        return out
    for s in ("0", "1"):
        problem = pairing_problem(t_rows[s], r_rows[s])
        if problem:
            out["reading"] = f"probe unavailable: seed {s}: {problem}"
            return out
    per_seed = {s: P2D.paired(t_rows[s], r_rows[s], "none", "none") for s in ("0", "1")}
    c = P2G.classify(per_seed)
    mem = {s: P2D.memory_use(t_rows[s]) for s in ("0", "1")}
    b = all(m["pass"] for m in mem.values())
    out.update(contrast={"per_seed_taskhead_minus_residual": per_seed, "label": c},
               bank_dependence={"per_seed": mem, "met": b},
               accuracy={s: {"taskhead": _acc(t_rows[s]), "residual_head": _acc(r_rows[s])} for s in ("0", "1")})
    out["reading"] = (GAIN_B if c == P2G.GAIN and b else GAIN_NO_B if c == P2G.GAIN
                      else f"rescue by the taskhead recipe not shown (C = {c})")
    return out


def _acc(rows: list) -> dict:
    by = {}
    for r in rows:
        by.setdefault(r["intervention"], []).append(r["correct"])
    return {iv: sum(v) / len(v) for iv, v in sorted(by.items())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    L = load("modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-logic.py", "slot_logic")
    PV = load(L.VALIDATOR_FILE, "probe_validation")
    P2D = load("scripts/sgm-p2d-step2-decision-rules.py", "p2d")
    P2G = load("scripts/sgm-p2g-decision-rules.py", "p2g")
    bind(ROOT / "scripts/sgm-p2d-step2-decision-rules.py")      # P2G imports this exact file by path
    spec = json.loads(bind(ROOT / AMENDMENT_SPEC))
    if spec["outputs"]["per_example_results.jsonl"] != COMPARATOR["1"][1]:
        raise SystemExit("seed-1 comparator hash differs from the amendment spec's bound output")
    r_rows = {}
    for s, (rel, h) in COMPARATOR.items():
        r_rows[s] = rows_of(ROOT / rel)
        if INPUTS[rel] != h:
            raise SystemExit(f"comparator seed {s} sha {INPUTS[rel]} != bound {h}")
    root = ROOT / L.LOCAL_OUT / L.GROUP / L.SLOT
    status = json.loads(bind(root / "collect_status.json"))
    if (status.get("final_shutdown") or {}).get("status") != "stopped_verified":
        raise SystemExit("probe collect is not stopped_verified: no reading")
    grid = json.loads(bind(ROOT / L.GRID_FILE))
    cells = L.probe_cells(grid)
    registry = json.loads(bind(ROOT / L.REGISTRY_FILE))["learned"]
    schema = json.loads(bind(ROOT / L.SCHEMA_FILE))["learned"]
    memsub = json.loads(bind(root / "launch_provenance.json"))["expected_identity"]["memsub"]
    admitted = sorted(int(k.split("-")[1]) for k in json.loads(bind(root / "admission.json")) if k.startswith("start-"))
    ev = ROOT / status["evidence_dir"]
    states, t_rows = {}, {}
    for c, p in cells.items():
        states[c] = L.cell_report(ev / L.SLOT / "cells" / c, p, admitted, memsub, registry, schema, terminal=True,
                                  validate=PV.validate_probe_outputs)
        if states[c].get("state") == "COMPLETE" and states[c].get("validation") == "valid":
            from memsub.sgm import packed_slot_epoch_state as es
            rec = es.read_record(ev / L.SLOT / "cells" / c, states[c]["epoch"])
            t_rows[str(p["seed"])] = rows_of(ev / L.SLOT / rec["outputs"]["attempt"] / "out" / "per_example_results.jsonl")
    report = {"format": "p2p5-readout-probe-reading-v1", "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "cells": states, **decide(states, t_rows, r_rows, P2D, P2G),
              "comparator_note": "seed-1 residual-head rows = the post-hoc amended cell's bound outputs (original FAILED record unchanged)"}
    report["inputs_sha256"] = dict(sorted(INPUTS.items()))
    with open(a.out, "x") as f:                          # write-once
        f.write(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
    print(report["reading"])


if __name__ == "__main__":
    main()
