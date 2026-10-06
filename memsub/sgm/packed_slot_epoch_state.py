"""Amendment PK §PK2 — per-cell durable state in epoch-scoped, write-once directories.

Layout under `<root>/cells/<cell>/`:
    epoch-<m>/state.json            written ONLY by admitted start m of the cell's slot
                                    (atomic replace; made durable by the caller's Volume.commit)
    epoch-<m>/gen-<g>-step<s>.pt    immutable checkpoint generations (written once)
    epoch-<m>/attempt-<a>/           run_pilot output dirs (never deleted)

No epoch writes into another epoch's directory, so a stale writer cannot overwrite or mix
into newer state (Modal Volumes are last-write-wins without locks). AUTHORITY for a cell at
start m = the highest admitted epoch < m with an acknowledged record. A new record COPIES
the predecessor's full chain of generations (epoch, g, step, file, sha256), so a late
mutation of an old epoch's state.json never changes a newer chain. It also stores an
IMMUTABLE SNAPSHOT of the whole predecessor record (`predecessor_snapshot`, recursively),
so the canonical chain is read from the authoritative record alone, never from mutable
older files (codex 21567 #3). Terminal states (COMPLETE / FAILED / LOST) are inherited
and never re-run.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

FORMAT = "m4-sgm-pk-cell-state-v1"
STARTED, TRAINED, COMPLETE, FAILED, LOST = "STARTED", "TRAINED", "COMPLETE", "FAILED", "LOST"
TERMINAL = (COMPLETE, FAILED, LOST)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def epoch_dir(cell_dir: Path, epoch: int) -> Path:
    return Path(cell_dir) / f"epoch-{epoch}"


def read_record(cell_dir: Path, epoch: int) -> dict | None:
    """The epoch's acknowledged record, or None (absent). A record that does not parse
    or has the wrong format/cell/epoch raises: it was written atomically, so damage is
    an error to surface, never a silent NEW."""
    path = epoch_dir(cell_dir, epoch) / "state.json"
    if not path.exists():
        return None
    rec = json.loads(path.read_text())
    if rec.get("format") != FORMAT or rec.get("epoch") != epoch or rec.get("cell") != Path(cell_dir).name:
        raise ValueError(f"foreign or malformed state record at {path}")
    return rec if rec.get("acknowledged") is True else None


def write_record(cell_dir: Path, rec: dict) -> None:
    """Atomic replace of THIS epoch's record (the caller commits the volume afterwards)."""
    d = epoch_dir(cell_dir, rec["epoch"])
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "state.json.tmp"
    with open(tmp, "w") as f:
        f.write(json.dumps(rec, indent=2, sort_keys=True))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, d / "state.json")


def select_authority(cell_dir: Path, admitted: list[int], before: int) -> tuple[int, dict] | None:
    """(epoch, record) of the highest admitted epoch < `before` with an acknowledged record."""
    for m in sorted((e for e in admitted if e < before), reverse=True):
        rec = read_record(cell_dir, m)
        if rec is not None:
            return m, rec
    return None


def verify_chain(cell_dir: Path, chain: list[dict]) -> str | None:
    """None if every generation of the chain exists with its bound sha256 and the steps
    strictly increase; else the problem."""
    last = 0
    for link in chain:
        path = epoch_dir(cell_dir, link["epoch"]) / link["file"]
        if not path.exists():
            return f"generation file missing: {path.name} (epoch {link['epoch']})"
        if file_sha256(path) != link["sha256"]:
            return f"generation sha mismatch: {path.name} (epoch {link['epoch']})"
        if link["step"] <= last:
            return "generation steps do not strictly increase"
        last = link["step"]
    return None


def inherit(cell_dir: Path, epoch: int, admitted: list[int], identity: dict, steps: int) -> dict:
    """The record admitted start `epoch` acknowledges for this cell BEFORE any work on it.
    recovery ∈ fresh | new_by_recovery | resume | replay_from_scratch | eval_only | terminal."""
    rec = {"format": FORMAT, "cell": Path(cell_dir).name, "epoch": epoch, "acknowledged": True,
           "identity": identity, "chain": [], "inherited_from": None, "history": [], "steps": steps}
    auth = select_authority(cell_dir, admitted, epoch)
    if auth is None:
        earlier = sorted(e for e in admitted if e < epoch)
        rec.update(state=STARTED, recovery="new_by_recovery" if earlier else "fresh",
                   unacknowledged_epochs=earlier)
        return rec
    m, prev = auth
    rec["inherited_from"] = {"epoch": m, "record_sha256": file_sha256(epoch_dir(cell_dir, m) / "state.json")}
    rec["predecessor_snapshot"] = copy.deepcopy(prev)              # immutable canonical chain
    rec["chain"] = [dict(link) for link in prev["chain"]]           # copied: immune to late old-epoch edits
    rec["history"] = list(prev.get("history", [])) + [{"epoch": m, "state": prev["state"]}]
    if prev["state"] in TERMINAL:
        rec.update({k: prev[k] for k in ("outputs", "reason") if k in prev})
        rec.update(state=prev["state"], recovery="terminal")
        return rec
    if prev["identity"] != identity:
        rec.update(state=FAILED, recovery="terminal", reason="continuity: identity differs from the predecessor")
        return rec
    problem = verify_chain(cell_dir, rec["chain"])
    if problem:
        rec.update(state=FAILED, recovery="terminal", reason=f"continuity: {problem}")
        return rec
    if prev["state"] == TRAINED:
        rec.update(state=TRAINED, recovery="eval_only")
    else:
        rec.update(state=STARTED, recovery="resume" if rec["chain"] else "replay_from_scratch")
    return rec


def add_generation(rec: dict, g: int, step: int, file: str, sha256: str) -> None:
    """Append this epoch's newly durable generation; the terminal step moves the cell to TRAINED."""
    if rec["state"] != STARTED:
        raise ValueError(f"cannot add a generation in state {rec['state']}")
    if rec["chain"] and step <= rec["chain"][-1]["step"]:
        raise ValueError("generation steps must strictly increase")
    rec["chain"].append({"epoch": rec["epoch"], "g": g, "step": step, "file": file, "sha256": sha256})
    if step == rec["steps"]:
        rec["state"] = TRAINED


def resume_point(rec: dict) -> dict | None:
    return rec["chain"][-1] if rec["chain"] else None


def mark(rec: dict, state: str, **fields) -> None:
    """Terminal transition (COMPLETE needs TRAINED; FAILED/LOST from any non-terminal state)."""
    if rec["state"] in TERMINAL:
        raise ValueError(f"cell already terminal ({rec['state']})")
    if state == COMPLETE and rec["state"] != TRAINED:
        raise ValueError("COMPLETE requires TRAINED")
    if state not in TERMINAL:
        raise ValueError(f"not a terminal state: {state}")
    rec.update(state=state, **fields)


def canonical_walk(rec: dict, max_len: int) -> list[dict]:
    """Oldest-first records along the predecessor SNAPSHOTS of an authoritative record;
    epochs strictly decrease along the links (acyclic) and the walk is at most `max_len`."""
    out = [rec]
    while out[0].get("predecessor_snapshot") is not None:
        prev = out[0]["predecessor_snapshot"]
        if prev.get("epoch") is None or prev["epoch"] >= out[0]["epoch"] or len(out) >= max_len:
            raise ValueError("predecessor chain is cyclic, non-decreasing or longer than the admitted starts")
        if out[0]["inherited_from"]["epoch"] != prev["epoch"]:
            raise ValueError("inherited_from does not match the predecessor snapshot")
        out.insert(0, prev)
    return out
