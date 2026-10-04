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
def preflight(run_id: str, expected_source_sha256: str, previous_run_id: str = ""):
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
    stage = "numerics" if previous_run_id else "preflight"
    status = {"run_id": run_id, "phase": stage, "status": "running", "modal_task_id": os.environ.get("MODAL_TASK_ID")}

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
        if previous_run_id:
            from experiments.context_policy.numerics import run_numerics
            verdict = run_numerics(config, root, run_path(previous_run_id), artifacts.commit, deadline)
        else:
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


@app.function(image=image, gpu="H100!", cpu=4, memory=32768,
              volumes={"/artifacts": artifacts, "/root/.cache/huggingface": hf_cache},
              timeout=900, retries=0, max_containers=1, scaledown_window=2)
def data_pilot(run_id: str, expected_source_sha256: str, numerics_run_id: str):
    import hashlib
    import sys
    import time
    import traceback
    sys.path.insert(0, "/root/repo")
    from experiments.context_policy.preflight import canonical, digest, source_manifest
    from experiments.context_policy.prepare import run_data_pilot
    started = time.monotonic()
    root = run_path(run_id)
    if root.exists():
        raise FileExistsError("run already exists")
    source = source_manifest(Path('/root/repo'), remote=True)
    if digest(source) != expected_source_sha256:
        raise ValueError('source binding mismatch')
    root.mkdir(parents=True)
    config = json.loads(Path('/root/repo/experiments/context_policy/design.json').read_text())
    (root/'manifest.json').write_bytes(canonical({'source_files':source,'source_sha256':expected_source_sha256,'config':config,'numerics_run_id':numerics_run_id}))
    def deadline():
        if time.monotonic()-started >= 870:
            raise TimeoutError('development pilot 15-minute ceiling')
    try:
        verdict = run_data_pilot(config, root, run_path(numerics_run_id), artifacts.commit, deadline)
        state = 'awaiting_local_audit' if verdict['automated_dialogue_gate_passed'] and verdict['generation_alone_fits_preparation_ceiling'] else 'data_pilot_failed'
        result = {'run_id':run_id,'phase':'data_pilot','status':state,'elapsed_seconds':time.monotonic()-started,'verdict':verdict}
        hashes = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()}
        (root/'artifact-hashes.json').write_bytes(canonical(hashes))
        (root/'status.json').write_bytes(canonical(result));artifacts.commit()
        return result
    except BaseException as exc:
        (root/'error.txt').write_text(traceback.format_exc())
        (root/'status.json').write_bytes(canonical({'run_id':run_id,'status':'failed','phase':'data_pilot','elapsed_seconds':time.monotonic()-started,'error':str(exc)}))
        artifacts.commit()
        raise


@app.local_entrypoint()
def main(run_id: str, previous_run_id: str = "", prepare_data: bool = False, repair_pilot: bool = False, repair_revision: int = 1):
    import sys
    sys.path.insert(0, str(Path.cwd()))
    from experiments.context_policy.preflight import canonical, digest, source_manifest
    if repair_revision not in (1, 2, 3, 4) or (repair_revision != 1 and not repair_pilot) or (prepare_data and repair_pilot):
        raise ValueError('invalid or conflicting pilot mode')
    source = source_manifest(Path.cwd())
    local = Path("plans/260910-context-policy") / run_id
    local.mkdir(parents=True, exist_ok=False)
    launch = {"run_id": run_id, "app_id": app.app_id, "source_files": source, "source_sha256": digest(source), "stage": "repair_pilot" if repair_pilot else "data_pilot" if prepare_data else "numerics" if previous_run_id else "preflight", "previous_run_id": previous_run_id}
    # Snapshot before launch, so later implementation cannot erase run provenance.
    for name in source:
        target = local / "source-snapshot" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(name).read_bytes())
    (local / "launch.json").write_bytes(canonical(launch))
    if repair_pilot:
        import hashlib
        input_path = Path("data/context-policy/personamem-v2/repair-v1/pilot-reader-input.json")
        input_sha = hashlib.sha256(input_path.read_bytes()).hexdigest()
        launch["reader_input_sha256"] = input_sha
        launch['repair_revision'] = repair_revision
        call = repaired_data_probe.spawn(run_id, digest(source), previous_run_id, input_sha, repair_revision)
    else:
        call = data_pilot.spawn(run_id, digest(source), previous_run_id) if prepare_data else preflight.spawn(run_id, digest(source), previous_run_id)
    launch["function_call_id"] = call.object_id
    (local / "launch.json").write_bytes(canonical(launch))
    print("LAUNCHED " + json.dumps(launch), flush=True)
    result = call.get()
    (local / "remote-status.json").write_bytes(canonical(result))
    print("RESULT " + json.dumps(result), flush=True)


@app.function(image=image.add_local_file(
    "data/context-policy/personamem-v2/repair-v1/pilot-reader-input.json", "/root/repair-pilot-reader-input.json"),
    gpu="H100!", cpu=4, memory=32768,
    volumes={"/artifacts": artifacts, "/root/.cache/huggingface": hf_cache},
    timeout=900, retries=0, max_containers=1, scaledown_window=2)
def repaired_data_probe(run_id: str, expected_source_sha256: str, numerics_run_id: str, input_sha256: str, repair_revision: int = 1):
    import hashlib
    import sys
    import time
    import traceback
    sys.path.insert(0, "/root/repo")
    from experiments.context_policy.preflight import canonical, digest, source_manifest
    if repair_revision == 1:
        from experiments.context_policy.repair_pilot import run
    elif repair_revision in (2, 3, 4):
        from experiments.context_policy.repair_v2 import run
        if repair_revision in (3, 4):
            from functools import partial
            run = partial(run, ranked_notes=True, constrained_notes=repair_revision == 4)
    else:
        raise ValueError('unknown repair revision')
    started = time.monotonic()
    root = run_path(run_id)
    if root.exists():
        raise FileExistsError("run already exists; no automatic retry")
    source = source_manifest(Path("/root/repo"), remote=True)
    if digest(source) != expected_source_sha256:
        raise ValueError("source binding mismatch")
    data = Path("/root/repair-pilot-reader-input.json").read_bytes()
    if hashlib.sha256(data).hexdigest() != input_sha256:
        raise ValueError("reader input binding mismatch")
    previous = json.loads((run_path(numerics_run_id)/"status.json").read_text())
    if previous["verdict"].get("selected_runtime") != "fp32_math" or not previous["verdict"]["pass"]:
        raise ValueError("required numerical preflight has not passed")
    config = json.loads(Path("/root/repo/experiments/context_policy/design.json").read_text())
    root.mkdir(parents=True)
    (root/"manifest.json").write_bytes(canonical({"source_files": source, "source_sha256": expected_source_sha256,
        "reader_input_sha256": input_sha256, "config": config, "numerics_run_id": numerics_run_id,
        "stage": "ten_question_repaired_reference_diagnostic", "repair_revision": repair_revision,
        "no_reference_answers_mounted": True}))
    def deadline():
        if time.monotonic()-started >= 850:
            raise TimeoutError("15-minute repair diagnostic ceiling; reserving artifact save time")
    result = {"run_id": run_id, "status": "starting"}
    try:
        result = run(config, json.loads(data), root, artifacts.commit, deadline)
        result.update(run_id=run_id, elapsed_seconds=time.monotonic()-started)
        return result
    except BaseException as exc:
        (root/"error.txt").write_text(traceback.format_exc())
        result = {"run_id": run_id, "status": "failed", "error": str(exc), "elapsed_seconds": time.monotonic()-started}
        raise
    finally:
        hashes = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in root.rglob("*") if p.is_file() and p.name not in ("artifact-hashes.json", "status.json")}
        (root/"artifact-hashes.json").write_bytes(canonical(hashes))
        (root/"status.json").write_bytes(canonical(result))
        artifacts.commit()
