"""P2.5 option A: a preempted training run resumed from its checkpoint reproduces the
uninterrupted run (tiny CPU backbone: bitwise), and resume refuses foreign configs."""

import json

import pytest
import torch

from memsub.sgm import synthetic_pilot_run as spr
from memsub.sgm.synthetic_pilot import PilotConfig, train
from memsub.sgm.training_resume_checkpoint import load

# curriculum switch at 3, eval at 0/3/6, fixed checkpoint at 4, crash after update 4
PCFG = dict(arm="learned", n_bindings=4, filler_len=4, steps=6, batch=2, eval_every=3, eval_batches=1,
            seed=99, checkpoint_steps=(4,), filler_len_schedule=((0, 0), (3, 4)))
TIMING = {"sec_per_step", "wall_seconds"}


class Preempted(RuntimeError):
    pass


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in TIMING}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def _outputs(d):
    out = {"metrics": _strip(json.loads((d / "metrics.json").read_text())),
           "telemetry": [_strip(json.loads(r)) for r in (d / "routing_telemetry.jsonl").read_text().splitlines()]}
    for f in sorted(d.glob("*.safetensors")) + sorted(d.glob("per_example_results*.jsonl")):
        out[f.name] = f.read_bytes()
    return out


def test_resumed_run_reproduces_uninterrupted_run(tmp_path, monkeypatch):
    spr.run_pilot(PilotConfig(**PCFG), tmp_path / "full", final_batches=1, final_batch_size=2)

    ckpt, real_train, saved = tmp_path / "train.ckpt", spr.train, []

    def crashing_train(*a, **k):
        def on_update(update, _s):
            if update == 4:
                raise Preempted("simulated preemption after update 4")
        inner = k["on_checkpoint"]
        k["on_checkpoint"] = lambda step, st: (saved.append(step), inner(step, st))
        k["on_update"] = on_update
        return real_train(*a, **k)
    monkeypatch.setattr(spr, "train", crashing_train)
    with pytest.raises(Preempted):
        spr.run_pilot(PilotConfig(**PCFG), tmp_path / "attempt1", final_batches=1, final_batch_size=2,
                      train_checkpoint=ckpt, checkpoint_every=2)
    assert saved == [2, 4] and load(ckpt)["step"] == 4

    monkeypatch.setattr(spr, "train", real_train)
    spr.run_pilot(PilotConfig(**PCFG), tmp_path / "resumed", final_batches=1, final_batch_size=2,
                  train_checkpoint=ckpt, checkpoint_every=2)
    assert json.loads((tmp_path / "resumed" / "run_manifest.json").read_text())["resumed_from_step"] == 4
    full, resumed = _outputs(tmp_path / "full"), _outputs(tmp_path / "resumed")
    assert full.keys() == resumed.keys()
    for k in full:
        assert full[k] == resumed[k], k


def test_resume_refuses_a_different_config():
    states = []
    train(PilotConfig(**PCFG), log=lambda _r: None, checkpoint_every=2,
          on_checkpoint=lambda _s, st: states.append(st))
    other = PilotConfig(**{**PCFG, "lr": 1e-3})
    with pytest.raises(ValueError, match="different PilotConfig"):
        train(other, log=lambda _r: None, resume=states[0])


def test_checkpoint_snapshot_is_detached_from_live_training():
    states = []
    train(PilotConfig(**PCFG), log=lambda _r: None, checkpoint_every=2,
          on_checkpoint=lambda _s, st: states.append(st))
    a, b = states[0]["adapters"], states[1]["adapters"]       # step 2 vs step 4: training moved on
    assert any(not torch.equal(a[k], b[k]) for k in a)


def test_terminal_generation_and_zero_update_eval_only_resume():
    """Amendment PK: a terminal state is offered at step == steps (before the final dev eval);
    resuming from it runs only the final iteration — zero optimizer updates — and reproduces
    the uninterrupted final weights and telemetry."""
    states, updates = {}, []
    full = train(PilotConfig(**PCFG), log=lambda _r: None, checkpoint_every=4,
                 on_checkpoint=lambda s, st: states.__setitem__(s, st))
    assert sorted(states) == [4, 6]                          # 6 = steps: terminal generation
    resumed = train(PilotConfig(**PCFG), log=lambda _r: None, resume=states[6],
                    on_update=lambda u, _s: updates.append(u))
    assert updates == []                                     # eval-only: no optimizer update
    for k, v in full["runtime"].adapters.state_dict().items():
        assert torch.equal(v, resumed["runtime"].adapters.state_dict()[k])
    assert resumed["telemetry"][:len(states[6]["telemetry"])] == states[6]["telemetry"]
    assert resumed["checkpoints"].keys() == full["checkpoints"].keys()
