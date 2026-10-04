"""Sparse cell banks — M4-SGM.md §5.1, §7.

One bank per (batch element, selected layer, memory head): a dict mapping
signed integer coordinates (ix, iy) -> FP32 matrix [key_dim, value_dim].

Invariants:
  * cells are runtime state, never nn.Parameters (optimizer identity is
    stable as the bank grows);
  * tensors are never mutated in place: a write replaces the dict entry with
    a new tensor, so a shallow dict copy is an alias-free fork that keeps the
    autograd graph (training) — `detached()` makes evaluation snapshots;
  * absent cells read as zero and are NOT allocated by reads;
  * a zero-weight write to an absent cell does not allocate;
  * a write that would exceed `max_cells` raises CapacityError before any
    cell of that call is modified.
No operation scans or copies the whole bank on the per-token path; only
`fork()` / `detached()` (per transaction / snapshot) touch every entry.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from ..errors import CapacityError

Coord = tuple[int, int]
BankKey = tuple[int, int, int]  # (batch, layer, head)


@dataclass
class BankCounters:
    cells_read: int = 0
    cells_written: int = 0
    cells_allocated: int = 0

    def copy(self) -> "BankCounters":
        return BankCounters(self.cells_read, self.cells_written, self.cells_allocated)


class SparseBankSet:
    def __init__(self, batch: int, layers: tuple[int, ...], heads: int,
                 key_dim: int, value_dim: int, max_cells: int,
                 device: torch.device | str = "cpu"):
        self.batch, self.layers, self.heads = batch, tuple(layers), heads
        self.key_dim, self.value_dim, self.max_cells = key_dim, value_dim, max_cells
        self.device = torch.device(device)
        self.cells: dict[BankKey, dict[Coord, torch.Tensor]] = {
            (b, l, h): {} for b in range(batch) for l in self.layers for h in range(heads)}
        self.counters = BankCounters()
        self._zero = torch.zeros(key_dim, value_dim, dtype=torch.float32, device=self.device)

    # -- transactions / snapshots ------------------------------------------------
    def fork(self) -> "SparseBankSet":
        """Alias-free branch that shares (immutable) tensors and keeps grads."""
        out = SparseBankSet.__new__(SparseBankSet)
        out.__dict__.update(self.__dict__)
        out.cells = {key: dict(bank) for key, bank in self.cells.items()}
        out.counters = self.counters.copy()
        return out

    def detached(self) -> "SparseBankSet":
        """Evaluation snapshot / documented truncation boundary: no graph."""
        out = self.fork()
        out.cells = {key: {c: t.detach() for c, t in bank.items()}
                     for key, bank in self.cells.items()}
        return out

    # -- access ----------------------------------------------------------------------
    def gather(self, layer: int, idx: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """idx [B, H, 9, 2] long -> (cells [B, H, 9, dk, dv], present [B, H, 9])."""
        coords = idx.tolist()
        tensors, present = [], []
        for b in range(self.batch):
            for h in range(self.heads):
                bank = self.cells[(b, layer, h)]
                for ix, iy in coords[b][h]:
                    cell = bank.get((ix, iy))
                    present.append(cell is not None)
                    tensors.append(self._zero if cell is None else cell)
        shape = (self.batch, self.heads, 9)
        stacked = torch.stack(tensors).view(*shape, self.key_dim, self.value_dim)
        mask = torch.tensor(present, dtype=torch.bool, device=self.device).view(shape)
        self.counters.cells_read += len(tensors)
        return stacked, mask

    def scatter(self, layer: int, idx: torch.Tensor, new_cells: torch.Tensor,
                weights: torch.Tensor) -> int:
        """Replace addressed cells with new_cells [B, H, 9, dk, dv]. Returns the
        number of newly allocated cells. Fails closed on capacity."""
        coords = idx.tolist()
        nonzero = (weights != 0).tolist()
        plan: list[tuple[dict, Coord, int]] = []
        for b in range(self.batch):
            for h in range(self.heads):
                bank = self.cells[(b, layer, h)]
                new_here = 0
                for c, (ix, iy) in enumerate(coords[b][h]):
                    key = (ix, iy)
                    if key not in bank:
                        if not nonzero[b][h][c]:
                            continue
                        new_here += 1
                    plan.append((bank, key, (b * self.heads + h) * 9 + c))
                if len(bank) + new_here > self.max_cells:
                    raise CapacityError(
                        f"bank (b={b}, layer={layer}, head={h}) would hold "
                        f"{len(bank) + new_here} > {self.max_cells} cells")
        flat = new_cells.reshape(-1, self.key_dim, self.value_dim)
        keep_graph = torch.is_grad_enabled() and flat.requires_grad
        allocated = 0
        for bank, key, row in plan:
            allocated += key not in bank
            # outside autograd, clone so dead write batches are not retained
            bank[key] = flat[row] if keep_graph else flat[row].clone()
        self.counters.cells_written += len(plan)
        self.counters.cells_allocated += allocated
        return allocated

    # -- telemetry ---------------------------------------------------------------------
    def occupancy(self) -> dict[BankKey, int]:
        return {key: len(bank) for key, bank in self.cells.items()}

    def total_cells(self) -> int:
        return sum(len(bank) for bank in self.cells.values())

    def neural_bytes(self) -> int:
        return self.total_cells() * self.key_dim * self.value_dim * 4
