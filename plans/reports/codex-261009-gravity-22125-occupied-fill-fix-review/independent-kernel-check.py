"""CPU-only fixed kernel checks; supply an isolated candidate source tree as argv[1]."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import torch
from memsub.sgm.sparse_cell_bank import SparseBankSet
from memsub.sgm.interpolation import stencil_2d
from memsub.sgm.occupied_cell_read_fallback import fill_read, query_anchor_loss
from memsub.sgm.delta_memory import read_memory

torch.set_num_threads(1)


def run(xy, contents):
    a = torch.tensor([[xy]], dtype=torch.float32, requires_grad=True)
    bank = SparseBankSet(1, (0,), 1, 1, 1, 100)
    bank.cells[(0, 0, 0)] = {xy: torch.tensor([[value]], dtype=torch.float32)
                            for xy, value in contents.items()}
    indices, weights = stencil_2d(a)
    cells, present = bank.gather(0, indices, mask=False)
    q = torch.ones(1, 1, 1)
    trace = {}
    base = read_memory(cells, weights, q)
    fill = fill_read(bank, 0, a, weights, present, q, 1., trace)
    row = trace['query_fallback'][0]
    return a, base, fill, trace, weights, present


full = {(x, y): float(x*x + 3*y + 1) for x in range(-3, 4) for y in range(-3, 4)}
roundoff = []
for xy in [(0.7645385265350342, 0.8300079107284546),
           (-0.40615832805633545, 0.6633709669113159)]:
    a, base, fill, trace, weights, present = run(xy, full)
    grad, = torch.autograd.grad(query_anchor_loss([trace]), a)
    absent = (weights * (~torch.tensor(present).view_as(weights))).sum()
    roundoff.append({'address': list(xy), 'all_stencil_cells_present': all(present),
                     'direct_absent_mass': float(absent.detach()),
                     'present_mass': float(trace['query_fallback'][0]['present_mass']),
                     'base_read': float(base.detach()), 'fill': float(fill.detach()),
                     'filled_read': float((base + fill).detach()),
                     'bitwise_same': bool(torch.equal(base, base + fill)),
                     'anchor': float(trace['query_anchor'][0].detach()),
                     'anchor_gradient': grad.tolist()})

# Independent derivative check for the task read, including the missing-mass term.
contents = {(0, 0): 1.7, (2, 1): -.4}
point = [.6, .2]
a, base, fill, trace, _, _ = run(point, contents)
analytic, = torch.autograd.grad((base + fill).sum(), a)
numeric = []
for axis in range(2):
    lo, hi = list(point), list(point)
    lo[axis] -= .001
    hi[axis] += .001
    _, bl, fl, *_ = run(lo, contents)
    _, bh, fh, *_ = run(hi, contents)
    numeric.append(float(((bh + fh - bl - fl) / .002).detach()))
error = max(abs(x-y) for x, y in zip(analytic.flatten().tolist(), numeric))
assert error < .001

# Anchor derivative must equal the nearest-cell pseudo-Huber derivative on a fully empty read.
a, _, _, trace, _, _ = run([7., -3.], {(0, 0): 1., (1, 0): -1.})
gradient, = torch.autograd.grad(query_anchor_loss([trace]), a)
delta = a.detach() - torch.tensor([[[1., 0.]]])
expected = delta / torch.sqrt(1 + (delta ** 2).sum(-1, keepdim=True))
assert torch.allclose(gradient, expected, atol=1e-7)

print(json.dumps({'device': 'cpu', 'torch': torch.__version__,
                  'module_sha256': hashlib.sha256(Path(sys.argv[1], 'memsub/sgm/occupied_cell_read_fallback.py').read_bytes()).hexdigest(),
                  'fully_supported_roundoff_cases': roundoff,
                  'partial_read_derivative': {'autograd': analytic.tolist(), 'finite_difference': numeric, 'max_error': error},
                  'far_empty_anchor_derivative': {'autograd': gradient.tolist(), 'expected': expected.tolist()},
                  'fully_supported_exact_contract_passes': all(r['fill'] == 0 and r['anchor'] == 0 for r in roundoff)}, indent=2))
