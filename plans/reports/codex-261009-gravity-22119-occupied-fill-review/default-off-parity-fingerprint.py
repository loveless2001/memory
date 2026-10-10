"""Default-off parity fingerprint (CPU only). Usage: python -I THIS_FILE REPO_ROOT

Trains the tiny random backbone, learned addresses, taskhead, 4 updates with dev evals at 0/2/4, on
CPU with one thread, from the checkout at REPO_ROOT. Prints one JSON line: sha256 of the trained
adapter+head state, sha256 of the telemetry (sec_per_step removed), and the policy_id. Run it on the
pre-change commit and on the changed tree: equal lines = the fallback switch at its default "off"
changes no numbers, no telemetry key and no identity.
"""
import hashlib
import json
import os
import sys

os.environ["CUDA_VISIBLE_DEVICES"] = ""
sys.path.insert(0, sys.argv[1])
import torch  # noqa: E402

torch.set_num_threads(1)
from memsub.sgm.synthetic_pilot import PilotConfig, train  # noqa: E402
from memsub.sgm.synthetic_pilot_evaluation import evaluate  # noqa: E402

pcfg = PilotConfig(arm="learned", readout="taskhead", n_bindings=4, n_queries=2, filler_len=4, steps=4,
                   batch=4, eval_every=2, eval_batches=1, seed=0)


def ev(backend, head, step):
    return evaluate(backend, head, pcfg.task_spec(), pcfg.arm, pcfg.readout, split="heldout",
                    batches=1, batch_size=4, seed=4242)


res = train(pcfg, log=lambda _r: None, evaluate_fn=ev)
h = hashlib.sha256()
for mod in (res["runtime"].adapters, res["head"]):
    for k, v in sorted(mod.state_dict().items()):
        h.update(k.encode()); h.update(v.detach().cpu().contiguous().numpy().tobytes())
tele = [{k: v for k, v in r.items() if k != "sec_per_step"} for r in res["telemetry"]]
print(json.dumps({"params_sha256": h.hexdigest(),
                  "telemetry_sha256": hashlib.sha256(json.dumps(tele, sort_keys=True).encode()).hexdigest(),
                  "policy_id": res["policy_id"], "rows": len(tele)}, sort_keys=True))
