"""M4-SGM runtime + backend contracts (SGM-01/03/05/07/08/09/15/17)."""

from __future__ import annotations

import pytest
import torch

from memsub.errors import CapacityError, CompatibilityError
from memsub.runtime.sgm_model_runtime import SGMModelRuntime
from memsub.sgm.backend import SourceRef, SparseGrowingMemoryBackend
from memsub.sgm.config import SGMConfig
from memsub.sgm.synthetic_pilot import build_tiny_backbone

SRC = SourceRef("span-1")


def _backend(**kw) -> SparseGrowingMemoryBackend:
    cfg = SGMConfig(**{**dict(selected_layers=(1, 3), memory_heads=2, key_dim=8, value_dim=8,
                              address_hidden=16, local_recent_tokens=4096,
                              max_cells_per_bank=4096), **kw})
    return SparseGrowingMemoryBackend(SGMModelRuntime(build_tiny_backbone(0), cfg))


def _ids(n, start=1000, batch=1):
    return torch.arange(start, start + n).repeat(batch, 1)


# -- SGM-01 ---------------------------------------------------------------------------
def test_sgm01_disabled_adapter_reproduces_original_runtime(runtime):
    be = _backend()
    ids = list(range(2000, 2012))
    _, ref = runtime.prefill(ids)
    with torch.no_grad():
        st = be.ingest_source(be.new_state(), torch.tensor([ids[:-1]]), SRC, enabled=False)
        serial = be.evaluate_query(st, torch.tensor([ids[-1:]]), enabled=False, detach=True)
        block = be.evaluate_query(be.new_state(), torch.tensor([ids]), enabled=False, detach=True)
    torch.testing.assert_close(serial["logits"][0], ref, atol=1e-4, rtol=0)
    torch.testing.assert_close(block["logits"][0], ref, atol=1e-4, rtol=0)
    assert st.banks.total_cells() == 0


def test_sgm01_ingest_never_mutates_the_input_state():
    be = _backend()
    st0 = be.new_state()
    st1 = be.ingest_source(st0, _ids(6), SRC)
    assert st0.source_cursor == 0 and st0.banks.total_cells() == 0
    assert st0.recent_kv.physical_length == 0
    assert st1.source_cursor == 6 and st1.banks.total_cells() > 0


# -- SGM-03 / SGM-15 -----------------------------------------------------------------------
def test_sgm03_sgm15_gradients_reach_read_and_write_paths_not_backbone():
    be = _backend()
    rt = be.runtime
    params = list(rt.adapters.parameters())
    ids_before, n_before = [id(p) for p in params], len(params)
    st = be.ingest_source(be.new_state(), _ids(20), SRC)
    out = be.evaluate_query(st, _ids(1, start=1003))
    loss = out["reads"][3].pow(2).sum()           # loss ONLY on the last selected layer
    loss.backward()
    for layer in ("1", "3"):                      # layer 1 reached through frozen layers 2-3
        groups = rt.adapters[layer].param_groups()
        for name in ("qk_proj", "value", "beta", "address_mlp"):
            g = sum(float(p.grad.abs().sum()) for p in groups[name] if p.grad is not None)
            assert g > 0, (layer, name)
    assert all(p.grad is None for p in rt.backbone.parameters())
    assert all(not p.requires_grad for p in rt.backbone.parameters())
    assert [id(p) for p in rt.adapters.parameters()] == ids_before and n_before == len(params)


# -- SGM-05 -------------------------------------------------------------------------------
def test_sgm05_read_before_write_and_suffix_cannot_change_prefix_outputs():
    be = _backend(address_mode="oracle")
    rt = be.runtime
    addr = torch.zeros(1, 1, 2)                   # every token reads/writes the same cell
    def run(tokens):
        st, reads = be.new_state(), []
        with torch.no_grad():
            for t in tokens:
                out = rt.step(st, torch.tensor([[t]]), write=True,
                              oracle={"read": addr, "write": addr})
                reads.append(out["reads"][1].clone())
        return reads
    a, b = run([1000, 1001, 1002, 1003, 1004]), run([1000, 1001, 1002, 1777, 1888])
    assert float(a[0].abs().max()) == 0.0         # first token cannot read its own write
    assert float(a[1].abs().max()) > 0.0
    for t in range(3):                            # shared prefix: identical reads
        torch.testing.assert_close(a[t], b[t])


# -- SGM-07 -------------------------------------------------------------------------------
def test_sgm07_bounded_recent_kv_sinks_and_logical_positions():
    be = _backend(local_recent_tokens=8, pinned_sink_tokens=4)
    with torch.no_grad():
        st = be.ingest_source(be.new_state(), _ids(40), SRC)
    cache = st.recent_kv
    assert cache.physical_length == 4 + 8
    assert cache.logical_positions == [0, 1, 2, 3] + list(range(32, 40))
    assert cache.next_logical_position == 40 and cache.logical_offset == 28
    k, _ = cache.layer_kv(0)
    assert k.shape[2] == 12


# -- SGM-08 / SGM-09 -----------------------------------------------------------------------
def test_sgm08_queries_never_write_and_unauthorized_sources_rejected():
    be = _backend()
    st = be.ingest_source(be.new_state(), _ids(10), SRC)
    snapshot = {k: dict(v) for k, v in st.banks.cells.items()}
    cursor, phys = st.source_cursor, st.recent_kv.physical_length
    be.evaluate_query(st, _ids(5, start=3000))
    assert {k: dict(v) for k, v in st.banks.cells.items()} == snapshot
    assert (st.source_cursor, st.recent_kv.physical_length) == (cursor, phys)
    for kind in ("query", "gold_answer", "generated_answer", "probe_output"):
        with pytest.raises(PermissionError):
            be.ingest_source(st, _ids(3), SourceRef("x", kind=kind))


def test_sgm09_query_fork_retry_and_batch_isolation():
    be = _backend()
    with torch.no_grad():
        st = be.ingest_source(be.new_state(), _ids(12), SRC)
        q1 = be.evaluate_query(st, _ids(3, start=5000), detach=True)
        q2 = be.evaluate_query(st, _ids(3, start=5000), detach=True)
        torch.testing.assert_close(q1["logits"], q2["logits"])
        mixed = torch.stack([_ids(12)[0], _ids(12, start=7000)[0]])
        both = be.ingest_source(be.new_state(2), mixed, SRC)
    for key, bank in st.banks.cells.items():        # episode 0 unaffected by episode 1
        other = both.banks.cells[(0,) + key[1:]]
        assert bank.keys() == other.keys()
        for c in bank:
            torch.testing.assert_close(bank[c], other[c], atol=1e-5, rtol=0)


# -- SGM-17 -------------------------------------------------------------------------------
def test_sgm17_overflow_after_earlier_layer_wrote_rolls_back_everything():
    be = _backend(address_mode="oracle", max_cells_per_bank=12)
    st = be.new_state()
    for h in range(2):                              # layer 3 nearly full, layer 1 empty
        st.banks.cells[(0, 3, h)] = {(500 + i, 0): torch.zeros(8, 8) for i in range(10)}
    addr = torch.zeros(1, 3, 2)
    with pytest.raises(CapacityError):
        be.ingest_source(st, _ids(3), SRC, oracle_addresses=addr)
    assert st.banks.cells[(0, 1, 0)] == {} and st.source_cursor == 0
    assert st.recent_kv.physical_length == 0


def test_sgm17_late_span_overflow_commits_nothing():
    be = _backend(address_mode="oracle", max_cells_per_bank=18)
    st = be.ingest_source(be.new_state(), _ids(2), SRC, oracle_addresses=torch.zeros(1, 2, 2))
    cells_before, cursor = st.banks.total_cells(), st.source_cursor
    addr = torch.tensor([[[0.0, 0.0], [10.0, 0.0], [20.0, 0.0]]])   # 3rd token overflows
    with pytest.raises(CapacityError):
        be.ingest_source(st, _ids(3, start=1500), SRC, oracle_addresses=addr)
    assert st.banks.total_cells() == cells_before and st.source_cursor == cursor


# -- identity -----------------------------------------------------------------------------
def test_policy_identity_changes_and_mismatched_state_is_rejected():
    a, b = _backend(), _backend(address_scale=4.0)
    assert a.policy_id != b.policy_id
    with pytest.raises(CompatibilityError):
        b.evaluate_query(a.new_state(), _ids(1))
