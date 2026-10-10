"""Independent, CPU-only correction of the historical L40S v2 52/20 model.

This computes a supplement; it never edits the historical ledger and is not a
packed A100 price, measured long-run bound, or launch authorization.
"""
import ast
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
PROFILE = PLAN / "p2p5-l40s-profile-v2/volume-evidence/p2p5-l40s-profile-v2/profile-l40s/profile.json"
OLD = PLAN / "p2p5-l40s-profile-v2/campaign-ledger-from-profile-v2-52-20.json"
GRID = ROOT / "configs/m4_sgm_p2p5_grid.json"
PREREG = PLAN / "prereg.md"
RUN = ROOT / "memsub/sgm/synthetic_pilot_run.py"
EVAL = ROOT / "memsub/sgm/synthetic_pilot_evaluation.py"
OUT = Path(__file__).with_suffix(".json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen = {str(p.relative_to(ROOT)): sha(p) for p in (PROFILE, OLD, GRID, PREREG, RUN, EVAL)}
    assert sha(PROFILE) == "ff2a7a437a3a1ae43d8c720522ff97e130650d82b2035d6c69efbc95083f862b"
    assert sha(GRID) == "d1c045eadfb562829cab72f58ba6b293f573f2e853629d3a3dd324b740a13073"
    assert sha(PREREG) == "0ce61a096b0c7150e00f0a604ed85cb8f9694584cb70790d43d5fb3d010c2002"
    profile, grid, old = (json.loads(p.read_text()) for p in (PROFILE, GRID, OLD))
    ivs = next(ast.literal_eval(n.value) for n in ast.parse(EVAL.read_text()).body
               if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "INTERVENTIONS" for t in n.targets))
    assert ivs == ("none", "bank_derange", "coord_shuffle", "read_offset", "query_off")
    # Source inspection: evaluate returns None for single_cell/coord_shuffle;
    # run_pilot uses all applicable interventions plus max(2,16//4) train batches.
    counts = {a: (1 if a == "memory_off" else len(ivs) - (a == "single_cell")) * 16 + 4
              for a in ("learned", "random_fixed", "oracle", "single_cell", "memory_off")}
    assert counts == {"learned": 84, "random_fixed": 84, "oracle": 84, "single_cell": 68, "memory_off": 20}
    cfgs = {(c["arm"], c["train_filler_len"]): c for c in profile["configs"]}
    cells = [(b["tag"], b["override"]["arm"], n, s) for b in grid["blocks"] for n in b["n_bindings"] for s in b["seeds"]]
    assert len(cells) == 18 and len({(a, n) for _, a, n, _ in cells}) == 9
    rate = .000542 + 4 * .0000131 + 32 * .00000222
    assert math.isclose(rate, old["usd_per_container_s"], abs_tol=1e-14)
    base = grid["base"]
    assert base["steps"] == 1500 and base["filler_len_schedule"] == [[0, 0], [1000, 40]]

    def calculate(basis, corrected):
        factor = 1.4 if basis == "bound" else 1.0
        scale = lambda n, f: (4 + 2*n + f + 4) / (4 + 2*32 + f + 4) if basis == "estimate" else 1.0
        rows, total, rd = [], 0.0, 0.0
        for tag, arm, n, seed in cells:
            proxy = "memory_off" if arm == "memory_off" else "learned"
            train = sum(updates * cfgs[(proxy, f)]["mean_measured_s_per_update"] * scale(n, f)
                        for updates, f in ((1000, 0), (500, 40)))
            eval_s = max(cfgs[(proxy, f)]["dev_eval_batch_s"] for f in (0, 40)) * scale(n, 40)
            batches = counts[arm] if corrected else 20 if arm == "memory_off" else 52
            wall = train + ((1500 // 100 + 1) * 4 + batches) * eval_s + 300
            life = wall * factor + (240 if factor > 1 else 0)
            rows.append({"cell": f"{tag}-n{n}-s{seed}", "artifact_batches": batches,
                         "eval_batch_s": eval_s, "wall_s": wall, "charged_life_s": life})
            total += life
            for pn in ([32, 16] if arm == "oracle" else [n]):
                rd += 16 * (1 if arm == "memory_off" else 3) * max(cfgs[(proxy, f)]["dev_eval_batch_s"] for f in (0, 40)) * scale(pn, 40)
        rd = (rd * 1.1 + 300) * factor
        # Preserve historical calculation, including its rounding of max life
        # before sizing the reaper allowance.
        longest = max(round(r["charged_life_s"], 1) for r in rows)
        parts = {"cells_usd": total * rate, "readings_usd": rd * rate,
                 "image_build_usd": 1200 * 2 * (4 * .0000131 + 8 * .00000222),
                 "reaper_usd": math.ceil(longest/120 + 2) * 110 * (.125 * .0000131 + .25 * .00000222),
                 "fixed_margin_usd": 5.0 if factor > 1 else 0.0}
        return {"cells": rows, "cell_gpu_hours": total/3600, "readings_s": rd,
                **parts, "total_usd": sum(parts.values()), "longest_cell_life_h": longest/3600}

    results = {}
    for basis in ("estimate", "bound"):
        reproduced, corrected = calculate(basis, False), calculate(basis, True)
        for field in ("cell_gpu_hours", "readings_s", "cells_usd", "readings_usd", "image_build_usd",
                      "reaper_usd", "fixed_margin_usd", "total_usd", "longest_cell_life_h"):
            assert math.isclose(reproduced[field], old["bases"][basis][field], rel_tol=1e-12, abs_tol=1e-10), field
        assert corrected["readings_s"] == reproduced["readings_s"]
        results[basis] = {"historical_total_usd": reproduced["total_usd"], "corrected": corrected,
                          "increase_usd": corrected["total_usd"] - reproduced["total_usd"]}
    assert frozen == {str(p.relative_to(ROOT)): sha(p) for p in (PROFILE, OLD, GRID, PREREG, RUN, EVAL)}
    result = {"status": "PASS_arithmetic_and_preservation_only", "input_sha256": frozen,
              "artifact_eval_batches_by_arm": counts, "usd_per_container_s": rate, "bases": results,
              "limitations": ["Historical L40S timing/proxy/linear-N16 assumptions retained.",
                              "The old key 'bound' is a planning reserve, not a measured or enforced execution bound.",
                              "Preemption, packed A100 overhead and performance are not modeled here.",
                              "No registered training, reserved readings, Modal call or spending."]}
    with OUT.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps({k: {"historical_usd": v["historical_total_usd"], "corrected_usd": v["corrected"]["total_usd"],
                          "increase_usd": v["increase_usd"]} for k, v in results.items()}, indent=2))


if __name__ == "__main__":
    main()
