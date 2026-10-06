"""P2.5 CPU-vs-CUDA numerical tolerance check (prereg v0.2 § Implementation checks).

    .venv-gpu/bin/python scripts/sgm-p2p5-cpu-cuda-tolerance-check.py

Same seed, same CPU-sampled episodes, tiny random backbone and the pinned
Qwen3-0.6B-Base, both with the residual head: query logits after ingest and
the loss/gradient norm of one training-style backward must agree within FP32
tolerance (TF32 off). CPU and CUDA arithmetic are NOT claimed bitwise equal.
"""

import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memsub.sgm.synthetic_binding_task import sample_batch  # noqa: E402
from memsub.sgm.synthetic_pilot import PilotConfig, build  # noqa: E402
from memsub.sgm.synthetic_pilot_evaluation import ingest, query_logits  # noqa: E402

RTOL = ATOL = 1e-4


def run(device: str, backbone: str) -> dict:
    p = PilotConfig(arm="learned", readout="residual_head", backbone=backbone, device=device,
                    n_bindings=4, filler_len=4, batch=2, seed=0)
    runtime, backend, head = build(p)
    batch = sample_batch(p.task_spec(), "train", 2, torch.Generator().manual_seed(11))
    state = ingest(backend, batch, "learned", None, True, p.n_bindings)
    logits, _ = query_logits(backend, head, state, batch, 0, "learned", "residual_head", detach=False)
    loss = torch.nn.functional.cross_entropy(logits, batch.labels[:, 0].to(logits.device))
    loss.backward()
    grad = sum(float(q.grad.norm()) ** 2 for q in runtime.adapters.parameters() if q.grad is not None) ** 0.5
    return {"logits": logits.detach().cpu(), "loss": float(loss), "adapter_grad_norm": grad}


def main():
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    out = {}
    for backbone in ("tiny", "qwen3-0.6b-base"):
        cpu, gpu = run("cpu", backbone), run("cuda", backbone)
        diff = float((cpu["logits"] - gpu["logits"]).abs().max())
        ok = (torch.allclose(cpu["logits"], gpu["logits"], rtol=RTOL, atol=ATOL)
              and abs(cpu["loss"] - gpu["loss"]) <= ATOL + RTOL * abs(cpu["loss"])
              and abs(cpu["adapter_grad_norm"] - gpu["adapter_grad_norm"]) <= 1e-3 * cpu["adapter_grad_norm"])
        out[backbone] = {"max_abs_logit_diff": diff, "loss_cpu": cpu["loss"], "loss_cuda": gpu["loss"],
                         "grad_norm_cpu": cpu["adapter_grad_norm"], "grad_norm_cuda": gpu["adapter_grad_norm"],
                         "pass": ok}
        torch.cuda.empty_cache()
    print(json.dumps(out, indent=2))
    sys.exit(0 if all(v["pass"] for v in out.values()) else 1)


if __name__ == "__main__":
    main()
