"""Fixed CPU mathematical examples, saved-JSON arithmetic; no model or optimizer."""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import torch
import torch.nn.functional as F
from memsub.sgm.delta_memory import delta_update, read_memory
from memsub.sgm.interpolation import stencil_2d
from memsub.sgm.sparse_cell_bank import SparseBankSet

torch.set_num_threads(1)
torch.manual_seed(0)


def tensor(data, grad=False):
    return torch.tensor(data, dtype=torch.float32, device="cpu", requires_grad=grad)


def plain(x):
    return None if x is None else x.detach().tolist()


def one_write_read(value, read_xy):
    """Actual sparse bank, exact delta kernel and stencil; fixed binary CE head."""
    banks = SparseBankSet(1, (0,), 1, 1, 1, 100, device="cpu")
    aw = tensor([[[0., 0.]]], True)
    ar = tensor([[read_xy]], True)
    q, k = tensor([[[1.]]], True), tensor([[[1.]]], True)
    v, beta = tensor([[[value]]], True), tensor([[.5]], True)
    iw, ww = stencil_2d(aw)
    cells, _ = banks.gather(0, iw)
    banks.scatter(0, iw, delta_update(cells, ww, beta, k, v), ww)
    ir, wr = stencil_2d(ar)
    cells, present = banks.gather(0, ir)
    r = read_memory(cells, wr, q)
    logits = torch.cat([r.flatten(1), torch.zeros(1, 1)], dim=1)
    loss = F.cross_entropy(logits, torch.tensor([0], device="cpu"))
    grads = torch.autograd.grad(loss, (ar, aw, q, k, v, beta), allow_unused=True, retain_graph=True)
    absent = (wr * (~present)).sum()
    absent_grad, = torch.autograd.grad(absent, ar)
    return {"value": value, "read_xy": read_xy, "read": plain(r),
            "loss": float(loss.detach()), "absent_mass": float(absent.detach()),
            "loss_grad": {name: plain(g) for name, g in zip(
                ("read_address", "write_address", "q", "k", "v", "beta"), grads)},
            "absent_mass_read_address_grad": plain(absent_grad)}


cases = {"helpful_value": one_write_read(4., [.6, 0.]),
         "harmful_value": one_write_read(-4., [.6, 0.]),
         "exact_empty_stencil": one_write_read(4., [10., 10.]),
         "partial_empty_stencil": one_write_read(4., [1.4, 0.])}
assert cases["helpful_value"]["loss_grad"]["read_address"][0][0][0] > 0
assert cases["harmful_value"]["loss_grad"]["read_address"][0][0][0] < 0
empty = cases["exact_empty_stencil"]
assert empty["read"] == [[[0.]]]
assert empty["loss_grad"]["read_address"] == [[[0., 0.]]]
assert empty["loss_grad"]["write_address"] is None
assert empty["absent_mass_read_address_grad"] == [[[0., 0.]]]
assert cases["partial_empty_stencil"]["absent_mass_read_address_grad"][0][0][0] > 0

# Independent symmetric logit noise, fixed target 0: an exact two-point expectation.
noise = []
for amplitude in (0., .25, 1., 2.):
    scale = tensor(amplitude, True)
    logits = torch.stack([torch.stack([scale, scale * 0]),
                          torch.stack([-scale, scale * 0])])
    loss = F.cross_entropy(logits, torch.zeros(2, dtype=torch.long, device="cpu"))
    grad, = torch.autograd.grad(loss, scale)
    noise.append({"amplitude": amplitude, "expected_loss": float(loss.detach()),
                  "amplitude_derivative": float(grad)})
assert noise[0]["expected_loss"] < noise[-1]["expected_loss"]
assert noise[-1]["amplitude_derivative"] > 0

# A common final address bias changes both outputs equally at fixed features.
mlp = torch.nn.Sequential(torch.nn.Linear(4, 8), torch.nn.SiLU(), torch.nn.Linear(8, 2))
q, k = F.normalize(torch.randn(7, 4), dim=-1), F.normalize(torch.randn(7, 4), dim=-1)
with torch.no_grad():
    before_r, before_w = mlp(q), mlp(k)
    mlp[-1].bias.add_(tensor([.125, -.25]))
    after_r, after_w = mlp(q), mlp(k)
    differential_error = float(((after_r - after_w) - (before_r - before_w)).abs().max())
assert differential_error < 1e-6

# A coordinate loss without the compact-support mask can restore a distant read.
ar = tensor([10., 10.], True)
distance = ((ar - tensor([0., 0.])) ** 2).sum()
distance_grad, = torch.autograd.grad(distance, ar)

# Pair alignment alone admits a constant address function, irrespective of features.
q, k = torch.randn(5, 4), torch.randn(5, 4)
constant_map = torch.nn.Linear(4, 2)
with torch.no_grad():
    constant_map.weight.zero_()
    constant_map.bias.fill_(2.)
pair_loss = ((constant_map(q) - constant_map(k)) ** 2).mean()
assert float(pair_loss.detach()) == 0.

# Read existing diagnosis JSONs only; no fresh episodes or model execution.
diagnosis = ROOT / "plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis/run-v1"
metrics = ("query_read_absent_weight_mean", "query_read_all_positive_cells_absent_fraction",
           "query_q_mean_pairwise_cos", "value_k_mean_pairwise_cos",
           "cos_q_bound_k_mean", "centroid_offset_cells", "binding_pair_intersect_rate")
saved = []
for path in sorted(diagnosis.glob("*.json")):
    obj = json.loads(path.read_text())
    if "per_layer_head" not in obj:
        continue
    row = {"file": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    for metric in metrics:
        xs = [x for layer in obj["per_layer_head"].values() for x in layer[metric]]
        row[metric] = {"head_mean": sum(xs) / len(xs), "head_min": min(xs), "head_max": max(xs)}
    saved.append(row)

stage = ROOT / "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/stage-a-run-v1"
telemetry = {}
for arm, lr in (("A0", .003), ("A1", .0003)):
    path = stage / arm / "routing_telemetry.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    first = next(row for row in rows if row.get("step") == 0 and "update_norm" in row)
    telemetry[arm] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "evals": [{"step": row["step"], "absent_mass": row["eval"]["query_empty_read_weight"],
                   "accuracy": row["eval"]["accuracy"]} for row in rows if "eval" in row],
        "initial_address_update_sum_of_tensor_norms": {
            key: value for key, value in first["update_norm"].items() if key.endswith("/address_mlp")},
        "first_step_sign_limit_sum_of_tensor_norms": lr * sum(math.sqrt(n) for n in (32*64, 64, 64*2, 2)),
        "first_step_sign_limit_concatenated_l2": lr * math.sqrt(32*64 + 64 + 64*2 + 2)}

sources = ("memsub/sgm/delta_memory.py", "memsub/sgm/interpolation.py",
           "memsub/sgm/sparse_cell_bank.py", "memsub/sgm/layer_adapter.py",
           "memsub/runtime/sgm_model_runtime.py", "memsub/sgm/synthetic_pilot.py",
           "memsub/sgm/synthetic_pilot_evaluation.py", "memsub/sgm/address_supervision.py")
out = {"scope": "Fixed CPU autograd examples and saved JSON arithmetic; no model, optimizer, training or GPU calls",
       "torch": torch.__version__, "device": "cpu", "threads": torch.get_num_threads(), "seed": 0,
       "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
       "actual_kernel_cases": cases, "symmetric_independent_logit_noise": noise,
       "shared_final_bias_differential_error": differential_error,
       "distance_to_fixed_occupied_cell_gradient": plain(distance_grad),
       "constant_map_pair_loss": float(pair_loss.detach()),
       "stage_a_saved_telemetry": telemetry, "saved_geometry_head_summaries": saved}
print(json.dumps(out, indent=2))
