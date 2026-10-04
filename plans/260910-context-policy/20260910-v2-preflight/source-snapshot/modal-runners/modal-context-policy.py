"""ContextPolicy v2 bounded GPU preflight. No automatic continuation or retry."""

import json
import re
from pathlib import Path

import modal

app = modal.App("memsub-context-policy-v2")
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
                      "peft==0.17.0", "accelerate==1.10.1", "numpy==2.2.6")
         .env({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
         .add_local_dir("experiments/context_policy", "/root/repo/experiments/context_policy", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_file("CONTEXT-POLICY.md", "/root/repo/CONTEXT-POLICY.md")
         .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
         .add_local_file("modal-runners/modal-context-policy.py", "/root/repo/modal-context-policy.py"))
artifacts = modal.Volume.from_name("memsub-artifacts")
hf_cache = modal.Volume.from_name("memsub-hf-cache")


def run_path(run_id):
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", run_id) is None:
        raise ValueError("invalid run ID")
    return Path("/artifacts/context-policy-v2") / run_id


@app.function(image=image, gpu="H100!", cpu=4, memory=32768,
              volumes={"/artifacts": artifacts, "/root/.cache/huggingface": hf_cache},
              timeout=900, retries=0, max_containers=1, scaledown_window=2)
def preflight(run_id: str, expected_source_sha256: str):
    import hashlib
    import os
    import sys
    import time
    import traceback
    sys.path.insert(0, "/root/repo")
    from experiments.context_policy.preflight import canonical, digest, source_manifest, run_preflight

    started = time.monotonic()
    root = run_path(run_id)
    if root.exists():
        raise FileExistsError("run already exists; no automatic resubmission")
    source = source_manifest(Path("/root/repo"), remote=True)
    if digest(source) != expected_source_sha256:
        raise ValueError("source binding mismatch")
    root.mkdir(parents=True)
    config = json.loads(Path("/root/repo/experiments/context_policy/design.json").read_text())
    (root / "manifest.json").write_bytes(canonical({"config": config, "source_files": source, "source_sha256": expected_source_sha256}))
    status = {"run_id": run_id, "phase": "preflight", "status": "running", "modal_task_id": os.environ.get("MODAL_TASK_ID")}

    def save(**values):
        status.update(values, elapsed_seconds=time.monotonic()-started)
        (root / "status.json").write_bytes(canonical(status))
        artifacts.commit()
        print(json.dumps(status), flush=True)

    def deadline():
        if time.monotonic()-started >= 870:
            raise TimeoutError("15-minute preflight ceiling; reserving time to save artifacts")

    save()
    try:
        verdict = run_preflight(config, root, artifacts.commit, deadline)
        hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(root.rglob("*")) if p.is_file() and p.name not in ("artifact-hashes.json", "status.json")}
        (root / "artifact-hashes.json").write_bytes(canonical(hashes))
        save(status="preflight_passed" if verdict["pass"] else "preflight_failed", verdict=verdict)
        return status
    except BaseException as exc:
        (root / "error.txt").write_text(traceback.format_exc())
        save(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise


@app.local_entrypoint()
def main(run_id: str):
    import sys
    sys.path.insert(0, str(Path.cwd()))
    from experiments.context_policy.preflight import canonical, digest, source_manifest
    source = source_manifest(Path.cwd())
    local = Path("plans/260910-context-policy") / run_id
    local.mkdir(parents=True, exist_ok=False)
    launch = {"run_id": run_id, "app_id": app.app_id, "source_files": source, "source_sha256": digest(source), "stage": "preflight"}
    (local / "launch.json").write_bytes(canonical(launch))
    call = preflight.spawn(run_id, digest(source))
    launch["function_call_id"] = call.object_id
    (local / "launch.json").write_bytes(canonical(launch))
    print("LAUNCHED " + json.dumps(launch), flush=True)
    result = call.get()
    (local / "remote-status.json").write_bytes(canonical(result))
    print("RESULT " + json.dumps(result), flush=True)
