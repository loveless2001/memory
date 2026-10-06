"""Read-only evidence for P2.5 prereg v0.1 audit; no model forward or training."""
import hashlib
import importlib.metadata
import json
import math
import statistics
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".json")
PREREG = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/prereg.md"
COMMIT = "59ca18d"
REVISION = "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"
CACHE = Path.home() / ".cache/huggingface/hub/models--Qwen--Qwen3-0.6B-Base/snapshots" / REVISION


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        while block := f.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def paired(learned, control):
    d = [a - b for a, b in zip(learned, control)]
    mean = statistics.mean(d)
    hw = 1.96 * statistics.stdev(d) / math.sqrt(len(d))
    return {"diff": mean, "lo": mean - hw, "hi": mean + hw, "n": len(d)}


def main():
    frozen = subprocess.check_output(["git", "show", COMMIT + ":" + PREREG], cwd=ROOT)
    h = hashlib.sha256(frozen).hexdigest()
    assert h == "53aae9c31e48bc51bd65b6c288dec81bc8fc1aef95dea607dae24b39d38e3ae0"
    config = json.loads((CACHE / "config.json").read_text())
    assert (config["num_hidden_layers"], config["hidden_size"], config["vocab_size"]) == (28, 1024, 151936)
    weight = CACHE / "model.safetensors"
    with weight.open("rb") as f:
        header = json.loads(f.read(struct.unpack("<Q", f.read(8))[0]))
    parameter_count = sum(math.prod(v["shape"]) for k, v in header.items() if k != "__metadata__")
    import torch
    gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                                   "--format=csv,noheader"], text=True).strip()
    learned = [.5] * 256
    controls = {"higher_mean": [.25] * 52 + [.5] * 204,
                "lower_mean": [1.] * 114 + [0.] * 142}
    counterexample = {}
    for name, values in controls.items():
        result = paired(learned, values)
        counterexample[name] = {"control_accuracy": statistics.mean(values),
                               "paired": result, "gain_pass": result["diff"] >= .05 and result["lo"] > 0}
    assert counterexample["higher_mean"]["gain_pass"] is True
    assert counterexample["lower_mean"]["gain_pass"] is False
    assert counterexample["higher_mean"]["control_accuracy"] > counterexample["lower_mean"]["control_accuracy"]
    paths = ["memsub/sgm/synthetic_pilot.py", "memsub/sgm/synthetic_pilot_evaluation.py",
             "memsub/runtime/sgm_model_runtime.py", "memsub/sgm/synthetic_binding_task.py",
             "scripts/sgm-p2g-common-observer-evaluation.py", "scripts/sgm-p2g-decision-rules.py",
             "scripts/sgm-p2d-step2-decision-rules.py", "pyproject.toml",
             "plans/261005-0210-m4-sgm-p0-p2/m4-sgm-design-spec-v0.1.md"]
    source = {}
    for p in paths:
        frozen_source = subprocess.check_output(["git", "show", COMMIT + ":" + p], cwd=ROOT)
        source[p] = {"at_review_commit_sha256": hashlib.sha256(frozen_source).hexdigest(),
                     "current_sha256": sha(ROOT / p), "unchanged": frozen_source == (ROOT / p).read_bytes()}
    result = {
        "prereg_commit": COMMIT, "prereg_sha256": h, "prereg_clearance": "HOLD",
        "audit_model_forward_calls": 0, "audit_optimizer_updates": 0, "audit_paid_launches": 0,
        "model_revision": REVISION, "cached_config": config,
        "cached_config_sha256": sha(CACHE / "config.json"), "cached_weights_sha256": sha(weight),
        "cached_weights_bytes": weight.stat().st_size, "stored_parameter_count": parameter_count,
        "stored_weight_dtypes": sorted({v["dtype"] for k, v in header.items() if k != "__metadata__"}),
        "derived_fp32_weight_bytes": parameter_count * 4,
        "local_environment": {"torch": torch.__version__, "cuda_build": torch.version.cuda,
                              "cuda_available": torch.cuda.is_available(),
                              "transformers": importlib.metadata.version("transformers"), "gpu": gpu},
        "stronger_control_counterexample": {"type": "constructed arithmetic example, not model results",
            "episodes": 256, "queries_per_episode": 4, "learned_accuracy": .5,
            "construction": {"learned": {"0.5": 256}, "higher_mean": {"0.25": 52, "0.5": 204},
                             "lower_mean": {"1.0": 114, "0.0": 142}},
            "controls": counterexample, "same_construction_can_be_used_for_both_seeds": True},
        "review_source_bindings": source,
        "model_config_primary_source": "https://huggingface.co/Qwen/Qwen3-0.6B-Base/raw/" + REVISION + "/config.json",
        "fact_and_counterexample_checks_pass": True,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"prereg_clearance": result["prereg_clearance"], "fact_checks_pass": True,
                      "checks_sha256": sha(OUT), "counterexample": counterexample,
                      "local_environment": result["local_environment"]}, indent=2))


if __name__ == "__main__":
    main()
