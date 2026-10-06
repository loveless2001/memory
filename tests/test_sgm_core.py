"""M4-SGM core: interpolation, sparse banks, delta kernel (SGM-02/04/06/16)."""

from __future__ import annotations

import pytest
import torch

from memsub.errors import CapacityError, NonFiniteStateError
from memsub.sgm.delta_memory import delta_update, read_memory
from memsub.sgm.interpolation import stencil_1d, stencil_2d
from memsub.sgm.sparse_cell_bank import SparseBankSet


# -- SGM-02 -------------------------------------------------------------------------
def test_sgm02_stencil_weights_nonnegative_and_normalised():
    coords = torch.randn(500, 2) * 7
    idx, w = stencil_2d(coords)
    assert idx.shape == (500, 9, 2) and w.shape == (500, 9)
    assert (w >= 0).all()
    torch.testing.assert_close(w.sum(-1), torch.ones(500), atol=1e-6, rtol=0)
    assert len({tuple(c) for c in idx[0].tolist()}) == 9


def _dense_1d(x: float) -> dict[int, float]:
    idx, w = stencil_1d(torch.tensor([x], dtype=torch.float64))
    return {int(i): float(v) for i, v in zip(idx[0], w[0])}


def test_sgm02_continuous_and_c1_across_stencil_transitions():
    for edge in (-2.5, -0.5, 0.5, 3.5):
        lo, hi = _dense_1d(edge - 1e-9), _dense_1d(edge + 1e-9)
        for cell in set(lo) | set(hi):
            assert abs(lo.get(cell, 0.0) - hi.get(cell, 0.0)) < 1e-6
        # derivative continuity (C1): one-sided finite differences agree
        h = 1e-5
        d_lo = {c: (_dense_1d(edge - 1e-9).get(c, 0) - _dense_1d(edge - h).get(c, 0)) / h
                for c in set(lo) | set(hi)}
        d_hi = {c: (_dense_1d(edge + h).get(c, 0) - _dense_1d(edge + 1e-9).get(c, 0)) / h
                for c in set(lo) | set(hi)}
        for c in d_lo:
            assert abs(d_lo[c] - d_hi[c]) < 1e-3


def test_sgm02_finite_differences_away_from_boundaries():
    x = torch.tensor([[0.2, -1.3], [4.1, 7.9]], dtype=torch.float64, requires_grad=True)
    torch.autograd.gradcheck(lambda c: stencil_2d(c)[1], (x,))


# -- SGM-04 -------------------------------------------------------------------------
def _bank(max_cells=64, batch=1):
    return SparseBankSet(batch, (0,), 1, 2, 3, max_cells)


def test_sgm04_absent_reads_do_not_allocate_and_negative_distant_coords_work():
    bank = _bank()
    idx, w = stencil_2d(torch.tensor([[[-1000.2, 5000.4]]]))
    cells, present = bank.gather(0, idx)
    assert not present.any() and float(cells.abs().sum()) == 0
    assert bank.total_cells() == 0
    new = torch.ones_like(cells)
    assert bank.scatter(0, idx, new, w) == 9
    keys = set(bank.cells[(0, 0, 0)])
    assert keys == {tuple(c) for c in idx[0, 0].tolist()}
    assert min(k[0] for k in keys) <= -1000 and max(k[1] for k in keys) >= 5000


def test_sgm04_only_addressed_cells_change_and_zero_weight_never_allocates():
    bank = _bank()
    far = torch.zeros(1, 1, 9, 2, dtype=torch.long); far[..., 0] = torch.arange(100, 109)
    bank.scatter(0, far, torch.ones(1, 1, 9, 2, 3), torch.ones(1, 1, 9))
    before = dict(bank.cells[(0, 0, 0)])
    idx = torch.zeros(1, 1, 9, 2, dtype=torch.long); idx[..., 1] = torch.arange(9)
    w = torch.zeros(1, 1, 9); w[..., 4] = 1.0
    assert bank.scatter(0, idx, torch.full((1, 1, 9, 2, 3), 2.0), w) == 1
    after = bank.cells[(0, 0, 0)]
    assert all(after[k] is v for k, v in before.items())       # untouched objects
    assert (0, 4) in after and (0, 0) not in after


def test_sgm04_capacity_overflow_fails_before_any_cell_changes():
    bank = _bank(max_cells=5)
    idx, w = stencil_2d(torch.tensor([[[0.1, 0.1]]]))
    with pytest.raises(CapacityError):
        bank.scatter(0, idx, torch.ones(1, 1, 9, 2, 3), w)
    assert bank.total_cells() == 0


# -- SGM-06 -------------------------------------------------------------------------
def test_sgm06_delta_update_matches_explicit_reference():
    torch.manual_seed(0)
    cells = torch.randn(1, 1, 9, 4, 3); w = torch.rand(1, 1, 9); beta = torch.rand(1, 1)
    k = torch.nn.functional.normalize(torch.randn(1, 1, 4), dim=-1); v = torch.randn(1, 1, 3)
    new = delta_update(cells, w, beta, k, v)
    for c in range(9):
        S = cells[0, 0, c]
        err = v[0, 0] - S.T @ k[0, 0]
        ref = S + w[0, 0, c] * beta[0, 0] * torch.outer(k[0, 0], err)
        torch.testing.assert_close(new[0, 0, c], ref)
    q = k
    torch.testing.assert_close(read_memory(new, w, q)[0, 0],
                               sum(w[0, 0, c] * new[0, 0, c].T @ q[0, 0] for c in range(9)))


def test_sgm06_repeated_binding_overwrite_and_independent_keys():
    cells = torch.zeros(1, 1, 9, 4, 2)
    w = torch.zeros(1, 1, 9); w[..., 4] = 1.0
    one = torch.ones(1, 1)
    e = torch.eye(4)
    k1, k2 = e[0].view(1, 1, 4), e[1].view(1, 1, 4)
    v_a, v_b, v_c = (torch.tensor([[[1.0, 0.0]]]), torch.tensor([[[0.0, 1.0]]]),
                     torch.tensor([[[3.0, -2.0]]]))
    cells = delta_update(cells, w, one, k1, v_a)
    cells = delta_update(cells, w, one, k2, v_c)                 # independent key
    torch.testing.assert_close(read_memory(cells, w, k1)[0, 0], v_a[0, 0])
    cells = delta_update(cells, w, one, k1, v_b)                 # overwrite k1
    torch.testing.assert_close(read_memory(cells, w, k1)[0, 0], v_b[0, 0])
    torch.testing.assert_close(read_memory(cells, w, k2)[0, 0], v_c[0, 0])
    # partial strength: repeated writes converge geometrically
    cells = torch.zeros(1, 1, 9, 4, 2)
    for _ in range(30):
        cells = delta_update(cells, w, torch.full((1, 1), 0.3), k1, v_a)
    torch.testing.assert_close(read_memory(cells, w, k1)[0, 0], v_a[0, 0], atol=1e-4, rtol=0)


def test_sgm06_nonfinite_state_fails_closed():
    cells = torch.zeros(1, 1, 9, 2, 2)
    with pytest.raises(NonFiniteStateError):
        delta_update(cells, torch.ones(1, 1, 9), torch.ones(1, 1),
                     torch.tensor([[[1.0, 0.0]]]), torch.tensor([[[float("nan"), 0.0]]]))


# -- SGM-16 -------------------------------------------------------------------------
def test_sgm16_access_cost_independent_of_distant_bank_size():
    bank = SparseBankSet(1, (0,), 2, 2, 2, 100_000)
    idx, w = stencil_2d(torch.tensor([[[0.0, 0.0], [1.0, 1.0]]]))
    for far in range(0, 20_000, 9):                       # grow the bank far away
        coords = torch.zeros(1, 2, 9, 2, dtype=torch.long)
        coords[..., 0] = 10_000 + far + torch.arange(9)
        bank.scatter(0, coords, torch.ones(1, 2, 9, 2, 2), torch.ones(1, 2, 9))
    assert bank.total_cells() > 4000
    r0, w0 = bank.counters.cells_read, bank.counters.cells_written
    cells, _ = bank.gather(0, idx)
    bank.scatter(0, idx, cells + 1, w)
    assert bank.counters.cells_read - r0 == 2 * 9
    assert bank.counters.cells_written - w0 == 2 * 9


def test_no_grad_scatter_cells_own_their_storage():
    """P2.5 option A keeps the reference no-grad contract: each stored cell is its
    own clone (no shared write buffer; later input mutation cannot reach the bank)."""
    bank = _bank()
    idx, w = stencil_2d(torch.tensor([[[0.2, 0.3]]]))
    new = torch.ones(1, 1, 9, 2, 3)
    with torch.no_grad():
        bank.scatter(0, idx, new, w)
    new.add_(5.0)
    for cell in bank.cells[(0, 0, 0)].values():
        assert torch.equal(cell, torch.ones(2, 3))
        assert cell.untyped_storage().nbytes() == 2 * 3 * 4


def test_grad_scatter_keeps_graph_into_every_cell():
    bank = _bank()
    idx, w = stencil_2d(torch.tensor([[[0.2, 0.3]]]))
    new = torch.randn(1, 1, 9, 2, 3, requires_grad=True)
    bank.scatter(0, idx, new, w)
    cells, _ = bank.gather(0, idx)
    cells.sum().backward()
    assert torch.equal(new.grad, torch.ones_like(new))
