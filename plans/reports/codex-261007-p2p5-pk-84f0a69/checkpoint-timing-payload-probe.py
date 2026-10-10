"""CPU-only size comparison: real post-update checkpoint versus timing's fresh optimizer.

The ratio applies only to this tiny CPU fixture; it is not a GPU performance measurement.
"""
import io
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from memsub.sgm.synthetic_pilot import PilotConfig, train
from memsub.sgm.training_resume_checkpoint import training_state

states = {}
pcfg = PilotConfig(backbone="tiny", device="cpu", arm="learned", readout="residual_head",
                   n_bindings=4, filler_len=4, steps=6, batch=2, eval_every=1000000, eval_batches=1, seed=99)
res = train(pcfg, log=lambda r: None, checkpoint_every=2,
            on_checkpoint=lambda step, state: states.__setitem__(step, state))
opt = torch.optim.AdamW([p for p in list(res["runtime"].adapters.parameters()) + list(res["head"].parameters())
                        if p.requires_grad], lr=pcfg.lr)
proxy = training_state(pcfg.steps, pcfg, res["runtime"], res["head"], opt, torch.Generator(), [], {})


def size(state):
    buf = io.BytesIO()
    torch.save(state, buf)
    return buf.getbuffer().nbytes


result = {"fixture": "tiny CPU N4 filler4 batch2 seed99 steps6", "real_optimizer_states": len(states[6]["optimizer"]["state"]),
          "timing_pattern_optimizer_states": len(proxy["optimizer"]["state"]),
          "real_checkpoint_bytes": size(states[6]), "timing_pattern_checkpoint_bytes": size(proxy)}
result["ratio"] = result["real_checkpoint_bytes"] / result["timing_pattern_checkpoint_bytes"]
assert result["real_optimizer_states"] > 0 and result["timing_pattern_optimizer_states"] == 0
with Path(__file__).with_suffix(".json").open("x") as f:
    json.dump(result, f, indent=2)
    f.write("\n")
print(json.dumps(result, indent=2))
