"""Builds inputs-index.json for the taskhead dead-start address diagnosis (run from the repo root).
Refuses unless every .pt matches the acknowledged state.json chain and every final .safetensors matches
its run_manifest's trained_parameters_sha256. Telemetry (routing_telemetry.jsonl) is hash-bound too."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, ".")
import torch, transformers
from memsub.sgm.synthetic_pilot_run import source_tree_sha256
R = Path(__file__).parent
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
PR = ("plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe/p2p5-readout-probe-v1/taskhead-learned-n32/"
      "volume-evidence/collect-1/taskhead-learned-n32/cells/taskhead-learned-n32-s{s}/epoch-1")
P25 = ("plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-qwen3-0p6b-screen-v1/{arm}/volume-evidence/"
       "collect-1/{arm}/cells/{arm}-s0/epoch-{e}/attempt-1/out")
TOY = "plans/261005-0210-m4-sgm-p0-p2/runs/p2c-filler-curriculum-v1-volume-mirror/curriculum-learned-n32-s{s}"
entries = []


def add(name, kind, out_dir, params, device, bound=None, step=None):
    man, tel = f"{out_dir}/run_manifest.json", f"{out_dir}/routing_telemetry.jsonl"
    e = {"name": name, "kind": kind, "manifest": man, "manifest_sha256": sha(man),
         "telemetry": tel, "telemetry_sha256": sha(tel), "params": params, "device": device}
    if params != "init":
        e["params_sha256"] = sha(params)
        if e["params_sha256"] != bound:
            raise SystemExit(f"{name}: {params} sha != bound {bound}")
    if step is not None:
        e["expected_step"] = step
    entries.append(e)


final = lambda d: json.loads(Path(f"{d}/run_manifest.json").read_text())["trained_parameters_sha256"]
for s in (0, 1):
    d, out = PR.format(s=s), PR.format(s=s) + "/attempt-1/out"
    chain = {c["file"]: c["sha256"] for c in json.loads(Path(f"{d}/state.json").read_text())["chain"]}
    add(f"qwen-probe-taskhead-s{s}-init", "geometry", out, "init", "cuda")
    add(f"qwen-probe-taskhead-s{s}-step100", "geometry", out, f"{d}/gen-2-step100.pt", "cuda",
        chain["gen-2-step100.pt"], 100)
    add(f"qwen-probe-taskhead-s{s}-final", "geometry", out, f"{out}/trained_parameters.safetensors", "cuda", final(out))
for arm, ep in (("learned-n32", 1), ("oracle-n32", 2)):
    out = P25.format(arm=arm, e=ep)
    add(f"qwen-p2p5-{arm}-residual-s0-final", "geometry", out, f"{out}/trained_parameters.safetensors", "cuda",
        final(out))
for s in (0, 1):
    out = TOY.format(s=s)
    add(f"toy-p2c-curriculum-taskhead-s{s}-init", "geometry", out, "init", "cpu")
    add(f"toy-p2c-curriculum-taskhead-s{s}-final", "geometry", out, f"{out}/trained_parameters.safetensors", "cpu",
        final(out))
add("toy-p2c-curriculum-taskhead-s0-grad-at-init", "grad_at_init", TOY.format(s=0), "init", "cpu")
add("qwen-probe-taskhead-s0-grad-at-init", "grad_at_init", PR.format(s=0) + "/attempt-1/out", "init", "cuda")
run = {"memsub_source_sha256": source_tree_sha256(Path("memsub")), "torch": torch.__version__,
       "transformers": transformers.__version__}
(R / "inputs-index.json").write_text(json.dumps({"run": run, "entries": entries}, indent=1))
print(len(entries), "entries", run)
