"""occupied_softmax_fill_v1 query-read fallback: identity, exact rule, gradients, scope (CPU)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
import torch
import torch.nn.functional as F

from memsub.sgm.config import SGMConfig
from memsub.sgm.delta_memory import read_memory
from memsub.sgm.interpolation import stencil_2d
from memsub.sgm.occupied_cell_read_fallback import fallback_summary, fill_read, query_anchor_loss
from memsub.sgm.sparse_cell_bank import SparseBankSet

ON = dict(read_fallback="occupied_softmax_fill_v1", read_fallback_tau=1.0, read_fallback_anchor=0.1)
MANIFESTS = [
    "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/stage-a-run-v1/A0/run_manifest.json",
    "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json",
]


# -- identity -----------------------------------------------------------------------------
@pytest.mark.parametrize("path", MANIFESTS)
def test_existing_policy_ids_unchanged(path):
    man = json.loads(Path(path).read_text())
    cfg = SGMConfig.from_json(man["sgm_config"])
    assert cfg.policy_id == man["policy_id"] and cfg.to_json() == man["sgm_config"]


def test_config_validation_and_distinct_identity():
    base = dict(selected_layers=(1,))
    off = SGMConfig(**base)
    assert "read_fallback" not in off.to_json()
    on = SGMConfig(**base, **ON)
    assert on.to_json()["read_fallback"] == ON["read_fallback"] and on.policy_id != off.policy_id
    assert SGMConfig.from_json(on.to_json()).policy_id == on.policy_id
    for bad in (dict(read_fallback="nearest"), dict(read_fallback_anchor=0.1), dict(read_fallback_tau=2.0),
                {**ON, "address_mode": "oracle"},
                {**ON, "read_fallback_tau": 0.0}, {**ON, "read_fallback_tau": math.inf},
                {**ON, "read_fallback_anchor": -1.0}):
        with pytest.raises(ValueError):
            SGMConfig(**base, **bad)


# -- the rule on a hand-built bank (dk = dv = 1) --------------------------------------------
def _banks(cells_by_bank: list[dict]) -> SparseBankSet:
    banks = SparseBankSet(len(cells_by_bank), (0,), 1, 1, 1, 64)
    for b, cells in enumerate(cells_by_bank):
        banks.cells[(b, 0, 0)] = {xy: torch.tensor([[float(v)]]) for xy, v in cells.items()}
    return banks


def _read(banks, a, q=1.0, tau=1.0):
    """Spec read + fill for addresses a [B,2]; returns (r [B], trace)."""
    a = a.view(-1, 1, 2)
    idx, w = stencil_2d(a)
    cells, present = banks.gather(0, idx, mask=False)
    qv = torch.full((a.shape[0], 1, 1), q)
    trace: dict = {}
    r = read_memory(cells, w, qv) + fill_read(banks, 0, a, w, present, qv, tau, trace)
    return r.view(-1), trace


def test_fully_present_read_is_the_spec_read():
    cells = {(x, y): 0.1 * (x + 3 * y) for x in range(-2, 3) for y in range(-2, 3)}
    a = torch.tensor([[0.3, -0.2]])
    r, tr = _read(_banks([cells]), a)
    idx, w = stencil_2d(a.view(1, 1, 2))
    spec = sum(float(w[0, 0, c]) * cells[tuple(idx[0, 0, c].tolist())] for c in range(9))
    assert float(tr["query_fallback"][0]["present_mass"]) == pytest.approx(1.0)
    assert float(r) == pytest.approx(spec, abs=1e-6) and float(tr["query_anchor"][0]) == pytest.approx(0, abs=1e-7)


def test_codex_example_fill_gives_soft_address_gradient():
    """codex 22104 review: address (10,0), values 1.5 / -1 at (0,0) / (1,0). Hard nearest
    selection gave address gradient None; the soft fill gives a finite nonzero one."""
    a = torch.tensor([[10.0, 0.0]], requires_grad=True)
    r, tr = _read(_banks([{(0, 0): 1.5, (1, 0): -1.0}]), a, tau=4.0)
    assert float(tr["query_fallback"][0]["present_mass"]) == 0.0            # fully absent stencil
    loss = F.cross_entropy(torch.stack([r[0], torch.tensor(0.0)])[None], torch.tensor([0]))
    (g,) = torch.autograd.grad(loss, a)
    assert torch.isfinite(g).all() and float(g[0, 0]) != 0.0


def test_fill_softmax_only_reweights_but_anchor_pulls_back():
    """|a|^2 cancels in the softmax: the fill depends on a only through a.(c_i - c_j). A read
    moved 45 cells further from the bank, orthogonally to the cells' spread, gets the SAME
    fill and zero fill gradient along that axis; the anchor gradient points at the nearest
    occupied cell with |g| <= 1."""
    banks = _banks([{(0, 0): 1.0, (1, 0): -1.0}])
    a = torch.tensor([[0.4, 5.0]], requires_grad=True)
    r_near, _ = _read(banks, a)
    r_far, _ = _read(banks, torch.tensor([[0.4, 50.0]]))
    assert -1.0 < float(r_near) < 1.0                                       # both cells weighted
    assert float(r_near) == pytest.approx(float(r_far), abs=1e-6)          # no pull from the fill
    (g_fill,) = torch.autograd.grad(r_near.sum(), a)
    assert float(g_fill[0, 0]) != 0.0 and float(g_fill[0, 1]) == 0.0       # reweights x, no y pull
    a = torch.tensor([[7.0, -3.0]], requires_grad=True)
    _, tr = _read(banks, a)
    assert float(tr["query_fallback"][0]["present_mass"]) == 0.0          # far-empty read
    (g,) = torch.autograd.grad(query_anchor_loss([tr]), a)                 # anchor ALONE, no task loss
    to_nearest = torch.tensor([0.0, 0.0]) - a.detach()[0]
    assert float((-g[0]) @ to_nearest) > 0 and float(g.norm()) <= 1.0 + 1e-6


def test_fill_gradient_reaches_stored_content():
    """No hidden detach: a fully absent read's fill sends pi_j * q into every stored state."""
    s0 = torch.tensor([[1.0]], requires_grad=True)
    s1 = torch.tensor([[-1.0]], requires_grad=True)
    banks = SparseBankSet(1, (0,), 1, 1, 1, 64)
    banks.cells[(0, 0, 0)] = {(0, 0): s0, (1, 0): s1}
    r, tr = _read(banks, torch.tensor([[0.4, 9.0]]), q=2.0)
    assert float(tr["query_fallback"][0]["present_mass"]) == 0.0
    g0, g1 = torch.autograd.grad(r.sum(), [s0, s1])
    pi1 = torch.softmax(torch.tensor([0.0, 2 * 0.4 - 1.0]), 0)[1]          # (2 a.c - |c|^2) / tau
    assert float(g0) == pytest.approx(2.0 * (1 - float(pi1)), abs=1e-6)
    assert float(g1) == pytest.approx(2.0 * float(pi1), abs=1e-6)


def test_empty_bank_adds_nothing_and_stays_finite():
    banks = _banks([{}, {(0, 0): 2.0}])                    # batch 0 empty, batch 1 occupied
    a = torch.tensor([[5.0, 5.0], [5.0, 5.0]], requires_grad=True)
    r, tr = _read(banks, a)
    assert float(r[0]) == 0.0 and float(tr["query_anchor"][0][0, 0]) == 0.0
    (r.sum() + query_anchor_loss([tr])).backward()
    assert torch.isfinite(a.grad).all() and a.grad[0].abs().sum() == 0 and a.grad[1].abs().sum() > 0
    s = fallback_summary(tr["query_fallback"])
    assert s["query_without_occupied_fraction"] == 0.5 and s["query_fully_absent_fraction"] == 1.0


def test_read_is_continuous_across_a_stencil_boundary():
    banks = _banks([{(0, 0): 1.0, (1, 0): -0.5, (2, 1): 0.7}])
    eps = 1e-4
    lo, _ = _read(banks, torch.tensor([[1.5 - eps, 0.2]]))   # stencil centre 1
    hi, _ = _read(banks, torch.tensor([[1.5 + eps, 0.2]]))   # stencil centre 2
    assert float(lo) == pytest.approx(float(hi), abs=1e-3)


# -- scope inside the runtime (tiny backbone) ------------------------------------------------
def _runtime(fallback: bool):
    from memsub.runtime.sgm_model_runtime import SGMModelRuntime
    from memsub.sgm.synthetic_pilot import TINY_SGM_DEFAULTS, build_tiny_backbone
    cfg = SGMConfig(**{**TINY_SGM_DEFAULTS, **(ON if fallback else {})})
    return SGMModelRuntime(build_tiny_backbone(0), cfg, seed=0)


def test_ingest_identical_and_only_query_reads_change():
    from memsub.sgm.backend import SourceRef, SparseGrowingMemoryBackend
    torch.manual_seed(0)
    src, query = torch.randint(10000, 10800, (2, 12)), torch.randint(10000, 10800, (2, 1))
    out = {}
    for on in (False, True):
        rt = _runtime(on)
        be = SparseGrowingMemoryBackend(rt)
        st = be.ingest_source(be.new_state(2), src, SourceRef("s"))
        res = be.evaluate_query(st, query, detach=True, logits=False)
        out[on] = (st, res, rt)
    (s0, r0, _), (s1, r1, rt1) = out[False], out[True]
    assert s0.banks.cells.keys() == s1.banks.cells.keys()
    for key in s0.banks.cells:
        assert s0.banks.cells[key].keys() == s1.banks.cells[key].keys()
        assert all(torch.equal(s0.banks.cells[key][c], s1.banks.cells[key][c]) for c in s0.banks.cells[key])
    assert "query_fallback" not in r0["trace"]
    rows = r1["trace"]["query_fallback"]
    partial = [(l, (row["present_mass"] < 1).unsqueeze(-1)) for l, row in zip(rt1.cfg.selected_layers, rows)]
    assert any(bool(m.any()) for _, m in partial)                          # the fill is exercised
    for l, m in partial:                                                   # ... and changes those reads
        if m.any():
            assert not torch.equal(r1["reads"][l][:, -1][m.expand_as(r1["reads"][l][:, -1])],
                                   r0["reads"][l][:, -1][m.expand_as(r0["reads"][l][:, -1])])
    assert len(rows) == len(rt1.cfg.selected_layers) == len(r1["trace"]["query_anchor"])
    for l, row in zip(rt1.cfg.selected_layers, rows):
        same = (row["present_mass"] == 1).unsqueeze(-1)              # [B,H,1]
        assert torch.equal(torch.where(same, r1["reads"][l][:, -1], 0), torch.where(same, r0["reads"][l][:, -1], 0))
    # the original-stencil absent mass is still what EmptyReadWeight reports (before any fill)
    first = float(r1["trace"]["empty_read_weight"][0])
    assert first == pytest.approx(float(1 - rows[0]["present_mass"].mean()), abs=1e-6)


def test_tiny_training_with_fill_and_anchor():
    from memsub.sgm.synthetic_pilot import PilotConfig, train
    from memsub.sgm.synthetic_pilot_evaluation import evaluate
    pcfg = PilotConfig(arm="learned", readout="taskhead", n_bindings=4, n_queries=2, filler_len=4, steps=2,
                       batch=2, eval_every=2, eval_batches=1, seed=0, sgm=dict(ON))
    ev = lambda be, hd, s: evaluate(be, hd, pcfg.task_spec(), "learned", "taskhead", split="heldout",  # noqa: E731
                                    batches=1, batch_size=2, seed=4242)
    res = train(pcfg, log=lambda _r: None, evaluate_fn=ev)
    rows = [r for r in res["telemetry"] if "loss" in r]
    assert rows and all(math.isfinite(r["loss"]) and math.isfinite(r["read_anchor"]) for r in rows)
    evals = [r["eval"] for r in res["telemetry"] if "eval" in r]
    assert all({"query_fully_absent_fraction", "query_nearest_occupied_cells_mean",
                "query_fill_support_cells_mean", "query_without_occupied_fraction"} <= e.keys() for e in evals)
    assert res["sgm_config"]["read_fallback_anchor"] == 0.1 and "read-fallback" in pcfg.result_label()


def test_anchor_alone_reaches_the_address_mlp():
    from memsub.sgm.backend import SourceRef, SparseGrowingMemoryBackend
    rt = _runtime(True)
    be = SparseGrowingMemoryBackend(rt)
    torch.manual_seed(1)
    st = be.ingest_source(be.new_state(2), torch.randint(10000, 10800, (2, 10)), SourceRef("s"))
    rt.diag_read_offset = 6.0                       # push query reads off the bank
    try:
        res = be.evaluate_query(st, torch.randint(10000, 10800, (2, 1)), logits=False)
    finally:
        rt.diag_read_offset = 0.0
    query_anchor_loss([res["trace"]]).backward()
    grads = [p.grad for a in rt.adapters.values() for p in a.address_mlp.parameters()]
    assert any(g is not None and float(g.abs().sum()) > 0 for g in grads)
