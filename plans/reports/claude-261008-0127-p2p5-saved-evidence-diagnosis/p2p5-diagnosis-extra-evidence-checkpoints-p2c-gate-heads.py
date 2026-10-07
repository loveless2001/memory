"""Extra hash-bound evidence for the P2.5 saved-evidence diagnosis (codex 21745 #2-#4). Imported by
p2p5-saved-evidence-diagnosis.py, which passes its `bind` (read + sha256-record) so every file here is indexed too.

  * l20_beta_drift: learned-n32 s0/s1 L20 beta_proj tensors at updates 50/100/500/1500 (weight inspection only).
  * p2c_reference:  P2C curriculum-learned-n32 metrics + the N32 dev values quoted in P2C RESULTS.md.
  * gate_heads:     full-precision per-head gate means from the readings report, incl. intermediate values.
"""

import json
import re

import torch

CELLS = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-qwen3-0p6b-screen-v1/learned-n32/volume-evidence/collect-1/learned-n32/cells"
CKPT_STEPS = ((1, 50), (2, 100), (10, 500), (30, 1500))
P2C_RUNS = "plans/261005-0210-m4-sgm-p0-p2/runs/p2c-filler-curriculum-v1"
P2C_RESULTS = "plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/readings-v1/RESULTS.md"
INTERMEDIATE = (0.01, 0.99)     # illustrative descriptive cutoff only, not a saturation criterion (codex 21745 #4)


def l20_beta_drift(root, bind) -> dict:
    """Exact tensor differences of the L20 write-gate projection between updates 50 and 1500 (no forward pass)."""
    out = {}
    for s in ("s0", "s1"):
        snaps = {}
        for g, st in CKPT_STEPS:
            p = root / CELLS / f"learned-n32-{s}/epoch-1/gen-{g}-step{st}.pt"
            bind(p)
            a = torch.load(p, map_location="cpu", weights_only=False)["adapters"]
            snaps[st] = (a["20.beta_proj.weight"].double(), a["20.beta_proj.bias"].double())
        (w0, b0), (w1, b1) = snaps[50], snaps[1500]
        dw, db = w1 - w0, b1 - b0
        out[s] = {"weight_norm": {str(st): float(w.norm()) for st, (w, _b) in snaps.items()},
                  "bias": {str(st): b.tolist() for st, (_w, b) in snaps.items()},
                  "delta_50_to_1500": {"weight_l2": float(dw.norm()), "weight_max_abs": float(dw.abs().max()),
                                       "weight_changed_elements": int((dw != 0).sum()), "weight_elements": dw.numel(),
                                       "bias_l2": float(db.norm()), "bias_max_abs": float(db.abs().max()),
                                       "bias_changed_elements": int((db != 0).sum())}}
    return out


def p2c_reference(root, bind) -> dict:
    """P2C (tiny model, taskhead readout) comparators. Cross-model values are descriptive only."""
    out = {}
    for s in (0, 1):
        m = json.loads(bind(root / P2C_RUNS / f"curriculum-learned-n32-s{s}/metrics.json"))
        f, tl = m["final"]["heldout_none"], m["train_last"]
        out[f"s{s}"] = {"readout": m["readout"], "none": f["accuracy"],
                        "bank_derange": m["final"]["heldout_bank_derange"]["accuracy"],
                        "query_empty_read_weight": f["query_empty_read_weight"],
                        "effective_cells_mean": f["effective_cells_mean"],
                        "beta_by_token_class": f.get("beta_by_token_class"),
                        "train_last_step": tl["step"],
                        "train_last_beta_grad_norm": {k: v for k, v in tl["grad_norm"].items() if k.endswith("/beta")}}
    text = " ".join(bind(root / P2C_RESULTS).decode().split())
    m = re.search(r"at updates 1000, 1200 and 1500 is ([\d.]+)% / ([\d.]+)%, ([\d.]+)% / ([\d.]+)%, "
                  r"and ([\d.]+)% / ([\d.]+)%, respectively, at N32", text)
    if not m:
        raise SystemExit("P2C RESULTS.md dev sentence not found")
    v = [float(x) for x in m.groups()]
    out["dev_n32_pct"] = {"1000": v[0:2], "1200": v[2:4], "1500": v[4:6], "seeds": ["s0", "s1"]}
    return out


def gate_heads(readings: dict) -> dict:
    """Per-head binding/filler effective gate means at full precision; counts intermediate head/class means."""
    lo, hi = INTERMEDIATE
    total, inter, l20_s1 = 0, [], {}
    for n, v in readings["n"].items():
        for corner, c in v["corners"].items():
            g = c.get("gate_telemetry_descriptive") or {}
            if g.get("status") != "measured":
                continue
            for h, x in g["per_head"].items():
                if corner == "learned-n32-s1" and h.startswith("L20h"):
                    l20_s1[h] = {"binding": x["binding_effective_mean"], "filler": x["filler_effective_mean"]}
                for cls in ("binding", "filler"):
                    total += 1
                    m = x[f"{cls}_effective_mean"]
                    if lo < m < hi:
                        inter.append([f"{corner}@N{n}", h, cls, m])
    return {"head_class_means": total, "cutoff": list(INTERMEDIATE), "strictly_between": len(inter),
            "intermediate": inter, "learned_n32_s1_L20": l20_s1}
