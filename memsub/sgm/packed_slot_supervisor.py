"""Amendment PK slot SUPERVISOR (the container's main process for one admitted start = epoch).

    1. reload; for every cell of the slot: inherit + write THIS epoch's record, then ONE
       commit -> acknowledge-before-work (an epoch without an acknowledged record did no work);
    2. launch one worker process per non-terminal cell (TRAINED -> eval_only, STARTED -> train
       from the chain's last generation, or a declared from-scratch replay / fresh start);
    3. loop: each worker generation request -> verify sha -> add to THIS epoch's record ->
       write -> commit -> ack (the worker blocks until the ack: <= C updates + in-flight lost);
       worker exit 0 + done.json -> validate output hashes -> COMPLETE -> write -> commit;
       worker exit != 0 -> FAILED -> write -> commit (co-tenant continues: policy, not immunity);
    4. liveness courtesy: a newer admitted start seen -> kill workers, write nothing more.
Proof-mode faults (never in campaign mode): container loss after a given ack, during a cell's
evaluation phase, or a worker exit at a physical update (passed to that worker).
`commit` / `reload` are injected (Modal Volume in the container; no-ops in local tests).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from . import packed_slot_epoch_state as es

REPO = Path(__file__).resolve().parents[2]


class ContainerFault(SystemExit):
    """Proof-mode simulated container loss (nonzero exit; the platform restarts the slot)."""


class Superseded(Exception):
    pass


def expand_cells(grid: dict) -> dict[str, dict]:
    """The registered universe: run id '{tag}-n{N}-s{seed}' -> PilotConfig kwargs (JSON form)."""
    cells = {}
    for block in grid["blocks"]:
        for n in block["n_bindings"]:
            for seed in block["seeds"]:
                cells[f"{block['tag']}-n{n}-s{seed}"] = {**grid["base"], **block.get("override", {}),
                                                        "n_bindings": n, "seed": seed}
    return cells


class SlotSupervisor:
    def __init__(self, *, root: Path, cells: dict[str, dict], epoch: int, admitted: list[int], identity: dict,
                 checkpoint_every: int, eval_cfg: dict, commit, reload, newer_start=lambda: False,
                 threads: int = 2, ack_timeout_s: float = 900.0, proof_capture: bool = False,
                 faults: dict | None = None, poll_s: float = 0.05, provenance: dict | None = None):
        self.root, self.cells, self.epoch, self.admitted = Path(root), cells, epoch, admitted
        self.identity, self.C, self.eval_cfg = identity, checkpoint_every, eval_cfg
        self.commit, self.reload, self.newer_start = commit, reload, newer_start
        self.threads, self.ack_timeout_s, self.proof_capture = threads, ack_timeout_s, proof_capture
        self.faults, self.poll_s = faults or {}, poll_s
        self.provenance = provenance or {}       # e.g. container id: recorded, never part of continuity
        self.records, self.procs, self.acked, self.finished = {}, {}, {}, set()
        self.fault_armed = False

    def cell_dir(self, cell: str) -> Path:
        return self.root / "cells" / cell

    def attempt_dir(self, cell: str) -> Path:
        return es.epoch_dir(self.cell_dir(cell), self.epoch) / "attempt-1"   # one attempt per epoch

    # -- phases ----------------------------------------------------------------------------
    def acknowledge(self) -> None:
        self.reload()
        for cell, pilot in self.cells.items():
            rec = es.inherit(self.cell_dir(cell), self.epoch, self.admitted, self.identity, pilot["steps"])
            prev = rec.get("history", [])
            rec["provenance"] = self.provenance
            rec["physical"] = {"observed_updates": 0, "last_observed_update": None,
                               "resume_step": es.resume_point(rec)["step"] if rec["chain"] else 0}
            if prev:     # the predecessor's unobserved physical tail is bounded, never counted exactly
                rec["physical"]["predecessor_unobserved_tail_bound_updates"] = self.C + 1
            es.write_record(self.cell_dir(cell), rec)
            self.records[cell] = rec
        self.commit()

    def launch(self) -> None:
        for cell, rec in self.records.items():
            if rec["state"] in es.TERMINAL:
                continue
            att = self.attempt_dir(cell)
            att.mkdir(parents=True, exist_ok=False)
            last = es.resume_point(rec)
            args = {"cell": cell, "epoch": self.epoch, "attempt": 1, "pilot_config": self.cells[cell],
                    "mode": "eval_only" if rec["state"] == es.TRAINED else "train",
                    "epoch_dir": str(es.epoch_dir(self.cell_dir(cell), self.epoch)), "attempt_dir": str(att),
                    "resume_file": str(es.epoch_dir(self.cell_dir(cell), last["epoch"]) / last["file"]) if last else None,
                    "resume_sha256": last["sha256"] if last else None, "next_g": (last["g"] + 1) if last else 1,
                    "checkpoint_every": self.C, "eval": self.eval_cfg, "parent_pid": __import__("os").getpid(),
                    "threads": self.threads, "ack_timeout_s": self.ack_timeout_s,
                    "proof_capture": self.proof_capture,
                    "fault": (self.faults.get("worker_exit") or {}).get(cell)}
            (att / "worker-args.json").write_text(json.dumps(args, indent=2))
            with open(att / "worker.log", "w") as log:
                self.procs[cell] = subprocess.Popen(
                    [sys.executable, "-u", "-m", "memsub.sgm.packed_slot_worker", str(att / "worker-args.json")],
                    stdout=log, stderr=subprocess.STDOUT, cwd=REPO)
            self.acked[cell] = set()

    def publish(self, cell: str, mutate) -> None:
        """Mutate THIS epoch's record for `cell`, write it and commit (liveness check first)."""
        if self.newer_start():
            raise Superseded(cell)
        mutate(self.records[cell])
        self.records[cell]["physical"].update(self.observed(cell))
        es.write_record(self.cell_dir(cell), self.records[cell])
        self.commit()

    def observed(self, cell: str) -> dict:
        path = self.attempt_dir(cell) / "physical-updates.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
        return {"observed_updates": len(rows), "last_observed_update": rows[-1]["update"] if rows else None}

    def serve_requests(self, cell: str) -> None:
        req = self.attempt_dir(cell) / "requests"
        for path in sorted(req.glob("req-*.json"), key=lambda p: int(p.stem.split("-")[1])):
            r = json.loads(path.read_text())
            if r["g"] in self.acked[cell]:
                continue
            gen = es.epoch_dir(self.cell_dir(cell), self.epoch) / r["file"]
            if es.file_sha256(gen) != r["sha256"]:
                raise RuntimeError(f"{cell}: generation {r['g']} sha mismatch")
            self.publish(cell, lambda rec: es.add_generation(rec, r["g"], r["step"], r["file"], r["sha256"]))
            (req / f"ack-{r['g']}").touch()
            self.acked[cell].add(r["g"])
            after = self.faults.get("after_ack") or {}
            if after.get("cell") == cell and after.get("step") == r["step"]:
                self.fault_armed = True        # fires once every `require_terminal` cell is acknowledged terminal

    def finish(self, cell: str, rc: int) -> None:
        att = self.attempt_dir(cell)
        if rc != 0:
            self.publish(cell, lambda rec: es.mark(rec, es.FAILED, reason=f"worker exit {rc}"))
            return
        done = json.loads((att / "done.json").read_text())
        bad = [f for f, h in done["outputs"].items() if es.file_sha256(att / "out" / f) != h]
        if bad or self.records[cell]["state"] != es.TRAINED:
            self.publish(cell, lambda rec: es.mark(rec, es.FAILED, reason=f"output validation: {bad or 'not TRAINED'}"))
            return
        outputs = {"attempt": str(att.relative_to(self.root)), "files": done["outputs"]}
        self.publish(cell, lambda rec: es.mark(rec, es.COMPLETE, outputs=outputs))

    def kill_all(self) -> None:
        for p in self.procs.values():
            if p.poll() is None:
                p.kill()
                p.wait()

    def run(self) -> dict:
        try:
            self.acknowledge()
            self.launch()
            during = (self.faults.get("during_eval") or {}).get("cell")
            while len(self.finished) < len(self.procs):
                for cell, p in self.procs.items():
                    if cell in self.finished:
                        continue
                    self.serve_requests(cell)
                    if during == cell and (self.attempt_dir(cell) / "eval-phase").exists():
                        raise ContainerFault(71)
                    need = (self.faults.get("after_ack") or {}).get("require_terminal", [])
                    if self.fault_armed and all(self.records[c]["state"] in es.TERMINAL for c in need):
                        raise ContainerFault(70)
                    rc = p.poll()
                    if rc is not None:
                        self.serve_requests(cell)
                        self.finish(cell, rc)
                        self.finished.add(cell)
                time.sleep(self.poll_s)
        except Superseded:
            self.kill_all()
            return {"status": "superseded", "states": {c: r["state"] for c, r in self.records.items()}}
        finally:
            self.kill_all()
        return {"status": "done", "states": {c: r["state"] for c, r in self.records.items()}}
