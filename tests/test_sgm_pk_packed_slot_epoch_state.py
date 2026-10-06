"""Amendment PK §PK2 epoch-scoped cell state (codex 21553/21556/21558): authority, chain
binding, stale-writer immunity, terminal precedence, continuity refusals."""

import json

import pytest

from memsub.sgm import packed_slot_epoch_state as es

ID = {"memsub": "a", "runner": "b", "env": "c", "config": {"seed": 0}}


def _gen(cell, epoch, g, step, payload=None):
    d = es.epoch_dir(cell, epoch)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"gen-{g}-step{step}.pt"
    p.write_bytes(payload or f"{epoch}-{g}-{step}".encode())
    return p.name, es.file_sha256(p)


def _started(cell, epoch, admitted, steps=8):
    rec = es.inherit(cell, epoch, admitted, ID, steps)
    es.write_record(cell, rec)
    return rec


def _publish(cell, rec, g, step):
    name, sha = _gen(cell, rec["epoch"], g, step)
    es.add_generation(rec, g, step, name, sha)
    es.write_record(cell, rec)


@pytest.fixture
def cell(tmp_path):
    return tmp_path / "cells" / "learned-n32-s0"


def test_fresh_then_resume_chain(cell):
    r1 = _started(cell, 1, [1])
    assert r1["recovery"] == "fresh" and r1["state"] == es.STARTED
    _publish(cell, r1, 1, 2)
    _publish(cell, r1, 2, 4)
    r2 = es.inherit(cell, 2, [1, 2], ID, 8)
    assert r2["recovery"] == "resume" and es.resume_point(r2)["step"] == 4
    assert r2["inherited_from"]["epoch"] == 1


def test_started_without_generation_is_declared_replay(cell):
    _started(cell, 1, [1])
    r2 = es.inherit(cell, 2, [1, 2], ID, 8)
    assert r2["recovery"] == "replay_from_scratch" and r2["chain"] == []


def test_admitted_but_unacknowledged_epochs_are_new_by_recovery(cell):
    r3 = es.inherit(cell, 3, [1, 2, 3], ID, 8)              # epochs 1, 2 admitted, never acknowledged
    assert r3["recovery"] == "new_by_recovery" and r3["unacknowledged_epochs"] == [1, 2]


def test_newest_unacknowledged_admission_falls_back_to_last_acknowledged(cell):
    r1 = _started(cell, 1, [1])
    _publish(cell, r1, 1, 2)
    r3 = es.inherit(cell, 3, [1, 2, 3], ID, 8)              # epoch 2 admitted, died before acknowledging
    assert r3["inherited_from"]["epoch"] == 1 and es.resume_point(r3)["step"] == 2


def test_late_old_publication_after_handoff_cannot_change_newer_chain(cell):
    """Interleaving: epoch 1 'checks', epoch 2 takes over and acknowledges, then the stale
    epoch 1 publishes a later generation and edits its record. Epoch 3 must follow epoch 2."""
    r1 = _started(cell, 1, [1])
    _publish(cell, r1, 1, 2)
    stale = json.loads((es.epoch_dir(cell, 1) / "state.json").read_text())   # epoch 1's in-memory view
    r2 = _started(cell, 2, [1, 2])                                           # handoff acknowledged
    es.add_generation(stale, 2, 4, *_gen(cell, 1, 2, 4))                     # stale publication
    es.write_record(cell, stale)
    r3 = es.inherit(cell, 3, [1, 2, 3], ID, 8)
    assert r3["inherited_from"]["epoch"] == 2
    assert [link["step"] for link in r3["chain"]] == [2] == [link["step"] for link in r2["chain"]]


def test_newer_chain_is_a_copy(cell):
    r1 = _started(cell, 1, [1])
    _publish(cell, r1, 1, 2)
    r2 = _started(cell, 2, [1, 2])
    r1["chain"][0]["sha256"] = "tampered"                    # late in-place edit of the old record
    es.write_record(cell, r1)
    assert es.read_record(cell, 2)["chain"][0]["sha256"] != "tampered"


@pytest.mark.parametrize("terminal", [es.FAILED, es.LOST])
def test_failed_and_lost_are_terminal_across_restarts(cell, terminal):
    r1 = _started(cell, 1, [1])
    _publish(cell, r1, 1, 2)
    es.mark(r1, terminal, reason="worker exit 3")
    es.write_record(cell, r1)
    r2 = es.inherit(cell, 2, [1, 2], ID, 8)
    assert r2["state"] == terminal and r2["recovery"] == "terminal" and r2["reason"] == "worker exit 3"


def test_terminal_generation_trained_then_eval_only_then_complete(cell):
    r1 = _started(cell, 1, [1], steps=4)
    _publish(cell, r1, 1, 2)
    _publish(cell, r1, 2, 4)                                 # step == steps
    assert r1["state"] == es.TRAINED
    r2 = es.inherit(cell, 2, [1, 2], ID, 4)
    assert r2["state"] == es.TRAINED and r2["recovery"] == "eval_only"
    with pytest.raises(ValueError):
        es.add_generation(r2, 3, 6, "x", "y")               # no updates after TRAINED
    es.mark(r2, es.COMPLETE, outputs={"metrics.json": "h"})
    es.write_record(cell, r2)
    r3 = es.inherit(cell, 3, [1, 2, 3], ID, 4)
    assert r3["state"] == es.COMPLETE and r3["outputs"] == {"metrics.json": "h"}


def test_complete_requires_trained_and_terminal_is_final(cell):
    r1 = _started(cell, 1, [1])
    with pytest.raises(ValueError, match="TRAINED"):
        es.mark(r1, es.COMPLETE)
    es.mark(r1, es.FAILED, reason="x")
    with pytest.raises(ValueError, match="terminal"):
        es.mark(r1, es.LOST)


def test_continuity_refusals(cell):
    r1 = _started(cell, 1, [1])
    _publish(cell, r1, 1, 2)
    other = es.inherit(cell, 2, [1, 2], {**ID, "memsub": "z"}, 8)
    assert other["state"] == es.FAILED and "identity" in other["reason"]
    (es.epoch_dir(cell, 1) / r1["chain"][0]["file"]).write_bytes(b"corrupted")
    r2 = es.inherit(cell, 2, [1, 2], ID, 8)
    assert r2["state"] == es.FAILED and "sha mismatch" in r2["reason"]


def test_malformed_or_foreign_record_raises(cell):
    d = es.epoch_dir(cell, 1)
    d.mkdir(parents=True)
    (d / "state.json").write_text(json.dumps({"format": es.FORMAT, "epoch": 2, "cell": cell.name}))
    with pytest.raises(ValueError, match="foreign or malformed"):
        es.read_record(cell, 1)


def test_canonical_walk_uses_immutable_snapshots(cell):
    r1 = _started(cell, 1, [1])
    _publish(cell, r1, 1, 2)
    r2 = _started(cell, 2, [1, 2])
    _publish(cell, r2, 2, 4)
    r3 = _started(cell, 3, [1, 2, 3])
    es.mark(r1, es.FAILED, reason="late stale edit")            # old epoch mutated after handoff
    es.write_record(cell, r1)
    walk = es.canonical_walk(es.read_record(cell, 3), max_len=4)
    assert [r["epoch"] for r in walk] == [1, 2, 3] and walk[0]["state"] == es.STARTED   # snapshot, not the edit
    with pytest.raises(ValueError, match="longer"):
        es.canonical_walk(r3, max_len=2)


def test_canonical_walk_rejects_cycles_and_mismatched_links(cell):
    r1 = _started(cell, 1, [1])
    r2 = es.inherit(cell, 2, [1, 2], ID, 8)
    bad = json.loads(json.dumps(r2))
    bad["predecessor_snapshot"]["epoch"] = 2                    # not strictly decreasing
    with pytest.raises(ValueError, match="cyclic"):
        es.canonical_walk(bad, max_len=4)
    bad = json.loads(json.dumps(r2))
    bad["inherited_from"]["epoch"] = 7
    with pytest.raises(ValueError, match="inherited_from"):
        es.canonical_walk(bad, max_len=4)
    assert [r["epoch"] for r in es.canonical_walk(r2, 4)] == [1, 2] and r1["epoch"] == 1
