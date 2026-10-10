"""Model-free measurement of the B3 retained-Volume size (proposal v0.3 open item; codex 22475/22479).

Builds the REAL B3 adapters (shift2, learned addresses, hidden 1024 x 28 layers = the pinned Qwen3 shape, given as a
config namespace: no weights are loaded) and the taskhead, materialises AdamW moments with one zero-grad step,
then serialises the REAL `training_state` (step 1500 = the terminal generation) with the REAL `save_atomic`, and
measures the file. Telemetry inside the state uses B2's retained eval rows as a same-schedule proxy.
Loader sentinel: any `from_pretrained` raises. Run inside a memory-capped systemd scope. Writes JSON only."""
import json, os, sys, tempfile, types
from pathlib import Path

import torch
from torch import nn

WT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WT))


def _sentinel(*a, **k):
    raise RuntimeError("MODEL LOAD ATTEMPTED")


import transformers  # noqa: E402
for cls in (transformers.PreTrainedModel, transformers.AutoModelForCausalLM, transformers.AutoModel):
    cls.from_pretrained = _sentinel

from memsub.sgm.config import SGMConfig  # noqa: E402
from memsub.sgm.layer_adapter import SGMLayerAdapter  # noqa: E402
from memsub.sgm.pinned_pretrained_qwen3_backbone import P2P5_SGM_DEFAULTS  # noqa: E402
from memsub.sgm.training_resume_checkpoint import save_atomic, training_state  # noqa: E402
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("b3_train", WT / "scripts/sgm-p2p5-b3-shift2-fill-long-run-train.py")
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)

base = json.loads((WT / "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/"
                         "probe-taskhead-learned-n32-s0-run_manifest.json").read_text())["pilot_config"]
pcfg = B.arm_config(base, "cpu")
assert pcfg.checkpoint_steps == () or list(pcfg.checkpoint_steps) == [], "fixed-endpoint snapshots would add size"
mc = types.SimpleNamespace(hidden_size=1024, num_hidden_layers=28, model_type="qwen3")
cfg = SGMConfig(**{**P2P5_SGM_DEFAULTS, **B.SGM_OVERRIDES, "address_mode": "learned"}).resolve(mc)
adapters = nn.ModuleDict({str(l): SGMLayerAdapter(cfg, l) for l in cfg.selected_layers})
head = nn.Linear(4 * 4 * 32, 64)                    # 4*4*32*64 + 64 head params (test_shift2_widens_..., codex 22479)
params = [*adapters.parameters(), *head.parameters()]
n_params = sum(p.numel() for p in params)
assert n_params == 3_744_604, n_params
opt = torch.optim.AdamW(params, lr=pcfg.lr, weight_decay=0.0)
for p in params:
    p.grad = torch.zeros_like(p)
opt.step()                                        # allocates exp_avg / exp_avg_sq for every parameter

b2_tele = WT / "plans/261009-1135-m4-sgm-p2p5-b2-occupied-fill-long-run/b2-resume-v1/volume/b2-run-v1/B2/routing_telemetry.jsonl"
telemetry = [json.loads(x) for x in b2_tele.read_text().splitlines() if x.strip()]
gen = torch.Generator().manual_seed(4242)
runtime = types.SimpleNamespace(adapters=adapters, device=torch.device("cpu"))
state = training_state(pcfg.steps, pcfg, runtime, head, opt, gen, telemetry, {})
state["b3_identity"] = {"proxy": "identity json (small)"}
with tempfile.TemporaryDirectory() as d:
    path = Path(d) / "resume.pt"
    save_atomic(state, path)
    resume_bytes = path.stat().st_size
fp32_params = n_params * 4
out = {"n_params": n_params, "fp32_params_bytes": fp32_params, "resume_pt_bytes": resume_bytes,
       "resume_pt_over_3x_params": round(resume_bytes / (3 * fp32_params), 4),
       "telemetry_rows_in_state_proxy": len(telemetry), "b2_routing_telemetry_bytes": b2_tele.stat().st_size,
       "checkpoint_steps": list(pcfg.checkpoint_steps), "torch": torch.__version__}
print(json.dumps(out, indent=1))
(Path(__file__).with_name("b3-retained-volume-size-measurement.json")).write_text(json.dumps(out, indent=1))
