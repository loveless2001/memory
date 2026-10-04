"""Bounded ContextGate v1 capture, controller training, and held-out replay.

Run from repository root:
  .venv/bin/modal run --detach modal-runners/modal-context-gate.py --run-id <unique-id>
Read artifacts without starting a GPU:
  .venv/bin/modal run modal-runners/modal-context-gate.py::inspect --run-id <id>
"""

import json
import re
from pathlib import Path

import modal

app = modal.App("memsub-context-gate-v1")
PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy==2.2.6", "scikit-learn==1.5.2"]
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install(*PINNED)
         .env({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
         .add_local_dir("memsub", "/root/repo/memsub", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_dir("experiments/context_gate", "/root/repo/experiments/context_gate", ignore=["**/__pycache__/**", "**/*.pyc"])
         .add_local_file("CONTEXT-GATE.md", "/root/repo/CONTEXT-GATE.md")
         .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
         .add_local_file("modal-runners/modal-context-gate.py", "/root/repo/modal-context-gate.py"))
artifacts = modal.Volume.from_name("memsub-artifacts")
hf_cache = modal.Volume.from_name("memsub-hf-cache")


def run_path(run_id):
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", run_id) is None:
        raise ValueError("run_id must be a short lowercase identifier")
    return Path("/artifacts/context-gate-v1") / run_id


@app.function(image=image, gpu="H100!", cpu=4, memory=32768,
              volumes={"/artifacts": artifacts, "/root/.cache/huggingface": hf_cache},
              timeout=7200, retries=0, max_containers=1)
def campaign(run_id: str, expected_source_sha256: str) -> dict:
    import hashlib
    import os
    import sys
    import time
    import traceback

    sys.path.insert(0, "/root/repo")
    from experiments.context_gate.data import audit_dataset, build_dataset, canonical, digest
    from experiments.context_gate.capture import FrozenReader, capture_rows, sequential_replay, smoke_verdict
    from experiments.context_gate.learning import train_and_evaluate
    from experiments.context_gate.provenance import source_manifest

    started = time.monotonic()
    root = run_path(run_id)
    if root.exists():
        raise FileExistsError("run namespace already exists; inspect artifacts before resubmitting")
    config = json.loads(Path("/root/repo/experiments/context_gate/config.json").read_text())
    source = source_manifest(Path("/root/repo"), remote=True)
    if digest(source) != expected_source_sha256:
        raise ValueError("remote source bytes do not match the prelaunch local manifest")
    root.mkdir(parents=True)
    status = {"run_id": run_id, "status": "starting", "phase": "manifest", "elapsed_seconds": 0,
              "modal_task_id": os.environ.get("MODAL_TASK_ID"), "modal_image_id": os.environ.get("MODAL_IMAGE_ID")}

    def save_status(phase, state="running", **extra):
        status.update(phase=phase, status=state, elapsed_seconds=time.monotonic()-started, **extra)
        (root / "status.json").write_bytes(canonical(status))
        artifacts.commit()
        print(json.dumps(status), flush=True)

    def check_time():
        if time.monotonic()-started > config["gpu_seconds_limit"]:
            raise TimeoutError("internal campaign GPU-time cutoff reached")

    try:
        rows = build_dataset(config)
        smoke = build_dataset(config, smoke=True)
        assert {r["episode_id"] for r in rows}.isdisjoint(r["episode_id"] for r in smoke)
        manifest = {"run_id": run_id, "config": config, "source_files": source,
                    "source_sha256": expected_source_sha256, "dataset_sha256": digest(rows),
                    "smoke_sha256": digest(smoke), "split_audit": audit_dataset(rows)}
        (root / "manifest.json").write_bytes(canonical(manifest))
        (root / "dataset.jsonl").write_bytes(b"".join(canonical(r) for r in rows))
        (root / "preregistration.md").write_bytes(Path("/root/repo/CONTEXT-GATE.md").read_bytes())
        save_status("load_model")
        reader = FrozenReader(config)
        (root / "reader.json").write_bytes(canonical(reader.metadata))
        # Warmup excluded from per-prompt timing, included in campaign elapsed cost.
        reader.infer(smoke[:2], "notes", hidden=True)
        save_status("smoke")
        smoke_start = time.monotonic()
        smoke_cap = capture_rows(reader, smoke, root / "smoke", artifacts.commit, check_time)
        verdict = smoke_verdict(smoke, smoke_cap, time.monotonic()-smoke_start, config, time.monotonic()-started)
        (root / "smoke-verdict.json").write_bytes(canonical(verdict))
        print("SMOKE " + json.dumps(verdict), flush=True)
        if not verdict["pass"]:
            save_status("smoke", "smoke_failed", smoke=verdict)
            return status
        save_status("capture")
        cap = capture_rows(reader, rows, root / "capture", artifacts.commit, check_time)
        assert cap["item_ids"].tolist() == [r["item_id"] for r in rows]
        check_time()
        save_status("train")
        results = train_and_evaluate(rows, cap, config, root)
        (root / "results.json").write_bytes(canonical(results))
        artifacts.commit()
        if results["status"] != "trained":
            save_status("train", results["status"])
            return status
        check_time()
        save_status("replay")
        replay = sequential_replay(reader, rows, cap, config, root, artifacts.commit, check_time)
        check_time()
        status["verdict"] = results["verdict"]
        status["comparator"] = results["frozen_policy"]["comparator"]
        status["trained_controllers"] = list(results["training"])
        status["test_accuracy"] = results["evaluation"]["test"]["arms"]["hidden_mlp"]["accuracy"]
        status["replay_rows_per_arm"] = replay["rows_per_arm"]
        # Manifest hashes cover all durable scientific artifacts, not the mutable status.
        hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(root.rglob("*")) if p.is_file() and p.name not in ("status.json", "artifact-hashes.json")}
        (root / "artifact-hashes.json").write_bytes(canonical(hashes))
        save_status("done", "complete")
        return status
    except BaseException as exc:
        (root / "error.txt").write_text(traceback.format_exc())
        save_status(status["phase"], "failed", error=f"{type(exc).__name__}: {exc}")
        raise


@app.function(image=modal.Image.debian_slim(python_version="3.12"), volumes={"/artifacts": artifacts}, timeout=60)
def inspect(run_id: str) -> dict:
    root = run_path(run_id)
    return {name: json.loads((root / name).read_text()) for name in
            ("status.json", "smoke-verdict.json", "frozen-policy.json", "replay-summary.json") if (root / name).exists()}


@app.local_entrypoint()
def main(run_id: str):
    import sys
    sys.path.insert(0, str(Path.cwd()))
    from experiments.context_gate.data import canonical, digest
    from experiments.context_gate.provenance import source_manifest

    source = source_manifest(Path.cwd())
    local = Path("plans/260910-context-gate") / run_id
    local.mkdir(parents=True, exist_ok=False)
    launch = {"run_id": run_id, "source_files": source, "source_sha256": digest(source), "app_id": app.app_id}
    (local / "launch.json").write_bytes(canonical(launch))
    call = campaign.spawn(run_id, digest(source))
    launch["function_call_id"] = call.object_id
    (local / "launch.json").write_bytes(canonical(launch))
    print("LAUNCHED " + json.dumps(launch), flush=True)
    result = call.get()
    (local / "remote-status.json").write_bytes(canonical(result))
    print("RESULT " + json.dumps(result), flush=True)
