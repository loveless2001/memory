"""Compact per-layer table (head means) from run-v1/*.json; descriptive only. Usage: python summarize-run.py RUN_DIR"""
import json, sys
from pathlib import Path
run = Path(sys.argv[1])
cols = [("absent_w", "query_read_absent_weight_mean"), ("all_abs", "query_read_all_positive_cells_absent_fraction"),
        ("in1cell", "align_within_1_cell"), ("couple", "align_spatial_coupling_mean"),
        ("offset", "centroid_offset_cells"), ("r_sprd", "read_spread_cells"), ("w_sprd", "value_write_spread_cells"),
        ("q_cos", "query_q_mean_pairwise_cos"), ("k_cos", "value_k_mean_pairwise_cos"), ("q.kb", "cos_q_bound_k_mean")]
m = lambda v: sum(v) / len(v)
order = [d["name"] for d in json.loads((run / "run.json").read_text())["done"]]
for name in order:
    d = json.loads((run / f"{name}.json").read_text())
    if d["kind"] == "grad_at_init":
        g = d["grad_reach_at_init"]
        print(f"\n{name}: loss {g['loss']:.4f} head_grad {g['head_grad_norm']}")
        for k, v in g["grad_norm"].items():
            if k.split("/")[1] in ("address_mlp", "q_proj", "k_proj", "value", "out_proj"):
                print(f"   {k:18s} {v if v is None else f'{v:.3e}'}")
        continue
    chk = d["training_dev_eval_check"]
    print(f"\n{name}: occ {d['bank']['occupancy_mean']:.1f} eff {d['bank']['effective_cells_mean']:.1f} "
          f"check {chk['status']} logged_acc {chk['logged_training_dev_accuracy_not_recomputed']:.4f}")
    print("   layer " + " ".join(f"{c:>8s}" for c, _ in cols))
    for l, v in d["per_layer_head"].items():
        print(f"   {l:>5s} " + " ".join(f"{m(v[k]):8.3f}" for _, k in cols))
