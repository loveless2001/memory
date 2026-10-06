"""Amendment PK slot WORKER: one cell, one OS process (python -m memsub.sgm.packed_slot_worker <args.json>).

Runs the unchanged `run_pilot` for its cell with:
  * resume from the supervisor-selected generation (sha checked) or a fresh start;
  * on_checkpoint = write an immutable generation into THIS epoch's dir (tmp + fsync + rename),
    file a request, then BLOCK until the supervisor's ack (made durable by Volume.commit);
  * on_update = append the PHYSICAL update to attempt/physical-updates.jsonl;
  * proof mode only: per-logical-update loss + name-bound gradients to attempt/proof-capture/,
    and fault injection (exit at a physical update);
  * an `eval-phase` marker once training returned (final iteration done, artifact eval next);
  * on success: hashes of every output file in done.json (atomic).
A checked PR_SET_PDEATHSIG + parent check makes it die with its supervisor.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def arm_parent_death(expected_ppid: int) -> None:
    import ctypes
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if libc.prctl(1, 9, 0, 0, 0) != 0:                          # PR_SET_PDEATHSIG, SIGKILL
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_PDEATHSIG) failed")
    if os.getppid() != expected_ppid:
        raise SystemExit(f"parent {expected_ppid} already gone (ppid {os.getppid()})")


def atomic_json(path: Path, obj) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w") as f:
        f.write(json.dumps(obj, indent=2, sort_keys=True, default=str))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def wait_for(path: Path, timeout_s: float) -> None:
    t0 = time.monotonic()
    while not path.exists():
        if time.monotonic() - t0 > timeout_s:
            raise TimeoutError(f"no ack {path.name} within {timeout_s}s")
        time.sleep(0.05)


def install_proof_capture(out_dir: Path, spr, pilot):
    """Per logical update: loss + gradients keyed by parameter NAME (proof mode only)."""
    import torch
    out_dir.mkdir(parents=True, exist_ok=True)
    names, pending = {}, {}
    orig_build, orig_backward, orig_step = pilot.build, torch.Tensor.backward, torch.optim.AdamW.step

    def build(c):
        rt, backend, head = orig_build(c)
        names.update({id(p): f"adapters.{n}" for n, p in rt.adapters.named_parameters()})
        names.update({id(p): f"head.{n}" for n, p in head.named_parameters()})
        return rt, backend, head

    def backward(self, *a, **k):
        pending["loss"] = self.detach().double().cpu()
        return orig_backward(self, *a, **k)

    def step(self, *a, **k):
        pending["grads"] = {names[id(p)]: p.grad.detach().cpu().clone()
                            for g in self.param_groups for p in g["params"] if p.grad is not None}
        return orig_step(self, *a, **k)

    def flush(update: int) -> None:
        torch.save({"update": update, "loss": pending.pop("loss"), "grads": pending.pop("grads")},
                   out_dir / f"u{update:05d}.pt")
    pilot.build, torch.Tensor.backward, torch.optim.AdamW.step = build, backward, step
    return flush


def main(args_path: str) -> None:
    a = json.loads(Path(args_path).read_text())
    arm_parent_death(a["parent_pid"])
    import torch
    from memsub.sgm import synthetic_pilot as pilot
    from memsub.sgm import synthetic_pilot_run as spr
    from memsub.sgm.packed_slot_epoch_state import file_sha256
    from memsub.sgm.training_resume_checkpoint import load, save_atomic
    torch.set_num_threads(a["threads"])
    epoch_dir, attempt = Path(a["epoch_dir"]), Path(a["attempt_dir"])
    req = attempt / "requests"
    req.mkdir(parents=True, exist_ok=True)
    resume = None
    if a["resume_file"]:
        if file_sha256(Path(a["resume_file"])) != a["resume_sha256"]:
            raise SystemExit("resume generation sha mismatch")
        resume = load(Path(a["resume_file"]))
        if resume.get("step") != a["resume_step"]:              # metadata/payload mismatch: refuse
            raise SystemExit(f"continuity: generation payload step {resume.get('step')} != {a['resume_step']}")
    if a["mode"] == "eval_only" and (resume is None or resume["step"] != a["pilot_config"]["steps"]):
        raise SystemExit("eval_only needs the terminal generation")
    next_g = [a["next_g"]]
    flush = install_proof_capture(attempt / "proof-capture", spr, pilot) if a["proof_capture"] else None
    phys = open(attempt / "physical-updates.jsonl", "a")
    fault = a.get("fault") or {}

    def on_checkpoint(step: int, state: dict) -> None:
        g = next_g[0]
        next_g[0] += 1
        name = f"gen-{g}-step{step}.pt"
        save_atomic(state, epoch_dir / name)
        atomic_json(req / f"req-{g}.json", {"g": g, "step": step, "file": name,
                                            "sha256": file_sha256(epoch_dir / name)})
        wait_for(req / f"ack-{g}", a["ack_timeout_s"])          # no update past a non-durable generation

    def on_update(update: int, seconds: float) -> None:
        if flush is not None:
            flush(update)
        phys.write(json.dumps({"update": update, "seconds": seconds, "t_end": time.time()}) + "\n")
        phys.flush()
        if fault.get("exit_at_update") == update:
            os._exit(3)                                         # proof-mode worker fault

    real_train, real_evaluate, artifact = spr.train, spr.evaluate, {"on": False}

    def train_then_flag(*args, **kw):
        out = real_train(*args, **kw)
        artifact["on"] = True                                   # every later evaluate() is artifact eval
        return out

    def evaluate_logged(*args, **kw):
        out = real_evaluate(*args, **kw)
        if artifact["on"]:                                      # completed artifact-eval unit, then the marker
            with open(attempt / "artifact-eval-progress.jsonl", "a") as f:
                f.write(json.dumps({"split": kw.get("split"), "intervention": kw.get("intervention", "none"),
                                    "seed": kw.get("seed"), "batches": kw.get("batches"), "t": time.time()}) + "\n")
            (attempt / "eval-phase").touch()                    # INSIDE artifact eval with partial work done
        return out
    spr.train, spr.evaluate = train_then_flag, evaluate_logged
    ev = a["eval"]
    spr.run_pilot(pilot.PilotConfig(**a["pilot_config"]), attempt / "out",
                  final_batches=ev["final_batches"], final_batch_size=ev["final_batch_size"],
                  final_seed_base=ev["final_seed_base"], dev_seed=ev["dev_seed"],
                  train_eval_seed_base=ev["train_eval_seed_base"],
                  extra_manifest={"pk": {k: a[k] for k in ("cell", "epoch", "attempt", "mode")}},
                  resume=resume, on_checkpoint=on_checkpoint, on_update=on_update,
                  checkpoint_every=a["checkpoint_every"])
    phys.close()
    out = attempt / "out"
    atomic_json(attempt / "done.json", {"outputs": {str(p.relative_to(out)): file_sha256(p)
                                                    for p in sorted(out.rglob("*")) if p.is_file()}})


if __name__ == "__main__":
    main(sys.argv[1])
