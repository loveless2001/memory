"""Makes geometry-index-v1.json for the Stage A post-hoc geometry pass (run from the repo root).

One `geometry` entry per Stage A arm whose stage_a_result.json is valid, at its update-100 final
parameters. The entry kind and loader are those of the cleared diagnosis script
(scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py, unchanged). Bindings: run_manifest,
routing_telemetry and trained parameters by sha256; the parameters must equal the manifest's
trained_parameters_sha256. The run block binds memsub/torch/transformers for .venv-gpu. Refuses an
existing index file (write-once).
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
import torch  # noqa: E402
import transformers  # noqa: E402
from memsub.sgm.synthetic_pilot_run import source_tree_sha256  # noqa: E402

P = Path("plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen")
RUN = P / "stage-a-run-v1"
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
dest = P / "geometry-index-v1.json"
if dest.exists():
    raise SystemExit(f"{dest} exists: write-once")
entries = []
for arm in ("A0", "A1", "A2"):
    d = RUN / arm
    res = d / "stage_a_result.json"
    if not res.exists() or json.loads(res.read_text()).get("status") != "valid":
        continue
    man, tel, prm = d / "run_manifest.json", d / "routing_telemetry.jsonl", d / "trained_parameters.safetensors"
    if sha(prm) != json.loads(man.read_text())["trained_parameters_sha256"]:
        raise SystemExit(f"{arm}: trained parameters differ from the manifest's sha")
    entries.append({"name": f"stage-a-{arm}-final-step100", "kind": "geometry", "manifest": str(man),
                    "manifest_sha256": sha(man), "telemetry": str(tel), "telemetry_sha256": sha(tel),
                    "params": str(prm), "params_sha256": sha(prm), "device": "cuda"})
if not entries:
    raise SystemExit("no valid Stage A arm: nothing to index")
run = {"memsub_source_sha256": source_tree_sha256(Path("memsub")), "torch": torch.__version__,
       "transformers": transformers.__version__}
dest.write_text(json.dumps({"run": run, "entries": entries}, indent=1))
print(len(entries), "entries", run)
